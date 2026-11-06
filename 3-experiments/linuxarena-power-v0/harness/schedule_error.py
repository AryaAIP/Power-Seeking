#!/usr/bin/env python3
"""How wrong would cheaper scoring schedules have been? Offline, from the every-turn scores we already have.

Score and roll back scores a stored run at every turn. For each schedule below, this script takes that every-turn
truth, keeps only the points the schedule would have scored, fills the curve with the project's reward rule
(`last-scored`: a test case counts at step H if it passes at the last scored step at or before H, values from
power_horizons.py, the single source of the formula) and compares the result with the truth. It also counts how much
reusing a score between equal machine states could save, and where the check list changes.

Reads only exported records (runs/, findings/excluded-labels.txt, findings/score-corrections.json) and the arms in
viz/run-v4-both.json. Writes nothing except the --json file. No environment, no model call, no queue. Prints and stores
check names, counts and class names only: never a scorer's explanation or a command's text (those can hold credentials).

  python3 -I harness/schedule_error.py [--json out.json]

What counts as a point: H = 1 .. T-1 of a run with T model turns. H = 0 (the no-work run) and H = T (the solver run's own
score) already exist and cost nothing, so every schedule has them. A run is in the sample if it has score and roll back
rows; a run whose valid rows stop early (sr-v4-afterA-p3-hotreload, valid to H = 23) is treated as a shorter run in the
per-run tables and left out of everything that uses POWER_H. Rows are read as power_horizons.rollback_rows reads them:
a later -rN label replaces an earlier one at the same H, a row counts only up to the first inexact restore, and hzcheck-*
labels are left out. Old per-step records (hz-*) fill a point the rows don't have, as in power_horizons.py.

Results are reported twice: for all the data, and without the two known doubts (the noisy `combined_filter_works` on the
access log task, removed as a check; and the A2 tamper run, left out because its H = 16-20 is under question).
"""

import argparse
import contextlib
import csv
import io
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True  # this script leaves nothing behind in harness/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_sr as cs  # noqa: E402  check_list: how the project reads a check list
import power_horizons as ph  # noqa: E402  the single source of the formula

REPO_VIZ = Path(__file__).resolve().parent.parent / "viz"
EPS = 1e-9

# Cost, from research_notes/Faster score and roll back/measured_time_budget.md (39 jobs, pause time removed): 39,492 s over
# 944 rows is the 42 environment-seconds per point "including everything". Of that, scorer + save + undo is
# (14,354 + 4,498 + 8,562) s over 903 scored points, which is what skipping a point saves: the turn's replay and the
# job's start and end still happen.
COST_ALL_IN = 42.0
COST_SKIPPED_POINT = (14354 + 4498 + 8562) / 903
REMAINING_POINTS = 2708  # the same file: pending lines' points that need scoring

# Scorer families, plans/residue-free-scoring-scope.md §2. Tests the running service, restarts it only if it is down:
RUNNING_SERVICE = {"model_favoriting_system", "admin_user_management", "model_access_audit_trail", "audit_log_tamper_detection",
                   "model_version_comment_thread", "custom_validation_rules_engine", "request_id_propagation",
                   "token_usage_analytics", "scheduled_model_expiration", "filebased_configuration_hotreload",
                   "webhook_notification_system", "jwt_claims_wrong_field"}
ALWAYS_RESTART = {"model_registry_rbac_matrix", "postgresqlbacked_job_queue"}  # restarts from the binary file on disk


def family_of(task: str) -> str:
    return "running service" if task in RUNNING_SERVICE else "always restarts" if task in ALWAYS_RESTART else "rebuilds"


NOISY_TASK, NOISY_CHECK = "model_access_audit_trail", "combined_filter_works"
QUESTIONED_RUN = ("A2", "audit_log_tamper_detection")  # H = 16-20 under question (log 18:42, 19:50)
# Points whose scorer ran across a machine pause (measured_time_budget.md, and the 19:52 log entry). Not left out: flagged.
PAUSED_POINTS = {("A1", "filebased_configuration_hotreload", 17), ("B1", "filebased_configuration_hotreload", 17),
                 ("before", "filebased_configuration_hotreload", 18), ("A1", "webhook_notification_system", 31),
                 ("B1", "postgresqlbacked_job_queue", 20), ("B1", "sqlite_audit_log_archive", 18),
                 ("A1", "admin_user_management", 18), ("B1", "admin_user_management", 15),
                 ("before", "admin_user_management", 43), ("B1", "audit_log_tamper_detection", 4),
                 ("before", "audit_log_tamper_detection", 16), ("A2", "abstract_middleware_chain", 1)}
COMPARISONS = (("A1", "before"), ("B1", "before"), ("B1", "A1"), ("A2", "before"), ("B2", "before"), ("B2", "A2"))
PAUSE_SECONDS = 600  # a point's row time at or above this crossed a machine pause: left out of measured time
# Jobs known to be wrong, left out when counting repeats of a point: the planted bug wiped; A2's restore before its fix.
INVALID_LABELS = {"sr-v4-afterB-p2-jwt", "sr-v4-afterA2-p1-adminusers", "sr-v4-afterA2-p5-middleware-r2"}


def quiet(fn, *a):
    """power_horizons' notes go to stderr and can quote an error's text: keep them out of the output."""
    with contextlib.redirect_stderr(io.StringIO()):
        return fn(*a)


# ---------------------------------------------------------------------------------------------- transcripts to turns
FENCE = "````"
STEP = re.compile(r"^### Step (\d+): (?:`(\w+)`|(no tool call))\s*$")
USER = re.compile(r"^### Message from the user")


def parse_steps(text: str, with_output: bool = False) -> list[dict]:
    """The steps of a transcript.md, in order: {'fn', 'reasoning'?, 'text'?, 'args'?}. A step is one tool call, or a turn
    with no call. Fence-aware, since a command's text or output can look like a heading."""
    lines = text.split("\n")
    i, in_fence = 0, False
    while i < len(lines):
        ln = lines[i]
        if in_fence:
            in_fence = ln.rstrip() != FENCE
        elif ln.startswith(FENCE):
            in_fence = True
        elif ln.strip() == "## Steps":
            break
        i += 1
    steps, cur, section = [], None, None
    i += 1
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(FENCE):
            j = i + 1
            while j < len(lines) and lines[j].rstrip() != FENCE:
                j += 1
            if cur is not None and section:
                cur[section] = cur.get(section, "") + "\n".join(lines[i + 1:j])
            i = j + 1
            continue
        m = STEP.match(ln)
        if m:
            cur, section = {"fn": m.group(2) or "none"}, None
            steps.append(cur)
        elif USER.match(ln):
            cur, section = None, None
        elif ln.startswith("**Reasoning**"):
            section = "reasoning"
        elif ln.startswith("**Text**"):
            section = "text"
        elif ln.startswith("**Tool call**"):
            section = "args"
        elif ln.startswith("**Output**"):
            section = "output" if with_output else None  # not read unless asked for
        i += 1
    return steps


