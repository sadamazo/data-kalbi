"""Resolve Google Cloud CLI commands across the supported platforms."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "data-kalbi"
SDK = DATA / "google-cloud-sdk"
WINDOWS_SDK_URL = (
    "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/"
    "google-cloud-sdk-594.0.1-windows-x86_64-bundled-python.zip"
)
WINDOWS_SDK_SHA256 = "9612ee5a32a13e917fda84a0dce8028264c3fec1e8ca2738d1d43c312c675332"


def cloud_command(tool):
    if sys.platform != "win32":
        managed = SDK / "bin" / tool
        executable = str(managed) if managed.is_file() else shutil.which(tool)
        if executable:
            return [executable]
        raise FileNotFoundError(f"{tool} bulunamadı. Google Cloud CLI'yi kur.")

    entry = {"gcloud": "lib/gcloud.py", "bq": "bin/bootstrapping/bq.py"}[tool]
    installed = shutil.which(f"{tool}.cmd")
    candidates = [SDK]
    if installed:
        candidates.append(Path(installed).resolve().parent.parent)
    for root in candidates:
        script = root / entry
        bundled = root / "platform/bundledpython/python.exe"
        if script.is_file():
            interpreter = str(bundled) if bundled.is_file() else sys.executable
            return [interpreter, "-X", "utf8", "-S", str(script)]
    raise FileNotFoundError(f"{tool} bulunamadı. Google Cloud CLI'yi kur.")


def sdk_available():
    try:
        cloud_command("gcloud")
        cloud_command("bq")
        return True
    except FileNotFoundError:
        return False


def install_sdk():
    DATA.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        with tempfile.TemporaryDirectory(prefix="sdk-", dir=DATA) as folder:
            staging = Path(folder)
            archive = staging / "sdk.zip"
            digest = hashlib.sha256()
            with urllib.request.urlopen(WINDOWS_SDK_URL, timeout=60) as source, archive.open("wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    target.write(chunk)
            if digest.hexdigest() != WINDOWS_SDK_SHA256:
                raise ValueError("Google Cloud CLI arşivinin bütünlüğü doğrulanamadı.")
            with zipfile.ZipFile(archive) as download:
                download.extractall(staging)
            (staging / SDK.name).rename(SDK)
        return

    with tempfile.TemporaryDirectory(prefix="data-kalbi-sdk-") as folder:
        installer = Path(folder) / "install.sh"
        subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
             "https://sdk.cloud.google.com", "--output", str(installer)],
            check=True,
        )
        subprocess.run(["bash", str(installer), "--disable-prompts", f"--install-dir={DATA}"], check=True)
