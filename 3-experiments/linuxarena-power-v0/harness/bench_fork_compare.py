#!/usr/bin/env python3
"""The fork test's comparison (plans/scoring-efficiency-tests.md): at each turn, did a score taken on a second stack from a
checkpoint match the score taken in place? Compares verdict, the check list by name, the bug fix's target tests, and the
built binary's hash, from raw rows in data/runs. Prints names and counts only, never explanations.
  python3 -I bench_fork_compare.py <in-place label> <fork label> [...]
"""

import glob
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import DATA  # noqa: E402

MARK = re.compile(r"^\s*(✓|✗|PASS:?|FAIL:?|PASSED|FAILED)\s+([\w.:\-/]+)", re.M)
COUNT = re.compile(r"(\d+)\s*/\s*(\d+)")


def rows_of(label: str) -> dict:
    out = {}
    for f in glob.glob(str(DATA / "runs" / label / "*" / "*" / "horizon_scores.jsonl")):
        for ln in Path(f).read_text().splitlines():
            r = json.loads(ln)
            out[r["H"]] = r
    return out


def result(r: dict) -> dict:
    sc = (r.get("score") or {}).get("linux_scorer") or {}
    expl = sc.get("explanation") or ""
    value = sc.get("value")
    count = COUNT.search(expl)
    return {"verdict": value.get("main_task_success") if isinstance(value, dict) else value,
            "count": count.group(0) if count else None,
            "checks": {name: mark.rstrip(":") in ("✓", "PASS", "PASSED") for mark, name in MARK.findall(expl)},
            "tests": {name: mark in ("PASSED",) for mark, name in MARK.findall(r.get("bugfix_tests") or "")}}


def differences(a: dict, b: dict) -> list[str]:
    out = [k for k in ("verdict", "count") if a[k] != b[k]]
    for part in ("checks", "tests"):
        out += sorted(n for n in set(a[part]) | set(b[part]) if a[part].get(n) != b[part].get(n))
    return out


def main() -> int:
    base = rows_of(sys.argv[1])
    print(f"{sys.argv[1]}: " + " ".join(f"H{h}={result(r)['verdict']},{result(r)['count']}" for h, r in sorted(base.items())))
    for label in sys.argv[2:]:
        fork = rows_of(label)
        same, diffs = 0, []
        for h, r in sorted(fork.items()):
            if h not in base:
                continue
            d = differences(result(base[h]), result(r))
            if d:
                diffs.append((h, result(base[h])["count"], result(r)["count"], d[:6]))
            else:
                same += 1
        bins = [(r.get("bench_binary_sha256"), base[h].get("bench_binary_sha256")) for h, r in fork.items() if h in base]
        apply_s = [r["seconds"]["restore"] for r in fork.values() if r.get("seconds")]
        undo_s = [r["seconds"]["restore"] for r in base.values() if r.get("seconds")]
        print(f"{label}: {same} identical, {len(diffs)} differ, of {same + len(diffs)} comparable; binary same "
              f"{sum(a == b for a, b in bins)} of {len(bins)}; apply median {st.median(apply_s) if apply_s else None} s, "
              f"undo median {st.median(undo_s) if undo_s else None} s")
        for d in diffs:
            print(f"  H={d[0]}: in place {d[1]}, fork {d[2]}: {d[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
