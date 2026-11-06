"""Routines for the efficiency tests' jobs (plans/scoring-efficiency-tests.md), named by POWER_BENCH's "program" (bench.py).
Each runs on the job's live stack, on the host, with a context from power_v0.py. They log timings, names and counts to
$POWER_V0_HOME/bench/logs/<label>.jsonl: never command output, never file contents. A scorer's explanation may hold secrets, so
the log keeps only check names and verdicts; a fork point's row goes to the run's horizon_scores.jsonl like any other point's,
and export_run.py redacts it.
"""

import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import bench
import env_fingerprint as fpr
import rollback
import state_store as ss

MARK = re.compile(r"^\s*(✓|✗) (\w+):", re.M)


def _checks(sc: dict) -> dict:
    """The verdict and the check names with their results, as export_run parses them. Nothing else of the explanation."""
    from export_run import _checks as parsed  # noqa: PLC0415  (Control Tower's Python, inside the job)
    from extract import parse_checks  # noqa: PLC0415

    expl = sc.get("explanation") or ""
    cp, ct, _ = parse_checks(expl)
    return {"value": sc.get("value"), "passed": cp, "total": ct,
            "checks": [(c["check"].split(" — ")[0].strip()[:80], c["passed"]) for c in parsed(expl)],
            "marks": [(m.group(2), m.group(1) == "✓") for m in MARK.finditer(expl)]}


def _state_dir() -> Path:
    return bench.HOME / "data" / "states" / bench.SPEC["state"]


def _diff_summary(cmp: dict, n: int = 12) -> dict:
    """Which sections differ, how many keys, and the first few key names (paths and table names; values are never in it)."""
    out = {}
    for sec, d in (cmp.get("sections") or {}).items():
        counts = {k: len(v) for k, v in d.items()}
        if any(counts.values()):
            names = [str(x)[:90] for v in d.values() for x in list(v)[:n]][:n]
            out[sec] = {"counts": counts, "first": [re.sub(r"(?i)(pass|secret|token|key)\S*", "<m>", x) for x in names]}
    return out


def _cap(cid, baseline=None):
    return fpr.capture(cid, baseline) if baseline is not None else fpr.capture(cid)


async def _capture(cid: str, baseline=None):
    t0 = time.time()
    fp = await asyncio.to_thread(_cap, cid, baseline)
    return fp, round(time.time() - t0, 1)


async def idle(ctx) -> None:
    """Test 2: hold the stack idle for bench.SPEC["idle_seconds"], so the sampler sees a stack with nothing else running."""
    secs = bench.SPEC.get("idle_seconds", 180)
    cid = await ctx.app_cid()
    await asyncio.sleep(60)  # past the start's settling
    bench.log({"op": "idle_start", **_observables(cid)})
    await asyncio.sleep(secs)
    bench.log({"op": "idle_end", "seconds": secs, **_observables(cid)})


def _observables(cid: str) -> dict:
    """What a scorer could count that health checks feed: the service log's lines, its /health lines, the metrics' /health
    count, and the row counts of tables that grow. Counts only."""
    script = ("wc -l < /tmp/model-registry.log; grep -c '/health' /tmp/model-registry.log; "
              "curl -s -m 5 http://127.0.0.1:8080/metrics | grep -v '^#' | grep -i 'health' | awk '{s+=$NF} END {print s+0}'; "
              "curl -s -m 5 http://127.0.0.1:8080/metrics | grep -v '^#' | grep -c .")
    r = ss.run(["docker", "exec", cid, "sh", "-c", script], check=False, timeout=30)
    f = (r.stdout or "").split()
    return dict(zip(("log_lines", "log_health_lines", "metrics_health_count", "metrics_series"), f))


def _timing(info: dict) -> dict:
    return {k: v for k, v in info.items() if k.endswith("_seconds") or k in ("service_healthy", "service_binary_matches_saved",
                                                                             "files_tar_rc", "service_restarted_by")}


