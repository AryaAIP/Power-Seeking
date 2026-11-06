#!/usr/bin/env python3
"""Change the scoring density of the score-and-roll-back jobs still pending in queue/jobs.tsv (lines already started
are left alone). A pending line's `-p score_every=N` (or `-p score_at=...`) becomes `-p score_at=<turns>`: every turn up
to and including --cut, then every --step turns, below the run's end (its -p prefix_turns=). --cut 0 --step 2 is every
2 turns throughout. Writes jobs.tsv by renaming a new copy
over it, so night_queue.py never reads half a file. Runs in WSL:
  python3 -I queue_density.py --cut 20 --step 2 [--dry-run]
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import QUEUE  # noqa: E402


def points(cut: int, step: int, end: int) -> list[int]:
    """Every turn up to and including cut, then every `step` turns after it (cut + step, ...), all below the end."""
    return list(range(1, min(cut + 1, end))) + list(range(cut + step, end, step))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", type=int, required=True, help="score every turn below this H")
    ap.add_argument("--step", type=int, required=True, help="then every this many turns")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    lines = (QUEUE / "jobs.tsv").read_text().splitlines(keepends=True)
    status = {}
    for ln in (QUEUE / "status.tsv").read_text().splitlines():
        f = ln.split("\t")
        if len(f) >= 2 and not ln.startswith("#"):
            status[f[0]] = f[1]
    out, changed, before, after = [], 0, 0, 0
    for ln in lines:
        label = ln.split("\t", 1)[0]
        m = re.search(r"-p prefix_turns=(\d+)", ln)
        if m and not ln.startswith("#") and status.get(label, "pending") in ("pending", "not started (deadline)") \
                and re.search(r"-p score_(every|at)=", ln) and not label.startswith("restorecheck"):
            end = int(m.group(1))
            old = re.search(r"-p score_every=(\d+)", ln)
            before += len(range(int(old.group(1)), end, int(old.group(1)))) if old else \
                len(re.search(r"-p score_at=(\S+)", ln).group(1).split(","))
            pts = points(a.cut, a.step, end)
            after += len(pts)
            ln = re.sub(r"-p score_(every|at)=\S+", f"-p score_at={','.join(map(str, pts))}", ln, count=1)
            changed += 1
        out.append(ln)
    print(f"{changed} pending lines: {before} points -> {after} (every turn to H={a.cut}, then every {a.step})")
    if not a.dry_run:
        tmp = QUEUE / "jobs.tsv.density"
        tmp.write_text("".join(out))
        os.replace(tmp, QUEUE / "jobs.tsv")
        print("jobs.tsv rewritten")


if __name__ == "__main__":
    main()
