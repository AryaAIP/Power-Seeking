"""Score and roll back (plans/score-and-rollback-scope.md): per-step scoring inside one machine per solver run.

power_v0.py replays a stored solver run's turns in order. At each scoring point (score_every= or score_at=) it calls
  save_point()     just before scoring. It records:
                     - the app container's changed files: its overlay upper folder, copied incrementally into a host
                       folder that always mirrors the upper folder as of the last save;
                     - Postgres: a paused copy of the cluster's data folder, plus a data-only dump of every database;
                     - the stack's two buckets, mirrored into a folder inside the shared MinIO;
                     - the processes, the running service, and a state summary;
  the scorer       the task's real scorer, as at the end of a sample;
  restore_point()  undoes what the scoring changed, and only that:
                     - kills processes the scoring started;
                     - puts back every file the scoring changed, removes every file it added;
                     - reloads changed tables in place (the service keeps its connections), or swaps the whole cluster
                       back if the schema, roles or databases changed;
                     - mirrors changed buckets back;
                     - restarts the service if the scoring replaced it (or the cluster was swapped);
                   then writes the state summary again and compares it with the first.
Runs on the host (WSL or the cloud machine) as root. Reuses state_store's stack lookup, Postgres swap, MinIO login and
service restart, and env_fingerprint's database, process, service and network sections. Nothing secret is printed or
recorded: the service's environment is only hashed, error messages carry no command output, and the work folder
(DATA/rollback/..., which holds copies of the machine's files and tables) is removed when the job ends.
"""

import hashlib
import io
import json
import os
import re
import shlex
import tarfile
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

import env_fingerprint as fpr
import state_store as ss

# The service log: restart.sh truncates it and the running service appends to it, so it's never restored or compared
# (env_fingerprint leaves it out too). Paths are relative to the container's /.
VOLATILE = ("tmp/model-registry.log",)
# With keep_build_cache (power_v0's score_keep_build_cache, off by default): root's caches, which the scorers' `go build`
# fill, are kept between points instead of undone, so later builds are incremental. Go's build cache is keyed by
# content, so a build gives the same result either way; its test cache is cleared before every scorer.
BUILD_CACHE = ("root/.cache",)
# Processes that come and go on their own: Docker's health checks, runc's helper, and zombies (a killed process its
# parent hasn't reaped yet: it can't run). Never killed, never compared.
TRANSIENT = re.compile(r"127\.0\.0\.1:8080/health|localhost:8080/health|^runc( |$)|runc init|env_fingerprint|^\[zombie\]$")
SERVICE_ARGS = "./model-registry"
# The service and what restart.sh leaves with it: `sudo -E -u service ./model-registry`, the service, and a restart.sh
# still running. Never the container's first process (`/bin/bash -c /app/restart.sh && tail -f /dev/null`): killing it
# stops the container. _kill refuses that process anyway.
SERVICE_TREE = re.compile(r"(^|\s)\./model-registry$|^(\S*/)?(ba)?sh /app/restart\.sh$|^sudo( -\S+)* /app/restart\.sh$")
TAR_POSIX = ["--format=posix", "--pax-option=delete=atime,delete=ctime"]  # keeps nanosecond modification times
# A build the replay left running: a replayed `sudo /app/rebuild.sh | tail` whose call hit its time limit, as it did in
# the original run, keeps compiling in the background (the SQLite driver's cgo build takes minutes). Its output is the
# agent's, not the scorer's, so save_point waits for it to finish (at most BUILD_WAIT s) rather than let the undo take
# its binary away (residue-undo-scope §6, risk 2).
BUILD = re.compile(r"(^|[ /])(go|gcc|cc|cc1|cc1plus|as|ld|collect2|compile|link|asm|cgo|vet)( |$)|/app/rebuild\.sh|"
                   r"go-build|\bgo (build|install|test|mod)\b")
BUILD_WAIT = 300
# A restart the replay left in flight (a replayed `sudo /app/restart.sh` still between its pkill and the new service):
# its `sudo … restart.sh`, or a `sleep` restart.sh is running. save_point waits for it too, so the service the restart
# starts is part of the saved state, not taken for one the scorer started.
RESTART_CALL = re.compile(r"^sudo( -\S+)* /app/restart\.sh$|^(\S*/)?(ba)?sh /app/restart\.sh$")
SHORT_SLEEP = 60  # a sleep of at most this many seconds is waited for too; a longer one is the agent's own business


def _unsettled(procs: dict) -> list[str]:
    """Builds and restarts the replay left running (see BUILD and RESTART_CALL)."""
    out = [p["args"] for p in procs.values() if BUILD.search(p["args"]) and not SERVICE_TREE.search(p["args"].strip())]
    pids = {k[0]: p for k, p in procs.items()}
    for (pid, _), p in procs.items():
        a = p["args"].strip()
        if re.match(r"^sudo( -\S+)* /app/restart\.sh$", a):
            out.append(a)  # the caller's sudo exits only when restart.sh's foreground part is done
        elif re.match(r"^(\S*/)?sleep \d+$", a) and RESTART_CALL.search(pids.get(p["ppid"], {}).get("args", "").strip()):
            out.append(f"{a} (in restart.sh)")
        elif (m := re.match(r"^(\S*/)?sleep (\d+)$", a)) and int(m.group(2)) <= SHORT_SLEEP:
            # e.g. `cd /app/model-registry && sudo /app/restart.sh & sleep 10`: restart.sh's pkill -f model-registry kills
            # the agent's own call, as it did in the run, and its sleep lives on. It would end during scoring.
            out.append(f"{a} (left behind)")
    return out


class Entry(NamedTuple):
    kind: str        # reg, dir, lnk, chr, blk, fifo, sock, whiteout (an overlay deletion marker)
    mode: int
    uid: int
    gid: int
    size: int
    mtime_ns: int
    ctime_ns: int
    ino: int
    rdev: int
    target: str      # a symlink's target
    opaque: bool     # an overlay directory that hides the layers below


def visible(e: Entry | None) -> tuple | None:
    """What a program in the container can see of an entry (no inode number, no change time)."""
    return None if e is None else (e.kind, e.mode, e.uid, e.gid, e.size, e.mtime_ns, e.rdev, e.target)


def entry(path: str) -> Entry:
    st = os.lstat(path)
    kind = fpr.TYPES.get(stat.S_IFMT(st.st_mode), "other")
    if kind == "chr" and st.st_rdev == 0:
        kind = "whiteout"
    opaque = False
    if kind == "dir":
        try:
            opaque = os.getxattr(path, "trusted.overlay.opaque", follow_symlinks=False) == b"y"
        except OSError:
            pass
    return Entry(kind, stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid, st.st_size if kind == "reg" else 0,
                 st.st_mtime_ns, st.st_ctime_ns, st.st_ino, st.st_rdev, os.readlink(path) if kind == "lnk" else "",
                 opaque)


def _under(rel: str, roots) -> bool:
    return any(rel == r or rel.startswith(r + "/") for r in roots)


def listing(root: str, skip=()) -> dict[str, Entry]:
    """Every entry under root (an overlay upper folder or a layer), as paths relative to it, without the subtrees in
    skip (the container's mount points, relative)."""
    out: dict[str, Entry] = {}
    for d, dirs, names in os.walk(root):
        rd = os.path.relpath(d, root)
        rd = "" if rd == "." else rd
        dirs[:] = [n for n in dirs if not _under(f"{rd}/{n}" if rd else n, skip)]
        for n in dirs + names:
            rel = f"{rd}/{n}" if rd else n
            if _under(rel, skip):
                continue
            try:
                out[rel] = entry(os.path.join(d, n))
            except FileNotFoundError:
                continue
    return out


