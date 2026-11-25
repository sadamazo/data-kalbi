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

from cloud_cli import cloud_command, install_sdk, sdk_available
from pipeline import Pipeline, VIEWS, load_config, main as pipeline_cli

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "data-kalbi"
APP_NAME = "Ece Data Kalbi Pro v300004"
SETTINGS = CONFIG / "config.json"
EXAMPLE = Path(__file__).resolve().parent / "config.example.json"
IAM_ACCOUNT = "search-console-data-export@system.gserviceaccount.com"

COLORS = {
    "rose": "38;5;211", "peach": "38;5;216", "lavender": "38;5;183",
    "mint": "38;5;121", "edge": "38;5;103",
}


def configure_console():
    if sys.platform != "win32" or not sys.stdout.isatty():
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.windll.kernel32
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.GetStdHandle(-11)
    mode = wintypes.DWORD()
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)) or not kernel.SetConsoleMode(handle, mode.value | 4):
        os.environ.setdefault("NO_COLOR", "1")


def terminal_effects():
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def paint(value, color):
    if terminal_effects():
        return f"\033[{COLORS[color]}m{value}\033[0m"
    return value


def couple_art(height=10, *, pulse=False, blink=False):
    left = (
        "        _ .-.-. _",
        "      .( `     ` ).",
        "     (   .---.    )",
        "     /  /     \\   \\",
        "    |  (o)---(o)   |",
        "    |    .  >      |",
        r"     \     \_/  . /",
        "      '._     _.'",
        "       __)---(__",
        r"     /'   '-'   '\ ",
    )
    right = (
        "         .-~~~~-.",
        "       .'  _     `.",
        "      /  .' `-.    \\",
        "     /  /      \\    \\",
        f"    |  |  {'-  -' if blink else 'o  o'}  |    |",
        "    |  |   <  . | o  |",
        r"    |   \  \_/ /  O  |",
        r"     \   '.__.'  /  /",
        r"      )  /    \ (  (",
        "     /_.'      '._  \\",
    )
    heart = (" _  _", r"( \/ )", r"\    /", r" \  /", r"  \/ ") if pulse else (
        "       ", "  _ _", r" (\/) ", r"  \/ ", "      ",
    )
    faces = tuple(zip(left, right))
    if height == 8:
        faces = faces[:2] + faces[3:8] + faces[-1:]
    elif height == 9:
        faces = faces[:2] + faces[3:]
    return [
        ((f"{a:<22}", "peach"), (f"{heart[index] if index < len(heart) else '':^8}", "rose"),
         (f"{b:<22}", "lavender"))
        for index, (a, b) in enumerate(faces)
    ]


MENU_GROUPS = (
    ("KURULUM", "peach", (("1", "Proje bilgileri"), ("2", "Google hesabına gir"),
                          ("3", "BigQuery’yi hazırla"), ("4", "Kaynakları bağla"))),
    ("VERİ VE RAPOR", "lavender", (("5", "Aktarımı denetle"), ("6", "Rapor tablosu oluştur"),
                                   ("7", "Power BI için CSV al"), ("0", "Çıkış"))),
)


def project_status():
    if not SETTINGS.exists():
        return "Proje eklemek için 1’i seç."
    try:
        config = get_pipeline()
        return f"{config.project}  /  {config.location}"
    except (ValueError, OSError, KeyError, TypeError):
        return "Proje ayarlarını düzeltmek için 1’i seç."


def panel_width(columns):
    return max(28, min(58, columns - 7))


