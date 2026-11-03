"""Report relative markdown links that do not resolve, in every .md file of the project (http links and
anchors are skipped). Run after moving or adding files; it should print "0 broken link(s)".
  python3 tools/check_links.py [ROOT] [--all]     (ROOT defaults to the project folder; --all includes
                                                  every generated run transcript)
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
skip_runs = "--all" not in sys.argv  # run transcripts are generated and linked only to their own files
link = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
bad = 0
for md in sorted(root.rglob("*.md")):
    rel = md.relative_to(root).as_posix()
    if skip_runs and "/runs/" in f"/{rel}" and rel.count("/") > 4:
        continue
    text = md.read_text(errors="ignore")
    for m in link.finditer(text):
        target = m.group(1)
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        path = unquote(target.split("#")[0])
        if not path:
            continue
        if not (md.parent / path).exists():
            bad += 1
            print(f"{rel}: {target}")
print(f"{bad} broken link(s)")
