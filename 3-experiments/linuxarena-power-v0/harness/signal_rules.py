"""Which free signals predict the turns where a run's check list changes? Offline, on the every-turn runs: no environment, no
model call. Plans: ../plans/scoring-schedules-analysis.md ("Free signals").

A signal is free if it costs nothing beyond what a replay or a real run already produces: the turn's commands, their output,
and which kind of scorer the task has. Each rule below says which turns to score. For each one this prints how many points it
keeps, how many list changes fall on turns it skips, and what that does to the curve.

  python3 -I signal_rules.py [--json OUT]

Builds on schedule_error.py, which owns the run loading, the turn classes and the evaluation. Set POWER_CACHE for speed.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_error as se  # noqa: E402

BUILD_FAILED = re.compile(r"(?m)^# [\w./-]+$|\.go:\d+:\d+: |^go: .*(error|cannot|missing)|build failed|Build failed")
NOT_SOURCE = re.compile(r"(_test\.go|\.md|\.txt|\.log|/tests?/[^/]*)$")
SIGNAL_CLASSES = ("restart", "build", "edit", "script", "api")


def edit_paths(call: dict) -> tuple[list[str], bool]:
    """What one tool call edits, by name, and whether it may edit something it doesn't name (a script, `go mod tidy`). Text only."""
    fn = call["fn"]
    try:
        a = json.loads(call.get("args") or "{}")
    except json.JSONDecodeError:
        a = {}
    a = a if isinstance(a, dict) else {}
    if fn != "bash":
        if a.get("command") == "view":
            return [], False
        p = str(a.get("path") or a.get("file_path") or "")
        return ([p] if p else []), not p
    cmd = a.get("cmd") if "cmd" in a else a.get("command")
    cmd = cmd if isinstance(cmd, str) else ""
    bare = se.QUOTED.sub("''", se.HEREDOC.sub(" <<HEREDOC\n", cmd))
    named: list[str] = []
    for segment in re.split(r"[;&|\n]+", bare):
        targets = [x or y for x, y in se.REDIRECT.findall(segment)]
        named += targets
        if se.MUTATES.search(segment):
            named += se.PATHS.findall(segment)
    unnamed = bool(se.EDITS_SOURCE.search(bare) or se.SCRIPT.search(re.sub(r"\S*\b(restart|rebuild)\.sh\b", "", bare))
                   or (se.PYTHON.search(bare) and se.PY_WRITES.search(cmd)))
    # a relative edit (`sed -i s/a/b/ main.go`) has no absolute path to name
    if se.MUTATES.search(bare) and not se.PATHS.findall(bare):
        unnamed = True
    return [p for p in named if not p.startswith(("/tmp", "/dev"))], unnamed


def only_non_source(paths: list[str], unnamed: bool) -> bool:
    """Every edit named is a test or a note, and nothing unnamed may have been edited."""
    return bool(paths) and not unnamed and all(NOT_SOURCE.search(p) for p in paths)


def turn_calls(r: dict) -> dict:
    """{H: this turn's tool calls, each with its output} from the source run's transcript."""
    d = next((se.ph.RUNS / r["src"] / r["task"]).glob("*/transcript.md"), None)
    if d is None:
        return {}
    with (d.parent / "usage.csv").open() as fh:
        usage = list(se.csv.DictReader(fh))
    if usage and "output_tokens" in usage[0]:
        usage = [u for u in usage if (u["output_tokens"] or "").strip() not in ("", "0")]
    reasoning = [int(u.get("reasoning_chars") or 0) > 0 for u in usage]
    turns, _ = se.split_turns(se.parse_steps(d.read_text(errors="replace"), with_output=True), reasoning)
    return {i + 1: t for i, t in enumerate(turns)}


def features(r: dict) -> dict:
    """{H: signals at turn H}, walking the run forward. `new_binary`: a build that didn't visibly fail since the last restart,
    this turn's included, so a restart here could put different code into the running service."""
    calls = turn_calls(r)
    out: dict = {}
    fresh_build = False
    for h in range(1, r["T"] + 1):
        cl = r["classes"].get(h, {"edit"})
        here = calls.get(h, [])
        output = "\n".join(c.get("output", "") for c in here)
        failed = "build" in cl and bool(BUILD_FAILED.search(output))
        paths: list[str] = []
        unnamed = False
        for c in here:
            p, u = edit_paths(c)
            paths += p
            unnamed = unnamed or u
        if "build" in cl and not failed:
            fresh_build = True
        out[h] = {"classes": cl, "build_failed": failed, "new_binary": fresh_build,
                  "edit_non_source": "edit" in cl and only_non_source(paths, unnamed)}
        if "restart" in cl:
            fresh_build = False
    return out


def _rule(want: dict, restart_needs_build=False, ignore_test_edits=False):
    def fn(r: dict) -> set:
        kept = set()
        for h in r["points"]:
            f = r["features"].get(h)
            if f is None:
                kept.add(h)
                continue
            cl = set(f["classes"]) & want[r["family"]]
            if restart_needs_build and r["family"] == "running service" and not f["new_binary"]:
                cl.discard("restart")
            if ignore_test_edits and f["edit_non_source"]:
                cl.discard("edit")
            if cl:
                kept.add(h)
        return kept
    return fn


def cell(r: dict, h: int) -> tuple:
    """What a learned rule may see: the kind of scorer, the turn's classes, and two stateful signals."""
    f = r["features"].get(h) or {"classes": {"edit"}, "new_binary": True, "edit_non_source": False}
    return (r["family"], tuple(c for c in SIGNAL_CLASSES if c in f["classes"]), bool(f["new_binary"]), bool(f["edit_non_source"]))


def changed(r: dict, h: int) -> bool:
    return r["value_list"][h] != r["value_list"][h - 1]


