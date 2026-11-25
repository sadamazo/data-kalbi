#!/usr/bin/env python3
"""Data Kalbi, a guided terminal app for the marketing warehouse."""
import csv
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
import webbrowser

from pipeline import Pipeline, VIEWS, load_config, main as pipeline_cli

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "data-kalbi"
DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "data-kalbi"
SETTINGS = CONFIG / "config.json"
EXAMPLE = Path(__file__).resolve().parent / "config.example.json"
SDK_INSTALLER = "https://sdk.cloud.google.com"
IAM_ACCOUNT = "search-console-data-export@system.gserviceaccount.com"

COLORS = {
    "rose": "38;5;211", "peach": "38;5;216", "lavender": "38;5;183",
    "mint": "38;5;121", "bold": "1",
}


def terminal_effects():
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def paint(value, color):
    if terminal_effects():
        return f"\033[{COLORS[color]}m{value}\033[0m"
    return value


def bird_banner(heartbeat=False, wink=False):
    width = 46
    heart = ("__  __", r"( \/  )", r"\    /", r" \  /") if heartbeat else (
        " _  _", r"( \/ )", r" \  /", r"  \/",
    )
    bird_left = "/   -_6" if wink else "/   6_6"
    birds = (
        f"               {heart[0]}",
        f"               {heart[1]}",
        f'        .---.  {heart[2]:7}  .-"-.',
        f"       {bird_left} {heart[3]:7} / 4 4 \\",
        r"       \_  (__\       \_ v _/",
        r"       //   \\        //   \\",
        r"      ((     ))      ((     ))",
        'jgs=====""===""========""===""=======',
        r"         |||            |||",
        r"          |              |",
    )
    border = paint("    ." + "-" * width + ".", "rose")
    rows = [border, *(paint(f"    |{line:^{width}}|", "rose") for line in ("", "D A T A   K A L B İ", ""))]
    art_color = "peach" if heartbeat else "rose"
    for line in birds:
        rows.append(paint("    |", "rose") + paint(f"    {line:<{width - 4}}", art_color) + paint("|", "rose"))
    rows.append(paint("    '" + "-" * width + "'", "rose"))
    return rows


def heading():
    rows = bird_banner()
    print("\n" + "\n".join(rows), flush=True)
    size = shutil.get_terminal_size()
    if terminal_effects() and size.columns >= 52 and size.lines >= len(rows) + 1:
        back = f"\033[{len(rows)}F"
        try:
            for delay, frame in ((0.24, bird_banner(heartbeat=True)), (0.20, bird_banner(wink=True)), (0.25, rows)):
                time.sleep(delay)
                print(back + "\n".join(frame), flush=True)
        except KeyboardInterrupt:
            print(back + "\n".join(rows), flush=True)


def ask(label, default=""):
    suffix = f" [{default}]" if default else ""
    return input(paint(f"  {label}{suffix} > ", "lavender")).strip() or default


def confirm(label):
    return ask(f"{label} (e/h)", "h").casefold() == "e"


def configure():
    previous = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    values = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    values.update(previous)
    print(paint("\n  <3  PROJE BİLGİLERİ", "rose"))
    print("  Cloud proje kimliğini ve Google hesap/mülk kimliklerini gir.")
    values["project"] = ask("Google Cloud proje kimliği", previous.get("project", ""))
    values["location"] = ask("BigQuery konumu", previous.get("location", "EU"))
    values["ads_customer_id"] = ask("Google Ads müşteri kimliği", previous.get("ads_customer_id", ""))
    values["search_console_property"] = ask(
        "Search Console mülkü, ör. sc-domain:example.com", previous.get("search_console_property", "")
    )
    values["ga4_property_id"] = ask("GA4 mülk kimliği", previous.get("ga4_property_id", ""))
    events = ", ".join(previous.get("ga4_key_events", []))
    values["ga4_key_events"] = [
        event.strip() for event in ask("GA4 anahtar etkinlikleri, virgülle ayır (isteğe bağlı)", events).split(",")
        if event.strip()
    ]
    prop = values["search_console_property"]
    if not prop.startswith(("sc-domain:", "https://", "http://")) or prop in ("sc-domain:", "http://", "https://"):
        raise ValueError("Search Console mülkünü sc-domain:example.com veya tam URL olarak gir.")
    CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        temporary.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        load_config(temporary)
        temporary.replace(SETTINGS)
    finally:
        temporary.unlink(missing_ok=True)
    print(paint("  <3  Proje bilgileri kaydedildi.", "mint"))


def sdk_path():
    managed = DATA / "google-cloud-sdk/bin"
    if (managed / "gcloud").is_file() and (managed / "bq").is_file():
        entries = os.environ.get("PATH", "").split(os.pathsep)
        if str(managed) not in entries:
            os.environ["PATH"] = os.pathsep.join([str(managed), *entries])


