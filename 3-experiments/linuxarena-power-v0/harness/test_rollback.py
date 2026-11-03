"""Known-answer tests for score and roll back (rollback.py, power_v0.py's turn grouping). No environment, no model calls.
Run in WSL as root:
  python3 -I test_rollback.py              pure tests, plus the file undo on a real overlay mount (needs root)
  <control tower>/.venv/bin/python test_rollback.py --logs
                                           also checks the turn grouping against two stored solver runs
Prints each test and exits non-zero on a failure.
"""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rollback as rb  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name} {detail}")
    if not cond:
        failures.append(name)


# ---------------------------------------------------------------- pure functions
check("score_points: every turn", rb.score_points(1, "", 10) == list(range(1, 10)))
check("score_points: every 5, below the end", rb.score_points(5, "", 28) == [5, 10, 15, 20, 25])
check("score_points: every 5 at an exact multiple", rb.score_points(5, "", 25) == [5, 10, 15, 20])
check("score_points: a list, past-the-end and zero dropped", rb.score_points(0, "0,5, 10,40", 28) == [5, 10])
check("score_points: both, merged", rb.score_points(5, "7", 12) == [5, 7, 10])
check("score_points: none", rb.score_points(0, "", 28) == [])

tree = {"./model-registry": True, "sudo -E -u service ./model-registry": True, "/bin/bash /app/restart.sh": True,
        "bash /app/restart.sh": True, "sudo -n /app/restart.sh": True,
        "/bin/bash -c /app/restart.sh && tail -f /dev/null": False,  # the container's first process: never
        "tail -f /dev/null": False, "tail -f /tmp/model-registry.log": False, "cd /app/model-registry": False,
        "/app/s3gw/gateway": False}
builds = {"sudo /app/rebuild.sh": True, "/bin/bash /app/rebuild.sh": True,
          "/usr/bin/gcc -I /app/go/pkg/mod/github.com/mattn/go-sqlite3@v1.14.24 -fPIC -m64": True,
          "/usr/lib/gcc/x86_64-linux-gnu/11/cc1 -quiet -I /app/go/pkg/mod/x": True,
          "/usr/local/go/pkg/tool/linux_amd64/compile -o /tmp/go-build1/b337/_pkg_.a": True,
          "/usr/local/go/bin/go build -o model-registry .": True, "bash -c cd /app/model-registry && go build -o x .": True,
          "./model-registry": False, "sudo -E -u service ./model-registry": False, "/app/s3gw/gateway": False,
          "tail -30": False, "tail -f /dev/null": False, "/bin/bash -c /app/restart.sh && tail -f /dev/null": False}
got_b = {k: bool(rb.BUILD.search(k)) for k in builds}
check("replay builds: compiles and rebuild.sh, not the service or other processes", got_b == builds,
      str({k: v for k, v in got_b.items() if v != builds[k]}))
got = {k: bool(rb.SERVICE_TREE.search(k)) for k in tree}
check("service tree: the service and restart.sh, never the container's first process", got == tree,
      str({k: v for k, v in got.items() if v != tree[k]}))
holder = subprocess.Popen(["bash", "-c", 'exec -a "/bin/bash /app/restart.sh" sleep 60'], stdout=subprocess.PIPE)
waiter = subprocess.Popen(["tail", "-10"], stdin=holder.stdout, stdout=subprocess.DEVNULL)
other = subprocess.Popen(["sleep", "60"], stdin=subprocess.PIPE)
import time as _t  # noqa: E402
_t.sleep(0.3)
procs_ = [(str(holder.pid), "root", [], "/bin/bash /app/restart.sh"), (str(waiter.pid), "dev", [], "tail -10"),
          (str(other.pid), "dev", [], "sleep 60")]
check("service waiters: a tail reading the restart subshell's pipe, and nothing else",
      rb.service_waiters(procs_) == {str(waiter.pid)}, str(rb.service_waiters(procs_)))
for p in (holder, waiter, other):
    p.kill()

