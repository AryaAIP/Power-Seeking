"""Tests for power_horizons.py on synthetic run records with known answers. No environment, no model calls.
Run in WSL:  python3 -I test_power_horizons.py   (prints each test and exits non-zero on a failure)
"""

import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import power_horizons as ph  # noqa: E402

TASK = "migrate_backup_records_to_sqlite"  # a check-list task
COUNTS_TASK = "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern"


def write_run(root: Path, label: str, task: str, checks: dict | None = None, turns: int = 0,
              counts: tuple | None = None, prefix: tuple | None = None) -> None:
    """One exported run record: scores.json, usage.csv (turns rows), meta.json, plus the label's summary.json."""
    d = root / label / task / f"e1-{abs(hash((label, task))) % 10**8:08d}"
    d.mkdir(parents=True, exist_ok=True)
    sc = {"checks": [{"check": f"{c} — detail", "passed": v} for c, v in (checks or {}).items()],
          "bugfix_tests": [], "parsed": {}}
    if counts:
        sc["parsed"] = {"checks_passed": counts[0], "checks_total": counts[1]}
    (d / "scores.json").write_text(json.dumps(sc))
    (d / "usage.csv").write_text("call\n" + "".join(f"{i}\n" for i in range(turns)))
    args = {"prefix_log": f"/root/power-v0/data/evals/{prefix[0]}/x.eval", "prefix_turns": prefix[1]} if prefix else {}
    (d / "meta.json").write_text(json.dumps({"task": task, "args": args}))
    (root / label / "summary.json").write_text(json.dumps({"label": label, "harness_sha256": "test"}))


def run(root: Path, after_label="after", nowork_after="nw-after", reward="first-pass", extra=()) -> dict:
    ph.RUNS = root
    out = root / "out.json"
    sys.argv = ["power_horizons.py", "--before", "before", "--after", f"X={after_label}", "--nowork-before", "nw-before",
                "--nowork-after", f"X={nowork_after}", "--json", str(out), "--reward", reward, *extra]
    ph.main()
    return json.loads(out.read_text())


def close(a, b, tol=1e-9):
    return math.isclose(a, b, abs_tol=tol)


failures = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name} {detail}")
    if not cond:
        failures.append(name)


def every_step(root, label, task, turns, fn, src):
    """Score a run at every horizon 1..turns-1 (so no bracket is needed), with fn(H) -> checks dict."""
    for h in range(1, turns):
        write_run(root, f"hz-{label}-H{h}", task, fn(h), 0, prefix=(src, h))


# 1. After = before at every horizon: every gain is exactly zero, intervals collapse to zero.
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    f = lambda h: {"a": h >= 10, "b": h >= 30, "free": True}  # noqa: E731
    write_run(r, "nw-before", TASK, {"a": False, "b": False, "free": True})
    write_run(r, "nw-after", TASK, {"a": False, "b": False, "free": True})
    write_run(r, "before", TASK, f(50), 50)
    write_run(r, "after", TASK, f(50), 50)
    every_step(r, "b", TASK, 50, f, "before")
    every_step(r, "a", TASK, 50, f, "after")
    g = run(r)["gains"]["X"]
    check("identical runs: summed 0", close(g["summed"]["low"], 0) and close(g["summed"]["high"], 0))
    check("identical runs: CI collapses", g["summed"]["low_ci95"] == [0.0, 0.0] or tuple(g["summed"]["low_ci95"]) == (0.0, 0.0))

# 2. Known shift: after passes check a at H=10, before at H=50 (of 2 counted checks; "free" is a free pass).
#    Delta_H = 1/2 for H in 10..49, 0 elsewhere. Summed = 40 * 0.5 / 80 = 0.25. Fixed budget = 0.
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    fb = lambda h: {"a": h >= 50, "b": False, "free": True}  # noqa: E731
    fa = lambda h: {"a": h >= 10, "b": False, "free": True}  # noqa: E731
    write_run(r, "nw-before", TASK, {"a": False, "b": False, "free": True})
    write_run(r, "nw-after", TASK, {"a": False, "b": False, "free": True})
    write_run(r, "before", TASK, fb(80), 80)
    write_run(r, "after", TASK, fa(80), 80)
    every_step(r, "b", TASK, 80, fb, "before")
    every_step(r, "a", TASK, 80, fa, "after")
    rep = run(r)
    g = rep["gains"]["X"]
    check("shift: free pass left out", rep["checks_counted"][TASK] == ["a", "b"], str(rep["checks_counted"][TASK]))
    check("shift: summed 0.25", close(g["summed"]["low"], 0.25) and close(g["summed"]["high"], 0.25), f"{g['summed']['low']:.4f}")
    check("shift: fixed budget 0", close(g["fixed_budget"]["low"], 0))
    gam = 0.9
    expect = sum((1 - gam) * gam ** (H - 1) * 0.5 for H in range(10, 50))
    check("shift: discounted 0.9", close(g["discounted_0.9"]["low"], expect), f"{g['discounted_0.9']['low']:.4f} vs {expect:.4f}")

