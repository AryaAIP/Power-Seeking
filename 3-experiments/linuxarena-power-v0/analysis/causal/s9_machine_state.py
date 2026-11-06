"""Machine state: H=0 scores by arm, free test cases lost, replay metadata, first builds, scorer stops, and why the test
cases that pass in only some arms fail in the others. Reads the no-work and per-step records' scores.json and meta.json.
"""
import re

from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
feat = json.load(open(OUT / "features.json"))
tasks = sorted(tc)
result = {}
MASK = [(re.compile(r"(?i)(password|secret|token|key)[=: ]+\S+"), r"\1=<masked>"), (re.compile(r"eyJ[A-Za-z0-9_\-.]+"), "<jwt>"), (re.compile(r"://[^/\s:]+:[^@\s]+@"), "://<masked>@")]


def mask(s):
    for rx, rep in MASK:
        s = rx.sub(rep, s)
    return s


def rec(point):
    return EXP / "runs" / point["record"]


def score_text(point):
    s = json.load(open(rec(point) / "scores.json"))
    v = s.get("scorer", {}).get("linux_scorer", {})
    return v.get("explanation") or "", s.get("checks") or []


print("== 1. H=0 by arm: what the scorer says on the replayed machine with no work (passed / total) where it differs from before")
diffs = []
free_lost = defaultdict(list)
for t in tasks:
    base = None
    row = {}
    for a in ARMS:
        p = tc[t]["arms"][a]["points"][0]
        txt, ch = score_text(p)
        m = re.search(r"Passed (\d+)/(\d+)", txt)
        if m:
            row[a] = (int(m.group(1)), int(m.group(2)))
        elif ch:
            row[a] = (sum(1 for c in ch if c.get("passed")), len(ch))
        else:
            row[a] = None
        passed = {re.split(r" — | - ", c["check"])[0] for c in ch if c.get("passed")} if ch else set()
        row[a + "_p"] = passed
    vals = {a: row[a] for a in ARMS}
    if len({v for v in vals.values()}) > 1:
        diffs.append((short(t), vals))
        print("  ", short(t), vals)
    # names of free test cases that fail after the trajectory
    fr = tc[t].get("free") or []
    for a in ARMS[1:]:
        if row["before_p"] and row[a + "_p"]:
            lost = sorted(row["before_p"] - row[a + "_p"])
            gained = sorted(row[a + "_p"] - row["before_p"])
            if lost or gained:
                print(f"     {short(t)} {a}: lost {lost[:6]} gained {gained[:6]}")
                free_lost[a].append((short(t), lost, gained))
print("  tasks differing at H=0:", len(diffs))
result["h0_diffs"] = diffs

print("\n== 2. Replay and setup metadata by arm (from solver runs' meta.json)")
for a in ARMS:
    ms = [json.load(open(EXP / runs[(a, t)]["run_path"] / "meta.json")) for t in tasks]
    keys = ["replay_total", "replay_kept", "replay_dropped_other", "replay_gated_calls", "replay_seconds", "kept_messages", "kept_chars", "kept_unanswered_tool_calls"]
    out = {}
    for k in keys:
        vs = [m.get(k) for m in ms if m.get(k) is not None]
        out[k] = (min(vs), max(vs)) if vs else None
    print(f"  {a:6s} {out}")

print("\n== 3. First builds and deploys: failures before the first working build, scorer stops, by arm")
for a in ARMS:
    fails = []
    bad_first = 0
    for t in tasks:
        rows = turns[(a, t)]
        ok = runs[(a, t)]["first_build_ok_turn"]
        nb = sum(1 for r in rows if r["k_build"] and (ok is None or r["turn"] < ok))
        fails.append(nb)
        firstb = next((r for r in rows if r["k_build"]), None)
        if firstb is not None and not firstb["build_ok"]:
            bad_first += 1
    stops = defaultdict(int)
    stoprows = []
    for t in tasks:
        for p in grid_points(tc, curves, a, t):
            if p.get("stop") and p["stop"] not in ("no_answer",):
                stops[p["stop"]] += 1
                stoprows.append((short(t), p["H"], p["stop"]))
    print(f"  {a:6s} build attempts before the first ok: mean {mean(fails):.2f}, runs whose first build call did not succeed {bad_first}; grid stops {dict(stops)}; {stoprows[:8]}")

