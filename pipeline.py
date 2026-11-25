#!/usr/bin/env python3
"""Provision and verify the Phase 1 BigQuery pipeline."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
from string import Template
import subprocess
import sys

from cloud_cli import cloud_command

SQL_DIR = Path(__file__).resolve().parent / "sql"
VIEWS = {
    "ads": ("ads_campaign_daily",),
    "search": ("search_site_daily", "search_query_page_daily"),
    "ga4": ("ga4_event_daily", "ga4_traffic_daily"),
}


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    rules = {
        "project": r"[a-z][a-z0-9-]{4,28}[a-z0-9]",
        "location": r"[a-zA-Z][a-zA-Z0-9-]{1,30}",
        "ga4_property_id": r"[1-9][0-9]{0,19}",
    }
    for key, pattern in rules.items():
        if not re.fullmatch(pattern, config[key]):
            raise ValueError(f"Geçersiz {key}")
    customer = config["ads_customer_id"]
    if not re.fullmatch(r"(?:[0-9]{10}|[0-9]{3}-[0-9]{3}-[0-9]{4})", customer):
        raise ValueError("Google Ads müşteri kimliği 10 haneli olmalı")
    config["ads_customer_id"] = customer.replace("-", "")
    datasets = config["datasets"]
    if set(datasets) != {"ads", "search", "reporting"} or any(
        not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,1023}", name) for name in datasets.values()
    ):
        raise ValueError("ads, search ve reporting için geçerli dataset adları girin")
    datasets["ga4"] = f'analytics_{config["ga4_property_id"]}'
    if len(set(datasets.values())) != len(datasets):
        raise ValueError("Dataset adları farklı olmalı")
    cap = config["maximum_bytes_billed"]
    if type(cap) is not int or cap <= 0:
        raise ValueError("maximum_bytes_billed pozitif tam sayı olmalı")
    events = config.get("ga4_key_events", [])
    if not isinstance(events, list) or any(
        not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,39}", event) for event in events
    ):
        raise ValueError("ga4_key_events geçerli GA4 etkinlik adlarının listesi olmalı")
    return config


class Pipeline:
    def __init__(self, config):
        self.config = config
        self.project = config["project"]
        self.location = config["location"]
        self.datasets = config["datasets"]
        self.customer = config["ads_customer_id"]
        self.refs = {key: f"{self.project}.{value}" for key, value in self.datasets.items()}
        for key, table in (("stats", "CampaignBasicStats"), ("campaign", "Campaign"), ("customer", "Customer")):
            self.refs[f"ads_{key}"] = f'{self.refs["ads"]}.ads_{table}_{self.customer}'
        events = config.get("ga4_key_events", [])
        self.refs["key_events"] = (
            f"COUNTIF(event_name IN UNNEST({json.dumps(events)}))" if events else "CAST(NULL AS INT64)"
        )

    def bq(self, *args, capture=True):
        cmd = [*cloud_command("bq"), f"--project_id={self.project}", f"--location={self.location}", *args]
        result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE if capture else None)
        return result.stdout

    def query(self, sql, *args, output_format="prettyjson"):
        return self.bq(
            "--quiet=true", f"--format={output_format}", "query", "--use_legacy_sql=false",
            f'--maximum_bytes_billed={self.config["maximum_bytes_billed"]}', *args, sql,
        )

    def render(self, name, **extra):
        return Template((SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")).substitute(
            self.refs, **extra
        ).strip()

    def check_location(self, source):
        raw = self.bq("--format=prettyjson", "show", "--dataset", f"{self.project}:{self.datasets[source]}")
        actual = json.loads(raw)["location"]
        if actual.casefold() != self.location.casefold():
            raise ValueError(f"{self.datasets[source]} konumu {actual}, beklenen {self.location}")

    def ads_transfer(self):
        raw = self.bq(
            "--format=prettyjson", "ls", "--transfer_config=true", f"--transfer_location={self.location}",
            "--max_results=1000",
        )
        transfers = json.loads(raw)
        if len(transfers) >= 1000:
            raise ValueError("Aktarım listesi sınırına ulaşıldı. Ads yapılandırmasını konsoldan kontrol edin.")
        matches = [
            item for item in transfers
            if item.get("dataSourceId") == "google_ads"
            and item.get("destinationDatasetId") == self.datasets["ads"]
            and str(item.get("params", {}).get("customer_id", "")).replace("-", "") == self.customer
        ]
        if len(matches) > 1:
            raise ValueError("Aynı Ads müşteri ve dataset için birden fazla aktarım var")
        if matches:
            if matches[0].get("disabled") or matches[0].get("scheduleOptions", {}).get("disableAutoScheduling"):
                raise ValueError("Mevcut Ads aktarımında otomatik zamanlama kapalı")
            return matches[0]["name"]
        return None

    def setup(self):
        subprocess.run(
            [*cloud_command("gcloud"), "services", "enable", "bigquery.googleapis.com", "bigquerydatatransfer.googleapis.com",
             f"--project={self.project}", "--quiet"],
            check=True,
        )
        for source in ("ads", "search", "reporting"):
            self.query(f"CREATE SCHEMA IF NOT EXISTS `{self.refs[source]}` OPTIONS(location={json.dumps(self.location)})")
            self.check_location(source)
        existing = self.ads_transfer()
        if existing:
            print(f"Mevcut Ads aktarımı: {existing}")
            return
        self.bq(
            "mk", "--transfer_config=true", "--data_source=google_ads",
            f'--target_dataset={self.datasets["ads"]}',
            f"--display_name=Marketing Google Ads {self.customer}",
            f'--params={json.dumps({"customer_id": self.customer})}',
            "--schedule=every 24 hours", "--refresh_window_days=7", capture=False,
        )

    def publish(self, source):
        self.check_location(source)
        self.check_location("reporting")
        for view in VIEWS[source]:
            sql = self.render(view)
            self.query(sql, "--dry_run=true")
        for view in VIEWS[source]:
            sql = self.render(view)
            self.query(f'CREATE OR REPLACE VIEW `{self.refs["reporting"]}.{view}` AS\n{sql}')
            print(f'{self.refs["reporting"]}.{view}')

    def audit(self, source, start, end):
        self.check_location(source)
        start_suffix = start.strftime("%y%m%d")
        end_suffix = end.strftime("%y%m%d")
        rows = json.loads(self.query(
            self.render(f"audit_{source}", start_suffix=start_suffix, end_suffix=end_suffix),
            f"--parameter=start:DATE:{start}", f"--parameter=end:DATE:{end}", "--max_rows=366",
        ))
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        if source == "ads":
            transfer = self.ads_transfer()
            if not transfer:
                raise ValueError("Bu müşteri ve dataset için Ads aktarımı bulunamadı")
            print(self.bq("--format=prettyjson", "ls", "--transfer_run=true", "--max_results=10", transfer))
        return all(row["coverage"] == "present" for row in rows) and len(rows) == (end - start).days + 1

    def plan(self):
        print(f"Proje {self.project} | BigQuery konumu {self.location}")
        print(f'Google Ads {self.customer} → {self.refs["ads"]} | günlük, 7 gün yenileme')
        print(f'Search Console → {self.refs["search"]} | Bulk data export, günlük')
        print(f'GA4 {self.config["ga4_property_id"]} → {self.refs["ga4"]} | Daily export')
        print(f'{self.refs["reporting"]} | ' + ", ".join(view for source in VIEWS.values() for view in source))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="Ağ çağrısı yapmadan yapılandırmayı göster")
    commands.add_parser("setup", help="API, dataset ve günlük Ads aktarımını oluştur")
    for command in ("publish", "audit"):
        sub = commands.add_parser(command)
        sub.add_argument("--source", choices=["all", *VIEWS], default="all")
        if command == "audit":
            sub.add_argument("--start", type=date.fromisoformat, required=True)
            sub.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)

    try:
        pipeline = Pipeline(load_config(args.config))
        if args.command == "plan":
            pipeline.plan()
            return 0
        for executable in ("gcloud", "bq") if args.command == "setup" else ("bq",):
            cloud_command(executable)
        if args.command == "setup":
            pipeline.setup()
            return 0
        if args.command == "audit" and not (
            date(2000, 1, 1) <= args.start <= args.end <= date(2099, 12, 31)
            and (args.end - args.start).days < 366
        ):
            raise ValueError("2000–2099 arasında en fazla 366 günlük bir tarih aralığı girin")

        sources = VIEWS if args.source == "all" else (args.source,)
        success = True
        for source in sources:
            print(f"\n[{source}]", flush=True)
            try:
                if args.command == "publish":
                    pipeline.publish(source)
                elif not pipeline.audit(source, args.start, args.end):
                    print("Tarih aralığındaki kapsama eksik veya belirsiz.", file=sys.stderr)
                    success = False
            except (subprocess.CalledProcessError, ValueError, KeyError) as error:
                print(f"{source}: {error}", file=sys.stderr)
                success = False
        return 0 if success else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
