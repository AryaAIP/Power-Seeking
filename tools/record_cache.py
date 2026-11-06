"""An optional read cache for the run records, because reading them over WSL's /mnt/c share is slow.

power_horizons.py (and build_dashboard.py, which imports it) read about 5,600 small files in runs/ on every run. With
POWER_CACHE set to a folder on a fast disk, they read through this instead. Without it this file isn't even imported.

What it keeps: the exact bytes of each file read, compressed, in <POWER_CACHE>/records.sqlite, with the file's size and
modification time. It keeps no parsed values, so every parsing rule, the reward rule and score-corrections.json stay
live in power_horizons.py and can't go stale here. The records are the redacted ones, so this holds no raw data.

How it stays right: each run starts with a walk of runs/ (32 threads, about 7 s), which lists every folder down to the
run folders and stats every record file. A file whose size or modification time differs is read again. A later listing
of all of runs/ walks again if the last walk is over 10 s old, so a long page build sees new records. stat() is always
the real one. Anything outside runs/ or below a run folder goes to the real file. If the cache can't be opened, a note
goes to stderr and the script reads the files directly.

  export POWER_CACHE=/root/power-v0/cache                    then run power_horizons.py or build_dashboard.py as usual
  python3 -I tools/record_cache.py warm|stats|clear          fill or check it, show its size, delete it
  python3 -I tools/test_record_cache.py                      known-answer tests, including byte-identical output
"""

import io
import os
import sqlite3
import sys
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CORE = frozenset({"summary.json", "scores.json", "meta.json", "usage.csv", "horizon_scores.jsonl"})
WORKERS = 32
MAX_DEPTH = 4  # label/task/run/file
FRESH_FOR = 10.0  # seconds a walk stands for a listing of all of runs/


class Store:
    """The latest walk of runs/, and the files' bytes in SQLite."""

    def __init__(self, runs: str, folder: str):
        self.base = runs
        self.prefix = runs.rstrip("/") + "/"
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(folder, "records.sqlite"), timeout=30, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS files(rel TEXT PRIMARY KEY, size INTEGER NOT NULL, "
                        "mtime_ns INTEGER NOT NULL, data BLOB NOT NULL)")
        self.stored: dict = {}   # rel -> (size, mtime_ns) in the database
        self.stats: dict = {}    # rel -> (size, mtime_ns) on disk, as of the walk or the first read since
        self.known: set = set()  # every file and folder seen, down to MAX_DEPTH
        self.by_name: dict = {}  # file name -> [rel]
        self.by_label: dict = {}  # (label, file name) -> [rel]
        self.walked = 0.0
        self.walk_seconds = 0.0
        self.refreshed = 0
        self.walk()

    def _list(self, rel: str) -> list:
        try:
            with os.scandir(self.prefix + rel if rel else self.base) as it:
                return [(e.name, e.is_dir()) for e in it]
        except OSError:  # the folder has gone since it was listed
            return []

    def _stat(self, rel: str) -> tuple | None:
        try:
            s = os.stat(self.prefix + rel)
        except OSError:
            return None
        return s.st_size, s.st_mtime_ns

    def _fetch(self, item: tuple) -> bytes | None:
        """The file's compressed bytes, or None if it isn't the size its stat said (it's being written)."""
        rel, st = item
        try:
            with open(self.prefix + rel, "rb") as fh:
                data = fh.read()
        except OSError:
            return None
        return zlib.compress(data, 6) if len(data) == st[0] else None

    def walk(self) -> None:
        t0 = time.monotonic()
        self.stored = {r: (s, m) for r, s, m in self.db.execute("SELECT rel, size, mtime_ns FROM files")}
        known: set = set()
        dirs = [""]
        with ThreadPoolExecutor(WORKERS) as pool:
            for _ in range(MAX_DEPTH):
                below = []
                for d, entries in zip(dirs, pool.map(self._list, dirs)):
                    for name, is_dir in entries:
                        rel = f"{d}/{name}" if d else name
                        known.add(rel)
                        if is_dir:
                            below.append(rel)
                dirs = below
            want = [r for r in known if r.rsplit("/", 1)[-1] in CORE or r in self.stored]
            stats = {r: st for r, st in zip(want, pool.map(self._stat, want)) if st}
            stale = [(r, st) for r, st in stats.items() if self.stored.get(r) != st]
            rows = [(r, st[0], st[1], blob) for (r, st), blob in zip(stale, pool.map(self._fetch, stale)) if blob is not None]
        gone = [(r,) for r in self.stored if r not in known]
        try:
            self.db.execute("BEGIN")
            self.db.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?)", rows)
            self.db.executemany("DELETE FROM files WHERE rel=?", gone)
            self.db.execute("COMMIT")
            self.stored = {r: st for r, st in self.stored.items() if r in known}
            self.stored.update({r: (s, m) for r, s, m, _ in rows})
        except sqlite3.Error:  # another process holds it: read those files directly this time
            pass
        by_name: dict = {}
        by_label: dict = {}
        for rel in known:
            parts = rel.split("/")
            by_name.setdefault(parts[-1], []).append(rel)
            by_label.setdefault((parts[0], parts[-1]), []).append(rel)
        self.known, self.stats, self.by_name, self.by_label = known, stats, by_name, by_label
        self.refreshed = len(rows)
        self.walked = time.monotonic()
        self.walk_seconds = self.walked - t0

    def read(self, rel: str) -> bytes:
        """The file's bytes: from the database if its size and modification time match, otherwise from the file. A
        missing file raises the usual FileNotFoundError."""
        st = self.stats.get(rel)
        if st is None:
            st = self._stat(rel)
            if st is not None:
                self.stats[rel] = st
        if st is not None and self.stored.get(rel) == st:
            try:
                row = self.db.execute("SELECT data FROM files WHERE rel=?", (rel,)).fetchone()
                data = zlib.decompress(row[0]) if row else None
                if data is not None and len(data) == st[0]:
                    return data
            except (sqlite3.Error, zlib.error):
                pass
        with open(self.prefix + rel, "rb") as fh:
            data = fh.read()
        if st is not None and len(data) == st[0]:
            try:
                self.db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?)", (rel, st[0], st[1], zlib.compress(data, 6)))
                self.stored[rel] = st
            except sqlite3.Error:
                pass
        return data


