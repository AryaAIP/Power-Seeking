"""Report relative markdown links that do not resolve, in every .md file of the project (http links and
anchors are skipped). Run after moving or adding files; it should print "0 broken link(s)".
  python3 tools/check_links.py [ROOT] [--all]     (ROOT defaults to the project folder; --all includes
                                                  every generated run transcript)
"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
skip_runs = "--all" not in sys.argv  # run transcripts are generated and linked only to their own files
link = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def markdown_files() -> list:
    """Every .md file, not walking .git or a batch's run folders (those files are skipped anyway): over /mnt/c the walk
    is most of the cost."""
    found = []
    for folder, dirs, files in os.walk(root):
        rel = Path(folder).relative_to(root).as_posix()
        rel = "" if rel == "." else rel + "/"
        if not rel:
            dirs[:] = [d for d in dirs if d != ".git"]
        if skip_runs and "/runs/" in f"/{rel}" and rel.count("/") >= 4:
            dirs[:] = []  # .../runs/<label>/<task>/: a file in it would have rel.count("/") > 4
        found += [rel + f for f in files if f.endswith(".md")]
    return sorted(found)


def broken(rel: str) -> list:
    md = root / rel
    if skip_runs and "/runs/" in f"/{rel}" and rel.count("/") > 4:
        return []
    out = []
    for m in link.finditer(md.read_text(errors="ignore")):
        target = m.group(1)
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        path = unquote(target.split("#")[0])
        if path and not (md.parent / path).exists():
            out.append(f"{rel}: {target}")
    return out


with ThreadPoolExecutor(16) as pool:  # file reads and stats wait on the share, so threads help
    lines = [ln for found in pool.map(broken, markdown_files()) for ln in found]
print("\n".join(lines + [f"{len(lines)} broken link(s)"]))
