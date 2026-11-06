"""Where the turns before the first pass go, by arm and per task pair; turns spent on power; correlations with delay.

Kinds come from turns.csv (README rules: heuristics). 'read-only' = the only kinds are read/other/db with no edit/build/test.
Delay measures for B against A on the same task:
 D_fp: first passing point on the 5-turn grid, B minus A;
 D_w20: steps lost by B inside H=1..20 (sum of share A - share B over H=1..20).
For understanding only: correlations are across 27 tasks with one run each, not causes.
"""
from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
cur = curves["no_rollback_rows"]["turns"]
tasks = sorted(tc)
result = {}


def fp_grid(a, t):
    return runs[(a, t)]["first_pass_H_grid"]


def fp_any(a, t):
    return runs[(a, t)]["first_pass_H"]


def d_w20(A, B, t):
    return sum(cur["per_task"][A][t][h] - cur["per_task"][B][t][h] for h in range(1, 21))


def stats_before_first_pass(a, t, limit=None):
    """Counts over turns strictly before the first passing point on the grid (or all turns if never)."""
    fp = fp_grid(a, t)
    T = runs[(a, t)]["turns_T"]
    stop = fp if fp is not None else T
    if limit is not None:
        stop = min(stop, limit)
    rows = [r for r in turns[(a, t)] if r["turn"] <= stop]
    d = defaultdict(float)
    prev_in = None
    for i, r in enumerate(rows):
        d["n"] += 1
        d["calls"] += r["tool_calls"]
        d["out"] += r["output_tokens"] or 0
        d["reasoning"] += r["reasoning_tokens"] or 0
        ro = not (r["k_edit"] or r["k_build"] or r["k_test"] or r["k_privileged"])
        d["read_only"] += 1 if ro else 0
        d["edit"] += r["k_edit"]
        d["build"] += r["k_build"]
        d["test"] += r["k_test"]
        d["db"] += r["k_db"]
        d["priv"] += r["k_privileged"]
        d["failed"] += r["failed"] or 0
        d["killed"] += r["killed_by_restart"] or 0
        d["buildok"] += r["build_ok"] or 0
        if r["k_edit"]:
            d["out_edit"] += r["output_tokens"] or 0
        if ro:
            d["out_ro"] += r["output_tokens"] or 0
        # tool output size: growth of the input between this and the next call, minus what the model wrote
        allrows = turns[(a, t)]
        j = int(r["turn"])
        if j < len(allrows):
            grow = (allrows[j]["input_tokens"] or 0) - (r["input_tokens"] or 0) - (r["output_tokens"] or 0)
            d["tool_out_tokens"] += max(0, grow)
    return d


print("== A. Mean over tasks of counts in the turns up to the first passing point (5-turn grid)")
hdr = ["n", "read_only", "edit", "build", "test", "db", "priv", "failed", "killed", "calls", "out", "reasoning", "tool_out_tokens", "out_edit", "out_ro"]
tabA = {}
print("arm    " + " ".join(f"{h[:9]:>9s}" for h in hdr))
for a in ARMS:
    dd = [stats_before_first_pass(a, t) for t in tasks if fp_grid(a, t) is not None]
    row = {h: mean([d[h] for d in dd]) for h in hdr}
    tabA[a] = row
    print(f"{a:6s} " + " ".join(f"{row[h]:9.1f}" for h in hdr))
result["before_first_pass"] = tabA

print("\n== A2. Paired B minus A in those counts, mean over tasks")
for A, B in PAIRS:
    row = {}
    for h in hdr:
        row[h] = mean([stats_before_first_pass(B, t)[h] - stats_before_first_pass(A, t)[h] for t in tasks])
    print(f"{B}-{A} " + " ".join(f"{h}:{row[h]:+.1f}" for h in hdr))
    result[f"paired_{B}-{A}"] = row

print("\n== B. Stage turns: medians, means, paired differences")
stage_cols = ["first_edit_turn", "first_build_ok_turn", "first_own_test_turn", "first_own_test_beyond_health_turn", "first_pass_H_grid", "H_100_grid", "turns_T"]
for c in stage_cols:
    print(c, {a: (median([runs[(a, t)][c] for t in tasks]), round(mean([runs[(a, t)][c] for t in tasks]), 1)) for a in ARMS})
for A, B in PAIRS:
    for c in stage_cols:
        v = [runs[(B, t)][c] - runs[(A, t)][c] for t in tasks if runs[(B, t)][c] is not None and runs[(A, t)][c] is not None]
        pos = sum(x > 0 for x in v)
        neg = sum(x < 0 for x in v)
        print(f"  {B}-{A} {c:36s} n {len(v)} mean {mean(v):+.2f} median {median(v):+.1f} B later {pos} earlier {neg} sign p {sign_test_p(pos,neg):.3f} perm p {signflip_p(v, n=40000):.3f}")

