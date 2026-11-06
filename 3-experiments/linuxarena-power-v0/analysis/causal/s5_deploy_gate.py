"""Do test cases start passing only once the solver deploys? If so, the first deploy gives the first pass's turn exactly.

1. On runs with every-turn rows: first passing turn against first restart turn.
2. A sharpened curve for every run: a change in share between two scored points is placed at the last restart inside
   that interval (at the later point if there's none). Checked against the every-turn rows.
3. With the sharpened curves: POWER and B minus A per turn, first pass, and where the lag sits.
Grid = 5-turn points only for the inputs, so that all arms are treated alike; the every-turn rows are used only to check.
"""
from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
feat = json.load(open(OUT / "features.json"))
cur = curves["no_rollback_rows"]["turns"]
curw = curves["with_rollback_rows"]["turns"]
tasks = sorted(tc)
result = {}


def restarts(a, t):
    return [r["t"] for r in feat["runs"][a][t] if r["restart"] or r["otherstart"]]


def first_edit(a, t):
    return runs[(a, t)]["first_edit_turn"]


print("== 1. Every-turn runs: first passing turn against first restart")
gate = defaultdict(list)
for a in ARMS:
    for t in tasks:
        if runs[(a, t)]["max_gap_between_points"] != 1:
            continue
        pts = all_points(tc, a, t)
        fp = next((p["H"] for p in pts if p["share"] > 0 and p["H"] > 0), None)
        rs = restarts(a, t)
        fr = rs[0] if rs else None
        gate[a].append((short(t), fp, fr, (fp - fr) if fp is not None and fr is not None else None))
for a in ARMS:
    d = [x[3] for x in gate[a] if x[3] is not None]
    print(f"{a}: runs {len(gate[a])}; first pass before first restart {sum(1 for x in d if x<0)}; same turn {sum(1 for x in d if x==0)}; 1 turn after {sum(1 for x in d if x==1)}; later {sum(1 for x in d if x>1)}; no restart/no pass {len(gate[a])-len(d)}")
    print("   ", [x for x in gate[a] if x[3] is None or x[3] < 0 or x[3] > 2][:12])
result["gate"] = {a: gate[a] for a in gate}

print("\n== 1b. All runs on the grid: any scored point passing before the first restart? (by task)")
pre = defaultdict(dict)
for a in ARMS:
    for t in tasks:
        rs = restarts(a, t)
        fr = rs[0] if rs else 10 ** 6
        pts = grid_points(tc, curves, a, t)
        early = [p for p in pts if p["H"] < fr and p["share"] > 0]
        if early:
            pre[t][a] = (early[0]["H"], round(early[0]["share"], 2), fr if fr < 10 ** 6 else None)
for t, v in pre.items():
    print("  ", short(t), v)


def sharpened(a, t):
    """list of share per H=0..80. Between scored points: value holds; a change is placed at the last restart inside the interval."""
    pts = grid_points(tc, curves, a, t)
    rs = restarts(a, t)
    T = int(runs[(a, t)]["turns_T"])
    change = []  # (turn, value)
    prev = pts[0]
    change.append((0, prev["share"]))
    for p in pts[1:]:
        if abs(p["share"] - prev["share"]) > 1e-9:
            inside = [r for r in rs if prev["H"] < r <= p["H"]]
            at = inside[-1] if inside else p["H"]
            change.append((at, p["share"]))
        prev = p
    out = []
    v = change[0][1]
    j = 0
    for H in range(0, 81):
        while j + 1 < len(change) and change[j + 1][0] <= H:
            j += 1
            v = change[j][1]
        out.append(v)
    return out


