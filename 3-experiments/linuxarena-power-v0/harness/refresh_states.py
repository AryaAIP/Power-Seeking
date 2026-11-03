#!/usr/bin/env python3
"""Keep saved trajectory states fresh while the queue runs jobs that restore them (plans/replay-free-scope.md, §8 item 5).

A state must be restored within about a day of its save: the service's backup worker treats backups more than a day
old as missing and makes new ones, and the trajectory's tokens last 24 hours. Every 5 minutes this:
  - finds the states that pending lines of queue/jobs.tsv restore (-p restore_state=NAME);
  - for one older than --max-age hours (default 18), with no re-save under way, puts a save job before the first
    pending line: restorecheck-resave-<NEW>, which replays the same trajectory (its traj=, traj_user= and traj_cmd_bug=
    come from those lines) and saves it as NEW = <base>-r2, -r3, ...;
  - once that save is complete, points the pending lines at NEW. Lines already started keep their state.
It writes jobs.tsv by renaming a new copy over it, so night_queue.py never reads half a file. Logs to
queue/refresh_states.log. Runs in WSL as root, alongside night_queue.py:
  nohup python3 refresh_states.py [--max-age 18] [--dry-run] >/dev/null 2>&1 &
It exits when no pending line restores a state.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import DATA, LAUNCH, QUEUE  # noqa: E402

STATES = DATA / "states"
ARG = re.compile(r"-p (traj|traj_user|traj_cmd_bug|restore_state)=(\S+)")


def log(msg: str) -> None:
    with (QUEUE / "refresh_states.log").open("a") as fh:
        fh.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def read_queue() -> tuple[list[str], dict]:
    lines = (QUEUE / "jobs.tsv").read_text().splitlines(keepends=True)
    status = {}
    if (QUEUE / "status.tsv").exists():
        for ln in (QUEUE / "status.tsv").read_text().splitlines():
            f = ln.split("\t")
            if len(f) >= 2 and not ln.startswith("#"):
                status[f[0]] = f[1]
    return lines, status


def pending(ln: str, status: dict) -> bool:
    if not ln.strip() or ln.startswith("#") or "\t" not in ln:
        return False
    return status.get(ln.split("\t", 1)[0], "pending") in ("pending", "not started (deadline)")


def write_queue(lines: list[str]) -> None:
    tmp = QUEUE / "jobs.tsv.refresh"
    tmp.write_text("".join(lines))
    os.replace(tmp, QUEUE / "jobs.tsv")


def age_hours(name: str) -> float | None:
    m = STATES / name / "manifest.json"
    if not m.exists():
        return None
    saved = json.loads(m.read_text()).get("saved")
    return (dt.datetime.now(dt.timezone.utc) - dt.datetime.strptime(saved, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc)).total_seconds() / 3600


def complete(name: str) -> bool:
    m = STATES / name / "manifest.json"
    return m.exists() and json.loads(m.read_text()).get("complete") is True


def next_name(name: str) -> str:
    base = re.sub(r"-r\d+$", "", name)
    n = 2
    while (STATES / f"{base}-r{n}").exists():
        n += 1
    return f"{base}-r{n}"


def step(max_age: float, dry: bool, under_way: dict) -> bool:
    """One pass. Returns False when no pending line restores a state any more."""
    lines, status = read_queue()
    for old, new in list(under_way.items()):  # a re-save finished: switch the pending lines to it
        label = f"restorecheck-resave-{new}"
        if status.get(label) == "done":
            if complete(new):
                pat = re.compile(rf"-p restore_state={re.escape(old)}(?=\s|$)")
                out, n = [], 0
                for ln in lines:
                    if pending(ln, status) and pat.search(ln):
                        ln, k = pat.subn(f"-p restore_state={new}", ln)
                        n += k
                    out.append(ln)
                if not dry:
                    write_queue(out)
                log(f"{new} saved; {n} pending lines now restore it instead of {old}")
                lines = out
            else:
                log(f"ERROR: the re-save {label} finished but {new} is incomplete; {old} stays in use")
            del under_way[old]
    uses: dict[str, dict] = {}  # after any switch, so a state just replaced isn't re-saved again
    for ln in lines:
        if pending(ln, status):
            a = dict(ARG.findall(ln))
            if "restore_state" in a:
                uses.setdefault(a["restore_state"], a)
    if not uses and not under_way:
        return False
    for name, a in sorted(uses.items()):
        age = age_hours(name)
        if age is None or age < max_age or name in under_way:
            continue
        new = next_name(name)
        label = f"restorecheck-resave-{new}"
        cmd = (f'PURPOSE="Re-save {a["traj"].rsplit("/", 1)[-1][:-5]}\'s end state as {new}: pending jobs would restore '
               f'{name} {age:.0f} h after its save" bash {LAUNCH} {label} tasks/one_model_favoriting_system.txt 1 '
               f"-p solver_user=dev -p traj={a['traj']} -p traj_user={a.get('traj_user', 'dev')} "
               f"-p traj_cmd_bug={a.get('traj_cmd_bug', 'false')} -p solve=false -p save_state={new}")
        first = next(i for i, ln in enumerate(lines) if pending(ln, status))
        lines = lines[:first] + [f"{label}\t1\t{cmd}\n"] + lines[first:]
        if not dry:
            write_queue(lines)
        under_way[name] = new
        log(f"{name} is {age:.1f} h old: queued {label} before the first pending line" + (" (dry run)" if dry else ""))
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=float, default=18.0, help="hours after its save at which a state is re-saved")
    ap.add_argument("--dry-run", action="store_true", help="log what would be done, once, without changing jobs.tsv")
    ap.add_argument("--every", type=int, default=300, help="seconds between passes")
    a = ap.parse_args()
    under_way: dict = {}
    log(f"started: re-save states older than {a.max_age} h" + (" (dry run)" if a.dry_run else ""))
    while step(a.max_age, a.dry_run, under_way) and not a.dry_run:
        time.sleep(a.every)
    log("no pending line restores a state: exiting" if not a.dry_run else "dry run done")


if __name__ == "__main__":
    main()
