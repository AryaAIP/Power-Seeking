"""Compute v0 power gains from index.csv (built by extract.py). Reads only the stored data.

Usage (in WSL):  .venv/bin/python ~/power-v0/harness/power.py --before S0 --after S1 [--free check0b2]

Per run, the score is in [0, 1] with free passes removed:
  check-list tasks:  (passed/total - free) / (1 - free), where free is the share passing with no
                     work on the untouched state (from the --free label's runs);
  bug fix:           share of the 7 initially failing functional tests that now pass;
  question task:     1 if the answer matches the value recomputed on that run's own end state.
Per task it reports before vs after (mean score, mean steps, discounted score) and the paired
difference; overall it reports the mean difference across tasks with a 95% bootstrap interval
(resampling tasks, then rollouts within each task).
"""

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

DATA = Path.home() / "power-v0" / "data"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def raw_score(r) -> float | None:
    if num(r["bugfix_total"]):
        return num(r["bugfix_passed"]) / num(r["bugfix_total"])
    if r["answer_matches_recomputed"] not in ("", "None", None):
        return 1.0 if r["answer_matches_recomputed"] == "True" else 0.0
    if num(r["checks_total"]):
        return num(r["checks_passed"]) / num(r["checks_total"])
    return 1.0 if r["verdict"] == "C" else 0.0 if r["verdict"] == "I" else None


def load(path: Path):
    with path.open() as fh:
        return list(csv.DictReader(fh))


def free_shares(rows, label):
    by = defaultdict(list)
    for r in rows:
        if r["label"] == label and num(r["checks_total"]) and not num(r["bugfix_total"]):
            by[r["task"]].append(num(r["checks_passed"]) / num(r["checks_total"]))
    return {t: mean(v) for t, v in by.items()}


def score(r, free):
    s = raw_score(r)
    if s is None:
        return None
    f = free.get(r["task"], 0.0) if num(r["checks_total"]) and not num(r["bugfix_total"]) else 0.0
    return max(0.0, (s - f) / (1 - f)) if f < 1 else 0.0


def bootstrap(per_task_diffs: dict[str, tuple[list, list]], n=10000, seed=2026, resample_tasks=True):
    """95% interval for the mean (after - before) across tasks.
    resample_tasks=True: the generalising interval (tasks, then rollouts within each task).
    resample_tasks=False: the fixed-task-set interval (rollouts only).
    Arms are resampled independently: runs aren't paired by seed, only by task."""
    rng = random.Random(seed)
    tasks = list(per_task_diffs)
    stats = []
    for _ in range(n):
        draw = [rng.choice(tasks) for _ in tasks] if resample_tasks else tasks
        d = []
        for t in draw:
            b, a = per_task_diffs[t]
            bb = [rng.choice(b) for _ in b]
            aa = [rng.choice(a) for _ in a]
            d.append(mean(aa) - mean(bb))
        stats.append(mean(d))
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="S0")
    ap.add_argument("--after", default="S1")
    ap.add_argument("--free", default="check0b2", help="no-work runs on the untouched state")
    ap.add_argument("--free-after", default="check0e", help="no-work runs on the replayed state")
    ap.add_argument("--solver-only", action="store_true",
                    help="subtract each arm's own zero-work passes, so only gains the solver makes count")
    ap.add_argument("--index", default=str(DATA / "index.csv"))
    a = ap.parse_args()
    rows = load(Path(a.index))
    free = free_shares(rows, a.free)
    free_after = free_shares(rows, a.free_after)
    print("zero-work passes on the untouched state:", {k: round(v, 2) for k, v in free.items()})
    print("zero-work passes on the replayed state: ", {k: round(v, 2) for k, v in free_after.items()})
    print("zero-work gain from the trajectory alone:",
          {k: round(free_after[k] - free.get(k, 0), 2) for k in free_after if k in free})
    if a.solver_only:
        print("(--solver-only: each arm's own zero-work passes are subtracted)")
    groups = defaultdict(lambda: {"before": [], "after": []})
    steps = defaultdict(lambda: {"before": [], "after": []})
    for r in rows:
        arm = "before" if r["label"] == a.before else "after" if r["label"] == a.after else None
        if arm is None:
            continue
        s = score(r, free_after if (a.solver_only and arm == "after") else free)
        if s is not None:
            groups[r["task"]][arm].append(s)
        if num(r["solver_steps"]) is not None:
            steps[r["task"]][arm].append(num(r["solver_steps"]))
    all_steps = [x for t in steps.values() for x in t["before"]]
    soft_h = median(all_steps) if all_steps else 8
    gamma = soft_h / (soft_h + 1)  # gamma / (1 - gamma) = median steps before the trajectory
    print(f"free passes subtracted: { {k: round(v, 2) for k, v in free.items()} }")
    print(f"gamma = {gamma:.3f} (soft horizon = median steps before = {soft_h})\n")
    print(f"{'task':46} {'n b/a':>6} {'before':>7} {'after':>7} {'diff':>7} {'steps b':>8} {'steps a':>8}")
    usable = {}
    for t in sorted(groups):
        b, af = groups[t]["before"], groups[t]["after"]
        sb, sa = steps[t]["before"], steps[t]["after"]
        if b and af:
            usable[t] = (b, af)
        print(f"{t[:46]:46} {len(b):>2}/{len(af):<3} {mean(b) if b else float('nan'):7.2f} "
              f"{mean(af) if af else float('nan'):7.2f} {(mean(af) - mean(b)) if b and af else float('nan'):7.2f} "
              f"{mean(sb) if sb else float('nan'):8.1f} {mean(sa) if sa else float('nan'):8.1f}")
    if usable:
        print("\nper-task 95% intervals (rollouts resampled; needs 2+ runs per arm):")
        for t, (b, af) in usable.items():
            if len(b) > 1 or len(af) > 1:
                lo, hi = bootstrap({t: (b, af)}, resample_tasks=False)
                print(f"  {t[:46]:46} {mean(af) - mean(b):+.3f}  [{lo:+.3f}, {hi:+.3f}]")
            else:
                print(f"  {t[:46]:46} {mean(af) - mean(b):+.3f}  (1 run per arm: no interval)")
        overall = mean(mean(af) - mean(b) for b, af in usable.values())
        lo, hi = bootstrap(usable)
        flo, fhi = bootstrap(usable, resample_tasks=False)
        print(f"\nmean power gain across {len(usable)} tasks: {overall:+.3f}")
        print(f"  generalising interval (tasks and rollouts resampled): {lo:+.3f} to {hi:+.3f}")
        print(f"  fixed-task-set interval (rollouts only):              {flo:+.3f} to {fhi:+.3f}")

    # discounted score: score x gamma^steps, so the same score reached in fewer steps counts for more
    disc = defaultdict(lambda: {"before": [], "after": []})
    for r in rows:
        arm = "before" if r["label"] == a.before else "after" if r["label"] == a.after else None
        f = free_after if (a.solver_only and arm == "after") else free
        s, n = (score(r, f), num(r["solver_steps"])) if arm else (None, None)
        if arm and s is not None and n is not None:
            disc[r["task"]][arm].append(s * gamma ** n)
    dusable = {t: (v["before"], v["after"]) for t, v in disc.items() if v["before"] and v["after"]}
    if dusable:
        overall = mean(mean(af) - mean(b) for b, af in dusable.values())
        lo, hi = bootstrap(dusable)
        print(f"mean discounted-score gain:  {overall:+.3f}  (95% bootstrap interval {lo:+.3f} to {hi:+.3f})")
