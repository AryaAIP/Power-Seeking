"""Which paths separate a turn from the last scored point (plans/scoring-efficiency-tests.md): reads the bench log's dedup
misses (bench.py's dedup_detail), the job's exported rows, and schedule_error.py's read-only call on the source run's turns.
Prints names, counts and what differs: no contents, and any secret-looking name part is masked.
  python3 -I bench_dedup_report.py LABEL [LABEL ...] [--ignore PREFIX ...] [--json out.json]
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_error as se  # noqa: E402
from compare_sr import check_list, differences  # noqa: E402
from power_paths import HOME, RUNS  # noqa: E402

MASK = re.compile(r"(?i)(pass|secret|token|key|credential)[^/ ]*")


def bucket(path: str) -> str:
    """A path's group: Go's cache folders by name, otherwise its first three folders."""
    m = re.match(r"((?:root|home/\w+)/\.cache/[\w-]+)/", path)
    if m:
        return m.group(1) + "/*"
    parts = path.split("/")
    return "/".join(parts[:3]) + ("/*" if len(parts) > 3 else "")


def outcome(r: dict) -> str:
    if r.get("same_state_as") is not None or r.get("dedup_audit_of") is not None:
        return "same"
    why = r.get("dedup_differs")
    if not why:
        return "first or no check"
    if "paths changed" in why:
        return "paths"
    if why.startswith("summary"):
        return "summary"
    return why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--ignore", nargs="*", default=[], help="path prefixes treated as bookkeeping for the what-if count")
    ap.add_argument("--json")
    a = ap.parse_args()
    all_rows = []
    for label in a.labels:
        for f in sorted(RUNS.glob(f"{label}/*/*/horizon_scores.jsonl")):
            task = f.parent.parent.name
            meta = json.loads((f.parent / "meta.json").read_text())
            src = Path(meta["args"]["prefix_log"]).parent.name
            classes, _ = se.turn_classes(next(RUNS.glob(f"{src}/{task}/*/transcript.md")).parent)
            misses = {}
            log = HOME / "bench" / "logs" / f"{label}.jsonl"
            for ln in log.read_text().splitlines():
                x = json.loads(ln)
                if x.get("op") == "dedup_miss":
                    misses[x["H"]] = x
            last = None
            for r in map(json.loads, f.read_text().splitlines()):
                h = r["H"]
                ro = se.main_class(classes[h]) in se.READ_ONLY if h in classes else None
                m = misses.get(h, {})
                paths = [[MASK.sub(r"\1<m>", p), w] for p, w in m.get("paths", [])]
                same_as_last = None
                if r.get("scores") and last is not None:
                    same_as_last = not differences(check_list(last["scores"]), check_list(r["scores"]))
                all_rows.append({"label": label, "task": task, "H": h, "read_only": ro, "class": se.main_class(classes[h]) if h in classes else None,
                                 "outcome": outcome(r), "paths": paths, "count": m.get("count"),
                                 "summary_differs": m.get("summary_differs"), "score_same_as_last": same_as_last})
                if r.get("scores"):
                    last = r
    for title, rows in (("read-only turns", [r for r in all_rows if r["read_only"]]),
                        ("other turns", [r for r in all_rows if r["read_only"] is False])):
        print(f"{title}: {len(rows)}; " + ", ".join(f"{k} {v}" for k, v in collections.Counter(r["outcome"] for r in rows).most_common()))
        pm = [r for r in rows if r["outcome"] == "paths"]
        counts = collections.Counter(r["count"] for r in pm)
        print(f"  path misses by number of paths: {sorted(counts.items(), key=lambda kv: (kv[0] is None, kv[0]))}")
        print(f"  the rest of the state matched on {sum(1 for r in pm if not r['summary_differs'])} of {len(pm)}; "
              f"sections that differed: {collections.Counter(s for r in pm for s in (r['summary_differs'] or [])).most_common()}")
        print(f"  score same as the last scored point: {sum(1 for r in pm if r['score_same_as_last'])} of "
              f"{sum(1 for r in pm if r['score_same_as_last'] is not None)}")
        groups: collections.Counter = collections.Counter()
        what: dict = collections.defaultdict(collections.Counter)
        for r in pm:
            for b in {bucket(p) for p, _ in r["paths"]}:
                groups[b] += 1
            for p, w in r["paths"]:
                what[bucket(p)][w] += 1
        for b, n in groups.most_common(25):
            print(f"    {n:4d} points  {b:50s} {dict(what[b].most_common(3))}")
        if a.ignore:
            alone = [r for r in pm if not r["summary_differs"] and all(p.startswith(tuple(a.ignore)) for p, _ in r["paths"])]
            print(f"  with those prefixes ignored, {len(alone)} of {len(pm)} path misses would be the same state; "
                  f"their score matched the last scored point on {sum(1 for r in alone if r['score_same_as_last'])} of "
                  f"{sum(1 for r in alone if r['score_same_as_last'] is not None)}")
    if a.json:
        Path(a.json).write_text(json.dumps(all_rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
