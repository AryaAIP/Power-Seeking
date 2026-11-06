"""Write each run's complete, readable record from the raw data in WSL. Reads only; never changes the data.

Usage (in WSL, from the Control Tower checkout so inspect_ai is importable, harness on PYTHONPATH):
  .venv/bin/python ~/power-v0/harness/export_run.py LABEL [LABEL ...] [--out DIR] [--check]

For every sample in data/evals/<LABEL>/*.eval it writes OUT/<LABEL>/<task>/<run>/:
  transcript.md   header with every setting, the prompts as sent, then every step: the full reasoning,
                  the tool call exactly as sent and the output exactly as received
  prompts/        system.txt, first-user.txt, and handover.txt for runs that continue a trajectory's chat
  config.json     the run's settings: policy args, generate config, harness hashes, trajectory, versions
  meta.json       our run record (timings, steps, how the run ended), copied from the run's folder
  scores.json     the scorer's full output, our parsed counts, and which checks passed
  usage.csv       one row per model call: tokens in, cached, out, reasoning, reasoning characters
  raw-paths.txt   where the unredacted raw data lives in WSL (log, snapshot, database dump)
The .eval log stays the source; this is generated from it. Known secret values (passwords and keys
from the environment's compose file, and passwords inside connection URLs) are replaced by a
placeholder in the copies, so the folder can be shared; the raw log in WSL is unchanged.
--check prints, per run, whether every piece is present and non-empty.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

sys.path.insert(0, str(Path(__file__).parent))
from extract import DATA, find_run_dir, parse_bugfix_text, parse_checks, rows_for_label  # noqa: E402
from power_paths import CONFIG as CONFIG_DIR, CT, RUNS as OUT_DEFAULT  # noqa: E402

COMPOSE = CT / ".environments" / "model_registry" / "codebase" / "compose.yml"
FENCE = "````"


def _secrets() -> list[str]:
    """Secret values from the environment's own setup files (compose file, credentials script, storage and
    database init): passwords, keys, secrets and tokens, and passwords in URLs."""
    vals = set()
    base = COMPOSE.parent
    files = [COMPOSE, base / "src" / "init-credentials.sh", *base.glob("init/s3/*"), *base.glob("init/db/*.sql")]
    text = "\n".join(f.read_text(errors="ignore") for f in files if f.is_file())
    for m in re.finditer(r"\"?([a-z_]*(?:secret|password|passwd|key|token)[a-z_]*)\"?\s*[:=]\s*[\"']([^\"'\s,}]+)", text, re.I):
        vals.add(m.group(2))
    for m in re.finditer(r"PASSWORD\s+'([^']+)'", text):
        vals.add(m.group(1))
    for m in re.finditer(r"([A-Z0-9_]*(?:PASS|SECRET|KEY|TOKEN)[A-Z0-9_]*)\s*[:=]\s*\"?([^\s\"]+)", text):
        vals.add(m.group(2))
    for m in re.finditer(r"://[^:/\s\"]+:([^@\s\"]+)@", text):
        vals.add(m.group(1))
    return sorted((v for v in vals if len(v) >= 6 and not v.startswith("$")), key=len, reverse=True)


SECRETS = _secrets()


# Secrets made while a run was going (storage keys, key files, tokens), which the known values can't contain.
_NL = r"(?:\r?\n|(?:\\+r)?\\+n)"  # a line break, real or escaped inside JSON
_PATTERNS = [
    # a whole private key block, BEGIN to END
    re.compile(r"-----BEGIN ([A-Z0-9 ]*)PRIVATE KEY-----(?:(?!-----BEGIN )[\s\S]){0,20000}?-----END \1PRIVATE KEY-----"),
    # a block cut short (by head, say) with no END line: BEGIN and the base64 lines after it
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----(?:[ \t]*" + _NL + r"[ \t]*[A-Za-z0-9+/]+=*(?=[ \t]*(?:" + _NL + r"|$|[\"'`])))*"),
    re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),  # AWS-style access key ids
    re.compile(r"sk-(?:or-v1-[A-Za-z0-9]{20,}|(?:ant|proj)-[A-Za-z0-9_-]{20,})|(?<![\w-])sk-[A-Za-z0-9]{32,}"),  # API keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{22,}"),  # GitHub tokens
]
# The secret key after its label (aws_secret_access_key, secret_key, secretKey, SecretAccessKey, MINIO_SECRET_KEY,
# MINIO_ROOT_PASSWORD), quoted or not, also inside JSON strings; and the secret in `mc alias set NAME URL ACCESS SECRET`.
_LABELLED = re.compile(r"((?i:secret[_-]?(?:access[_-]?)?key|minio_root_password)(?:\\*[\"'])?\s*[:=]\s*(?:\\*[\"'])?)"
                       r"([A-Za-z0-9/+=_-]{8,})(?![\w/+=.(\[-])")
_MC_SECRET = re.compile(r"(\bmc\s+(?:alias\s+set|config\s+host\s+add)\s+\S+\s+\S*(?:://|\$)\S*\s+\S+\s+(?:\\*[\"'])?)"
                        r"(?![$<{])([^\s\"'\\]{8,})")
_VAR = re.compile(r"[A-Za-z_]\w*")  # a variable holding the secret, as in `SecretKey: secretKey`, is kept
_VAR_WORDS = re.compile(r"(?i)secret|key|password|token|cred|env")


def redact(s: str | None) -> str:
    s = s or ""
    for v in SECRETS:
        s = s.replace(v, "<secret>")
    for rx in _PATTERNS:
        s = rx.sub("<secret>", s)
    s = _LABELLED.sub(lambda m: m[0] if _VAR.fullmatch(m[2]) and _VAR_WORDS.search(m[2]) else m[1] + "<secret>", s)
    s = _MC_SECRET.sub(r"\1<secret>", s)
    s = re.sub(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", "<token>", s)  # tokens the service issued during a run
    return re.sub(r"(://[^:/\s\"'@]+:)([^@\s\"']+)@", r"\1<secret>@", s)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(getattr(c, "text", "") or "" for c in content if type(c).__name__ == "ContentText")


def _reasoning(content) -> list[str]:
    if isinstance(content, str):
        return []
    out = []
    for c in content:
        if type(c).__name__ == "ContentReasoning":
            r = c.reasoning or ""
            if str(getattr(c, "redacted", "")).lower() == "true":
                r = "[the provider marked this reasoning as redacted]\n" + r
            out.append(r)
    return out


def _block(text: str, lang: str = "text") -> str:
    return f"{FENCE}{lang}\n{redact(text).rstrip()}\n{FENCE}\n"


def _config_text(label: str) -> str:
    base = re.sub(r"-S[01]$", "", label)
    for name in (label, base):
        p = CONFIG_DIR / f"{name}.txt"
        if p.exists():
            return p.read_text(errors="replace")
    return ""


def _checks(expl: str) -> list[dict]:
    """Which checks passed, from the scorer's PASS:/FAIL: lines (check-list scorers)."""
    return [{"check": m.group(2).strip()[:300], "passed": m.group(1) == "PASS"}
            for m in re.finditer(r"^\s*(PASS|FAIL):\s*(.+)$", expl or "", re.M)]


