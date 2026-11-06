"""Tests for schedule_error.py on synthetic runs with known answers. No environment, no model calls, no real records.
Run in WSL:  python3 -I test_schedule_error.py   (prints each test and exits non-zero on a failure)
"""

import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
import power_horizons as ph  # noqa: E402
import schedule_error as se  # noqa: E402

TASK = "custom_validation_rules_engine"  # a task that tests the running service
REBUILD_TASK = "abstract_middleware_chain"
failures = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name} {detail}")
    if not cond:
        failures.append(name)


def close(a, b, tol=1e-9):
    return math.isclose(a, b, abs_tol=tol)


def make_run(T, fn, flags=None, classes=None, arm="A1", task=TASK, full=True):
    """A run in memory: fn(H) gives {check: passed} at every H = 0..T, so this is its every-turn truth."""
    scored = {h: {"kind": "checks", "x": fn(h), "path": f"x#H{h}"} for h in range(T + 1)}
    names = sorted({c for o in scored.values() for c in o["x"]})
    r = {"arm": arm, "task": task, "src": "x", "turns": T, "T": T, "full": full, "scored": scored, "flags": flags or {},
         "classes": classes or {}, "uncertain_turns": 0, "checks": names, "free": 0, "family": se.family_of(task),
         "items": {h: frozenset(c for c, v in fn(h).items() if v) for h in range(T + 1)}, "base0_items": frozenset()}
    se.finish_run(r)
    return r


# 1. Which points each schedule keeps. T = 23: points are 1..22; the end and H = 0 are free, so they are never counted.
r = make_run(23, lambda h: {"a": False})
check("every 5 keeps 5, 10, 15, 20", se.every(r, 5) == {5, 10, 15, 20})
check("every 10 keeps 10, 20", se.every(r, 10) == {10, 20})
check("every turn to 4, then every 10", se.dense_then(r, 4, 10) == {1, 2, 3, 4, 10, 20})

# 2. One step: the check starts passing at H = 7 of 20 and stays. Every 5 sees it at 10, so H = 7, 8, 9 are wrong by 1.
step = make_run(20, lambda h: {"a": h >= 7})
e = se.evaluate([step], lambda r: se.every(r, 5))
check("one step, every 5: 3 wrong points of 19", e["curve"]["points_wrong"] == 3 and e["points"] == 19 and e["kept"] == 3, str(e["curve"]))
check("one step, every 5: mean error 3/19, max 1", close(e["curve"]["mean_abs"], 3 / 19) and close(e["curve"]["max_abs"], 1))
check("one step, every 5: summed POWER_H is low by 3/80", close(e["power_per_task_and_arm"]["summed"]["mean_signed"], -3 / 80))
expect = -sum(0.1 * 0.9 ** (h - 1) for h in (7, 8, 9))
check("one step, every 5: discounted 0.9 error", close(e["power_per_task_and_arm"]["discounted_0.9"]["mean_signed"], expect))
check("one step, every 5: budget 10 and 80 are right", close(e["power_per_task_and_arm"]["fixed_budget_10"]["max_abs"], 0) and close(e["power_per_task_and_arm"]["fixed_budget"]["max_abs"], 0))
check("one step, every 5: called a delay", e["wrong_stretches"] == {"delayed": 1}, str(e["wrong_stretches"]))
check("one step, every 5: not exact", e["exact"] is False)

# 3. Bisection finds that step exactly: midpoints 10, 5, 7, 6, and nothing else.
check("bisection on one step scores 10, 5, 7, 6", se.bisect(step, "list") == {10, 5, 7, 6}, str(sorted(se.bisect(step, "list"))))
check("bisection on one step is exact", se.evaluate([step], lambda r: se.bisect(r, "list"))["exact"])

# 4. A change that reverts between agreeing ends: bisection scores nothing and is wrong on those 3 points, and counts it.
rev = make_run(20, lambda h: {"a": 3 <= h <= 5})
st = Counter()
check("revert: ends agree, nothing scored", se.bisect(rev, "list", stats=st) == set())
check("revert: the failed assumption is counted", st["intervals with agreeing ends"] == 1 and st["of which something inside differs"] == 1, str(dict(st)))
e = se.evaluate([rev], lambda r: se.bisect(r, "list"))
check("revert: 3 wrong points, called reverted", e["curve"]["points_wrong"] == 3 and e["wrong_stretches"] == {"reverted": 1}, str(e["wrong_stretches"]))
rv = se.reversals([rev])
check("revert: one check changes and changes back", rv["checks_that_do"] == 1 and rv["runs_with_a_check_that_changes_and_changes_back"] == 1)

