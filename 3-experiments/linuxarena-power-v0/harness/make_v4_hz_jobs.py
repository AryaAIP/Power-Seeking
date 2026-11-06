"""Print the per-step scoring queue lines for every v4 solver batch this machine holds (plans/nov3-plan-to-6am.md,
"Per-step jobs"), coarse horizons first: H = 10 for every run, then 20 for every run, then 30, 40, 5, 15, 25, 35, so
every task gets a coarse curve before any gets a fine one. Run it on the machine that holds the source runs (each
replays its source run's raw log); append the output to queue/jobs.tsv there. Prints only; changes nothing.
  python3 -I make_v4_hz_jobs.py [--horizons 10,20,30,40,5,15,25,35] [--labels v4-before-p1,v4-afterA-p1,...]

The lines are make_hz_jobs.py's, exactly: label hz-<label>-<task short name>-H<h>; a horizon at or past the run's own
number of model turns is skipped; after arms replay their trajectory first (-p traj=...). Differences:
  - the batches: every finished v4 solver batch here (v4-before-pK, v4-afterA-pK, v4-afterB-pK: one .eval log in
    data/evals/<label>/ and its exported runs/<label>/summary.json), or the --labels given;
  - turns are counted as power_horizons.outcome() counts them: usage rows with output tokens (a failed call isn't a turn);
  - the trajectory comes from the batch's own policy args (summary.json, else a run's config.json), not a fixed path;
  - a label already in the data folder (started or done) or already in queue/jobs.tsv is skipped, and counted on stderr.

Options, all off by default (without them the output is exactly as before):
  --restore-state     after batches start from their trajectory's saved end state (-p restore_state=<trajectory label>,
                      plans/replay-free-scope.md) instead of replaying it; the state must be saved first
  --score-every N, --score-at H1,H2,...
                      score and roll back (plans/score-and-rollback-scope.md): one job per run instead of one per (run, H),
                      labelled <prefix>-<label>-<task short name>, which replays the whole run and scores and rolls back
                      at every N turns and/or the listed turns below its end. Question tasks are skipped: their scorer
                      reads the submitted answer, so a partway score is always "no answer"
  --label-prefix P    the per-run label's prefix (default hz; e.g. hzcheck-sr for checks)
  --min-timeout N, --keep-build-cache
                      per-run jobs: a floor in seconds on command time limits while scoring; keep root's Go build
                      cache between points (power_v0's score_min_timeout, score_keep_build_cache)
"""

import argparse
import csv
import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import CT, DATA, LAUNCH, QUEUE, RUNS  # noqa: E402
from rollback import score_points  # noqa: E402
from task_names import SHORT  # noqa: E402

EVALS = DATA / "evals"
ARMS = ("before", "afterA", "afterB", "afterA2", "afterB2")  # A2/B2: the second pair (Nov 3, 04:30)
V4 = re.compile(r"^v4-(before|afterA2|afterB2|afterA|afterB)-p(\d+)$")


def note(msg: str) -> None:
    print(msg, file=sys.stderr)