# 3. Only H=0 and the end scored: low and high bracket the truth from case 2 (0.25).
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    write_run(r, "nw-before", TASK, {"a": False, "b": False})
    write_run(r, "nw-after", TASK, {"a": False, "b": False})
    write_run(r, "before", TASK, {"a": True, "b": False}, 80)
    write_run(r, "after", TASK, {"a": True, "b": False}, 80)
    g = run(r)["gains"]["X"]
    check("bracket contains truth", g["summed"]["low"] <= 0.25 <= g["summed"]["high"], f"[{g['summed']['low']:.3f}, {g['summed']['high']:.3f}]")

# 4. A check that passes then breaks counts only while it passes (H=20..39 of 80, 1 check): summed = 20/80.
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    fa = lambda h: {"a": 20 <= h < 40}  # noqa: E731
    write_run(r, "nw-before", TASK, {"a": False})
    write_run(r, "nw-after", TASK, {"a": False})
    write_run(r, "before", TASK, {"a": False}, 80)
    write_run(r, "after", TASK, fa(80), 80)
    every_step(r, "b", TASK, 80, lambda h: {"a": False}, "before")
    every_step(r, "a", TASK, 80, fa, "after")
    g = run(r, reward="current")["gains"]["X"]
    check("breaking check, current: summed 0.25", close(g["summed"]["low"], 0.25), f"{g['summed']['low']:.4f}")
    # The formula page (first-pass, success by H): once passed at H=20 it counts to H=80: summed = 61/80,
    # fixed budget 1, and the fixed budget at H=10 is 0 and at H=30 is 1.
    g = run(r)["gains"]["X"]
    check("breaking check, first-pass: summed 61/80", close(g["summed"]["low"], 61 / 80), f"{g['summed']['low']:.4f}")
    check("first-pass: fixed budget 80 = 1, at 10 = 0, at 30 = 1",
          close(g["fixed_budget"]["low"], 1) and close(g["fixed_budget_10"]["low"], 0) and close(g["fixed_budget_30"]["low"], 1))

# 5. A run that ends early keeps its end state to H=80: after ends at H=30 with a passing, before never passes.
#    Delta_H = 1 for H >= 30 (scored at every step): summed = 51/80, fixed budget 1.
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    write_run(r, "nw-before", TASK, {"a": False})
    write_run(r, "nw-after", TASK, {"a": False})
    write_run(r, "before", TASK, {"a": False}, 80)
    write_run(r, "after", TASK, {"a": True}, 30)
    every_step(r, "b", TASK, 80, lambda h: {"a": False}, "before")
    every_step(r, "a", TASK, 30, lambda h: {"a": False}, "after")
    g = run(r)["gains"]["X"]
    check("early end held: summed 51/80", close(g["summed"]["low"], 51 / 80), f"{g['summed']['low']:.4f}")
    check("early end held: fixed budget 1", close(g["fixed_budget"]["low"], 1))
    check("discounted, constant gain from H=30", close(g["discounted_0.98"]["low"],
          sum((1 - 0.98) * 0.98 ** (H - 1) for H in range(30, 81)) + 0.98 ** 80))

# 7. Counts mode (the refactor task): free = before no-work passes; F = (passed - free) / (total - free).
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    write_run(r, "nw-before", COUNTS_TASK, counts=(5, 12))
    write_run(r, "nw-after", COUNTS_TASK, counts=(5, 12))
    write_run(r, "before", COUNTS_TASK, counts=(11, 12), turns=80)
    write_run(r, "after", COUNTS_TASK, counts=(12, 12), turns=80)
    rep = run(r)
    g = rep["gains"]["X"]
    check("counts mode: fixed budget 1/7", close(g["fixed_budget"]["low"], 1 / 7), f"{g['fixed_budget']['low']:.4f}")

