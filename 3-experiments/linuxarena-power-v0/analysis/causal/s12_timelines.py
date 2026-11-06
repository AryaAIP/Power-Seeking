"""Per-task timelines up to the first pass; the call axis read with deploys; test cases lost after passing; blank-spec hunting.

Timeline letters for a turn, kinds joined: R read only, E edit, B build (rebuild or go build), D deploy (restart), T own test, P privileged,
digit = calls in the turn when more than one, * = first pass (sharpened reading; exact on every-turn runs is close, see s11).
"""
import re

from common import *
from s4_parse_transcripts_lib import parse_transcript

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


def tl(a, t, upto):
    out = []
    f = fp[a][t]
    for r, x in zip(turns[(a, t)], feat["runs"][a][t]):
        if r["turn"] > upto:
            break
        s = ""
        if r["k_edit"]:
            s += "E"
        if x["rebuild"] or x["gobuild"]:
            s += "B"
        if x["restart"]:
            s += "D"
        if r["k_test"]:
            s += "T"
        if r["k_privileged"]:
            s += "P"
        if not s:
            s = "R"
        if r["tool_calls"] and r["tool_calls"] > 1:
            s += str(int(r["tool_calls"]))
        if f == r["turn"]:
            s += "*"
        out.append(s)
    return " ".join(out)


print("== Timelines up to max(first pass)+1, largest B lag first")
for A, B in PAIRS:
    print(f"--- {B}-{A}")
    order = sorted(tasks, key=lambda t: -((fp[B][t] or 0) - (fp[A][t] or 0)))
    for t in order:
        up = max(fp[A][t] or 0, fp[B][t] or 0) + 1
        print(f"{short(t):22s} {A}: {tl(A,t,up)}")
        print(f"{'':22s} {B}: {tl(B,t,up)}")

print("\n== Calls before the first edit, and privileged turns before first pass, for the 10 tasks where B lags most")
for A, B in PAIRS:
    order = sorted(tasks, key=lambda t: -((fp[B][t] or 0) - (fp[A][t] or 0)))[:10]
    rows = []
    for t in order:
        ea = runs[(A, t)]["first_edit_turn"] or 0
        eb = runs[(B, t)]["first_edit_turn"] or 0
        ca = sum(r["tool_calls"] for r in turns[(A, t)] if r["turn"] < ea)
        cb = sum(r["tool_calls"] for r in turns[(B, t)] if r["turn"] < eb)
        pb = sum(r["k_privileged"] for r in turns[(B, t)] if r["turn"] <= (fp[B][t] or 0))
        pa = sum(r["k_privileged"] for r in turns[(A, t)] if r["turn"] <= (fp[A][t] or 0))
        rows.append((short(t), fp[A][t], fp[B][t], ea, eb, ca, cb, pa, pb))
    print(f"--- {B}-{A}: task, fp A, fp B, edit A, edit B, calls before edit A, B, priv up to fp A, B")
    for r in rows:
        print("  ", r)
    print(f"   means: fp {mean([r[1] for r in rows]):.1f} {mean([r[2] for r in rows]):.1f}; edit {mean([r[3] for r in rows]):.1f} {mean([r[4] for r in rows]):.1f}; calls before edit {mean([r[5] for r in rows]):.1f} {mean([r[6] for r in rows]):.1f}; priv {mean([r[7] for r in rows]):.2f} {mean([r[8] for r in rows]):.2f}")
    result[f"top10_{B}-{A}"] = rows


# ---- the call axis using the sharpened curve (a change at the last restart in its interval), so no staleness from 5-turn points
def sharp_changes(a, t):
    pts = grid_points(tc, curves, a, t)
    rs = [r["t"] for r in feat["runs"][a][t] if r["restart"] or r["otherstart"]]
    ch = [(0, pts[0]["share"])]
    prev = pts[0]
    for p in pts[1:]:
        if abs(p["share"] - prev["share"]) > 1e-9:
            ins = [r for r in rs if prev["H"] < r <= p["H"]]
            ch.append((ins[-1] if ins else p["H"], p["share"]))
        prev = p
    return ch


def kmap(a, t):
    c = {0: 0}
    for r in turns[(a, t)]:
        c[int(r["turn"])] = r["cum_tool_calls_no_submit"]
    return c


def curve_on(a, t, axis="k", nmax=80):
    ch = sharp_changes(a, t)
    km = kmap(a, t)
    if axis == "k":
        ch = [(km.get(h, max(km.values())), v) for h, v in ch]
    out = []
    v = ch[0][1]
    j = 0
    for x in range(0, nmax + 1):
        while j + 1 < len(ch) and ch[j + 1][0] <= x:
            j += 1
            v = ch[j][1]
        out.append(v)
    return out


