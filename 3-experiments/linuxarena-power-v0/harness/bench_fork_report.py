"""The fork test's result (plans/scoring-efficiency-tests.md): each checkpoint's score on the second stack against the replaying
job's in-place score at the same turn, and against the existing record, from the exported records. Then what each
checkpoint and apply cost, and which fingerprint sections differed, from the bench logs in WSL. Prints check names, counts and
times only.
  python3 -I bench_fork_report.py A_LABEL B_LABEL [B_LABEL ...] [--record LABEL]
"""

import argparse
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_sr import check_list, differences  # noqa: E402
from power_paths import HOME, RUNS  # noqa: E402

MASK = re.compile(r"(?i)(pass|secret|token|key|credential)[^/ ,]*")


def rows_of(label: str) -> tuple[dict, dict | None, str]:
    f = next(RUNS.glob(f"{label}/*/*/horizon_scores.jsonl"), None)
    if f is None:
        return {}, None, ""
    end = f.parent / "scores.json"
    return ({r["H"]: r for r in map(json.loads, f.read_text().splitlines())},
            json.loads(end.read_text()) if end.exists() else None, f.parent.parent.name)


def log_of(label: str) -> list[dict]:
    p = HOME / "bench" / "logs" / f"{label}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("bs", nargs="+")
    ap.add_argument("--record")
    a = ap.parse_args()
    rows_a, end_a, task = rows_of(a.a)
    rows_rec = rows_of(a.record)[0] if a.record else {}
    alog = [x for x in log_of(a.a) if x.get("op") == "save_at"]
    print(f"{a.a} ({task}): {len(rows_a)} in-place points, {len(alog)} checkpoints")
    for x in alog:
        print(f"  H={x['H']}: checkpoint {x.get('save_seconds')} s (paused {x.get('paused_seconds')}), fingerprint {x.get('fingerprint_seconds')} s, "
              f"waited {x.get('wait_seconds')} s for {x.get('unsettled_at_turn_end')} unsettled ({x.get('still_unsettled')} still), sizes {x.get('sizes_mb')}, "
              f"entries {x.get('upper_entries')}, running binary differs: {x.get('running_binary_differs_from_file')}, "
              f"others: {[MASK.sub('<m>', o)[:60] for o in x.get('other_processes', [])]}")
    bad = 0
    for b in a.bs:
        rows_b, _, _ = rows_of(b)
        blog = {x["H"]: x for x in log_of(b) if x.get("op") == "fork_point"}
        print(f"\n{b}: {len(rows_b)} points")
        same_a, same_rec, n_rec = 0, 0, 0
        secs: dict = collections.defaultdict(list)
        secdiff: collections.Counter = collections.Counter()
        for h, r in sorted(rows_b.items()):
            lg = blog.get(h, {})
            for k, v in (lg.get("timing") or {}).items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and k.endswith("_seconds"):
                    secs[k].append(v)
            secs["apply"].append(lg.get("apply_seconds"))
            secs["fingerprint"].append(lg.get("fingerprint_seconds"))
            secs["score"].append(lg.get("score_seconds"))
            for sec in lg.get("vs_source") or {}:
                secdiff[sec] += 1
            ra = rows_a.get(h)
            ref = (ra or {}).get("scores") or (end_a if ra is None else None)
            line = f"  H={h}: "
            if not r.get("scores"):
                line += f"NO SCORE ({r.get('error')})"
                bad += 1
            elif ref:
                d = differences(check_list(ref), check_list(r["scores"]))
                same_a += not d
                bad += bool(d)
                line += ("same as in place" if not d else "DIFFERS from in place: " + "; ".join(d)[:400])
            else:
                line += "no in-place score"
            rec = rows_rec.get(h, {}).get("scores")
            if rec and r.get("scores"):
                n_rec += 1
                d = differences(check_list(rec), check_list(r["scores"]))
                same_rec += not d
                if d:
                    line += " | DIFFERS from record: " + "; ".join(d)[:300]
            bin_a = (ra or {}).get("bench_binary_sha256")
            print(MASK.sub("<m>", line) + f" | apply {lg.get('apply_seconds')} s, score {lg.get('score_seconds')} s, fingerprint equal {lg.get('state_equal')}, "
                  f"sections {sorted(lg.get('vs_source') or {})}, used running binary {(lg.get('timing') or {}).get('used_running_binary')}, delta {(lg.get('timing') or {}).get('delta')}")
        print(f"  identical to in place at {same_a} of {len(rows_b)}; to the record at {same_rec} of {n_rec}. Differences so far in this report: {bad}")
        print("  median seconds: " + ", ".join(f"{k} {med(v)}" for k, v in secs.items()))
        print(f"  points whose fingerprint differed, by section: {secdiff.most_common()}")
        shown: dict = {}
        for h, lg in sorted(blog.items()):
            for sec, d in (lg.get("vs_source") or {}).items():
                for name in d.get("first", []):
                    shown.setdefault(sec, collections.Counter())[re.sub(r"[0-9a-f]{12,}", "<hex>", MASK.sub("<m>", name))[:80]] += 1
        for sec, c in shown.items():
            print(f"    {sec}: {c.most_common(10)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
