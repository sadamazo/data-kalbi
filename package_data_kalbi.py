#!/usr/bin/env python3
"""Build the standalone Data Kalbi launchers."""
import base64
import gzip
import io
from pathlib import Path
import tarfile
import textwrap

ROOT = Path(__file__).resolve().parent
LAUNCHER = r"""
(
  set -eu
  umask 077
  if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    printf '%s\n' 'Ece Data Kalbi Pro için Python 3.9 veya üstü gerekiyor.' >&2
    exit 1
  fi
  data_kalbi_tmp=$(mktemp -d "${TMPDIR:-/tmp}/data-kalbi.XXXXXXXX")
  trap 'rm -rf -- "$data_kalbi_tmp"' EXIT
  python3 -c 'import base64, sys; sys.stdout.buffer.write(base64.b64decode(sys.stdin.buffer.read()))' <<'DATA_KALBI_PACKAGE' > "$data_kalbi_tmp/app.tar.gz"
{payload}
DATA_KALBI_PACKAGE
  tar -xzf "$data_kalbi_tmp/app.tar.gz" -C "$data_kalbi_tmp"
  python3 "$data_kalbi_tmp/data_kalbi.py"
)
""".lstrip()

POWERSHELL_LAUNCHER = r"""
$ErrorActionPreference = 'Stop'

function Find-KalbiPython {
    $ErrorActionPreference = 'Continue'
    $probe = 'import sys; print(sys.executable) if sys.version_info >= (3, 9) else sys.exit(1)'
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $found = & py.exe -3 -c $probe 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { return $found }
    }
    $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $localPython) { return $localPython }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\Microsoft\WindowsApps\python.exe') {
        $found = & $pythonCommand.Source -c $probe 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { return $found }
    }
}

$kalbiPython = Find-KalbiPython
if (-not $kalbiPython) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'Ece Data Kalbi Pro: https://www.python.org/downloads/windows/ (Python 3.9+)'
    }
    $permission = Read-Host 'Ece Data Kalbi Pro: Python 3.12 kurulsun mu? (e/h)'
    if ($permission -ne 'e') { return }
    & winget.exe install --id Python.Python.3.12 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python kurulumu tamamlanamadi.' }
    $kalbiPython = Find-KalbiPython
    if (-not $kalbiPython) { throw 'Python kuruldu. PowerShell penceresini yeniden acip komutu calistir.' }
}

$kalbiFolder = Join-Path ([System.IO.Path]::GetTempPath()) ('ece-data-kalbi-' + [Guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($kalbiFolder) | Out-Null
try {
    $payload = @'
{payload}
'@
    $archive = Join-Path $kalbiFolder 'app.tar.gz'
    [IO.File]::WriteAllBytes($archive, [Convert]::FromBase64String($payload))
    & $kalbiPython -m tarfile -e $archive $kalbiFolder
    if ($LASTEXITCODE -ne 0) { throw 'Uygulama paketi acilamadi.' }
    & $kalbiPython -X utf8 (Join-Path $kalbiFolder 'data_kalbi.py')
    if ($LASTEXITCODE -ne 0) { throw 'Ece Data Kalbi Pro kapandi.' }
} finally {
    Remove-Item -LiteralPath $kalbiFolder -Recurse -Force
}
""".lstrip()


def build():
    files = [ROOT / name for name in (
        "data_kalbi.py", "pipeline.py", "cloud_cli.py", "config.example.json", "sticker_edges.py", "sticker_pixels.json",
    )]
    files.extend(sorted((ROOT / "sql").glob("*.sql")))
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        for file in files:
            contents = file.read_bytes()
            info = tarfile.TarInfo(str(file.relative_to(ROOT)))
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
    payload = base64.b64encode(gzip.compress(data.getvalue(), mtime=0)).decode("ascii")
    wrapped = "\n".join(textwrap.wrap(payload, width=76))
    for name, source in (("Data-Kalbi.sh", LAUNCHER), ("Data-Kalbi.ps1", POWERSHELL_LAUNCHER)):
        target = ROOT / name
        target.write_text(source.replace("{payload}", wrapped), encoding="utf-8")
        print(f"{target.name} · {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    build()
