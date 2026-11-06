"""Is the sign change on the tool-call axis real?

Readings of a run's share at k calls:
- last: the last scored point at or below k (the curves.json axis);
- linear: straight line in k between the two scored points around k;
- next: the first scored point at or above k.
Then the same on tasks with every-turn rows in both arms, where the point placement is not an issue.
Also the output-token axis, and how the mean per-run k at H compares by arm.
"""
from common import *

runs = load_runs()
turns = load_turns()
tc = load_tc()
curves = load_curves()
tasks = sorted(tc)
KS = (5, 10, 15, 20, 25, 30)
result = {}


def k_at_turn(rows, H):
    """Non-submit calls in the first H turns; the run's total after its end."""
    c = 0
    for r in rows:
        if r["turn"] <= H:
            c = r["cum_tool_calls_no_submit"]
    return c


def run_points(arm, task, every=False):
    pts = all_points(tc, arm, task) if every else grid_points(tc, curves, arm, task)
    rows = turns[(arm, task)]
    out = []
    for p in pts:
        out.append((p["H"], k_at_turn(rows, p["H"]), p["share"]))
    return out


def read_x(points, x, how, xi=1):
    """points: (H, k, share), read at x on axis xi (0=H, 1=k). A point at the same x as a later one: keep the later."""
    pts = sorted(points, key=lambda p: (p[xi], p[0]))
    below = None
    above = None
    for p in pts:
        if p[xi] <= x:
            below = p
        if p[xi] >= x and above is None:
            above = p
    if below is None:
        below = pts[0]
    if above is None:
        above = pts[-1]
    # the value at the same x: the latest point with that x
    if how == "last":
        return below[2]
    if how == "next":
        return above[2]
    if how == "linear":
        if above[xi] == below[xi]:
            return below[2]
        return below[2] + (above[2] - below[2]) * (x - below[xi]) / (above[xi] - below[xi])


# --- A. mean k at H and the reference reproduction
print("== A. Where the 5-turn points sit on the call axis: mean non-submit calls at turn H (runs still going; end value after that)")
meanK = {}
for a in ARMS:
    row = {}
    for H in (1, 2, 3, 5, 10, 15, 20):
        row[H] = mean([k_at_turn(turns[(a, t)], H) for t in tasks if runs[(a, t)]["turns_T"] >= H])
    meanK[a] = row
    print(a, {k: round(v, 2) for k, v in row.items()})
result["mean_k_at_H"] = meanK

print("\n== A2. Share of each arm's runs whose k=10 reading comes from which turn H (5-turn points), and staleness in calls")
stale = {}
for a in ARMS:
    for K in (5, 10, 15):
        hs = defaultdict(int)
        st = []
        for t in tasks:
            pts = sorted(run_points(a, t), key=lambda p: (p[1], p[0]))
            b = None
            for p in pts:
                if p[1] <= K:
                    b = p
            hs[b[0]] += 1
            st.append(K - b[1] if K <= pts[-1][1] else 0)
        stale[f"{a}@{K}"] = {"H_read": dict(sorted(hs.items())), "mean_stale_calls": mean(st)}
        print(f"  {a:6s} k={K:2d}: reads H {dict(sorted(hs.items()))}; mean staleness {mean(st):.2f} calls")
result["stale"] = stale

# --- B. reading on the three rules, grid
print("\n== B. POWER and B-A on the call axis by reading rule, all 27 tasks, 5-turn points")
tab = {}
for how in ("last", "linear", "next"):
    pow_k = {a: {K: mean([read_x(run_points(a, t), K, how) for t in tasks]) for K in KS} for a in ARMS}
    tab[how] = pow_k
    print(f" rule {how}")
    for A, B in PAIRS:
        print(f"   {B}-{A} " + " ".join(f"k={K}: {pow_k[B][K]-pow_k[A][K]:+.3f}" for K in KS) + "   levels at k=10: " + f"{A} {pow_k[A][10]:.3f} {B} {pow_k[B][10]:.3f}")
result["k_axis_by_rule"] = {h: {a: {str(k): v for k, v in d.items()} for a, d in tab[h].items()} for h in tab}

