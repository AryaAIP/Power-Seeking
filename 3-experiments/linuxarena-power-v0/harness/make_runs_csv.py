"""Write one CSV row per run for the dashboard, from index.csv and each run's meta.json.

Usage (in WSL):  .venv/bin/python ~/power-v0/harness/make_runs_csv.py <before-label> <after-label> <out.csv>
Also includes the no-work runs (check0b2 = untouched state, check0e = replayed state) as zero-work rows.

score is in [0, 1] with the untouched state's free passes removed (see power.py), so a no-work run
on the untouched state scores 0, and any zero-work gain on the replayed state shows as a score above 0.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from power import free_shares, load, num, raw_score, score  # noqa: E402
from power_paths import DATA  # noqa: E402
SHORT = {
    "migrate_backup_records_to_sqlite": "Backup records to SQLite",
    "model_favoriting_system": "Model favourites",
    "untracked_s3_objects_total_bytes": "Untracked storage bytes (question)",
    "jwt_claims_wrong_field": "JWT claims bug fix",
    "model_registry_health_dashboard_data": "Health dashboard",
    "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern": "Repository refactor (overlap probe)",
}
POWER = {
    "migrate_backup_records_to_sqlite": "Network and dependencies",
    "model_favoriting_system": "App access control",
    "untracked_s3_objects_total_bytes": "Data",
    "jwt_claims_wrong_field": "Network and dependencies",
    "model_registry_health_dashboard_data": "Oversight and audit",
    "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern": "Tools and infrastructure",
}
KIND = lambda r: ("test suite" if num(r["bugfix_total"]) else "answer" if r["answer_matches_recomputed"] not in ("", "None") else "check list")


def main(before: str, after: str, out: Path, free_before: str = "check0b2", free_after: str = "check0e"):
    rows = load(DATA / "index.csv")
    free = free_shares(rows, free_before)
    arms = {before: "before", after: "after", free_before: "no work, before", free_after: "no work, after"}
    outrows = []
    for r in rows:
        if r["label"] not in arms or r["task"] not in SHORT:
            continue
        meta = {}
        if r["run_dir"] and Path(r["run_dir"], "meta.json").exists():
            meta = json.loads(Path(r["run_dir"], "meta.json").read_text())
        s, raw = score(r, free), raw_score(r)
        steps = num(r["solver_steps"])
        outrows.append({
            "run": f"{arms[r['label']]} / {SHORT[r['task']]} / {r['epoch']}",
            "arm": arms[r["label"]],
            "task": SHORT[r["task"]],
            "power_kind": POWER[r["task"]],
            "scorer": KIND(r),
            "rollout": int(r["epoch"]),
            "score": round(s, 4) if s is not None else "",
            "raw_share": round(raw, 4) if raw is not None else "",
            "free_share": round(free.get(r["task"], 0.0), 4) if KIND(r) == "check list" else 0,
            "checks_passed": r["checks_passed"] or r["bugfix_passed"] or "",
            "checks_total": r["checks_total"] or r["bugfix_total"] or "",
            "answer": r["answer"] if r["answer"] not in ("None",) else "",
            "answer_on_this_state": r["answer_recomputed"] if r["answer_recomputed"] not in ("None",) else "",
            "steps": int(steps) if steps is not None else "",
            "input_tokens": int(num(r.get("input_tokens")) or 0),
            "cached_input_tokens": int(num(r.get("input_tokens_cache_read")) or 0),
            "output_tokens": int(num(r.get("output_tokens")) or 0),
            "solver_minutes": round((meta.get("solver_seconds") or 0) / 60, 1),
            "replay_minutes": round((meta.get("replay_seconds") or 0) / 60, 1),
            "run_minutes": round(num(r["total_time_s"]) / 60, 1) if num(r["total_time_s"]) else "",
            "context": meta.get("context") or "",
            "ended_by": meta.get("ended_by") or "",
            "scorer_verdict": r["verdict"],
        })
    outrows.sort(key=lambda x: (["before", "after", "no work, before", "no work, after"].index(x["arm"]), x["task"], x["rollout"]))
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(outrows[0].keys()))
        w.writeheader()
        w.writerows(outrows)
    print(f"{len(outrows)} rows -> {out}")


if __name__ == "__main__":
    # usage: make_runs_csv.py <before> <after> <out.csv> [<no-work before label> <no-work after label>]
    main(sys.argv[1], sys.argv[2], Path(sys.argv[3]), *sys.argv[4:6])
