"""Step 1 of nov5-causal-factors: the gap in steps, later versus never, time-to-pass, slope, and tasks.

Writes out/s1.json and prints the tables. Numbers on the 5-turn grid (the reference), by test case.
"""
from common import *

runs = load_runs()
tc = load_tc()
curves = load_curves()
cur = curves["no_rollback_rows"]["turns"]
tasks = sorted(tc)
result = {}

# ---- check: test-case bits reproduce the reference mean, and how far
print("== check: by-test-case steps against the reference mean over H=1..80")
units = {a: {t: tc_units(tc, curves, a, t) for t in tasks} for a in ARMS}
area = {}
for a in ARMS:
    per_task = {}
    for t in tasks:
        per_task[t] = sum(w * steps_counted(s) for _, w, s in units[a][t])
    area[a] = per_task
    print(a, "reference", round(cur["mean_1_80"][a], 4), "from bits", round(mean(per_task.values()) / 80, 4))
result["reference_mean"] = {a: cur["mean_1_80"][a] for a in ARMS}
result["bits_mean"] = {a: mean(area[a].values()) / 80 for a in ARMS}
# the reference-weighted steps by task from share curves
share_area = {a: {t: sum(cur["per_task"][a][t][1:81]) for t in tasks} for a in ARMS}

# ---- later vs never, by test case
print("\n== B minus A in steps per test case (task-equal weights): later versus never")
print("classes: both pass at end; only A at end; only B at end; neither at end")
dec = {}
for A, B in PAIRS + [("before", "A1"), ("before", "B1"), ("before", "A2"), ("before", "B2")]:
    c = defaultdict(float)
    n = defaultdict(float)
    nraw = defaultdict(int)
    pertask = defaultdict(lambda: defaultdict(float))
    for t in tasks:
        ua, ub = units[A][t], units[B][t]
        if [u[0] for u in ua] != [u[0] for u in ub]:
            # refactor pseudo-units could differ in n; align on the smaller
            pass
        for (name, w, sa), (_, wb, sb) in zip(ua, ub):
            ea, eb = sa[-1][1], sb[-1][1]
            d = steps_counted(sb) - steps_counted(sa)
            cls = "both" if ea and eb else "only_A" if ea else "only_B" if eb else "neither"
            c[cls] += w * d / 27
            n[cls] += w / 27
            nraw[cls] += 1
            pertask[t][cls] += w * d
    total = sum(c.values())
    # the reference difference in steps
    ref = (cur["mean_1_80"][B] - cur["mean_1_80"][A]) * 80
    dec[f"{B}-{A}"] = {"steps_total_bits": total, "steps_reference": ref, "by_class": dict(c), "weight": dict(n), "n_raw": dict(nraw),
                       "per_task": {t: dict(v) for t, v in pertask.items()}}
    print(f"{B}-{A}: reference {ref:+.2f} steps; bits {total:+.2f}; both(later) {c['both']:+.2f}; only_A(never in B) {c['only_A']:+.2f}; only_B(never in A) {c['only_B']:+.2f}; neither {c['neither']:+.2f}; "
          f"share of tc: both {n['both']:.3f} only_A {n['only_A']:.3f} only_B {n['only_B']:.3f} neither {n['neither']:.3f}; raw {dict(nraw)}")
result["decomposition"] = dec

# which test cases/tasks carry the never part
print("\n== never part by task (steps per test case over all 27 tasks = value/27)")
for A, B in PAIRS:
    k = f"{B}-{A}"
    rows = []
    for t in tasks:
        v = dec[k]["per_task"][t]
        rows.append((t, v.get("only_A", 0), v.get("only_B", 0), v.get("both", 0)))
    rows.sort(key=lambda r: r[1] + r[2])
    for t, oa, ob, b in rows:
        if abs(oa) + abs(ob) > 0:
            print(f"  {k} {short(t):24s} only_A {oa:+7.1f} only_B {ob:+7.1f} later {b:+7.1f}  end A {runs[(A,t)]['end_share']:.2f} B {runs[(B,t)]['end_share']:.2f}")

