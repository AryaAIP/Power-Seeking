"""What the chat taught: which code each trajectory named against what each future task touches.

Files are read from command text only (s4 features: paths named in commands, heredoc bodies dropped), so this is a rough
measure: it can't see which lines were shown, and it counts a grep as much as a cat.
- target files of a task: files named in an edit turn by at least 3 of the 5 arms, that already existed (named in a
  read-only turn before any edit turn naming them, by some arm or trajectory).
- overlap(arm, task): share of those target files the arm's trajectory named.
Then: does overlap track first edit, first deploy, first pass, and reading before first edit?
"""
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

traj_files = {}
traj_edit = {}
for a, rows in feat["traj"].items():
    named = defaultdict(int)
    edited = set()
    for r in rows:
        for f in r["files_named"]:
            named[f] += 1
        edited |= set(r["files_edited"])
    traj_files[a] = named
    traj_edit[a] = edited
print("== Trajectories: files named, code files only")
for a in traj_files:
    go = [f for f in traj_files[a] if f.endswith(".go")]
    print(a, TRAJ[a], "go files named", len(go), "top", sorted(go, key=lambda f: -traj_files[a][f])[:14])
allgo = sorted(set(f for a in traj_files for f in traj_files[a] if f.endswith(".go")))
print("only in pair 1:", sorted(set(f for a in ("A1", "B1") for f in traj_files[a] if f.endswith(".go")) - set(f for a in ("A2", "B2") for f in traj_files[a] if f.endswith(".go")))[:30])
print("only in pair 2:", sorted(set(f for a in ("A2", "B2") for f in traj_files[a] if f.endswith(".go")) - set(f for a in ("A1", "B1") for f in traj_files[a] if f.endswith(".go")))[:40])
print("A1 not B1:", sorted(set(f for f in traj_files["A1"] if f.endswith(".go")) - set(f for f in traj_files["B1"] if f.endswith(".go"))))
print("B1 not A1:", sorted(set(f for f in traj_files["B1"] if f.endswith(".go")) - set(f for f in traj_files["A1"] if f.endswith(".go"))))
print("A2 not B2:", sorted(set(f for f in traj_files["A2"] if f.endswith(".go")) - set(f for f in traj_files["B2"] if f.endswith(".go")))[:30])
print("B2 not A2:", sorted(set(f for f in traj_files["B2"] if f.endswith(".go")) - set(f for f in traj_files["A2"] if f.endswith(".go")))[:30])

# existing: named in a read-only turn before any edit turn naming it
existing = set()
for a in ARMS:
    for t in tasks:
        seen_edit = set()
        for r, tr in zip(feat["runs"][a][t], turns[(a, t)]):
            names = set(r["files_named"])
            if tr["k_edit"]:
                seen_edit |= names
            else:
                existing |= (names - seen_edit)
for a, rows in feat["traj"].items():
    seen_edit = set()
    for r in rows:
        names = set(r["files_named"])
        if r["files_edited"]:
            seen_edit |= names
        else:
            existing |= (names - seen_edit)

targets = {}
for t in tasks:
    cnt = defaultdict(int)
    for a in ARMS:
        ed = set()
        for r, tr in zip(feat["runs"][a][t], turns[(a, t)]):
            if tr["k_edit"]:
                ed |= set(f for f in r["files_named"] if f.endswith(".go"))
        for f in ed:
            cnt[f] += 1
    targets[t] = sorted(f for f, c in cnt.items() if c >= 3 and f in existing)

ov = {a: {} for a in TRAJ}
for t in tasks:
    for a in TRAJ:
        tg = targets[t]
        ov[a][t] = (sum(1 for f in tg if f in traj_files[a]) / len(tg)) if tg else None
print("\n== Overlap by task")
print("task, n target, overlap A1 B1 A2 B2, first pass (sharpened) A1 B1 A2 B2, first edit A1 B1 A2 B2")
for t in tasks:
    print(f"  {short(t):24s} {len(targets[t]):2d}  " + " ".join(fmt(ov[a][t], 2) for a in TRAJ) + "   " + " ".join(str(fp[a][t]) for a in TRAJ) + "   " + " ".join(str(runs[(a, t)]["first_edit_turn"]) for a in TRAJ) + "  " + ",".join(sorted(f for f in targets[t] if not any(f in traj_files[x] for x in ("A2", "B2")))[:3]))
for a in TRAJ:
    print(a, "mean overlap", round(mean(list(ov[a].values())), 3))
result["overlap_mean"] = {a: mean(list(ov[a].values())) for a in TRAJ}
result["targets"] = targets
result["overlap"] = ov


def rd_before_edit(a, t):
    """Tool output characters and turns before the first edit, and files named before the first edit that the chat had not named."""
    e = runs[(a, t)]["first_edit_turn"] or runs[(a, t)]["turns_T"]
    rows = [r for r in feat["runs"][a][t] if r["t"] < e]
    chars = sum(r["out_chars"] for r in rows)
    names = set(f for r in rows for f in r["files_named"] if f.endswith(".go"))
    reread = sum(1 for f in names if a in traj_files and f in traj_files[a])
    new = sum(1 for f in names if a not in traj_files or f not in traj_files[a])
    return chars, len(rows), reread, new


print("\n== Reading before the first edit, by arm: tool output chars, turns, Go files named already named in the trajectory, Go files new to the chat")
for a in ARMS:
    v = [rd_before_edit(a, t) for t in tasks]
    print(f"  {a:6s} chars {mean([x[0] for x in v]):8.0f}  turns {mean([x[1] for x in v]):5.2f}  already known files {mean([x[2] for x in v]):5.2f}  new files {mean([x[3] for x in v]):5.2f}")