def _bugfix_tests(run_dir: Path | None) -> list[dict]:
    f = run_dir / "bugfix_tests.txt" if run_dir else None
    if not f or not f.exists():
        return []
    return _bugfix_tests_text(f.read_text(errors="replace"))


def _bugfix_tests_text(text: str) -> list[dict]:
    return [{"test": m.group(2), "outcome": m.group(1)}
            for m in re.finditer(r"^(PASSED|FAILED|ERROR|SKIPPED)\s+\S*::(test_\w+)", text or "", re.M)]


def _horizon_rows(run_dir: Path, task: str) -> list[dict]:
    """Score and roll back's horizon_scores.jsonl (rollback.py), one row per scoring point, each score shaped like a
    run's scores.json (scorer, checks, bugfix_tests, parsed) so power_horizons reads both the same way."""
    out = []
    for ln in (run_dir / "horizon_scores.jsonl").read_text().splitlines():
        r = json.loads(ln)
        sc = (r.get("score") or {}).get("linux_scorer") or {}
        expl, value = sc.get("explanation") or "", sc.get("value")
        cp, ct, method = parse_checks(expl)
        bp, bt, bnote = parse_bugfix_text(r.get("bugfix_tests") or "", task)
        parsed = {"verdict": value.get("main_task_success") if isinstance(value, dict) else value,
                  "checks_passed": cp, "checks_total": ct, "checks_parse": method,
                  "bugfix_passed": bp, "bugfix_total": bt, "bugfix_note": bnote}
        row = {"H": r["H"], "started": r.get("started"),
               "scores": {"scorer": {"linux_scorer": sc} if sc else {}, "checks": _checks(expl),
                          "bugfix_tests": _bugfix_tests_text(r.get("bugfix_tests") or ""), "parsed": parsed},
               "state_equal": r.get("state_equal"), "error": r.get("error") or r.get("score_error"),
               "skipped": r.get("skipped"),  # a point not scored because its save failed (the machine untouched)
               "reused_from": r.get("reused_from"),  # a point a per-step job had already scored: its record (runs/...)
               "same_state_as": r.get("same_state_as"),  # state dedup: the earlier point whose machine was identical
               "dedup_audit_of": r.get("dedup_audit_of"),  # ... or scored anyway, as a check against that point
               "dedup_differs": r.get("dedup_differs"),
               "seconds": r.get("seconds"), "save": r.get("save"), "restore": r.get("restore")}
        out.append(row)
    return out


