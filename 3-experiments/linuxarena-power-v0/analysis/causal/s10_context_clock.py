"""Chat length, model time, run order, timeouts and commands killed by their own restart.

For understanding only: arms differ by chat size at 4 levels, so chat size is confounded with the trajectory and the pair.
"""
from common import *

runs = load_runs()
turns = load_turns()
tasks = sorted(load_tc())
feat = json.load(open(OUT / "features.json"))
sg = json.load(open(OUT / "s5_deploy_gate.json"))
fp = sg["fp"]
result = {}

print("== 1. Chat size and behaviour, by arm")
for a in ARMS:
    inp = mean([runs[(a, t)]["first_call_input_tokens"] for t in tasks])
    tot = mean([runs[(a, t)]["total_tokens"] for t in tasks])
    allt = [r for t in tasks for r in turns[(a, t)]]
    secs = sum(r["model_seconds"] or 0 for r in allt)
    outs = sum(r["output_tokens"] or 0 for r in allt)
    reas = sum(r["reasoning_tokens"] or 0 for r in allt)
    print(f"  {a:6s} first input {inp:8.0f} total {tot:10.0f}; output/turn {outs/len(allt):5.0f}; reasoning/turn {reas/len(allt):5.0f}; model s/turn {secs/len(allt):5.2f}; model s per 1000 output tokens {1000*secs/max(1,outs):5.2f}; turns with no call {sum(1 for r in allt if not r['tool_calls'])}; failed model calls {sum(runs[(a,t)]['failed_model_calls'] for t in tasks):.0f}")

print("\n== 2. Inside a run: do output tokens or model seconds per output token change as the chat grows? Mean over runs by turn band")
for a in ARMS:
    bands = {}
    for lo, hi in ((1, 5), (6, 10), (11, 20), (21, 40), (41, 80)):
        rows = [r for t in tasks for r in turns[(a, t)] if lo <= r["turn"] <= hi]
        if rows:
            s = sum(r["model_seconds"] or 0 for r in rows)
            o = sum(r["output_tokens"] or 0 for r in rows)
            bands[f"{lo}-{hi}"] = (len(rows), round(o / len(rows)), round(1000 * s / max(1, o), 1), round(mean([r["input_tokens"] for r in rows]) / 1000))
    print(f"  {a:6s} (turns, out/turn, model s per 1k out, k input): {bands}")

print("\n== 3. Trajectory style against its solvers: calls/turn, reasoning/turn, output/turn")
for a in TRAJ:
    d = next((EXP / "runs" / TRAJ[a]).glob("*/e1-*"))
    u = list(csv.DictReader(open(d / "usage.csv")))
    print(f"  {a} columns {list(u[0].keys())[:8]}" if a == "A1" else "", end="")
    keyo = next(k for k in u[0] if "output" in k)
    keyr = next((k for k in u[0] if "reason" in k), None)
    rows = [x for x in u if int(float(x[keyo] or 0)) > 0]
    o = sum(int(float(x[keyo] or 0)) for x in rows)
    r = sum(int(float(x[keyr] or 0)) for x in rows) if keyr else 0
    allt = [x for t in tasks for x in turns[(a, t)]]
    so = sum(x["output_tokens"] or 0 for x in allt)
    sr = sum(x["reasoning_tokens"] or 0 for x in allt)
    fr = feat["traj"][a]
    last20 = [x for x in fr[-20:]]
    print(f"  {a} trajectory turns {len(rows)}: output/turn {o/len(rows):.0f}, reasoning/turn {r/len(rows):.0f}; solver: output/turn {so/len(allt):.0f}, reasoning/turn {sr/len(allt):.0f}; trajectory restart turns {sum(1 for x in fr if x['restart'])} statements per step {mean([x['n_stmt'] for x in fr]):.1f}; solver statements per turn {mean([x['n_stmt'] for t in tasks for x in feat['runs'][a][t]]):.1f}")
print("  across the 4 trajectories, the trajectory's calls per turn, against solver turn-1 calls: see s2 G")

print("\n== 4. Run order: first call UTC by arm, and within an arm whether later runs differ")
for a in ARMS:
    st = sorted(runs[(a, t)]["first_call_utc"] for t in tasks)
    print(f"  {a:6s} first {st[0]} last {st[-1]}")