print("\n== B2. The same on the turn axis, by rule (H multiples of 5 are scored points, so rules agree there except where points are missing)")
for how in ("last", "linear", "next"):
    pow_h = {a: {H: mean([read_x(run_points(a, t), H, how, xi=0) for t in tasks]) for H in KS} for a in ARMS}
    print(f" rule {how}")
    for A, B in PAIRS:
        print(f"   {B}-{A} " + " ".join(f"H={H}: {pow_h[B][H]-pow_h[A][H]:+.3f}" for H in KS))

# --- C. every-turn tasks
print("\n== C. Tasks with every-turn rows, no gap, in both arms of the pair")
ev = {}
for A, B in PAIRS:
    sub = [t for t in tasks if runs[(A, t)]["max_gap_between_points"] == 1 and runs[(B, t)]["max_gap_between_points"] == 1]
    print(f"{A}/{B}: {len(sub)} tasks: {[short(t) for t in sub]}")
    rows = {}
    for x in (5, 10, 15, 20):
        h_e = [read_x(run_points(B, t, True), x, "last", 0) - read_x(run_points(A, t, True), x, "last", 0) for t in sub]
        k_e = [read_x(run_points(B, t, True), x, "last", 1) - read_x(run_points(A, t, True), x, "last", 1) for t in sub]
        k_g = [read_x(run_points(B, t), x, "last", 1) - read_x(run_points(A, t), x, "last", 1) for t in sub]
        h_g = [read_x(run_points(B, t), x, "last", 0) - read_x(run_points(A, t), x, "last", 0) for t in sub]
        k_gl = [read_x(run_points(B, t), x, "linear", 1) - read_x(run_points(A, t), x, "linear", 1) for t in sub]
        rows[x] = {"H_every": mean(h_e), "k_every": mean(k_e), "H_grid": mean(h_g), "k_grid": mean(k_g), "k_grid_linear": mean(k_gl)}
        print(f"  x={x:2d}: on turns: every-turn {mean(h_e):+.3f}, 5-turn {mean(h_g):+.3f}; on calls: every-turn {mean(k_e):+.3f}, 5-turn last {mean(k_g):+.3f}, 5-turn linear {mean(k_gl):+.3f}")
    # mean over x=1..30
    for lab, xi in (("turns", 0), ("calls", 1)):
        e = mean([sum(read_x(run_points(B, t, True), x, "last", xi) - read_x(run_points(A, t, True), x, "last", xi) for x in range(1, 31)) for t in sub])
        print(f"  steps inside 1..30 on {lab}, every turn: {e:+.2f}")
    # paired first-pass exact in turns and calls
    fp = []
    for t in sub:
        def fpass(arm):
            pts = run_points(arm, t, True)
            for H, k, s in pts:
                if s > 0:
                    return H, k
            return None, None
        ha, ka = fpass(A)
        hb, kb = fpass(B)
        fp.append((short(t), ha, hb, ka, kb))
    d_h = [x[2] - x[1] for x in fp if x[1] is not None and x[2] is not None]
    d_k = [x[4] - x[3] for x in fp if x[3] is not None and x[4] is not None]
    print(f"  exact first pass: B minus A in turns mean {mean(d_h):+.2f} median {median(d_h):+.1f}; in calls mean {mean(d_k):+.2f} median {median(d_k):+.1f}; n {len(d_h)}")
    for x in fp:
        print("    ", x)
    ev[f"{B}-{A}"] = {"tasks": [short(t) for t in sub], "rows": rows, "fp_turns": mean(d_h), "fp_calls": mean(d_k), "fp_table": fp}
result["every_turn"] = ev

# --- D. all five arms' every-turn tasks
sub = [t for t in tasks if all(runs[(a, t)]["max_gap_between_points"] == 1 for a in ARMS)]
print("\n== D. every-turn in all five:", [short(t) for t in sub])

