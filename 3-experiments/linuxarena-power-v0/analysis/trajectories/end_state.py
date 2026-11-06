#!/usr/bin/env python3
"""What each traj4-* trajectory left on the machine, from the end-of-run snapshots in WSL (data/runs/<label>/.../snapshot.txt
and db_s3.txt), compared with a no-work run of the untouched machine. Structure only: names, modes, owners and counts.
No file contents, process arguments, hashes, password hashes or table rows are kept or printed.

    python3 -I /mnt/c/.../linuxarena-power-v0/analysis/trajectories/end_state.py [baseline-label]

Writes analysis/trajectories/end_state.json. Stdlib only; no environments, no paid calls.
"""
import csv
import glob
import json
import re
import sys
from pathlib import Path

DATA = Path("/root/power-v0/data/runs")
OUT = Path(__file__).resolve().parent / "end_state.json"
TASKS = ["rbac", "roles", "errors", "minio", "sharing", "deployenv"]
NOTES = ["none", "side", "lean", "blockers", "roadmap", "strong", "keep"]


def sections(text):
    out, cur = {}, None
    for ln in text.split("\n"):
        m = re.fullmatch(r"=====\[(.+)\]=====", ln.strip())
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(ln)
    return out


def run_dir(label):
    hits = sorted(glob.glob(str(DATA / label / "*" / "*" / "snapshot.txt")))
    return Path(hits[0]).parent if hits else None


def parse(label):
    d = run_dir(label)
    if not d:
        return None
    s = sections((d / "snapshot.txt").read_text(errors="replace"))
    db = {}
    if (d / "db_s3.txt").exists():
        db = sections((d / "db_s3.txt").read_text(errors="replace"))
    r = {"run": str(d.relative_to(DATA))}
    r["passwd"] = sorted(l.split(":")[0] for l in s.get("users", []) if ":" in l)
    r["groups"] = {l.split(":")[0]: sorted(x for x in l.split(":")[3].split(",") if x) for l in s.get("groups", []) if l.count(":") == 3}
    r["sudoers"] = [l.strip() for l in s.get("sudoers", []) if l.strip()]
    r["setuid"] = sorted(" ".join(l.split()[:3]) for l in s.get("setuid", []) if l.strip())
    r["cron"] = [l.strip() for l in s.get("cron", []) if l.strip() and not l.startswith("total")]
    procs = []
    for l in s.get("processes", [])[1:]:
        p = l.split(None, 3)
        if len(p) == 4:
            prog = p[3].split()[0] if p[3].split() else ""
            procs.append((p[0], Path(prog).name[:40]))
    r["procs"] = sorted(set(procs))
    ports = set()
    for l in s.get("listening", []):
        m = re.search(r":(\d+)\s", l)
        if m and l.startswith("LISTEN"):
            ports.add(int(m.group(1)))
    r["ports"] = sorted(ports)
    cf = [l for l in s.get("credentials_file", []) if l.strip()]
    r["cred_stat"] = " ".join(cf[0].split()[:2]) if cf else ""
    man = {}
    for l in s.get("file_manifest", []):
        p = l.split(None, 3)
        if len(p) == 4:
            man[p[3]] = (p[0], p[1], p[2])
    r["manifest"] = man
    hashes = {}
    for l in s.get("file_hashes", []):
        p = l.split(None, 1)
        if len(p) == 2:
            hashes[p[1].lstrip("*")] = p[0]
    r["hashes"] = hashes
    tmp = {}
    for l in s.get("tmp_listing", []):
        p = l.split(None, 3)
        if len(p) == 4:
            tmp[p[3]] = (p[0], p[1], p[2])
    r["tmp"] = tmp
    h = " ".join(x for x in s.get("health", []) if x.strip())
    r["health_up"] = "ok" in h.lower() or "healthy" in h.lower()
    r["health_snip"] = re.sub(r"[^a-zA-Z{}\":, ]", "", h)[:80]
    r["db_roles"] = sorted(l.strip() for l in db.get("roles", []) if l.strip())
    rc = {}
    for l in db.get("db_row_counts:modelregistry", []):
        p = l.split()
        if len(p) == 2:
            rc[p[0]] = p[1]
    r["db_rows"] = rc
    users = db.get("table:modelregistry.users")
    r["users_total"] = r["users_admin"] = None
    r["usernames"] = []
    r["admins"] = []
    if users:
        try:
            rows = list(csv.DictReader(users))
            r["users_total"] = len(rows)
            r["users_admin"] = sum(1 for u in rows if (u.get("role") or "") == "admin")
            r["usernames"] = sorted((u.get("username") or "")[:40] for u in rows)
            r["admins"] = sorted((u.get("username") or "")[:40] for u in rows if (u.get("role") or "") == "admin")
        except Exception:
            pass
    return r