async def reuse(ctx) -> None:
    """Test 5: restore a state into a stack that was already used, twice, then with a scorer in between; what stays different?"""
    cid = await ctx.app_cid()
    src = _state_dir()
    saved_fp = fpr.load(str(src / "fingerprint.tsv"))
    fp0, s = await _capture(cid, saved_fp)
    bench.log({"op": "fingerprint", "tag": "after first restore", "seconds": s,
               "vs_state": _diff_summary(fpr.compare(saved_fp, fp0))})
    work = bench.HOME / "bench" / "work" / bench.SPEC.get("label", "x")
    shutil.rmtree(work, ignore_errors=True)
    st = await asyncio.to_thread(rollback.Stack, cid, work, True)
    procs = await asyncio.to_thread(rollback._procs, st)
    protected = {k for k, p in procs.items() if not rollback.SERVICE_TREE.search(p["args"].strip()) and not rollback.TRANSIENT.search(p["args"])}
    try:
        for i in (1, 2):
            info = await asyncio.to_thread(ss.restore, cid, src)
            st._pgpid = None
            fp, s = await _capture(cid, saved_fp)
            bench.log({"op": "restore", "tag": f"again {i}, nothing between", "timing": _timing(info), "fingerprint_seconds": s,
                       "vs_state": _diff_summary(fpr.compare(saved_fp, fp)), "vs_first_restore": _diff_summary(fpr.compare(fp0, fp))})
        t0 = time.time()
        sc = await ctx.score()
        bench.log({"op": "score", "tag": "on the used stack", "seconds": round(time.time() - t0, 1), **_checks(sc)})
        fp, s = await _capture(cid, saved_fp)
        bench.log({"op": "fingerprint", "tag": "after the scorer", "seconds": s, "vs_first_restore": _diff_summary(fpr.compare(fp0, fp))})
        info = await asyncio.to_thread(ss.restore, cid, src)
        st._pgpid = None
        fp, s = await _capture(cid, saved_fp)
        bench.log({"op": "restore", "tag": "after a scorer", "timing": _timing(info), "fingerprint_seconds": s,
                   "vs_state": _diff_summary(fpr.compare(saved_fp, fp)), "vs_first_restore": _diff_summary(fpr.compare(fp0, fp))})
        t0 = time.time()
        sc = await ctx.score()
        bench.log({"op": "score", "tag": "after the restore", "seconds": round(time.time() - t0, 1), **_checks(sc)})
        info = await asyncio.to_thread(apply_state, cid, src, st, {"running_bin": True}, protected)
        fp, s = await _capture(cid, saved_fp)
        bench.log({"op": "apply_state", "tag": "added files cleared, after a scorer", "timing": info, "fingerprint_seconds": s,
                   "vs_state": _diff_summary(fpr.compare(saved_fp, fp)), "vs_first_restore": _diff_summary(fpr.compare(fp0, fp))})
    finally:
        await asyncio.to_thread(st.cleanup)


def _extras(s: dict, src: Path, st) -> list[str]:
    """Top-most paths the stack has in its upper folder and the state doesn't (root's build cache and the service log stay)."""
    saved = set((src / "entries.nul").read_bytes().decode("utf-8", "surrogateescape").split("\0"))
    keep, _, _ = ss.scan_upper(s["upper"], s["mounts"])
    extra = [p for p in keep if "./" + p not in saved and not rollback._under(p, (*rollback.VOLATILE, *rollback.BUILD_CACHE))]
    tops: list[str] = []
    for p in sorted(extra):
        if not any(p.startswith(t + "/") for t in tops):
            tops.append(p)
    return tops


def _kill_leftovers(st, protected: set) -> int:
    """Everything running in the app container that wasn't there before the stack's first checkpoint, the service tree included."""
    procs = rollback._procs(st)
    keys = [k for k, p in procs.items() if k not in protected and not rollback.TRANSIENT.search(p["args"])]
    rollback._kill(keys, init=st.pid)
    return len(keys)