print("  Spearman inside an arm: start order against first pass, and against model s per 1k output")
for a in ARMS:
    order = sorted(tasks, key=lambda t: runs[(a, t)]["first_call_utc"])
    idx = [order.index(t) for t in tasks]
    y = [fp[a][t] for t in tasks]
    z = [1000 * sum(r["model_seconds"] or 0 for r in turns[(a, t)]) / max(1, sum(r["output_tokens"] or 0 for r in turns[(a, t)])) for t in tasks]
    print(f"    {a:6s} vs first pass rho {fmt(spearman(idx,y),2,True)}; vs model s/1k out rho {fmt(spearman(idx,z),2,True)}")

print("\n== 5. Timeouts")
for a in ARMS:
    rows = [(short(t), int(r["turn"]), r["tool_seconds"]) for t in tasks for r in turns[(a, t)] if r["timeout"]]
    print(f"  {a:6s} {rows}")

print("\n== 6. Commands killed by their own restart: turns, position, what the next turn does, cost")
for a in ARMS:
    kills = []
    nxt_check = 0
    nxt_total = 0
    before_fp = 0
    for t in tasks:
        rows = turns[(a, t)]
        f = fp[a][t] or 999
        for i, r in enumerate(rows):
            if r["killed_by_restart"]:
                kills.append(r["turn"])
                if r["turn"] <= f:
                    before_fp += 1
                if i + 1 < len(rows):
                    nxt_total += 1
                    n = rows[i + 1]
                    if not n["k_edit"] and not n["k_build"]:
                        nxt_check += 1
    kinds = [r for t in tasks for r in turns[(a, t)] if r["killed_by_restart"]]
    print(f"  {a:6s} killed turns {len(kills)}; in T1-10 {sum(1 for k in kills if k<=10)}; up to first pass {before_fp} ({before_fp/27:.2f} per run); next turn neither edits nor builds {nxt_check}/{nxt_total}; killed turn also edits {sum(1 for r in kinds if r['k_edit'])}")
print("  how a restart is issued in the first deploy: alone or chained with others (share of restart turns with 2+ statements)")
for a in ARMS:
    rs = [x for t in tasks for x in feat["runs"][a][t] if x["restart"]]
    print(f"  {a:6s} restart turns {len(rs)}; statements per restart turn mean {mean([x['n_stmt'] for x in rs]):.1f}; alone (1 statement) {sum(1 for x in rs if x['n_stmt']<=1)}; cmd chars mean {mean([x['cmd_chars'] for x in rs]):.0f}")
print("  in the trajectories' last 40 steps")
for a in TRAJ:
    fr = feat["traj"][a]
    rs = [x for x in fr[-40:] if x["restart"]]
    rs_all = [x for x in fr if x["restart"]]
    print(f"  {a} restarts in the last 40 steps {len(rs)}; statements {[x['n_stmt'] for x in rs]}; whole trajectory {[x['n_stmt'] for x in rs_all]}")

print("\n== 7. After the first pass: turns left, what they do")
for a in ARMS:
    rows = defaultdict(list)
    for t in tasks:
        f = fp[a][t] or int(runs[(a, t)]["turns_T"])
        tr = [r for r in turns[(a, t)] if r["turn"] > f]
        rows["after"].append(len(tr))
        rows["test"].append(sum(r["k_test"] for r in tr))
        rows["priv"].append(sum(r["k_privileged"] for r in tr))
        rows["db"].append(sum(r["k_db"] for r in tr))
        rows["edit"].append(sum(r["k_edit"] for r in tr))
        rows["build"].append(sum(r["k_build"] for r in tr))
    print(f"  {a:6s} " + " ".join(f"{k} {mean(v):5.1f}" for k, v in rows.items()))

print("\n== 8. Solver's own privileged turns: which rule and how many (all turns), to see how much is SQL for tests")
for a in ARMS:
    c = defaultdict(int)
    for t in tasks:
        for r in turns[(a, t)]:
            if r["k_privileged"]:
                for k in (r["priv_rules"] or "").split(";"):
                    c[k.strip()] += 1
    print(f"  {a:6s} {dict(sorted(c.items(), key=lambda kv:-kv[1]))}")
