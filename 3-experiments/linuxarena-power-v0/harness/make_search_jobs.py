"""Print the next round of per-step scoring jobs that narrow down where checks change (plans/score-and-rollback-scope.md,
section 10). Jobs are the usual per-step jobs (fresh machine, replay, real scorer); only the choice of H is new.

For each arm and task, it takes the horizons already scored (H = 0 from the no-work run, the per-step scores, and the
run's own end score). For every gap between neighbouring scored horizons whose results differ (a different set of
passing checks, or a different count for the count-scored refactor task), it schedules the middle turn. A horizon
whose scorer crashed counts as unscored and is retried, at most MAX_TRIES times in all, after which the nearest other
turn in the gap is used. The question task is skipped: its scorer only reads the final answer. Run in WSL; append
the output to queue/jobs.tsv. Prints nothing when every changing gap is down to one turn.
  python3 make_search_jobs.py [--max-jobs N]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import power_horizons as ph  # noqa: E402
from power_paths import DATA, LAUNCH, TRAJECTORY  # noqa: E402
from task_names import SHORT  # noqa: E402  the per-step jobs' task short names, as in make_hz_jobs.py

ARMS = [("v2-before", "nowork-v2-S0", ""),
        ("v2-afterA", "nowork-v2-afterA", str(TRAJECTORY / "traj2-control.eval")),
        ("v3-afterB", "nowork-v3-afterB", str(TRAJECTORY / "traj3-power.eval"))]
SKIP_TASKS = {"untracked_s3_objects_total_bytes"}
MAX_TRIES = 3
EVALS = DATA / "evals"


def result_key(o: dict):
    return o["x"][0] if o["kind"] == "counts" else frozenset(c for c, v in o["x"].items() if v)


def tries(base: str) -> list[str]:
    """Labels already used for this horizon: base, base-r2, base-r3, ..."""
    return sorted(p.name for p in EVALS.glob(base + "*") if p.is_dir() and (p.name == base or p.name.startswith(base + "-r")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-jobs", type=int, default=200)
    a = ap.parse_args()
    pre = ph.prefix_runs()
    attempted = {}  # (label, task, H) -> number of labels already used
    jobs = []
    for lab, nw, traj in ARMS:
        solver, zero = ph.one_per_task(lab), ph.one_per_task(nw)
        log = sorted((EVALS / lab).glob("*.eval"))[0]
        for task, end in solver.items():
            if task in SKIP_TASKS or end["kind"] == "error":
                continue
            s = {0: zero[task]} if task in zero and zero[task]["kind"] != "error" else {}
            s.update({h: v for h, v in pre.get((lab, task), {}).items() if h < end["turns"] and v["kind"] != "error"})
            s[end["turns"]] = end
            hs = sorted(s)
            for lo, hi in zip(hs, hs[1:]):
                if hi - lo < 2 or result_key(s[lo]) == result_key(s[hi]):
                    continue
                inside = range(lo + 1, hi)
                order = sorted(inside, key=lambda h: (abs(h - (lo + hi) / 2), h))  # the middle first
                for h in order:
                    base = f"hz-{lab}-{SHORT[task]}-H{h}"
                    used = tries(base)
                    if len(used) >= MAX_TRIES:
                        continue  # this turn keeps crashing: try the nearest other turn in the gap
                    label = base if not used else f"{base}-r{len(used) + 1}"
                    purpose = (f"Gap search: H={h} of {end['turns']} in {lab}'s {task} run, between scored H={lo} and "
                               f"H={hi} whose results differ; replayed with no model calls, then scored")
                    tr = f" -p traj={traj} -p traj_user=dev -p traj_cmd_bug=false" if traj else ""
                    jobs.append(f'{label}\t1\tPURPOSE="{purpose}" bash {LAUNCH} {label} tasks/one_{task}.txt 1 '
                                f"-p solver_user=dev -p solve=false{tr} -p prefix_log={log} -p prefix_turns={h}")
                    break
    for j in jobs[: a.max_jobs]:
        print(j)
    print(f"# {len(jobs)} gap-search jobs", file=sys.stderr)


if __name__ == "__main__":
    main()
