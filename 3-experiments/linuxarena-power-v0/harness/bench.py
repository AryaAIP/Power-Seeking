"""Opt-in hooks for the efficiency tests (plans/scoring-efficiency-tests.md). Nothing here does anything unless the
POWER_BENCH environment variable is set, so a production job's behaviour and records are unchanged.

POWER_BENCH holds JSON (or the path of a JSON file, starting with /). Keys, all optional:
  label          the job's label: names the generated files, and records which compose project the job got
  health         true: health checks far less often after start (docs: research_notes docker_wsl_runtime.md): interval 297 s,
                 timeout 3 s, retries 1, start_period 130 s, start_interval 1 s, and Postgres's probe over TCP. Inspect's wait limit
                 (retries x (interval + timeout)) stays 300 s
  pg_fsync_off   true: Postgres runs with `-c fsync=off` (a server argument, so nothing is written into its data folder)
  pg_tmpfs       true: Postgres's data folder is a bind mount of /dev/shm/bench-pg-<label>, removed when the sample ends
  work_tmpfs     true: score and roll back's work folder is under /dev/shm
  go_seed        a tar of root's Go build cache, loaded with fresh file times just before the first scorer (bench_seed.sh)
  go_seed_dev    a tar for dev's Go build cache, loaded before the replay starts (the before arm's cache is otherwise cold)
  db_detect      true: rollback.py skips the repeated full database hash when a cheap detector says nothing moved
  dedup_detail   true: at each state dedup miss, log the changed paths' names and whether the rest of the state matched
  capture_only   true: visit every scoring point's turn but don't score or roll back there, so a job only replays and saves
                 (with save_at). The stand-in for saving during a real run; another job scores the saved states afterwards
  settle         {"quiet": 1.0, "observe": false, "probe": false}: in place of the undo's fixed 5 s after a restart, watch the
                 database detector, the file listing and the buckets, and go on once they've been still for `quiet` seconds
                 (5 s at most). observe: watch for the full 5 s and only log. probe: after each undo with a restart, wait
                 probe_wait seconds (default 6) and log whatever changed since the undo's check
  save_at        {"H": [3, 6] or "all", "dir": "/root/power-v0/bench/states/x"}: at those turns, before the point's own save, save the
                 machine's state and fingerprint with state_store (for the fork test); a sentinel when the replay ends
  program        names of routines in bench_tests.py, run in order after the dev setup, before any replay
  fork           {"dir", "mode": "restore" | "apply" | "delta", "running_bin": bool}: bench_tests.fork's settings

A generated compose file sits beside the original, because compose resolves relative paths from it, and is removed when
the sample ends. The originals are never changed. Nothing here prints a compose file or any secret.
"""

import json
import os
import re
import shutil
import time
from pathlib import Path

_raw = os.environ.get("POWER_BENCH", "").strip()
SPEC: dict | None = (json.loads(Path(_raw).read_text() if _raw.startswith("/") else _raw) if _raw else None)
HOME = Path(os.environ.get("POWER_V0_HOME") or Path.home() / "power-v0")
BENCH = HOME / "bench"

HEALTH = {"interval": "297s", "timeout": "3s", "retries": 1, "start_period": "130s", "start_interval": "1s"}
PG_DATA = "/var/lib/postgresql/data"


def _label() -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", (SPEC or {}).get("label") or "job")


def edit_compose(data: dict, spec: dict, label: str) -> dict:
    """The compose file's services, changed as the spec says. Only the keys named above are touched."""
    services = data["services"]
    if spec.get("health"):
        for name in ("default", "postgres", "s3-proxy"):
            services[name].setdefault("healthcheck", {}).update(HEALTH)
        services["postgres"]["healthcheck"]["test"] = ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U postgres"]
    if spec.get("pg_fsync_off"):
        services["postgres"]["command"] = ["postgres", "-c", "fsync=off"]
    if spec.get("pg_tmpfs"):
        services["postgres"].setdefault("volumes", []).append(
            {"type": "bind", "source": f"/dev/shm/bench-pg-{label}", "target": PG_DATA})
    return data


def _compose_copy(config):
    """A copy of the sample's compose file with the spec's changes, or the file itself if nothing changes."""
    if not SPEC or not any(SPEC.get(k) for k in ("health", "pg_fsync_off", "pg_tmpfs")) or not isinstance(config, str):
        return config
    import yaml  # noqa: PLC0415  (Control Tower's Python has it)

    src = Path(config)
    data = edit_compose(yaml.safe_load(src.read_text()), SPEC, _label())
    if SPEC.get("pg_tmpfs"):
        Path(f"/dev/shm/bench-pg-{_label()}").mkdir(parents=True, exist_ok=True)
    dst = src.parent / f".compose-bench-{_label()}.yml"
    dst.write_text(yaml.safe_dump(data, default_flow_style=False))
    return str(dst)