print("\n== 2. Check of the sharpened curve against every-turn rows: mean absolute error per turn, over runs with no gap, H=1..T")
errs = defaultdict(lambda: [0.0, 0.0, 0])
for a in ARMS:
    for t in tasks:
        if runs[(a, t)]["max_gap_between_points"] != 1:
            continue
        T = int(runs[(a, t)]["turns_T"])
        truth = curw["per_task"][a][t]
        grid = cur["per_task"][a][t]
        sh = sharpened(a, t)
        for H in range(1, T + 1):
            errs[a][0] += abs(grid[H] - truth[H])
            errs[a][1] += abs(sh[H] - truth[H])
            errs[a][2] += 1
for a in ARMS:
    g, s, n = errs[a]
    print(f"  {a}: turns {n}; error of last-scored 5-turn reading {g/n:.4f}; error of the sharpened reading {s/n:.4f}")
result["sharpen_check"] = {a: {"grid": errs[a][0] / errs[a][2], "sharp": errs[a][1] / errs[a][2], "n": errs[a][2]} for a in ARMS}

# ---- 3. sharpened POWER
sharp = {a: {t: sharpened(a, t) for t in tasks} for a in ARMS}
P = {a: [mean([sharp[a][t][H] for t in tasks]) for H in range(0, 81)] for a in ARMS}
print("\n== 3. POWER on the sharpened curves (no new scoring; a reading, not a measurement)")
print("H      " + " ".join(f"{H:6d}" for H in (3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 25, 30)))
for a in ARMS:
    print(f"{a:6s} " + " ".join(f"{P[a][H]:6.3f}" for H in (3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 25, 30)))
for A, B in PAIRS:
    print(f"{B}-{A:3s} " + " ".join(f"{P[B][H]-P[A][H]:+6.3f}" for H in (3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 25, 30)))
    print(f"   steps inside 1..10 {sum(P[B][H]-P[A][H] for H in range(1,11)):+.2f}, 1..20 {sum(P[B][H]-P[A][H] for H in range(1,21)):+.2f}, 1..30 {sum(P[B][H]-P[A][H] for H in range(1,31)):+.2f}, 1..80 {sum(P[B][H]-P[A][H] for H in range(1,81)):+.2f}")
    # horizontal lag by level
    lags = []
    for lv in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        def first(curve):
            return next((H for H in range(0, 81) if curve[H] >= lv), None)
        ha, hb = first(P[A]), first(P[B])
        lags.append((lv, ha, hb, None if ha is None or hb is None else hb - ha))
    print("   turn each curve first reaches a level (level, A, B, B minus A):", lags)
result["sharp_power"] = {a: P[a] for a in ARMS}

print("\n== 4. First pass on the sharpened curves, paired; first deploy; and the intervals")
fp = {a: {t: next((H for H in range(0, 81) if sharp[a][t][H] > 0), None) for t in tasks} for a in ARMS}
fd = {a: {t: (restarts(a, t)[0] if restarts(a, t) else None) for t in tasks} for a in ARMS}
fd_after_edit = {}
for a in ARMS:
    fd_after_edit[a] = {}
    for t in tasks:
        e = first_edit(a, t)
        rs = restarts(a, t)
        fd_after_edit[a][t] = next((r for r in rs if e is not None and r >= e), None)
for a in ARMS:
    print(f"{a:6s} first pass mean {mean(list(fp[a].values())):.2f} median {median(list(fp[a].values()))}; first deploy mean {mean(list(fd[a].values())):.2f} median {median(list(fd[a].values()))} n {sum(1 for v in fd[a].values() if v is not None)}; first deploy at or after first edit mean {mean(list(fd_after_edit[a].values())):.2f}; first edit mean {mean([first_edit(a,t) for t in tasks]):.2f}; deploys per run {mean([len(restarts(a,t)) for t in tasks]):.1f}")
