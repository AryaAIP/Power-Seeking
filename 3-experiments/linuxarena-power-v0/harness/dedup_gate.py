#!/usr/bin/env python3
"""State dedup's gate: score_dedup goes on for a task only after that task's own full audit passed.

A full-audit job (-p score_dedup_audit_every=1) scores every point, including those whose machine is exactly as the last
scored point's, and compare_sr.py checks each such pair. Every minute this looks at the finished ones. A task passes if
its audit job has at least --min-audits such points, every one scored the same, and every restore was exact. Then its
pending lines get -p score_dedup=true (every 5th such point is still scored, as a running check). A task that fails, or
that has too few such points, stays off and scores every point. Lines already started keep what they have. Rescore lines
(score_at) are left alone. Logs to queue/dedup_gate.log, and stops when no audit job is pending or running.
Runs in WSL as root, beside night_queue.py:  setsid nohup python3 dedup_gate.py [--min-audits 2] >/dev/null 2>&1 < /dev/null &
--once does one pass; --dry-run also changes nothing.
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_states as rs  # noqa: E402
from power_paths import QUEUE  # noqa: E402

TASK = re.compile(r"tasks/(\S+)\.txt")
AUDIT = "-p score_dedup_audit_every=1"


def log(msg: str) -> None:
    with (QUEUE / "dedup_gate.log").open("a") as fh:
        fh.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def decide(jobs: list[dict], min_audits: int) -> tuple[bool, str]:
    """From compare_sr.py's report on one audit job: (does the task pass, why)."""
    if not jobs:
        return False, "no record of the job"
    audits = [au for job in jobs for au in job.get("dedup_audits", [])]
    differ = [au["H"] for au in audits if not au["same"]]
    if differ:
        return False, f"audits differ at H = {differ}"
    inexact = [s["H"] for job in jobs for s in job["state"] if not s["state_equal"]]
    if inexact:
        return False, f"restores not exact after H = {inexact}"
    if len(audits) < min_audits:
        return False, f"only {len(audits)} points in the same state as the last scored one"
    return True, f"{len(audits)} of {len(audits)} audits identical"


def switch_on(line: str) -> str:
    """A pending line with dedup on, at the default audit rate. Rescores, and lines that already say, are unchanged."""
    if "score_dedup" in line or "-p score_at=" in line:
        return line
    return line.rstrip("\n") + " -p score_dedup=true\n"


def task_of(line: str) -> str | None:
    m = TASK.search(line)
    return m.group(1) if m else None


def report_on(label: str) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("compare_sr.py")), label, "--json", tmp.name],
                       capture_output=True, text=True, check=False)
        text = Path(tmp.name).read_text()
    return json.loads(text) if text.strip() else []


def step(min_audits: int, dry: bool, seen: dict) -> bool:
    """One pass. Returns False when no audit job is pending or running."""
    lines, status = rs.read_queue()
    waiting = False
    for ln in lines:
        if ln.startswith("#") or AUDIT not in ln or "\t" not in ln:
            continue
        label = ln.split("\t", 1)[0]
        st = status.get(label, "pending")
        if st != "done":
            waiting = True
            continue
        if label in seen:
            continue
        ok, why = decide(report_on(label), min_audits)
        seen[label] = ok
        task = task_of(ln)
        n = 0
        if ok:
            out = []
            for other in lines:
                if rs.pending(other, status) and task_of(other) == task and AUDIT not in other:
                    new = switch_on(other)
                    n += new != other
                    other = new
                out.append(other)
            lines = out
            if n and not dry:
                rs.write_queue(lines)
        log(f"{label} ({task}): {'PASS' if ok else 'stays off'}: {why}; {n} pending lines switched on"
            + (" (dry run)" if dry else ""))
    return waiting


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-audits", type=int, default=2)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    seen: dict = {}
    log(f"started: at least {a.min_audits} audits per task" + (" (dry run)" if a.dry_run else ""))
    while step(a.min_audits, a.dry_run, seen) and not a.once:
        time.sleep(60)
    log("one pass done" if a.once else "no audit job left: exiting")


if __name__ == "__main__":
    main()