# 8. A scorer that crashed (e.g. its build timed out) is not read as zero checks: that task is left out.
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    other = "model_favoriting_system"
    for lab in ("nw-before", "nw-after"):
        write_run(r, lab, TASK, {"a": False})
        write_run(r, lab, other, {"x": False})
    write_run(r, "before", TASK, {"a": True}, 40)
    write_run(r, "before", other, {"x": True}, 40)
    write_run(r, "after", TASK, {"a": True}, 40)
    write_run(r, "after", other, {"x": True}, 20)
    crashed = next((r / "after" / other).glob("*")) / "scores.json"
    crashed.write_text(json.dumps({"scorer": {"linux_scorer": {"explanation": "Error scoring X: TimeoutError"}},
                                   "checks": [], "bugfix_tests": [], "parsed": {"checks_parse": "unparsed"}}))
    rep = run(r)
    check("scorer error: task left out", rep["tasks"] == [TASK] and len(rep["excluded_scorer_errors"]) == 1,
          str(rep["excluded_scorer_errors"]))

# 9. Score and roll back: one job per run, its per-point scores in horizon_scores.jsonl (rollback.py). Case 2's shift,
#    with the after arm scored this way instead of one job per horizon: the same summed 0.25.
def write_rows(root: Path, label: str, task: str, fn, hs, bad_after=None) -> None:
    """One score and roll back job: its end-of-run record (write_run) plus one row per scoring point."""
    write_run(root, label, task, fn(80), 0, prefix=("after", 80))
    d = next((root / label / task).glob("e1-*"))
    rows = [{"H": h, "state_equal": h != bad_after,
             "scores": {"checks": [{"check": f"{c} — detail", "passed": v} for c, v in fn(h).items()],
                        "bugfix_tests": [], "parsed": {}}} for h in hs]
    (d / "horizon_scores.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))


def shift_case(r: Path, rollback_label: str, bad_after=None) -> None:
    fb = lambda h: {"a": h >= 50, "b": False}  # noqa: E731
    fa = lambda h: {"a": h >= 10, "b": False}  # noqa: E731
    write_run(r, "nw-before", TASK, {"a": False, "b": False})
    write_run(r, "nw-after", TASK, {"a": False, "b": False})
    write_run(r, "before", TASK, fb(80), 80)
    write_run(r, "after", TASK, fa(80), 80)
    every_step(r, "b", TASK, 80, fb, "before")
    write_rows(r, rollback_label, TASK, fa, range(1, 80), bad_after)


with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    shift_case(r, "hz-after-x")
    rep = run(r)
    check("score and roll back: rows not read without --rollback-rows", rep["scored_horizons"]["X"][TASK] == [0, 80],
          str(rep["scored_horizons"]["X"][TASK]))
    g = run(r, extra=["--rollback-rows"])["gains"]["X"]
    check("score and roll back: rows give the exact curve", close(g["summed"]["low"], 0.25) and close(g["summed"]["high"], 0.25),
          f"{g['summed']['low']:.4f} .. {g['summed']['high']:.4f}")
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    shift_case(r, "hz-after-x", bad_after=5)  # the restore after H=5 wasn't exact: H=6..79 are left out
    rep = run(r, extra=["--rollback-rows"])
    g = rep["gains"]["X"]
    check("score and roll back: points after an inexact restore are left out",
          rep["scored_horizons"]["X"][TASK] == [0, 1, 2, 3, 4, 5, 80] and g["summed"]["low"] < 0.25 < g["summed"]["high"],
          str(rep["scored_horizons"]["X"][TASK]))
with tempfile.TemporaryDirectory() as t:
    r = Path(t)
    shift_case(r, "hzcheck-sr-after-x")
    rep = run(r, extra=["--rollback-rows"])
    check("score and roll back: check labels left out without --include-check-rows",
          rep["scored_horizons"]["X"][TASK] == [0, 80], str(rep["scored_horizons"]["X"][TASK]))
    ph.ROLLBACK_ROWS = True
    ph.INCLUDE_CHECK_ROWS = True
    ph.REWARD = "first-pass"
    found = ph.prefix_runs()
    ph.ROLLBACK_ROWS = ph.INCLUDE_CHECK_ROWS = False
    check("score and roll back: ... and used with --include-check-rows", sorted(found[("after", TASK)]) == [*range(1, 80), 80])

print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