def export_sample(label: str, log_path: Path, log, s, index_row: dict | None, out_root: Path) -> Path:
    meta_md = s.metadata or {}
    task = (meta_md.get("main_task") or {}).get("id") or str(s.id).split(":")[0]
    run_dir = find_run_dir(label, task, s.epoch, s.id)
    info = json.loads((run_dir / "meta.json").read_text()) if run_dir and (run_dir / "meta.json").exists() else {}
    run_name = run_dir.name if run_dir else f"e{s.epoch}-{hashlib.sha1(str(s.id).encode()).hexdigest()[:8]}"
    out = out_root / label / task / run_name
    (out / "prompts").mkdir(parents=True, exist_ok=True)

    msgs = list(s.messages or [])
    kept = info.get("context") == "kept"
    first_asst = next((i for i, m in enumerate(msgs) if m.role == "assistant"), len(msgs))
    # In a run that continues a trajectory's chat, the solver's own part starts after the hand-over.
    solver_start = info.get("kept_messages", first_asst) if kept else first_asst
    system = "\n\n".join(_text(m.content) for m in msgs[:solver_start] if m.role == "system")
    first_user = "\n\n".join(_text(m.content) for m in msgs[:first_asst] if m.role == "user")
    handover = _text(msgs[solver_start - 1].content) if kept and solver_start >= 1 else ""
    no_model = info.get("solve") is False and not system
    none_sent = "(nothing was sent: this run had no solver and made no model calls)\n"
    (out / "prompts" / "system.txt").write_text(redact(system) if system else none_sent if no_model else "")
    (out / "prompts" / "first-user.txt").write_text(redact(first_user) if first_user else none_sent if no_model else "")
    if kept:
        (out / "prompts" / "handover.txt").write_text(redact(handover))

    # settings. The model is built inside the policy, so the settings actually sent are on each model call.
    ev = log.eval
    calls = [e for e in (s.events or []) if e.event == "model"]
    gen_used = calls[0].config.model_dump(exclude_none=True, mode="json") if calls and calls[0].config else None
    cfg = {
        "generate_config_sent": gen_used,
        "label": label, "task": task, "epoch": s.epoch, "sample_id": str(s.id),
        "eval_log": log_path.name, "eval_log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "eval": {k: (v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v))
                 for k, v in ev.model_dump(exclude={"dataset"}, mode="json").items()},
        "run_record": info,
        "launch_config_file": _config_text(label).splitlines(),
    }
    (out / "config.json").write_text(redact(json.dumps(cfg, indent=2, default=str)))
    if run_dir and (run_dir / "meta.json").exists():
        (out / "meta.json").write_text(redact((run_dir / "meta.json").read_text()))
    for extra in ("probe.txt", "bugfix_tests.txt"):  # small outputs of our own checks, kept as they are
        if run_dir and (run_dir / extra).exists():
            (out / extra).write_text(redact((run_dir / extra).read_text(errors="replace")))
    hz_rows = _horizon_rows(run_dir, task) if run_dir and (run_dir / "horizon_scores.jsonl").exists() else []
    if hz_rows:  # score and roll back: one score per scoring point
        (out / "horizon_scores.jsonl").write_text("".join(redact(json.dumps(r, default=str)) + "\n" for r in hz_rows))

    # scores
    scores = {name: {"value": sc.value, "answer": sc.answer, "explanation": sc.explanation,
                     "metadata": sc.metadata} for name, sc in (s.scores or {}).items()}
    expl = next((v["explanation"] for v in scores.values() if v.get("explanation")), "") or ""
    (out / "scores.json").write_text(redact(json.dumps(
        {"scorer": scores, "checks": _checks(expl), "bugfix_tests": _bugfix_tests(run_dir),
         "parsed": index_row}, indent=2, default=str)))

    # usage per model call
    r_tok = r_chars = 0
    with (out / "usage.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["call", "timestamp", "input_tokens", "input_tokens_cache_read", "output_tokens",
                    "reasoning_tokens", "reasoning_chars", "seconds"])
        for i, e in enumerate(calls, 1):
            u = e.output.usage if e.output else None
            rc = sum(len(r) for ch in (e.output.choices if e.output else []) for r in _reasoning(ch.message.content))
            r_tok += (u.reasoning_tokens or 0) if u else 0
            r_chars += rc
            w.writerow([i, e.timestamp, u.input_tokens if u else "", (u.input_tokens_cache_read or 0) if u else "",
                        u.output_tokens if u else "", (u.reasoning_tokens or 0) if u else "", rc,
                        round(e.working_time or 0, 1)])

    (out / "raw-paths.txt").write_text(
        f"eval log (unredacted, the source): {log_path}\n"
        f"run folder (snapshot.txt, db_s3.txt with the full database export, meta.json): {run_dir}\n")

    # transcript
    steps = []
    n = 0
    tool_out = {m.tool_call_id: m for m in msgs if m.role == "tool"}
    for m in msgs[solver_start:]:
        if m.role != "assistant":
            if m.role == "user":
                steps.append(f"### Message from the user (message {msgs.index(m) + 1})\n\n{_block(_text(m.content))}")
            continue
        reasoning = _reasoning(m.content)
        text = _text(m.content)
        tcs = m.tool_calls or []
        head = []
        if reasoning:
            head.append("**Reasoning**\n\n" + "".join(_block(r) for r in reasoning))
        if text.strip():
            head.append("**Text**\n\n" + _block(text))
        if not tcs:
            n += 1
            steps.append(f"### Step {n}: no tool call\n\n" + "\n".join(head))
            continue
        for j, tc in enumerate(tcs):
            n += 1
            res = tool_out.get(tc.id)
            out_text = _text(res.content) if res else "(no result recorded)"
            err = getattr(res, "error", None) if res else None
            part = [f"### Step {n}: `{tc.function}`\n"]
            if j == 0:
                part += head
            part.append("**Tool call**\n\n" + _block(json.dumps(tc.arguments, indent=2, ensure_ascii=False), "json"))
            part.append("**Output**\n\n" + _block(out_text))
            if err:
                part.append(f"**Tool error:** {redact(str(err))}\n")
            steps.append("\n".join(part))

    u = index_row or {}
    traj = info.get("traj") or ""
    header = [
        f"# {label} · {task} · epoch {s.epoch}\n",
        "*Generated by `harness/export_run.py` from the raw Inspect log; nothing is summarised or left out. "
        "Known secret values are replaced by `<secret>`; the raw log in WSL is unchanged.*\n",
        "| Field | Value |", "| --- | --- |",
        f"| Kind of run | {'continues a trajectory chat (after run)' if kept else ('no solver (no-work run)' if info.get('solve') is False else 'new chat')} |",
        f"| Account | {info.get('solver_user') or ('dev' if info.get('dev_setup') else 'root')} |",
        f"| Removed from dev's environment | {info.get('dev_strip_env') or 'nothing (old setup)'} |",
        f"| Model | {info.get('model')}, provider {json.dumps(info.get('provider'))} |",
        f"| Generate config sent | {redact(json.dumps(gen_used, default=str)) if gen_used else 'none (no model calls)'} |",
        f"| Trajectory | {traj or 'none'} (replayed {info.get('replay_kept', 0)} calls) |",
        f"| Instruction (trajectory runs) | {info.get('incline') or 'none'} |",
        f"| Hand-over note | {info.get('handover_note') or 'none'} |",
        f"| Step cap | {info.get('max_steps')} |",
        f"| Started / finished (UTC) | {info.get('started')} / {info.get('finished')} |",
        f"| How it ended | {info.get('ended_by')} |",
        f"| Tool calls by the agent | {info.get('solver_tool_calls')} |",
        f"| Score | verdict {u.get('verdict')}, checks {u.get('checks_passed')}/{u.get('checks_total')}, "
        f"bug-fix tests {u.get('bugfix_passed')}/{u.get('bugfix_total')}, answer {u.get('answer')} |",
        f"| Tokens | in {u.get('input_tokens')} (cached {u.get('input_tokens_cache_read')}), out {u.get('output_tokens')}, "
        f"reasoning {r_tok} ({r_chars} characters of reasoning text, {round(r_chars / r_tok, 2) if r_tok else '-'} per token) |",
        f"| Error | {redact(str(u.get('error'))) if u.get('error') else 'none'} |",
        *([f"| Scored partway (score and roll back) | {len(hz_rows)} of {len(info.get('score_points') or [])} points, "
           f"H = {', '.join(str(r['H']) for r in hz_rows)}; state equal after {sum(1 for r in hz_rows if r['state_equal'])} "
           f"of {len(hz_rows)} restores; scores in horizon_scores.jsonl |"] if info.get("score_points") is not None else []),
        f"| Raw data | see raw-paths.txt |", "",
        "## Prompts as sent\n",
        "### System prompt\n", _block(system),
        "### First user message(s)\n", _block(first_user or "(empty)"),
    ]
    if kept:
        header += [f"### The trajectory's chat\n\nMessages 1 to {solver_start - 1} are the trajectory's own chat, "
                   f"exactly as recorded in `{traj}`. They are not repeated here; see that trajectory's transcript.\n",
                   f"### Hand-over message (message {solver_start})\n", _block(handover)]
    body = "\n".join(header) + "\n## Steps\n\n" + ("\n".join(steps) if steps else "(no steps: no solver ran)\n")
    (out / "transcript.md").write_text(body)
    return out


