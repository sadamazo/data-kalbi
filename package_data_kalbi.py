#!/usr/bin/env python3
"""Build the standalone Data Kalbi shell launcher."""
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
    printf '%s\n' 'Data Kalbi için Python 3.9 veya üstü gerekiyor.' >&2
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


def build():
    files = [ROOT / name for name in ("data_kalbi.py", "pipeline.py", "config.example.json")]
    files.extend(sorted((ROOT / "sql").glob("*.sql")))
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        for file in files:
            contents = file.read_bytes()
            info = tarfile.TarInfo(str(file.relative_to(ROOT)))
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
    payload = base64.b64encode(gzip.compress(data.getvalue(), mtime=0)).decode("ascii")
    target = ROOT / "Data-Kalbi.sh"
    target.write_text(
        LAUNCHER.replace("{payload}", "\n".join(textwrap.wrap(payload, width=76))),
        encoding="utf-8",
    )
    print(f"{target.name} · {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    build()