def require_sdk():
    sdk_path()
    if shutil.which("gcloud") and shutil.which("bq"):
        return
    if sys.platform not in ("darwin", "linux"):
        raise ValueError("Google Cloud CLI kurulumunu macOS veya Linux üzerinde aç.")
    print("  Google Cloud CLI gerekiyor. Google'ın resmi yükleyicisi indirilecek.")
    if not confirm("Google Cloud CLI bu uygulamanın klasörüne kurulsun mu?"):
        raise ValueError("Kuruluma devam etmek için gcloud ve bq gerekiyor.")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="data-kalbi-sdk-") as folder:
        installer = Path(folder) / "install.sh"
        subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
             SDK_INSTALLER, "--output", str(installer)],
            check=True,
        )
        subprocess.run(["bash", str(installer), "--disable-prompts", f"--install-dir={DATA}"], check=True)
    sdk_path()
    if not (shutil.which("gcloud") and shutil.which("bq")):
        raise ValueError("Google Cloud CLI kurulumu tamamlanamadı. Kurulum çıktısını kontrol et.")


def google_login():
    require_sdk()
    print(paint("\n  <3  Google giriş ekranı açılıyor.", "rose"), flush=True)
    subprocess.run(["gcloud", "auth", "login", "--force"], check=True)
    print(paint("  Google oturumu açıldı.", "mint"))