# ---- broke-after-pass
print("\n== test cases that passed and later stopped (by end of run), weight by task")
for a in ARMS:
    broke = fixedagain = 0
    wbroke = 0
    for t in tasks:
        for name, w, s in units[a][t]:
            fp = first_pass(s)
            if fp is not None:
                if s[-1][1] == 0:
                    broke += 1
                    wbroke += w / 27
                seq = [b for _, b in s]
                first = seq.index(1)
                if 0 in seq[first:] and s[-1][1] == 1:
                    fixedagain += 1
    print(a, "passed then not at end", broke, f"(weight {wbroke:.4f})", "dipped and came back", fixedagain)

# ---- time to pass
print("\n== time to pass per test case, 5-turn grid: quantiles among test cases passing at any scored point")
ttp = {}
for a in ARMS:
    vals, weights = [], []
    nev = 0
    wnev = 0
    wall = 0
    all_tc = 0
    for t in tasks:
        for name, w, s in units[a][t]:
            all_tc += 1
            wall += w
            fp = first_pass(s)
            if fp is None:
                nev += 1
                wnev += w
            else:
                vals.append(fp)
                weights.append(w)
    # weighted quantiles
    pairs = sorted(zip(vals, weights))
    tot = sum(weights)

    def wq(q):
        acc = 0
        for v, w in pairs:
            acc += w
            if acc >= q * tot:
                return v
        return pairs[-1][0]
    wm = sum(v * w for v, w in pairs) / tot
    ttp[a] = {"n_tc": all_tc, "never_raw": nev, "never_task_weight": wnev / wall, "q10": wq(.1), "q25": wq(.25), "q50": wq(.5), "q75": wq(.75), "q90": wq(.9), "mean_given_pass": wm,
              "le5": sum(w for v, w in pairs if v <= 5) / 27, "le10": sum(w for v, w in pairs if v <= 10) / 27, "le15": sum(w for v, w in pairs if v <= 15) / 27, "le20": sum(w for v, w in pairs if v <= 20) / 27, "le30": sum(w for v, w in pairs if v <= 30) / 27}
    print(a, {k: round(v, 3) if isinstance(v, float) else v for k, v in ttp[a].items()})
result["time_to_pass"] = ttp

# ---- pass in some arms only
print("\n== test cases by which arms pass them at the end (task-equal weight)")
pat = defaultdict(float)
patraw = defaultdict(int)
per_tc = {}
ever = defaultdict(float)
for t in tasks:
    uu = {a: units[a][t] for a in ARMS}
    n = len(uu["before"])
    if not all(len(uu[a]) == n for a in ARMS):
        print("  unit length differs", t, {a: len(uu[a]) for a in ARMS})
    for i in range(n):
        key = "".join("1" if uu[a][i][2][-1][1] else "0" for a in ARMS)
        w = uu["before"][i][1] / 27
        pat[key] += w
        patraw[key] += 1
        everkey = "".join("1" if first_pass(uu[a][i][2]) is not None else "0" for a in ARMS)
        ever[everkey] += w
tot = sum(pat.values())
print("  pass at end in all five:", round(pat["11111"], 4), "raw", patraw["11111"])
print("  in none:", round(pat["00000"], 4), "raw", patraw["00000"])
print("  in some only:", round(tot - pat["11111"] - pat["00000"], 4), "raw", sum(v for k, v in patraw.items() if k not in ("11111", "00000")))
print("  ever-pass: all five", round(ever["11111"], 4), "none", round(ever["00000"], 4), "some", round(tot - ever["11111"] - ever["00000"], 4))
for k, v in sorted(pat.items(), key=lambda kv: -kv[1])[:12]:
    print("   pattern before,A1,B1,A2,B2", k, round(v, 4), patraw[k])
result["end_patterns"] = {k: {"weight": pat[k], "raw": patraw[k]} for k in pat}
result["ever_patterns"] = dict(ever)

