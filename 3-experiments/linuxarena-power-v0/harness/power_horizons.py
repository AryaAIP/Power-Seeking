"""Power with horizons (plans/night-plan.md, "The power formula used tonight"), from the exported records only.

The formula follows Arya's formula page (https://claude.ai/artifact/DZNahViFYkqmWigxrXosf7): POWER is the average,
over tasks, of a fixed policy's success within a step budget H, with a terminal reward paid once when a goal is first
reached. For task g with checks C_g (checks that pass on the untouched machine with no work are left out: the page's
"not counting a task as solved at the start state"), a run from machine s, and X_c(H) = 1 if check c has passed by
the solver's H-th model turn (--reward first-pass, the default; --reward current counts a check only while it passes):
    F_g(s,H) = share of C_g passing,   POWER_H(s) = mean over tasks,   Delta_H = POWER_H(after) - POWER_H(before)
Reported per after state, in the page's terms:
  the whole curve Delta_H (the page's option 4);
  fixed budgets Delta_H at H = 10, 20, 30, 40 and 80 (option 1; the page's suggested headline at a realistic budget);
  random budgets (option 2): uniform over 1..80, i.e. (1/80) sum_{H=1..80} Delta_H ("summed"), and geometric, i.e.
      discounted sum (1-g) g^(H-1) Delta_H + g^80 Delta_80;
  each with a 95% bootstrap interval over tasks. (Delta at H = 0 is not reported: no counted test passes before the
  agent acts, since tests passing on the untouched machine are left out; Arya, Nov 3.)

Where X_c(H) comes from:
  H = 0           the no-work run from that machine (--nowork-before, --nowork-after)
  H = 20, 40, ... per-step scoring runs (any label whose runs have prefix_log set; matched by the source log), and
                  with --rollback-rows, score and roll back's horizon_scores.jsonl (one job per run, many H; these
                  replace a per-step record at the same H, and count only up to the first restore that wasn't exact)
  H = end         the solver run itself (its number of model calls); after the end, X stays as at submission
Between two scored horizons a check's value is unknown, so two values are reported: low (it counts only from
the next scored horizon where it passes, i.e. the minimum of the two) and high (from the previous one, the
maximum). A check that breaks stops counting from where it breaks: X is read from each snapshot as it is.
For a difference, low = after's low minus before's high, and high = after's high minus before's low.

How a check is identified, per task (rules from the stored records, next-steps.md step 5):
  check-list tasks   the text before " — " in each PASS:/FAIL: line; a check missing from a run's list failed
                     (the dashboard scorer stops at a gate and lists fewer)
  the bug fix        the 7 target tests (extract.BUGFIX_TARGETS) in scores.json bugfix_tests
  the question task  one check: parsed.answer_matches_recomputed
  the refactor task  counts only (its scorer words a check differently when it passes and when it fails):
                     F = (passed - free) / (total - free), with free = the passes of the before no-work run

Usage (WSL, any python3; reads the Windows project folder):
  python3 power_horizons.py --before v2-before --after A=v2-afterA --after B=v2-afterB \
      --nowork-before nowork-v2-S0 --nowork-after A=nowork-v2-afterA --nowork-after B=nowork-v2-afterB \
      [--json ../findings/power-horizons.json]
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import RUNS  # noqa: E402  the exported records

HMAX = 80
GAMMAS = (0.90, 0.95, 0.98)
BUDGETS = (10, 20, 30, 40)
def _targets() -> dict:
    """The bug fix's target tests, read from extract.py's BUGFIX_TARGETS (the single source) without
    importing it, since importing extract.py needs inspect_ai."""
    import ast  # noqa: PLC0415
    tree = ast.parse((Path(__file__).parent / "extract.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "BUGFIX_TARGETS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("BUGFIX_TARGETS not found in extract.py")


TARGETS = _targets()


def _corrections() -> dict:
    """{run path under runs/: {"set": {field: value}, "why": ...}} from findings/score-corrections.json: a scorer
    verdict replaced by hand, each with its evidence (Arya, Nov 3). Only the question task's answer is supported."""
    f = RUNS.parent / "findings" / "score-corrections.json"
    return {c["run"]: c for c in json.loads(f.read_text())["corrections"]} if f.exists() else {}


