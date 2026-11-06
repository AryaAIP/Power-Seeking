"""CPU and load sampler for the efficiency tests (plans/scoring-efficiency-tests.md). Opt-in: nothing starts it but a test.

Every --interval seconds it appends one JSON line: load, /proc/pressure/{cpu,io,memory}, /proc/stat, memory, the cumulative
cpu.stat of system.slice, docker.service, containerd.service and each container, and each `ct` process's CPU. It reads
only counters and asks Docker once per new container for its compose project. No command output, no environment, no
secret: names and numbers only.

  python3 -I bench_sample.py run OUT.jsonl [--interval 15] [--minutes 30]
  python3 -I bench_sample.py report OUT.jsonl LABEL [LABEL ...]     CPU-seconds and wall time for each job, by phase
"""

import argparse
import glob
import http.client
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_paths import CONFIG, DATA, HOME  # noqa: E402

CG = Path("/sys/fs/cgroup")
HZ = os.sysconf("SC_CLK_TCK")
_NAMES: dict[str, str] = {}


def _usage(path: Path) -> dict:
    out = {}
    try:
        for ln in (path / "cpu.stat").read_text().splitlines():
            k, _, v = ln.partition(" ")
            if k in ("usage_usec", "user_usec", "system_usec"):
                out[k] = int(v)
    except OSError:
        pass
    return out


