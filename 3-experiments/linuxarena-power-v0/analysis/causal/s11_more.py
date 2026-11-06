"""Remaining checks: tasks whose scorer needs the solver's deploy; never-pass test cases; run length against end share; turn-size
arithmetic; attribution of the 'never' part; every-turn check of the jumpy gap at H = 10 and 11; pair 1 vs pair 2 on A arms only.
"""
from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
feat = json.load(open(OUT / "features.json"))
sg = json.load(open(OUT / "s5_deploy_gate.json"))
fp = sg["fp"]
cur = curves["no_rollback_rows"]["turns"]
curw = curves["with_rollback_rows"]["turns"]
tasks = sorted(tc)
result = {}


def restarts(a, t):
    return [r["t"] for r in feat["runs"][a][t] if r["restart"] or r["otherstart"]]


# 1. deploy-gated tasks: no arm has a counted test case passing before that arm's first restart (H=0 excluded)
gated, ungated = [], []
for t in tasks:
    early = 0
    for a in ARMS:
        rs = restarts(a, t)
        fr = rs[0] if rs else 10 ** 6
        for p in all_points(tc, a, t):
            if 0 < p["H"] < fr and p["share"] > 0.15:
                early += 1
                break
    (ungated if early else gated).append(t)
print("== 1. Tasks needing the solver's own deploy (no arm passes more than a stray test case before its first restart):", len(gated))
print("  ", [short(t) for t in gated])
print("  others:", len(ungated), [short(t) for t in ungated])
result["gated"] = [short(t) for t in gated]
for A, B in PAIRS:
    for nm, grp in (("deploy-gated", gated), ("others", ungated)):
        vals = {H: mean([cur["per_task"][B][t][H] - cur["per_task"][A][t][H] for t in grp]) for H in (5, 10, 15, 20)}
        w = mean([sum(cur["per_task"][B][t][h] - cur["per_task"][A][t][h] for h in range(1, 21)) for t in grp])
        fpd = mean([fp[B][t] - fp[A][t] for t in grp])
        print(f"  {B}-{A} {nm}: " + " ".join(f"H={h}: {v:+.3f}" for h, v in vals.items()) + f"; steps inside 1..20 per test case on these tasks {w:+.2f}; first pass {fpd:+.2f} turns")
print("  deploy turn against first pass on gated tasks, every arm: mean first pass", {a: round(mean([fp[a][t] for t in gated]), 2) for a in ARMS}, "others", {a: round(mean([fp[a][t] for t in ungated]), 2) for a in ARMS})

# 2. Never-pass in all arms
print("\n== 2. Test cases failing at the end in all five arms, by task (share of the task's counted test cases)")
tot_w = 0
for t in tasks:
    u = {a: tc_units(tc, curves, a, t) for a in ARMS}
    n = len(u["before"])
    never = [u["before"][i][0] for i in range(n) if all(u[a][i][2][-1][1] == 0 for a in ARMS)]
    if never:
        tot_w += len(never) / n / 27
        print(f"  {short(t):24s} {len(never)}/{n}: {[x[:32] for x in never][:6]}")
print("  weight:", round(tot_w, 4))
result["never_all_arms_weight"] = tot_w

# 3. Run length against end share and tests after first pass
print("\n== 3. B minus A in run length against end share (for understanding)")
for A, B in PAIRS:
    dT = [runs[(B, t)]["turns_T"] - runs[(A, t)]["turns_T"] for t in tasks]
    dE = [runs[(B, t)]["end_share"] - runs[(A, t)]["end_share"] for t in tasks]
    print(f"  {B}-{A}: mean dT {mean(dT):+.2f} (B shorter in {sum(1 for x in dT if x<0)}, longer {sum(1 for x in dT if x>0)}); perm p {signflip_p(dT,n=40000):.3f}; mean dEnd {mean(dE):+.3f} tasks lower in B {sum(1 for x in dE if x<-1e-9)} higher {sum(1 for x in dE if x>1e-9)}; rho {fmt(spearman(dT,dE),2,True)}; rows with an end difference: {[(short(t), runs[(A,t)]['turns_T'], runs[(B,t)]['turns_T'], round(runs[(A,t)]['end_share'],2), round(runs[(B,t)]['end_share'],2)) for t in tasks if abs(runs[(B,t)]['end_share']-runs[(A,t)]['end_share'])>1e-9]}")
    aft = [(runs[(B, t)]["turns_T"] - (fp[B][t] or 0)) - (runs[(A, t)]["turns_T"] - (fp[A][t] or 0)) for t in tasks]
    print(f"     turns after first pass, B minus A: mean {mean(aft):+.2f} perm p {signflip_p(aft,n=40000):.3f}")