def lower_lookup(rel: str, lowers: list[str]) -> tuple:
    """Where the image's layers (top first) put rel: ("lower", layer, Entry) or ("absent",)."""
    parts = rel.split("/")
    for layer in lowers:
        hidden = False
        for i in range(1, len(parts)):
            p = os.path.join(layer, *parts[:i])
            try:
                e = entry(p)
            except (FileNotFoundError, NotADirectoryError):
                break
            if e.kind != "dir":
                return ("absent",)  # a whiteout or a file in place of a parent folder
            hidden = hidden or e.opaque
        try:
            e = entry(os.path.join(layer, rel))
        except (FileNotFoundError, NotADirectoryError):
            if hidden:
                return ("absent",)
            continue
        return ("absent",) if e.kind == "whiteout" else ("lower", layer, e)
    return ("absent",)


def effective(rel: str, upper: dict[str, Entry], lowers: list[str]) -> tuple:
    """What the container sees at rel, given the upper folder's listing: ("upper", Entry), ("lower", layer, Entry) or
    ("absent",)."""
    if rel in upper:
        e = upper[rel]
        return ("absent",) if e.kind == "whiteout" else ("upper", e)
    parts = rel.split("/")
    for i in range(1, len(parts)):
        a = upper.get("/".join(parts[:i]))
        if a is not None and (a.kind != "dir" or a.opaque):
            return ("absent",)
    return lower_lookup(rel, lowers)


def plan_files(before: dict, after: dict, lowers: list[str], skip=()) -> dict:
    """How to bring the upper folder from `after` back to `before`, as the container sees it:
      remove      paths to delete (rm -rf), top-most only;
      from_saved  paths to copy back from the saved copy of the upper folder;
      from_lower  (layer, path) pairs to copy back from the image's layers;
      opaque      folders the scoring made opaque, which hide image files and can't be undone from inside;
      skipped     changed paths left alone (volatile, or open for writing by a process that keeps running)."""
    remove, saved, lower, opaque, skipped = [], [], [], [], []
    for rel in sorted(set(before) | set(after)):
        a, b = before.get(rel), after.get(rel)
        if a == b:
            continue
        if _under(rel, skip) or "sock" in (getattr(a, "kind", ""), getattr(b, "kind", "")):
            skipped.append(rel)  # a socket can't be copied: tar ignores it
            continue
        e0, e1 = effective(rel, before, lowers), effective(rel, after, lowers)
        if b is not None and b.opaque and not (a is not None and a.opaque) and lower_lookup(rel, lowers)[0] == "lower":
            opaque.append(rel)
        if e0[0] == "absent":
            if e1[0] != "absent":
                remove.append(rel)
            continue
        if e1[0] != "absent" and e1[-1].kind != e0[-1].kind:
            remove.append(rel)  # a type change: clear the path first
        if e0[0] == "upper":
            saved.append(rel)
        elif (e1[0] == "absent" or visible(e0[2]) != visible(e1[-1])
              or (e1[0] == "upper" and e0[2].kind == "reg")):  # a copied-up file may differ in content alone
            lower.append((e0[1], rel))
            if e0[2].kind == "dir" and e1[0] == "absent":  # an image folder the scoring deleted: its whole tree
                for layer in lowers:
                    base = os.path.join(layer, rel)
                    for d, dirs, names in os.walk(base) if os.path.isdir(base) else ():
                        for n in dirs + names:
                            sub = os.path.relpath(os.path.join(d, n), layer)
                            e = effective(sub, before, lowers)
                            if e[0] == "lower" and e[1] == layer:
                                lower.append((layer, sub))
    # A folder above a skipped path stays (its other added contents are removed one by one); otherwise rm -rf of a
    # folder covers what's inside it.
    remove = [r for r in remove if not any(s.startswith(r + "/") for s in skipped)]
    top = []
    for rel in remove:
        if not any(rel.startswith(t + "/") for t in top):
            top.append(rel)
    # Deleting or rewriting a path changes its folder's modification time: every folder above a touched path is put
    # back too (its own entry only), and tar sets folder times after their contents.
    have = set(saved) | {r for _, r in lower}
    for rel in [*top, *saved, *(r for _, r in lower)]:
        p = rel.rsplit("/", 1)[0] if "/" in rel else ""
        while p and p not in have:
            have.add(p)
            e = effective(p, before, lowers)
            if e[0] == "upper":
                saved.append(p)
            elif e[0] == "lower":
                lower.append((e[1], p))
            p = p.rsplit("/", 1)[0] if "/" in p else ""
    return {"remove": top, "from_saved": sorted(saved), "from_lower": sorted(set(lower)), "opaque": opaque,
            "skipped": skipped}


def compare_files(before: dict, after: dict, lowers: list[str], saved_root: str, upper: str, skip=()) -> list:
    """Paths whose visible state differs between the listing taken at the save (`before`, whose files are in
    saved_root) and now (`after`, live in upper). Regular files are compared by content too."""
    out = []
    for rel in sorted(set(before) | set(after)):
        a, b = before.get(rel), after.get(rel)
        if a == b or _under(rel, skip):
            continue
        e0, e1 = effective(rel, before, lowers), effective(rel, after, lowers)
        v0 = visible(e0[-1]) if e0[0] != "absent" else None
        v1 = visible(e1[-1]) if e1[0] != "absent" else None
        if v0 != v1:
            fields = ("kind", "mode", "uid", "gid", "size", "mtime", "rdev", "target")
            out.append([rel, "exists" if v0 is None or v1 is None else
                        ",".join(f for f, x, y in zip(fields, v0, v1) if x != y)])
            continue
        if v0 and v0[0] == "reg":
            src0 = os.path.join(saved_root if e0[0] == "upper" else e0[1], rel)
            src1 = os.path.join(upper if e1[0] == "upper" else e1[1], rel)
            if fpr.sha_file(src0) != fpr.sha_file(src1):
                out.append([rel, "content"])
    return out


def score_points(every: int, at: str, end: int) -> list[int]:
    """The scoring points strictly between 0 and the replay's end: every N turns, and/or the listed turns."""
    pts = set(range(every, end, every)) if every > 0 else set()
    pts |= {int(x) for x in str(at or "").replace(" ", "").split(",") if x}
    return sorted(h for h in pts if 0 < h < end)


def compare_sections(a: dict, b: dict) -> dict:
    """{section: {"only_before": [...], "only_after": [...], "differ": [...]}} for the sections that differ."""
    out = {}
    for sec in sorted(set(a) | set(b)):
        x, y = a.get(sec) or {}, b.get(sec) or {}
        d = {"only_before": sorted(set(x) - set(y)), "only_after": sorted(set(y) - set(x)),
             "differ": sorted(k for k in set(x) & set(y) if x[k] != y[k])}
        if any(d.values()):
            out[sec] = d
    return out


# ---------------------------------------------------------------- the running stack
def _run(cmd, check=True, timeout=600, say_err=False, **kw):
    """state_store.run, but an error carries the command's first words and exit code only, never its output; with
    say_err (our own rm, cat and the like, whose messages name paths, not contents), also the end of its stderr."""
    r = subprocess.run(cmd, capture_output=True, text=kw.pop("text", True), timeout=timeout, **kw)
    if check and r.returncode != 0:
        err = r.stderr if isinstance(r.stderr, str) else (r.stderr or b"").decode(errors="replace")
        raise RuntimeError(f"{' '.join(str(c) for c in cmd[:3])} exit {r.returncode}"
                           + (f": {err.strip()[-300:]}" if say_err and err.strip() else ""))
    return r


def _unoct(s: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), s)