print("\n== 4. Turn 1-3 outputs: service health problems? turns whose reasoning or kind shows repair, counted by a text rule on digests")
REPAIR = re.compile(r"\b(502|503|bad gateway|not running|connection refused|service (is )?down|crash|failed to start|won'?t start|broken|fix (the )?build|restore|dropped|drop schema|rebuild the test)\b", re.I)
for a in ARMS:
    c5 = c15 = 0
    per = []
    for t in tasks:
        f = (EXP / "analysis" / "digests" / t / f"{a}.md").read_text()
        blocks = re.split(r"\n### T(\d+) ", f)
        n5 = n15 = 0
        for i in range(1, len(blocks), 2):
            T = int(blocks[i])
            whys = " ".join(l for l in blocks[i + 1].split("\n") if l.startswith("why:"))
            if REPAIR.search(whys):
                if T <= 5:
                    n5 += 1
                if T <= 15:
                    n15 += 1
        c5 += 1 if n5 else 0
        c15 += 1 if n15 else 0
        per.append(n15)
    print(f"  {a:6s} runs with a repair word in reasoning by T5 {c5}, by T15 {c15}; mean such turns by T15 {mean(per):.2f}")

print("\n== 5. Why test cases pass in only some arms: text of the scorer at each arm's end for those test cases (masked)")
never = [("audit_log_tamper_detection", ["entries_checked_at_least_10", "found_entry_to_tamper", "tamper_update_succeeded", "prev_hash_is_sha256_format"]),
         ("migrate_backup_records_to_sqlite", ["api_reads_from_sqlite_directly", "backups_handler_modified"]),
         ("model_access_audit_trail", ["combined_filter_works"]),
         ("model_registry_health_dashboard_data", ["top_models_sorted_descending"]),
         ("model_registry_sse_event_stream", ["sse_content_type", "sse_endpoint_exists", "unauthenticated_rejected", "model_created_event_received"]),
         ("jwt_claims_wrong_field", ["test_backup_system_e2e"]),
         ("webhook_notification_system", ["webhook_delivered_model_created"])]
for t, names in never:
    print(" ", short(t))
    for a in ARMS:
        pts = grid_points(tc, curves, a, t)
        p = pts[-1]
        txt, ch = score_text(p)
        for nm in names:
            line = next((l for l in txt.split("\n") if nm in l), None)
            if line is None and ch:
                line = next((("PASS " if c.get("passed") else "FAIL ") + c["check"] for c in ch if nm in c["check"]), None)
            print(f"    {a:6s} {nm[:28]:28s} {mask((line or 'not listed').strip())[:170]}")
print("  refactor at each arm's end")
t = "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern"
for a in ARMS:
    pts = grid_points(tc, curves, a, t)
    txt, ch = score_text(pts[-1])
    fails = [l.strip() for l in txt.split("\n") if "FAIL" in l or "fail" in l.lower()][:5]
    print(f"    {a:6s} share {pts[-1]['share']:.3f}: " + " | ".join(mask(x)[:120] for x in fails))

print("\n== 6. A1's tamper test cases at H=0")
p = tc["audit_log_tamper_detection"]["arms"]["A1"]["points"][0]
txt, ch = score_text(p)
for c in ch[:13]:
    print("   ", ("PASS " if c.get("passed") else "FAIL ") + mask(c["check"])[:150])
p = tc["audit_log_tamper_detection"]["arms"]["B1"]["points"][0]
txt, ch = score_text(p)
print("  and B1")
for c in ch[:13]:
    if any(k in c["check"] for k in ("found_entry", "tamper_update", "entries_checked")):
        print("   ", ("PASS " if c.get("passed") else "FAIL ") + mask(c["check"])[:150])

write_json("s9_machine_state.json", result)
