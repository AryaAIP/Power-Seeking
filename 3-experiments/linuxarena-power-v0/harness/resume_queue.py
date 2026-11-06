#!/usr/bin/env python3
"""Resume a drained production queue. A plain restart of night_queue.py would be wrong: it keeps its list of finished
jobs in memory, so it would try every finished line again (launch.sh refuses them, but their logs get overwritten), and a
saved state may be too old by now (refresh_states.py says why). This:
  1. refuses if a queue is running, or if status.tsv lists a job as still running;
  2. backs up status.tsv and queue.log, and comments out the finished lines of jobs.tsv;
  3. re-saves every state that pending lines restore and that is at least --max-age hours old, waits for those saves, and
     points the pending lines at the new states, so that no job starts from an old state;
  4. sets queue/deadline and queue/max_envs, then starts refresh_states.py and night_queue.py, detached.
Runs in WSL as root, detached, since re-saves can take half an hour:
  setsid nohup python3 resume_queue.py [--deadline "YYYY-MM-DD HH:MM"] [--cap 7] >> <queue>/resume.log 2>&1 < /dev/null &
--dry-run says what it would do and changes nothing. --no-start does steps 1, 2 and 4's files and starts nothing (for tests).
The deadline defaults to queue/deadline.before-drain.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_states as rs  # noqa: E402
from power_paths import LAUNCH, QUEUE  # noqa: E402


def say(msg: str) -> None:
    print(f"{time.strftime('%F %T')} {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", help='"YYYY-MM-DD HH:MM", Chicago time; default: queue/deadline.before-drain')
    ap.add_argument("--cap", type=int, default=7)
    ap.add_argument("--max-age", type=float, default=18.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-start", action="store_true")
    a = ap.parse_args()
    here = Path(__file__).resolve().parent

    if not a.no_start and subprocess.run(["pgrep", "-f", "night_queue.py"], capture_output=True).returncode == 0:
        say("a queue is already running: nothing done")
        return 1
    lines, status = rs.read_queue()
    stale_running = [k for k, v in status.items() if v == "running"]
    if stale_running:
        say(f"status.tsv lists jobs as running: {stale_running}. Check them first: nothing done")
        return 1
    deadline = a.deadline or (QUEUE / "deadline.before-drain").read_text().strip()
    if not re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", deadline):
        say(f"bad deadline {deadline!r}: nothing done")
        return 1
    done = {k for k, v in status.items() if v == "done"}
    pending = [ln for ln in lines if rs.pending(ln, status)]
    uses: dict[str, dict] = {}
    for ln in pending:
        args = dict(rs.ARG.findall(ln))
        if "restore_state" in args:
            uses.setdefault(args["restore_state"], args)
    ages = {n: rs.age_hours(n) for n in uses}
    stale = [n for n, age in ages.items() if age is None or age >= a.max_age]
    say(f"{len(done)} jobs done, {len(pending)} pending; deadline {deadline}, cap {a.cap}")
    say("state ages (h): " + ", ".join(f"{n} {'missing' if v is None else f'{v:.1f}'}" for n, v in sorted(ages.items())))
    say(f"to re-save first: {stale or 'none'}")
    if a.dry_run:
        say("dry run: nothing changed")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    for f in ("status.tsv", "queue.log"):
        if (QUEUE / f).exists():
            shutil.copy2(QUEUE / f, QUEUE / f"{f}.before-resume-{stamp}")
    lines = [f"# done before the resume: {ln}" if not ln.startswith("#") and ln.split("\t", 1)[0] in done else ln for ln in lines]
    rs.write_queue(lines)

    if stale and not a.no_start:
        procs = {}
        for name in stale:
            args, new = uses[name], rs.next_name(name)
            label = f"restorecheck-resave-{new}"
            cmd = ["bash", str(LAUNCH), label, "tasks/one_model_favoriting_system.txt", "1", "-p", "solver_user=dev",
                   "-p", f"traj={args['traj']}", "-p", f"traj_user={args.get('traj_user', 'dev')}",
                   "-p", f"traj_cmd_bug={args.get('traj_cmd_bug', 'false')}", "-p", "solve=false", "-p", f"save_state={new}"]
            env = {**os.environ, "PURPOSE": f"Re-save {name} as {new} before resuming the queue: it was {ages[name] or 0:.0f} h old"}
            log = (QUEUE / "logs" / f"{label}.out").open("w")
            procs[name] = (new, subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT))
            say(f"re-saving {name} as {new}")
        for name, (new, p) in procs.items():
            p.wait()
            if not rs.complete(new):
                say(f"the re-save of {name} as {new} is incomplete: stopping, queue not started")
                return 1
            pat = re.compile(rf"-p restore_state={re.escape(name)}(?=\s|$)")
            lines, status = rs.read_queue()
            lines = [pat.sub(f"-p restore_state={new}", ln) if rs.pending(ln, status) else ln for ln in lines]
            rs.write_queue(lines)
            say(f"{new} saved; pending lines now restore it")
    (QUEUE / "deadline").write_text(deadline + "\n")
    (QUEUE / "max_envs").write_text(f"{a.cap}\n")
    if a.no_start:
        say("no start: files written, nothing started")
        return 0
    for script, extra in (("refresh_states.py", ["--max-age", str(a.max_age)]), ("night_queue.py", [])):
        subprocess.Popen([sys.executable, str(here / script), *extra], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, cwd=str(here))
    say("refresh_states.py and night_queue.py started")
    return 0


if __name__ == "__main__":
    sys.exit(main())
