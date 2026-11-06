"""Save a model_registry stack's state once, and restore it into fresh stacks (plans/replay-free-scope.md).

Runs on the host (WSL or the cloud machine, as root), called from power_v0.py through save_state= / restore_state=.
A state is:
  - the app container's own changes: its overlay upper folder, tarred from the host (whiteouts and opaque folders
    listed separately), restored through `docker exec ... tar` in the fresh container;
  - the whole Postgres cluster: a copy of the db container's data folder, taken while the container is paused,
    restored by stopping the fresh db container, swapping the folder's contents and starting it again;
  - the stack's two buckets in the shared MinIO, mirrored to the host and back;
  - the service: restarted from the restored binary, by the same account that last restarted it.
Nothing secret is printed or stored in the manifest: the MinIO admin login is used only inside the MinIO container.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

SHARED_MINIO = "shared-minio"
PG_DATA = "/var/lib/postgresql/data"
MC_ENV = 'export MC_HOST_x="https://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@localhost:9000"; '


def run(cmd, check=True, timeout=900, **kw):
    r = subprocess.run(cmd, capture_output=True, text=kw.pop("text", True), timeout=timeout, **kw)
    if check and r.returncode != 0:
        err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode(errors="replace")
        raise RuntimeError(f"{cmd[:3]} exit {r.returncode}: {err.strip()[-300:]}")
    return r


STACK_ID_FILES = ("/tmp/.trajectory-id", "/etc/vertex/trajectory-id", "/app/model-registry/trajectory_id")


def bucket_suffix(project: str) -> str:
    """The s3-init script's cleaning of the compose project name (init/s3/init.sh)."""
    t = re.sub(r"[^a-z0-9-]", "-", project.lower())
    return re.sub(r"-+", "-", t).strip("-")


def app_cid_from_mountinfo(mountinfo: str) -> str:
    m = re.search(r"/containers/([0-9a-f]{64})/", mountinfo)
    if not m:
        raise RuntimeError("could not find the app container's id")
    return m.group(1)


def find_stack(app_cid: str) -> dict:
    fmt = '{{index .Config.Labels "com.docker.compose.project"}} {{.State.Pid}}'
    project, pid = run(["docker", "inspect", "-f", fmt, app_cid]).stdout.split()
    upper, mounts = None, []
    for line in Path(f"/proc/{pid}/mountinfo").read_text().splitlines():
        f = line.split()
        mounts.append(f[4].encode().decode("unicode_escape"))
        if f[4] == "/" and "upperdir=" in line:
            upper = re.search(r"upperdir=([^,\s]+)", line).group(1)
    if not upper:
        raise RuntimeError("no overlay upper folder for the app container")
    pg = run(["docker", "ps", "-q", "--no-trunc", "--filter", f"label=com.docker.compose.project={project}",
              "--filter", "label=com.docker.compose.service=postgres"]).stdout.split()
    if len(pg) != 1:
        raise RuntimeError(f"expected one postgres container in {project}, found {len(pg)}")
    fmt = '{{range .Mounts}}{{if eq .Destination "' + PG_DATA + '"}}{{.Source}}{{end}}{{end}}'
    pgdata = run(["docker", "inspect", "-f", fmt, pg[0]]).stdout.strip()
    if not pgdata or not Path(pgdata).is_dir():
        raise RuntimeError("postgres data folder not found on the host")
    return {"project": project, "suffix": bucket_suffix(project), "app": app_cid, "pid": pid, "upper": upper,
            "mounts": sorted(set(m for m in mounts if m != "/")), "pg": pg[0], "pgdata": pgdata}


def _under_mount(rel: str, mounts: list[str]) -> bool:
    p = "/" + rel
    return any(p == m or p.startswith(m.rstrip("/") + "/") for m in mounts)