def _put_buckets(s: dict, src: Path) -> None:
    tmp = f"/tmp/power-state-{s['suffix']}"
    ss.run(["docker", "exec", ss.SHARED_MINIO, "rm", "-rf", tmp], check=False)
    ss.run(["docker", "cp", str(src / "s3"), f"{ss.SHARED_MINIO}:{tmp}"])
    ss.run(["docker", "exec", ss.SHARED_MINIO, "sh", "-c", ss.MC_ENV + f'mkdir -p {tmp}/models {tmp}/backups && '
            f'mc --insecure mirror --quiet --overwrite --remove {tmp}/models x/models-{s["suffix"]} >/dev/null && '
            f'mc --insecure mirror --quiet --overwrite --remove {tmp}/backups x/backups-{s["suffix"]} >/dev/null'])
    ss.run(["docker", "exec", ss.SHARED_MINIO, "rm", "-rf", tmp], check=False)


def _restart(cid: str, st, src: Path, man: dict, cfg: dict, out: dict) -> None:
    """The service, by the account that last started it. With running_bin, from the binary that was running when the
    state was saved, if that wasn't the file on disk (as rollback.restore_point does), and then the file is put back."""
    t0 = time.time()
    saved = man.get("service", {})
    bin_copy = src / "running-service.bin"
    use = bool(cfg.get("running_bin")) and bin_copy.exists()
    out["used_running_binary"] = use
    if use:
        with open(bin_copy, "rb") as fh:
            rollback._run(st.in_container("sh", "-c", "cat > /app/model-registry/model-registry"), stdin=fh, text=False, say_err=True)
    info: dict = {}
    if saved.get("running"):
        ss.restart_service(cid, not any(p.get("test_database_url_set") for p in saved.get("procs", [])), info)
    if use:
        rollback._run(st.in_container("rm", "-f", "/app/model-registry/model-registry"), say_err=True)
        with open(src / "files.tar", "rb") as fh:
            subprocess.run(["docker", "exec", "-i", cid, "tar", "-C", "/", "--numeric-owner", "--xattrs", "--xattrs-include=*",
                            "--no-recursion", "-xpf", "-", "./app/model-registry/model-registry", "./app/model-registry"],
                           stdin=fh, capture_output=True, timeout=600)
    out["service_seconds"] = round(time.time() - t0, 1)
    out["service_healthy"] = info.get("service_healthy")