print("\n== Within pair: B minus A in overlap against B minus A in speed (for understanding)")
for A, B in PAIRS:
    x = [ov[B][t] - ov[A][t] if ov[B][t] is not None else None for t in tasks]
    for nm, y in (("first pass", [fp[B][t] - fp[A][t] if fp[B][t] is not None and fp[A][t] is not None else None for t in tasks]),
                  ("first edit", [runs[(B, t)]["first_edit_turn"] - runs[(A, t)]["first_edit_turn"] if runs[(B, t)]["first_edit_turn"] and runs[(A, t)]["first_edit_turn"] else None for t in tasks]),
                  ("steps lost 1..20", [sum(cur["per_task"][A][t][h] - cur["per_task"][B][t][h] for h in range(1, 21)) for t in tasks])):
        print(f"  {B}-{A} overlap diff mean {mean(x):+.3f}, tasks with a difference {sum(1 for v in x if v)}; vs {nm}: rho {fmt(spearman(x,y),2,True)} p {fmt(perm_corr_p(x,y,n=4000),3)}")

print("\n== Between pairs: pair 1 minus pair 2 in overlap against speed (mean of the two arms per pair; for understanding)")
x = [mean([ov["A1"][t], ov["B1"][t]]) - mean([ov["A2"][t], ov["B2"][t]]) if ov["A1"][t] is not None else None for t in tasks]
pairs_y = {
    "first pass (pair 2 minus pair 1)": [(fp["A2"][t] + fp["B2"][t]) / 2 - (fp["A1"][t] + fp["B1"][t]) / 2 for t in tasks],
    "first edit (pair 2 minus pair 1)": [mean([runs[("A2", t)]["first_edit_turn"], runs[("B2", t)]["first_edit_turn"]]) - mean([runs[("A1", t)]["first_edit_turn"], runs[("B1", t)]["first_edit_turn"]]) if any(runs[("A2", t)]["first_edit_turn"] is not None for _ in [0]) else None for t in tasks],
    "steps inside 1..20 (pair 1 minus pair 2)": [sum((cur["per_task"]["A1"][t][h] + cur["per_task"]["B1"][t][h] - cur["per_task"]["A2"][t][h] - cur["per_task"]["B2"][t][h]) / 2 for h in range(1, 21)) for t in tasks],
}
print("  mean overlap difference", round(mean(x), 3), "tasks with pair 1 higher", sum(1 for v in x if v and v > 0), "pair 2 higher", sum(1 for v in x if v and v < 0))
for nm, y in pairs_y.items():
    print(f"  vs {nm}: mean {mean(y):+.2f}; rho {fmt(spearman(x,y),2,True)} p {fmt(perm_corr_p(x,y,n=4000),3)}")
result["between_pairs_mean_overlap_diff"] = mean(x)

print("\n== Tasks by which trajectory's subject they sit near")
storage = ["untracked_s3_objects_total_bytes", "migrate_backup_records_to_sqlite", "model_artifact_quarantine_system", "mtg_model_registry_pollute_training_01_constitution_versioning_system"]
for t in storage:
    print(" ", short(t), "first pass", {a: fp[a][t] for a in TRAJ}, "targets", targets[t])
s1 = [(fp["A1"][t] + fp["B1"][t]) / 2 for t in storage]
s2 = [(fp["A2"][t] + fp["B2"][t]) / 2 for t in storage]
others = [t for t in tasks if t not in storage]
o1 = [(fp["A1"][t] + fp["B1"][t]) / 2 for t in others]
o2 = [(fp["A2"][t] + fp["B2"][t]) / 2 for t in others]
print(f"  storage-near tasks: pair 1 mean {mean(s1):.2f}, pair 2 mean {mean(s2):.2f}; other {len(others)} tasks: pair 1 {mean(o1):.2f}, pair 2 {mean(o2):.2f}")

print("\n== Stage turns on sharpened first pass, pair 1 v pair 2 (mean over tasks), and between first edit and first deploy")
for a in ARMS:
    e = [runs[(a, t)]["first_edit_turn"] for t in tasks]
    d = [fd[a][t] for t in tasks]
    gap = [dd - ee for dd, ee in zip(d, e) if dd is not None and ee is not None]
    print(f"  {a:6s} first edit {mean(e):.2f}; first deploy after edit {mean(d):.2f}; edit to deploy {mean(gap):.2f}; deploy count before first pass n/a")

print("\n== Turns from first edit to first deploy, what they contain (kinds per turn), by arm")
for a in ARMS:
    rows = defaultdict(list)
    for t in tasks:
        e = runs[(a, t)]["first_edit_turn"]
        d = fd[a][t]
        if e is None or d is None:
            continue
        tr = [x for x in turns[(a, t)] if e <= x["turn"] < d]
        fr = [x for x in feat["runs"][a][t] if e <= x["t"] < d]
        rows["n"].append(len(tr))
        rows["edit"].append(sum(x["k_edit"] for x in tr))
        rows["readonly"].append(sum(1 for x in tr if not (x["k_edit"] or x["k_build"] or x["k_test"] or x["k_privileged"])))
        rows["gobuild"].append(sum(1 for x in fr if x["gobuild"] or x["rebuild"]))
        rows["priv"].append(sum(x["k_privileged"] for x in tr))
        rows["test"].append(sum(x["k_test"] for x in tr))
        rows["failed"].append(sum((x["failed"] or 0) for x in tr))
        rows["out"].append(sum((x["output_tokens"] or 0) for x in tr))
    print(f"  {a:6s} " + " ".join(f"{k} {mean(v):7.2f}" for k, v in rows.items()))

write_json("s7_chat_taught.json", result)
