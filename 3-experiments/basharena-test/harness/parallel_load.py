"""C4: start 1, 4, then 8 copies of the primary task environment at once; time startup/teardown, measure memory/CPU."""
import concurrent.futures as cf, json, re, subprocess, time
from pathlib import Path
from control_arena.settings.bash_arena.task.task_utils import get_workspaces_base_dir
from common import PRIMARY_TASK

SETUP = Path(__file__).resolve().parents[1] / ".venv/lib/python3.13/site-packages/control_arena/settings/bash_arena/base_environment/setup.sh"
SETUP = Path("/root/work/.venv/lib/python3.13/site-packages/control_arena/settings/bash_arena/base_environment/setup.sh")
COMPOSE = get_workspaces_base_dir() / "default" / PRIMARY_TASK / "compose.yml"
OUT = Path("/root/work/logs/c4_parallel_results.json")


def sh(cmd, timeout=1200):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def mem_used_mb():
    m = dict(re.findall(r"(\w+):\s+(\d+)", open("/proc/meminfo").read()))
    return (int(m["MemTotal"]) - int(m["MemAvailable"])) / 1024


def up(proj):
    t = time.time()
    r = sh(["docker", "compose", "-p", proj, "-f", str(COMPOSE), "up", "-d", "--wait"])
    up_s = time.time() - t
    res = {"proj": proj, "up_s": round(up_s, 1), "ok": r.returncode == 0}
    if r.returncode != 0:
        res["err"] = r.stderr[-800:]
        return res
    cid = sh(["docker", "compose", "-p", proj, "-f", str(COMPOSE), "ps", "-q", "default"]).stdout.strip()
    t = time.time()
    sh(["docker", "cp", str(SETUP), f"{cid}:/tmp/setup.sh"])
    s = sh(["docker", "exec", cid, "bash", "/tmp/setup.sh"])
    res["setup_s"] = round(time.time() - t, 1); res["setup_ok"] = s.returncode == 0
    return res


def down(proj):
    t = time.time()
    r = sh(["docker", "compose", "-p", proj, "-f", str(COMPOSE), "down", "-v", "-t", "1"])
    return {"proj": proj, "down_s": round(time.time() - t, 1), "ok": r.returncode == 0}


def stats(prefix):
    r = sh(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"])
    per_env, per_service = {}, {}
    for line in r.stdout.splitlines():
        name, mem, cpu = line.split("\t")
        if not name.startswith(prefix):
            continue
        used = mem.split("/")[0].strip()
        num, unit = re.match(r"([\d.]+)\s*([KMG]i?B)", used).groups()
        mb = float(num) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1000, "MB": 1, "GB": 1000}[unit]
        proj = name.rsplit("-", 2)[0]
        svc = name[len(proj) + 1:].rsplit("-", 1)[0]
        per_env[proj] = per_env.get(proj, 0) + mb
        per_service.setdefault(svc, []).append(mb)
    return per_env, {k: round(sum(v) / len(v), 1) for k, v in per_service.items()}


def load_sampler(stop, samples):
    while not stop[0]:
        samples.append(float(open("/proc/loadavg").read().split()[0]))
        time.sleep(1)


results = {"host": {"cpus": int(sh(["nproc"]).stdout), "mem_total_mb": round(int(re.search(r"MemTotal:\s+(\d+)", open('/proc/meminfo').read()).group(1)) / 1024)}}
import threading
for n in [1, 4, 8]:
    prefix = f"c4-{n}-"
    projs = [f"{prefix}{i}" for i in range(n)]
    base_mem = mem_used_mb()
    stop, samples = [False], []
    th = threading.Thread(target=load_sampler, args=(stop, samples)); th.start()
    t = time.time()
    with cf.ThreadPoolExecutor(n) as ex:
        ups = list(ex.map(up, projs))
    all_up = time.time() - t
    stop[0] = True; th.join()
    time.sleep(10)  # settle
    per_env, per_service = stats(prefix)
    used = mem_used_mb()
    t = time.time()
    with cf.ThreadPoolExecutor(n) as ex:
        downs = list(ex.map(down, projs))
    all_down = time.time() - t
    results[f"n{n}"] = {
        "wall_all_up_s": round(all_up, 1), "wall_all_down_s": round(all_down, 1),
        "failures": [u for u in ups if not u.get("ok") or not u.get("setup_ok")],
        "up_s": [u["up_s"] for u in ups], "setup_s": [u.get("setup_s") for u in ups], "down_s": [d["down_s"] for d in downs],
        "mem_per_env_mb_docker_stats": {k: round(v) for k, v in per_env.items()},
        "mem_per_service_avg_mb": per_service,
        "host_mem_increase_mb": round(used - base_mem), "host_mem_increase_per_env_mb": round((used - base_mem) / n),
        "peak_loadavg_1m_during_startup": max(samples) if samples else None,
    }
    print(json.dumps({f"n{n}": results[f"n{n}"]}, indent=1), flush=True)
OUT.write_text(json.dumps(results, indent=2))
