"""Last checks: free test cases at H=0 from the scorer's text; per-task contributions; sensitivity to dropping test cases that
don't test the solver's work; a control for selection on the top-lag table; how pair 2's deploys are packaged.
"""
import re

from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
feat = json.load(open(OUT / "features.json"))
sg = json.load(open(OUT / "s5_deploy_gate.json"))
fp = sg["fp"]
fd = sg["fd_after_edit"]
cur = curves["no_rollback_rows"]["turns"]
tasks = sorted(tc)
result = {}

print("== 1. H=0: test cases passing by the scorer's text (lines marked PASS/FAIL or check marks, or the checks list), against before")
PASS = re.compile(r"(?:^|\n)\s*(?:PASS:|✓|\[PASS\]|\[x\]|OK:)\s*([\w\-]+)")
FAIL = re.compile(r"(?:^|\n)\s*(?:FAIL:|✗|\[FAIL\]|FAILED:)\s*([\w\-]+)")
for t in tasks:
    sets = {}
    txts = {}
    for a in ARMS:
        p = tc[t]["arms"][a]["points"][0]
        s = json.load(open(EXP / "runs" / p["record"] / "scores.json"))
        v = s.get("scorer", {}).get("linux_scorer", {})
        txt = v.get("explanation") or ""
        ps = set(PASS.findall(txt))
        if not ps and s.get("checks"):
            ps = {re.split(r" — | - ", c["check"])[0] for c in s["checks"] if c.get("passed")}
        sets[a] = ps
        txts[a] = txt
    for a in ARMS[1:]:
        lost, gained = sorted(sets["before"] - sets[a]), sorted(sets[a] - sets["before"])
        if lost or gained:
            print(f"  {short(t):24s} {a}: lost {lost[:6]} gained {gained[:6]}")
    # counts in text for tasks with no names
    if not any(sets.values()):
        heads = {a: (re.findall(r"(\d+)\s*/\s*(\d+)", txts[a])[:1] or ["?"])[0] for a in ARMS}
        print(f"  {short(t):24s} no names; counts in text {heads}; share {[round(tc[t]['arms'][a]['points'][0]['share'],3) for a in ARMS]}")

print("\n== 2. Contribution of each task to B minus A in steps per test case (task's area difference / 27), all H and inside 1..20")
contrib = {}
for A, B in PAIRS:
    rows = []
    for t in tasks:
        tot = sum(cur["per_task"][B][t][h] - cur["per_task"][A][t][h] for h in range(1, 81)) / 27
        low = sum(cur["per_task"][B][t][h] - cur["per_task"][A][t][h] for h in range(1, 21)) / 27
        rows.append((short(t), round(tot, 3), round(low, 3)))
    rows.sort(key=lambda r: r[1])
    print(f"  {B}-{A} total {sum(r[1] for r in rows):+.2f}, inside 1..20 {sum(r[2] for r in rows):+.2f}")
    print("   lowest:", rows[:6])
    print("   highest:", rows[-6:])
    rowsl = sorted(rows, key=lambda r: r[2])
    print("   by low-H, lowest:", [(r[0], r[2]) for r in rowsl[:7]])
    print("   by low-H, highest:", [(r[0], r[2]) for r in rowsl[-5:]])
    contrib[f"{B}-{A}"] = rows
result["contrib"] = contrib

print("\n== 3. Sensitivity: drop test cases that don't test the solver's work (by name, equal task weight, 5-turn grid; share by names)")
DROP_AUDIT = {"audit_log_tamper_detection": ["entries_checked_at_least_10", "found_entry_to_tamper", "tamper_update_succeeded", "prev_hash_is_sha256_format"],
              "model_access_audit_trail": ["logs_contain_entries", "pagination_limit_works", "pagination_offset_works", "combined_filter_works"]}
DROP_GUESS = {"model_registry_sse_event_stream": ["sse_content_type", "sse_endpoint_exists", "unauthenticated_rejected"]}
DROP_TAMPER_TASK = ["audit_log_tamper_detection"]


def area(a, drop=None, droptasks=(), upto=80):
    drop = drop or {}
    vals = []
    for t in tasks:
        if t in droptasks:
            continue
        units = tc_units(tc, curves, a, t)
        keep = [(nm, s) for nm, w, s in units if nm not in drop.get(t, [])]
        if not keep:
            continue
        s = 0
        for H in range(1, upto + 1):
            c = 0
            for nm, series in keep:
                v = 0
                for h, b in series:
                    if h <= H:
                        v = b
                    else:
                        break
                c += v
            s += c / len(keep)
        vals.append(s)
    return sum(vals) / len(vals)