def turns(run: Path) -> int:
    """power_horizons.outcome()'s count: one usage row per model call, but a failed call leaves a row with no output."""
    with (run / "usage.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    if rows and "output_tokens" in rows[0]:
        return sum(1 for r in rows if (r["output_tokens"] or "").strip() not in ("", "0"))
    return len(rows)


def policy_args(label: str, runs: list) -> dict:
    """{name: value} of the batch's -p arguments: summary.json's policy_args, else the first run's config.json."""
    text = ""
    summ = RUNS / label / "summary.json"
    if summ.is_file():
        text = json.loads(summ.read_text()).get("policy_args") or ""
    if text:
        toks = shlex.split(text)
        return dict(t.split("=", 1) for t in (toks[i + 1] for i, x in enumerate(toks[:-1]) if x == "-p") if "=" in t)
    for run in runs:
        cfg = run.parent / "config.json"
        if cfg.is_file():
            d = json.loads(cfg.read_text())
            pa = ((d.get("run_record") or {}).get("args")
                  or (((d.get("eval") or {}).get("metadata") or {}).get("policy_selection") or {}).get("args") or {})
            if isinstance(pa, dict) and pa:
                return {k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in pa.items()}
    return {}


def batches() -> list:
    found = []
    for d in EVALS.iterdir() if EVALS.is_dir() else []:
        m = V4.match(d.name)
        if m and d.is_dir():
            found.append((int(m.group(2)), ARMS.index(m.group(1)), d.name))
    return [lab for _, _, lab in sorted(found, key=lambda x: (x[1], x[0]))]  # before p1..p4, afterA p1..p4, afterB


ap = argparse.ArgumentParser()
ap.add_argument("--horizons", default="10,20,30,40,5,15,25,35")  # the plan's priority order
ap.add_argument("--labels", default="", help="comma-separated solver batches instead of this machine's v4 batches")
ap.add_argument("--include-existing", action="store_true", help="also print labels already in the data folder or queue (for checking)")
ap.add_argument("--restore-state", action="store_true", help="after batches restore the trajectory's saved state instead of replaying it")
ap.add_argument("--score-every", type=int, default=0, help="one job per run: score and roll back every N turns")
ap.add_argument("--score-at", default="", help="one job per run: score and roll back at these turns (comma-separated)")
ap.add_argument("--label-prefix", default="hz", help="the per-run label's prefix")
ap.add_argument("--min-timeout", type=int, default=0, help="per-run jobs: -p score_min_timeout=N (a floor on command limits while scoring)")
ap.add_argument("--keep-build-cache", action="store_true", help="per-run jobs: -p score_keep_build_cache=true")
a = ap.parse_args()
labels = [x for x in a.labels.split(",") if x] or batches()
queued = set()
if (QUEUE / "jobs.tsv").is_file():
    queued = {ln.split("\t", 1)[0] for ln in (QUEUE / "jobs.tsv").read_text().splitlines() if ln.strip()}

src = []  # (label, log, traj part of the command, [(task, turns)])
for lab in labels:
    logs = sorted((EVALS / lab).glob("*.eval"))
    metas = sorted(RUNS.glob(f"{lab}/*/*/meta.json"))
    if len(logs) != 1:
        note(f"skip {lab}: expected one .eval log in {EVALS / lab}, found {len(logs)}")
        continue
    if not (RUNS / lab / "summary.json").is_file() or not metas:
        note(f"skip {lab}: not exported yet (no {RUNS / lab}/summary.json or no runs): still running?")
        continue
    pa = policy_args(lab, metas)
    traj = ""
    if "after" in lab:
        if not pa.get("traj"):
            note(f"skip {lab}: an after batch, but its policy args name no trajectory")
            continue
        traj = (f" -p traj={pa['traj']} -p traj_user={pa.get('traj_user', 'dev')}"
                f" -p traj_cmd_bug={pa.get('traj_cmd_bug', 'false')}")
        if a.restore_state:
            traj += f" -p restore_state={Path(pa['traj']).stem}"
    runs = [(json.loads(m.read_text())["task"], turns(m.parent)) for m in metas]
    src.append((lab, logs[0], traj, runs))


def question_task(task: str) -> bool:
    """A question task (task_category research): its scorer reads the submitted answer, which a replay never submits."""
    info = CT / ".environments" / "model_registry" / "main_tasks" / task / "info.yml"
    return info.is_file() and re.search(r"^task_category:\s*research\s*$", info.read_text(), re.M) is not None


def has_setup(task: str) -> bool:
    """A task with a planted bug: its setup runs before the policy, so restoring a saved state would wipe the bug."""
    return (CT / ".environments" / "model_registry" / "main_tasks" / task / "mutation.patch").is_file()


n = skipped_done = skipped_queued = 0
per_run = bool(a.score_every or a.score_at)
for lab, log, batch_traj, runs in src if per_run else []:
    for task, t in runs:
        pts = score_points(a.score_every, a.score_at, t)
        if not pts or question_task(task):
            continue
        restores = a.restore_state and not has_setup(task)
        traj = batch_traj if restores else re.sub(r" -p restore_state=\S+", "", batch_traj)
        how = " from the trajectory's saved state" if restores else " after the trajectory"
        hz = f"{a.label_prefix}-{lab}-{SHORT[task]}"
        if not a.include_existing and ((EVALS / hz).exists() or (DATA / "runs" / hz).exists()):
            skipped_done += 1
            continue
        if not a.include_existing and hz in queued:
            skipped_queued += 1
            continue
        where = (f"every {a.score_every} turns" if a.score_every else "") + (" and " if a.score_every and a.score_at else "") \
            + (f"H = {a.score_at}" if a.score_at else "")
        purpose = (f"Score and roll back: all {t} model turns of {lab}'s {task} run, replayed with no model calls"
                   f"{how if traj else ''} in one machine, scored and restored at {where} ({len(pts)} points), "
                   f"then scored at its end")
        score = ((f" -p score_every={a.score_every}" if a.score_every else "") + (f" -p score_at={a.score_at}" if a.score_at else "")
                 + (f" -p score_min_timeout={a.min_timeout}" if a.min_timeout else "")
                 + (" -p score_keep_build_cache=true" if a.keep_build_cache else ""))
        print(f'{hz}\t1\tPURPOSE="{purpose}" bash {LAUNCH} {hz} tasks/one_{task}.txt 1 -p solver_user=dev -p solve=false'
              f"{traj} -p prefix_log={log} -p prefix_turns={t}{score}")
        n += 1
for h in (int(x) for x in a.horizons.split(",")) if not per_run else []:
    for lab, log, traj, runs in src:
        for task, t in runs:
            if h >= t:
                continue
            hz = f"hz-{lab}-{SHORT[task]}-H{h}"
            if not a.include_existing and ((EVALS / hz).exists() or (DATA / "runs" / hz).exists()):
                skipped_done += 1
                continue
            if not a.include_existing and hz in queued:
                skipped_queued += 1
                continue
            purpose = (f"Per-step scoring: the first {h} of {t} model turns of {lab}'s {task} run, replayed "
                       f"with no model calls{' after the trajectory' if traj else ''}, then scored")
            job_traj = re.sub(r" -p restore_state=\S+", "", traj) if has_setup(task) else traj
            print(f'{hz}\t1\tPURPOSE="{purpose}" bash {LAUNCH} {hz} tasks/one_{task}.txt 1 -p solver_user=dev -p solve=false'
                  f"{job_traj} -p prefix_log={log} -p prefix_turns={h}")
            n += 1
note(f"{n} jobs from {len(src)} batches ({', '.join(s[0] for s in src) or 'none'}); "
     f"skipped {skipped_done} already in the data folder, {skipped_queued} already in queue/jobs.tsv")