print("\n== B2. Intervals: first edit -> first build ok -> first own test -> first pass (grid); paired means")
for a in ARMS:
    e2b = [runs[(a, t)]["first_build_ok_turn"] - runs[(a, t)]["first_edit_turn"] for t in tasks if runs[(a, t)]["first_build_ok_turn"] is not None and runs[(a, t)]["first_edit_turn"] is not None]
    b2t = [runs[(a, t)]["first_own_test_turn"] - runs[(a, t)]["first_build_ok_turn"] for t in tasks if runs[(a, t)]["first_build_ok_turn"] is not None and runs[(a, t)]["first_own_test_turn"] is not None]
    e2p = [runs[(a, t)]["first_pass_H_grid"] - runs[(a, t)]["first_edit_turn"] for t in tasks if runs[(a, t)]["first_pass_H_grid"] is not None and runs[(a, t)]["first_edit_turn"] is not None]
    print(a, "edit->build", round(mean(e2b), 2), "build->test", round(mean(b2t), 2), "edit->first pass", round(mean(e2p), 2))

print("\n== C. Privileged turns: when they fall relative to the first pass")
for a in ARMS:
    before = []
    after = []
    share15 = []
    kinds = defaultdict(int)
    for t in tasks:
        fp = fp_grid(a, t) or runs[(a, t)]["turns_T"]
        rows = turns[(a, t)]
        before.append(sum(r["k_privileged"] for r in rows if r["turn"] <= fp))
        after.append(sum(r["k_privileged"] for r in rows if r["turn"] > fp))
        first15 = [r for r in rows if r["turn"] <= 15]
        share15.append(sum(r["k_privileged"] for r in first15) / max(1, len(first15)))
        for r in rows:
            if r["k_privileged"] and r["turn"] <= fp:
                for k in (r["priv_rules"] or "").split(";"):
                    kinds[k.strip()] += 1
    print(f"{a:6s} priv turns up to first pass mean {mean(before):.2f} median {median(before):.0f}, runs with any {sum(1 for x in before if x)}; after {mean(after):.2f}; share of turns 1-15 {mean(share15):.3f}; rules {dict(sorted(kinds.items(), key=lambda kv:-kv[1]))}")

print("\n== D. Does a run's share of early turns on power predict its delay against the paired control? (for understanding)")
corr = {}
for A, B in PAIRS:
    delays_fp = [fp_grid(B, t) - fp_grid(A, t) for t in tasks]
    delays_w = [d_w20(A, B, t) for t in tasks]
    preds = {
        "B priv turns up to first pass": [stats_before_first_pass(B, t)["priv"] for t in tasks],
        "B priv share of turns 1-15": [sum(r["k_privileged"] for r in turns[(B, t)] if r["turn"] <= 15) / max(1, len([r for r in turns[(B, t)] if r["turn"] <= 15])) for t in tasks],
        "B minus A priv turns in 1-15": [sum(r["k_privileged"] for r in turns[(B, t)] if r["turn"] <= 15) - sum(r["k_privileged"] for r in turns[(A, t)] if r["turn"] <= 15) for t in tasks],
        "B priv turns in 1-10": [sum(r["k_privileged"] for r in turns[(B, t)] if r["turn"] <= 10) for t in tasks],
        "B first priv turn (None if none)": [runs[(B, t)]["first_privileged_attempt_turn"] for t in tasks],
        "A extra calls by H=10 minus B's": [(sum(r["tool_calls"] for r in turns[(A, t)] if r["turn"] <= 10) - len([r for r in turns[(A, t)] if r["turn"] <= 10])) - (sum(r["tool_calls"] for r in turns[(B, t)] if r["turn"] <= 10) - len([r for r in turns[(B, t)] if r["turn"] <= 10])) for t in tasks],
        "A minus B output tokens per turn in 1-10": [mean([r["output_tokens"] for r in turns[(A, t)] if r["turn"] <= 10]) - mean([r["output_tokens"] for r in turns[(B, t)] if r["turn"] <= 10]) for t in tasks],
        "A killed-by-restart turns in 1-10": [sum(r["killed_by_restart"] or 0 for r in turns[(A, t)] if r["turn"] <= 10) for t in tasks],
        "B minus A read-only turns up to first pass": [stats_before_first_pass(B, t)["read_only"] - stats_before_first_pass(A, t)["read_only"] for t in tasks],
        "B minus A first edit turn": [runs[(B, t)]["first_edit_turn"] - runs[(A, t)]["first_edit_turn"] if runs[(B, t)]["first_edit_turn"] and runs[(A, t)]["first_edit_turn"] else None for t in tasks],
        "B minus A first build ok": [runs[(B, t)]["first_build_ok_turn"] - runs[(A, t)]["first_build_ok_turn"] if runs[(B, t)]["first_build_ok_turn"] and runs[(A, t)]["first_build_ok_turn"] else None for t in tasks],
    }
    print(f"{B}-{A}")
    for name, x in preds.items():
        r1, p1 = spearman(x, delays_fp), perm_corr_p(x, delays_fp, n=4000)
        r2, p2 = spearman(x, delays_w), perm_corr_p(x, delays_w, n=4000)
        print(f"  {name:44s} mean {mean(x):+7.2f}  vs first-pass delay: rho {fmt(r1,2,True)} p {fmt(p1,3)}; vs steps lost 1..20: rho {fmt(r2,2,True)} p {fmt(p2,3)}")
        corr[f"{B}-{A}: {name}"] = {"mean": mean(x), "rho_fp": r1, "p_fp": p1, "rho_w20": r2, "p_w20": p2}