# ---- slope and lag
print("\n== gap against slope at the curve: uses grid values at H multiples of 5")
P = cur["power"]
lag_rows = {}
for A, B in PAIRS:
    print(f"pair {A}/{B}")
    rows = []
    for H in (5, 10, 15, 20, 25, 30):
        gap = P[B][H] - P[A][H]
        slope_a = (P[A][H + 5] - P[A][H - 5]) / 10
        slope_b = (P[B][H + 5] - P[B][H - 5]) / 10
        sl = (slope_a + slope_b) / 2
        # horizontal: at the level B has at H, when does A reach it? and vice versa (linear between multiples of 5)

        def inv(curve, y):
            pts = [(h, curve[h]) for h in range(0, 81, 5)]
            for (h0, v0), (h1, v1) in zip(pts, pts[1:]):
                if v0 <= y <= v1 and v1 > v0:
                    return h0 + (y - v0) / (v1 - v0) * (h1 - h0)
            return None
        ha = inv(P[A], P[B][H])
        hb = inv(P[B], P[A][H])
        lag1 = H - ha if ha is not None else None
        lag2 = hb - H if hb is not None else None
        rows.append({"H": H, "gap": gap, "slope_A": slope_a, "slope_B": slope_b, "gap_over_slope": (gap / sl if sl else None), "lag_read_on_A": lag1, "lag_read_on_B": lag2})
        print(f"  H={H:2d} gap {gap:+.3f} slope A {slope_a:.3f} B {slope_b:.3f} gap/slope {gap/sl if sl else float('nan'):+.2f} steps; lag via A curve {fmt(lag1,2)} via B curve {fmt(lag2,2)}")
    lag_rows[f"{B}-{A}"] = rows

    # best constant shift on H=1..30 (linear interpolation in the raw per-H curve)
    def at(curve, x):
        if x <= 0:
            return curve[0]
        lo = int(x)
        hi = min(lo + 1, 80)
        return curve[lo] + (curve[hi] - curve[lo]) * (x - lo)
    best = None
    for k10 in range(-100, 101):
        k = k10 / 10
        e = sum((P[B][H] - at(P[A], H - k)) ** 2 for H in range(1, 31))
        if best is None or e < best[1]:
            best = (k, e)
    e0 = sum((P[B][H] - P[A][H]) ** 2 for H in range(1, 31))
    # shift + level
    best2 = None
    for k10 in range(-100, 101):
        k = k10 / 10
        d = [P[B][H] - at(P[A], H - k) for H in range(1, 31)]
        c = sum(d) / len(d)
        e = sum((x - c) ** 2 for x in d)
        if best2 is None or e < best2[2]:
            best2 = (k, c, e)
    print(f"  best constant shift on H=1..30: B(H)=A(H-k), k={best[0]:+.1f}, rmse {math.sqrt(best[1]/30):.4f} (no shift {math.sqrt(e0/30):.4f}); with a level too: k={best2[0]:+.1f}, level {best2[1]:+.4f}, rmse {math.sqrt(best2[2]/30):.4f}")
    lag_rows[f"{B}-{A}_shift"] = {"k": best[0], "rmse": math.sqrt(best[1] / 30), "rmse_no_shift": math.sqrt(e0 / 30), "k_with_level": best2[0], "level": best2[1], "rmse_with_level": math.sqrt(best2[2] / 30)}
result["lag"] = lag_rows

# area in the low-H window, in steps
print("\n== steps lost per test case inside the window H=1..W (mean over 1..W of B-A, times W)")
win = {}
for A, B in PAIRS + [("before", "A1"), ("before", "B1"), ("before", "A2"), ("before", "B2")]:
    row = {}
    for W in (10, 15, 20, 30, 40, 80):
        row[W] = sum(P[B][H] - P[A][H] for H in range(1, W + 1))
    win[f"{B}-{A}"] = row
    print(f"  {B}-{A}", {k: round(v, 2) for k, v in row.items()})
result["window_steps"] = win

