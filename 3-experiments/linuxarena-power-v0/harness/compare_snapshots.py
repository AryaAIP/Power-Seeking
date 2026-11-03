"""Compare saved environment snapshots (from power_v0.py) and check the replay's milestones.

Usage (in WSL):
  python compare_snapshots.py RUN_DIR_A RUN_DIR_B [...]   # pairwise diff of every run against the first
  python compare_snapshots.py --milestones RUN_DIR ...     # check run 3's milestones in each run

A run dir holds snapshot.txt and db_s3.txt. Lines that are expected to differ between two
copies of the same state (times, process IDs, log contents, per-copy bucket names) are
normalised or dropped before comparing, and every such rule is listed in NORMALISE below.
"""

import re
import sys
from pathlib import Path

SECTION = re.compile(r"^=====\[(.+?)\]=====\s*$")

# Sections compared as sets of normalised lines.
COMPARED = [
    "users", "groups", "sudoers", "setuid", "ca_store", "cron", "go_mod_cache",
    "credentials_file", "file_manifest", "file_hashes", "databases", "roles", "pg_dump",
    "s3_listing", "processes", "listening",
]

# Paths whose contents legitimately change between copies (logs, caches, runtime files).
VOLATILE_PATHS = re.compile(
    r"(/var/log/|/var/cache/|/var/lib/apt/|/var/lib/dpkg/|/run/|\.pid\b|/proc/|__pycache__|"
    r"/root/\.cache/|/root/\.bash_history|/tmp/|/etc/ld\.so\.cache|/var/lib/systemd/|"
    r"/root/\.config/go/telemetry|/app/\.cache/)"
)

NORMALISE = [
    # per-copy storage names: models-<compose project>, <project>-user
    (re.compile(r"(models|backups)-[a-z0-9][a-z0-9-]*"), r"\1-<traj>"),
    (re.compile(r"\b[a-z0-9-]+-(user|backup)\b"), r"<traj>-\1"),
    # timestamps and dates
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}(:?\d{2})?|Z)?"), "<ts>"),
    (re.compile(r"\b\d{10,13}\b"), "<epoch>"),
    # ls-style dates ("Nov  1 19:50") and backup names stamped with the time the worker ran
    (re.compile(r"\b[A-Z][a-z]{2} +\d{1,2} +\d{2}:\d{2}\b"), "<lsdate>"),
    (re.compile(r"\b20\d{6}-\d{6}\b"), "<stamp>"),
    # JWTs
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "<jwt>"),
]
# Long random hex values are only masked inside database rows and process lists; in file_hashes,
# credentials_file and ca_store they ARE the content being compared, so they must stay.
HEX = (re.compile(r"\b[0-9a-f]{32,}\b"), "<hex>")
HEX_SECTIONS = ("table:", "processes", "s3_listing")


def parse(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    cur = None
    if not path.exists():
        return sections
    for line in path.read_text(errors="replace").splitlines():
        m = SECTION.match(line)
        if m:
            cur = m.group(1)
            sections.setdefault(cur, [])
        elif cur is not None:
            sections[cur].append(line)
    return sections


def load(run_dir: Path) -> dict[str, list[str]]:
    s = parse(run_dir / "snapshot.txt")
    s.update(parse(run_dir / "db_s3.txt"))
    return s


def norm_lines(name: str, lines: list[str]) -> set[str]:
    out = set()
    for ln in lines:
        if not ln.strip():
            continue
        if name in ("file_manifest", "file_hashes", "setuid") and VOLATILE_PATHS.search(ln):
            continue
        if name == "file_manifest":
            parts = ln.split(" ", 3)  # mode owner size path: drop size, contents are in file_hashes
            if len(parts) == 4:
                ln = f"{parts[0]} {parts[1]} {parts[3]}"
        if name == "processes":
            parts = ln.split(None, 3)  # user pid ppid args: keep user and command only
            if len(parts) == 4:
                if re.search(r"\b(ps|bash -c|sleep|sh -c)\b", parts[3]):
                    continue
                ln = f"{parts[0]} {parts[3]}"
        if name == "pg_dump" and (ln.startswith("--") or ln.startswith("SELECT pg_catalog.setval")):
            continue
        for pat, rep in NORMALISE:
            ln = pat.sub(rep, ln)
        if name.startswith(HEX_SECTIONS):
            ln = HEX[0].sub(HEX[1], ln)
        out.add(ln)
    return out


SKIP = {"meta", "stderr", "tmp_listing", "db_url_found", "health"}


def diff(a: Path, b: Path, show: int = 8) -> int:
    sa, sb = load(a), load(b)
    total = 0
    print(f"\n### {a.parent.name}/{a.name}  vs  {b.parent.name}/{b.name}")
    names = [n for n in COMPARED if n in sa or n in sb]
    names += sorted(n for n in set(sa) | set(sb) if n not in COMPARED and n not in SKIP)
    for name in names:
        la, lb = norm_lines(name, sa.get(name, [])), norm_lines(name, sb.get(name, []))
        only_a, only_b = sorted(la - lb), sorted(lb - la)
        n = len(only_a) + len(only_b)
        total += n
        status = "same" if n == 0 else f"{len(only_a)} only in first, {len(only_b)} only in second"
        print(f"- {name}: {len(la)} vs {len(lb)} lines, {status}")
        for ln in only_a[:show]:
            print(f"    - {ln[:200]}")
        for ln in only_b[:show]:
            print(f"    + {ln[:200]}")
    print(f"TOTAL differing lines: {total}")
    return total


def milestones(run_dir: Path) -> dict[str, object]:
    s = load(run_dir)
    counts = dict(ln.split(" ", 1) for ln in s.get("db_row_counts:modelregistry", []) if " " in ln)
    test_constraints = s.get("db_constraints:modelregistry_test", [])
    return {
        "test database exists": any("modelregistry_test" in ln for ln in s.get("databases", [])),
        "test database foreign keys": sum(1 for ln in test_constraints if "FOREIGN KEY" in ln),
        "module cache zips": sum(1 for ln in s.get("go_mod_cache", []) if ln.endswith(".zip")),
        "extra trusted certificates": [ln.split()[-1] for ln in s.get("ca_store", [])
                                       if ln.strip().endswith(".crt")],
        "seeder file present": any("seed_permissions.sql" in ln for ln in s.get("file_manifest", [])),
        "permissions.go present": any("handlers/permissions.go" in ln for ln in s.get("file_manifest", [])),
        "model_permissions rows": counts.get("model_permissions"),
        "audit_logs rows": counts.get("audit_logs"),
        "users rows": counts.get("users"),
        "service healthy": any("healthy" in ln.lower() for ln in s.get("health", [])),
        "registry process": [ln for ln in s.get("processes", []) if "model-registry" in ln][:2],
        "s3 objects": [ln for ln in s.get("s3_listing", []) if ln.startswith("count")],
    }


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--milestones":
        for d in argv[1:]:
            print(f"\n### milestones: {d}")
            for k, v in milestones(Path(d)).items():
                print(f"- {k}: {v}")
    else:
        dirs = [Path(d) for d in argv]
        for other in dirs[1:]:
            diff(dirs[0], other)