def split_turns(steps: list[dict], has_reasoning: list[bool]) -> tuple[list[list[dict]], int]:
    """Group steps into model turns. The transcript numbers tool calls, not turns, and marks only a turn's first call
    with its reasoning or text, so a turn with neither looks like a further call of the turn before. usage.csv says
    how many turns there are and which had reasoning: steps with reasoning line up with those turns, and between two of
    them the count of turns without reasoning says how many further starts there are. Returns the turns and how many
    stretches stayed ambiguous (there the later candidates are taken as the starts)."""
    t_total = len(has_reasoning)
    if len(steps) == t_total:
        return [[s] for s in steps], 0
    starts = [("reasoning" in s or "text" in s or s["fn"] == "none") for s in steps]
    if steps:
        starts[0] = True
    uncertain = 0
    r_steps = [i for i, s in enumerate(steps) if "reasoning" in s]
    r_turns = [t for t, f in enumerate(has_reasoning) if f]
    if sum(starts) < t_total and len(r_steps) == len(r_turns):
        edges = [(-1, -1)] + list(zip(r_steps, r_turns)) + [(len(steps), t_total)]
        for (s0, t0), (s1, t1) in zip(edges, edges[1:]):
            seg = list(range(s0 + 1, s1))
            needed = (t1 - t0 - 1) - sum(starts[i] for i in seg)
            cand = [i for i in seg if not starts[i]]
            if needed <= 0 or not cand:
                continue
            if needed < len(cand):
                uncertain += 1
            for i in cand[-needed:]:
                starts[i] = True
    missing = t_total - sum(starts)
    if missing > 0:  # no reasoning to line up with: take the last candidates, and say so
        uncertain += 1
        for i in [i for i in range(len(steps)) if not starts[i]][-missing:]:
            starts[i] = True
    turns: list[list[dict]] = []
    for s, st in zip(steps, starts):
        if st or not turns:
            turns.append([s])
        else:
            turns[-1].append(s)
    return turns, uncertain


# ------------------------------------------------------------------------------------------ what a turn's commands do
CLASS_ORDER = ("restart", "build", "edit", "script", "api", "gotool", "tmp", "read", "none")
READ_ONLY = {"read", "none"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?(?:\n\s*\2\s*(?:\n|$)|\Z)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
RESTART = re.compile(r"\brestart\.sh\b|\bpkill\b|\bkillall\b|\bkill\s+-?\w|\bnohup\b|\bsystemctl\s+(re)?start|(^|[;&|]\s*)\./model-registry\b|/model-registry\s*&(?!&)")
BUILD = re.compile(r"\bgo\s+(build|install|run)\b|\brebuild\.sh\b|\bmake\b")
GOTOOL = re.compile(r"\bgo\s+(vet|test|list|doc|version|env|fmt|mod\s+(?:verify|why|graph|download))\b|\bgofmt\s+-[ld]")
EDITS_SOURCE = re.compile(r"\bgo\s+(?:mod\s+(?:tidy|edit|init)|get|generate)\b|\bgofmt\s+-w\b|\bgoimports\s+-w\b")
CURL_WRITE = re.compile(r"curl\b.*(\s-X\s*(POST|PUT|DELETE|PATCH)|--request\s+(POST|PUT|DELETE|PATCH)|\s--data|\s-d\s|\s-F\s|--form|\s-T\s)", re.I)
API_WRITE = re.compile(r"\brequests\.(post|put|delete|patch)|method=['\"](POST|PUT|DELETE|PATCH)|\bmc\s+(cp|rm|mv|mirror|mb|rb)\b|\baws\s+s3\s+(cp|rm|mv|sync|mb|rb)\b", re.I)
PYTHON = re.compile(r"\bpython3?\b")
PY_WRITES = re.compile(r"open\([^)]*['\"][wax+]|\.write\(|write_text|requests\.|urllib|http\.client|subprocess|os\.system|os\.(remove|rename|mkdir|makedirs|unlink)|shutil|psycopg|sqlite3|connect\(|socket")
SQL_CLIENT = re.compile(r"\bpsql\b|\bsqlite3\b|\bpg_restore\b")
SQL_WRITE = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|CREATE\s+(TABLE|INDEX|UNIQUE|EXTENSION|TYPE|ROLE|USER)|ALTER\s+|DROP\s+|TRUNCATE\s+|GRANT\s+|REVOKE\s+)", re.I)
MUTATES = re.compile(r"\bsed\s+(-[a-zA-Z]*i|--in-place)|\bperl\s+-[a-z]*i|\btee\b|\bmv\s|\bcp\s|\brm\s|\bmkdir\s|\btouch\s|\bchmod\s|\bchown\s|\bchgrp\s|\bln\s|\btruncate\s|"
                     r"\bpatch\s|\bgit\s+(add|commit|apply|checkout|stash|reset|merge|rebase|restore|init)\b|\btar\s+-?\w*x|\bunzip\s|\bdd\s|\binstall\s+-|\bapt(-get)?\s+install|\bpip3?\s+install|\buseradd\b|\busermod\b|\bcrontab\b")
SCRIPT = re.compile(r"\bbash\s+\S|\bsh\s+\S|\bnode\s|\bperl\s|\bruby\s|(^|[;&|]\s*)(sudo\s+(-\S+\s+)*)?\.?/[\w./-]+\.(sh|py)\b|(^|[;&|]\s*)\./[\w./-]+|\bpython3?\s+[\w./-]+\.py\b", re.M)
REDIRECT = re.compile(r"(?<![0-9&>])>{1,2}\s*(?!&)(?!/dev/)([^\s;&|)]+)|\b[01]>{1,2}\s*(?!&)(?!/dev/)([^\s;&|)]+)")
PATHS = re.compile(r"(?<![\w.$])(/[\w\-./]+)")


def classify_command(cmd: str) -> set:
    """The classes of one shell command, from its text alone. A rough rule by design: `read` means nothing here looks like
    it writes. Its errors are what the analysis measures."""
    out = set()
    bare = QUOTED.sub("''", HEREDOC.sub(" <<HEREDOC\n", cmd))
    if RESTART.search(bare):
        out.add("restart")
    if BUILD.search(bare):
        out.add("build")
    if GOTOOL.search(bare):
        out.add("gotool")
    if EDITS_SOURCE.search(bare):
        out.add("edit")
    # a request that writes; logging in writes nothing (same-state rows confirm it), so a login alone doesn't count
    curl_writes = any(CURL_WRITE.search(seg) and "auth/login" not in seg for seg in re.split(r"\n|&&|;|\|", cmd))
    if curl_writes or API_WRITE.search(cmd) or (SQL_CLIENT.search(bare) and SQL_WRITE.search(cmd)):
        out.add("api")
    # a script: named files and other languages always count; inline Python only if its text looks like it writes
    if SCRIPT.search(re.sub(r"\S*\b(restart|rebuild)\.sh\b", "", bare)) or (PYTHON.search(bare) and PY_WRITES.search(cmd)):
        out.add("script")
    for segment in re.split(r"[;&|\n]+", bare):  # what each part writes: only under /tmp, or anywhere else?
        targets = [a or b for a, b in REDIRECT.findall(segment)]
        named = targets + (PATHS.findall(segment) if MUTATES.search(segment) else [])
        if targets or MUTATES.search(segment):
            out.add("tmp" if named and all(p.startswith(("/tmp", "/dev")) for p in named) else "edit")
    return out or {"read"}


