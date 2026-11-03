"""Print the queue lines for the Nov 3 search for B (plans/nov3-plan-to-6am.md): every trajectory task in
tasks/traj_*.txt under every note, one environment each. Labels: traj4-<task short name>-<note>, "none" for no note.
In order of note, so the no-note controls (A's candidates) start first. Append the output to queue/jobs.tsv.
  python3 -I make_traj_jobs.py [--notes none,side,blockers,roadmap,lean]
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from power_paths import LAUNCH  # noqa: E402
from task_names import SHORT  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--notes", default="none,side,blockers,roadmap,lean")
a = ap.parse_args()
for note in a.notes.split(","):
    for f in sorted((HERE / "tasks").glob("traj_*.txt")):
        task = f.stem.removeprefix("traj_")
        label = f"traj4-{SHORT[task]}-{note}"
        incline = f" -p incline={note}" if note != "none" else ""
        purpose = f"Search for B (Nov 3): a trajectory on {task}, " + (f"with the {note} note" if note != "none" else "with no note (the control)")
        print(f'{label}\t1\tPURPOSE="{purpose}" bash {LAUNCH} {label} tasks/{f.name} 1 -p solver_user=dev -p max_steps=200{incline}')