REQUIRED = ["transcript.md", "prompts/system.txt", "prompts/first-user.txt", "config.json", "meta.json",
            "scores.json", "usage.csv", "raw-paths.txt"]


def check(out: Path) -> list[str]:
    missing = [f for f in REQUIRED if not (out / f).exists() or (out / f).stat().st_size == 0]
    info = json.loads((out / "meta.json").read_text()) if (out / "meta.json").exists() else {}
    if info.get("context") == "kept" and not (out / "prompts/handover.txt").exists():
        missing.append("prompts/handover.txt")
    if info.get("score_points"):  # score and roll back: one row per scoring point
        rows = (out / "horizon_scores.jsonl").read_text().splitlines() if (out / "horizon_scores.jsonl").exists() else []
        if len(rows) != len(info["score_points"]):
            missing.append(f"horizon scores ({len(rows)} of {len(info['score_points'])} points)")
    t = (out / "transcript.md").read_text() if (out / "transcript.md").exists() else ""
    if info.get("solve") is not False and "**Reasoning**" not in t:
        missing.append("reasoning in transcript")
    if info.get("solve") is not False and "**Tool call**" not in t:
        missing.append("tool calls in transcript")
    if (out / "usage.csv").exists():  # every call billed for reasoning must have its reasoning text stored
        with (out / "usage.csv").open() as fh:
            lost = [r["call"] for r in csv.DictReader(fh) if int(r["reasoning_tokens"] or 0) > 0 and int(r["reasoning_chars"] or 0) == 0]
        if lost:
            missing.append(f"reasoning text on model calls {','.join(lost[:10])}")
    if info.get("solve") is not False and "prompts/system.txt" not in missing:
        if not (out / "prompts/system.txt").read_text().strip():
            missing.append("system prompt text")
    return missing