scen = {"all test cases (by names)": ({}, ()),
        "without the audit-row test cases (tamper 4, access 4)": (DROP_AUDIT, ()),
        "without the URL-guess test cases (sse 3)": (DROP_GUESS, ()),
        "without both": ({**DROP_AUDIT, **DROP_GUESS}, ()),
        }
for nm, (dr, dt) in scen.items():
    row = []
    for A, B in PAIRS:
        row.append(f"{B}-{A} all {area(B,dr,dt)-area(A,dr,dt):+.2f}, inside 1..20 {area(B,dr,dt,20)-area(A,dr,dt,20):+.2f}")
    print(f"  {nm}: " + "; ".join(row))
    result[nm] = row

print("\n== 4. Selection control: the 10 tasks where B leads most: calls before edit, privileged up to first pass")
for A, B in PAIRS:
    order = sorted(tasks, key=lambda t: ((fp[B][t] or 0) - (fp[A][t] or 0)))[:10]
    rows = []
    for t in order:
        ea = runs[(A, t)]["first_edit_turn"] or 0
        eb = runs[(B, t)]["first_edit_turn"] or 0
        ca = sum(r["tool_calls"] for r in turns[(A, t)] if r["turn"] < ea)
        cb = sum(r["tool_calls"] for r in turns[(B, t)] if r["turn"] < eb)
        pb = sum(r["k_privileged"] for r in turns[(B, t)] if r["turn"] <= (fp[B][t] or 0))
        pa = sum(r["k_privileged"] for r in turns[(A, t)] if r["turn"] <= (fp[A][t] or 0))
        rows.append((short(t), fp[A][t], fp[B][t], ea, eb, ca, cb, pa, pb))
    print(f"  {B}-{A}: means fp {mean([r[1] for r in rows]):.1f} {mean([r[2] for r in rows]):.1f}; edit {mean([r[3] for r in rows]):.1f} {mean([r[4] for r in rows]):.1f}; calls before edit {mean([r[5] for r in rows]):.1f} {mean([r[6] for r in rows]):.1f}; priv {mean([r[7] for r in rows]):.2f} {mean([r[8] for r in rows]):.2f}; tasks {[r[0] for r in rows][:10]}")

print("\n== 5. Packaging of the first deploy: turns from the last edit before it to it; turn holding the deploy has an edit?, a test?; only-build and only-deploy turns before the first deploy")
for a in ARMS:
    gap = []
    has_edit = has_test = 0
    only_b = []
    only_d = 0
    n = 0
    for t in tasks:
        d = fd[a][t]
        if d is None:
            continue
        n += 1
        rows = turns[(a, t)]
        fr = feat["runs"][a][t]
        last_e = max([r["turn"] for r in rows if r["k_edit"] and r["turn"] <= d] or [0])
        gap.append(d - last_e)
        row = rows[int(d) - 1]
        has_edit += 1 if row["k_edit"] else 0
        has_test += 1 if row["k_test"] else 0
        only_b.append(sum(1 for r, x in zip(rows, fr) if r["turn"] < d and (x["gobuild"] or x["rebuild"]) and not r["k_edit"]))
        if not row["k_edit"] and not row["k_test"]:
            only_d += 1
    print(f"  {a:6s} n {n}; last edit to first deploy {mean(gap):.2f} turns; deploy turn has an edit {has_edit}, a test {has_test}, neither {only_d}; build-only turns before it {mean(only_b):.2f}")

print("\n== 6. Rough per-run dollars from the registry, by arm")
reg = (EXP / "runs" / "runs-registry.md").read_text().splitlines()
for a, pat in (("before", "v4-before-p"), ("A1", "v4-afterA-p"), ("B1", "v4-afterB-p"), ("A2", "v4-afterA2-p"), ("B2", "v4-afterB2-p")):
    tot = 0
    n = 0
    for l in reg:
        m = re.match(r"\|\s*(" + pat + r"\d)\s*\|", l)
        if m:
            parts = [x.strip() for x in l.split("|")]
            dollars = [x for x in parts if x.startswith("$")]
            runsn = [x for x in parts if re.match(r"^\d+ \(\d+\)$", x)]
            if dollars and runsn:
                c = int(runsn[0].split()[0])
                tot += float(dollars[0][1:])
                n += c
    print(f"  {a:6s} runs with a figure {n}, dollars {tot:.2f}, per run {tot/max(1,n):.3f}")

write_json("s13.json", result)