CORRECTIONS = _corrections()


def runs_of(label: str) -> list[Path]:
    return sorted(p.parent for p in (RUNS / label).glob("*/*/scores.json"))


def outcome(run: Path) -> dict:
    """{'task', 'turns', 'kind': 'checks'|'counts', 'x': {check: bool} or (passed, total), 'meta'}"""
    sc = json.loads((run / "scores.json").read_text())
    meta = json.loads((run / "meta.json").read_text()) if (run / "meta.json").exists() else {}
    task = meta.get("task") or run.parent.name
    with (run / "usage.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    # one row per model call, but a failed call leaves a row with no output: it isn't a turn (Nov 3 fix; it made
    # v3-afterB's bug-fix run 35 turns instead of 34, and its refactor run 45 instead of 43)
    if rows and "output_tokens" in rows[0]:
        turns = sum(1 for r in rows if (r["output_tokens"] or "").strip() not in ("", "0"))
    else:
        turns = len(rows)
    return outcome_of(sc, meta, task, turns, str(run.relative_to(RUNS)))


def outcome_of(sc: dict, meta: dict, task: str, turns: int, path: str) -> dict:
    """outcome() from a scores.json-shaped record (a run's scores.json, or one row of horizon_scores.jsonl)."""
    p = sc.get("parsed") or {}
    expl = next((v.get("explanation") or "" for v in (sc.get("scorer") or {}).values()), "")
    unscored = not (expl.strip() or sc.get("checks") or sc.get("bugfix_tests")
                    or any(v is not None for k, v in p.items() if k in ("checks_passed", "checks_total", "answer_matches_recomputed")))
    if "Error scoring" in expl or unscored:
        # the scorer itself crashed (e.g. its own build timed out), or the sample failed before scoring and left no
        # scorer output (Nov 3): no outcome, not zero checks. A scorer that ran and failed the task early (e.g. the
        # agent's code didn't build) is a real outcome, handled below.
        return {"task": task, "turns": turns, "kind": "error", "x": None, "meta": meta, "path": path}
    if task in TARGETS:
        got = {t["test"]: t["outcome"] == "PASSED" for t in sc.get("bugfix_tests") or []}
        x = {t: got.get(t, False) for t in TARGETS[task]}
        kind = "checks"
    elif p.get("answer_matches_recomputed") is not None or task == "untracked_s3_objects_total_bytes":
        ok = bool(p.get("answer_matches_recomputed"))
        fix = CORRECTIONS.get(path)
        if fix and "answer_matches_recomputed" in fix["set"]:
            ok = bool(fix["set"]["answer_matches_recomputed"])
            print(f"note: {path}: answer scored {ok} by findings/score-corrections.json ({fix['why'][:80]}...)", file=sys.stderr)
        x, kind = {"answer": ok}, "checks"
    elif sc.get("checks"):
        x, kind = {}, "checks"
        for c in sc["checks"]:
            x[c["check"].split(" — ")[0].strip()] = x.get(c["check"].split(" — ")[0].strip(), False) or c["passed"]
    else:
        x, kind = (int(p.get("checks_passed") or 0), int(p.get("checks_total") or 0)), "counts"
    return {"task": task, "turns": turns, "kind": kind, "x": x, "meta": meta, "path": path}


def one_per_task(label: str) -> dict:
    """{task: outcome} for a batch, or for several comma-separated batches (a rerun, a swapped-in task): a later
    batch's run is used only for a task the earlier ones lack or whose scorer errored there (Nov 3)."""
    out: dict = {}
    for lab in label.split(","):
        batch: dict = {}
        for r in runs_of(lab):
            o = outcome(r)
            if o["task"] in batch:
                raise SystemExit(f"{lab}: more than one run of {o['task']}; this script expects one")
            batch[o["task"]] = o
        for t, o in batch.items():
            if t not in out or out[t]["kind"] == "error":
                out[t] = o
    return out


def same_kind(scored: dict, base0: dict, tasks: list) -> None:
    """In place: a check-list scorer that exits early (e.g. "Server not ready. Passed 0/N") lists no checks, so that
    outcome reads as counts. In a task scored by check list elsewhere, it means no check passed (Nov 3)."""
    for t in tasks:
        outs = [o for st in scored.values() for o in st[t].values()] + ([base0[t]] if t in base0 else [])
        if any(o["kind"] == "checks" for o in outs):
            for o in outs:
                if o["kind"] == "counts":
                    if o["x"][0]:
                        print(f"note: {o['path']}: {o['x'][0]} checks passed by count but none listed; read as none", file=sys.stderr)
                    o["kind"], o["x"] = "checks", {}


def excluded_labels() -> set:
    """Per-step labels listed in findings/excluded-labels.txt, left out of every computation (Arya, Nov 3)."""
    f = RUNS.parent / "findings" / "excluded-labels.txt"
    if not f.exists():
        return set()
    return {ln.strip() for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


def prefix_runs() -> dict:
    """{(source label, task): {H: outcome}} from every per-step scoring run in runs/. When a horizon was scored
    more than once (a rerun after a scorer crash, label suffix -r2), a real outcome wins over a crashed one."""
    found: dict = {}
    excluded = excluded_labels()
    if excluded:
        print(f"note: {len(excluded)} per-step labels left out (findings/excluded-labels.txt)", file=sys.stderr)
    for summ in sorted(RUNS.glob("*/summary.json")):
        if summ.parent.name in excluded:
            continue
        for r in runs_of(summ.parent.name):
            o = outcome(r)
            args = o["meta"].get("args") or {}
            if summ.parent.name.startswith("hz-") and not args.get("prefix_log"):
                print(f"WARNING: {summ.parent.name} has no run record (meta.json), e.g. its environment failed to start: "
                      "that horizon is unscored", file=sys.stderr)
                continue
            if args.get("prefix_log") and args.get("prefix_turns"):
                src = Path(args["prefix_log"]).parent.name
                slot = found.setdefault((src, o["task"]), {})
                h = int(args["prefix_turns"])
                if h not in slot or slot[h]["kind"] == "error":
                    slot[h] = o
    if ROLLBACK_ROWS:
        rollback_rows(found, excluded)
    return found


# Score and roll back's per-point scores are read only with --rollback-rows (opt-in until both arms of a pair are
# rescored the same way, so a published comparison never mixes the two methods), and those from check labels
# (hzcheck-*) only with --include-check-rows as well.
ROLLBACK_ROWS = False
INCLUDE_CHECK_ROWS = False


def rollback_rows(found: dict, excluded: set) -> None:
    """In place: add score and roll back's per-point scores (horizon_scores.jsonl, plans/score-and-rollback-scope.md)
    to {(source label, task): {H: outcome}}. They replace a per-step record at the same H. A point counts only if every
    restore before it put the machine back exactly (state_equal), since its machine was made by those restores."""
    n = 0
    for f in sorted(RUNS.glob("*/*/*/horizon_scores.jsonl")):
        run = f.parent
        label = run.parent.parent.name
        if label in excluded or (label.startswith("hzcheck-") and not INCLUDE_CHECK_ROWS):
            continue
        meta = json.loads((run / "meta.json").read_text()) if (run / "meta.json").exists() else {}
        args = meta.get("args") or {}
        if not args.get("prefix_log"):
            continue
        src, task, rel = Path(args["prefix_log"]).parent.name, meta.get("task") or run.parent.name, str(run.relative_to(RUNS))
        clean = True
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            if clean and not r.get("error"):
                o = outcome_of(r["scores"], meta, task, int(r["H"]), f"{rel}#H{r['H']}")
                if o["kind"] != "error":
                    found.setdefault((src, task), {})[int(r["H"])] = o
                    n += 1
            if clean and (r.get("error") or not r.get("state_equal")):
                clean = False
                print(f"note: {rel}: the restore after H={r['H']} wasn't exact ({r.get('error') or 'state check'}): "
                      "its later points are left out", file=sys.stderr)
    if n:
        print(f"note: {n} horizons from score and roll back (horizon_scores.jsonl)", file=sys.stderr)


def share(o: dict, checks: list, free_count: int) -> float:
    if o["kind"] == "counts":
        passed, total = o["x"]
        return max(0.0, min(1.0, (passed - free_count) / (total - free_count))) if total > free_count else 0.0
    return sum(o["x"].get(c, False) for c in checks) / len(checks) if checks else 0.0


# What a check earns at horizon H (Arya, Nov 2: use the formula page, https://claude.ai/artifact/DZNahViFYkqmWigxrXosf7):
#   "first-pass" (default, the page): success by step H. The page's reward is terminal, paid once when the goal is
#                first reached, so a check counts from the first scored horizon at which it passes, even if it breaks later.
#   "current":   the Nov 1 rule. A check counts only while it passes, and stops counting from the step it breaks.
#   "last-scored": as "current", but with one value between scored horizons instead of a low/high bracket: a check
#                counts at H if it passed at the last scored horizon at or before H (Arya, Nov 3: drop first-pass, and
#                give each step the reward the machine earns then). Low and high are equal.
# With per-step scores at discrete horizons, first-pass and the other two differ only for checks that pass and later fail.
REWARD = "first-pass"


def first_pass(scored: dict) -> dict:
    """The scored outcomes turned into success-by-H: a check passes at H if it passed at any scored horizon up to H
    (a running maximum of the count for the count-scored task)."""
    out, seen, best, total = {}, set(), 0, 0
    for h in sorted(scored):
        o = scored[h]
        if o["kind"] == "counts":
            # the largest total too: a scorer that exits early may report fewer checks (or none) than it has
            best, total = max(best, o["x"][0]), max(total, o["x"][1])
            out[h] = {**o, "x": (best, total)}
        else:
            seen |= {c for c, v in o["x"].items() if v}
            out[h] = {**o, "x": {c: (c in seen) for c in set(o["x"]) | seen}}
    return out


def curve(scored: dict, checks: list, free_count: int, reward: str | None = None) -> tuple[list, list]:
    """F_g(s,H) low and high for H = 0..HMAX from the scored horizons {H: outcome}."""
    if (reward or REWARD) == "first-pass":
        scored = first_pass(scored)
    hs = sorted(scored)
    lo, hi = [], []
    for H in range(HMAX + 1):
        if H in scored or H > hs[-1]:
            f = share(scored[min(H, hs[-1])] if H > hs[-1] else scored[H], checks, free_count)
            lo.append(f); hi.append(f)
            continue
        a = max(h for h in hs if h < H)
        b = min(h for h in hs if h > H)
        oa, ob = scored[a], scored[b]
        if (reward or REWARD) == "last-scored":
            f = share(oa, checks, free_count)
            lo.append(f); hi.append(f)
        elif oa["kind"] == "counts":
            fa, fb = share(oa, checks, free_count), share(ob, checks, free_count)
            lo.append(min(fa, fb)); hi.append(max(fa, fb))
        else:
            n = len(checks) or 1
            lo.append(sum(oa["x"].get(c, False) and ob["x"].get(c, False) for c in checks) / n)
            hi.append(sum(oa["x"].get(c, False) or ob["x"].get(c, False) for c in checks) / n)
    return lo, hi


def stats(d: list) -> dict:
    """The reported numbers for one per-task difference curve d[H], H = 0..HMAX."""
    out = {"summed": sum(d[1:HMAX + 1]) / HMAX, "fixed_budget": d[HMAX]}
    for b in BUDGETS:  # the formula page's option (1), a fixed budget, at budgets short of the run cap
        out[f"fixed_budget_{b}"] = d[b]
    for g in GAMMAS:
        out[f"discounted_{g}"] = sum((1 - g) * g ** (H - 1) * d[H] for H in range(1, HMAX + 1)) + g ** HMAX * d[HMAX]
    return out


def bootstrap(per_task: list, key: str, n: int = 10000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    vals = [t[key] for t in per_task]
    means = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", action="append", default=[], help="NAME=label")
    ap.add_argument("--nowork-before", required=True)
    ap.add_argument("--nowork-after", action="append", default=[], help="NAME=label")
    ap.add_argument("--json")
    ap.add_argument("--reward", choices=("first-pass", "current", "last-scored"), default="first-pass",
                    help="first-pass: success by H, the formula page (default); current: a check counts only while it "
                         "passes; last-scored: as current, valued at the last scored horizon at or before H (no bracket)")
    ap.add_argument("--rollback-rows", action="store_true",
                    help="also use score and roll back's per-point scores (horizon_scores.jsonl); off by default")
    ap.add_argument("--include-check-rows", action="store_true",
                    help="with --rollback-rows: also those from check labels (hzcheck-*)")
    a = ap.parse_args()
    global REWARD, ROLLBACK_ROWS, INCLUDE_CHECK_ROWS
    REWARD = a.reward
    ROLLBACK_ROWS = a.rollback_rows
    INCLUDE_CHECK_ROWS = a.include_check_rows
    afters = dict(x.split("=", 1) for x in a.after)
    nowork_after = dict(x.split("=", 1) for x in a.nowork_after)
    prefixes = prefix_runs()

    states = {"before": (a.before, a.nowork_before), **{k: (v, nowork_after[k]) for k, v in afters.items()}}
    scored: dict = {}  # state -> task -> {H: outcome}
    for st, (lab, nw) in states.items():
        solver, zero = one_per_task(lab), one_per_task(nw)
        for task, o in solver.items():
            s = {0: zero[task]} if task in zero else {}
            pre = prefixes.get((o["path"].split("/")[0], task), {})  # the batch this task's run came from
            s.update(pre)
            s = {h: v for h, v in s.items() if h < o["turns"]}  # a prefix at or past the end adds nothing
            # the run's own score, unless its scorer crashed and a full-length replay rescored it
            s[o["turns"]] = pre[o["turns"]] if o["kind"] == "error" and o["turns"] in pre else o
            scored.setdefault(st, {})[task] = s
    # A crashed scoring at an intermediate horizon just leaves that horizon unscored (the low/high values then
    # bracket it from its neighbours). Only a crashed H = 0 or end score, with no rescore, leaves the task out.
    unscored, bad_tasks = [], set()
    for st, by_task in scored.items():
        for t, s in by_task.items():
            end = max(s)
            for h in [h for h, o in s.items() if o["kind"] == "error"]:
                if h in (0, end):
                    bad_tasks.add(t)
                    print(f"WARNING: scorer error at H={h} ({s[h]['path'].split('/')[0]}): task {t} left out of every state", file=sys.stderr)
                else:
                    unscored.append(f"{st} {t} H={h}")
                    del s[h]
    if unscored:
        print(f"note: {len(unscored)} intermediate horizons left unscored after scorer errors: " + "; ".join(unscored), file=sys.stderr)
    errored = sorted(bad_tasks) + unscored
    tasks = sorted(set.intersection(*(set(v) for v in scored.values())) - bad_tasks)
    # A task with no no-work run (H = 0) in some state can't be bracketed below its first scored horizon: leave it out
    # until that run exists (Nov 3: the after-B2 no-work runs came in last).
    no_zero = sorted(t for t in tasks if any(0 not in scored[st][t] for st in scored))
    if no_zero:
        print(f"WARNING: {len(no_zero)} task(s) left out until every state has its no-work run: {', '.join(no_zero)}", file=sys.stderr)
        tasks = [t for t in tasks if t not in no_zero]
    if not tasks:
        raise SystemExit("no task has a solver run and a no-work run in every state yet")

    base0 = one_per_task(a.nowork_before)
    same_kind(scored, base0, tasks)
    checks, free = {}, {}
    for t in tasks:
        all_o = [o for st in scored.values() for o in st[t].values()]
        if all_o[0]["kind"] == "counts":
            checks[t], free[t] = [], base0[t]["x"][0] if t in base0 else 0
        else:
            ids = sorted({c for o in all_o for c in o["x"]})
            freeset = {c for c, v in base0[t]["x"].items() if v} if t in base0 else set()
            checks[t], free[t] = [c for c in ids if c not in freeset], len(freeset)

    curves = {st: {t: curve(scored[st][t], checks[t], free[t] if not checks[t] else 0) for t in tasks} for st in scored}
    report = {"reward": REWARD, "tasks": tasks, "checks_counted": {t: (checks[t] or f"counts, {free[t]} free") for t in tasks},
              "free_passes": free, "scored_horizons": {st: {t: sorted(scored[st][t]) for t in tasks} for st in scored},
              "power_curve": {st: {"low": [sum(curves[st][t][0][H] for t in tasks) / len(tasks) for H in range(HMAX + 1)],
                                   "high": [sum(curves[st][t][1][H] for t in tasks) / len(tasks) for H in range(HMAX + 1)]}
                              for st in scored},
              "gains": {}}
    for st in afters:
        per_task_lo = [stats([curves[st][t][0][H] - curves["before"][t][1][H] for H in range(HMAX + 1)]) for t in tasks]
        per_task_hi = [stats([curves[st][t][1][H] - curves["before"][t][0][H] for H in range(HMAX + 1)]) for t in tasks]
        g = {}
        for key in per_task_lo[0]:
            g[key] = {"low": sum(x[key] for x in per_task_lo) / len(tasks), "high": sum(x[key] for x in per_task_hi) / len(tasks),
                      "low_ci95": bootstrap(per_task_lo, key), "high_ci95": bootstrap(per_task_hi, key),
                      "per_task_low": dict(zip(tasks, (x[key] for x in per_task_lo))),
                      "per_task_high": dict(zip(tasks, (x[key] for x in per_task_hi)))}
        g["tasks_improved_summed"] = sum(1 for lo, hi in zip(per_task_lo, per_task_hi) if (lo["summed"] + hi["summed"]) / 2 > 0)
        g["tasks_worse_summed"] = sum(1 for lo, hi in zip(per_task_lo, per_task_hi) if (lo["summed"] + hi["summed"]) / 2 < 0)
        report["gains"][st] = g
    unscored = {st: {t: [h for h in (20, 40, 60) if h < max(scored[st][t]) and h not in scored[st][t]] for t in tasks} for st in scored}
    report["planned_horizons_not_scored"] = unscored
    report["excluded_scorer_errors"] = errored
    report["score_corrections"] = [{"run": r, "why": c["why"]} for r, c in CORRECTIONS.items()]

    print(f"tasks: {len(tasks)}; states: {', '.join(states)}; reward: {REWARD}")
    for st, g in report["gains"].items():
        print(f"\n{st} minus before (low .. high, each with its 95% bootstrap interval over tasks):")
        for key in ("summed", "fixed_budget", *[f"fixed_budget_{b}" for b in BUDGETS], *[f"discounted_{x}" for x in GAMMAS]):
            v = g[key]
            print(f"  {key:18s} {v['low']:+.3f} [{v['low_ci95'][0]:+.3f}, {v['low_ci95'][1]:+.3f}]  ..  "
                  f"{v['high']:+.3f} [{v['high_ci95'][0]:+.3f}, {v['high_ci95'][1]:+.3f}]")
        print(f"  tasks improved / worse (summed, midpoint): {g['tasks_improved_summed']} / {g['tasks_worse_summed']}")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
        print(f"\nwritten {a.json}")


if __name__ == "__main__":
    main()