def classify_turn(calls: list[dict]) -> set:
    """The classes of one turn: the union over its tool calls. No call, or only `submit`, is `none`."""
    out = set()
    for s in calls:
        fn = s["fn"]
        if fn in ("none", "submit"):
            continue
        try:
            a = json.loads(s.get("args") or "{}")
        except json.JSONDecodeError:
            a = {}
        a = a if isinstance(a, dict) else {}
        if fn == "bash":
            c = a.get("cmd") if "cmd" in a else a.get("command")
            out |= classify_command(c if isinstance(c, str) else "")
        elif fn == "text_editor" or "path" in a or "file_path" in a:
            p = str(a.get("path") or a.get("file_path") or "")
            if a.get("command") == "view":
                out.add("read")
            else:
                out.add("tmp" if p.startswith("/tmp") else "edit")
        else:
            out.add("edit")  # an unknown tool: don't assume it only reads
    return out or {"none"}


def main_class(classes: set) -> str:
    return next(c for c in CLASS_ORDER if c in classes)


def turn_classes(run_dir: Path) -> tuple[dict, int]:
    """{H: classes of turn H} for a solver run's exported record, and how many stretches stayed ambiguous."""
    with (run_dir / "usage.csv").open() as fh:
        usage = list(csv.DictReader(fh))
    if usage and "output_tokens" in usage[0]:
        usage = [u for u in usage if (u["output_tokens"] or "").strip() not in ("", "0")]
    has_reasoning = [int(u.get("reasoning_chars") or 0) > 0 for u in usage]
    turns, uncertain = split_turns(parse_steps((run_dir / "transcript.md").read_text(errors="replace")), has_reasoning)
    return {i + 1: classify_turn(t) for i, t in enumerate(turns)}, uncertain


# -------------------------------------------------------------------------------------------------- reading the records
def arms_from_config(path: Path | None = None) -> dict:
    """{arm: (solver labels, no-work labels)}, from the config of the page that shows both pairs."""
    cfg = json.loads((path or REPO_VIZ / "run-v4-both.json").read_text())
    return {"before": tuple(cfg["before"]), **{a: tuple(v) for a, v in cfg["afters"].items()}}


def passing_set(sc: dict) -> frozenset:
    """A point's whole check list, as the set of passing checks (a check missing from the list failed; order doesn't
    matter). A scorer with only a count gives the count."""
    out = set()
    for name, v in cs.check_list(sc)["checks"]:
        if name == "passed/total":
            n = str(v).split("/")[0]
            if n not in ("0", "None", ""):
                out.add(f"count:{n}")
        elif v in (True, "PASSED"):
            out.add(name)
    return frozenset(out)


def read_row_flags(runs: Path, excluded: set) -> tuple[dict, dict]:
    """{(source label, task): {H: what the row in force says}} and each point's raw score. Mirrors
    power_horizons.rollback_rows, including its order and its clean rule; load_runs checks the two agree."""
    flags: dict = {}
    raw: dict = {}
    for f in sorted(runs.glob("*/*/*/horizon_scores.jsonl"), key=lambda p: (len(p.parents[2].name), str(p))):
        run = f.parent
        label = run.parent.parent.name
        if label in excluded or label.startswith("hzcheck-"):
            continue
        meta = json.loads((run / "meta.json").read_text()) if (run / "meta.json").exists() else {}
        args = meta.get("args") or {}
        if not args.get("prefix_log"):
            continue
        src, task = Path(args["prefix_log"]).parent.name, meta.get("task") or run.parent.name
        clean = True
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            h = int(r["H"])
            if clean and not r.get("error"):
                unscored = quiet(ph.outcome_of, r.get("scores") or {}, meta, task, h, "x")["kind"] == "error"
                if r.get("reused_from") or not unscored:
                    sec = r.get("seconds") or {}
                    flags.setdefault((src, task), {})[h] = {
                        "label": label, "reused_from": bool(r.get("reused_from")),
                        "same_state_as": r.get("same_state_as"), "dedup_audit_of": r.get("dedup_audit_of"),
                        "dedup_differs": r.get("dedup_differs"), "job_dedup": bool(args.get("score_dedup")),
                        "seconds": sum(v or 0 for v in sec.values()) if sec else None,
                        "upper_entries": (r.get("save") or {}).get("upper_entries")}
                    if not unscored:
                        raw[(label, task, h)] = r["scores"]
            if clean and (r.get("error") or not r.get("state_equal")):
                clean = False
    return flags, raw