# 4. Attribution of 'never' by test case and arm in steps per test case
print("\n== 4. The never part by task, in steps per test case over 27 tasks")
for A, B in PAIRS:
    rows = []
    for t in tasks:
        ua, ub = tc_units(tc, curves, A, t), tc_units(tc, curves, B, t)
        s = 0
        for (nm, w, sa), (_, _, sb) in zip(ua, ub):
            if sa[-1][1] != sb[-1][1]:
                s += w * (steps_counted(sb) - steps_counted(sa))
        if abs(s) > 1e-9:
            rows.append((short(t), round(s / 27, 3)))
    print(f"  {B}-{A}: {sorted(rows, key=lambda r:r[1])}; total {sum(r[1] for r in rows):+.3f}")

# 5. Every-turn check of the gap at H=8..16, tasks with no gap in both arms, grid against every-turn
print("\n== 5. Every-turn truth on tasks with no gap in both arms, at H=8..16 (B minus A)")
for A, B in PAIRS:
    sub = [t for t in tasks if runs[(A, t)]["max_gap_between_points"] == 1 and runs[(B, t)]["max_gap_between_points"] == 1]
    print(f"  {B}-{A} n={len(sub)}: " + " ".join(f"H={h}: {mean([curw['per_task'][B][t][h]-curw['per_task'][A][t][h] for t in sub]):+.3f}" for h in range(5, 21)))

# A wider check: a run with every-turn rows in only one arm: difference between that run's exact first pass and the sharpened one
print("\n== 5b. Sharpened first pass against the exact first pass, runs with no gap")
for a in ARMS:
    d = []
    for t in tasks:
        if runs[(a, t)]["max_gap_between_points"] != 1:
            continue
        ex = next((p["H"] for p in all_points(tc, a, t) if p["share"] > 0), None)
        if ex is not None and fp[a][t] is not None:
            d.append(fp[a][t] - ex)
    print(f"  {a:6s} n {len(d)}: sharpened minus exact, mean {mean(d):+.2f}, max abs {max(abs(x) for x in d) if d else 0}; exact in {sum(1 for x in d if x==0)}")

# 6. Pair 1 vs pair 2 on A arms and on B arms, separately
print("\n== 6. Pair 1 against pair 2 with the same kind of arm")
for x, y in (("A1", "A2"), ("B1", "B2"), ("A1", "B2"), ("B1", "A2")):
    d = [fp[y][t] - fp[x][t] for t in tasks]
    h10 = [cur["per_task"][x][t][10] - cur["per_task"][y][t][10] for t in tasks]
    print(f"  {x} vs {y}: first pass later in {y} by mean {mean(d):+.2f} (earlier {sum(1 for v in d if v<0)}, later {sum(1 for v in d if v>0)}); H=10 gap {mean(h10):+.3f}; steps over 1..80 {(cur['mean_1_80'][x]-cur['mean_1_80'][y])*80:+.2f}")

# 7. Work per turn in the same tasks, every turn up to the first pass: turn-size arithmetic
print("\n== 7. Turn-size arithmetic: if each turn before first pass did A's or B's mean work, how far does a run get?")
for A, B in PAIRS:
    rows = []
    for t in tasks:
        fa, fb = fp[A][t], fp[B][t]
        if not fa or not fb:
            continue
        ca = sum(x["tool_calls"] for x in turns[(A, t)] if x["turn"] <= fa)
        cb = sum(x["tool_calls"] for x in turns[(B, t)] if x["turn"] <= fb)
        sa = sum(x["n_stmt"] for x in feat["runs"][A][t] if x["t"] <= fa)
        sb = sum(x["n_stmt"] for x in feat["runs"][B][t] if x["t"] <= fb)
        oa = sum(x["output_tokens"] or 0 for x in turns[(A, t)] if x["turn"] <= fa)
        ob = sum(x["output_tokens"] or 0 for x in turns[(B, t)] if x["turn"] <= fb)
        rows.append((fb - fa, cb - ca, sb - sa, ob - oa))
    print(f"  {B}-{A} to first pass, n={len(rows)}: turns {mean([r[0] for r in rows]):+.2f} (perm p {signflip_p([r[0] for r in rows],n=40000):.3f}); calls {mean([r[1] for r in rows]):+.2f} (p {signflip_p([r[1] for r in rows],n=40000):.3f}); statements {mean([r[2] for r in rows]):+.1f} (p {signflip_p([r[2] for r in rows],n=40000):.3f}); output tokens {mean([r[3] for r in rows]):+.0f} (p {signflip_p([r[3] for r in rows],n=40000):.3f})")
print("\n== 8. Output includes reasoning? turns where reasoning > output")
n = bad = 0
for k, v in turns.items():
    for r in v:
        n += 1
        if (r["reasoning_tokens"] or 0) > (r["output_tokens"] or 0):
            bad += 1
print(n, bad)

print("\n== 9. Turn-1 calls per run and trajectory's last 20 turns' calls")
for a in TRAJ:
    d = next((EXP / "runs" / TRAJ[a]).glob("*/e1-*"))
    print(a, "solver T1 calls", round(mean([turns[(a, t)][0]["tool_calls"] for t in tasks]), 2), "solver multi-call share turns 1-3", round(mean([1 if r["tool_calls"] > 1 else 0 for t in tasks for r in turns[(a, t)][:3]]), 2))

write_json("s11_more.json", result)
