"""Put score and roll back's every-turn scores on the results pages, keeping each pair's arms at the same density.

Runs in WSL as root:  python3 -I harness/vm/sync_rollback_pages.py [--dry-run] [--both-only]
For each page (viz/run-v4-both.json, the main one; viz/run-v4.json; viz/run-v4b.json), a task's sr-* jobs are used
only once all that page's arms have an exported job for it and none is pending or running; every other sr-* label is
left out for that build through POWER_EXTRA_EXCLUDED (power_horizons.py). So an interim page never compares an
every-turn arm with an every-5-turn one. Then, per page: power_horizons.py --reward <config's> --rollback-rows -> the
findings tables, and build_dashboard.py --config (its "rollback_rows": true passes --rollback-rows). Prints the tasks
included per page.
Publishing the pages is a separate step (the Artifact tool, by a Claude session).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EXP = Path(__file__).resolve().parents[2]
RUNS = EXP / "runs"
LABEL = re.compile(r"^sr-v4-(before|afterA2|afterB2|afterA|afterB)-p\d+-(.+?)(-r\d+)?$")
PAIRS = [("both pairs", "viz/run-v4-both.json", "findings/both"), ("pair 1", "viz/run-v4.json", "findings"),
         ("pair 2", "viz/run-v4b.json", "findings/v4b")]


def unfinished() -> set:
    """{(arm, task short)} with an sr-* job still pending or running in the queue (e.g. a rescore of later points)."""
    st = Path(os.environ.get("POWER_V0_HOME", "/root/power-v0")) / "queue" / "status.tsv"
    out = set()
    for ln in (st.read_text().splitlines() if st.exists() else []):
        f = ln.split("\t")
        m = LABEL.match(f[0]) if len(f) > 1 and f[1] in ("pending", "running") else None
        if m:
            out.add((m.group(1), m.group(2)))
    return out


def exported() -> dict:
    """{(arm, task short): [labels]} for sr-* labels with an exported run record (meta.json and scores), leaving out
    any (arm, task) that still has a job pending or running."""
    out: dict = {}
    busy = unfinished()
    for d in sorted(RUNS.glob("sr-v4-*")):
        m = LABEL.match(d.name)
        if m and (m.group(1), m.group(2)) not in busy and any(d.glob("*/*/meta.json")) \
                and any(d.glob("*/*/horizon_scores.jsonl")):
            out.setdefault((m.group(1), m.group(2)), []).append(d.name)
    return out


def arms_of(cfg: dict) -> list:
    """The config's arms as sr label words: before, and each after arm's batch name without -p<k>."""
    words = ["before"]
    for k in cfg["afters"]:
        first = cfg["afters"][k][0].split(",")[0]  # e.g. v4-afterA2-p1
        words.append(re.match(r"v4-(\w+)-p\d+", first).group(1))
    return words


def main() -> None:
    dry = "--dry-run" in sys.argv
    only_both = "--both-only" in sys.argv  # an interim sync: just the main page (each build takes a while under load)
    have = exported()
    all_sr = sorted(d.name for d in RUNS.glob("sr-v4-*"))
    for name, cfg_path, out_dir in PAIRS:
        if only_both and name != "both pairs":
            continue
        cfg = json.loads((EXP / cfg_path).read_text())
        arms = arms_of(cfg)
        shorts = {t for (_, t) in have}
        complete = sorted(t for t in shorts if all((a, t) in have for a in arms))
        keep = {lab for t in complete for a in arms for lab in have[(a, t)]}
        leave_out = [lab for lab in all_sr if lab not in keep]
        print(f"{name}: arms {arms}; {len(complete)} task(s) rescored in all three: {', '.join(complete) or '-'}")
        if dry:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("\n".join(leave_out) + "\n")
            extra = fh.name
        env = {**os.environ, "POWER_EXTRA_EXCLUDED": extra}
        ph = ["--before", cfg["before"][0], "--nowork-before", cfg["before"][1]]
        for k, (lab, nw) in cfg["afters"].items():
            ph += ["--after", f"{k}={lab}", "--nowork-after", f"{k}={nw}"]
        ph += ["--reward", cfg.get("reward", "first-pass"), "--rollback-rows"]
        od = EXP / out_dir
        od.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable, "-I", str(EXP / "harness/power_horizons.py"), *ph, "--json",
                            str(od / "power-horizons-v4.json")], env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{name}: power_horizons.py failed: {r.stderr[-400:]}")
        (od / "power-horizons-v4.txt").write_text(f"# python3 harness/power_horizons.py {' '.join(ph)} "
                                                  f"(score and roll back rows for {len(complete)} task(s): "
                                                  f"{', '.join(complete)})\n{r.stdout}\n# notes and warnings (stderr):\n{r.stderr}")
        b = subprocess.run([sys.executable, "-I", "build_dashboard.py", "--config", str(EXP / cfg_path)],
                           cwd=EXP / "viz", env=env, capture_output=True, text=True)
        lines = [ln for ln in (b.stdout + b.stderr).splitlines()
                 if re.search(r"values compared|comparisons|^written|template text|Traceback|Error", ln)]
        print("\n".join(f"  {ln[:200]}" for ln in lines))
        if b.returncode:
            sys.exit(f"{name}: build_dashboard.py failed (exit {b.returncode})")
        os.unlink(extra)


if __name__ == "__main__":
    main()