def scan_upper(upper: str, mounts: list[str]) -> tuple[list[str], list[str], list[str]]:
    """(entries to tar, whiteouts = deleted paths, opaque folders), as paths relative to /, sorted."""
    keep, white, opaque = [], [], []
    for dirpath, dirnames, filenames in os.walk(upper):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, upper)
            if _under_mount(rel, mounts):
                continue
            st = os.lstat(full)
            if stat.S_ISCHR(st.st_mode) and st.st_rdev == 0:
                white.append(rel)
                continue
            if stat.S_ISDIR(st.st_mode):
                try:
                    if os.getxattr(full, "trusted.overlay.opaque", follow_symlinks=False) == b"y":
                        opaque.append(rel)
                except OSError:
                    pass
            keep.append(rel)
    return sorted(keep), sorted(white), sorted(opaque)


def _nul(paths: list[str], prefix: str = "") -> bytes:
    return b"".join((prefix + p).encode() + b"\0" for p in paths)


def service_info(cid: str) -> dict:
    """The running service: host pid, user, whether the running binary equals the file on disk, and whether
    TEST_DATABASE_URL is set in its environment (a boolean only: the value is never read out)."""
    out = run(["docker", "top", cid, "-eo", "pid,args"]).stdout.splitlines()[1:]
    rows = []
    for line in out:
        pid, _, args = line.strip().partition(" ")
        if args.strip() == "./model-registry":
            try:
                env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
                exe = hashlib.sha256(Path(f"/proc/{pid}/exe").read_bytes()).hexdigest()
                uid = Path(f"/proc/{pid}/status").read_text().split("Uid:")[1].split()[0]
            except OSError:
                continue
            rows.append({"uid": uid, "exe_sha256": exe,
                         "test_database_url_set": any(e.startswith(b"TEST_DATABASE_URL=") and len(e) > 18 for e in env)})
    disk = run(["docker", "exec", cid, "sha256sum", "/app/model-registry/model-registry"], check=False).stdout.split()
    return {"running": len(rows), "procs": rows, "disk_sha256": disk[0] if disk else None}