# 5. List against count: one check takes over from another. The count never moves, the list does.
swap = make_run(20, lambda h: {"a": h < 10, "b": h >= 10})
check("swap: by count, ends agree", se.bisect(swap, "count") == set())
check("swap: by list, ends differ", len(se.bisect(swap, "list")) > 0)
check("swap: both exact on the curve", se.evaluate([swap], lambda r: se.bisect(r, "count"))["exact"] and se.evaluate([swap], lambda r: se.bisect(r, "list"))["exact"])
check("foresight: count changes nowhere, list at one turn", se.only_count_changes(swap) == set() and se.only_list_changes(swap) == {10})


# 6. Same-state rows. H = 6 is recorded same-state and also really equal; H = 12 was scored anyway and differs (a noisy check).
def flag(**k):
    return {"label": "l", "reused_from": False, "same_state_as": None, "dedup_audit_of": None, "dedup_differs": None, "job_dedup": True,
            "seconds": 30.0, "upper_entries": 5, **k}


flags = {h: flag() for h in range(1, 20)}
flags[6] = flag(same_state_as=5)
flags[12] = flag(dedup_audit_of=11)
noisy = make_run(20, lambda h: {"a": h >= 3, "n": h == 12}, flags=flags)
e = se.evaluate([noisy], se.skip_same_state)
check("same state: both rows skipped", e["kept"] == 17, str(e["kept"]))
check("same state: the noisy audit shows as one wrong point", e["curve"]["points_wrong"] == 1 and close(e["curve"]["max_abs"], 0.5))
check("same state: the time of skipped points is measured", close(e["share_of_measured_point_time_saved"], 1 / 18), str(e["share_of_measured_point_time_saved"]))
quiet_run = se.drop_check(noisy, "n")
check("without the noisy check: exact", se.evaluate([quiet_run], se.skip_same_state)["exact"])
check("without the noisy check: its share is out of 1 check", close(quiet_run["truth"][5], 1.0) and quiet_run["checks"] == ["a"])

# 7. Dropping a check from a count-only scorer: 12/16 with it, 11/15 without; free passes lose it too if it was free.
scored = {h: {"kind": "counts", "x": (12, 16), "path": "x"} for h in range(4)}
cr = {"arm": "A1", "task": se.NOISY_TASK, "src": "x", "turns": 3, "T": 3, "full": True, "scored": scored, "flags": {}, "classes": {}, "uncertain_turns": 0,
      "checks": [], "free": 2, "family": "running service", "items": {h: frozenset({"n"}) for h in range(4)}, "base0_items": frozenset({"n"})}
se.finish_run(cr)
check("counts: share before", close(cr["truth"][1], 10 / 14))
d = se.drop_check(cr, "n")
check("counts: share without the check", close(d["truth"][1], (11 - 1) / (15 - 1)) and d["free"] == 1, str(d["truth"][1]))

# 8. What a command does, by its text.
for cmd, want in (("cat /app/x.go | head -5", {"read"}), ("cd /app/model-registry && grep -n foo main.go", {"read"}),
                  ("sed -n '1,5p' /app/x.go", {"read"}), ("sed -i 's/a/b/' /app/x.go", {"edit"}), ("cat > /app/x.go <<'EOF'\nsed -i rm -rf\nEOF", {"edit"}),
                  ("echo hi > /tmp/note", {"tmp"}), ("cd /app/model-registry && go build -o model-registry .", {"build"}), ("sudo /app/restart.sh", {"restart"}),
                  ("/app/rebuild.sh | tail -3", {"build"}), ("go vet ./...", {"gotool"}), ("go mod tidy", {"edit"}), ("curl -s http://x/health", {"read"}),
                  ("curl -s -X POST http://x/auth/login -d '{}'", {"read"}), ("curl -s -X POST http://x/api/models -d '{}'", {"api"}),
                  ("psql -c 'SELECT 1'", {"read"}), ("psql -c 'DELETE FROM t'", {"api"}), ("python3 -c 'print(1)'", {"read"}),
                  ("python3 - <<'EOF'\nopen('/app/x','w').write('y')\nEOF", {"script"}), ("bash /tmp/run.sh", {"script"}), ("grep -rn foo ./services", {"read"}),
                  ("ls 2>/dev/null", {"read"}), ("grep 'rm -rf' /app/x.sh", {"read"})):
    got = se.classify_command(cmd)
    check(f"command: {cmd.splitlines()[0][:44]}", got == want, f"{sorted(got)} wanted {sorted(want)}")