def load_runs(arms: dict, runs_root: Path | None = None) -> tuple[list[dict], dict]:
    """The sample: every (arm, task) with score and roll back rows, each as power_horizons.main() would see it."""
    if runs_root is not None:
        ph.RUNS = runs_root
    runs = ph.RUNS
    ph.ROLLBACK_ROWS, ph.INCLUDE_CHECK_ROWS = True, False
    excluded = quiet(ph.excluded_labels)
    flags, raw_rows = read_row_flags(runs, excluded)
    prefixes = quiet(ph.prefix_runs)
    scored: dict = {}
    for arm, (lab, nw) in arms.items():
        solver, zero = quiet(ph.one_per_task, lab), quiet(ph.one_per_task, nw)
        for task, o in solver.items():
            s = {0: zero[task]} if task in zero else {}
            pre = prefixes.get((o["path"].split("/")[0], task), {})
            s.update(pre)
            s = {h: v for h, v in s.items() if h < o["turns"]}
            s[o["turns"]] = pre[o["turns"]] if o["kind"] == "error" and o["turns"] in pre else o
            scored.setdefault(arm, {})[task] = s
    bad_tasks = set()
    for by_task in scored.values():
        for t, s in by_task.items():
            end = max(s)
            for h in [h for h, o in s.items() if o["kind"] == "error"]:
                if h in (0, end):
                    bad_tasks.add(t)
                else:
                    del s[h]
    tasks = sorted(set.intersection(*(set(v) for v in scored.values())) - bad_tasks)
    tasks = [t for t in tasks if all(0 in scored[a][t] for a in scored)]
    base0 = quiet(ph.one_per_task, arms["before"][1])
    if tasks:
        ph.same_kind(scored, base0, tasks)

    def checks_of(which: list) -> dict:
        """As power_horizons.main(): the counted checks and free passes of each task, over the arms given."""
        checks, free = {}, {}
        for t in tasks:
            all_o = [o for a in which for o in scored[a][t].values()]
            if all_o[0]["kind"] == "counts":
                checks[t], free[t] = [], base0[t]["x"][0] if t in base0 else 0
            else:
                ids = sorted({c for o in all_o for c in o["x"]})
                fs = {c for c, v in base0[t]["x"].items() if v} if t in base0 else set()
                checks[t], free[t] = [c for c in ids if c not in fs], len(fs)
        return checks, free

    checks, free = checks_of(list(scored))
    # The pages for one pair count the checks seen in that pair's arms. Say where that differs from all arms together.
    differ = {}
    for name, which in (("pair 1", ["before", "A1", "B1"]), ("pair 2", ["before", "A2", "B2"])):
        if all(a in scored for a in which):
            c2, _ = checks_of(which)
            differ[name] = sorted(t for t in tasks if c2[t] != checks[t])

    raw_cache: dict = {}

    def raw_score(o: dict) -> dict:
        path = o["path"]
        if "#H" in path:
            rel, h = path.split("#H")
            label, task = rel.split("/")[0], rel.split("/")[1]
            if (label, task, int(h)) in raw_rows:
                return raw_rows[(label, task, int(h))]
        if path not in raw_cache:
            raw_cache[path] = json.loads((runs / path.split("#H")[0] / "scores.json").read_text())
        return raw_cache[path]

    sample, status = [], []
    for arm in scored:
        for task in tasks:
            s = scored[arm][task]
            src_label = next((lab for lab in arms[arm][0].split(",") if (lab, task) in flags), None)
            if src_label is None:
                continue
            fl = flags[(src_label, task)]
            for h, f in fl.items():  # the mirror of rollback_rows must agree with it
                if not f["reused_from"] and h in s and f"{f['label']}/" not in s[h]["path"]:
                    raise SystemExit(f"row reader and power_horizons disagree at {arm} {task} H={h}")
            turns = max(s)
            cut = max(fl) < turns - 1
            t_eff = max(fl) if cut else turns
            s = {h: o for h, o in s.items() if h <= t_eff}
            run_dir = next((runs / src_label / task).glob("*/transcript.md"), None)
            classes, uncertain = turn_classes(run_dir.parent) if run_dir else ({}, 0)  # no transcript: every turn counts as writing
            b0 = passing_set(raw_score(base0[task])) if task in base0 else frozenset()
            r = {"arm": arm, "task": task, "src": src_label, "turns": turns, "T": t_eff, "full": not cut, "scored": s, "flags": fl,
                 "classes": classes, "uncertain_turns": uncertain, "checks": checks[task], "free": free[task], "family": family_of(task),
                 "items": {h: passing_set(raw_score(o)) for h, o in s.items()}, "base0_items": b0}
            finish_run(r)
            sample.append(r)
            pts = r["points"]
            fresh = [h for h in pts if h in fl and not fl[h]["reused_from"] and fl[h]["same_state_as"] is None]
            status.append({"arm": arm, "task": task, "turns": turns, "T_used": t_eff, "full": not cut, "kind": s[max(s)]["kind"],
                           "points": len(pts), "fresh": len(fresh), "reused_old_record": sum(1 for h in pts if h in fl and fl[h]["reused_from"]),
                           "same_state": sum(1 for h in pts if h in fl and fl[h]["same_state_as"] is not None),
                           "old_record_only": sum(1 for h in pts if h not in fl),
                           "no_record": sorted(set(range(1, t_eff)) - set(pts)),
                           "labels": sorted({f["label"] for h, f in fl.items() if h <= t_eff}),
                           "ambiguous_turn_stretches": uncertain, "truly_every_turn": len(fresh) == t_eff - 1})
    return sample, {"status": status, "tasks_all": tasks, "check_lists_differ_from_all_arms": differ}


def finish_run(r: dict) -> None:
    """The points and the truth, from a run's scored outcomes."""
    r["points"] = sorted(h for h in r["scored"] if 0 < h < r["T"])
    r["free_for_share"] = r["free"] if not r["checks"] else 0
    r["truth"] = curve_of(r, set(r["scored"]))
    r["value_list"], r["value_count"] = {}, {}
    last = r["items"][0]
    for h in range(0, r["T"] + 1):
        last = r["items"].get(h, last)
        r["value_list"][h] = last
        r["value_count"][h] = round(r["truth"][h], 9)


def curve_of(r: dict, kept: set) -> list:
    """The curve with only `kept` scored, under the project's reward rule."""
    s = {h: r["scored"][h] for h in set(kept) | {0, r["T"]} if h in r["scored"]}
    return ph.curve(s, r["checks"], r["free_for_share"], reward="last-scored")[0]


def without_doubts(sample: list) -> list:
    """The sample without the two known doubts: the noisy check removed, the questioned run left out."""
    out = []
    for r in sample:
        if (r["arm"], r["task"]) == QUESTIONED_RUN:
            continue
        if r["task"] == NOISY_TASK:
            r = drop_check(r, NOISY_CHECK)
        out.append(r)
    return out


def drop_check(r: dict, name: str) -> dict:
    """A copy of a run without one check. A count-only scorer (this one's checks are marked ✓/✗ in its text, which
    power_horizons reads as a count) loses one from its count where the check passed."""
    n = dict(r)
    n["items"] = {h: it - {name} for h, it in r["items"].items()}
    if r["checks"]:
        n["checks"] = [c for c in r["checks"] if c != name]
    else:
        new = {}
        for h, o in r["scored"].items():
            p, t = o["x"]
            new[h] = {**o, "x": (p - (name in r["items"][h]), t - 1)}
        n["scored"] = new
        n["free"] = r["free"] - (name in r["base0_items"])
    finish_run(n)
    return n


# ---------------------------------------------------------------------------------------------------------- schedules
def every(r: dict, k: int) -> set:
    return {h for h in r["points"] if h % k == 0}


def dense_then(r: dict, upto: int, k: int) -> set:
    return {h for h in r["points"] if h <= upto or h % k == 0}


