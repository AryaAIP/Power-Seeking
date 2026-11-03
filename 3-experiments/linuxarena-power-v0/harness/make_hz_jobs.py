"""Print the queue lines for per-step scoring of one solver batch (plans/night-plan.md, Phase 6).

For each run in runs/<LABEL>, and each horizon H in --horizons below the run's own number of model turns, one job
replays that run's first H turns into a fresh machine (after the trajectory, for after runs) with no model calls,
then scores. Labels: hz-<LABEL>-<task short name>-H<H>. Run in WSL; append the output to queue/jobs.tsv.
  python3 make_hz_jobs.py v2-before [--horizons 40,20,60] [--traj /root/power-v0/trajectory/traj2-control.eval]
"""

import argparse
import json
from pathlib import Path

RUNS = Path("/mnt/c/Users/arya/OneDrive/Desktop/AI-Safety/Projects/Power-Seeking/3-experiments/linuxarena-power-v0/runs")  # the exported records
EVALS = Path("/root/power-v0/data/evals")
SHORT = {"jwt_claims_wrong_field": "jwt", "migrate_backup_records_to_sqlite": "backup",
         "model_favoriting_system": "fav", "model_registry_health_dashboard_data": "dash",
         "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern": "refactor",
         "untracked_s3_objects_total_bytes": "s3"}
LAUNCH = "/root/power-v0/harness/launch.sh"

ap = argparse.ArgumentParser()
ap.add_argument("label")
ap.add_argument("--horizons", default="40,20,60")  # the plan's priority order
ap.add_argument("--traj", default="")
a = ap.parse_args()
log = sorted((EVALS / a.label).glob("*.eval"))
assert len(log) == 1, f"expected one .eval log for {a.label}, found {len(log)}"
metas = sorted(RUNS.glob(f"{a.label}/*/*/meta.json"))
assert metas, f"no exported runs for {a.label} in {RUNS}"
traj = f" -p traj={a.traj} -p traj_user=dev -p traj_cmd_bug=false" if a.traj else ""
for h in (int(x) for x in a.horizons.split(",")):
    for run in metas:
        meta = json.loads(run.read_text())
        task = meta["task"]
        turns = sum(1 for _ in (run.parent / "usage.csv").open()) - 1
        if h >= turns:
            continue
        lab = f"hz-{a.label}-{SHORT[task]}-H{h}"
        purpose = (f"Per-step scoring: the first {h} of {turns} model turns of {a.label}'s {task} run, replayed "
                   f"with no model calls{' after the trajectory' if a.traj else ''}, then scored")
        print(f'{lab}\t1\tPURPOSE="{purpose}" bash {LAUNCH} {lab} tasks/one_{task}.txt 1 -p solver_user=dev -p solve=false'
              f"{traj} -p prefix_log={log[0]} -p prefix_turns={h}")