def leave_one_task_out(sample: list, min_seen: int = 1):
    """A rule learned from the data, tested on a task it never saw: skip a cell only if the other tasks saw it at least
    min_seen times and it never changed a list there. How far the signals could go on new tasks, without my hand on the rule."""
    def fn(r: dict) -> set:
        seen, hits = Counter(), Counter()
        for o in sample:
            if o["task"] == r["task"]:
                continue
            for h in o["points"]:
                c = cell(o, h)
                seen[c] += 1
                hits[c] += changed(o, h)
        return {h for h in r["points"] if seen[cell(r, h)] < min_seen or hits[cell(r, h)] > 0}
    return fn


FR, FRA = se.FAMILY_RULE, se.FAMILY_RULE_AMENDED
NO_API_REBUILD = {**FRA, "rebuilds": {"edit", "script"}}  # fitted: 0 of 38 API writes changed a list for this kind
RULES = [
    ("Every turn", lambda r: set(r["points"])),
    ("Skip turns that only read", se.not_read_only),
    ("Also skip Go tools and /tmp writes", se.writes_only),
    ("By scorer kind (today's amended rule)", _rule(FRA)),
    ("  + a restart counts for a running-service scorer only after a build", _rule(FRA, restart_needs_build=True)),
    ("  + edits to tests and notes don't count", _rule(FRA, restart_needs_build=True, ignore_test_edits=True)),
    ("  + API writes don't count for a rebuilding scorer (fitted)", _rule(NO_API_REBUILD, restart_needs_build=True, ignore_test_edits=True)),
    ("Learned from the other tasks: cell seen, never changed", None),
    ("Learned from the other tasks: cell seen 5+ times, never changed", None),
    ("By scorer kind, then skip identical machines", se.family_rule_same_state),
]


def line(sample: list, name: str, fn) -> dict:
    total = kept = changes = missed = kept_changes = 0
    late = []
    miss_list = []
    for r in sample:
        k = fn(r)
        kept += len(k)
        total += len(r["points"])
        for i, h in enumerate(r["points"]):
            if changed(r, h):
                changes += 1
                if h in k:
                    kept_changes += 1
                else:
                    missed += 1
                    nxt = next((x for x in r["points"][i + 1:] if x in k), r["T"])
                    late.append(nxt - h)
                    miss_list.append({"arm": r["arm"], "task": r["task"], "H": h, "turns_late": nxt - h, "main_class": se.main_class(r["classes"].get(h, {"edit"}))})
    ev = se.evaluate(sample, fn)
    return {"rule": name, "points": total, "kept": kept, "skipped_share": 1 - kept / total, "list_changes": changes, "missed": missed,
            "kept_points_that_change": kept_changes / kept if kept else 0, "turns_late_max": max(late, default=0),
            "runs_wrong": ev["curve"]["runs_wrong"], "points_wrong": ev["curve"]["points_wrong"], "curve_mean": ev["curve"]["mean_abs"],
            "curve_max": ev["curve"]["max_abs"], "summed_power_max": ev["power_per_task_and_arm"]["sum"]["max_abs"] if "sum" in ev["power_per_task_and_arm"] else None,
            "misses": miss_list}


def table(rows: list) -> None:
    print(f"{'rule':<70} {'kept':>5} {'skip':>6} {'missed':>9} {'hit rate':>8} {'late':>4} {'runs':>4} {'mean':>7} {'max':>6}")
    for x in rows:
        print(f"{x['rule']:<70} {x['kept']:>5} {x['skipped_share']:>6.1%} {x['missed']:>3} of {x['list_changes']:<3} "
              f"{x['kept_points_that_change']:>8.1%} {x['turns_late_max']:>4} {x['runs_wrong']:>4} {x['curve_mean']:>7.4f} {x['curve_max']:>6.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json")
    a = ap.parse_args()
    sample, _ = se.load_runs(se.arms_from_config())
    for r in sample:
        r["features"] = features(r)
    clean = se.without_doubts(sample)
    for r in clean:
        r.setdefault("features", features(r))
    out = {}
    for title, s in (("All data", sample), ("Without the noisy check and the A2 tamper run", clean)):
        rows = []
        for name, fn in RULES:
            if fn is None:
                fn = leave_one_task_out(s, 5 if "5+" in name else 1)
            rows.append(line(s, name, fn))
        print(f"\n{title}: {len(s)} runs")
        table(rows)
        out[title] = rows
        print("  missed by the last rule before the learned ones:", [(m["arm"], m["task"][:22], m["H"], m["turns_late"]) for m in rows[6]["misses"]][:20])
        print("  missed by the learned rule:", [(m["arm"], m["task"][:22], m["H"], m["turns_late"], m["main_class"]) for m in rows[7]["misses"]][:20])
    # What a stateful restart actually predicts, on running-service scorers
    s = [r for r in clean if r["family"] == "running service"]
    tab = defaultdict(lambda: [0, 0])
    for r in s:
        for h in r["points"]:
            f = r["features"].get(h)
            if f and "restart" in f["classes"]:
                k = ("restart after a build" if f["new_binary"] else "restart with no build since the last")
                tab[k][0] += 1
                tab[k][1] += changed(r, h)
    print("\nRunning-service scorers:", dict(tab))
    tab2 = Counter()
    for r in sample:
        for h in r["points"]:
            f = r["features"].get(h) or {}
            if f.get("build_failed"):
                tab2["build failed, points"] += 1
                tab2["build failed, list changes"] += changed(r, h)
            if f.get("edit_non_source"):
                tab2["only test or note edits, points"] += 1
                tab2["only test or note edits, list changes"] += changed(r, h)
    print("Signals seen:", dict(tab2))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
