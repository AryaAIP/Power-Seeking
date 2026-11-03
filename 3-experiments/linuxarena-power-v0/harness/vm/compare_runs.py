"""Compare two batches' scores task by task, from the exported records: the cloud machine's check against WSL's.
Prints, per task, "same" or the checks that differ (names only, never scorer output). Exit code 1 if any differ.
  python3 -I compare_runs.py nowork-v2-S0 vmcheck-nowork
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import power_horizons as ph  # noqa: E402

a, b = ph.one_per_task(sys.argv[1]), ph.one_per_task(sys.argv[2])
differ = 0
for task in sorted(set(a) | set(b)):
    if task not in a or task not in b:
        print(f"{task}: only in {sys.argv[1] if task in a else sys.argv[2]}")
        differ += 1
        continue
    x, y = a[task], b[task]
    if (x["kind"], x["x"]) == (y["kind"], y["x"]):
        print(f"{task}: same")
        continue
    differ += 1
    if x["kind"] == y["kind"] == "checks":
        names = sorted(c for c in set(x["x"]) | set(y["x"]) if x["x"].get(c) != y["x"].get(c))
        print(f"{task}: {len(names)} checks differ: {', '.join(names)}")
    else:
        print(f"{task}: differs ({x['kind']} {x['x']} against {y['kind']} {y['x']})")
print(f"{differ} of {len(set(a) | set(b))} tasks differ")
sys.exit(1 if differ else 0)