def require_login():
    require_sdk()
    active = subprocess.run(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not active:
        google_login()


def get_pipeline():
    if not SETTINGS.exists():
        raise ValueError("Önce 1 ile proje bilgilerini gir.")
    return Pipeline(load_config(SETTINGS))


def setup_cloud():
    pipe = get_pipeline()
    print(f"  Hedef proje {pipe.project} · {pipe.location}")
    print("  API'ler, dataset'ler ve günlük Google Ads aktarımı hazırlanacak.")
    if confirm("BigQuery kurulumunu başlatalım mı?"):
        require_login()
        pipe.setup()
        print(paint("  BigQuery hazırlığı tamamlandı. Search Console ve GA4 için 4'ü aç.", "mint"))


def show_link(label, url):
    print(f"  {label}  {url}")
    if confirm("Tarayıcıda açalım mı?"):
        if not webbrowser.open(url):
            print("  Yukarıdaki adresi tarayıcıya yapıştırabilirsin.")


def connections():
    pipe = get_pipeline()
    prop = pipe.config["search_console_property"]
    print(paint("\n  <3  KAYNAK BAĞLANTILARI", "rose"))
    print("  [1] Search Console   [2] Google Analytics 4   [3] Ads aktarımı   [0] Geri")
    choice = ask("Seçim", "0")
    if choice == "1":
        print(f"  Mülk  {prop}\n  Hedef  {pipe.refs['search']} · {pipe.location}")
        print("  Mülk sahibi hesabıyla Settings → Bulk data export bölümünü aç.")
        print(f"  Google'ın aktarım hesabı  {IAM_ACCOUNT}")
        print("  Projede BigQuery Job User ve hedef dataset'te BigQuery Data Editor gerekir.")
        if confirm("Bu iki rolü Google'ın aktarım hesabına verelim mi?"):
            require_login()
            pipe.check_location("search")
            subprocess.run(
                ["gcloud", "projects", "add-iam-policy-binding", pipe.project,
                 f"--member=serviceAccount:{IAM_ACCOUNT}", "--role=roles/bigquery.jobUser",
                 "--condition=None"],
                check=True,
            )
            pipe.query(
                f'GRANT `roles/bigquery.dataEditor` ON SCHEMA `{pipe.refs["search"]}` '
                f'TO "serviceAccount:{IAM_ACCOUNT}"'
            )
            print(paint("  Search Console aktarım izinleri verildi.", "mint"))
        show_link("Search Console", "https://search.google.com/search-console?" + urlencode({"resource_id": prop}))
    elif choice == "2":
        print(f"  Mülk  {pipe.config['ga4_property_id']}\n  Hedef  {pipe.refs['ga4']} · {pipe.location}")
        print("  Admin → Product links → BigQuery Links bölümünde projeyi seç ve Daily aktarımı aç.")
        show_link("Google Analytics", "https://analytics.google.com/")
    elif choice == "3":
        show_link("BigQuery aktarımları", "https://console.cloud.google.com/bigquery?" +
                  urlencode({"project": pipe.project, "page": "transfers"}))
    elif choice != "0":
        print("  Menüdeki bir numarayı seç.")


def selected_source():
    print("  [0] Tümü   [1] Google Ads   [2] Search Console   [3] GA4")
    options = {"0": "all", "1": "ads", "2": "search", "3": "ga4"}
    choice = ask("Kaynak", "0")
    if choice not in options:
        raise ValueError("Kaynak için 0–3 arasında bir numara seç.")
    return options[choice]


def date_range():
    today = date.today()
    try:
        start = date.fromisoformat(ask("Başlangıç, YYYY-AA-GG", str(today - timedelta(days=7))))
        end = date.fromisoformat(ask("Bitiş, YYYY-AA-GG", str(today - timedelta(days=4))))
    except ValueError:
        raise ValueError("Tarihleri YYYY-AA-GG biçiminde gir.") from None
    if not date(2000, 1, 1) <= start <= end <= date(2099, 12, 31) or (end - start).days >= 366:
        raise ValueError("2000–2099 arasında en fazla 366 günlük bir tarih aralığı seç.")
    return start, end


def warehouse_action(command):
    get_pipeline()
    source = selected_source()
    args = ["--config", str(SETTINGS), command, "--source", source]
    if command == "audit":
        start, end = date_range()
        args.extend(["--start", str(start), "--end", str(end)])
    require_login()
    if pipeline_cli(args) == 0:
        print(paint("  <3  İşlem tamamlandı.", "mint"))
    else:
        print(paint("  Yukarıdaki aktarım ve hata ayrıntılarını kontrol et.", "peach"))


def export_csv():
    pipe = get_pipeline()
    views = [view for group in VIEWS.values() for view in group]
    for index, view in enumerate(views, start=1):
        print(f"  [{index}] {view}")
    choice = ask("Tablo", "1")
    if choice not in [str(index) for index in range(1, len(views) + 1)]:
        raise ValueError("Menüdeki bir tablo numarası seç.")
    view = views[int(choice) - 1]
    start, end = date_range()
    require_login()
    limit = 10000
    table = f'{pipe.refs["reporting"]}.{view}'
    raw = pipe.query(
        f"SELECT * FROM `{table}` WHERE report_date BETWEEN @start AND @end "
        f"ORDER BY report_date LIMIT {limit + 1}",
        f"--parameter=start:DATE:{start}", f"--parameter=end:DATE:{end}",
        f"--max_rows={limit + 1}", output_format="csv",
    )
    rows = list(csv.reader(io.StringIO(raw)))
    if len(rows) <= 1:
        raise ValueError("Bu aralıkta rapor satırı bulunamadı.")
    if len(rows) > limit + 1:
        raise ValueError("CSV 10.000 satırı aşıyor. Daha kısa bir tarih aralığı seç.")
    downloads = Path.home() / "Downloads"
    exports = (downloads if downloads.is_dir() else Path.home()) / "Data-Kalbi"
    exports.mkdir(exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=exports,
        prefix=f"{view}_{start}_{end}_", suffix=".csv", delete=False,
    ) as output:
        csv.writer(output).writerows(rows)
    print(paint(f"  <3  {len(rows) - 1:,} satır kaydedildi. Power BI'da Metin/CSV ile aç.", "mint"))
    print(f"  {output.name}")


def menu():
    print(paint("\n  KURULUM", "peach"))
    print("  [1] Proje bilgileri        [2] Google hesabına gir")
    print("  [3] BigQuery'yi hazırla    [4] Kaynakları bağla")
    print(paint("\n  VERİ", "lavender"))
    print("  [5] Aktarımı denetle       [6] Rapor tablolarını oluştur")
    print("  [7] Power BI için CSV al   [0] Çıkış")


def main():
    os.environ["CLOUDSDK_CONFIG"] = str(CONFIG / "gcloud")
    os.environ.setdefault("CLOUDSDK_CORE_DISABLE_USAGE_REPORTING", "true")
    heading()
    if SETTINGS.exists():
        try:
            pipe = get_pipeline()
            print(f"  Proje {pipe.project} · {pipe.location}")
        except (ValueError, OSError, KeyError, TypeError):
            print("  Proje ayarları okunamadı. 1 ile bilgileri yeniden gir.")
    else:
        print("  İlk defa mı? Proje bilgilerinle başla. <3")
    actions = {
        "1": configure, "2": google_login, "3": setup_cloud, "4": connections,
        "5": lambda: warehouse_action("audit"), "6": lambda: warehouse_action("publish"), "7": export_csv,
    }
    while True:
        try:
            menu()
            choice = ask("Seçim", "0")
            if choice == "0":
                break
            if choice in actions:
                actions[choice]()
            else:
                print("  Menüdeki bir numarayı seç.")
        except EOFError:
            break
        except KeyboardInterrupt:
            print(paint("\n  İşlem durduruldu. Menüye döndün.", "peach"))
        except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
            print(paint(f"  İşlem tamamlanamadı. {error}", "peach"))
    print(paint("  Görüşürüz! <3", "rose"))


if __name__ == "__main__":
    main()