sleeper = subprocess.Popen(["sleep", "60"])
start = int(Path(f"/proc/{sleeper.pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
rb._kill([(sleeper.pid, start)], seconds=1, init=sleeper.pid)  # standing in for the container's first process
check("kill: never the container's first process", sleeper.poll() is None)
rb._kill([(sleeper.pid, start)], seconds=5)
check("kill: any other process", sleeper.wait(timeout=5) == -9)

E = lambda kind, ino=1: rb.Entry(kind, 0o755, 0, 0, 0, 1, 1, ino, 0, "", False)  # noqa: E731
before_ = {"app": E("dir"), "app/x": E("reg")}
after_ = {**before_, "app/x": E("reg", 2), "root": E("dir", 3), "root/.cache": E("dir", 4), "root/.cache/go-build": E("dir", 5),
          "root/other": E("reg", 6)}
p_all, p_keep = rb.plan_files(before_, after_, []), rb.plan_files(before_, after_, [], skip=rb.BUILD_CACHE)
check("keep build cache: off, the scorer's cache is removed", p_all["remove"] == ["root"] and p_all["from_saved"] == ["app", "app/x"],
      str(p_all))
check("keep build cache: on, it stays: its folder isn't removed, other additions are",
      p_keep["remove"] == ["root/other"] and "root/.cache" in p_keep["skipped"] and "app/x" in p_keep["from_saved"], str(p_keep))

a = {"db": {"x:table:public.t": "rows=1 md5=a", "x:schema": "s"}, "proc": {"root sleep": "1"}}
b = {"db": {"x:table:public.t": "rows=2 md5=b", "x:schema": "s"}, "proc": {"root sleep": "1", "root curl": "1"}}
d = rb.compare_sections(a, b)
check("compare_sections: only differing sections", set(d) == {"db", "proc"} and d["db"]["differ"] == ["x:table:public.t"]
      and d["proc"]["only_after"] == ["root curl"])
check("compare_sections: equal", rb.compare_sections(a, a) == {})

base = {"databases": "modelregistry,postgres", "modelregistry:schema": "h", "modelregistry:table:public.users": "rows=3 md5=a",
        "modelregistry:seq:public.users_id_seq": "3", "role:postgres": "super=t"}
check("db plan: same", rb._db_plan(base, dict(base)) == ("same", []))
rows = {**base, "modelregistry:table:public.users": "rows=4 md5=b", "modelregistry:seq:public.users_id_seq": "4"}
check("db plan: rows only -> reload in place", rb._db_plan(base, rows) == ("rows", ["modelregistry"]))
check("db plan: schema -> swap", rb._db_plan(base, {**rows, "modelregistry:schema": "h2"})[0] == "swap")
check("db plan: a new database -> swap", rb._db_plan(base, {**base, "databases": "modelregistry,postgres,x"})[0] == "swap")
check("db plan: a role -> swap", rb._db_plan(base, {**base, "role:evil": "super=t"})[0] == "swap")
check("db plan: an error -> swap", rb._db_plan(base, {"_error": "x"})[0] == "swap")


# ---------------------------------------------------------------- the file undo on a real overlay
def visible_tree(root: str) -> dict:
    """What a program sees under root: per path, type, mode, owner, size, modification time, and content or target."""
    out = {}
    for d, dirs, names in os.walk(root):
        for n in dirs + names:
            p = os.path.join(d, n)
            st = os.lstat(p)
            kind = stat.S_IFMT(st.st_mode)
            extra = (hashlib.sha256(Path(p).read_bytes()).hexdigest() if stat.S_ISREG(st.st_mode)
                     else os.readlink(p) if stat.S_ISLNK(st.st_mode) else "")
            out[os.path.relpath(p, root)] = (kind, stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid,
                                             st.st_size if stat.S_ISREG(st.st_mode) else 0, st.st_mtime_ns, extra)
    return out


class FakeStack:
    """rollback.Stack's file parts, with "the container" being an overlay mounted at merged."""

    def __init__(self, base: Path):
        self.upper, self.merged = str(base / "upper"), str(base / "merged")
        self.lowers = [str(base / "l1"), str(base / "l2")]
        self.work = base / "wk"
        self.saved = self.work / "upper"
        self.saved.mkdir(parents=True)
        self.prev = {}

    def in_container(self, *cmd):
        cmd = list(cmd)
        if cmd[:2] == ["sh", "-c"]:
            cmd[2] = cmd[2].replace("cd / ", f"cd {self.merged} ")
        if "-C" in cmd and cmd[cmd.index("-C") + 1] == "/":
            cmd[cmd.index("-C") + 1] = self.merged
        return cmd


def write(p: Path, text: str, mode: int = 0o644, mtime: int | None = None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    os.chmod(p, mode)
    if mtime:
        os.utime(p, (mtime, mtime))


def sh(*cmd):
    subprocess.run(cmd, check=True)


def overlay_tests():
    if os.geteuid() != 0:
        print("skip overlay tests: needs root")
        return
    top = Path(tempfile.mkdtemp(prefix="sr-test-", dir="/root" if os.path.isdir("/root") else None))
    try:
        for n in ("l1", "l2", "upper", "ovl-work", "merged"):
            (top / n).mkdir()
        l1, l2, m = top / "l1", top / "l2", top / "merged"
        # the image: two layers. l1 hides l2's opt/x (a whiteout) and replaces l2's lib (an opaque folder)
        write(l2 / "etc/conf", "port=1\n", mtime=1_600_000_000)
        write(l2 / "usr/bin/tool", "#!/bin/sh\necho tool\n", 0o755, mtime=1_600_000_000)
        write(l2 / "data/a.txt", "a\n")
        write(l2 / "data/sub/b.txt", "b\n")
        write(l2 / "data/sub/deep/c.txt", "c\n")
        (l2 / "root").mkdir(mode=0o700)
        (l2 / "tmp").mkdir()
        os.chmod(l2 / "tmp", 0o1777)
        write(l2 / "opt/x", "hidden\n")
        write(l2 / "lib/old.txt", "old\n")
        write(l1 / "data/c.txt", "layer one\n", mtime=1_600_000_000)
        (l1 / "opt").mkdir()
        os.mknod(l1 / "opt/x", stat.S_IFCHR | 0o000, 0)
        write(l1 / "lib/new.txt", "new\n")
        os.setxattr(l1 / "lib", "trusted.overlay.opaque", b"y")
        sh("mount", "-t", "overlay", "overlay", "-o",
           f"lowerdir={l1}:{l2},upperdir={top / 'upper'},workdir={top / 'ovl-work'}", str(m))
        try:
            check("overlay: the image as built", (m / "opt/x").exists() is False and not (m / "lib/old.txt").exists()
                  and (m / "lib/new.txt").read_text() == "new\n")
            st = FakeStack(top)
            # --- the agent's turns
            write(m / "etc/conf", "port=2\n")
            write(m / "app/code.go", "package main\n")
            write(m / "app/bin", "\x7fELF", 0o755)
            os.symlink("code.go", m / "app/link")
            (m / "data/a.txt").unlink()  # deletes an image file: a whiteout in the upper folder
            write(m / "data/newdir/f", "f\n")
            os.chmod(m / "usr/bin/tool", 0o750)
            v0 = visible_tree(str(m))
            l0 = rb.listing(st.upper)
            n = rb._sync_saved(st, l0)
            check("save: the whole upper folder copied the first time", n == len(l0) and n > 0, f"({n} entries)")
            check("save: the copy equals the upper folder",
                  {r: rb.visible(e) for r, e in rb.listing(str(st.saved)).items()} == {r: rb.visible(e) for r, e in l0.items()})
            # --- the scorer
            write(m / "app/code.go", "package main // rebuilt by the scorer\n")
            write(m / "etc/conf", "port=3\n")
            os.chown(m / "etc/conf", 1000, 1000)
            write(m / "root/.cache/go-build/aa/bb", "cache\n")  # copies up root/, an image folder
            (m / "usr/bin/tool").unlink()  # an image file the agent had changed
            shutil.rmtree(m / "data/sub")  # an image folder, with a sub-folder
            write(m / "data/a.txt", "back again\n")  # where the agent's deletion was
            (m / "app/bin").unlink()  # the agent's own file
            (m / "app/link").unlink()
            (m / "app/link").mkdir()  # a type change
            write(m / "app/link/inside", "x\n")
            os.utime(m / "data/c.txt", (1_700_000_000, 1_700_000_000))  # only the time changes (a copy-up)
            write(m / "tmp/model-registry.log", "log\n")  # volatile: left alone
            l1_ = rb.listing(st.upper)
            plan, rc = rb.restore_files(st, l0, l1_, skip=rb.VOLATILE)
            check("restore: tar extraction ok", rc == 0, f"(exit {rc})")
            check("restore: removes only top-most added paths",
                  set(plan["remove"]) >= {"root/.cache", "app/link"} and "root/.cache/go-build" not in plan["remove"],
                  str(plan["remove"]))
            check("restore: the deleted image folder comes back whole from the layers",
                  {r for _, r in plan["from_lower"]} >= {"data/sub", "data/sub/b.txt", "data/sub/deep", "data/sub/deep/c.txt"})
            check("restore: volatile path skipped", plan["skipped"] == ["tmp/model-registry.log"], str(plan["skipped"]))
            v2 = visible_tree(str(m))
            v2.pop("tmp/model-registry.log", None)
            diff = sorted(r for r in set(v0) | set(v2) if v0.get(r) != v2.get(r))
            check("restore: the container sees exactly what it saw at the save", not diff, str(diff[:8]))
            l2_ = rb.listing(st.upper)
            fd = rb.compare_files(l0, l2_, st.lowers, str(st.saved), st.upper, skip=rb.VOLATILE)
            check("check: compare_files finds no difference", fd == [], str(fd[:5]))
            # --- more turns, a second save (incremental), a second scoring
            write(m / "app/more.go", "package more\n")
            write(m / "etc/conf", "port=4\n")
            (m / "data/newdir/f").unlink()
            v0b = visible_tree(str(m))
            v0b.pop("tmp/model-registry.log", None)
            l0b = rb.listing(st.upper)
            n = rb._sync_saved(st, l0b)
            check("save 2: the copy equals the upper folder",
                  {r: rb.visible(e) for r, e in rb.listing(str(st.saved)).items()} == {r: rb.visible(e) for r, e in l0b.items()},
                  f"({n} of {len(l0b)} entries copied)")
            n = rb._sync_saved(st, rb.listing(st.upper))
            check("save 2 again, nothing changed: copies nothing", n == 0, f"({n})")
            write(m / "app/more.go", "package more // changed\n")
            write(m / "data/newdir/g", "g\n")
            shutil.rmtree(m / "app")
            l1b = rb.listing(st.upper)
            plan, rc = rb.restore_files(st, l0b, l1b, skip=rb.VOLATILE)
            v2b = visible_tree(str(m))
            v2b.pop("tmp/model-registry.log", None)
            diff = sorted(r for r in set(v0b) | set(v2b) if v0b.get(r) != v2b.get(r))
            check("restore 2: back to the second save, a deleted agent folder included", rc == 0 and not diff, str(diff[:8]))
            fd = rb.compare_files(l0b, rb.listing(st.upper), st.lowers, str(st.saved), st.upper, skip=rb.VOLATILE)
            check("check 2: no difference", fd == [], str(fd[:5]))
            # --- an image folder deleted and made again: opaque, which can't be undone from inside, so it's reported
            l0c = rb.listing(st.upper)
            rb._sync_saved(st, l0c)
            shutil.rmtree(m / "lib")
            (m / "lib").mkdir()
            write(m / "lib/new.txt", "new\n")
            plan = rb.plan_files(l0c, rb.listing(st.upper), st.lowers)
            check("opaque: reported", plan["opaque"] == ["lib"], str(plan["opaque"]))
            # --- a file a running process appends to (the restarted service's log, say): rewritten in place
            l0d = rb.listing(st.upper)
            rb._sync_saved(st, l0d)
            fh = open(m / "etc/conf", "a")  # held open for appending, as the service would
            fh.write("written at start-up\n")
            fh.flush()
            rb._rewrite_in_place(st, "etc/conf", l0d["etc/conf"])
            fd = rb.compare_files(l0d, rb.listing(st.upper), st.lowers, str(st.saved), st.upper)
            check("in place: the file is back as saved", fd == [], str(fd))
            fh.write("appended later\n")
            fh.close()
            check("in place: the holder keeps writing to the visible file",
                  (m / "etc/conf").read_text() == "port=4\nappended later\n", repr((m / "etc/conf").read_text()))
            # --- a mass deletion is refused
            try:
                rb.restore_files(st, {}, rb.listing(st.upper))
                check("guard: an empty listing is refused", False)
            except RuntimeError:
                check("guard: an empty listing is refused", True)
        finally:
            subprocess.run(["umount", str(m)], check=False)
    finally:
        shutil.rmtree(top, ignore_errors=True)


overlay_tests()


# ---------------------------------------------------------------- turn grouping, against stored runs
def log_tests():
    import json  # noqa: PLC0415

    import power_v0  # noqa: PLC0415  (needs Control Tower's Python)
    from power_paths import DATA, RUNS  # noqa: PLC0415

    for label, short_task in (("v4-afterB-p1", "model_favoriting_system"), ("v4-afterA2-p1", "migrate_backup_records_to_sqlite")):
        log = str(next((DATA / "evals" / label).glob("*.eval")))
        meta = next(m for m in RUNS.glob(f"{label}/{short_task}/*/meta.json"))
        turns = sum(1 for ln in (meta.parent / "usage.csv").read_text().splitlines()[1:] if ln.split(",")[4] not in ("", "0"))
        flat, i1 = power_v0._prefix_calls(log, short_task, 1, turns)
        grouped, i2 = power_v0._prefix_calls(log, short_task, 1, turns, grouped=True)
        check(f"grouping {label} {short_task}: one list per turn", len(grouped) == turns, f"({len(grouped)} vs {turns})")
        check(f"grouping {label} {short_task}: flattened = the per-step jobs' calls",
              [c.id for t in grouped for c in t] == [c.id for c in flat] and i1 == i2, f"({len(flat)} calls)")
        h = turns // 2
        part, _ = power_v0._prefix_calls(log, short_task, 1, h)
        check(f"grouping {label} {short_task}: the first {h} turns = the H={h} per-step job's calls",
              [c.id for t in grouped[:h] for c in t] == [c.id for c in part])
        check(f"grouping {label} {short_task}: the run's whole length is its own turn count",
              i2["prefix_total_turns"] == turns, f"({i2['prefix_total_turns']} assistant messages, {turns} turns in usage.csv)")
        json.dumps(i2)


if "--logs" in sys.argv:
    log_tests()

print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
