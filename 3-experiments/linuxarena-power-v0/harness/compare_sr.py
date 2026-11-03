"""Compare score and roll back's per-point scores with the per-step records (plans/score-and-rollback-scope.md, §6).

For every run of the given labels that has horizon_scores.jsonl, from the exported records only:
  - each scoring point H that a per-step job also scored (runs/hz-<source>-<task short name>-H<H>, and its reruns
    -H<H>-*): the same list of checks, in order, each passing or failing the same, and the same verdict;
  - the job's own end score (the whole run replayed) against the solver run's own score;
  - every restore's state check (state_equal), with the differences when there are any.
For the bug fix the checks are the target tests of our rerun; for a scorer with no check list, its pass count.
  python3 -I compare_sr.py LABEL [LABEL ...] [--json out.json]     (exit 1 if any pair or end score differs)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import RUNS  # noqa: E402
from task_names import SHORT  # noqa: E402


def check_list(sc: dict) -> dict:
    """What is compared: the verdict, and the checks in order as (name, passed); or the target tests; or the counts."""
    p = sc.get("parsed") or {}
    expl = next((v.get("explanation") or "" for v in (sc.get("scorer") or {}).values()), "")
    out = {"verdict": p.get("verdict"), "error": "Error scoring" in expl or "timed out" in expl}
    if sc.get("bugfix_tests"):
        out["checks"] = [(t["test"], t["outcome"]) for t in sc["bugfix_tests"]]
    elif sc.get("checks"):
        out["checks"] = [(c["check"].split(" — ")[0].strip(), c["passed"]) for c in sc["checks"]]
    else:
        out["checks"] = [("passed/total", f"{p.get('checks_passed')}/{p.get('checks_total')}")]
    return out


def differences(a: dict, b: dict) -> list[str]:
    out = []
    if a["verdict"] != b["verdict"]:
        out.append(f"verdict {a['verdict']} vs {b['verdict']}")
    if a["checks"] != b["checks"]:
        da, db = dict(a["checks"]), dict(b["checks"])
        changed = [f"{k}: {da.get(k)} vs {db.get(k)}" for k in sorted(set(da) | set(db)) if da.get(k) != db.get(k)]
        out.append("checks: " + ("; ".join(changed) if changed else "same names and results, different order or count"))
    return out


def scores_of(label_glob: str, task: str) -> list[tuple[str, dict]]:
    return [(p.parent.relative_to(RUNS).as_posix(), json.loads(p.read_text()))
            for p in sorted(RUNS.glob(f"{label_glob}/{task}/*/scores.json"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args()
    report, bad = [], 0
    for label in a.labels:
        for f in sorted(RUNS.glob(f"{label}/*/*/horizon_scores.jsonl")):
            run = f.parent
            meta = json.loads((run / "meta.json").read_text())
            task, src = meta["task"], Path(meta["args"]["prefix_log"]).parent.name
            rows = [json.loads(ln) for ln in f.read_text().splitlines()]
            job = {"label": label, "task": task, "source": src, "points": len(rows),
                   "planned_points": len(meta.get("score_points") or []), "pairs": [], "state": []}
            for r in rows:
                job["state"].append({"H": r["H"], "state_equal": r.get("state_equal"), "error": r.get("error"),
                                     "seconds": r.get("seconds"),
                                     "differences": (r.get("restore") or {}).get("differences"),
                                     "service_restarted": (r.get("restore") or {}).get("service_restarted"),
                                     "db": (r.get("restore") or {}).get("db")})
                new = check_list(r["scores"])
                for path, sc in scores_of(f"hz-{src}-{SHORT[task]}-H{r['H']}", task) + \
                        scores_of(f"hz-{src}-{SHORT[task]}-H{r['H']}-*", task):
                    old = check_list(sc)
                    d = differences(old, new)
                    job["pairs"].append({"H": r["H"], "old": path, "same": not d, "differences": d,
                                         "old_scorer_error": old["error"], "new_scorer_error": new["error"],
                                         "passed": sum(1 for _, v in new["checks"] if v in (True, "PASSED"))})
            own = scores_of(src, task)
            end = json.loads((run / "scores.json").read_text())
            if own:
                d = differences(check_list(own[0][1]), check_list(end))
                job["end"] = {"own": own[0][0], "same": not d, "differences": d}
            bad += sum(1 for p in job["pairs"] if not p["same"]) + (0 if job.get("end", {}).get("same", True) else 1)
            report.append(job)
            n_same = sum(1 for p in job["pairs"] if p["same"])
            print(f"{label} {task}: {job['points']} of {job['planned_points']} points scored; "
                  f"{n_same} of {len(job['pairs'])} pairs with a per-step record identical; "
                  f"end score {'identical to' if job.get('end', {}).get('same') else 'DIFFERENT from'} the run's own; "
                  f"state equal after {sum(1 for s in job['state'] if s['state_equal'])} of {len(rows)} restores")
            for p in job["pairs"]:
                if not p["same"]:
                    print(f"  H={p['H']} differs from {p['old']}: {'; '.join(p['differences'])}")
            if not job.get("end", {}).get("same", True):
                print(f"  end differs from {job['end']['own']}: {'; '.join(job['end']['differences'])}")
            for s in job["state"]:
                if not s["state_equal"]:
                    print(f"  restore after H={s['H']} not exact: {s['error'] or json.dumps(s['differences'])[:400]}")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
    print(f"\n{bad} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