# ---- tasks
print("\n== by task at H=5,10,15,20 and steps inside H=1..20 (for understanding, not the headline)")
tab = {}
for A, B in PAIRS:
    for H in (5, 10, 15, 20, "w20"):
        diffs = {}
        for t in tasks:
            if H == "w20":
                diffs[t] = sum(cur["per_task"][B][t][h] - cur["per_task"][A][t][h] for h in range(1, 21))
            else:
                diffs[t] = cur["per_task"][B][t][H] - cur["per_task"][A][t][H]
        vals = list(diffs.values())
        pos = sum(1 for v in vals if v > 1e-9)
        neg = sum(1 for v in vals if v < -1e-9)
        tie = 27 - pos - neg
        m = mean(vals)
        s = sd(vals)
        # removal of the top tasks in the direction of the mean's sign, and the reverse
        order = sorted(diffs.items(), key=lambda kv: kv[1])
        rem_neg = {}
        rem_pos = {}
        for k in (1, 3, 5):
            rest = [v for _, v in order[k:]]
            rem_neg[k] = sum(rest) / 27  # keep the /27 scale: their contribution set to zero
            rest2 = [v for _, v in order[:-k]]
            rem_pos[k] = sum(rest2) / 27
        p_sign = sign_test_p(pos, neg)
        p_perm = signflip_p(vals)
        tab[f"{B}-{A}@{H}"] = {"mean": m, "sd": s, "se": s / math.sqrt(27), "favour_B": pos, "favour_A": neg, "tie": tie, "drop_top_A_favouring": rem_neg, "drop_top_B_favouring": rem_pos, "p_sign": p_sign, "p_perm": p_perm,
                               "order": [(short(t), round(v, 3)) for t, v in order if abs(v) > 1e-9]}
        print(f"{B}-{A} @{H}: mean {m:+.3f} sd {s:.3f} se {s/math.sqrt(27):.3f}; favour B {pos} A {neg} tie {tie}; drop A-top1,3,5 -> {rem_neg[1]:+.3f} {rem_neg[3]:+.3f} {rem_neg[5]:+.3f}; drop B-top1,3,5 -> {rem_pos[1]:+.3f} {rem_pos[3]:+.3f} {rem_pos[5]:+.3f}; sign p {p_sign:.3f}; perm p {p_perm:.3f}")
result["tasks"] = tab

# correlation of the two pairs' B-A across tasks, as a consistency check
print("\n== correlation across tasks of (B1-A1) and (B2-A2)")
for H in (5, 10, 15, 20, "w20", "all"):
    x, y = [], []
    for t in tasks:
        if H == "w20":
            x.append(sum(cur["per_task"]["B1"][t][h] - cur["per_task"]["A1"][t][h] for h in range(1, 21)))
            y.append(sum(cur["per_task"]["B2"][t][h] - cur["per_task"]["A2"][t][h] for h in range(1, 21)))
        elif H == "all":
            x.append(sum(cur["per_task"]["B1"][t][h] - cur["per_task"]["A1"][t][h] for h in range(1, 81)))
            y.append(sum(cur["per_task"]["B2"][t][h] - cur["per_task"]["A2"][t][h] for h in range(1, 81)))
        else:
            x.append(cur["per_task"]["B1"][t][H] - cur["per_task"]["A1"][t][H])
            y.append(cur["per_task"]["B2"][t][H] - cur["per_task"]["A2"][t][H])
    print(f"  H={H}: pearson {pearson(x,y):+.3f} spearman {spearman(x,y):+.3f}  sd(B1-A1) {sd(x):.3f} sd(B2-A2) {sd(y):.3f}; implied per-run sd if all noise {sd(x)/math.sqrt(2):.3f}, {sd(y)/math.sqrt(2):.3f}")
result["cross_pair_corr"] = None

# first pass paired
print("\n== paired first-pass turn on the grid; negative = B earlier")
for A, B in PAIRS:
    d = []
    for t in tasks:
        fa, fb = runs[(A, t)]["first_pass_H_grid"], runs[(B, t)]["first_pass_H_grid"]
        d.append((short(t), fa, fb, None if fa is None or fb is None else fb - fa))
    vals = [x[3] for x in d if x[3] is not None]
    pos = sum(v > 0 for v in vals)
    neg = sum(v < 0 for v in vals)
    print(f"{B}-{A}: n {len(vals)} mean {mean(vals):+.2f} median {median(vals):+.1f} B later {pos} B earlier {neg} same {len(vals)-pos-neg} sign p {sign_test_p(pos,neg):.3f} perm p {signflip_p(vals):.3f}; missing {[x for x in d if x[3] is None]}")
    for r in sorted(d, key=lambda x: (x[3] is None, x[3] if x[3] is not None else 0)):
        print("   ", r)

write_json("s1.json", result)
