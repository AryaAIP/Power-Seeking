#!/usr/bin/env python3
"""Which scoring points did a machine pause interrupt? A laptop that sleeps stops every job mid-step, and a point whose
scorer was running then may have timed out or changed (its row's seconds include the pause). This lists every exported
point of the given labels whose save, scorer or restore started before the pause and ended after it, using each row's
start time and durations:
  python3 -I find_paused_points.py "HH:MM:SS" "HH:MM:SS" [LABEL ...]     (local time, Nov 3; no labels: every sr- label)
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import RUNS  # noqa: E402


def straddles(started: str, seconds: dict, t0: dt.datetime, t1: dt.datetime) -> bool:
    """Did this row's work run across the pause? Its start was before the pause, and its end after."""
    start = dt.datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone()
    end = start + dt.timedelta(seconds=sum(seconds.values()))
    return start < t0 and end > t1


def main() -> int:
    day = dt.datetime.now().astimezone()
    t0, t1 = (day.replace(hour=int(x[:2]), minute=int(x[3:5]), second=int(x[6:8]), microsecond=0) for x in sys.argv[1:3])
    labels = sys.argv[3:] or sorted(p.name for p in RUNS.glob("sr-*"))
    n = 0
    for label in labels:
        for f in RUNS.glob(f"{label}/*/*/horizon_scores.jsonl"):
            for ln in f.read_text().splitlines():
                r = json.loads(ln)
                if r.get("started") and r.get("seconds") and straddles(r["started"], r["seconds"], t0, t1):
                    p = (r.get("scores") or {}).get("parsed") or {}
                    print(f"{label} H={r['H']} {p.get('verdict')} {p.get('checks_passed')}/{p.get('checks_total')} "
                          f"restore exact: {r.get('state_equal')} seconds: {r['seconds']}")
                    n += 1
    print(f"{n} point(s) ran across the pause")
    return 0


if __name__ == "__main__":
    sys.exit(main())