def _lowers(pid: int | str) -> list[str]:
    """The image's layer folders (top first) from the app container's root mount."""
    for line in Path(f"/proc/{pid}/mountinfo").read_text().splitlines():
        if _unoct(line.split(" ")[4]) == "/":
            for opt in line.split(" - ", 1)[1].split(" ", 2)[2].strip().split(","):
                if opt.startswith("lowerdir="):
                    return [p if p.startswith("/") else os.path.join("/var/lib/docker/overlay2", p)
                            for p in (_unoct(x) for x in opt[9:].split(":")) if p]
    raise RuntimeError("no overlay lowerdir for the app container's /")


class Stack:
    """One job's stack, and the work folder that holds the saved copies."""

    def __init__(self, app_cid: str, work: Path, keep_build_cache: bool = False):
        self.keep = BUILD_CACHE if keep_build_cache else ()
        s = ss.find_stack(app_cid)
        self.s, self.cid, self.project, self.suffix = s, app_cid, s["project"], s["suffix"]
        self.pid, self.upper, self.pg, self.pgdata = int(s["pid"]), s["upper"], s["pg"], s["pgdata"]
        self.skip = sorted({m.lstrip("/") for m in s["mounts"]})
        self.lowers = _lowers(self.pid)
        self.work = work
        self.saved = work / "upper"  # mirrors the upper folder as of the last save
        self.saved.mkdir(parents=True)
        self.prev: dict[str, Entry] = {}
        self.minio_tmp = f"/tmp/power-sr-{self.suffix}"
        self.points = 0

    def in_container(self, *cmd: str) -> list[str]:
        """A command run at the container's / (tests run it at a mounted overlay instead): through nsenter into its
        namespaces, with its own PATH, since a `docker exec` costs ~2 s under load. ns_env() gives the environment."""
        return [*_ns(self.pid), "env", "-i", f"PATH={_container_env(self.pid).get('PATH', '/usr/bin:/bin')}", *cmd]

    def pg_pid(self) -> int:
        """The Postgres container's first process (cached; reset when the cluster is swapped back and restarted)."""
        if not getattr(self, "_pgpid", None):
            self._pgpid = int(_run(["docker", "inspect", "-f", "{{.State.Pid}}", self.pg]).stdout.strip())
        return self._pgpid

    def cleanup(self) -> None:
        _run(["docker", "exec", ss.SHARED_MINIO, "rm", "-rf", self.minio_tmp], check=False)
        shutil.rmtree(self.work, ignore_errors=True)
        for p in (self.work.parent, self.work.parent.parent):  # the task and label folders, once empty
            try:
                p.rmdir()
            except OSError:
                pass


def _nul(paths) -> bytes:
    return b"".join(p.encode("utf-8", "surrogateescape") + b"\0" for p in paths)


def _tar_out(root: str, rels: list[str], lst: Path) -> list[str]:
    """tar's create command for these entries of root, without recursion; the list goes into the file lst."""
    lst.write_bytes(_nul(rels))
    return ["tar", "-C", root, *TAR_POSIX, "--numeric-owner", "--xattrs", "--xattrs-exclude=trusted.*",
            "--no-recursion", "--null", "-T", str(lst), "-cf", "-"]


