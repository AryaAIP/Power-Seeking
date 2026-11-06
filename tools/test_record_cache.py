"""Known-answer tests for record_cache.py on synthetic records, in temporary folders. No environment, no model calls.
Run in WSL:  python3 -I tools/test_record_cache.py   (prints each test; exits non-zero on a failure)
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import record_cache as rc  # noqa: E402

PROJECT = TOOLS.parent
HARNESS = PROJECT / "3-experiments" / "linuxarena-power-v0" / "harness"
TASK = "migrate_backup_records_to_sqlite"
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failed
    print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail and not ok else ''}")
    failed += 0 if ok else 1


def write_run(runs: Path, label: str, passed: dict, turns: int, prefix: tuple | None = None, rows: list | None = None) -> Path:
    d = runs / label / TASK / "e1-00000001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scores.json").write_text(json.dumps({"checks": [{"check": f"{c} — detail é", "passed": v} for c, v in passed.items()],
                                               "bugfix_tests": [], "parsed": {}}), encoding="utf-8")
    (d / "usage.csv").write_bytes(b"call,output_tokens\r\n" + b"".join(b"%d,5\r\n" % i for i in range(turns)))
    args = {"prefix_log": f"/x/{prefix[0]}/x.eval", **({"prefix_turns": prefix[1]} if len(prefix) > 1 else {})} if prefix else {}
    (d / "meta.json").write_text(json.dumps({"task": TASK, "args": args}))
    (d / "transcript.md").write_bytes(b"bad byte \xff here\r\nline two\n")
    if rows:
        (d / "horizon_scores.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (runs / label / "summary.json").write_text(json.dumps({"label": label}))
    (runs / label / "README.md").write_text(f"# {label}\n")
    return d


def fake_records(runs: Path) -> None:
    ab = {"a": True, "b": False}
    write_run(runs, "before", {"a": True, "b": True}, 8)
    write_run(runs, "after", {"a": True, "b": True}, 6)
    write_run(runs, "nw-before", {"a": False, "b": False}, 0)
    write_run(runs, "nw-after", {"a": False, "b": False}, 0)
    write_run(runs, "hz-after-H3", ab, 3, prefix=("after", 3))
    write_run(runs, "hz-before-H4", ab, 4, prefix=("before", 4))
    row = {"scores": {"checks": [{"check": "a — d", "passed": True}, {"check": "b — d", "passed": True}]}, "state_equal": True}
    write_run(runs, "sr-after", ab, 6, prefix=("after",), rows=[{**row, "H": 4}, {**row, "H": 5}])


def touch_later(f: Path) -> None:
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))


def test_reads(tmp: Path) -> None:
    runs = tmp / "runs"
    fake_records(runs)
    (runs / "runs-registry.md").write_text("registry\n")
    cached = rc.cached_runs(runs, str(tmp / "cache"))
    check("the cache is in use", isinstance(cached, rc.CachedPath))
    check("the cached path prints as the plain one", str(cached) == str(runs))
    same = True
    for f in sorted(p for p in runs.rglob("*") if p.is_file()):
        c = cached / f.relative_to(runs)
        same &= c.read_bytes() == f.read_bytes() and c.exists()
        same &= c.read_text(encoding="latin-1") == f.read_text(encoding="latin-1")
        same &= c.read_text(errors="replace") == f.read_text(errors="replace")
        with c.open("rb") as a, f.open("rb") as b:
            same &= a.read() == b.read()
        with c.open(errors="replace") as a, f.open(errors="replace") as b:
            same &= a.read() == b.read()
    check("every read gives what the file gives (bytes, text, newlines, bad bytes)", same)
    d = "before/" + TASK + "/e1-00000001"
    with (cached / d / "usage.csv").open(newline="") as fh:
        check("newline='' keeps \\r\\n", fh.read().startswith("call,output_tokens\r\n"))
    for pat, base in (("*/summary.json", ""), ("*/*/*/horizon_scores.jsonl", ""), ("*/*/scores.json", "after"), ("*/*/scores.json", "missing")):
        got = sorted(str(p) for p in (cached / base).glob(pat))
        want = sorted(str(p) for p in (runs / base).glob(pat))
        check(f"glob {base or 'runs'}: {pat} ({len(want)} found)", got == want and all(isinstance(p, rc.CachedPath) for p in (cached / base).glob(pat)), f"{got} != {want}")
    other = sorted(str(p) for p in cached.glob("hz-*"))
    check("any other glob pattern goes to the real one", other == sorted(str(p) for p in runs.glob("hz-*")) and len(other) == 2)
    check("a missing record reads as missing", not (cached / d / "power-actions.json").exists())
    try:
        (cached / d / "power-actions.json").read_text()
        check("a missing record raises FileNotFoundError", False)
    except FileNotFoundError:
        check("a missing record raises FileNotFoundError", True)
    check("a file below a run folder goes to the real one", not (cached / d / "prompts" / "x.txt").exists())
    check("a path outside runs/ goes to the real one", (cached.parent / "runs" / "runs-registry.md").exists() and not (cached.parent / "nothing").exists())
    check("relative_to and parent keep working", str((cached / d).relative_to(cached)) == d and (cached / d).parent.name == TASK)
    store = rc.CachedPath._store

    scores = cached / d / "scores.json"
    real = runs / d / "scores.json"
    first = scores.read_bytes()
    real.write_bytes(first.replace(b"true", b"TRUE"))  # the same size
    touch_later(real)
    store.walk()
    check("the same size with a new modification time is read again", scores.read_bytes() != first and scores.read_bytes() == real.read_bytes())
    real.write_bytes(real.read_bytes() + b"\n")
    store.walk()
    check("a new size is read again", scores.read_bytes() == real.read_bytes())
    readme = cached / "after" / "README.md"
    readme.read_text()
    check("a file outside the core list is kept once read", "after/README.md" in store.stored)
    (runs / "after" / "README.md").write_text("# changed text\n")
    touch_later(runs / "after" / "README.md")
    store.walk()
    check("and is checked on the next walk", readme.read_text() == "# changed text\n" and store.stored["after/README.md"] == store.stats["after/README.md"])
    write_run(runs, "newbatch", {"a": True}, 2)
    store.walked = 0  # as if the walk were old
    check("a listing of runs/ walks again once the last walk is old", "newbatch" in [p.parent.name for p in cached.glob("*/summary.json")])
    t = store.walked
    list(cached.glob("*/summary.json"))
    check("and not while it's fresh", store.walked == t)
    (runs / "newbatch" / TASK / "e1-00000001" / "usage.csv").unlink()
    store.walk()
    check("a removed file reads as gone", not (cached / "newbatch" / TASK / "e1-00000001" / "usage.csv").exists()
          and "newbatch/" + TASK + "/e1-00000001/usage.csv" not in store.stored)
    store.db.execute("UPDATE files SET data=? WHERE rel=?", (b"junk", d + "/meta.json"))
    check("a damaged row falls back to the file", (cached / d / "meta.json").read_bytes() == (runs / d / "meta.json").read_bytes())
    store.db.close()
    rc.CachedPath._store = None


def test_bad_database(tmp: Path) -> None:
    runs = tmp / "runs"
    fake_records(runs)
    (tmp / "cache").mkdir()
    (tmp / "cache" / "records.sqlite").write_bytes(b"this is not a database" * 100)
    got = rc.cached_runs(runs, str(tmp / "cache"))
    check("a damaged cache file falls back to the plain path", type(got) is type(runs) and got == runs)
    rc.CachedPath._store = None


def digest(tmp: Path, env: dict, name: str) -> tuple:
    """power_horizons.py's --json, stdout and stderr, as hashes (its output path is the same in every run)."""
    out = tmp / "out.json"
    r = subprocess.run([sys.executable, "-I", str(HARNESS / "power_horizons.py"),
                        "--before", "before", "--nowork-before", "nw-before", "--after", "X=after", "--nowork-after", "X=nw-after",
                        "--reward", "last-scored", "--rollback-rows", "--json", str(out)],
                       env={**os.environ, **env}, capture_output=True)
    if r.returncode:
        check(f"{name}: power_horizons.py runs", False, r.stderr.decode(errors="replace")[-400:])
    return r.returncode, hashlib.sha256(out.read_bytes()).hexdigest(), r.stdout, r.stderr


