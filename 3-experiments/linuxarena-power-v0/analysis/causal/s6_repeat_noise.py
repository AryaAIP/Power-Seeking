"""The only true repeats in the records: the before arm was also run on 6 tasks on Nov 2 (v2-before), with per-step scoring.

Same model, same task, new chat, but a slightly different setup (hide_log and test_db came later, and the Nov 3 runs have the
service log hidden), so this is a rough size of run-to-run differences, for understanding only.
Compares v2-before with v4-before per task: turns, first pass, deploy turn, and steps inside H=1..20.
"""
import re

from common import *
from s4_parse_transcripts_lib import parse_transcript, RESTART

runs = load_runs()
tc = load_tc()
curves = load_curves()
cur = curves["no_rollback_rows"]["turns"]
tasks = sorted(tc)
SHORT = {"backup": "migrate_backup_records_to_sqlite", "jwt": "jwt_claims_wrong_field"}


def passed_counts(path):
    s = json.load(open(path / "scores.json"))
    expl = json.dumps(s.get("scorer", {}))
    m = re.search(r"Passed (\d+)/(\d+)", expl)
    if m:
        return int(m.group(1)), int(m.group(2))
    ch = s.get("checks") or []
    if ch:
        return sum(1 for c in ch if c.get("passed")), len(ch)
    return None, None


v2 = {}
for d in sorted((EXP / "runs" / "v2-before").iterdir()):
    if not d.is_dir():
        continue
    run = next(d.glob("e1-*"))
    meta = json.load(open(run / "meta.json"))
    v2[d.name] = {"T": None, "run": run, "tool_calls": meta.get("solver_tool_calls")}

labels = sorted(p.name for p in (EXP / "runs").iterdir() if p.name.startswith("hz-v2-before-"))
hz = defaultdict(dict)
for lb in labels:
    m = re.match(r"hz-v2-before-(\w+?)-H(\d+)(-r\d+)?$", lb)
    if not m:
        continue
    short_name, H = m.group(1), int(m.group(2))
    sub = [x for x in (EXP / "runs" / lb).iterdir() if x.is_dir()]
    if not sub:
        continue
    task = sub[0].name
    try:
        run = next(sub[0].glob("e1-*"))
        p, n = passed_counts(run)
    except (StopIteration, FileNotFoundError):
        continue
    if p is not None:
        hz[task][H] = (p, n)

print("Task, v2 T (usage rows), v4 T; first scored passing above no-work; per-step passes")
rows = []
for task, info in v2.items():
    usage = list(csv.DictReader(open(info["run"] / "usage.csv")))
    T2 = sum(1 for u in usage if int(u.get("output_tokens") or u.get("output") or 0) > 0)
    steps = parse_transcript(info["run"] / "transcript.md")
    # the first restart step (steps, roughly turns in this arm: reported as calls)
    first_restart_step = next((s for s in sorted(steps) if RESTART.search(steps[s]["cmd"])), None)
    v4 = runs[("before", task)]
    pts = hz.get(task, {})
    base = None
    p0 = tc[task]["arms"]["before"]["points"][0]
    base = p0.get("scorer_passed")
    fp2 = None
    if pts:
        lo = min(v[0] for v in pts.values())
        for H in sorted(pts):
            if pts[H][0] > lo:
                fp2 = H
                break
    fp4 = v4["first_pass_H_grid"]
    rows.append((short(task), T2, int(v4["turns_T"]), fp2, fp4, first_restart_step, info["tool_calls"], int(v4["tool_calls"]), {h: pts[h] for h in sorted(pts)}))
    print(rows[-1])

d_T = [r[1] - r[2] for r in rows]
d_fp = [r[3] - r[4] for r in rows if r[3] is not None and r[4] is not None]
print("\nv2 minus v4 turns:", d_T, "mean abs", round(mean([abs(x) for x in d_T]), 1), "sd", round(sd(d_T), 1))
print("v2 minus v4 first pass (5-turn resolution or coarser):", d_fp, "mean abs", round(mean([abs(x) for x in d_fp]), 1), "sd", round(sd(d_fp), 1), "implied per-run sd", round(sd(d_fp) / math.sqrt(2), 1))
write_json("s6_repeat_noise.json", {"rows": [list(r[:8]) for r in rows], "d_T": d_T, "d_fp": d_fp})