# --- E. first pass on calls, all tasks, as an interval from the 5-turn points
print("\n== E. Paired first pass on all 27 tasks (5-turn points), turns against calls, midpoint of the interval (previous point, first passing point]")
fpt = {}
for A, B in PAIRS:
    rows = []
    for t in tasks:
        def fi(arm):
            pts = run_points(arm, t)
            prev = pts[0]
            for p in pts:
                if p[2] > 0:
                    return ((prev[0] + p[0]) / 2 if p[0] > 0 else 0, (prev[1] + p[1]) / 2 if p[0] > 0 else 0, p[0], p[1])
                prev = p
            return None
        a, b = fi(A), fi(B)
        if a and b:
            rows.append((t, b[0] - a[0], b[1] - a[1], b[2] - a[2], b[3] - a[3], a[3] - a[2], b[3] - b[2]))
    dh = [r[1] for r in rows]
    dk = [r[2] for r in rows]
    print(f"{B}-{A}: n={len(rows)} turns mid {mean(dh):+.2f}, calls mid {mean(dk):+.2f}; first-passing point: turns {mean([r[3] for r in rows]):+.2f}, calls {mean([r[4] for r in rows]):+.2f}; extra calls over turns at first pass: {A} {mean([r[5] for r in rows]):.2f} {B} {mean([r[6] for r in rows]):.2f}; perm p on calls {signflip_p(dk):.3f}")
    fpt[f"{B}-{A}"] = {"turns_mid": mean(dh), "calls_mid": mean(dk), "extra_A": mean([r[5] for r in rows]), "extra_B": mean([r[6] for r in rows])}
result["first_pass_all"] = fpt

# --- F. equal-call shift: what the turn axis gap becomes if A's curve is moved right by its extra calls at each H
print("\n== F. The gap on calls estimated by moving each run onto its own k, then reading at a common k by straight lines, by k; the levels")
for A, B in PAIRS:
    print(f"{B}-{A}: " + " ".join(f"k={K}: A {tab['linear'][A][K]:.3f} B {tab['linear'][B][K]:.3f} d {tab['linear'][B][K]-tab['linear'][A][K]:+.3f};" for K in (5, 10, 15, 20)))

# --- G. the style inherited from the chat
print("\n== G. Calls per turn in the trajectory's own chat, against its solvers (from runs.csv) ")
for a in ("A1", "B1", "A2", "B2"):
    r = runs[(a, tasks[0])]
    tot_turns = r["traj_turns"]
    tot_calls = r["traj_tool_calls"]
    print(a, r["traj"], "traj turns", tot_turns, "calls", tot_calls, "calls/turn", round(tot_calls / tot_turns, 3), "solver runs with a multi-call turn", sum(1 for t in tasks if runs[(a, t)]["max_calls_per_turn"] > 1), "solver mean calls/turn", round(mean([runs[(a, t)]["mean_calls_per_turn"] for t in tasks]), 3), "turn 1 mean calls", round(mean([turns[(a, t)][0]["tool_calls"] for t in tasks]), 2))

# --- H. Output tokens axis
print("\n== H. Axis of cumulative output tokens: POWER at T thousand output tokens, last-scored and linear readings, and tokens at first pass")


def tok_points(arm, task):
    rows = turns[(arm, task)]
    cum = {}
    c = 0
    for r in rows:
        c += r["output_tokens"] or 0
        cum[r["turn"]] = c
    cum[0] = 0
    out = []
    for p in grid_points(tc, curves, arm, task):
        H = p["H"]
        H2 = min(H, rows[-1]["turn"])
        out.append((H, cum.get(H2, c), p["share"]))
    return out


toks = (1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000)
pow_t = {h: {a: {x: mean([read_x(tok_points(a, t), x, h) for t in tasks]) for x in toks} for a in ARMS} for h in ("last", "linear")}
for how in ("last", "linear"):
    print(" rule", how)
    for a in ARMS:
        print(f"   {a:6s}", " ".join(f"{x//1000 if x>=1000 else x}k:{pow_t[how][a][x]:.3f}" for x in toks))
    for A, B in PAIRS:
        print(f"   {B}-{A}", " ".join(f"{x/1000:.1f}k:{pow_t[how][B][x]-pow_t[how][A][x]:+.3f}" for x in toks))
print(" mean output tokens per turn before first passing point (5-turn), and cumulative at first pass")
for a in ARMS:
    per = []
    cu = []
    for t in tasks:
        pts = tok_points(a, t)
        for H, x, s in pts:
            if s > 0 and H > 0:
                cu.append(x)
                per.append(x / H)
                break
    print(f"   {a:6s} cum output at first passing point: median {median(cu):.0f} mean {mean(cu):.0f}; per turn mean {mean(per):.0f}")
result["tokens_axis"] = {h: {a: {str(x): v for x, v in d.items()} for a, d in pow_t[h].items()} for h in pow_t}

write_json("s2_toolcalls.json", result)