def panel_indent(columns):
    unused = columns - panel_width(columns) - 2
    return min(12, max(0, unused // 2))


def panel_rows(columns, state, art=()):
    width = panel_width(columns)
    inner = width - 6
    rich = terminal_effects()
    top_left, top_right, bottom_left, bottom_right, left_join, right_join, horiz, vert = (
        ("╭", "╮", "╰", "╯", "├", "┤", "─", "│") if rich else ("+", "+", "+", "+", "+", "+", "-", "|")
    )
    rows = []

    def line(first, last):
        rows.append(paint(first + horiz * width + last, "edge"))

    def row(*parts, center=False):
        length = sum(len(part) for part, _ in parts)
        start = max(0, (width - length) // 2) if center else 3
        value = "".join(paint(part, tint) if tint else part for part, tint in parts)
        rows.append(paint(vert, "edge") + " " * start + value
                    + " " * (width - start - length) + paint(vert, "edge"))

    line(top_left, top_right)
    row((APP_NAME, "rose"), center=True)
    row((state[:inner], "mint"), center=True)
    if art:
        row()
        for element in art:
            row(*element, center=True)
        row()
    line(left_join, right_join)
    for label, color, actions in MENU_GROUPS:
        row((label, color))
        if width >= 57:
            for first, second in zip(actions[::2], actions[1::2]):
                hotkey, caption = first
                other_key, other_caption = second
                row((hotkey, color), (f"  {caption:<23}", None),
                    (other_key, color), (f"  {other_caption}", None))
        else:
            for hotkey, caption in actions:
                row((hotkey, color), ("  " + caption[:inner - 3], None))
        if label == "KURULUM":
            row()
    line(bottom_left, bottom_right)
    margin = " " * panel_indent(columns)
    return [margin + entry for entry in rows]


def menu(intro=False):
    size = shutil.get_terminal_size()
    state = project_status()
    if size.columns < 36:
        print(f"\n{APP_NAME}\n{state}")
        for label, color, actions in MENU_GROUPS:
            print(paint(label, color))
            for key, caption in actions:
                print(f"{key}  {caption}")
        return 0

    base = panel_rows(size.columns, state)
    art_height = size.lines - len(base) - 4
    show_couple = intro and size.columns >= 59 and art_height >= 8
    compact_faces = (
        (("   .ooo.    ", "peach"), ("     ", None), ("   .~~~~.    ", "lavender")),
        (("  (o)-(o)   ", "peach"), (" <3  ", "rose"), ("  / o  o \\   ", "lavender")),
        ((r"    \_/     ", "peach"), ("     ", None), (r"  \  \_/ O   ", "lavender")),
        (("   /   \\    ", "peach"), ("     ", None), ("   '~..~'    ", "lavender")),
    )
    art = ()
    if show_couple:
        art = couple_art(art_height)
    elif intro and art_height >= 2:
        art = compact_faces if art_height >= 4 else compact_faces[1:3]
    settle = panel_rows(size.columns, state, art) if art else base
    print("\n" + "\n".join(settle), flush=True)
    if not show_couple or not terminal_effects() or size.lines < len(settle) + 2:
        return panel_indent(size.columns)

    back = f"\033[{len(settle)}F"
    frames = (
        (0.28, panel_rows(size.columns, state, couple_art(art_height, pulse=True))),
        (0.20, panel_rows(size.columns, state, couple_art(art_height, blink=True))),
        (0.24, settle),
    )
    try:
        for delay, rows in frames:
            time.sleep(delay)
            print(back + "\n".join(rows), flush=True)
    except KeyboardInterrupt:
        print(back + "\n".join(settle), flush=True)
    return panel_indent(size.columns)


def ask(label, default="", *, indent=2):
    suffix = f" [{default}]" if default else ""
    return input(paint(f"{' ' * indent}{label}{suffix} > ", "lavender")).strip() or default


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


def require_sdk():
    if sdk_available():
        return
    if sys.platform not in ("darwin", "linux", "win32"):
        raise ValueError("Google Cloud CLI kurulumu için macOS, Linux veya Windows kullan.")
    print("  Google Cloud CLI gerekiyor. Google'ın resmi paketi indirilecek.")
    if not confirm("Google Cloud CLI bu uygulamanın klasörüne kurulsun mu?"):
        raise ValueError("Kuruluma devam etmek için gcloud ve bq gerekiyor.")
    print("  Google Cloud CLI indiriliyor…", flush=True)
    install_sdk()
    if not sdk_available():
        raise ValueError("Google Cloud CLI kurulumu tamamlanamadı. Kurulum çıktısını kontrol et.")


def google_login():
    require_sdk()
    print(paint("\n  <3  Google giriş ekranı açılıyor.", "rose"), flush=True)
    subprocess.run([*cloud_command("gcloud"), "auth", "login", "--force"], check=True)
    print(paint("  Google oturumu açıldı.", "mint"))


def require_login():
    require_sdk()
    active = subprocess.run(
        [*cloud_command("gcloud"), "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
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
                [*cloud_command("gcloud"), "projects", "add-iam-policy-binding", pipe.project,
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


def main():
    os.environ["CLOUDSDK_CONFIG"] = str(CONFIG / "gcloud")
    os.environ.setdefault("CLOUDSDK_CORE_DISABLE_USAGE_REPORTING", "true")
    configure_console()
    actions = {
        "1": configure, "2": google_login, "3": setup_cloud, "4": connections,
        "5": lambda: warehouse_action("audit"), "6": lambda: warehouse_action("publish"), "7": export_csv,
    }
    first_menu = True
    while True:
        try:
            margin = menu(intro=first_menu)
            first_menu = False
            choice = ask("Seçim", "0", indent=margin + 1)
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