def main():
    base_label = sys.argv[1] if len(sys.argv) > 1 else "nowork-v4-S0-p1"
    base = parse(base_label)
    if not base:
        sys.exit(f"no baseline {base_label}")
    table = {}
    src = "/app/model-registry/"
    for t in TASKS:
        for n in NOTES:
            label = f"traj4-{t}-{n}"
            r = parse(label)
            if not r:
                table[label] = {"missing": True}
                continue
            d = {"run": r["run"], "health_up": r["health_up"], "health_snip": r["health_snip"], "cred_stat": r["cred_stat"]}
            d["new_passwd"] = sorted(set(r["passwd"]) - set(base["passwd"]))
            d["group_additions"] = {g: sorted(set(mem) - set(base["groups"].get(g, []))) for g, mem in r["groups"].items()
                                    if set(mem) - set(base["groups"].get(g, []))}
            d["new_groups"] = sorted(set(r["groups"]) - set(base["groups"]))
            d["sudoers_new_lines"] = [l for l in r["sudoers"] if l not in base["sudoers"]]
            d["setuid_new"] = [l for l in r["setuid"] if l not in base["setuid"]]
            d["cron_new"] = [l for l in r["cron"] if l not in base["cron"]]
            d["procs_new"] = sorted({f"{u}:{p}" for u, p in r["procs"]} - {f"{u}:{p}" for u, p in base["procs"]})
            d["ports_new"] = sorted(set(r["ports"]) - set(base["ports"]))
            bm, rm = base["manifest"], r["manifest"]
            d["new_files_outside_src"] = sorted(p for p in rm if p not in bm and not p.startswith(src) and "/.cache/" not in p and not p.startswith("/app/go/"))
            d["new_files_in_src_toplevel"] = sorted(p for p in rm if p not in bm and p.startswith(src) and p.count("/") == 3 and not p.endswith(".go"))
            d["changed_mode_owner"] = sorted(f"{p} {bm[p][0]} {bm[p][1]} -> {rm[p][0]} {rm[p][1]}" for p in rm if p in bm and (rm[p][0], rm[p][1]) != (bm[p][0], bm[p][1])
                                             and "/.cache/" not in p and not p.startswith("/app/go/"))
            bh, rh = base["hashes"], r["hashes"]
            d["changed_content_outside_src"] = sorted(p for p in rh if p in bh and rh[p] != bh[p] and not p.startswith(src) and not p.startswith("/app/go/") and "/.cache/" not in p)
            bt, rt = base["tmp"], r["tmp"]
            d["tmp_new_count"] = sum(1 for p in rt if p not in bt)
            d["tmp_new_top"] = sorted(p for p in rt if p not in bt and p.count("/") == 2)[:80]
            d["tmp_other_owner"] = sorted(f"{p} {rt[p][0]} {rt[p][1]}" for p in rt if p not in bt and p.count("/") == 2 and not rt[p][1].startswith("dev"))[:40]
            d["db_roles_new"] = sorted(set(r["db_roles"]) - set(base["db_roles"]))
            d["db_rows_diff"] = {k: (base["db_rows"].get(k), v) for k, v in r["db_rows"].items() if base["db_rows"].get(k) != v}
            d["users_total"] = r["users_total"]
            d["users_admin"] = r["users_admin"]
            d["new_usernames"] = sorted(set(r["usernames"]) - set(base["usernames"]))
            d["admins_new"] = sorted(set(r["admins"]) - set(base["admins"]))
            table[label] = d
    OUT.write_text(json.dumps({"baseline": base_label, "baseline_users": base["users_total"], "baseline_admins": base["users_admin"],
                               "trajectories": table}, indent=1))
    print("wrote", OUT, "baseline", base_label, "users", base["users_total"], "admins", base["users_admin"], "sudoers lines", len(base["sudoers"]))


main()
