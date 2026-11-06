"""The table of work up to the first pass, on the 26 tasks other than audit_log_tamper_detection, where A1 has test cases passing
at H=0 so its first pass isn't a turn. First pass is read by restart turn (s5). Same tasks in every arm.
"""
from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
feat = json.load(open(OUT / "features.json"))
sg = json.load(open(OUT / "s5_deploy_gate.json"))
fp = sg["fp"]
tasks = [t for t in sorted(tc) if t != "audit_log_tamper_detection"]
print("n tasks", len(tasks))


def work(a, t):
    f = fp[a][t]
    tr = [r for r in turns[(a, t)] if r["turn"] <= f]
    fr = [r for r in feat["runs"][a][t] if r["t"] <= f]
    e = runs[(a, t)]["first_edit_turn"]
    return {
        "turns": len(tr), "calls": sum(r["tool_calls"] for r in tr), "statements": sum(r["n_stmt"] for r in fr),
        "command_chars": sum(r["cmd_chars"] for r in fr), "tool_output_chars": sum(r["out_chars"] for r in fr),
        "output_tokens": sum(r["output_tokens"] or 0 for r in tr), "reasoning_tokens": sum(r["reasoning_tokens"] or 0 for r in tr),
        "privileged_turns": sum(r["k_privileged"] for r in tr), "read_only_turns": sum(1 for r in tr if not (r["k_edit"] or r["k_build"] or r["k_test"] or r["k_privileged"])),
        "edit_turns": sum(r["k_edit"] for r in tr),
    }


W = {a: {t: work(a, t) for t in tasks} for a in ARMS}
keys = list(W["A1"][tasks[0]].keys())
print("mean per task")
for k in keys:
    print(f"  {k:20s} " + " ".join(f"{a}:{mean([W[a][t][k] for t in tasks]):9.1f}" for a in ARMS))
print("  non-reasoning output " + " ".join(f"{a}:{mean([W[a][t]['output_tokens']-W[a][t]['reasoning_tokens'] for t in tasks]):9.1f}" for a in ARMS))
print("  output tokens per turn " + " ".join(f"{a}:{mean([W[a][t]['output_tokens'] for t in tasks])/mean([W[a][t]['turns'] for t in tasks]):9.1f}" for a in ARMS))
print("  statements per turn " + " ".join(f"{a}:{mean([W[a][t]['statements'] for t in tasks])/mean([W[a][t]['turns'] for t in tasks]):9.2f}" for a in ARMS))
print("  calls per turn " + " ".join(f"{a}:{mean([W[a][t]['calls'] for t in tasks])/mean([W[a][t]['turns'] for t in tasks]):9.2f}" for a in ARMS))
print("paired B minus A, for understanding")
for A, B in PAIRS:
    for k in keys:
        d = [W[B][t][k] - W[A][t][k] for t in tasks]
        pos = sum(1 for x in d if x > 0)
        neg = sum(1 for x in d if x < 0)
        print(f"  {B}-{A} {k:20s} mean {mean(d):+9.2f} sd {sd(d):9.2f}; B more {pos}, less {neg}; perm p {signflip_p(d,n=40000):.3f}")

print("\ntop 10 B lag and top 10 B lead on these 26 tasks")
for A, B in PAIRS:
    for lab, rev in (("lag", True), ("lead", False)):
        order = sorted(tasks, key=lambda t: (fp[B][t] - fp[A][t]) * (-1 if rev else 1))[:10]
        rows = []
        for t in order:
            ea = runs[(A, t)]["first_edit_turn"] or 0
            eb = runs[(B, t)]["first_edit_turn"] or 0
            ca = sum(r["tool_calls"] for r in turns[(A, t)] if r["turn"] < ea)
            cb = sum(r["tool_calls"] for r in turns[(B, t)] if r["turn"] < eb)
            rows.append((fp[A][t], fp[B][t], ea, eb, ca, cb, W[A][t]["privileged_turns"], W[B][t]["privileged_turns"]))
        m = [mean([r[i] for r in rows]) for i in range(8)]
        print(f"  {B}-{A} {lab}: first pass {m[0]:.1f} {m[1]:.1f}; first edit {m[2]:.1f} {m[3]:.1f}; calls before edit {m[4]:.1f} {m[5]:.1f}; privileged up to first pass {m[6]:.2f} {m[7]:.2f}; {[short(t) for t in order]}")

print("\nprivileged turns up to first pass against delay, these 26 tasks, Spearman (for understanding)")
for A, B in PAIRS:
    x = [W[B][t]["privileged_turns"] for t in tasks]
    y = [fp[B][t] - fp[A][t] for t in tasks]
    x2 = [W[B][t]["privileged_turns"] - W[A][t]["privileged_turns"] for t in tasks]
    print(f"  {B}-{A}: B's count rho {fmt(spearman(x,y),2,True)} p {fmt(perm_corr_p(x,y,n=4000),3)}; B minus A rho {fmt(spearman(x2,y),2,True)} p {fmt(perm_corr_p(x2,y,n=4000),3)}")
    g0 = [fp[B][t] - fp[A][t] for t in tasks if W[B][t]["privileged_turns"] == 0]
    g1 = [fp[B][t] - fp[A][t] for t in tasks if W[B][t]["privileged_turns"] > 0]
    print(f"     runs with none n={len(g0)} delay {fmt(mean(g0),2,True)}; with some n={len(g1)} delay {fmt(mean(g1),2,True)}")

print("\nturns after first pass, on these 26 tasks")
after = {a: {t: runs[(a, t)]["turns_T"] - fp[a][t] for t in tasks} for a in ARMS}
print("  " + " ".join(f"{a}:{mean(list(after[a].values())):.1f}" for a in ARMS))
for A, B in PAIRS:
    d = [after[B][t] - after[A][t] for t in tasks]
    print(f"  {B}-{A} mean {mean(d):+.2f} perm p {signflip_p(d,n=40000):.4f}")