print("\n== Sharpened reading on both axes: B minus A at x, and steps inside 1..W")
axis_tab = {}
for A, B in PAIRS:
    for ax in ("H", "k"):
        cA = {t: curve_on(A, t, "k" if ax == "k" else "H") for t in tasks}
        cB = {t: curve_on(B, t, "k" if ax == "k" else "H") for t in tasks}
        d = lambda x: mean([cB[t][x] - cA[t][x] for t in tasks])
        row = {x: d(x) for x in (5, 8, 10, 12, 15, 18, 20, 25, 30)}
        for W in (10, 20, 30, 40):
            per = [sum(cB[t][x] - cA[t][x] for x in range(1, W + 1)) for t in tasks]
            row[f"W{W}"] = mean(per)
            if W == 20:
                row["W20_sd"] = sd(per)
                row["W20_p"] = signflip_p(per, n=40000)
        axis_tab[f"{B}-{A}:{ax}"] = row
        print(f"  {B}-{A} on {ax}: " + " ".join(f"{x}: {row[x]:+.3f}" for x in (5, 8, 10, 12, 15, 18, 20, 25, 30)) + f"; steps 1..10 {row['W10']:+.2f}, 1..20 {row['W20']:+.2f} (sd {row['W20_sd']:.2f}, perm p {row['W20_p']:.3f}), 1..30 {row['W30']:+.2f}, 1..40 {row['W40']:+.2f}")
result["axis_tab"] = {k: {str(a): b for a, b in v.items()} for k, v in axis_tab.items()}

# A1 exact against B1 at multiples of 5: B1 has one call per turn so its turn points sit at those calls
print("\n== A1 read from every-turn rows on the call axis, B1 read at its 5-turn points (calls = turns), tasks where A1 has no gap")
sub = [t for t in tasks if runs[("A1", t)]["max_gap_between_points"] == 1]
print("  n tasks", len(sub))


def exact_k(a, t, k):
    km = kmap(a, t)
    v = 0
    for p in all_points(tc, a, t):
        if km.get(min(p["H"], max(km)), 0) <= k:
            v = p["share"]
    return v


for k in (5, 10, 15, 20):
    a1 = mean([exact_k("A1", t, k) for t in sub])
    b1 = mean([exact_k("B1", t, k) for t in sub])
    h_a = mean([curw["per_task"]["A1"][t][k] for t in sub])
    h_b = mean([cur["per_task"]["B1"][t][k] for t in sub])
    print(f"  x={k}: on calls A1 {a1:.3f} B1 {b1:.3f} d {b1-a1:+.3f}; on turns A1 {h_a:.3f} B1 {h_b:.3f} d {h_b-h_a:+.3f}")
result["a1_exact_subset_n"] = len(sub)

# ---- test cases lost after passing
print("\n== Test cases that passed and do not pass at the end: which, when, and whether the turns in between hold a privileged DB action")
lost_tab = {}
for a in ARMS:
    total_w = 0
    steps = 0
    for t in tasks:
        units = tc_units(tc, curves, a, t)
        lost = []
        for nm, w, s in units:
            fpass = first_pass(s)
            if fpass is not None and s[-1][1] == 0:
                last_pass = max(h for h, b in s if b)
                next_fail = min(h for h, b in s if not b and h > last_pass)
                lost.append((nm, last_pass, next_fail, w))
                total_w += w / 27
                steps += w * (80 - next_fail + 1) / 27
        if lost:
            lp = min(x[1] for x in lost)
            nf = max(x[2] for x in lost)
            priv = [int(r["turn"]) for r in turns[(a, t)] if lp < r["turn"] <= nf and r["k_privileged"]]
            print(f"  {a:6s} {short(t):22s} lost {len(lost)} between H={lp} and H={nf}; privileged turns in that interval {priv}; {[x[0][:22] for x in lost][:5]}")
    print(f"  {a:6s} total weight {total_w:.4f}; steps these would have added had they stayed {steps:+.2f}")
    lost_tab[a] = {"weight": total_w, "steps": steps}
result["lost"] = lost_tab

# ---- blank spec hunting
print("\n== Solver reasoning that says the task text has blanks, by arm: runs mentioning it in turns 1-10, and turns that search for it")
BL = re.compile(r"(task|spec|description|prompt|text)[^.\n]{0,50}(omit|truncat|blank|missing|cut off|formatting|not shown|stripp)|(omit|truncat|blank|stripp)[^.\n]{0,40}(task|spec|description|prompt|example|json|code block|endpoint)", re.I)
for a in ARMS:
    n = 0
    turnsm = []
    perrun = {}
    for t in tasks:
        steps = parse_transcript(EXP / runs[(a, t)]["run_path"] / "transcript.md")
        c = 0
        for row in turns[(a, t)][:10]:
            fs = int(row["first_step"]) if row["first_step"] else None
            k = int(row["tool_calls"] or 0)
            tx = " ".join(steps[s]["reasoning"] for s in range(fs, fs + k) if s in steps) if fs else ""
            if BL.search(tx):
                c += 1
        if c:
            n += 1
        turnsm.append(c)
    print(f"  {a:6s} runs mentioning {n}; turns mentioning, mean per run {mean(turnsm):.2f}")

# ---- first-pass cross pair correlation
x = [fp["B1"][t] - fp["A1"][t] for t in tasks]
y = [fp["B2"][t] - fp["A2"][t] for t in tasks]
print("\n== Cross-pair: first-pass differences, Spearman", round(spearman(x, y), 2), "perm p", round(perm_corr_p(x, y, n=4000), 3), "sd", round(sd(x), 2), round(sd(y), 2))

write_json("s12.json", result)