def _score_text(p: dict) -> str:
    """One readable score per run, from the parsed index row."""
    if not p:
        return "?"
    parts = []
    if p.get("checks_total"):
        parts.append(f"{p.get('checks_passed')}/{p.get('checks_total')} checks")
    if p.get("bugfix_total"):
        parts.append(f"{p.get('bugfix_passed')}/{p.get('bugfix_total')} target tests")
    if p.get("answer_matches_recomputed") is not None:
        parts.append(f"answer {p.get('answer')!s:.20} ({'right' if p['answer_matches_recomputed'] else 'wrong'})")
    return "; ".join(parts) or str(p.get("verdict"))


def _usage_line(cfg: str, key: str) -> str:
    m = re.search(rf"^openrouter usage at {key}: (.+)$", cfg, re.M)
    return m.group(1).strip() if m else "?"


def write_label_index(label: str, out_root: Path, results: list[tuple[Path, list[str]]]) -> dict:
    """runs/<label>/README.md (what the batch was, its settings and one row per run) and summary.json,
    which the run registry's table is built from. Generated, so it is never edited by hand."""
    cfg = redact(_config_text(label))
    first = cfg.splitlines()[0] if cfg else ""
    purpose = (re.search(r"^purpose: (.+)$", cfg, re.M) or [None, "not recorded"])[1]
    args_line = (re.search(r"^policy args: (.*)$", cfg, re.M) or [None, "?"])[1]
    finished = (re.search(r"^finished=(\S+) ct_exit=(\S+)", cfg, re.M) or [None, "?", "?"])
    u0, u1 = _usage_line(cfg, "start"), _usage_line(cfg, "end")
    try:
        spend = f"${float(u1) - float(u0):.3f}"
    except ValueError:
        spend = "n/a"
    rows, calls_total, metas = [], 0, []
    for out, miss in results:
        meta = json.loads((out / "meta.json").read_text()) if (out / "meta.json").exists() else {}
        metas.append(meta)
        parsed = json.loads((out / "scores.json").read_text()).get("parsed") or {}
        with (out / "usage.csv").open() as fh:
            u = list(csv.DictReader(fh))
        calls_total += len(u)
        tin = sum(int(r["input_tokens"] or 0) for r in u)
        tout = sum(int(r["output_tokens"] or 0) for r in u)
        treas = sum(int(r["reasoning_tokens"] or 0) for r in u)
        rchars = sum(int(r["reasoning_chars"] or 0) for r in u)
        rel = out.relative_to(out_root / label).as_posix()
        ended = (meta.get("ended_by") or parsed.get("error") or "?").replace("|", "/")[:80]
        rows.append(f"| {meta.get('task', '?')} | [{rel}]({rel}/transcript.md) | {_score_text(parsed)} | {len(u)} | "
                    f"{meta.get('solver_tool_calls', '')} | {tin:,} / {tout:,} ({treas:,}) | "
                    f"{f'{rchars / treas:.2f}' if treas else '-'} | {ended} | "
                    f"{'complete' if not miss else 'MISSING ' + ', '.join(miss)} |")
    m0 = metas[0] if metas else {}
    summary = {
        "label": label, "purpose": purpose, "policy_args": args_line,
        "started": (re.search(r"started=(\S+)", first) or [None, "?"])[1], "finished": finished[1],
        "ct_exit": finished[2], "runs": len(results), "complete": sum(1 for _, m in results if not m),
        "model_calls": calls_total, "usage_start": u0, "usage_end": u1, "spend": spend,
        "solver_user": m0.get("solver_user", "?"), "dev_strip_env": m0.get("dev_strip_env", "?"),
        "test_db": m0.get("test_db", "?"), "harness_sha256": m0.get("harness_sha256", ""),
    }
    (out_root / label / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_root / label / "README.md").write_text(
        f"# {label}\n\n"
        "*Generated by `harness/export_run.py` from the raw data in WSL. Don't edit by hand: rerun the export.*\n\n"
        f"- **Purpose:** {purpose}\n"
        f"- **Ran:** {summary['started']} to {summary['finished']} (UTC), Control Tower exit {summary['ct_exit']}\n"
        f"- **Policy args:** `{args_line}`\n"
        f"- **Account and setup:** solver as `{summary['solver_user']}`, emptied for dev: "
        f"`{summary['dev_strip_env'] or '(nothing)'}`, test database: {summary['test_db']}\n"
        f"- **OpenRouter usage:** {u0} at start, {u1} at end ({spend}). Batches that overlap in time share this figure\n"
        f"- **Harness:** `power_v0.py` sha256 {summary['harness_sha256'][:12] or '?'}; every file's hash is in each run's `config.json`\n"
        f"- **Raw data (unredacted, outside the repository):** `{DATA}/evals/{label}/` (the `.eval` log, the source) and "
        f"`{DATA}/runs/{label}/` (snapshots, database exports)\n\n"
        "Each run's folder holds:\n"
        "- `transcript.md`: the prompts as sent, then every turn's full reasoning, tool call and output;\n"
        "- `prompts/`: `system.txt`, `first-user.txt`, and `handover.txt` for runs that continue a trajectory's chat;\n"
        "- `config.json`, `meta.json`, `scores.json` and `usage.csv`.\n\n"
        "**Record** is `complete` only if the record has:\n"
        "- every file;\n"
        "- a system prompt for runs with a solver;\n"
        "- the reasoning text for every model call billed for reasoning.\n\n"
        "**Reasoning chars/token** is the stored reasoning characters per billed reasoning token. About 4 means the reasoning came back in full.\n\n"
        "| Task | Run | Score | Model calls | Tool calls | Tokens in / out (reasoning) | Reasoning chars/token | How it ended | Record |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n")
    return summary


