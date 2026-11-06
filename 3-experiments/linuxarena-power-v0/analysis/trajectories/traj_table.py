#!/usr/bin/env python3
"""One row per traj4-* trajectory: turns, tool calls, turns flagged by analysis/build_dataset.py's existing rule set, refusals,
and the scorer's verdict. Reuses build_dataset's parser and rules, and adds none. Counts only: no command, output or
reasoning text is written.

    python3 -I /mnt/c/.../linuxarena-power-v0/analysis/trajectories/traj_table.py

Writes analysis/trajectories/traj_table.json. Stdlib only; no environments, no paid calls.
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_dataset as bd  # noqa: E402

TASKS = ["rbac", "roles", "errors", "minio", "sharing", "deployenv"]
NOTES = ["none", "side", "lean", "blockers", "roadmap", "strong", "keep"]


def row(label):
    hits = sorted(glob.glob(str(bd.CACHE / "exp" / "runs" / label / "*" / "*" / "transcript.md")))
    if not hits:
        return {"missing": True}
    run = Path(hits[0]).parent
    a = bd.assemble(run, None)
    turns = a["turns"]
    flagged = [t["turn"] for t in turns if any(c["priv"] for c in t["calls"])]
    denied = [t["turn"] for t in turns if any(c["denied"] for c in t["calls"])]
    cats = Counter()
    for t in turns:
        for name in {p for c in t["calls"] for p in c["priv"]}:
            cats[name] += 1
    scores = json.loads((run / "scores.json").read_text()).get("parsed", {})
    return {"run": str(run.relative_to(bd.CACHE / "exp" / "runs")), "T": len(turns),
            "tool_calls": sum(len(t["calls"]) for t in turns), "flagged_turns": len(flagged),
            "flagged_share": round(len(flagged) / len(turns), 3) if turns else None,
            "first_flagged": flagged[0] if flagged else None, "last_flagged": flagged[-1] if flagged else None,
            "denied_turns": len(denied), "flag_categories": dict(cats), "verdict": scores.get("verdict"),
            "checks_passed": scores.get("checks_passed"), "checks_total": scores.get("checks_total"),
            "problems": a["problems"][:3]}


def main():
    table = {f"traj4-{t}-{n}": row(f"traj4-{t}-{n}") for t in TASKS for n in NOTES}
    (HERE / "traj_table.json").write_text(json.dumps(table, indent=1))
    for k, v in table.items():
        print(k.replace("traj4-", ""), v.get("T"), v.get("tool_calls"), v.get("flagged_turns"), v.get("flagged_share"),
              v.get("first_flagged"), v.get("last_flagged"), v.get("denied_turns"), v.get("verdict"), v.get("checks_passed"),
              v.get("checks_total"), len(v.get("problems") or []))


main()
