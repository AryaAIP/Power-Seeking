#!/usr/bin/env python3
"""The night's job queue (plans/night-plan.md). Starts jobs from ~/power-v0/queue/jobs.tsv in file order,
keeps at most MAX_ENVS environments busy, and starts nothing after the deadline (23:30 CST, Nov 2; set it before each use).
Runs inside WSL as root, in the background:  nohup python3 night_queue.py >/dev/null 2>&1 &

jobs.tsv: one job per line, tab-separated:  label <TAB> environments it uses <TAB> bash command
Lines starting with # are skipped. Append new jobs at any time; the file is re-read every 15 seconds.
Status: queue/status.tsv (label, state, start, end, exit code) and queue/queue.log. Each job's output is in
queue/logs/<label>.out. Touch queue/stop to start nothing more; queue/max_envs overrides MAX_ENVS, and queue/deadline
("YYYY-MM-DD HH:MM", Chicago time) overrides DEADLINE. Both files are re-read every 15 seconds.
"""

import datetime as dt
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import QUEUE as Q  # noqa: E402  (~/power-v0 is $POWER_V0_HOME)

CST = ZoneInfo("America/Chicago")
DEADLINE = dt.datetime(2026, 11, 2, 23, 30, tzinfo=CST)
MAX_ENVS = 8


def now() -> dt.datetime:
    return dt.datetime.now(CST)


def log(msg: str) -> None:
    with (Q / "queue.log").open("a") as fh:
        fh.write(f"{now():%H:%M:%S} {msg}\n")


def deadline() -> dt.datetime:
    if not (Q / "deadline").exists():
        return DEADLINE
    text = (Q / "deadline").read_text().strip()
    try:
        return dt.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=CST)
    except ValueError:
        log(f"queue/deadline {text!r} isn't YYYY-MM-DD HH:MM: using {DEADLINE:%Y-%m-%d %H:%M}")
        return DEADLINE


def main() -> None:
    (Q / "logs").mkdir(parents=True, exist_ok=True)
    running: dict[str, tuple[subprocess.Popen, int, str]] = {}
    finished: dict[str, tuple[str, str, str, int]] = {}
    log(f"queue started, deadline {deadline():%Y-%m-%d %H:%M}")
    max_envs = MAX_ENVS
    while True:
        try:  # a file caught mid-write reads as empty: keep the last cap
            max_envs = int((Q / "max_envs").read_text().strip()) if (Q / "max_envs").exists() else MAX_ENVS
        except ValueError:
            pass
        for label, (p, envs, t0) in list(running.items()):
            if p.poll() is not None:
                finished[label] = ("done", t0, f"{now():%H:%M:%S}", p.returncode)
                del running[label]
                log(f"done {label} exit={p.returncode}")
        jobs = []
        if (Q / "jobs.tsv").exists():
            for ln in (Q / "jobs.tsv").read_text().splitlines():
                if ln.strip() and not ln.startswith("#"):
                    parts = ln.split("\t", 2)
                    if len(parts) != 3 or not parts[1].strip().isdigit():
                        continue  # not a job line (e.g. a stray message): skip it rather than stop the queue
                    label, envs, cmd = parts
                    jobs.append((label, int(envs), cmd))
        stop = (Q / "stop").exists() or now() >= deadline()
        used = sum(e for _, e, _ in running.values())
        for label, envs, cmd in jobs:
            if stop or label in running or label in finished:
                continue
            if used + envs > max_envs:
                break  # keep the file's order: a big job is not overtaken by smaller ones behind it
            out = (Q / "logs" / f"{label}.out").open("w")
            p = subprocess.Popen(["bash", "-c", cmd], stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
            running[label] = (p, envs, f"{now():%H:%M:%S}")
            used += envs
            log(f"start {label} envs={envs} (in use {used}/{max_envs})")
        pending = [j[0] for j in jobs if j[0] not in running and j[0] not in finished]
        with (Q / "status.tsv").open("w") as fh:
            fh.write(f"# {now():%H:%M:%S} running={len(running)} envs={used}/{max_envs} pending={len(pending)} "
                     f"{'NO NEW STARTS' if stop else ''}\n")
            for label, (p, envs, t0) in running.items():
                fh.write(f"{label}\trunning\t{t0}\t\t\n")
            for label, (st, t0, t1, rc) in finished.items():
                fh.write(f"{label}\t{st}\t{t0}\t{t1}\t{rc}\n")
            for label in pending:
                fh.write(f"{label}\t{'not started (deadline)' if stop else 'pending'}\t\t\t\n")
        if stop and not running:
            log("nothing running and no new starts: queue exits")
            return
        time.sleep(15)


if __name__ == "__main__":
    main()