def test_end_to_end(tmp: Path) -> None:
    """The real power_horizons.py, in a folder laid out like the project: same bytes with no cache, cold and warm."""
    exp = tmp / "project" / "3-experiments" / "x"
    runs = exp / "runs"
    runs.mkdir(parents=True)
    (exp / "findings").mkdir()
    fake_records(runs)
    (tmp / "project" / "tools").symlink_to(TOOLS)
    base = {"POWER_V0_EXP": str(exp)}
    plain = digest(tmp, base, "no cache")
    report = json.loads((tmp / "out.json").read_text())
    check("the synthetic report has the score and roll back rows", 4 in report["scored_horizons"]["X"][TASK])
    with_cache = {**base, "POWER_CACHE": str(tmp / "cache")}
    check("no cache = cold cache: --json, stdout and stderr byte-identical", digest(tmp, with_cache, "cold") == plain)
    check("the cold run filled the cache", (tmp / "cache" / "records.sqlite").exists())
    check("no cache = warm cache: --json, stdout and stderr byte-identical", digest(tmp, with_cache, "warm") == plain)
    f = runs / "after" / TASK / "e1-00000001" / "scores.json"
    f.write_text(json.dumps({"checks": [{"check": "a — d", "passed": False}, {"check": "b — d", "passed": False}], "bugfix_tests": [], "parsed": {}}))
    touch_later(f)
    changed = digest(tmp, base, "changed, no cache")
    check("after a change, the result differs from before", changed != plain)
    check("after a change, the cache gives the new result, byte-identical", digest(tmp, with_cache, "changed, cached") == changed)


def main() -> int:
    for t in (test_reads, test_bad_database, test_end_to_end):
        print(f"-- {t.__name__}")
        with tempfile.TemporaryDirectory() as td:
            t(Path(td))
    print(f"{'all passed' if not failed else str(failed) + ' FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