class CachedPath(Path):
    """A pathlib path that answers reads, exists() and the scripts' glob patterns under runs/ from the Store. The
    scripts need no changes: every path made from RUNS is one of these. Needs Python 3.12 or later."""

    _store: Store | None = None

    def _rel(self) -> str | None:
        st = CachedPath._store
        s = str(self)
        if st is not None and s.startswith(st.prefix):
            rel = s[len(st.prefix):]
            if rel.count("/") < MAX_DEPTH:
                return rel
        return None

    def exists(self, *, follow_symlinks=True):
        rel = self._rel()
        return rel in CachedPath._store.known if rel is not None else super().exists(follow_symlinks=follow_symlinks)

    def read_bytes(self):
        rel = self._rel()
        return CachedPath._store.read(rel) if rel is not None else super().read_bytes()

    def read_text(self, encoding=None, errors=None, newline=None):
        with self.open("r", -1, encoding, errors, newline) as fh:
            return fh.read()

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        rel = self._rel()
        if rel is None or mode not in ("r", "rt", "rb"):
            return super().open(mode, buffering, encoding, errors, newline)
        raw = io.BytesIO(CachedPath._store.read(rel))
        return raw if mode == "rb" else io.TextIOWrapper(raw, encoding=encoding, errors=errors, newline=newline)

    def glob(self, pattern, **kwargs):
        """`*/.../name` from a folder under runs/ comes from the walk. Callers sort, so the order doesn't matter."""
        st = CachedPath._store
        s = str(self)
        parts = pattern.split("/")
        in_runs = st is not None and (s == st.base or s.startswith(st.prefix))
        rel = "" if not in_runs or s == st.base else s[len(st.prefix):]
        depth = (rel.count("/") + 1 if rel else 0) + len(parts)
        if kwargs or not in_runs or depth > MAX_DEPTH or "*" in parts[-1] or any(p != "*" for p in parts[:-1]):
            return super().glob(pattern, **kwargs)
        if not rel and time.monotonic() - st.walked > FRESH_FOR:
            st.walk()
        found = st.by_name.get(parts[-1], []) if not rel else st.by_label.get((rel.split("/")[0], parts[-1]), [])
        return iter([self.with_segments(st.prefix + r) for r in sorted(found)
                     if r.count("/") + 1 == depth and (not rel or r.startswith(rel + "/"))])


def cached_runs(runs: Path, folder: str) -> Path:
    """RUNS as a CachedPath, or unchanged if the cache can't be used."""
    if sys.version_info < (3, 12):
        return runs
    try:
        CachedPath._store = Store(str(runs), folder)
    except (OSError, sqlite3.Error) as e:
        print(f"note: read cache unavailable ({type(e).__name__}): reading the records directly. To reset it: "
              f"rm {folder}/records.sqlite*", file=sys.stderr)
        return runs
    return CachedPath(runs)


def main() -> int:
    runs = Path(__file__).resolve().parents[1] / "3-experiments" / "linuxarena-power-v0" / "runs"
    folder = os.environ.get("POWER_CACHE") or "/root/power-v0/cache"
    what = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if what == "clear":
        for f in Path(folder).glob("records.sqlite*"):
            f.unlink()
        print(f"cleared {folder}")
    elif what == "warm":
        s = Store(str(runs), folder)
        print(f"{len(s.stats)} record files checked in {s.walk_seconds:.1f} s; {s.refreshed} read again; {len(s.stored)} held")
    elif what == "stats":
        db = Path(folder) / "records.sqlite"
        if not db.exists():
            print(f"no cache at {folder}")
            return 0
        n, size = sqlite3.connect(db).execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM files").fetchone()
        print(f"{n} files, {size / 1e6:.0f} MB of records held in {db.stat().st_size / 1e6:.0f} MB at {db}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