def _pipe(src_cmd: list[str], dst_cmd: list[str], timeout: int = 900) -> None:
    p1 = subprocess.Popen(src_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        r = subprocess.run(dst_cmd, stdin=p1.stdout, capture_output=True, timeout=timeout)
    finally:
        p1.stdout.close()
        rc1 = p1.wait(timeout=timeout)
    if rc1 > 1 or r.returncode > 1:  # 1 = a file changed or vanished while read; 2 = fatal
        raise RuntimeError(f"tar copy failed (create exit {rc1}, extract exit {r.returncode})")


def _rm_host(p: Path) -> None:
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    elif p.exists() or p.is_symlink():
        p.unlink()


def _parent(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _sync_saved(st: Stack, cur: dict[str, Entry]) -> int:
    """Bring the host copy of the upper folder up to date with the listing `cur` (taken with the container paused):
    copy entries that are new or changed since the last save, delete entries that are gone. Returns the count copied."""
    prev = st.prev
    keep = getattr(st, "keep", ())  # kept caches are never restored, so never copied
    changed = sorted(r for r, e in cur.items() if prev.get(r) != e and e.kind != "sock" and not _under(r, keep))
    gone = [r for r in prev if r not in cur]
    retyped = [r for r in changed if r in prev and prev[r].kind != cur[r].kind]
    for r in sorted(gone + retyped, reverse=True):
        _rm_host(st.saved / r)
    if changed:
        _pipe(_tar_out(st.upper, changed, st.work / "sync.nul"),
              ["tar", "-C", str(st.saved), "--delay-directory-restore", "--numeric-owner", "--xattrs", "--xattrs-include=*",
               "-xpf", "-"])
    for r in {_parent(x) for x in changed + gone} - {""}:  # writing a folder's children changed its time
        e = cur.get(r)
        if e is not None and e.kind == "dir" and (st.saved / r).is_dir():
            os.utime(st.saved / r, ns=(e.mtime_ns, e.mtime_ns), follow_symlinks=False)
    st.prev = cur
    return len(changed)


NSENTER = shutil.which("nsenter") or "/usr/bin/nsenter"  # the host's, whatever PATH the container's environment has


def _ns(pid) -> list[str]:
    """Run a command inside a container's namespaces (mount, UTS, IPC, network, PID) from the host."""
    return [NSENTER, "-t", str(pid), "-m", "-u", "-i", "-n", "-p", "--"]


_ENV_CACHE: dict = {}


def _container_env(pid) -> dict:
    """A container's own environment, from its first process: what `docker exec` gives a command. In memory only (it
    can hold secrets, such as the MinIO admin login); never written or printed."""
    if pid not in _ENV_CACHE:
        env = {}
        for kv in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
            if b"=" in kv:
                k, v = kv.split(b"=", 1)
                env[k.decode(errors="replace")] = v.decode(errors="replace")
        _ENV_CACHE[pid] = env
    return _ENV_CACHE[pid]


def _in(pid: int, fallback: list[str], cmd: list[str], **kw):
    """Run cmd in the container whose first process is pid, with its environment; if nsenter can't, `docker exec`
    (fallback is the docker command's prefix, e.g. ["docker", "exec", "-i", cid])."""
    try:
        r = subprocess.run([*_ns(pid), *cmd], env=_container_env(pid), capture_output=True,
                           timeout=kw.pop("timeout", 600), **kw)
        if r.returncode not in (126, 127):  # 126/127: nsenter or the command couldn't run
            return r
    except OSError:
        pass
    return subprocess.run([*fallback, *cmd], capture_output=True, timeout=600, **kw)


_MINIO_PID: list = []


def _minio_pid() -> int:
    if not _MINIO_PID:
        _MINIO_PID.append(int(_run(["docker", "inspect", "-f", "{{.State.Pid}}", ss.SHARED_MINIO]).stdout.strip()))
    return _MINIO_PID[0]


def _cgroup_pids(st) -> list[str]:
    """The app container's processes (host pids), from its cgroup: the set `docker top` lists, without the ~2 s a
    docker command costs under load. Falls back to `docker top` if the cgroup can't be read."""
    try:
        if not getattr(st, "cgroup", None):
            rel = Path(f"/proc/{st.pid}/cgroup").read_text().splitlines()[0].split(":", 2)[2]
            st.cgroup = Path("/sys/fs/cgroup") / rel.lstrip("/")
        pids = [p for p in (st.cgroup / "cgroup.procs").read_text().split() if p]
        if pids:
            return pids
    except (OSError, IndexError):
        pass
    return _run(["docker", "top", st.cid, "-eo", "pid"]).stdout.split()[1:]


def _docker_api(method: str, path: str) -> int:
    """One call to the Docker daemon's API over its socket (the CLI costs ~1 s just to start under load)."""
    import http.client  # noqa: PLC0415
    import socket  # noqa: PLC0415

    class Conn(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(120)
            self.sock.connect("/var/run/docker.sock")

    c = Conn("localhost")
    c.request(method, path)
    status = c.getresponse().status
    c.close()
    return status


def _pause(*cids: str) -> None:
    for c in cids:
        if _docker_api("POST", f"/containers/{c}/pause") not in (204, 304):
            _run(["docker", "pause", c])


def _unpause(*cids: str) -> None:
    for c in cids:
        if _docker_api("POST", f"/containers/{c}/unpause") not in (204, 304):
            _run(["docker", "unpause", c], check=False)


def _processes(st) -> list:
    """env_fingerprint.processes (host pid, user, argv, redacted args), with the pids from the cgroup."""
    users = {}
    with open(f"/proc/{st.pid}/root/etc/passwd") as fh:
        for ln in fh:
            f = ln.split(":")
            if len(f) > 2:
                users.setdefault(f[2], f[0])
    out = []
    for hp in _cgroup_pids(st):
        try:
            argv = [a.decode(errors="replace") for a in open(f"/proc/{hp}/cmdline", "rb").read().split(b"\0")[:-1]]
            uid = next(ln.split()[1] for ln in open(f"/proc/{hp}/status") if ln.startswith("Uid:"))
        except (OSError, StopIteration):
            continue
        args = " ".join(argv) or "[zombie]"
        for rx, rep in fpr.REDACT:
            args = rx.sub(rep, args)
        if not fpr.PROC_IGNORE.search(args):
            out.append((hp, users.get(uid, uid), argv, args))
    return out


def _procs(st: Stack) -> dict:
    """{(host pid, start time): {"ppid", "uid", "args"}} for the app container's processes."""
    out = {}
    for hp in _cgroup_pids(st):
        try:
            fields = Path(f"/proc/{hp}/stat").read_text().rsplit(")", 1)[1].split()
            argv = [a.decode(errors="replace") for a in Path(f"/proc/{hp}/cmdline").read_bytes().split(b"\0")[:-1]]
            uid = next(ln.split()[1] for ln in Path(f"/proc/{hp}/status").read_text().splitlines() if ln.startswith("Uid:"))
        except (OSError, StopIteration, IndexError):
            continue
        args = " ".join(argv) or "[zombie]"
        out[(int(hp), int(fields[19]))] = {"ppid": int(fields[1]), "uid": uid, "args": args}
    return out


def _redact(args: str) -> str:
    for rx, rep in fpr.REDACT:
        args = rx.sub(rep, args)
    return args[:300]


def _service(st: Stack, procs: dict) -> dict:
    """The running service: its processes, the running binary's hash against the file's, and (in memory only) whether
    TEST_DATABASE_URL is set in its environment, which says whether dev or root started it (as state_store records)."""
    rows = []
    for (hp, start), p in procs.items():
        if p["args"].strip() != SERVICE_ARGS:
            continue
        try:
            env = Path(f"/proc/{hp}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        rows.append({"pid": hp, "start": start, "exe_sha256": fpr.sha_file(f"/proc/{hp}/exe", nofollow=False),
                     "test_database_url_set": any(e.startswith(b"TEST_DATABASE_URL=") and len(e) > 18 for e in env)})
    disk = fpr.sha_file(f"/proc/{st.pid}/root/app/model-registry/model-registry")
    return {"procs": rows, "disk_sha256": disk}


def _listening_8080(st: Stack) -> bool:
    for fn in ("tcp", "tcp6"):
        try:
            lines = Path(f"/proc/{st.pid}/net/{fn}").read_text().splitlines()[1:]
        except OSError:
            continue
        if any(f[3] == "0A" and f[1].endswith(":1F90") for f in (ln.split() for ln in lines)):
            return True
    return False


def _kill(keys, seconds: int = 15, init: int = 0) -> None:
    """SIGKILL these (host pid, start time) processes and wait until they're gone; never `init`, the container's
    first process, whose end would stop the container."""
    keys = [k for k in keys if k[0] != init]
    for pid, _ in keys:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.time() + seconds
    while time.time() < deadline:
        alive = []
        for pid, start in keys:
            try:
                f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                if int(f[19]) == start and f[0] != "Z":
                    alive.append(pid)
            except (OSError, IndexError):
                pass
        if not alive:
            return
        time.sleep(0.2)


def _open_for_writing(st: Stack, keys) -> set[str]:
    """Container paths (relative) that these processes hold open for writing."""
    out = set()
    for pid, _ in keys:
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
                flags = int(next(ln.split()[1] for ln in Path(f"/proc/{pid}/fdinfo/{fd}").read_text().splitlines()
                                 if ln.startswith("flags:")), 8)
            except (OSError, StopIteration, ValueError):
                continue
            if target.startswith("/") and flags & 3 and not target.startswith(("/dev/", "/proc/")):
                out.add(target.removesuffix(" (deleted)").lstrip("/"))
    return out


def _psql(st: Stack, db: str, sql: str, timeout: int = 120):
    return _in(st.pg_pid(), ["docker", "exec", "-i", st.pg], ["psql", "-U", "postgres", "-X", "-q", "-A", "-t", "-v",
               "ON_ERROR_STOP=1", "-d", db, "-f", "-"], input=sql, text=True, timeout=timeout)


def _mc(st: Stack, script: str, timeout: int = 300, stdin: str | None = None):
    """A shell script run in the shared MinIO with its admin login set for `mc` (as alias x), never printed."""
    return _in(_minio_pid(), ["docker", "exec", "-i", ss.SHARED_MINIO], ["sh", "-c", ss.MC_ENV + script],
               input=stdin, text=True, timeout=timeout)


def _buckets(st: Stack) -> dict:
    """{role/key: "size=… md5=…"} for the stack's two buckets, plus a count per bucket. A single-part object's ETag is
    its content's MD5; a multipart one's ("…-N") isn't, so its content is hashed, and a re-upload compares equal."""
    out, multi = {}, []
    r = _mc(st, "; ".join(f'echo "@@ {role}"; mc --insecure ls --recursive --json "x/{role}-{st.suffix}"; echo "@@rc $?"'
                          for role in fpr.BUCKETS))  # both listings in one `docker exec`
    parts: dict[str, list[str]] = {}
    ok: set[str] = set()
    cur = None
    for ln in r.stdout.splitlines():
        if ln.startswith("@@ "):
            cur = ln[3:]
            parts[cur] = []
        elif ln.startswith("@@rc "):
            if ln == "@@rc 0" and cur:
                ok.add(cur)
        elif cur:
            parts[cur].append(ln)
    for role in fpr.BUCKETS:
        items = [json.loads(ln) for ln in parts.get(role, []) if ln.startswith("{")]
        if role not in ok or any(i.get("status") != "success" for i in items):
            out[f"{role}:_error"] = "listing failed"
            continue
        files = [i for i in items if i.get("type") == "file"]
        out[f"{role}:objects"] = str(len(files))
        for i in files:
            etag = str(i.get("etag", "?")).strip('"')
            out[f"{role}/{i['key']}"] = f"size={i.get('size')} md5={etag}"
            if "-" in etag:
                multi.append((role, i["key"]))
    if multi:
        script = "".join(f'mc --insecure cat {shlex.quote(f"x/{role}-{st.suffix}/{key}")} | md5sum | cut -c1-32\n'
                         for role, key in multi)
        r = _mc(st, "sh -s", stdin=script)
        sums = r.stdout.split()
        for (role, key), md5 in zip(multi, sums if len(sums) == len(multi) else [None] * len(multi)):
            out[f"{role}/{key}"] = out[f"{role}/{key}"].split(" md5=")[0] + f" md5={md5 or 'ERR'}"
    return out


def _restore_buckets(st: Stack, saved: dict) -> str:
    """Put back only the objects that changed or went missing since the save (from the mirror inside the shared MinIO),
    and remove those that were added: unchanged objects are never touched."""
    now = _buckets(st)
    if now == saved:
        return "same"
    obj = lambda d: {k for k in d if "/" in k and ":" not in k.split("/", 1)[0]}  # noqa: E731  (not the counts)
    put = sorted(k for k in obj(saved) if now.get(k) != saved[k])
    drop = sorted(k for k in obj(now) if k not in saved)
    lines = [f"mc --insecure cp --quiet {shlex.quote(f'{st.minio_tmp}/{k}')} "
             f"{shlex.quote(f'x/{k.split(chr(47), 1)[0]}-{st.suffix}/{k.split(chr(47), 1)[1]}')} >/dev/null" for k in put]
    lines += [f"mc --insecure rm --quiet {shlex.quote(f'x/{k.split(chr(47), 1)[0]}-{st.suffix}/{k.split(chr(47), 1)[1]}')} "
              ">/dev/null" for k in drop]
    r = _mc(st, "sh -se", stdin="\n".join(lines) + "\n")
    return f"{len(put)} put back, {len(drop)} removed" + ("" if r.returncode == 0 else f" (exit {r.returncode})")


# env_fingerprint.dbstate in one round trip: the same queries, run by one shell inside the Postgres container (it takes
# ~7 `docker exec`s, a few seconds each under load, and the state summary needs it 3–4 times per point).
_TABLES_SQL = (r"select format($q$select %L, count(*), md5(coalesce(string_agg(t::text, E'\n' order by t::text),'')) "
               r"from %s t$q$, tbl, tbl) from (select format('%I.%I', schemaname, tablename) as tbl from pg_tables "
               f"where schemaname not in {fpr.PG_SYS} order by 1) x" "\n\\gexec\n")
_DB_SCRIPT = (
    'T=$(printf "\\t"); P() { psql -U "${POSTGRES_USER:-postgres}" -X -q -A -t -F "$T" -v ON_ERROR_STOP=1 -d "$1"; }\n'
    "echo @@G; P postgres <<'EOSQL'\n" + fpr.SQL_GLOBAL + "\nEOSQL\n"
    "P postgres <<'EOSQL' | while IFS= read -r db; do\nselect datname from pg_database where not datistemplate order by 1;\nEOSQL\n"
    '  echo "@@D $db"; P "$db" <<\'EOSQL\'\n' + fpr.SQL_DB + "\nEOSQL\n"
    '  echo "@@T $db"; P "$db" <<\'EOSQL\'\n' + _TABLES_SQL + "EOSQL\n"
    "done\n")


def dbstate_fast(st: Stack) -> dict:
    """{key: value} exactly as env_fingerprint.dbstate gives it, from one `docker exec`. Retried: under load a psql
    can fail to connect (exit 2)."""
    for attempt in range(3):
        r = _in(st.pg_pid(), ["docker", "exec", "-i", st.pg], ["sh", "-s"], input=_DB_SCRIPT, text=True, timeout=300)
        if r.returncode == 0:
            break
        time.sleep(3)
    if r.returncode:
        return {"_error": f"database summary exit {r.returncode}"}
    out, dbs, sec, db, schema = {}, [], None, None, {}
    for ln in r.stdout.splitlines():
        if ln.startswith("@@"):
            sec, _, db = ln[2:].partition(" ")
            if sec == "D":
                schema[db] = hashlib.sha256()
            continue
        if not ln:
            continue
        f = ln.split("\t")
        if sec == "G":
            if f[0] == "db":
                dbs.append(f[1])
                out[f"dbacl:{f[1]}"] = f"owner={f[2]} acl={f[3]} allowconn={f[4]}"
            elif f[0] == "role":
                out[f"role:{f[1]}"] = " ".join(f"{k}={v}" for k, v in zip(
                    ("super", "inherit", "createrole", "createdb", "login", "replication", "bypassrls"), f[2:]))
            elif f[0] == "member":
                out[f"member:{f[1]}:{f[2]}"] = f"admin={f[3]}"
            elif f[0] == "hba":
                out["pg_hba"] = f[1]
        elif sec == "D":
            if f[0] == "S":
                schema[db].update("\t".join(f).encode() + b"\n")
            elif f[0] == "acl":
                out[f"{db}:acl:{f[1]}"] = f"kind={f[2]} owner={f[3]} acl={f[4]}"
            elif f[0] == "nsp":
                out[f"{db}:schema-acl:{f[1]}"] = f"owner={f[2]} acl={f[3]}"
            elif f[0] == "seq":
                out[f"{db}:seq:{f[1]}"] = f[2]
        elif sec == "T":
            out[f"{db}:table:{f[0]}"] = f"rows={f[1]} md5={f[2]}"
    out["databases"] = ",".join(sorted(dbs))
    for d, h in schema.items():
        out[f"{d}:schema"] = h.hexdigest()
    return out


def _pipes(pid) -> set[str]:
    out = set()
    try:
        for fd in os.listdir(f"/proc/{pid}/fd"):
            try:
                t = os.readlink(f"/proc/{pid}/fd/{fd}")
            except OSError:
                continue
            if t.startswith("pipe:"):
                out.add(t)
    except OSError:
        pass
    return out


def service_waiters(procs) -> set:
    """Host pids of processes whose input is a pipe the service's process tree holds: the `tail` in a replayed
    `sudo /app/restart.sh | tail`, which only waits for the service's output and ends whenever the service is
    restarted (residue-undo-scope §4). They do no work and can't be brought back, so they're left out of the comparison."""
    held = set()
    for hp, _, _, args in procs:
        if SERVICE_TREE.search(args.strip()):
            held |= _pipes(hp)
    out = set()
    for hp, _, _, args in procs:
        if SERVICE_TREE.search(args.strip()):
            continue
        try:
            t = os.readlink(f"/proc/{hp}/fd/0")
        except OSError:
            continue
        if t in held:
            out.add(hp)
    return out


# Opt-in (bench.py's db_detect, off by default): skip a full database hash when a cheap detector says nothing moved since
# the last full hash. The final check of every restore always takes the full hash, so a detector that misses a change
# shows up there as an inexact restore. A detector that moves without a real change only costs the full hash.
DB_DETECT = False
_DETECT_SCRIPT = (
    'T=$(printf "\\t"); P() { psql -U "${POSTGRES_USER:-postgres}" -X -q -A -t -F "$T" -v ON_ERROR_STOP=1 -d "$1"; }\n'
    "P postgres <<'EOSQL'\nselect pg_current_wal_insert_lsn();\n"
    "select datname, tup_inserted, tup_updated, tup_deleted from pg_stat_database where datname is not null order by 1;\nEOSQL\n"
    "P postgres <<'EOSQL' | while IFS= read -r db; do\nselect datname from pg_database where not datistemplate order by 1;\nEOSQL\n"
    '  echo "@@D $db"; P "$db" <<\'EOSQL\'\n'
    "select schemaname, sequencename, last_value from pg_sequences order by 1, 2;\n"
    "select 'unlogged', count(*) from pg_class where relpersistence = 'u';\nEOSQL\n"
    "done\n")


def db_detector(st: Stack) -> str | None:
    """A hash of the WAL position, the databases' row counters, and every sequence's value. None if it can't be trusted
    here: an unlogged table writes no WAL, so the full hash is needed."""
    r = _in(st.pg_pid(), ["docker", "exec", "-i", st.pg], ["sh", "-s"], input=_DETECT_SCRIPT, text=True, timeout=120)
    if r.returncode or re.search(r"^unlogged\t[1-9]", r.stdout, re.M):
        return None
    return hashlib.sha256(r.stdout.encode()).hexdigest()


def _db_now(st: Stack, sv: dict) -> dict:
    """The database summary now: with DB_DETECT, the save's, if the detector hasn't moved since the save."""
    if DB_DETECT and sv.get("db_detect") is not None and db_detector(st) == sv["db_detect"]:
        st.detect_hits = getattr(st, "detect_hits", 0) + 1
        return sv["summary"].get("db") or {}
    st.detect_misses = getattr(st, "detect_misses", 0) + 1
    return summary_section(st, "db")


def summary(st: Stack, db: dict | None = None) -> dict:
    """The state summary (everything but the files, which are compared through the listings): processes, the service,
    the network, Postgres and the buckets, each as {key: value}. No secret values (env_fingerprint's rules)."""
    procs = [p for p in _processes(st) if not TRANSIENT.search(p[3])]
    waiters = service_waiters(procs)
    procs = [p for p in procs if p[0] not in waiters]
    out = {}
    for sec, fn in (("proc", lambda: fpr.procstate(procs)), ("service", lambda: fpr.servicestate(st.pid, procs)),
                    ("net", lambda: fpr.netstate(st.pid))):
        try:
            out[sec] = {k: v for _, k, v in fn()}
        except Exception as e:  # noqa: BLE001  no output in the message (run() never includes stderr)
            out[sec] = {"_error": f"{type(e).__name__}: {e}"}
    out["db"] = dbstate_fast(st) if db is None else db
    out["s3"] = _buckets(st)
    return out


# ---------------------------------------------------------------- state dedup
DEDUP_DETAIL = False  # opt-in, off by default: same_state notes the changed paths' names on its Stack (st.dedup_detail)


def same_state(st: Stack, last: dict) -> tuple[bool, dict | None, str]:
    """Is the machine exactly as it was at the last scored point's save (`last`: its files listing, summary and
    service)? Then that score is this point's too. (same, the summary just taken, why not). Requires: nothing the replay
    left running (no build or restart in flight); every path visibly the same, content included; the summary equal
    (both databases, buckets, processes, network, the service); and the same service process, so its memory carried
    over too. The summary is passed on to save_point when the state differs."""
    procs = _procs(st)
    if _unsettled(procs):
        return False, None, "a build or restart still running"
    svc = _service(st, procs)
    if sorted((p["pid"], p["start"]) for p in svc["procs"]) != sorted((p["pid"], p["start"]) for p in last["service"]["procs"]):
        return False, None, "a different service process"
    keep = getattr(st, "keep", ())
    fd = compare_files(last["files"], listing(st.upper, st.skip), st.lowers, str(st.saved), st.upper,
                       skip=(*VOLATILE, *keep))
    if fd:
        if DEDUP_DETAIL:  # opt-in (bench.py's dedup_detail): which paths, and would the rest of the state have matched?
            st.dedup_detail = {"paths": [[p, w] for p, w in fd[:200]], "count": len(fd),
                               "summary_differs": sorted(compare_sections(last["summary"], summary(st)))}
        return False, None, f"{len(fd)} paths changed"
    now = summary(st)
    d = compare_sections(last["summary"], now)
    return (not d), now, ("" if not d else "summary: " + ",".join(sorted(d)))


# ---------------------------------------------------------------- save and restore
def save_point(st: Stack, pre_summary: dict | None = None) -> dict:
    """Save the state just before a scoring point. Returns the handle restore_point needs; its "info" is the record."""
    t_all = time.time()
    info: dict = {}
    procs = _procs(st)
    builds = _unsettled(procs)
    if builds:  # the replay's own build or restart, still running: let it finish first
        info["waited_for_builds"] = sorted({_redact(a)[:120] for a in builds})[:6]
        t0 = time.time()
        while builds and time.time() - t0 < BUILD_WAIT:
            time.sleep(2)
            procs = _procs(st)
            builds = _unsettled(procs)
        info["waited_for_builds_seconds"] = round(time.time() - t0, 1)
        info["builds_still_running"] = len(builds)
    # DB_DETECT: nothing moved since the last restore's full hash, before this save's CHECKPOINT moves the WAL position
    db_cached = None
    if DB_DETECT:
        last = getattr(st, "db_last", None)
        if last is not None and last[0] is not None and db_detector(st) == last[0]:
            db_cached = last[1]
        info["db_hash_reused"] = db_cached is not None
    svc = _service(st, procs)
    running_bin = None
    if svc["procs"] and any(p["exe_sha256"] != svc["disk_sha256"] for p in svc["procs"]):
        # the agent built without restarting: keep the binary that runs, for a restart after scoring
        running_bin = st.work / "running-service.bin"
        shutil.copyfile(f"/proc/{svc['procs'][0]['pid']}/exe", running_bin)
    info["service_running"] = len(svc["procs"])
    info["running_binary_differs_from_file"] = running_bin is not None
    _in(st.pg_pid(), ["docker", "exec", st.pg], ["psql", "-U", "postgres", "-qAtc", "CHECKPOINT"], text=True)
    t0 = time.time()
    _pause(st.cid, st.pg)
    try:
        files = listing(st.upper, st.skip)
        info["files_copied"] = _sync_saved(st, files)
        _run(["tar", "-C", st.pgdata, "--numeric-owner", "-cpf", str(st.work / "pg.tar"), "."])
    finally:
        _unpause(st.cid, st.pg)
    info["paused_seconds"] = round(time.time() - t0, 1)
    info["upper_entries"] = len(files)
    t0 = time.time()
    dbs = _dump_databases(st)
    info["db_dump_seconds"] = round(time.time() - t0, 1)
    t0 = time.time()
    r = _mc(st, f'mkdir -p {st.minio_tmp}/models {st.minio_tmp}/backups && '
                f'mc --insecure mirror --quiet --overwrite --remove x/models-{st.suffix} {st.minio_tmp}/models >/dev/null && '
                f'mc --insecure mirror --quiet --overwrite --remove x/backups-{st.suffix} {st.minio_tmp}/backups >/dev/null')
    if r.returncode:
        raise RuntimeError(f"bucket mirror exit {r.returncode}")
    info["s3_seconds"] = round(time.time() - t0, 1)
    t0 = time.time()
    db_detect = db_detector(st) if DB_DETECT else None  # read before the hash: a write after it only costs a full hash later
    if pre_summary is not None:  # the dedup check's, taken just before: nothing ran since
        summ = pre_summary
    else:
        summ = summary(st) if db_cached is None else summary(st, db_cached)
    info["summary_seconds"] = round(time.time() - t0, 1)
    # The processes and the service as scoring finds them, which the restore measures "started by scoring" against:
    # anything that started during the save (a replayed restart finishing, say) belongs to the saved state.
    end_procs = _procs(st)
    end_svc = _service(st, end_procs)
    if [p["exe_sha256"] for p in end_svc["procs"]] != [p["exe_sha256"] for p in svc["procs"]]:
        info["service_changed_during_save"] = True
        running_bin = None
        if end_svc["procs"] and any(p["exe_sha256"] != end_svc["disk_sha256"] for p in end_svc["procs"]):
            running_bin = st.work / "running-service.bin"
            shutil.copyfile(f"/proc/{end_svc['procs'][0]['pid']}/exe", running_bin)
        info["service_running"] = len(end_svc["procs"])
        info["running_binary_differs_from_file"] = running_bin is not None
    svc = end_svc  # same binary, perhaps a new process: the restore checks the service by these pids
    info["save_seconds"] = round(time.time() - t_all, 1)
    st.points += 1
    return {"info": info, "files": files, "procs": end_procs, "service": svc, "running_bin": running_bin,
            "summary": summ, "dbs": dbs, "db_detect": db_detect}


_DUMP_SCRIPT = (
    'set -e; D=$(mktemp -d); trap \'rm -rf "$D"\' EXIT\n'
    'psql -U postgres -X -A -t -d postgres -c "select datname from pg_database where not datistemplate order by 1" > "$D/.dbs"\n'
    'while IFS= read -r db; do pg_dump -U postgres --data-only --disable-triggers -d "$db" -f "$D/db-$db.sql"; done < "$D/.dbs"\n'
    'tar -C "$D" -cf - .\n')


def _dump_databases(st: Stack) -> list[str]:
    """A data-only dump of every database into the work folder (db-<name>.sql), in one `docker exec`. Returns the
    databases' names."""
    for attempt in range(3):  # under load a psql or pg_dump can fail to connect (exit 2)
        r = _in(st.pg_pid(), ["docker", "exec", "-i", st.pg], ["sh", "-s"], input=_DUMP_SCRIPT.encode(), timeout=600)
        if r.returncode == 0:
            break
        time.sleep(3)
    if r.returncode:
        raise RuntimeError(f"database dump exit {r.returncode}")
    dbs = []
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for m in tf.getmembers():
            name = os.path.basename(m.name)
            if m.isfile() and name.startswith("db-") and name.endswith(".sql"):
                (st.work / name).write_bytes(tf.extractfile(m).read())
                dbs.append(name[3:-4])
    return sorted(dbs)


def _db_plan(before: dict, after: dict) -> tuple[str, list[str]]:
    """"same", "rows" (only table contents or sequence values changed: reload those databases in place) or "swap"."""
    diff = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    if not diff:
        return "same", []
    dbs = set()
    for k in diff:
        m = re.match(r"^([^:]+):(table|seq):", k)
        if not m or k.startswith("_error"):
            return "swap", []
        dbs.add(m.group(1))
    return "rows", sorted(dbs)


def _reload_rows(st: Stack, db: str) -> bool:
    """Empty every table of db and load the saved rows and sequence values, in one transaction."""
    tables = _psql(st, db, "select string_agg(format('%I.%I', schemaname, tablename), ', ' order by 1) from pg_tables "
                           "where schemaname not in ('pg_catalog', 'information_schema')").stdout.strip()
    sql = ("SET lock_timeout = '20s';\nSET session_replication_role = replica;\n"
           + (f"TRUNCATE TABLE {tables};\n" if tables else "")
           + (st.work / f"db-{db}.sql").read_text(errors="surrogateescape"))
    r = _in(st.pg_pid(), ["docker", "exec", "-i", st.pg], ["psql", "-U", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=1",
            "--single-transaction", "-d", db, "-f", "-"], input=sql, text=True, timeout=300, errors="surrogateescape")
    return r.returncode == 0


def _into_container(st: Stack, sources: list[tuple[str, list[str]]]) -> int:
    """Copy (root, [relative paths]) entries into the container at the same paths, in one tar stream, so folder
    times are set after their contents. Returns tar's exit code inside the container."""
    if not any(rels for _, rels in sources):
        return 0
    stream = st.work / "restore.tar"
    with open(stream, "wb") as fh:
        for i, (root, rels) in enumerate(sources):
            if rels:
                r = subprocess.run(_tar_out(root, rels, st.work / f"restore-{i}.nul"), stdout=fh,
                                   stderr=subprocess.DEVNULL, timeout=900)
                if r.returncode > 1:
                    raise RuntimeError(f"tar of the saved files exit {r.returncode}")
    with open(stream, "rb") as fh:
        r = subprocess.run(st.in_container("tar", "-C", "/", "-i", "--delay-directory-restore", "--numeric-owner",
                                           "--xattrs", "--xattrs-include=*", "-xpf", "-"),
                           stdin=fh, capture_output=True, timeout=900)
    return r.returncode


def restore_files(st: Stack, before: dict, after: dict, skip=()) -> tuple[dict, int]:
    """Put the files back as they were at the save (`before`, copied in st.saved), from the listing `after`: delete what
    was added, then copy back, in one tar stream, what changed or went missing. Returns the plan and tar's exit code."""
    if not before or not after:
        raise RuntimeError("an empty listing of the upper folder: refusing to restore from it")
    plan = plan_files(before, after, st.lowers, skip=skip)
    if len(plan["remove"]) > 500:
        raise RuntimeError(f"{len(plan['remove'])} paths to remove: too many to trust, refusing")
    if plan["remove"]:
        _run(st.in_container("sh", "-c", "cd / && xargs -0 -r rm -rf --"), input=_nul(plan["remove"]), text=False,
             say_err=True)
    by_layer: dict[str, list[str]] = {}
    for layer, rel in plan["from_lower"]:
        by_layer.setdefault(layer, []).append(rel)
    return plan, _into_container(st, [(str(st.saved), plan["from_saved"]), *sorted(by_layer.items())])


def restore_point(st: Stack, sv: dict) -> dict:
    """Undo what scoring changed since save_point, then compare the state summary and the files with the save."""
    t_all = time.time()
    info: dict = {}
    # 1. Processes the scoring started (never the health checks), and processes it ended.
    procs = _procs(st)
    new = {k: p for k, p in procs.items() if k not in sv["procs"] and not TRANSIENT.search(p["args"])}
    lost = {k: p for k, p in sv["procs"].items() if k not in procs and not TRANSIENT.search(p["args"])}
    old_service = {(p["pid"], p["start"]) for p in sv["service"]["procs"]}
    replaced = bool(old_service) and (not old_service <= set(procs)
                                      or any(p["args"].strip() == SERVICE_ARGS for p in new.values()))
    _kill(list(new), init=st.pid)
    info["killed"] = sorted(_redact(p["args"]) for p in new.values())
    info["ended_by_scoring"] = sorted(_redact(p["args"]) for p in lost.values() if not SERVICE_TREE.search(p["args"].strip()))
    info["service_replaced"] = replaced
    # 2. What changed in Postgres and in the files. A changed file the surviving service holds open for writing (its
    #    SQLite file, say) is put back with the service stopped and restarted; one another surviving process writes to
    #    (a log) is left alone. The service log is never touched.
    t0 = time.time()
    db_after = _db_now(st, sv) if DB_DETECT else summary_section(st, "db")
    mode, dbs = _db_plan(sv["summary"].get("db") or {}, db_after)
    survivors = {k: p for k, p in _procs(st).items() if k not in new}
    tree = [k for k, p in survivors.items() if SERVICE_TREE.search(p["args"].strip())]
    live_service = _open_for_writing(st, tree)
    live_other = _open_for_writing(st, [k for k in survivors if k not in tree]) - live_service
    after = listing(st.upper, st.skip)
    skip = (*VOLATILE, *st.keep, *sorted(live_other))
    plan = plan_files(sv["files"], after, st.lowers, skip=skip)
    touched = set(plan["remove"]) | set(plan["from_saved"]) | {r for _, r in plan["from_lower"]}
    held = sorted(r for r in touched if _under(r, live_service) and not _under(r, VOLATILE))
    restart = bool(old_service) and (replaced or mode == "swap" or bool(held))
    info["files_held_by_service"] = held[:20]
    if restart:  # stop what's left of the service tree before the database and the files
        _stop_service(st)
    # 3. Postgres: reload changed tables in place, or swap the cluster back if more than rows changed.
    info["db"] = mode if mode != "rows" else f"rows: {', '.join(dbs)}"
    if mode == "rows" and not all(_reload_rows(st, db) for db in dbs):
        mode, info["db"] = "swap", "swap (the in-place reload failed)"
        if old_service and not restart:
            restart = True
            _stop_service(st)
    if mode == "swap":
        ss.swap_pg(st.s, st.work / "pg.tar")
        st._pgpid = None  # the restarted cluster has a new first process
    info["db_seconds"] = round(time.time() - t0, 1)
    # 4. Files: what the scoring changed, back to the saved copy or the image; what it added, removed.
    t0 = time.time()
    plan, rc = restore_files(st, sv["files"], after, skip)
    info["files"] = {"removed": len(plan["remove"]), "from_saved": len(plan["from_saved"]),
                     "from_image": len(plan["from_lower"]), "tar_exit": rc}
    info["files_skipped"] = plan["skipped"][:50]
    info["files_opaque"] = plan["opaque"][:50]
    info["files_seconds"] = round(time.time() - t0, 1)
    # 5. Buckets, if anything in them changed.
    t0 = time.time()
    info["s3"] = _restore_buckets(st, sv["summary"].get("s3") or {})
    info["s3_seconds"] = round(time.time() - t0, 1)
    # 6. The service, if the scoring replaced it: the binary that was running, started by the account that started it.
    t0 = time.time()
    info["service_restarted"] = restart
    if restart:
        before_restart = _procs(st)
        if sv["running_bin"] is not None:  # the running binary differed from the file: start that one, then put the file back
            with open(sv["running_bin"], "rb") as fh:
                _run(st.in_container("sh", "-c", "cat > /app/model-registry/model-registry"), stdin=fh, text=False,
                     say_err=True)
        ss.restart_service(st.cid, not any(p["test_database_url_set"] for p in sv["service"]["procs"]), info)
        if sv["running_bin"] is not None:
            rels = [r for r in ("app/model-registry", "app/model-registry/model-registry") if r in sv["files"]]
            _run(st.in_container("rm", "-f", "/app/model-registry/model-registry"), say_err=True)
            _into_container(st, [(str(st.saved), rels)])
        after_restart = _procs(st)
        info["ended_by_restart"] = sorted(_redact(p["args"]) for k, p in before_restart.items()
                                          if k not in after_restart and not TRANSIENT.search(p["args"])
                                          and not SERVICE_TREE.search(p["args"].strip()))
        # 6b. The restart itself writes: restart.sh, and the service at start-up (its backup pass; an agent's code may
        #     log or record its start). Undo that too, with the service running: rows in place, buckets, and files,
        #     those the service holds open rewritten in place so it keeps writing to the same file.
        if SETTLE is None:
            time.sleep(RESTART_SETTLE)
        else:  # bench.py's test of a shorter wait; off in production
            info["settle"] = SETTLE(st)
        info["after_restart"] = _undo_running(st, sv, skip)
    info["service_seconds"] = round(time.time() - t0, 1)
    # 7. The check: the state summary and the files, against the save.
    t0 = time.time()
    detect_final = db_detector(st) if DB_DETECT else None  # read before the hash, as at the save
    now = summary(st)  # always the full hash
    if DB_DETECT:
        st.db_last = (detect_final, now["db"])
    diffs = compare_sections(sv["summary"], now)
    if "s3" in diffs:  # sizes and ETags, never contents
        d, b4 = diffs["s3"], sv["summary"].get("s3") or {}
        d["values"] = {k: [b4.get(k), now["s3"].get(k)] for k in (d["differ"] + d["only_before"] + d["only_after"])[:10]}
    accepted = {}
    if restart and "service" in diffs:  # sudo sets per-call variables: the environment's values may differ, never its names
        d = diffs["service"]
        if not d["only_before"] and not d["only_after"] and all(k.endswith(".env_sha256") for k in d["differ"]):
            accepted["service"] = diffs.pop("service")
    final = listing(st.upper, st.skip)
    fdiff = compare_files(sv["files"], final, st.lowers, str(st.saved), st.upper, skip=skip)
    if fdiff:
        diffs["files"] = {"differ": [f"{p} ({w})" for p, w in fdiff[:50]], "count": len(fdiff)}
    info["check_seconds"] = round(time.time() - t0, 1)
    info["differences"] = diffs
    info["accepted_differences"] = accepted
    info["state_equal"] = not diffs and not plan["opaque"] and rc == 0
    # the service as the next point will find it (for state dedup: a later point equal to this one must have it too)
    info["service_after"] = [[p["pid"], p["start"]] for p in _service(st, _procs(st))["procs"]]
    info["restore_seconds"] = round(time.time() - t_all, 1)
    return info


RESTART_SETTLE = 5  # seconds after the restarted service is healthy, for its start-up pass to finish
SETTLE = None  # bench.py can put a function here, in place of that fixed wait


def _rewrite_in_place(st: Stack, rel: str, e: Entry) -> None:
    """Put a regular file's saved content, owner, mode and time back into the same inode (a process holding it open,
    appending, keeps writing to the visible file)."""
    stamp = f"@{e.mtime_ns // 10**9}.{e.mtime_ns % 10**9:09d}"
    with open(st.saved / rel, "rb") as fh:
        _run(st.in_container("sh", "-c", 'cd / && cat > "$1" && chown "$2" "$1" && chmod "$3" "$1" && touch -m -d "$4" "$1"',
                             "sh", rel, f"{e.uid}:{e.gid}", f"{e.mode:o}", stamp),
             stdin=fh, text=False, say_err=True)


def _undo_running(st: Stack, sv: dict, skip) -> dict:
    """After a restart: undo what changed since the save, without stopping the service."""
    out: dict = {}
    mode, dbs = _db_plan(sv["summary"].get("db") or {}, _db_now(st, sv) if DB_DETECT else summary_section(st, "db"))
    out["db"] = mode if mode != "rows" else f"rows: {', '.join(dbs)}"
    if mode == "rows" and not all(_reload_rows(st, db) for db in dbs):
        out["db"] = "rows: the in-place reload failed"
    procs = _procs(st)
    held = _open_for_writing(st, [k for k, p in procs.items() if SERVICE_TREE.search(p["args"].strip())])
    after = listing(st.upper, st.skip)
    plan = plan_files(sv["files"], after, st.lowers, skip=(*skip, *sorted(held)))
    in_place, cannot = [], []
    for rel in sorted(held):
        if _under(rel, VOLATILE) or sv["files"].get(rel) == after.get(rel):
            continue
        e = sv["files"].get(rel)
        if e is not None and e.kind == "reg" and after.get(rel) is not None and after[rel].kind == "reg":
            _rewrite_in_place(st, rel, e)
            in_place.append(rel)
        else:
            cannot.append(rel)
    _, rc = restore_files(st, sv["files"], after, skip=(*skip, *sorted(held)))
    out["files"] = {"removed": len(plan["remove"]), "from_saved": len(plan["from_saved"]),
                    "from_image": len(plan["from_lower"]), "rewritten_in_place": in_place, "not_restorable": cannot,
                    "tar_exit": rc}
    out["s3"] = _restore_buckets(st, sv["summary"].get("s3") or {})
    return out


def _stop_service(st: Stack) -> None:
    """Kill the service and what restart.sh left with it (never other processes), and wait until port 8080 is free."""
    _kill([k for k, p in _procs(st).items() if SERVICE_TREE.search(p["args"].strip())], init=st.pid)
    for _ in range(60):
        if not _listening_8080(st):
            break
        time.sleep(0.5)


def summary_section(st: Stack, sec: str) -> dict:
    if sec == "db":
        return dbstate_fast(st)
    raise ValueError(sec)
