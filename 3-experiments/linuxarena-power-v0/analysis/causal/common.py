"""Shared loading for analysis/causal/. Stdlib only. Run in WSL with python3 -I, from any folder.

Reads analysis/data/ only (runs.csv, turns.csv, testcases.json, curves.json). Never touches runs/, harness/ or logs/.
Grid = the 5-turn per-step points plus H = 0 and the run's end: curves.json's no_rollback_rows.scored_points_H, which
reproduces the reference numbers. Every-turn rows are used only where a script says so.
"""
import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
DATA = EXP / "analysis" / "data"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
ARMS = ["before", "A1", "B1", "A2", "B2"]
PAIRS = [("A1", "B1"), ("A2", "B2")]
TRAJ = {"A1": "traj4-sharing-none", "B1": "traj4-sharing-side", "A2": "traj4-minio-none", "B2": "traj4-minio-keep"}
TMAX = 80


def num(x):
    if x in ("", None):
        return None
    try:
        return float(x)
    except ValueError:
        return x


def load_runs():
    rows = {}
    with open(DATA / "runs.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows[(r["arm"], r["task"])] = {k: (num(v) if k not in ("arm", "pair", "task", "label", "run_path", "traj", "handover_note", "ended", "first_call_utc", "last_call_utc") else v) for k, v in r.items()}
    return rows


def load_turns():
    rows = defaultdict(list)
    with open(DATA / "turns.csv", newline="") as f:
        for r in csv.DictReader(f):
            d = dict(r)
            for k in ("turn", "tool_calls", "cum_tool_calls_no_submit", "k_read", "k_edit", "k_build", "k_test", "k_db", "k_privileged", "k_submit", "k_other", "failed", "n_failed", "denied", "timeout", "killed_by_restart", "build_ok", "tool_seconds", "model_seconds", "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "first_step", "scored_here", "share_last_scored"):
                d[k] = num(d.get(k))
            rows[(r["arm"], r["task"])].append(d)
    for v in rows.values():
        v.sort(key=lambda d: d["turn"])
    return rows


def load_tc():
    return json.load(open(DATA / "testcases.json"))["tasks"]


def load_curves():
    return json.load(open(DATA / "curves.json"))


def short(task):
    m = {
        "mtg_model_registry_pollute_training_01_constitution_versioning_system": "constitution_versioning",
        "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern": "db_layer_refactor",
        "migrate_from_gorilla_mux_to_chi_router": "chi_router",
        "untracked_s3_objects_total_bytes": "storage_question",
        "filebased_configuration_hotreload": "config_hot_reload",
        "migrate_backup_records_to_sqlite": "backup_to_sqlite",
        "model_registry_health_dashboard_data": "health_dashboard",
        "model_artifact_quarantine_system": "artifact_quarantine",
        "model_version_compatibility_matrix": "compat_matrix",
        "model_search_with_fulltext_index": "fulltext_search",
        "custom_validation_rules_engine": "validation_rules",
        "webhook_notification_system": "webhooks",
        "model_registry_sse_event_stream": "sse_stream",
        "model_registry_rbac_matrix": "rbac_matrix",
        "model_registry_data_export": "data_export",
        "model_version_comment_thread": "version_comments",
        "audit_log_tamper_detection": "tamper_detection",
        "model_access_audit_trail": "access_audit",
        "abstract_middleware_chain": "middleware_chain",
        "admin_user_management": "admin_users",
        "postgresqlbacked_job_queue": "job_queue",
        "scheduled_model_expiration": "scheduled_expiry",
        "request_id_propagation": "request_ids",
        "sqlite_audit_log_archive": "sqlite_audit_archive",
        "model_favoriting_system": "favourites",
        "jwt_claims_wrong_field": "jwt_bug",
        "token_usage_analytics": "token_usage",
    }
    return m.get(task, task)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def spearman(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    return pearson(rank(list(xs)), rank(list(ys)))


def perm_corr_p(xs, ys, n=20000, seed=11):
    """Two-sided permutation p for the Spearman correlation, for understanding only."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 4:
        return None
    a, b = zip(*pairs)
    ra, rb = rank(list(a)), rank(list(b))
    obs = abs(pearson(ra, rb) or 0)
    rnd = random.Random(seed)
    c = 0
    rb = list(rb)
    for _ in range(n):
        rnd.shuffle(rb)
        if abs(pearson(ra, rb) or 0) >= obs - 1e-12:
            c += 1
    return (c + 1) / (n + 1)


def sign_test_p(n_pos, n_neg):
    """Exact two-sided sign test on the non-ties."""
    n = n_pos + n_neg
    if n == 0:
        return 1.0
    k = min(n_pos, n_neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def signflip_p(diffs, n=200000, seed=7):
    """Two-sided sign-flip permutation p of the mean, with ties kept. Exact if few non-zero values."""
    d = [x for x in diffs if abs(x) > 1e-12]
    if not d:
        return 1.0
    obs = abs(sum(d))
    if len(d) <= 16:
        c = 0
        for m in range(2 ** len(d)):
            s = sum(x if (m >> i) & 1 else -x for i, x in enumerate(d))
            if abs(s) >= obs - 1e-12:
                c += 1
        return c / 2 ** len(d)
    rnd = random.Random(seed)
    c = 0
    for _ in range(n):
        s = sum(x if rnd.random() < 0.5 else -x for x in d)
        if abs(s) >= obs - 1e-12:
            c += 1
    return (c + 1) / (n + 1)


def grid_points(tc, curves, arm, task):
    """The arm's points on the 5-turn grid, sorted by H."""
    keep = set(curves["no_rollback_rows"]["scored_points_H"][arm][task])
    return sorted([p for p in tc[task]["arms"][arm]["points"] if p["H"] in keep], key=lambda p: p["H"])


def all_points(tc, arm, task):
    return sorted(tc[task]["arms"][arm]["points"], key=lambda p: p["H"])


def read_last_scored(points, H, key="share"):
    v = points[0][key]
    for p in points:
        if p["H"] <= H:
            v = p[key]
        else:
            break
    return v


def pseudo_bits(point, n):
    """Refactor task: no names, so counts only. The first m of n pseudo test cases pass, where m = round(share*n)."""
    m = int(round(point["share"] * n))
    return "1" * m + "0" * (n - m)


def tc_units(tc, curves, arm, task, use_all=False):
    """Yields (id, weight within task, list of (H, bit)) per test case; for the refactor task, pseudo test cases."""
    pts = all_points(tc, arm, task) if use_all else grid_points(tc, curves, arm, task)
    t = tc[task]
    ids = t.get("counted") or []
    out = []
    if ids:
        n = len(ids)
        for i, name in enumerate(ids):
            series = []
            for p in pts:
                bits = p.get("passing_bits") or "0" * n
                series.append((p["H"], int(bits[i]) if i < len(bits) else 0))
            out.append((name, 1.0 / n, series))
    else:
        # how many counted? No total in this task's records: the smallest n that makes every share a whole count.
        shares = [p["share"] for p in tc[task]["arms"]["before"]["points"] + tc[task]["arms"]["A1"]["points"] + tc[task]["arms"]["B1"]["points"] + tc[task]["arms"]["A2"]["points"] + tc[task]["arms"]["B2"]["points"]]
        n = next(k for k in range(1, 60) if all(abs(x * k - round(x * k)) < 1e-3 for x in shares))
        for i in range(n):
            series = []
            for p in pts:
                bits = pseudo_bits(p, n)
                series.append((p["H"], int(bits[i])))
            out.append((f"pseudo{i}", 1.0 / n, series))
    return out


def steps_counted(series, tmax=TMAX):
    """H in 1..tmax at which the last scored point at or before H passes."""
    c = 0
    for H in range(1, tmax + 1):
        v = 0
        for h, b in series:
            if h <= H:
                v = b
            else:
                break
        c += v
    return c


def first_pass(series):
    for h, b in series:
        if b:
            return h
    return None


def fmt(x, nd=3, plus=False):
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    s = f"{x:+.{nd}f}" if plus else f"{x:.{nd}f}"
    return s


def write_json(name, obj):
    with open(OUT / name, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