def save(app_cid: str, dest: Path, extra: dict | None = None) -> dict:
    """Save the stack's state into dest (which must not exist yet). Returns timings and sizes."""
    t_all = time.time()
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.mkdir(dest)  # claims the name atomically: a second save to the same name fails here
    s = find_stack(app_cid)
    info: dict = {"project": s["project"], "saved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **(extra or {})}
    info["service"] = service_info(app_cid)
    keep, white, opaque = scan_upper(s["upper"], s["mounts"])
    (dest / "whiteouts.nul").write_bytes(_nul(white))
    (dest / "opaque.nul").write_bytes(_nul(opaque))
    (dest / "entries.nul").write_bytes(_nul(keep, "./"))
    info.update(upper_entries=len(keep), whiteouts=len(white), opaque=len(opaque))
    run(["docker", "exec", s["pg"], "psql", "-U", "postgres", "-qAtc", "CHECKPOINT"], check=False)
    t0 = time.time()
    run(["docker", "pause", s["app"], s["pg"]])
    try:
        run(["tar", "-C", s["upper"], "--numeric-owner", "--xattrs", "--xattrs-exclude=trusted.*", "--no-recursion",
             "--null", "-T", str(dest / "entries.nul"), "-cpf", str(dest / "files.tar")])
        info["files_tar_seconds"] = round(time.time() - t0, 1)
        t1 = time.time()
        run(["tar", "-C", s["pgdata"], "--numeric-owner", "-cpf", str(dest / "pg.tar"), "."])
        info["pg_tar_seconds"] = round(time.time() - t1, 1)
    finally:
        run(["docker", "unpause", s["app"], s["pg"]], check=False)
    info["paused_seconds"] = round(time.time() - t0, 1)
    t0 = time.time()
    tmp = f"/tmp/power-state-{s['suffix']}"
    run(["docker", "exec", SHARED_MINIO, "sh", "-c", MC_ENV + f'rm -rf {tmp}; mkdir -p {tmp}/models {tmp}/backups && '
         f'mc --insecure mirror --quiet x/models-{s["suffix"]} {tmp}/models >/dev/null && '
         f'mc --insecure mirror --quiet x/backups-{s["suffix"]} {tmp}/backups >/dev/null'])
    run(["docker", "cp", f"{SHARED_MINIO}:{tmp}", str(dest / "s3")])
    run(["docker", "exec", SHARED_MINIO, "rm", "-rf", tmp], check=False)
    info["s3_seconds"] = round(time.time() - t0, 1)
    info["sizes_mb"] = {n: round((dest / n).stat().st_size / 1e6, 1) for n in ("files.tar", "pg.tar")}
    info["s3_objects"] = sum(len(f) for _, _, f in os.walk(dest / "s3"))
    info["save_seconds"] = round(time.time() - t_all, 1)
    info["complete"] = True
    (dest / "manifest.json").write_text(json.dumps(info, indent=2))
    return info


def _wait(cmd: list[str], seconds: int) -> bool:
    for _ in range(seconds):
        try:
            if run(cmd, check=False, timeout=10).returncode == 0:
                return True
        except subprocess.TimeoutExpired:  # a slow docker exec under load isn't an answer: ask again
            pass
        time.sleep(1)
    return False


def swap_pg(s: dict, pg_tar: Path) -> None:
    """Stop the stack's Postgres, swap its data folder's contents for a saved copy, start it again."""
    run(["docker", "stop", "-t", "30", s["pg"]])
    for child in Path(s["pgdata"]).iterdir():
        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    run(["tar", "-C", s["pgdata"], "--numeric-owner", "-xpf", str(pg_tar)])
    run(["docker", "start", s["pg"]])
    if not _wait(["docker", "exec", s["pg"], "pg_isready", "-U", "postgres"], 90):
        raise RuntimeError("postgres not ready after the restore")


def restart_service(app_cid: str, as_dev: bool, info: dict) -> None:
    """Start the service with /app/restart.sh: as dev (through its sudo rule, with TEST_DATABASE_URL emptied, as power_v0
    runs dev's commands) or as root; then wait until it's healthy. Notes who restarted it and whether it's healthy."""
    rc = 1
    if as_dev:
        rc = run(["docker", "exec", "-u", "dev", "-e", "TEST_DATABASE_URL=", app_cid, "bash", "--login", "-c",
                  "sudo -n /app/restart.sh </dev/null >/dev/null 2>&1"], check=False, timeout=120).returncode
        info["service_restarted_by"] = "dev" if rc == 0 else "root (dev's sudo failed)"
    if rc != 0:
        run(["docker", "exec", app_cid, "bash", "-c", "/app/restart.sh </dev/null >/dev/null 2>&1"],
            check=False, timeout=120)
        info.setdefault("service_restarted_by", "root")
    info["service_healthy"] = _wait(["docker", "exec", app_cid, "curl", "-sf", "-m", "2", "-o", "/dev/null",
                                     "http://localhost:8080/health"], 120)


def _rename_stack_id(app_cid: str, old: str, new: str) -> list[str]:
    """A restored state names the stack it was saved from. Control Tower writes the id into every new stack, and a
    trajectory may copy it (A2's S3 gateway finds its buckets with it), so each such file must name this stack, as it
    would after a replay here. Returns the files changed."""
    if old == new:
        return []
    script = ('for f in "$@"; do if [ -f "$f" ] && [ "$(cat "$f")" = "$OLD" ]; then sed -i "s/$OLD/$NEW/" "$f" && echo "$f"; fi; done')
    return run(["docker", "exec", "-e", f"OLD={old}", "-e", f"NEW={new}", app_cid, "sh", "-c", script, "sh",
                *STACK_ID_FILES]).stdout.split()


def restore(app_cid: str, src: Path) -> dict:
    """Restore a saved state into this (fresh) stack: Postgres, files, the stack's id, buckets, then the service."""
    man = json.loads((src / "manifest.json").read_text())
    if not man.get("complete"):
        raise RuntimeError(f"state {src} is incomplete")
    t_all = time.time()
    s = find_stack(app_cid)
    info: dict = {"project": s["project"], "state_project": man["project"], "state_saved": man["saved"]}
    # 1. Postgres: stop the fresh cluster, swap its data folder for the saved one, start it again.
    t0 = time.time()
    swap_pg(s, src / "pg.tar")
    info["pg_seconds"] = round(time.time() - t0, 1)
    # 2. Files: stop the fresh service, delete what the trajectory deleted, empty opaque folders, untar the rest.
    t0 = time.time()
    run(["docker", "exec", app_cid, "pkill", "-f", "[m]odel-registry"], check=False)
    wh = (src / "whiteouts.nul").read_bytes()
    if wh:
        run(["docker", "exec", "-i", app_cid, "sh", "-c", "cd / && xargs -0 -r rm -rf --"], input=wh, text=False)
    op = (src / "opaque.nul").read_bytes()
    if op:
        run(["docker", "exec", "-i", app_cid, "sh", "-c",
             'cd / && xargs -0 -r -I{} find {} -mindepth 1 -delete'], input=op, text=False, check=False)
    with open(src / "files.tar", "rb") as f:
        r = subprocess.run(["docker", "exec", "-i", app_cid, "tar", "-C", "/", "--numeric-owner", "--xattrs",
                            "--xattrs-include=*", "-xpf", "-"], stdin=f, capture_output=True, timeout=1800)
    info["files_tar_rc"] = r.returncode
    if r.returncode != 0:  # paths only, never contents
        info["files_tar_errors"] = r.stderr.decode(errors="replace").strip().splitlines()[-8:]
    info["files_seconds"] = round(time.time() - t0, 1)
    info["stack_id_files"] = _rename_stack_id(app_cid, bucket_suffix(man["project"]), s["suffix"])
    # 3. Buckets: mirror the saved objects back, removing objects the fresh stack has and the state doesn't.
    t0 = time.time()
    tmp = f"/tmp/power-state-{s['suffix']}"
    run(["docker", "exec", SHARED_MINIO, "rm", "-rf", tmp], check=False)
    run(["docker", "cp", str(src / "s3"), f"{SHARED_MINIO}:{tmp}"])
    run(["docker", "exec", SHARED_MINIO, "sh", "-c", MC_ENV + f'mkdir -p {tmp}/models {tmp}/backups && '
         f'mc --insecure mirror --quiet --overwrite --remove {tmp}/models x/models-{s["suffix"]} >/dev/null && '
         f'mc --insecure mirror --quiet --overwrite --remove {tmp}/backups x/backups-{s["suffix"]} >/dev/null'])
    run(["docker", "exec", SHARED_MINIO, "rm", "-rf", tmp], check=False)
    info["s3_seconds"] = round(time.time() - t0, 1)
    # 4. The service, from the restored binary, by the account that last started it: dev (through its sudo
    #    rule, with TEST_DATABASE_URL emptied, as power_v0 runs dev's commands) or root (the container's start).
    t0 = time.time()
    saved = man.get("service", {})
    info["service_was_running"] = saved.get("running", 0)
    if saved.get("running"):
        restart_service(app_cid, not any(p.get("test_database_url_set") for p in saved.get("procs", [])), info)
    now = service_info(app_cid)
    info["service_binary_matches_saved"] = (sorted(p["exe_sha256"] for p in now["procs"])
                                            == sorted(p["exe_sha256"] for p in saved.get("procs", [])))
    info["service_seconds"] = round(time.time() - t0, 1)
    info["restore_seconds"] = round(time.time() - t_all, 1)
    return info


def gate_dev_internet(app_cid: str, private_nets: list[str]) -> str:
    """The same rule _setup_dev sets: dev's own traffic to public addresses is refused (it lives in the
    container's network namespace, so a new container needs it again)."""
    uid = run(["docker", "exec", app_cid, "id", "-u", "dev"]).stdout.strip()
    pid = run(["docker", "inspect", "-f", "{{.State.Pid}}", app_cid]).stdout.strip()
    for net in private_nets:
        run(["nsenter", "-t", pid, "-n", "iptables", "-A", "OUTPUT", "-m", "owner", "--uid-owner", uid, "-d", net, "-j", "ACCEPT"])
    run(["nsenter", "-t", pid, "-n", "iptables", "-A", "OUTPUT", "-m", "owner", "--uid-owner", uid, "-j", "REJECT"])
    run(["nsenter", "-t", pid, "-n", "ip6tables", "-A", "OUTPUT", "-m", "owner", "--uid-owner", uid, "-j", "REJECT"], check=False)
    return f"uid {uid} blocked except {', '.join(private_nets)} (container {app_cid[:12]})"
