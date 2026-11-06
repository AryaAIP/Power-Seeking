"""Known-answer tests of dedup_gate.py, with no environment:  python3 -I test_dedup_gate.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dedup_gate as g  # noqa: E402


def job(audits=(), states=()):
    return {"dedup_audits": [{"H": h, "same": s} for h, s in audits],
            "state": [{"H": h, "state_equal": s} for h, s in states]}


CASES = [
    ("no record", [], False),
    ("two identical audits, restores exact", [job([(3, True), (4, True)], [(3, True), (4, True)])], True),
    ("one audit is too few", [job([(3, True)], [(3, True)])], False),
    ("none in the same state", [job([], [(3, True)])], False),
    ("an audit differs", [job([(3, True), (4, False), (5, True)], [(3, True)])], False),
    ("a restore not exact", [job([(3, True), (4, True)], [(3, False)])], False),
]

LINE = "sr-x\t1\tPURPOSE=\"y\" bash launch.sh sr-x tasks/one_a.txt 1 -p score_every=1\n"


def main() -> int:
    bad = 0
    for name, jobs, want in CASES:
        got, why = g.decide(jobs, 2)
        if got != want:
            print(f"FAIL {name}: {got} ({why})")
            bad += 1
    checks = [
        ("switch adds the option", g.switch_on(LINE) == LINE.rstrip("\n") + " -p score_dedup=true\n"),
        ("switch keeps one trailing newline", g.switch_on(LINE).count("\n") == 1),
        ("switch leaves a line that says", g.switch_on(LINE.rstrip("\n") + " -p score_dedup=true\n").count("score_dedup") == 1),
        ("switch leaves a rescore", g.switch_on(LINE.rstrip("\n") + " -p score_at=22\n").count("score_dedup") == 0),
        ("task of a line", g.task_of(LINE) == "one_a"),
        ("task of a stray line", g.task_of("# nothing\n") is None),
    ]
    for name, ok in checks:
        if not ok:
            print(f"FAIL {name}")
            bad += 1
    print(f"{len(CASES) + len(checks)} tests, {bad} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