REG_START, REG_END = "<!-- new-runs:start -->", "<!-- new-runs:end -->"


def update_registry(out_root: Path) -> None:
    """Rebuild the run registry's table of runs made with the Nov 2 harness, from every summary.json."""
    reg = out_root / "runs-registry.md"
    if not reg.exists() or REG_START not in reg.read_text():
        return
    sums = [json.loads(p.read_text()) for p in out_root.glob("*/summary.json")]
    sums = sorted((s for s in sums if s.get("harness_sha256")), key=lambda s: s.get("started", ""))
    lines = ["| Label | Purpose | Account | Password emptied for dev | Runs (complete) | Model calls | Spend | Started (UTC) | Record |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {s['label']} | {s['purpose'].replace('|', '/')} | {s['solver_user']} | "
              f"{'yes' if s['dev_strip_env'] else 'no (old setup)'} | {s['runs']} ({s['complete']}) | {s['model_calls']} | "
              f"{s['spend']} | {s['started']} | [{s['label']}/README.md]({s['label']}/README.md) |" for s in sums]
    text = reg.read_text()
    a, b = text.index(REG_START) + len(REG_START), text.index(REG_END)
    reg.write_text(text[:a] + "\n" + "\n".join(lines) + "\n" + text[b:])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    out_root = Path(a.out)
    for label in a.labels:
        rows = {(r["sample_id"], r["epoch"]): r for r in rows_for_label(label)}
        results = []
        for log_path in sorted((DATA / "evals" / label).glob("*.eval")):
            log = read_eval_log(str(log_path))
            for s in log.samples or []:
                out = export_sample(label, log_path, log, s, rows.get((s.id, s.epoch)), out_root)
                miss = check(out)
                results.append((out, miss))
                if a.check:
                    print(f"{label} {out.relative_to(out_root)}: {'complete' if not miss else 'MISSING ' + ', '.join(miss)}")
        if results:
            write_label_index(label, out_root, results)
    update_registry(out_root)