def _files_full(cid: str, s: dict, src: Path, st, out: dict) -> None:
    """Extras removed, image files deleted since put back, then the whole saved tar."""
    t0 = time.time()
    tops = _extras(s, src, st)
    out["extra_paths_removed"] = len(tops)
    if tops:
        ss.run(["docker", "exec", "-i", cid, "sh", "-c", "cd / && xargs -0 -r rm -rf --"],
               input=b"".join(p.encode("utf-8", "surrogateescape") + b"\0" for p in tops), text=False)
    saved_white = set((src / "whiteouts.nul").read_bytes().decode("utf-8", "surrogateescape").split("\0"))
    _, white, _ = ss.scan_upper(s["upper"], s["mounts"])
    gone = [w for w in white if w not in saved_white]
    out["whiteouts_extra"] = len(gone)
    for layer in rollback._lowers(int(s["pid"])):
        here = [g for g in gone if Path(layer, g).exists()]
        if here:
            rollback._into_container(st, [(layer, here)])
            gone = [g for g in gone if g not in here]
    wh = (src / "whiteouts.nul").read_bytes()
    if wh:
        ss.run(["docker", "exec", "-i", cid, "sh", "-c", "cd / && xargs -0 -r rm -rf --"], input=wh, text=False)
    op = (src / "opaque.nul").read_bytes()
    if op:
        ss.run(["docker", "exec", "-i", cid, "sh", "-c", "cd / && xargs -0 -r -I{} find {} -mindepth 1 -delete"],
               input=op, text=False, check=False)
    out["clean_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    with open(src / "files.tar", "rb") as f:
        r = subprocess.run(["docker", "exec", "-i", cid, "tar", "-C", "/", "--numeric-owner", "--xattrs", "--xattrs-include=*",
                            "-xpf", "-"], stdin=f, capture_output=True, timeout=1800)
    out["files_tar_rc"] = r.returncode
    out["files_seconds"] = round(time.time() - t0, 1)


def _files_delta(s: dict, src: Path, st, out: dict) -> None:
    """Only what differs from the checkpoint, through rollback.restore_files. A file with the same visible metadata, size and
    time counts as the same, like an rsync quick check; the fingerprint compared afterwards checks contents."""
    t0 = time.time()
    staging = st.work / "staged"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    ss.run(["tar", "-C", str(staging), "--numeric-owner", "--xattrs", "--xattrs-include=*", "-xpf", str(src / "files.tar")])
    out["extract_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    before = rollback.listing(str(staging))
    zero = rollback.Entry("whiteout", 0, 0, 0, 0, 0, 0, 0, 0, "", False)
    for w in filter(None, (src / "whiteouts.nul").read_bytes().decode("utf-8", "surrogateescape").split("\0")):
        before[w] = zero
    for o in filter(None, (src / "opaque.nul").read_bytes().decode("utf-8", "surrogateescape").split("\0")):
        if o in before:
            before[o] = before[o]._replace(opaque=True)
    after = rollback.listing(s["upper"], st.skip)
    for rel, a in list(before.items()):
        b = after.get(rel)
        if b is not None and ((a.kind == b.kind == "whiteout") or (rollback.visible(a) == rollback.visible(b) and a.opaque == b.opaque)):
            before[rel] = b
    out["plan_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    st.saved = staging
    plan, rc = rollback.restore_files(st, before, after, skip=(*rollback.VOLATILE, *rollback.BUILD_CACHE))
    out["delta"] = {"removed": len(plan["remove"]), "from_saved": len(plan["from_saved"]), "from_image": len(plan["from_lower"]),
                    "opaque": len(plan["opaque"]), "tar_exit": rc}
    out["files_seconds"] = round(time.time() - t0, 2)


def apply_state(cid: str, src: Path, st, cfg: dict, protected: set, delta: bool = False) -> dict:
    """A saved state into a running stack that has been used, keeping its containers and network. Beyond state_store.restore:
    what's left running is killed, added paths are removed, image files deleted since are put back, and optionally the
    service starts from the binary that was running. delta: only what differs is copied, not the whole saved tar."""
    out: dict = {}
    t_all = time.time()
    s = st.s
    man = json.loads((src / "manifest.json").read_text())
    t0 = time.time()
    out["killed"] = _kill_leftovers(st, protected)
    out["kill_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    ss.swap_pg(s, src / "pg.tar")
    st._pgpid = None
    out["pg_seconds"] = round(time.time() - t0, 1)
    if delta:
        try:
            _files_delta(s, src, st, out)
        except RuntimeError as e:  # too many paths to remove, say: a full copy instead
            out["delta_fallback"] = str(e)[:120]
            _files_full(cid, s, src, st, out)
    else:
        _files_full(cid, s, src, st, out)
    out["stack_id_files"] = len(ss._rename_stack_id(cid, ss.bucket_suffix(man["project"]), s["suffix"]))
    t0 = time.time()
    _put_buckets(s, src)
    out["s3_seconds"] = round(time.time() - t0, 1)
    _restart(cid, st, src, man, cfg, out)
    out["apply_seconds"] = round(time.time() - t_all, 1)
    return out


async def fork(ctx) -> None:
    """The fork test: this stack does no replay. It waits for each checkpoint a replaying job saves (bench.SPEC["fork"]: {"dir",
    "mode": restore | apply | delta, "running_bin": bool}), applies it, compares it with that job's fingerprint, scores
    there with the task's real scorer and writes a row like a score-and-roll-back point's, until the sentinel.
      restore  state_store.restore as it is, made for a fresh stack
      apply    apply_state: also clears what the last scorer left, keeping containers and network
      delta    the first checkpoint as apply, then only what differs"""
    cfg = bench.SPEC["fork"]
    mode = cfg.get("mode", "restore")
    cid = await ctx.app_cid()
    root = Path(cfg["dir"])
    work = bench.HOME / "bench" / "work" / bench.SPEC.get("label", "x")
    shutil.rmtree(work, ignore_errors=True)
    st = await asyncio.to_thread(rollback.Stack, cid, work, True)
    procs = await asyncio.to_thread(rollback._procs, st)
    protected = {k for k, p in procs.items() if not rollback.SERVICE_TREE.search(p["args"].strip()) and not rollback.TRANSIENT.search(p["args"])}
    rows = ctx.run_dir / "horizon_scores.jsonl"
    done: set[int] = set()
    last = time.time()
    try:
        while True:
            ready = sorted(int(p.name[1:]) for p in root.glob("H*") if (p / ".ready").exists())
            todo = [h for h in ready if h not in done]
            if not todo:
                if (root / ".done").exists():
                    break
                if time.time() - last > cfg.get("timeout", 1500):
                    bench.log({"op": "fork_timeout", "waited": round(time.time() - last)})
                    break
                await asyncio.sleep(1)
                continue
            h = todo[0]
            done.add(h)
            await _fork_point(ctx, st, cid, root / f"H{h}", h, cfg, rows, mode, protected, first=len(done) == 1)
            last = time.time()
    finally:
        await asyncio.to_thread(st.cleanup)


async def _fork_point(ctx, st, cid, src: Path, h: int, cfg: dict, rows: Path, mode: str, protected: set, first: bool) -> None:
    row: dict = {"H": h, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t0 = time.time()
    if mode == "restore":
        info = await asyncio.to_thread(ss.restore, cid, src)
        timing = _timing(info)
        st._pgpid = None
    else:
        timing = await asyncio.to_thread(apply_state, cid, src, st, cfg, protected, mode == "delta" and not first)
    t1 = time.time()
    saved_fp = fpr.load(str(src / "fingerprint.tsv"))
    fp, fs = await _capture(cid, saved_fp)
    cmp = fpr.compare(saved_fp, fp)
    t2 = time.time()
    try:
        sc = await ctx.score()
        bug = sc.pop("bugfix_tests", None)
        if bug is not None:
            row["bugfix_tests"] = bug
        row["score"] = {"linux_scorer": sc}
    except Exception as e:  # noqa: BLE001
        row["score_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    t3 = time.time()
    binary = await asyncio.to_thread(_binary_sha, st)
    row.update(state_equal=cmp.get("equal"), bench_binary_sha256=binary,
               seconds={"save": 0, "score": round(t3 - t2, 1), "restore": round(t1 - t0, 1)})
    with rows.open("a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    bench.log({"op": "fork_point", "H": h, "mode": mode, "apply_seconds": round(t1 - t0, 1), "timing": timing, "fingerprint_seconds": fs,
               "score_seconds": round(t3 - t2, 1), "state_equal": cmp.get("equal"), "vs_source": _diff_summary(cmp, 25),
               "value": (row.get("score") or {}).get("linux_scorer", {}).get("value"), "score_error": row.get("score_error"),
               "binary": (binary or "")[:12]})


def _binary_sha(st) -> str | None:
    try:
        return hashlib.sha256(Path(f"/proc/{st.pid}/root/app/model-registry/model-registry").read_bytes()).hexdigest()
    except OSError:
        return None


async def restart_timing(ctx) -> None:
    """What the seconds in restart.sh go on, as dev runs it through sudo: bash's own trace, with times."""
    cid = await ctx.app_cid()
    await asyncio.to_thread(_restart_timing, cid)


def _restart_timing(cid: str) -> None:
    """Root's shell ignores a PS4 from its environment, so this sources the script under a trace set inside the shell. Only for
    timing: the job ends after it, and the service it leaves running is never scored."""
    trace = "PS4='+ $EPOCHREALTIME '; set -x; . /app/restart.sh"
    for i in range(4):
        t0 = time.time()
        r = subprocess.run(["docker", "exec", cid, "bash", "-c", trace], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        wall = time.time() - t0
        marks = []
        for ln in r.stderr.splitlines():
            parts = ln.split(None, 2)
            if len(parts) >= 2 and parts[0].startswith("+"):
                try:
                    marks.append((round(float(parts[1]) - t0, 2), (parts[2] if len(parts) > 2 else "")[:36]))
                except ValueError:
                    pass
        t1 = time.time()
        dev = subprocess.run(["docker", "exec", "-u", "dev", "-e", "TEST_DATABASE_URL=", cid, "bash", "--login", "-c",
                              "sudo -n /app/restart.sh </dev/null >/dev/null 2>&1"], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        bench.log({"op": "restart_timing", "i": i, "traced_wall": round(wall, 2), "marks": marks[:14], "as_dev_wall": round(time.time() - t1, 2), "as_dev_rc": dev.returncode})


async def fast_means(ctx) -> None:
    """Test 6: the fastest ways to put Postgres and the buckets back on a running stack, each checked by the row hashes."""
    cid = await ctx.app_cid()
    work = bench.HOME / "bench" / "work" / (bench.SPEC.get("label", "x") + "-fast")
    shutil.rmtree(work, ignore_errors=True)
    st = await asyncio.to_thread(rollback.Stack, cid, work, True)
    try:
        await asyncio.to_thread(_fast_means, st, cid)
    finally:
        await asyncio.to_thread(st.cleanup)


def _fast_means(st, cid: str) -> None:
    res: dict = {}
    db = "modelregistry"
    rollback._stop_service(st)  # a template copy needs every connection to the database closed
    before = rollback.dbstate_fast(st)
    for name in ("WAL_LOG", "FILE_COPY"):
        t0 = time.time()
        rc = _sql(st, "postgres", f"create database bench_t_{name.lower()} template {db} strategy {name};").returncode
        res[f"create_template_{name}"] = {"seconds": round(time.time() - t0, 2), "rc": rc}
    t0 = time.time()
    rc = _sql(st, "postgres", f"drop database {db}; ").returncode
    rc2 = _sql(st, "postgres", f"create database {db} template bench_t_wal_log strategy WAL_LOG;").returncode
    res["swap_by_template"] = {"seconds": round(time.time() - t0, 2), "rc": [rc, rc2]}
    for name in ("wal_log", "file_copy"):
        _sql(st, "postgres", f"drop database bench_t_{name};")
    after = rollback.dbstate_fast(st)
    res["template_differs_from_before"] = sorted(rollback.compare_sections({"db": before}, {"db": after}).get("db", {}).get("differ", []))[:8]
    t0 = time.time()
    rollback._dump_databases(st)
    res["dump_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    res["reload_rows_ok"] = rollback._reload_rows(st, db)
    res["reload_rows_seconds"] = round(time.time() - t0, 2)
    t0 = time.time()
    ss.run(["tar", "-C", st.pgdata, "--numeric-owner", "-cpf", str(st.work / "pg.tar"), "."])
    res["pg_tar_seconds"] = round(time.time() - t0, 2)
    res["pg_tar_mb"] = round((st.work / "pg.tar").stat().st_size / 1e6, 1)
    t0 = time.time()
    ss.swap_pg(st.s, st.work / "pg.tar")
    st._pgpid = None
    res["swap_data_folder_seconds"] = round(time.time() - t0, 2)
    after2 = rollback.dbstate_fast(st)
    res["swap_differs_from_template"] = sorted(rollback.compare_sections({"db": after}, {"db": after2}).get("db", {}).get("differ", []))[:8]
    # buckets: a mirror to a folder inside MinIO, a mirror to a second bucket, and each done again with nothing changed
    tmp = f"/tmp/bench-mirror-{st.suffix}"
    role = "models"
    for tag, script in (
            ("mirror_to_folder", f'mkdir -p {tmp}; mc --insecure mirror --quiet --overwrite --remove x/{role}-{st.suffix} {tmp} >/dev/null'),
            ("mirror_to_folder_again", f'mc --insecure mirror --quiet --overwrite --remove x/{role}-{st.suffix} {tmp} >/dev/null'),
            ("mirror_back_unchanged", f'mc --insecure mirror --quiet --overwrite --remove {tmp} x/{role}-{st.suffix} >/dev/null'),
            ("mirror_to_bucket", f'mc --insecure mb --quiet x/bench-{st.suffix} >/dev/null; mc --insecure mirror --quiet --overwrite --remove x/{role}-{st.suffix} x/bench-{st.suffix} >/dev/null'),
            ("mirror_to_bucket_again", f'mc --insecure mirror --quiet --overwrite --remove x/{role}-{st.suffix} x/bench-{st.suffix} >/dev/null'),
            ("remove_bucket", f'mc --insecure rb --force x/bench-{st.suffix} >/dev/null; rm -rf {tmp}')):
        t0 = time.time()
        r = rollback._mc(st, script)
        res[tag] = {"seconds": round(time.time() - t0, 2), "rc": r.returncode}
    res["objects"] = {k: v for k, v in rollback._buckets(st).items() if k.endswith(":objects")}
    info: dict = {}
    t0 = time.time()
    ss.restart_service(cid, True, info)
    res["service_restart_seconds"] = round(time.time() - t0, 2)
    res["service_healthy"] = info.get("service_healthy")
    bench.log({"op": "fast_means", **res})


async def fork_sees(ctx) -> None:
    """Test 6: names a fork sees that differ from its source: hostname, bucket suffix, trajectory id, service process."""
    cid = await ctx.app_cid()
    s = ss.find_stack(cid)
    script = ("hostname | wc -c; for f in /tmp/.trajectory-id /etc/vertex/trajectory-id /app/model-registry/trajectory_id; do "
              "[ -f \"$f\" ] && (echo \"$f\"; sha256sum < \"$f\" | cut -c1-12); done; "
              "getent hosts postgres s3-proxy 2>/dev/null | awk '{print $2, $1}'; pgrep -f 'model-registry' | wc -l")
    r = ss.run(["docker", "exec", cid, "sh", "-c", script], check=False, timeout=30)
    bench.log({"op": "fork_sees", "project": s["project"], "suffix": s["suffix"], "lines": (r.stdout or "").split("\n")[:12]})


async def hash_timing(ctx) -> None:
    """Test 7: what each part of the state summary costs on this stack, repeated, with nothing else happening."""
    cid = await ctx.app_cid()
    work = bench.HOME / "bench" / "work" / bench.SPEC.get("label", "x")
    shutil.rmtree(work, ignore_errors=True)
    st = await asyncio.to_thread(rollback.Stack, cid, work, True)
    try:
        await asyncio.to_thread(_hash_timing, st)
        await asyncio.to_thread(_detector_checks, st)
    finally:
        await asyncio.to_thread(st.cleanup)


def _timed(fn, n=5):
    xs = []
    for _ in range(n):
        t0 = time.time()
        fn()
        xs.append(time.time() - t0)
    return {"median": round(sorted(xs)[len(xs) // 2], 3), "max": round(max(xs), 3)}


def _hash_timing(st) -> None:
    procs = [p for p in rollback._processes(st) if not rollback.TRANSIENT.search(p[3])]
    res = {"dbstate_fast": _timed(lambda: rollback.dbstate_fast(st)),
           "db_detector": _timed(lambda: rollback.db_detector(st)),
           "buckets": _timed(lambda: rollback._buckets(st)),
           "procstate": _timed(lambda: fpr.procstate(procs)),
           "servicestate": _timed(lambda: fpr.servicestate(st.pid, procs)),
           "netstate": _timed(lambda: fpr.netstate(st.pid)),
           "listing": _timed(lambda: rollback.listing(st.upper, st.skip)),
           "summary": _timed(lambda: rollback.summary(st), 3),
           "checkpoint": _timed(lambda: rollback._in(st.pg_pid(), ["docker", "exec", st.pg],
                                                     ["psql", "-U", "postgres", "-qAtc", "CHECKPOINT"], text=True)),
           "dump": _timed(lambda: rollback._dump_databases(st), 3)}
    bench.log({"op": "hash_timing", **res})


def _sql(st, db, sql):
    return rollback._psql(st, db, sql)


def _detector_checks(st) -> None:
    """Does the detector see each kind of change, and does the restore's final full hash still catch what the undo missed?"""
    rollback.DB_DETECT = True
    tables = rollback._psql(st, "modelregistry", "select format('%I.%I', schemaname, tablename) from pg_tables "
                            "where schemaname='public' order by 1").stdout.split()
    seqs = rollback._psql(st, "modelregistry", "select format('%I.%I', schemaname, sequencename) from pg_sequences "
                          "order by 1").stdout.split()
    res = {"tables": len(tables), "sequences": len(seqs)}
    base = rollback.db_detector(st)
    res["detector_stable_when_idle"] = base == rollback.db_detector(st)
    time.sleep(20)
    res["detector_stable_after_20s"] = base == rollback.db_detector(st)
    # a sequence moved, with no row written
    if seqs:
        _sql(st, "modelregistry", f"select nextval('{seqs[0]}');")
        res["detector_sees_nextval"] = base != rollback.db_detector(st)
    # a full cycle: save, change a row as a scorer might, restore: the undo must find it and put it back
    sv = rollback.save_point(st)
    sv2 = sv["db_detect"]
    tgt = _a_table_with_rows(st, tables)
    res["changed_table_found"] = bool(tgt)
    if tgt:
        rc = _sql(st, "modelregistry", _delete_one(tgt)).returncode
        res["row_delete_rc"] = rc
        res["detector_sees_row_delete"] = sv2 != rollback.db_detector(st)
    r = rollback.restore_point(st, sv)
    res["undo_after_row_change"] = {"db": r.get("db"), "state_equal": r.get("state_equal"),
                                    "db_seconds": r.get("db_seconds"), "check_seconds": r.get("check_seconds")}
    # nothing changed: the undo should skip the hash
    sv = rollback.save_point(st)
    res["save_reused_db_hash"] = sv["info"].get("db_hash_reused")
    r = rollback.restore_point(st, sv)
    res["undo_nothing_changed"] = {"db": r.get("db"), "state_equal": r.get("state_equal"), "db_seconds": r.get("db_seconds"),
                                   "hits": getattr(st, "detect_hits", 0), "misses": getattr(st, "detect_misses", 0)}
    # a deliberate difference the undo can't see: written after the database step, before the final check
    if tgt:
        sv = rollback.save_point(st)
        real = rollback._restore_buckets

        def inject(*a, **k):
            _sql(st, "modelregistry", _delete_one(tgt))
            return real(*a, **k)

        rollback._restore_buckets = inject
        try:
            r = rollback.restore_point(st, sv)
        finally:
            rollback._restore_buckets = real
        res["deliberate_difference"] = {"state_equal": r.get("state_equal"), "sections": sorted(r.get("differences") or {})}
        r = rollback.restore_point(st, sv)  # and put it back
        res["after_repair"] = {"db": r.get("db"), "state_equal": r.get("state_equal")}
    rollback.DB_DETECT = bool(bench.SPEC.get("db_detect"))
    bench.log({"op": "detector_checks", **res})


def _delete_one(table: str) -> str:
    return (f"set session_replication_role = replica;\n"
            f"delete from {table} where ctid in (select ctid from {table} limit 1);\n")


def _a_table_with_rows(st, tables):
    for t in tables:
        if rollback._psql(st, "modelregistry", f"select count(*) from {t};").stdout.strip() not in ("", "0"):
            return t
    return None
