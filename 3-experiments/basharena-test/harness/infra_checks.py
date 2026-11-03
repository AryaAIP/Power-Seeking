"""No-model checks C2 (empty submission), C3 (test repeatability), C5 (container copy)."""
import json, re, sys, tempfile, time
from pathlib import Path

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.solver import Generate, Solver, TaskState, chain, solver
from inspect_ai.util import sandbox

from control_arena import ControlTaskMetadata, EvalMode
from control_arena.settings.bash_arena.task.scorer import main_task_success, run_main_task_test_with_results
from control_arena.settings.bash_arena.task.task_utils import get_workspaces_base_dir
from common import PRIMARY_TASK, BACKUP_TASKS, make_setting, mark, host, default_container_id, now

RESULTS = Path("/root/work/logs/infra_checks_results.json")


def parse_diff(out: str) -> set[str]:
    return {l.strip() for l in out.splitlines() if l.strip()}


async def file_hashes(paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    script = "for f in \"$@\"; do if [ -f \"$f\" ]; then sha256sum \"$f\"; fi; done"
    r = await sandbox().exec(["bash", "-c", script, "_", *paths])
    out = {}
    for line in r.stdout.splitlines():
        h, _, f = line.partition("  ")
        out[f] = h
    return out


async def copy_check(task_id: str, tests: str, cid: str) -> dict:
    """C5: snapshot the agent container's filesystem, bring up a full copy of the environment from it, test the copy."""
    res = {}
    tag = f"bash-arena-copy-{task_id}:snap"
    t = now(); r = await host(["docker", "commit", cid, tag]); res["commit_s"] = round(now() - t, 2); res["commit_ok"] = r.returncode == 0
    sz = await host(["docker", "image", "inspect", tag, "--format", "{{.Size}}"])
    base = await host(["docker", "image", "inspect", f"bash-arena-default-{task_id}:latest", "--format", "{{.Size}}"])
    try:
        res["snapshot_layer_mb"] = round((int(sz.stdout.strip()) - int(base.stdout.strip())) / 1e6, 2)
    except Exception:
        pass
    ws = get_workspaces_base_dir() / "default" / task_id
    comp = (ws / "compose.yml").read_text().replace(f"image: bash-arena-default-{task_id}:latest", f"image: {tag}")
    cpath = ws / "compose.copy.yml"; cpath.write_text(comp)
    proj = f"copy-{task_id}"
    t = now(); up = await host(["docker", "compose", "-p", proj, "-f", str(cpath), "up", "-d", "--wait"], timeout=900)
    res["copy_up_s"] = round(now() - t, 2); res["copy_up_ok"] = up.returncode == 0
    if up.returncode != 0:
        res["copy_up_err"] = up.stderr[-1500:]
    ccid = (await host(["docker", "compose", "-p", proj, "-f", str(cpath), "ps", "-q", "default"])).stdout.strip()
    # running processes don't survive a filesystem snapshot: is the firewall daemon running in the copy?
    fw = await host(["docker", "exec", ccid, "bash", "-c", "pgrep -x firewall-daemon >/dev/null && echo yes || echo no"])
    res["firewall_daemon_running_in_copy"] = fw.stdout.strip()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(tests); tf = f.name
    t = now()
    await host(["docker", "cp", tf, f"{ccid}:/tmp/tests.py"])
    pr = await host(["docker", "exec", ccid, "python3", "-m", "pytest", "/tmp/tests.py", "--junitxml", "/tmp/test_results.xml", "-q"], timeout=900)
    xml = (await host(["docker", "exec", ccid, "cat", "/tmp/test_results.xml"])).stdout
    res["copy_tests_s"] = round(now() - t, 2)
    m = re.search(r'tests="(\d+)".*?failures="(\d+)"|failures="(\d+)".*?tests="(\d+)"', xml)
    total = len(re.findall(r"<testcase", xml)); bad = len(re.findall(r"<(failure|error|skipped)", xml))
    res["copy_tests_passed"] = total - bad; res["copy_tests_total"] = total
    t = now(); dn = await host(["docker", "compose", "-p", proj, "-f", str(cpath), "down", "-v", "-t", "1"], timeout=600)
    res["copy_down_s"] = round(now() - t, 2)
    await host(["docker", "rmi", tag])
    cpath.unlink(missing_ok=True)
    return res


@solver
def infra_checks(copy_task: str) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        md = state.metadata_as(ControlTaskMetadata)
        tests = md.metadata["main_task_tests"]
        task_id = md.main_task_name
        cid = await default_container_id()
        out = {"task_id": task_id, "container": cid[:12]}
        d0 = parse_diff((await host(["docker", "diff", cid])).stdout)
        runs = []
        prev = d0
        for i in range(2):
            t = now()
            r, p, n = await run_main_task_test_with_results(tests)
            dt = now() - t
            d = parse_diff((await host(["docker", "diff", cid])).stdout)
            changed = sorted(d - prev)
            hashes = await file_hashes([c[2:] for c in changed if not c.startswith("D ")][:200])
            runs.append({"passed": p, "total": n, "seconds": round(dt, 2), "exit": r.returncode,
                         "paths_changed_by_this_run": changed[:60], "n_paths_changed": len(changed),
                         "files_hashed": len(hashes)})
            prev = d
        out["c2_empty_submission"] = runs[0]
        out["c3_second_run"] = runs[1]
        out["c3_same_result"] = (runs[0]["passed"], runs[0]["total"]) == (runs[1]["passed"], runs[1]["total"])
        out["c3_second_run_changed_state"] = runs[1]["n_paths_changed"] > 0
        if task_id == copy_task:
            out["c5_copy"] = await copy_check(task_id, tests, cid)
        mark(state, "solver_end")
        state.metadata["infra_checks"] = out
        return state
    return solve


if __name__ == "__main__":
    tasks = [PRIMARY_TASK] + BACKUP_TASKS
    setting = make_setting(tasks)
    from control_arena import EvalMode
    ds = setting.get_dataset(EvalMode.HONEST)
    task = Task(dataset=ds, solver=chain(setting.setup_environment(), infra_checks(PRIMARY_TASK)),
                scorer=[main_task_success()], name="infra_checks_c2_c3_c5")
    t0 = time.time()
    logs = inspect_eval(task, model="mockllm/model", max_samples=1, max_sandboxes=1, sandbox_prebuilt=True,
                        log_dir="/root/work/logs/infra", display="plain")
    wall = time.time() - t0
    log = logs[0]
    out = {"eval_wall_s": round(wall, 1), "status": log.status, "samples": []}
    for s in log.samples or []:
        tm = s.metadata.get("timing", {})
        rec = {"id": s.id, "error": str(s.error.message)[:500] if s.error else None,
               "started_at": str(getattr(s, "started_at", "")), "completed_at": str(getattr(s, "completed_at", "")),
               "total_time": s.total_time, "timing": tm,
               "score": {k: v.value for k, v in (s.scores or {}).items()},
               "checks": s.metadata.get("infra_checks"),
               "setup_rc": (s.metadata.get("base_setup_script_result") or {}),
               }
        out["samples"].append(rec)
    RESULTS.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str)[:6000])
