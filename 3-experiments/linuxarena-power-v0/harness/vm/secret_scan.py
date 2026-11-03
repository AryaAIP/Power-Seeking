"""Scan files for secrets before committing. Prints file paths and the kind of match only, never the text.
Exit code 1 if anything is found, 2 if the list can't be read.
  usage (in WSL, with Control Tower's Python, since export_run.py imports inspect_ai):
    $POWER_V0_CT/.venv/bin/python secret_scan.py <file list>
The list has one path per line: relative to the repository root, or absolute. Checks each file for the environment's
known secret values (export_run.SECRETS: compose file, credentials script, init files), the OpenRouter key if
OPENROUTER_API_KEY is set, and secret-looking patterns. Used by finish_v4.sh."""
import os
import re
import sys
from pathlib import Path

HOME = Path(os.environ.get("POWER_V0_HOME") or Path.home() / "power-v0")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # this repository's harness
sys.path.insert(1, str(HOME / "harness"))  # the synced copy, as before
from export_run import SECRETS  # noqa: E402  the environment's known secret values

ROOT = Path(__file__).resolve().parents[4]  # harness/vm -> the repository (Power-Seeking)
try:
    files = [ROOT / ln.strip() for ln in Path(sys.argv[1]).read_text().splitlines() if ln.strip()]
except (IndexError, OSError) as e:
    print(f"can't read the file list: {type(e).__name__}"); sys.exit(2)
key = os.environ.get("OPENROUTER_API_KEY", "")
patterns = {
    "jwt-like token": re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    "password in a URL": re.compile(r"://[A-Za-z0-9_.-]+:(?!<secret>|\$|\{|\*|password@|PASSWORD|pass@|<)[^@\s/\"']{4,}@"),
    "OpenRouter-style key": re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Anthropic/OpenAI-style key": re.compile(r"sk-(ant-|proj-)?[A-Za-z0-9_-]{32,}"),
}


def show(f: Path) -> str:
    try:
        return str(f.relative_to(ROOT))
    except ValueError:
        return str(f)


hits = 0
for f in files:
    try:
        text = f.read_text(errors="ignore")
    except Exception as e:  # noqa: BLE001
        print(f"UNREADABLE {show(f)}: {type(e).__name__}"); continue
    found = []
    n_known = sum(text.count(v) for v in SECRETS)
    if n_known:
        found.append(f"{n_known} known environment secret value(s)")
    if key and len(key) > 10 and key in text:
        found.append("the OpenRouter key itself")
    for name, rx in patterns.items():
        n = len(rx.findall(text))
        if n:
            found.append(f"{n} {name}")
    if found:
        hits += 1
        print(f"HIT {show(f)}: " + "; ".join(found))
print(f"scanned {len(files)} files with {len(SECRETS)} known values{' and the API key' if key else ' (API key not available to check)'}: {hits} file(s) with hits")
sys.exit(1 if hits else 0)
