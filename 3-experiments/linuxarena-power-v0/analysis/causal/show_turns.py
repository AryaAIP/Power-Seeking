"""Compact view of a run's first turns from analysis/digests, for reading. Usage: show_turns.py <task> <arm> [last_turn] [why_chars] [cmd_chars]"""
import re
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent.parent
task, arm = sys.argv[1], sys.argv[2]
last = int(sys.argv[3]) if len(sys.argv) > 3 else 15
wc = int(sys.argv[4]) if len(sys.argv) > 4 else 90
cc = int(sys.argv[5]) if len(sys.argv) > 5 else 110
matches = [d for d in (EXP / "analysis" / "digests").iterdir() if d.name.startswith(task)]
f = matches[0] / f"{arm}.md"
lines = f.read_text().splitlines()
print(f"--- {matches[0].name} · {arm}")
for l in lines:
    if l.startswith("T=") or l.startswith("First:") or l.startswith("Share of") or l.startswith("Failed"):
        print(l[:170])
    if l.startswith("- H=") and "(" in l:
        print("  " + l[:150])
cur = None
for l in lines:
    m = re.match(r"### T(\d+) · (.*?) · in (\d+) out (\d+)", l)
    m2 = re.match(r"- T(\d+) (\S*): (.*)", l)
    if m:
        cur = int(m.group(1))
        if cur > last:
            break
        print(f"T{cur} [{m.group(2)}] out={m.group(4)}")
    elif m2:
        cur = int(m2.group(1))
        if cur > last:
            break
        print(f"T{cur} [{m2.group(2)}] {m2.group(3)[:cc]}")
    elif cur is not None and cur <= last:
        if l.startswith("why:"):
            print("   why: " + l[5:5 + wc])
        elif l.startswith("- `"):
            print("   " + l[2:2 + cc])
        elif l.startswith("**scored here"):
            print("   " + l[:40])