def _docker_get(path: str) -> dict:
    class Conn(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect("/var/run/docker.sock")

    c = Conn("localhost")
    c.request("GET", path)
    body = c.getresponse().read()
    c.close()
    return json.loads(body)


def _name(cid: str) -> str:
    """<project>/<service>/<id8> for a container, or <name>/-/<id8> for one outside compose."""
    if cid not in _NAMES:
        try:
            info = _docker_get(f"/containers/{cid}/json")
            labels = (info.get("Config") or {}).get("Labels") or {}
            _NAMES[cid] = (f"{labels.get('com.docker.compose.project') or (info.get('Name') or '').lstrip('/')}/"
                           f"{labels.get('com.docker.compose.service') or '-'}/{cid[:8]}")
        except (OSError, ValueError, http.client.HTTPException):
            return f"?/?/{cid[:8]}"
    return _NAMES[cid]


def _containers() -> dict:
    out = {}
    for d in glob.glob(str(CG / "system.slice" / "docker-*.scope")):
        cid = os.path.basename(d)[len("docker-"):-len(".scope")]
        u = _usage(Path(d))
        if u:
            out[_name(cid)] = u.get("usage_usec", 0)
    return out


def _ct_procs() -> dict:
    """{label: CPU seconds of the `ct run eval` process, its own and its finished children's}."""
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"--run-name" not in argv or not any(a.endswith(b"/ct") for a in argv[:2]):
            continue
        label = argv[argv.index(b"--run-name") + 1].decode(errors="replace").removeprefix("power-v0-")
        try:
            f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        out[label] = {"self_s": (int(f[11]) + int(f[12])) / HZ, "child_s": (int(f[13]) + int(f[14])) / HZ}
    return out


def _psi(name: str) -> dict:
    out = {}
    try:
        for ln in Path(f"/proc/pressure/{name}").read_text().splitlines():
            f = ln.split()
            kv = dict(x.split("=") for x in f[1:])
            out[f"{f[0]}_avg10"] = float(kv["avg10"])
            out[f"{f[0]}_total"] = int(kv["total"])
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return out


def sample() -> dict:
    la = Path("/proc/loadavg").read_text().split()
    with open("/proc/stat") as fh:
        cpu = fh.readline().split()[1:9]
    mem = next((int(ln.split()[1]) // 1024 for ln in open("/proc/meminfo") if ln.startswith("MemAvailable")), None)
    # the machine's speed right now: a fixed bit of work, its CPU time (a slower clock makes the same work cost more CPU-seconds)
    c0 = time.process_time()
    for _ in range(300_000):
        pass
    spin = (time.process_time() - c0) * 1000
    return {"t": round(time.time(), 2), "load1": float(la[0]), "load5": float(la[1]), "runnable": la[3].split("/")[0],
            "spin_cpu_ms": round(spin, 2),
            "psi": {n: _psi(n) for n in ("cpu", "io", "memory")},
            "stat": dict(zip(("user", "nice", "sys", "idle", "iowait", "irq", "softirq", "steal"), map(int, cpu))),
            "memavail_mb": mem, "system_slice": _usage(CG / "system.slice").get("usage_usec"),
            "docker": _usage(CG / "system.slice" / "docker.service"),
            "containerd": _usage(CG / "system.slice" / "containerd.service"),
            "c": _containers(), "ct": _ct_procs()}


def run(a) -> int:
    end = time.time() + a.minutes * 60
    with open(a.out, "a") as fh:
        while time.time() < end:
            fh.write(json.dumps(sample()) + "\n")
            fh.flush()
            time.sleep(a.interval)
    return 0


# ---------------------------------------------------------------- report
def _busy(s: dict) -> float:
    st = s["stat"]
    return (st["user"] + st["nice"] + st["sys"] + st["irq"] + st["softirq"] + st["steal"]) / HZ


def _at(samples: list[dict], t: float, fn) -> float:
    """fn's cumulative value interpolated at time t."""
    if t <= samples[0]["t"]:
        return fn(samples[0])
    for a, b in zip(samples, samples[1:]):
        if a["t"] <= t <= b["t"]:
            va, vb = fn(a), fn(b)
            return va + (vb - va) * (t - a["t"]) / max(b["t"] - a["t"], 1e-6)
    return fn(samples[-1])


def _iso(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp()


def _project_of(label: str) -> str | None:
    p = HOME / "bench" / "projects" / label
    return p.read_text().strip() if p.exists() else None


def _phases(label: str) -> list[tuple[str, float, float]]:
    """(phase, start, end) from the job's config, meta.json and rows."""
    cfg = (CONFIG / f"{label}.txt").read_text(errors="replace")
    started = _iso(cfg.split("started=", 1)[1].split()[0])
    finished = _iso(cfg.split("finished=", 1)[1].split()[0]) if "finished=" in cfg else None
    metas = glob.glob(str(DATA / "runs" / label / "*" / "*" / "meta.json"))
    if not metas:
        return [("whole job", started, finished or started)]
    meta = json.loads(Path(metas[0]).read_text())
    t0, t9 = _iso(meta["started"]), _iso(meta["finished"])
    out = [("ct start, stack start", started, t0)]
    prev = t0
    rows = []
    f = Path(metas[0]).parent / "horizon_scores.jsonl"
    if f.exists():
        rows = [json.loads(ln) for ln in f.read_text().splitlines()]
    for r in rows:
        s = r.get("seconds")
        if not s:
            continue
        t = _iso(r["started"])
        out.append(("replay", prev, t))
        out.append(("save", t, t + s["save"]))
        out.append(("scorer", t + s["save"], t + s["save"] + s["score"]))
        out.append(("undo and check", t + s["save"] + s["score"], t + s["save"] + s["score"] + s["restore"]))
        prev = t + s["save"] + s["score"] + s["restore"]
    out.append(("replay", prev, t9))
    if finished:
        out.append(("end scorer, teardown, export", t9, finished))
    return out


def report(a) -> int:
    samples = [json.loads(ln) for ln in open(a.out)]
    res = {}
    for label in a.labels:
        phases = _phases(label)
        project = _project_of(label)

        def stack(s, project=project):
            return sum(v for k, v in s["c"].items() if k.startswith(f"{project}/")) / 1e6

        def ct(s, label=label):
            c = s["ct"].get(label) or {}
            return c.get("self_s", 0) + c.get("child_s", 0)

        # a container's counter disappears with it, and ct's with ct: make the series never fall
        def mono(fn):
            best = [0.0]
            vals = {}
            for s in samples:
                best[0] = max(best[0], fn(s))
                vals[s["t"]] = best[0]
            return lambda s: vals[s["t"]]

        fstack, fct = mono(stack), mono(ct)
        dock = lambda s: ((s["docker"].get("usage_usec") or 0) + (s["containerd"].get("usage_usec") or 0)) / 1e6  # noqa: E731
        by: dict = {}
        for name, x, y in phases:
            b = by.setdefault(name, {"wall": 0.0, "stack_cpu": 0.0, "machine_cpu": 0.0, "ct_cpu": 0.0, "daemons_cpu": 0.0})
            b["wall"] += y - x
            b["stack_cpu"] += _at(samples, y, fstack) - _at(samples, x, fstack)
            b["ct_cpu"] += _at(samples, y, fct) - _at(samples, x, fct)
            b["machine_cpu"] += _at(samples, y, _busy) - _at(samples, x, _busy)
            b["daemons_cpu"] += _at(samples, y, dock) - _at(samples, x, dock)
        total = {k: sum(b[k] for b in by.values()) for k in ("wall", "stack_cpu", "machine_cpu", "ct_cpu", "daemons_cpu")}
        res[label] = {"project": project, "phases": by, "total": total}
        print(f"{label} (stack {project})")
        print(f"  {'phase':32s}{'wall s':>9s}{'stack CPU-s':>13s}{'ct CPU-s':>10s}{'daemons':>9s}{'machine':>9s}")
        for name, b in [*by.items(), ("TOTAL", total)]:
            print(f"  {name:32s}{b['wall']:9.0f}{b['stack_cpu']:13.0f}{b['ct_cpu']:10.0f}{b['daemons_cpu']:9.0f}{b['machine_cpu']:9.0f}")
    loads = [s["load1"] for s in samples]
    spins = sorted(s["spin_cpu_ms"] for s in samples if s.get("spin_cpu_ms"))
    if spins:
        print(f"fixed work's CPU time: median {spins[len(spins) // 2]:.1f} ms, 10th-90th percentile "
              f"{spins[len(spins) // 10]:.1f}-{spins[len(spins) * 9 // 10]:.1f}")
    print(f"samples {len(samples)}; load1 max {max(loads):.1f}, mean {sum(loads) / len(loads):.1f}; "
          f"cpu pressure avg10 max {max((s['psi'].get('cpu') or {}).get('some_avg10', 0) for s in samples):.0f}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("out")
    r.add_argument("--interval", type=float, default=15)
    r.add_argument("--minutes", type=float, default=30)
    p = sub.add_parser("report")
    p.add_argument("out")
    p.add_argument("labels", nargs="+")
    p.add_argument("--json")
    a = ap.parse_args()
    return run(a) if a.cmd == "run" else report(a)


if __name__ == "__main__":
    sys.exit(main())