def install() -> None:
    """Wrap the sandbox's sample start and end. Does nothing unless POWER_BENCH is set."""
    if not SPEC:
        return
    import rollback  # noqa: PLC0415

    if SPEC.get("db_detect"):
        rollback.DB_DETECT = True
    if SPEC.get("dedup_detail"):
        rollback.DEDUP_DETAIL = True
    if SPEC.get("settle"):
        rollback.SETTLE = settle
    from control_tower.sandbox.docker import LBDockerSandboxEnvironment as LB  # noqa: PLC0415

    init, cleanup = LB.sample_init.__func__, LB.sample_cleanup.__func__

    async def sample_init(cls, task_name, config, metadata):
        t0 = time.time()
        envs = await init(cls, task_name, _compose_copy(config), metadata)
        project = next(iter(envs.values()))._project.name
        (BENCH / "projects").mkdir(parents=True, exist_ok=True)
        (BENCH / "projects" / _label()).write_text(project + "\n")
        log({"op": "sample_init", "seconds": round(time.time() - t0, 1), "project": project})
        return envs

    async def sample_cleanup(cls, task_name, config, environments, interrupted):
        t0 = time.time()
        try:
            await cleanup(cls, task_name, config, environments, interrupted)
        finally:
            log({"op": "sample_cleanup", "seconds": round(time.time() - t0, 1)})
            if isinstance(config, str):
                Path(config).parent.joinpath(f".compose-bench-{_label()}.yml").unlink(missing_ok=True)
            shutil.rmtree(f"/dev/shm/bench-pg-{_label()}", ignore_errors=True)

    LB.sample_init = classmethod(sample_init)
    LB.sample_cleanup = classmethod(sample_cleanup)


def log(row: dict) -> None:
    """One line of this job's bench log, in WSL only. Callers pass timings, names and counts: never command output."""
    if not SPEC:
        return
    (BENCH / "logs").mkdir(parents=True, exist_ok=True)
    with open(BENCH / "logs" / f"{_label()}.jsonl", "a") as fh:
        fh.write(json.dumps({"t": round(time.time(), 2), **row}, default=str) + "\n")


def work_dir(default: Path) -> Path:
    if SPEC and SPEC.get("work_tmpfs"):
        return Path(f"/dev/shm/bench-work-{_label()}") / default.name
    return default


def seed_cache(st, row: dict) -> None:
    """go_seed: root's Go build cache, once, just before the first scorer, with fresh file times so Go's 5-day trim keeps it."""
    import subprocess  # noqa: PLC0415

    if SPEC:  # the binary as the turn left it, before any scorer's build
        row["bench_binary_before_sha256"] = _binary_sha(st)
    if not (SPEC and SPEC.get("go_seed")) or getattr(st, "_bench_seeded", False):
        return
    st._bench_seeded = True
    t0 = time.time()
    with open(SPEC["go_seed"], "rb") as fh:
        r = subprocess.run(st.in_container("sh", "-c", "mkdir -p /root/.cache/go-build && "
                                           "tar -C /root/.cache/go-build --touch --no-same-owner -xf -"),
                           stdin=fh, capture_output=True, timeout=600)
    row["bench_seed"] = {"seconds": round(time.time() - t0, 2), "tar_exit": r.returncode}
    log({"op": "seed_cache", **row["bench_seed"]})


def seed_dev_cache(st) -> None:
    """go_seed_dev: dev's Go build cache, once, before the replay starts, owned by dev, with fresh file times."""
    import subprocess  # noqa: PLC0415

    if not (SPEC and SPEC.get("go_seed_dev")):
        return
    t0 = time.time()
    with open(SPEC["go_seed_dev"], "rb") as fh:
        r = subprocess.run(st.in_container("sh", "-c", "mkdir -p /home/dev/.cache/go-build && "
                                           "tar -C /home/dev/.cache/go-build --touch --no-same-owner -xf - && "
                                           "chown -R dev:dev /home/dev/.cache"),
                           stdin=fh, capture_output=True, timeout=600)
    log({"op": "seed_dev_cache", "seconds": round(time.time() - t0, 2), "tar_exit": r.returncode})


def _binary_sha(st) -> str | None:
    import hashlib  # noqa: PLC0415

    try:
        return hashlib.sha256(Path(f"/proc/{st.pid}/root/app/model-registry/model-registry").read_bytes()).hexdigest()
    except OSError:
        return None


_SECRETISH = re.compile(r"(?i)(pass|secret|token|key|credential)[^/]*")


def dedup_miss(h: int, st, why: str) -> None:
    """dedup_detail: which paths separate this point from the last scored one, by name (a secret-looking name part is
    masked) and what about them differs, in this job's bench log in WSL. Paths only, never contents."""
    detail = getattr(st, "dedup_detail", None)
    st.dedup_detail = None
    log({"op": "dedup_miss", "H": h, "why": why, **({"count": detail["count"], "summary_differs": detail["summary_differs"],
         "paths": [[_SECRETISH.sub(r"\1<m>", p), w] for p, w in detail["paths"]]} if detail else {})})


def after_scorer(st, row: dict) -> None:
    """The service binary as the scorer left it, by hash: two jobs at the same turn must hold the same bytes (cmp, in effect)."""
    if SPEC:
        row["bench_binary_sha256"] = _binary_sha(st)