check("turn: no call is none", se.classify_turn([{"fn": "none"}]) == {"none"})
check("turn: submit alone is none", se.classify_turn([{"fn": "submit", "args": "{}"}]) == {"none"})
check("turn: the editor's view reads", se.classify_turn([{"fn": "text_editor", "args": json.dumps({"command": "view", "path": "/app/x"})}]) == {"read"})
check("turn: the editor's replace edits", se.classify_turn([{"fn": "text_editor", "args": json.dumps({"command": "str_replace", "path": "/app/x"})}]) == {"edit"})
check("turn: classes add up over calls", se.classify_turn([{"fn": "bash", "args": json.dumps({"cmd": "ls"})}, {"fn": "bash", "args": json.dumps({"cmd": "go build ."})}]) == {"read", "build"})

# 9. The scorer-kind rule: a running-service scorer ignores edits and builds; one that rebuilds ignores restarts.
cl = {1: {"edit"}, 2: {"build"}, 3: {"restart"}, 4: {"read"}, 5: {"api"}, 6: {"none"}}
run_service = make_run(7, lambda h: {"a": False}, classes=cl)
rebuild = make_run(7, lambda h: {"a": False}, classes=cl, task=REBUILD_TASK)
check("kind rule: running service keeps restart and API turns", se.family_rule(run_service) == {3, 5}, str(se.family_rule(run_service)))
check("kind rule: rebuilding scorer keeps edit and API turns", se.family_rule(rebuild) == {1, 5}, str(se.family_rule(rebuild)))
check("read-only rule keeps the rest", se.not_read_only(run_service) == {1, 2, 3, 5})
restarts = make_run(7, lambda h: {"a": False}, classes=cl, task="postgresqlbacked_job_queue")
check("kind rule: an always-restart scorer, as first written, keeps build and API turns", se.family_rule_first(restarts) == {2, 5})
check("kind rule: ... and as amended, restart turns too", se.family_rule(restarts) == {2, 3, 5})

# 10. Turn boundaries from a transcript: steps number tool calls, and only a turn's first call shows its reasoning.
tr = """# x

## Prompts as sent

````text
## Steps
### Step 99: `bash`
````

## Steps

### Step 1: `bash`

**Reasoning**

````text
r
````

**Tool call**

````json
{"cmd": "ls"}
````

**Output**

````text
### Step 50: `bash`
````

### Step 2: `bash`

**Tool call**

````json
{"cmd": "go build ."}
````

### Step 3: `bash`

**Tool call**

````json
{"cmd": "sed -i s/a/b/ /app/x"}
````

### Step 4: `submit`

**Reasoning**

````text
r
````

**Tool call**

````json
{}
````
"""
steps = se.parse_steps(tr)
check("transcript: fences hide look-alike headings", len(steps) == 4 and steps[0]["args"] == '{"cmd": "ls"}', str(len(steps)))
turns, unc = se.split_turns(steps, [True, False, True])  # step 3 has no reasoning, and usage says a turn without reasoning sits there
check("transcript: 3 turns from 4 steps, one ambiguous stretch", [len(t) for t in turns] == [2, 1, 1] and unc == 1, str([len(t) for t in turns]))
turns, unc = se.split_turns(steps, [True, True])
check("transcript: 2 turns, nothing ambiguous", [len(t) for t in turns] == [3, 1] and unc == 0, str([len(t) for t in turns]))


# 11. End to end on files: two arms, a rerun label replacing a point, a run cut short by an inexact restore.
def write_run(root, label, task, checks, turns=0, prefix=None):
    d = root / label / task / "e1-00000001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scores.json").write_text(json.dumps({"checks": [{"check": f"{c} — detail", "passed": v} for c, v in checks.items()], "bugfix_tests": [], "parsed": {}}))
    (d / "usage.csv").write_text("call,output_tokens,reasoning_chars\n" + "".join(f"{i},10,5\n" for i in range(turns)))
    args = {"prefix_log": f"/x/evals/{prefix[0]}/x.eval", "prefix_turns": prefix[1], "score_dedup": False} if prefix else {}
    (d / "meta.json").write_text(json.dumps({"task": task, "args": args}))
    (root / label / "summary.json").write_text(json.dumps({"label": label}))
    if turns:  # a solver run: one read-only turn per model call
        body = "".join(f"### Step {i + 1}: `bash`\n\n**Reasoning**\n\n````text\nr\n````\n\n**Tool call**\n\n````json\n" + json.dumps({"cmd": "ls"}) + "\n````\n\n" for i in range(turns))
        (d / "transcript.md").write_text("# x\n\n## Steps\n\n" + body)
    return d