for A, B in PAIRS:
    for name, d in (("first pass", fp), ("first deploy after first edit", fd_after_edit)):
        v = [d[B][t] - d[A][t] for t in tasks if d[B][t] is not None and d[A][t] is not None]
        pos = sum(x > 0 for x in v)
        neg = sum(x < 0 for x in v)
        print(f"  {B}-{A} {name}: n {len(v)} mean {mean(v):+.2f} median {median(v):+.1f} sd {sd(v):.2f} B later {pos} earlier {neg} same {len(v)-pos-neg}; sign p {sign_test_p(pos,neg):.3f} perm p {signflip_p(v,n=40000):.3f} (for understanding)")
    rows = sorted([(fp[B][t] - fp[A][t], short(t), fp[A][t], fp[B][t], fd_after_edit[A][t], fd_after_edit[B][t], first_edit(A, t), first_edit(B, t)) for t in tasks if fp[B][t] is not None and fp[A][t] is not None])
    print("   B-A first pass, task, fp A, fp B, deploy A, deploy B, edit A, edit B")
    for r in rows:
        print("    ", r)
result["fp"] = fp
result["fd_after_edit"] = fd_after_edit

print("\n== 5. Work per turn: statements, command size, tool output, reasoning, in turns up to first pass (sharpened), and calls")
for a in ARMS:
    rows = []
    for t in tasks:
        f = fp[a][t] or int(runs[(a, t)]["turns_T"])
        tr = [r for r in feat["runs"][a][t] if r["t"] <= f]
        rows.append({"turns": len(tr), "stmt": sum(r["n_stmt"] for r in tr), "cmd": sum(r["cmd_chars"] for r in tr), "out": sum(r["out_chars"] for r in tr), "reason": sum(r["reason_chars"] for r in tr), "calls": sum(turns[(a, t)][r["t"] - 1]["tool_calls"] for r in tr), "out_tok": sum(turns[(a, t)][r["t"] - 1]["output_tokens"] or 0 for r in tr), "reasoning_tok": sum(turns[(a, t)][r["t"] - 1]["reasoning_tokens"] or 0 for r in tr)})
    m = {k: mean([r[k] for r in rows]) for k in rows[0]}
    print(f"{a:6s} " + " ".join(f"{k} {v:9.1f}" for k, v in m.items()) + f"  per turn: stmt {m['stmt']/m['turns']:.2f}, cmd chars {m['cmd']/m['turns']:.0f}, tool out chars {m['out']/m['turns']:.0f}; non-reasoning output tokens {m['out_tok']-m['reasoning_tok']:.0f}")
    result[f"work_{a}"] = m
print(" paired")
for A, B in PAIRS:
    d = defaultdict(list)
    for t in tasks:
        for arm, sign in ((B, 1), (A, -1)):
            f = fp[arm][t] or int(runs[(arm, t)]["turns_T"])
            tr = [r for r in feat["runs"][arm][t] if r["t"] <= f]
            d["turns"].append(0)
    vals = {}
    for k in ("n_stmt", "cmd_chars", "out_chars", "reason_chars"):
        vs = []
        for t in tasks:
            fa = fp[A][t] or int(runs[(A, t)]["turns_T"])
            fb = fp[B][t] or int(runs[(B, t)]["turns_T"])
            vs.append(sum(r[k] for r in feat["runs"][B][t] if r["t"] <= fb) - sum(r[k] for r in feat["runs"][A][t] if r["t"] <= fa))
        vals[k] = mean(vs)
    print(f"  {B}-{A}", {k: round(v, 1) for k, v in vals.items()})

print("\n== 6. Packing: share of turns 1..15 with an edit and a deploy in one turn; turns from a deploy to the first test after it")
for a in ARMS:
    pk = []
    pk2 = []
    for t in tasks:
        tr = [r for r in feat["runs"][a][t] if r["t"] <= 15]
        tt = turns[(a, t)][:15]
        pk.append(mean([1 if (x["k_edit"] and y["restart"]) else 0 for x, y in zip(tt, tr)]))
        pk2.append(mean([1 if (x["k_test"] and y["restart"]) else 0 for x, y in zip(tt, tr)]))
    print(f"  {a:6s} edit+deploy in a turn {mean(pk):.3f}; deploy+test in a turn {mean(pk2):.3f}")

write_json("s5_deploy_gate.json", result)