def before_point(h: int, st) -> None:
    """save_at: the machine's state and fingerprint at turn h, for a second stack to apply (the fork test). First waits for
    what the replay left running, as the point's own save will (rollback.save_point), so it isn't caught part-way. If the
    running service's binary isn't the file on disk, a copy of it goes with the state. Nothing here changes the machine."""
    sa = (SPEC or {}).get("save_at")
    if not sa or (sa.get("H") != "all" and h not in sa.get("H", [])):
        return
    import shutil  # noqa: PLC0415

    import env_fingerprint  # noqa: PLC0415
    import rollback  # noqa: PLC0415
    import state_store  # noqa: PLC0415

    dest = Path(sa["dir"]) / f"H{h}"
    t0 = time.time()
    procs = rollback._procs(st)
    unsettled = rollback._unsettled(procs)
    n_unsettled = len(unsettled)
    while unsettled and time.time() - t0 < sa.get("wait", rollback.BUILD_WAIT):
        time.sleep(2)
        procs = rollback._procs(st)
        unsettled = rollback._unsettled(procs)
    t1 = time.time()
    fp = env_fingerprint.capture(st.cid)
    t2 = time.time()
    info = state_store.save(st.cid, dest, {"H": h})
    (dest / "fingerprint.tsv").write_text("".join("\t".join(x) + "\n" for x in fp), encoding="utf-8",
                                          errors="surrogateescape")
    svc = rollback._service(st, procs)
    differs = bool(svc["procs"]) and any(p["exe_sha256"] != svc["disk_sha256"] for p in svc["procs"])
    if differs:
        shutil.copyfile(f"/proc/{svc['procs'][0]['pid']}/exe", dest / "running-service.bin")
    others = sorted({rollback._redact(p["args"])[:70] for p in procs.values() if not rollback.TRANSIENT.search(p["args"])
                     and not rollback.SERVICE_TREE.search(p["args"].strip())})
    (dest / ".ready").write_text("1")
    log({"op": "save_at", "H": h, "unsettled_at_turn_end": n_unsettled, "still_unsettled": len(unsettled),
         "wait_seconds": round(t1 - t0, 1), "fingerprint_seconds": round(t2 - t1, 1), "save_seconds": info.get("save_seconds"),
         "paused_seconds": info.get("paused_seconds"), "sizes_mb": info.get("sizes_mb"), "upper_entries": info.get("upper_entries"),
         "s3_objects": info.get("s3_objects"), "running_binary_differs_from_file": differs, "other_processes": others})


def capture_only() -> bool:
    return bool(SPEC and SPEC.get("capture_only"))


def settle(st) -> dict:
    """settle: how long the restarted service's start-up pass really writes, and optionally not waiting longer than that."""
    import rollback  # noqa: PLC0415

    cfg = SPEC["settle"]
    quiet, cap = cfg.get("quiet", 1.0), rollback.RESTART_SETTLE
    t0 = last = time.time()
    prev = None
    polls = changes = 0
    while True:
        now = (rollback.db_detector(st), rollback.listing(st.upper, st.skip), rollback._buckets(st))
        t = time.time()
        polls += 1
        if now != prev:
            if prev is not None:
                changes += 1
            last, prev = t, now
        if t - t0 >= cap or (not cfg.get("observe") and t - last >= quiet):
            break
        time.sleep(0.15)
    out = {"seconds": round(time.time() - t0, 2), "last_change_after": round(last - t0, 2), "polls": polls, "changes": changes}
    log({"op": "settle", **out})
    return out


def after_undo(h: int, st, sv: dict, info: dict) -> None:
    """settle's probe: anything written after the undo's check, which a shorter wait would have let through to the next turn."""
    cfg = (SPEC or {}).get("settle") or {}
    if not cfg.get("probe") or not info.get("service_restarted"):
        return
    import rollback  # noqa: PLC0415

    time.sleep(cfg.get("probe_wait", 6))
    diffs = rollback.compare_sections(sv["summary"], rollback.summary(st))
    for k in list(diffs):
        d = diffs[k]
        if k == "service" and not d.get("only_before") and not d.get("only_after") and all(x.endswith(".env_sha256") for x in d.get("differ", [])):
            diffs.pop(k)
    log({"op": "late_writes", "H": h, "equal_at_check": info.get("state_equal"), "sections_changed_since": sorted(diffs),
         "detail": {k: {x: v[:6] for x, v in d.items() if isinstance(v, list)} for k, d in diffs.items()}})


def after_replay() -> None:
    """save_at: the sentinel that tells the second stack no more checkpoints are coming."""
    sa = (SPEC or {}).get("save_at")
    if sa:
        Path(sa["dir"]).mkdir(parents=True, exist_ok=True)
        (Path(sa["dir"]) / ".done").write_text("1")


async def run_program(ctx) -> None:
    """The routines the spec names, from bench_tests.py, on this job's live stack."""
    import bench_tests  # noqa: PLC0415

    for name in (SPEC or {}).get("program") or []:
        t0 = time.time()
        log({"op": "routine_start", "name": name})
        await getattr(bench_tests, name)(ctx)
        log({"op": "routine_end", "name": name, "seconds": round(time.time() - t0, 1)})
