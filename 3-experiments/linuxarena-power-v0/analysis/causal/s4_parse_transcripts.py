"""Runs the parser in s4_parse_transcripts_lib.py over all runs and trajectories; writes out/features.json."""
from s4_parse_transcripts_lib import *

runs = load_runs()
turns = load_turns()
tasks = sorted(load_tc())

out = {"runs": {}, "traj": {}}
for a in ARMS:
    out["runs"][a] = {}
    for t in tasks:
        r = runs[(a, t)]
        p = EXP / r["run_path"] / "transcript.md"
        steps = parse_transcript(p)
        rows = []
        for row in turns[(a, t)]:
            fs = int(row["first_step"]) if row["first_step"] else None
            n = int(row["tool_calls"] or 0)
            srows = [steps[s] for s in range(fs, fs + n) if s in steps] if fs else []
            feat = features_for_turn(srows)
            feat["t"] = int(row["turn"])
            rows.append(feat)
        out["runs"][a][t] = rows

# trajectories: no turn mapping in turns.csv, so per step
for a, tr in TRAJ.items():
    d = next((EXP / "runs" / tr).glob("*/e1-*/transcript.md"))
    steps = parse_transcript(d)
    rows = []
    for s in sorted(steps):
        feat = features_for_turn([steps[s]])
        feat["step"] = s
        rows.append(feat)
    out["traj"][a] = rows
    print(a, tr, "steps", len(steps), "restarts", sum(1 for r in rows if r["restart"]), "files named", len({f for r in rows for f in r["files_named"]}), "tool output chars", sum(r["out_chars"] for r in rows))

write_json("features.json", out)
print("written")
