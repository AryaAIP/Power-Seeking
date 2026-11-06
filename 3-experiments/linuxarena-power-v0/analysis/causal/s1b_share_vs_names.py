"""Where does the count-based reference share differ from reading test-case names? Damage to free test cases shows here.

For each arm and task: steps (sum over H=1..80) from the reference share, and from the by-name bits. Prints differences
of 2 steps or more, and each scored point where the scorer's own passed count falls below the free count plus bits.
"""
from common import *

runs = load_runs()
tc = load_tc()
curves = load_curves()
cur = curves["no_rollback_rows"]["turns"]
tasks = sorted(tc)

print("arm, task, steps by reference, steps by names, difference, scoring")
for a in ARMS:
    tot = 0
    for t in tasks:
        ref = sum(cur["per_task"][a][t][1:81])
        names = sum(w * steps_counted(s) for _, w, s in tc_units(tc, curves, a, t))
        tot += ref - names
        if abs(ref - names) >= 1.0:
            print(f"{a:6s} {short(t):24s} ref {ref:6.1f} names {names:6.1f} diff {ref-names:+6.1f}  {tc[t]['scoring'][:12]} free {tc[t].get('free_count_in_power_horizons')}")
    print(f"{a}: total difference in steps per test case {tot/27:+.2f}")

print("\nPoints in pair arms where passed count minus free differs from by-name passes (grid points only)")
for a in ["A1", "B1", "A2", "B2", "before"]:
    for t in tasks:
        fr = tc[t].get("free_count_in_power_horizons")
        if fr is None:
            continue
        for p in grid_points(tc, curves, a, t):
            sp = p.get("scorer_passed")
            n = p.get("n_passing")
            if sp is None or n is None:
                continue
            if sp - fr != n:
                print(f"  {a:6s} {short(t):24s} H={p['H']:3d} src {p['source'][:8]:8s} scorer {sp}/{p.get('scorer_total')} free {fr} names {n}/{len(tc[t].get('counted') or [])} share {p['share']:.3f} by_name {p.get('share_by_name')} stop {p.get('stop')}")
