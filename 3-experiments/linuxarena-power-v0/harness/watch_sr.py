#!/usr/bin/env python3
"""Watch a score-and-roll-back production queue, printing one line per thing someone would act on (for a Monitor).

For each job that finishes, it runs compare_sr.py and prints a line only if something is wrong: no record (with the kind
of failure, never the job's output), missing points, a pair or an end score that differs, a dedup audit that differs, or
a restore that wasn't exact. It also prints each fifth of the runs complete, when the first pass of full-audit jobs ends,
gate decisions that aren't passes, the queue stopping, and a machine short of memory or Docker networks. It remembers
what it has reported in sr-validate/watch-seen.json, so it can be restarted. Stops after --minutes:
  python3 -I -u watch_sr.py --minutes 29
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import HOME, QUEUE, RUNS  # noqa: E402

STATE = HOME / "sr-validate" / "watch-seen.json"
TOTAL_RUNS = 130
NETWORKS_NEAR_FULL = 32  # as `docker network ls` counts: Docker's 3 defaults, then the pool of 31, one stack using 2
FAILURES =(("mount namespace", "Control Tower's probe of the internet simulator timed out"),
            ("address pools", "Docker's network pool is full"), ("Cannot connect to the Docker daemon", "Docker isn't up"),
            ("already used", "launch.sh refused the label"), ("Traceback", "a Python error in the job"))


def base(label: str) -> str:
    return re.sub(r"-r\d+$", "", label)


def read_status() -> tuple[dict, str]:
    status, head = {}, ""
    for ln in (QUEUE / "status.tsv").read_text().splitlines():
        if ln.startswith("#"):
            head = ln
        else:
            f = ln.split("\t")
            if len(f) >= 2:
                status[f[0]] = f
    return status, head


def seed() -> dict:
    """The runs complete before this queue started: from the status files saved at each resume."""
    runs = set()
    for f in QUEUE.glob("status.tsv.before-resume-*"):
        for ln in f.read_text().splitlines():
            p = ln.split("\t")
            if len(p) >= 2 and p[1] == "done" and p[0].startswith("sr-"):
                runs.add(base(p[0]))
    return {"reported": [], "runs": sorted(runs), "gate": 0, "first_pass_said": False, "marks": len(runs) // (TOTAL_RUNS // 5)}


def failure_kind(label: str) -> str:
    out = QUEUE / "logs" / f"{label}.out"
    text = out.read_text(errors="replace") if out.exists() else ""
    return next((why for pat, why in FAILURES if pat in text), "cause not recognised")


def check(label: str, exit_code: str) -> tuple[list[str], bool]:
    """(problems, did the job leave a record)."""
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("compare_sr.py")), label, "--json", tmp.name],
                       capture_output=True, text=True, check=False)
        text = Path(tmp.name).read_text()
    jobs = json.loads(text) if text.strip() else []
    if not jobs:
        return [f"no record, exit {exit_code}: {failure_kind(label)}"], False
    out = []
    for j in jobs:
        if j["points"] < j["planned_points"]:
            out.append(f"{j['points']} of {j['planned_points']} points")
        diff = [p["H"] for p in j["pairs"] if not p["same"]]
        if diff:
            out.append(f"pairs differ at H = {sorted(set(diff))}")
        if not j.get("end", {}).get("same", True):
            out.append("end score differs from the run's own")
        aud = [a for a in j.get("dedup_audits", []) if not a["same"]]
        if aud:  # the checks that came out differently on the same machine, by name
            names = sorted({m for a in aud for d in a["differences"] for m in re.findall(r"(\w+): \S+ vs ", d)})
            out.append(f"same machine, different score at H = {[a['H'] for a in aud]} (of {len(j['dedup_audits'])} audits)"
                       + (f": {', '.join(names)}" if names else ""))
        inexact = [s["H"] for s in j["state"] if not s["state_equal"]]
        if inexact:
            out.append(f"restores not exact after H = {inexact}")
    return out, True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=29)
    a = ap.parse_args()
    seen = json.loads(STATE.read_text()) if STATE.exists() else seed()
    t_end = time.time() + a.minutes * 60
    while time.time() < t_end:
        status, head = read_status()
        for label, f in status.items():
            if f[1] != "done" or label in seen["reported"] or not label.startswith("sr-"):
                continue
            problems, record = check(label, f[4] if len(f) > 4 else "?")
            seen["reported"].append(label)
            if record and base(label) not in seen["runs"]:
                seen["runs"].append(base(label))
            if problems:
                print(f"{time.strftime('%H:%M')} {label}: " + "; ".join(problems), flush=True)
            n = len(seen["runs"])
            if n // (TOTAL_RUNS // 5) > seen["marks"]:
                seen["marks"] = n // (TOTAL_RUNS // 5)
                print(f"{time.strftime('%H:%M')} MILESTONE {n} of {TOTAL_RUNS} runs complete", flush=True)
        gate = (QUEUE / "dedup_gate.log").read_text().splitlines() if (QUEUE / "dedup_gate.log").exists() else []
        for ln in gate[seen["gate"]:]:
            if "differ" in ln or "not exact" in ln or "no record" in ln:
                print(f"gate: {ln[11:]}", flush=True)
        seen["gate"] = len(gate)
        audit = [ln.split("\t", 1)[0] for ln in (QUEUE / "jobs.tsv").read_text().splitlines()
                 if "-p score_dedup_audit_every=1" in ln and not ln.startswith("#")]
        if audit and not seen["first_pass_said"] and all(status.get(x, [0, ""])[1] == "done" for x in audit):
            seen["first_pass_said"] = True
            print(f"{time.strftime('%H:%M')} FIRST PASS done: all {len(audit)} full-audit jobs finished", flush=True)
        if subprocess.run(["pgrep", "-f", "night_queue.py"], capture_output=True).returncode:
            print(f"{time.strftime('%H:%M')} QUEUE NOT RUNNING: {head}", flush=True)
            STATE.write_text(json.dumps(seen))
            return
        nets = int(subprocess.run("docker network ls -q | wc -l", shell=True, capture_output=True, text=True).stdout or 0)
        avail = int(re.search(r"MemAvailable:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1)) // 1024 ** 2
        short = nets > NETWORKS_NEAR_FULL or avail < 2
        if short and not seen.get("short"):  # once per crossing
            print(f"{time.strftime('%H:%M')} MACHINE: {nets} Docker networks, {avail} GB memory available", flush=True)
        seen["short"] = short
        STATE.write_text(json.dumps(seen))
        time.sleep(45)


if __name__ == "__main__":
    main()