result["correlations"] = corr

print("\n== E. Within B, runs with no privileged turn before the first pass against those with one: delay against A")
for A, B in PAIRS:
    g0, g1 = [], []
    w0, w1 = [], []
    for t in tasks:
        p = stats_before_first_pass(B, t)["priv"]
        d = fp_grid(B, t) - fp_grid(A, t)
        (g1 if p else g0).append(d)
        (w1 if p else w0).append(d_w20(A, B, t))
    print(f"{B}-{A}: no priv before first pass n={len(g0)} mean fp delay {fmt(mean(g0),2,True)}, steps lost {fmt(mean(w0),2,True)}; with priv n={len(g1)} mean fp delay {fmt(mean(g1),2,True)}, steps lost {fmt(mean(w1),2,True)}")

print("\n== F. Output per turn by turn number (mean), and share of first-10 turns with kinds")
for a in ARMS:
    print(a, "out tokens per turn at T=1..10:", [round(mean([turns[(a, t)][i]["output_tokens"] for t in tasks if len(turns[(a, t)]) > i])) for i in range(10)])
    print(a, "calls by turn 1..6:", [round(mean([turns[(a, t)][i]["tool_calls"] for t in tasks if len(turns[(a, t)]) > i]), 2) for i in range(6)], "tool output tokens by turn 1..6:", [round(mean([max(0, (turns[(a, t)][i + 1]["input_tokens"] or 0) - (turns[(a, t)][i]["input_tokens"] or 0) - (turns[(a, t)][i]["output_tokens"] or 0)) for t in tasks if len(turns[(a, t)]) > i + 1])) for i in range(6)])

print("\n== G. Pair 1 against pair 2, task by task: mean of the two arms at H=10 and first pass, and stage turns")
rows = []
for t in tasks:
    p1 = (cur["per_task"]["A1"][t][10] + cur["per_task"]["B1"][t][10]) / 2
    p2 = (cur["per_task"]["A2"][t][10] + cur["per_task"]["B2"][t][10]) / 2
    fp1 = (fp_grid("A1", t) + fp_grid("B1", t)) / 2
    fp2 = (fp_grid("A2", t) + fp_grid("B2", t)) / 2
    e1 = mean([runs[("A1", t)]["first_edit_turn"], runs[("B1", t)]["first_edit_turn"]])
    e2 = mean([runs[("A2", t)]["first_edit_turn"], runs[("B2", t)]["first_edit_turn"]])
    rows.append((p1 - p2, short(t), round(p1, 2), round(p2, 2), fp1, fp2, e1, e2, runs[("A1", t)]["turns_T"], runs[("B1", t)]["turns_T"], runs[("A2", t)]["turns_T"], runs[("B2", t)]["turns_T"]))
rows.sort(reverse=True)
print("diff@10, task, pair1@10, pair2@10, fp1, fp2, edit1, edit2, T A1,B1,A2,B2")
for r in rows:
    print("  ", (round(r[0], 2),) + r[1:])
n_better = sum(1 for r in rows if r[0] > 1e-9)
n_worse = sum(1 for r in rows if r[0] < -1e-9)
print("pair 1 better at H=10:", n_better, "worse", n_worse, "same", 27 - n_better - n_worse, "sign p", round(sign_test_p(n_better, n_worse), 5))
d_fp = [r[4] - r[5] for r in rows]
print("first pass pair1-pair2: mean", round(mean(d_fp), 2), "earlier in", sum(1 for x in d_fp if x < 0), "later in", sum(1 for x in d_fp if x > 0), "perm p", signflip_p(d_fp))

write_json("s3_stages.json", result)