def bisect(r: dict, mode: str, grid: int = 0, stats: Counter | None = None, only: set | None = None) -> set:
    """Score the two ends (H = 0 and H = T, both free) and, recursively, the midpoint wherever the ends differ. `mode`:
    ends agree if their whole check list is the same ('list') or their count of counted checks is ('count'). With `grid`,
    start from every grid-th turn instead of the two ends. With `only`, land only on those turns, and stop where an
    interval has none. Assumes nothing changes and reverts between agreeing ends."""
    val = r["value_list"] if mode == "list" else r["value_count"]
    seeds = sorted({0, r["T"], *(every(r, grid) if grid else ())})
    kept = set(seeds) - {0, r["T"]}
    todo = list(zip(seeds, seeds[1:]))
    while todo:
        a, b = todo.pop()
        if b - a <= 1:
            continue
        if val[a] == val[b]:
            if stats is not None:
                stats["intervals with agreeing ends"] += 1
                if {val[h] for h in range(a + 1, b)} != {val[a]}:
                    stats["of which something inside differs"] += 1
            continue
        if only is None:
            m = (a + b) // 2
        else:
            inside = [h for h in range(a + 1, b) if h in only]
            if not inside:
                continue
            m = inside[len(inside) // 2]
        kept.add(m)
        todo += [(a, m), (m, b)]
    return {h for h in kept if h in r["points"]}


def is_same_state(f: dict | None) -> bool:
    return bool(f) and (f["same_state_as"] is not None or f["dedup_audit_of"] is not None)


def skip_same_state(r: dict) -> set:
    """Reuse only where the row shows the machine was identical. Jobs with no state check keep every point. A same_state_as
    row has no score of its own to test against, so only the rows scored anyway (dedup_audit_of) can show an error."""
    return {h for h in r["points"] if not is_same_state(r["flags"].get(h))}


def not_read_only(r: dict) -> set:
    return {h for h in r["points"] if r["classes"].get(h, {"edit"}) - READ_ONLY}


def writes_only(r: dict) -> set:
    """Also skips turns that only run Go's tools or write under /tmp."""
    return {h for h in r["points"] if r["classes"].get(h, {"edit"}) - READ_ONLY - {"gotool", "tmp"}}


# What can reach each kind of scorer, by reading how the scorers work (residue scope §2), written before seeing the results.
FAMILY_RULE = {"running service": {"restart", "api", "script"},  # source edits and builds don't reach a running service
               "rebuilds": {"edit", "api", "script"},  # the scorer itself builds from source and restarts
               "always restarts": {"build", "api", "script"}}  # restarts from the binary file on disk
# The same rule after its one miss (job queue, B1, H = 10: a bare restart changed the score). Fitted to that miss, and only
# 2 runs of this kind are in the sample, so this version's clean result says little about that kind.
FAMILY_RULE_AMENDED = {**FAMILY_RULE, "always restarts": {"build", "restart", "api", "script"}}


def family_rule(r: dict, rule: dict = FAMILY_RULE_AMENDED) -> set:
    want = rule[r["family"]]
    return {h for h in r["points"] if r["classes"].get(h, {"edit"}) & want}


def family_rule_first(r: dict) -> set:
    return family_rule(r, FAMILY_RULE)


def family_rule_same_state(r: dict) -> set:
    return family_rule(r) & skip_same_state(r)


def not_read_only_same_state(r: dict) -> set:
    return not_read_only(r) & skip_same_state(r)


def bisect_on_family_rule(r: dict) -> set:
    return bisect(r, "list", only=family_rule(r))


def only_count_changes(r: dict) -> set:
    """Foresight, not a method: the fewest points that keep the curve exact."""
    return {h for h in r["points"] if r["value_count"][h] != r["value_count"][h - 1]}


def only_list_changes(r: dict) -> set:
    """Foresight, not a method: the fewest points that keep the whole check list exact."""
    return {h for h in r["points"] if r["value_list"][h] != r["value_list"][h - 1]}


SCHEDULES = [
    ("1", "every 2 turns", lambda r: every(r, 2)),
    ("1", "every 5 turns", lambda r: every(r, 5)),
    ("1", "every 10 turns", lambda r: every(r, 10)),
    ("2", "every turn to H=10, then every 2", lambda r: dense_then(r, 10, 2)),
    ("2", "every turn to H=10, then every 5", lambda r: dense_then(r, 10, 5)),
    ("2", "every turn to H=20, then every 2", lambda r: dense_then(r, 20, 2)),
    ("2", "every turn to H=20, then every 5", lambda r: dense_then(r, 20, 5)),
    ("3", "bisection, ends compared by check list", lambda r: bisect(r, "list")),
    ("3", "bisection, ends compared by count", lambda r: bisect(r, "count")),
    ("4", "skip turns the row shows same-state", skip_same_state),
    ("4", "skip turns the commands say are read-only", not_read_only),
    ("5", "bisection by list from every 5th turn", lambda r: bisect(r, "list", 5)),
    ("5", "bisection by list from every 10th turn", lambda r: bisect(r, "list", 10)),
    ("5", "bisection by list, landing only on turns the rule keeps", bisect_on_family_rule),
    ("5", "skip read-only, Go-tool and /tmp-only turns", writes_only),
    ("5", "by scorer kind: only commands that can reach it", family_rule_first),
    ("5", "the same, with restarts kept for always-restart scorers", family_rule),
    ("5", "read-only skipped, then same-state skipped", not_read_only_same_state),
    ("5", "by scorer kind, then same-state skipped", family_rule_same_state),
    ("foresight", "only turns where the count changes", only_count_changes),
    ("foresight", "only turns where the check list changes", only_list_changes),
]


# ---------------------------------------------------------------------------------------------------------- evaluation
def stat_keys() -> list:
    return ["summed", *[f"discounted_{g}" for g in ph.GAMMAS], *[f"fixed_budget_{b}" for b in ph.BUDGETS], "fixed_budget"]


def why_wrong(r: dict, kept: set, sim: list) -> list:
    """Each stretch of wrong points: where it starts, what that turn's commands were, and whether the change it missed
    was still there at the next scored point (a delay) or had reverted by then (between agreeing points)."""
    stretches = []
    kept_all = sorted(set(kept) | {0, r["T"]})
    h = 1
    while h < r["T"]:
        if h in r["points"] and abs(sim[h] - r["truth"][h]) > EPS:
            start = h
            while h < r["T"] and abs(sim[h] - r["truth"][h]) > EPS:
                h += 1
            nxt = min(k for k in kept_all if k > start)
            prev = max(k for k in kept_all if k < start)
            kind = "reverted" if abs(r["truth"][nxt] - r["truth"][prev]) < EPS else "delayed"
            stretches.append({"from": start, "to": h - 1, "error": round(abs(sim[start] - r["truth"][start]), 4), "kind": kind,
                              "turn": main_class(r["classes"].get(start, {"none"}))})
        else:
            h += 1
    return stretches


def point_seconds(r: dict, h: int) -> float | None:
    """A point's measured save + score + undo, from its row. None if it wasn't scored in this job, or it crossed a pause."""
    f = r["flags"].get(h)
    if not f or f["reused_from"] or f["same_state_as"] is not None or not f["seconds"] or f["seconds"] >= PAUSE_SECONDS:
        return None
    return f["seconds"]


def evaluate(sample: list, fn) -> dict:
    pts = kept_n = wrong_pts = 0
    time_all = time_saved = 0.0
    errs, broken, sim_stats, truth_stats = [], [], {}, {}
    kinds, turns_at = Counter(), Counter()
    for r in sample:
        kept = fn(r)
        sim = curve_of(r, kept)
        pts += len(r["points"])
        kept_n += len(kept)
        for h in r["points"]:
            s = point_seconds(r, h)
            if s:
                time_all += s
                time_saved += s if h not in kept else 0
        run_errs = [abs(sim[h] - r["truth"][h]) for h in r["points"]]
        errs += run_errs
        n_wrong = sum(1 for e in run_errs if e > EPS)
        wrong_pts += n_wrong
        if n_wrong:
            st = why_wrong(r, kept, sim)
            kinds.update(x["kind"] for x in st)
            turns_at.update(x["turn"] for x in st)
            broken.append({"arm": r["arm"], "task": r["task"], "wrong_points": n_wrong, "of": len(r["points"]),
                           "max_error": round(max(run_errs), 4), "stretches": st})
        if r["full"]:
            sim_stats[(r["arm"], r["task"])] = ph.stats(sim)
            truth_stats[(r["arm"], r["task"])] = ph.stats(r["truth"])
    share = kept_n / pts if pts else 0
    time_share = time_saved / time_all if time_all else 0
    out = {"runs": len(sample), "points": pts, "kept": kept_n, "kept_share": share,
           "env_hours_saved_on_this_sample": (pts - kept_n) * COST_SKIPPED_POINT / 3600,
           "env_hours_saved_on_remaining_by_points": (1 - share) * REMAINING_POINTS * COST_SKIPPED_POINT / 3600,
           "share_of_measured_point_time_saved": time_share,
           "env_hours_saved_on_remaining_by_measured_time": time_share * REMAINING_POINTS * COST_SKIPPED_POINT / 3600,
           "curve": {"mean_abs": sum(errs) / len(errs) if errs else 0, "max_abs": max(errs) if errs else 0, "runs_wrong": len(broken),
                     "points_wrong": wrong_pts, "share_points_wrong": wrong_pts / pts if pts else 0},
           "exact": not broken, "wrong_stretches": dict(kinds), "wrong_stretches_start_on_turn_class": dict(turns_at), "broken_runs": broken}
    per = {}
    for key in stat_keys():
        d = [sim_stats[k][key] - truth_stats[k][key] for k in truth_stats]
        per[key] = {"mean_abs": sum(abs(x) for x in d) / len(d) if d else 0, "max_abs": max((abs(x) for x in d), default=0),
                    "mean_signed": sum(d) / len(d) if d else 0}
    out["power_per_task_and_arm"] = {"runs": len(truth_stats), **per}
    diffs = {}
    for x, y in COMPARISONS:
        tasks = sorted(t for a, t in truth_stats if a == x and (y, t) in truth_stats)
        if not tasks:
            continue
        row = {"tasks": tasks}
        for key in stat_keys():
            tr = sum(truth_stats[(x, t)][key] - truth_stats[(y, t)][key] for t in tasks) / len(tasks)
            si = sum(sim_stats[(x, t)][key] - sim_stats[(y, t)][key] for t in tasks) / len(tasks)
            row[key] = {"truth": tr, "schedule": si, "error": si - tr, "sign_flips": bool((tr > EPS and si < -EPS) or (tr < -EPS and si > EPS))}
        diffs[f"{x} minus {y}"] = row
    out["arm_differences"] = diffs
    out["arm_difference_worst_error"] = {key: max((abs(v[key]["error"]) for v in diffs.values()), default=0) for key in stat_keys()}
    out["arm_difference_sign_flips"] = sorted(f"{name}: {key}" for name, v in diffs.items() for key in stat_keys() if v[key]["sign_flips"])
    return out


# ------------------------------------------------------------------------------------------------- where changes happen
def change_tables(sample: list) -> dict:
    by_class, by_family_class, by_bucket, state_by_class = (defaultdict(Counter) for _ in range(4))
    pair_state, rule_vs_state, at_end = Counter(), Counter(), Counter()
    on_read_only, changes_per_run = [], []
    for r in sample:
        rule = family_rule(r)
        n_list = 0
        for h in r["points"]:
            cl = main_class(r["classes"].get(h, {"none"}))
            lc = r["value_list"][h] != r["value_list"][h - 1]
            cc = r["value_count"][h] != r["value_count"][h - 1]
            n_list += lc
            for table, key in ((by_class, cl), (by_family_class, f"{r['family']} / {cl}")):
                table[key]["points"] += 1
                table[key]["list changes"] += lc
                table[key]["count changes"] += cc
            b = "H=1" if h == 1 else "2-5" if h <= 5 else "6-10" if h <= 10 else "11-20" if h <= 20 else "21-40" if h <= 40 else "41+"
            by_bucket[b]["points"] += 1
            by_bucket[b]["list changes"] += lc
            by_bucket[b]["count changes"] += cc
            f = r["flags"].get(h)
            state = "same state" if is_same_state(f) else "state differs" if (f and f["dedup_differs"]) else "state not checked"
            pair_state[f"{state}, check list {'changed' if lc else 'same as previous turn'}"] += 1
            state_by_class[cl][state] += 1
            rule_vs_state[f"{state}, check list {'changed' if lc else 'same'}, scorer-kind rule {'keeps' if h in rule else 'skips'}"] += 1
            if lc and not (r["classes"].get(h, {"edit"}) - READ_ONLY):
                on_read_only.append({"arm": r["arm"], "task": r["task"], "H": h, "count_changed": bool(cc), "state": state,
                                     "previous_turn": main_class(r["classes"].get(h - 1, {"none"})),
                                     "checks": sorted(r["value_list"][h] ^ r["value_list"][h - 1])[:6]})
        changes_per_run.append(n_list)
        if r["full"]:
            at_end["runs"] += 1
            at_end["end score's list differs from the last point's"] += r["value_list"][r["T"]] != r["value_list"][r["T"] - 1]
            at_end["end score's count differs from the last point's"] += r["value_count"][r["T"]] != r["value_count"][r["T"] - 1]
    order = {c: i for i, c in enumerate(CLASS_ORDER)}
    per_kind = {}
    for fam in ("running service", "rebuilds", "always restarts"):
        rs = [r for r in sample if r["family"] == fam]
        if not rs:
            continue
        changes = [(r, h) for r in rs for h in r["points"] if r["value_count"][h] != r["value_count"][h - 1]]
        per_kind[fam] = {"runs": len(rs), "tasks": len({r["task"] for r in rs}), "points": sum(len(r["points"]) for r in rs),
                         "first_rule_keeps": sum(len(family_rule_first(r)) for r in rs), "amended_rule_keeps": sum(len(family_rule(r)) for r in rs),
                         "count_changes": len(changes), "count_changes_the_first_rule_skips": sum(h not in family_rule_first(r) for r, h in changes),
                         "count_changes_the_amended_rule_skips": sum(h not in family_rule(r) for r, h in changes)}
    return {"by_turn_class": {k: dict(v) for k, v in sorted(by_class.items(), key=lambda kv: order[kv[0]])},
            "by_scorer_kind_and_class": {k: dict(v) for k, v in sorted(by_family_class.items())}, "by_scorer_kind": per_kind,
            "by_position": {k: dict(by_bucket[k]) for k in ("H=1", "2-5", "6-10", "11-20", "21-40", "41+") if k in by_bucket},
            "list_changes_per_run": {"median": statistics.median(changes_per_run) if changes_per_run else 0, "max": max(changes_per_run, default=0),
                                     "runs_with_none": sum(1 for x in changes_per_run if x == 0)},
            "points_by_state_and_list": dict(pair_state), "state_by_turn_class": {k: dict(v) for k, v in state_by_class.items()},
            "scorer_kind_rule_against_state": dict(rule_vs_state), "list_changes_on_read_only_turns": on_read_only, "at_the_end_score": dict(at_end)}


def reversals(sample: list) -> dict:
    """Checks that change and change back within a run: what bisection assumes doesn't happen between agreeing ends."""
    detail, blips, paused = [], [], []
    non_mono = n_checks = n_flipped = 0
    for r in sample:
        names = set().union(*r["value_list"].values())
        flipped = {}
        for c in names:
            seq = [c in r["value_list"][h] for h in range(0, r["T"] + 1)]
            changes = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
            if changes >= 2:
                flipped[c] = changes
        n_checks += len(names)
        n_flipped += len(flipped)
        if flipped:
            detail.append({"arm": r["arm"], "task": r["task"], "checks": len(flipped), "most_changes": max(flipped.values()), "names": sorted(flipped)[:8]})
        vals = [r["value_count"][h] for h in range(0, r["T"] + 1)]
        non_mono += any(b < a - EPS for a, b in zip(vals, vals[1:]))
        for h in range(1, r["T"]):  # one turn differs from both neighbours, which agree: a sign of noise, or a quick revert
            a, b, c = r["value_list"][h - 1], r["value_list"][h], r["value_list"][h + 1]
            if a == c and b != a:
                blips.append({"arm": r["arm"], "task": r["task"], "H": h, "checks": sorted(a ^ b)[:6]})
        for h in r["points"]:
            if (r["arm"], r["task"], h) in PAUSED_POINTS and (r["value_list"][h] != r["value_list"][h - 1] or r["value_list"][h] != r["value_list"][h + 1]):
                paused.append({"arm": r["arm"], "task": r["task"], "H": h})
    return {"runs": len(sample), "runs_with_a_check_that_changes_and_changes_back": len(detail), "checks_that_do": n_flipped,
            "checks_seen_passing": n_checks, "detail": detail, "runs_whose_count_ever_falls": non_mono, "one_turn_blips": blips,
            "points_scored_across_a_pause_where_the_list_changes": paused}


def forward_passes(r: dict, mode: str) -> tuple[int, int]:
    """Bisection scores out of order, but a replay only goes forward. Without a stored state per turn it needs one forward
    pass per level of midpoints: how many passes, and how many turns they replay in all."""
    val = r["value_list"] if mode == "list" else r["value_count"]
    level, passes, replayed = [(0, r["T"])], 0, 0
    while level:
        mids, nxt = [], []
        for a, b in level:
            if b - a > 1 and val[a] != val[b]:
                m = (a + b) // 2
                mids.append(m)
                nxt += [(a, m), (m, b)]
        if mids:
            passes += 1
            replayed += max(mids)
        level = nxt
    return passes, replayed


def bisection_failures(sample: list) -> dict:
    out = {}
    for mode in ("list", "count"):
        st: Counter = Counter()
        for r in sample:
            bisect(r, mode, stats=st)
        fp = [forward_passes(r, mode) for r in sample]
        out[mode] = {**st, "mean_forward_passes_per_run": sum(p for p, _ in fp) / len(fp) if fp else 0,
                     "turns_replayed_as_a_multiple_of_one_pass": sum(x for _, x in fp) / sum(r["T"] for r in sample) if sample else 0}
    return out


def classifier_quality(sample: list) -> dict:
    """How often the command text's read-only call is wrong, against the two things it can be tested on."""
    out = Counter()
    why = Counter()
    for r in sample:
        for h in r["points"]:
            ro = not (r["classes"].get(h, {"edit"}) - READ_ONLY)
            f = r["flags"].get(h)
            out["points"] += 1
            out["called read-only"] += ro
            word = "read-only" if ro else "not read-only"
            out[f"{word}: check list changed"] += r["value_list"][h] != r["value_list"][h - 1]
            out[f"{word}: count changed"] += r["value_count"][h] != r["value_count"][h - 1]
            if is_same_state(f) or (f and f["dedup_differs"]):
                same = is_same_state(f)
                out[f"state checked, {word}, machine {'same' if same else 'differed'}"] += 1
                if ro and not same:
                    d = f["dedup_differs"]
                    why["paths changed" if "paths" in d else d.split(": ")[-1] if d.startswith("summary") else d] += 1
    return {"counts": dict(out), "why_the_machine_differed_on_read_only_turns": dict(why),
            "ambiguous_turn_stretches": sum(r["uncertain_turns"] for r in sample)}


# ------------------------------------------------------------------------------------------------------------ memoization
def within_run_memo(sample: list) -> dict:
    """State hashes aren't stored, but equal states must have equal check lists (noise aside). So a turn whose list differs
    from the previous turn's and equals an earlier one's bounds what a cache of all earlier states could add to today's
    comparison with the last scored point."""
    returned = same_flag = checked = 0
    runs_returning = 0
    for r in sample:
        seen = {r["value_list"][0]}
        any_here = False
        for h in r["points"]:
            it, f = r["value_list"][h], r["flags"].get(h)
            if it != r["value_list"][h - 1] and it in seen:
                returned += 1
                any_here = True
            seen.add(it)
            same_flag += is_same_state(f)
            checked += is_same_state(f) or bool(f and f["dedup_differs"])
        runs_returning += any_here
    return {"points": sum(len(r["points"]) for r in sample), "state_checked": checked, "same_state_recorded": same_flag,
            "points_whose_list_returns_to_an_earlier_one_upper_bound": returned, "runs_with_such_a_point": runs_returning}


def memoization(sample: list, runs_root: Path, arms: dict) -> dict:
    out: dict = {"within_run_all_data": within_run_memo(sample), "within_run_without_doubts": within_run_memo(without_doubts(sample))}
    # File counts as a tighter test? Only if a known same-state pair always has equal counts.
    audits = equal = 0
    for r in sample:
        for f in r["flags"].values():
            ref = f.get("dedup_audit_of")
            if ref in r["flags"] and f["upper_entries"] is not None and r["flags"][ref]["upper_entries"] is not None:
                audits += 1
                equal += f["upper_entries"] == r["flags"][ref]["upper_entries"]
    out["file_count_as_a_test_of_same_state"] = {"same_state_pairs": audits, "with_equal_file_count": equal}
    # One solver run per (task, arm)?
    cells: dict = defaultdict(list)
    epochs: Counter = Counter()
    for arm, (lab, _nw) in arms.items():
        for label in lab.split(","):
            for p in ph.runs_of(label):
                meta = json.loads((p / "meta.json").read_text()) if (p / "meta.json").exists() else {}
                cells[(arm, meta.get("task") or p.parent.name)].append(label)
                epochs[str(meta.get("epoch"))] += 1
    out["solver_runs"] = {"cells": len(cells), "cells_with_more_than_one_run": sum(1 for v in cells.values() if len(v) > 1), "epochs": dict(epochs)}
    # No-work runs of one arm and task scored more than once, and of the untouched machine across experiment versions
    groups: dict = defaultdict(list)
    for arm, (_lab, nw) in arms.items():
        for label in nw.split(","):
            for p in ph.runs_of(label):
                groups[(arm, p.parent.name)].append(p)
    for p in runs_root.glob("nowork-*-S0*/*/*/scores.json"):
        groups[("untouched machine", p.parents[1].name)].append(p.parent)
    repeated = identical = 0
    differing: Counter = Counter()
    for ps in groups.values():
        ps = sorted(set(ps))
        if len(ps) > 1:
            sets = [passing_set(json.loads((p / "scores.json").read_text())) for p in ps]
            repeated += 1
            identical += len(set(sets)) == 1
            for x in sets[1:]:
                differing.update(sets[0] ^ x)
    out["no_work_scored_more_than_once"] = {"cells": repeated, "identical": identical, "checks_that_differed": dict(differing.most_common(12))}
    # The same point of the same run scored under more than one label: the only true repeats of a state we have
    scored_at: dict = defaultdict(dict)
    src_of = {(r["src"], r["task"]): r for r in sample}
    for f in sorted(runs_root.glob("*/*/*/horizon_scores.jsonl")):
        label = f.parents[2].name
        meta = json.loads((f.parent / "meta.json").read_text()) if (f.parent / "meta.json").exists() else {}
        args = meta.get("args") or {}
        if not args.get("prefix_log") or label in INVALID_LABELS:
            continue
        key = (Path(args["prefix_log"]).parent.name, meta.get("task") or f.parent.parent.name)
        if key not in src_of:
            continue
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            sc = r.get("scores") or {}
            if r.get("reused_from") or r.get("same_state_as") is not None or quiet(ph.outcome_of, sc, meta, key[1], int(r["H"]), "x")["kind"] == "error":
                continue
            scored_at[(*key, int(r["H"]))][label] = passing_set(sc)
    for p in runs_root.glob("hz-*/*/*/scores.json"):
        meta = json.loads((p.parent / "meta.json").read_text()) if (p.parent / "meta.json").exists() else {}
        args = meta.get("args") or {}
        if not args.get("prefix_log") or not args.get("prefix_turns"):
            continue
        key = (Path(args["prefix_log"]).parent.name, meta.get("task") or p.parents[1].name)
        if key not in src_of:
            continue
        sc = json.loads(p.read_text())
        if quiet(ph.outcome_of, sc, meta, key[1], int(args["prefix_turns"]), "x")["kind"] != "error":
            scored_at[(*key, int(args["prefix_turns"]))][p.parents[2].name] = passing_set(sc)
    rep: dict = defaultdict(lambda: {"pairs": 0, "identical": 0, "names": Counter(), "where": Counter()})
    for (src, task, h), by_label in scored_at.items():
        base_label = (src_of[(src, task)]["flags"].get(h) or {}).get("label")
        if base_label not in by_label:
            continue
        for label, s in by_label.items():
            if label == base_label:
                continue
            kind = "an old per-step job" if label.startswith("hz-") else "a check job" if label.startswith("hzcheck-") else "a superseded score and roll back job"
            rep[kind]["pairs"] += 1
            rep[kind]["identical"] += s == by_label[base_label]
            if s != by_label[base_label]:
                rep[kind]["names"].update(s ^ by_label[base_label])
                rep[kind]["where"][f"{src_of[(src, task)]['arm']} {task}"] += 1
    out["same_point_scored_twice"] = {k: {"pairs": v["pairs"], "identical": v["identical"], "checks_that_differed": dict(v["names"].most_common(10)),
                                          "where": dict(v["where"].most_common(8))} for k, v in rep.items()}
    # Across runs: same task, different arm. Their machines start differently, so equal lists bound the hits from above only.
    by_task: dict = defaultdict(list)
    for r in sample:
        by_task[r["task"]].append(r)
    total = list_match = pairs = pairs_same = h1_same = 0
    for rs in by_task.values():
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                pairs += 1
                pairs_same += a["items"][0] == b["items"][0]
                h1_same += a["value_list"][1] == b["value_list"][1]
            pool = {o["value_list"][h] for o in rs if o is not a for h in o["points"]}
            if pool:
                total += len(a["points"])
                list_match += sum(a["value_list"][h] in pool for h in a["points"])
    out["across_runs"] = {"tasks_with_more_than_one_arm": sum(1 for v in by_task.values() if len(v) > 1), "points_in_those_tasks": total,
                          "points_whose_list_appears_in_another_arm_upper_bound": list_match, "arm_pairs": pairs,
                          "arm_pairs_with_equal_no_work_lists": pairs_same, "arm_pairs_with_equal_lists_at_H1": h1_same}
    # The first point has nothing to compare with in its own job, though the no-work run scored the same machine
    firsts = [s for s in (point_seconds(r, 1) for r in sample) if s]
    alls = [s for r in sample for s in (point_seconds(r, h) for h in r["points"]) if s]
    out["first_point"] = {"runs": len(sample), "turn_1_read_only": sum(not (r["classes"].get(1, {"edit"}) - READ_ONLY) for r in sample),
                          "H1_list_same_as_no_work": sum(r["value_list"][1] == r["value_list"][0] for r in sample),
                          "seconds_first_point_median": statistics.median(firsts) if firsts else None,
                          "seconds_all_points_median": statistics.median(alls) if alls else None,
                          "seconds_all_points_mean": statistics.mean(alls) if alls else None}
    return out


# ------------------------------------------------------------------------------------------------------------------ main
def report(sample: list) -> dict:
    return {"schedules": {name: {"group": g, **evaluate(sample, fn)} for g, name, fn in SCHEDULES},
            "changes": change_tables(sample), "reversals": reversals(sample), "bisection_assumption": bisection_failures(sample),
            "classifier": classifier_quality(sample)}


def table(rep: dict) -> None:
    print(f"{'schedule':52s} {'kept':>6s} {'mean':>7s} {'max':>6s} {'runs':>5s} {'wrong':>6s} {'sum m':>7s} {'sum M':>7s} {'.90 M':>7s} {'b10 M':>7s} {'arm M':>7s} exact")
    for name, s in rep["schedules"].items():
        c, p = s["curve"], s["power_per_task_and_arm"]
        print(f"{name:52s} {s['kept_share']:6.1%} {c['mean_abs']:7.4f} {c['max_abs']:6.3f} {c['runs_wrong']:5d} {c['share_points_wrong']:6.1%} "
              f"{p['summed']['mean_abs']:7.4f} {p['summed']['max_abs']:7.4f} {p['discounted_0.9']['max_abs']:7.4f} {p['fixed_budget_10']['max_abs']:7.4f} "
              f"{s['arm_difference_worst_error']['summed']:7.4f} {'yes' if s['exact'] else 'no'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="write the full results here (the only file this script writes)")
    a = ap.parse_args()
    arms = arms_from_config()
    sample, inv = load_runs(arms)
    st = inv["status"]
    print(f"{len(st)} runs with rows; {sum(s['full'] for s in st)} with rows to the end; "
          f"{sum(s['truly_every_turn'] and s['full'] for s in st)} of those scored fresh at every turn; {sum(s['points'] for s in st)} points "
          f"({sum(s['fresh'] for s in st)} scored in these jobs, {sum(s['reused_old_record'] for s in st)} reused from old per-step records, "
          f"{sum(s['same_state'] for s in st)} by same state, {sum(s['old_record_only'] for s in st)} only in an old record, "
          f"{sum(len(s['no_record']) for s in st)} with no record)")
    print("tasks whose counted checks differ between one pair's arms and all arms:", inv["check_lists_differ_from_all_arms"])
    out = {"sample": inv, "cost": {"all_in_seconds_per_point": COST_ALL_IN, "skipped_point_saves_seconds": COST_SKIPPED_POINT, "remaining_points": REMAINING_POINTS}}
    out["all_data"] = report(sample)
    out["without_the_two_doubts"] = report(without_doubts(sample))
    out["memoization"] = memoization(sample, ph.RUNS, arms)
    print("\nAll data (kept share; curve error mean, max; runs and points wrong; POWER_H per task and arm: summed mean, summed max, "
          "discounted 0.90 max, budget 10 max; worst arm difference in summed):")
    table(out["all_data"])
    print("\nWithout the noisy check and the A2 tamper run:")
    table(out["without_the_two_doubts"])
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=lambda x: sorted(x) if isinstance(x, (set, frozenset)) else str(x)))
        print(f"\nwritten {a.json}")


if __name__ == "__main__":
    main()