def write_rows(root, label, task, src, turns, fn, hs, bad_after=None):
    d = write_run(root, label, task, fn(turns), 0, (src, turns))
    rows = [{"H": h, "state_equal": h != bad_after, "seconds": {"save": 1, "score": 2, "restore": 3}, "scores": {"checks": [{"check": f"{c} — detail", "passed": v} for c, v in fn(h).items()], "bugfix_tests": [], "parsed": {}}} for h in hs]
    (d / "horizon_scores.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))


with tempfile.TemporaryDirectory() as t:
    root = Path(t) / "runs"
    root.mkdir()
    fb = lambda h: {"a": h >= 15, "free": True}  # noqa: E731
    fa = lambda h: {"a": h >= 7, "free": True}  # noqa: E731
    for lab in ("nw-before", "nw-after"):
        write_run(root, lab, TASK, {"a": False, "free": True})
    write_run(root, "before", TASK, fb(20), 20)
    write_run(root, "after", TASK, fa(20), 20)
    write_rows(root, "sr-before-x", TASK, "before", 20, fb, range(1, 20))
    write_rows(root, "sr-after-x", TASK, "after", 20, lambda h: {"a": True, "free": True}, range(1, 20))  # a bad first job
    write_rows(root, "sr-after-x-r2", TASK, "after", 20, fa, range(1, 20))  # replaces it at every H
    other = "model_favoriting_system"
    write_run(root, "nw-before", other, {"x": False})
    write_run(root, "nw-after", other, {"x": False})
    write_run(root, "before", other, {"x": False}, 20)
    write_run(root, "after", other, {"x": False}, 20)
    write_rows(root, "sr-after-y", other, "after", 20, lambda h: {"x": False}, range(1, 20), bad_after=9)  # valid to H = 9
    before_files = sorted(str(p) for p in root.rglob("*"))
    arms = {"before": ("before", "nw-before"), "A1": ("after", "nw-after")}
    sample, inv = se.load_runs(arms, root)
    by = {(r["arm"], r["task"]): r for r in sample}
    check("files: three runs in the sample", len(sample) == 3 and ("before", other) not in by, str(sorted(by)))
    a = by[("A1", TASK)]
    check("files: the rerun label's rows are in force", a["items"][3] == frozenset({"free"}) and all(a["flags"][h]["label"] == "sr-after-x-r2" for h in a["points"]))
    check("files: the free pass is left out", a["checks"] == ["a"], str(a["checks"]))
    check("files: truth rises at 7", close(a["truth"][6], 0) and close(a["truth"][7], 1) and close(a["truth"][80], 1))
    # the same truth as power_horizons' own curve, built from its own reader
    ph.ROLLBACK_ROWS = True
    found = se.quiet(ph.prefix_runs)
    s = {0: se.quiet(ph.one_per_task, "nw-after")[TASK], **found[("after", TASK)], 20: se.quiet(ph.one_per_task, "after")[TASK]}
    check("files: truth equals power_horizons.curve", ph.curve(s, ["a"], 0, reward="last-scored")[0] == a["truth"])
    cut = by[("A1", other)]
    check("files: a run cut by an inexact restore is a shorter run, out of POWER_H", cut["T"] == 9 and not cut["full"] and cut["points"] == list(range(1, 9)), str(cut["points"]))
    e = se.evaluate(sample, lambda r: se.every(r, 5))
    check("files: POWER_H covers only full runs", e["power_per_task_and_arm"]["runs"] == 2)
    # before passes at 15 (seen at 15), after at 7 (seen at 10): after minus before is 8/80 true, 5/80 with every 5
    d = e["arm_differences"]["A1 minus before"]
    check("files: arm difference, truth 8/80", close(d["summed"]["truth"], 8 / 80), str(d["summed"]["truth"]))
    check("files: arm difference, every 5 gives 5/80", close(d["summed"]["schedule"], 5 / 80) and close(d["summed"]["error"], -3 / 80), str(d["summed"]["schedule"]))
    check("files: arm difference names its tasks", d["tasks"] == [TASK])
    rep = se.report(sample)
    check("files: every schedule ran", set(rep["schedules"]) == {n for _, n, _ in se.SCHEDULES})
    check("files: read-only turns skip everything here", rep["schedules"]["skip turns the commands say are read-only"]["kept"] == 0)
    check("files: foresight keeps only the change points", rep["schedules"]["only turns where the count changes"]["kept"] == 2)
    m = se.memoization(sample, root, arms)
    check("files: one run per cell", m["solver_runs"]["cells_with_more_than_one_run"] == 0)
    check("files: a superseded job's disagreement is counted as a repeat", m["same_point_scored_twice"]["a superseded score and roll back job"]["pairs"] == 19)
    check("files: reading writes nothing", sorted(str(p) for p in root.rglob("*")) == before_files)

print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
