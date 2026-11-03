#!/usr/bin/env bash
# Bring the Nov 3 (v4) results home and rebuild everything from them, in one command (plans/nov3-plan-to-6am.md).
# Runs in WSL as root; safe to rerun while scoring continues: each step goes on whatever the one before found.
#   finish_v4.sh [address] [key]      defaults: $VM_ADDR or 132.145.142.218, $VM_KEY or /root/.ssh/power2.pem
#   (a) copy.sh back from the Lambda machine (login $VM_USER, default ubuntu)
#   (b) rebuild runs/runs-registry.md from every summary.json (each copy back leaves only the machine's batches)
#   (c) power_horizons.py on the config's arms -> findings/power-horizons-v4.json, its printed table -> .txt
#   (d) the dashboard: viz/build_dashboard.py --config viz/run-v4.json
#   (e) the secret scan (secret_scan.py) of files under runs/ and findings/ changed since the last commit, plus (b)-(d)'s
#       outputs. Prints paths and kinds of match only, never a value
#   (f) a short summary
# For a test, set any of:
#   SKIP_COPY=1        leave out (a)
#   FINISH_CONFIG=f    a run config other than viz/run-v4.json (its arms feed (c) and (d))
#   FINISH_OUT=dir     write (b), (c) and (d)'s outputs into dir instead: nothing in the repository changes
#   SCAN_SINCE=epoch   scan files changed since this time (seconds) instead of since the last commit
#   COPY_TIMEOUT=secs  give up on (a) after this long (default: no limit)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
HARNESS=$(dirname "$HERE"); EXP=$(dirname "$HARNESS")
. "$HARNESS/paths.sh"
VM_ADDR=${1:-${VM_ADDR:-132.145.142.218}}
export VM_KEY=${2:-${VM_KEY:-/root/.ssh/power2.pem}} VM_USER=${VM_USER:-ubuntu}
CONFIG=${FINISH_CONFIG:-$EXP/viz/run-v4.json}
PY=$POWER_V0_CT/.venv/bin/python  # Control Tower's Python: export_run.py needs inspect_ai
if [ -n "${FINISH_OUT:-}" ]; then
  mkdir -p "$FINISH_OUT"; OUTD=$(cd "$FINISH_OUT" && pwd)
  REG_OUT=$OUTD/runs-registry.md; PH_JSON=$OUTD/power-horizons-v4.json; PH_TXT=$OUTD/power-horizons-v4.txt
  DASH_ARGS=(--out "$OUTD/power-dashboard-v4.html")
else
  exec 9>/tmp/finish_v4.lock; flock -n 9 || { echo "finish_v4.sh is already running"; exit 1; }
  REG_OUT=$EXP/runs/runs-registry.md; PH_JSON=$EXP/findings/power-horizons-v4.json; PH_TXT=$EXP/findings/power-horizons-v4.txt
  DASH_ARGS=()
fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
SUMMARY=()
say() { SUMMARY+=("$*"); }
step() { echo; echo "=== $(date '+%H:%M:%S') $*"; }

step "(a) copy back from $VM_USER@$VM_ADDR"
if [ "${SKIP_COPY:-0}" = 1 ]; then
  say "(a) copy back: skipped (SKIP_COPY=1)"
else
  cp -p "$EXP/runs/runs-registry.md" "$TMP/registry.local" 2>/dev/null
  if ${COPY_TIMEOUT:+timeout "$COPY_TIMEOUT"} bash "$HERE/copy.sh" back "$VM_ADDR"; then
    say "(a) copy back from $VM_ADDR: done"
  else
    say "(a) copy back from $VM_ADDR: FAILED (exit $?); the steps below use what's already here"
  fi
  # copy.sh back replaced the registry with the machine's copy: put this one back (keeps any local text outside the
  # table), and (b) rebuilds its table from every batch
  [ -f "$TMP/registry.local" ] && ! cmp -s "$TMP/registry.local" "$EXP/runs/runs-registry.md" &&
    cp "$TMP/registry.local" "$EXP/runs/runs-registry.md"
fi

step "(b) rebuild the run registry -> $REG_OUT"
( cd "$POWER_V0_CT" && PYTHONPATH="$HARNESS" "$PY" - "$EXP/runs" "$REG_OUT" ) > "$TMP/b.out" 2>&1 <<'PY'
import shutil, sys, tempfile
from pathlib import Path
import export_run
runs, dest = Path(sys.argv[1]), Path(sys.argv[2])
if dest.resolve() == (runs / "runs-registry.md").resolve():
    export_run.update_registry(runs)
else:  # a test: the same rebuild in a scratch folder, so runs/ is untouched
    td = Path(tempfile.mkdtemp())
    shutil.copy(runs / "runs-registry.md", td / "runs-registry.md")
    for s in runs.glob("*/summary.json"):
        (td / s.parent.name).mkdir()
        (td / s.parent.name / "summary.json").symlink_to(s)
    export_run.update_registry(td)
    shutil.copy(td / "runs-registry.md", dest)
    shutil.rmtree(td)
text = dest.read_text()
if export_run.REG_START not in text:
    sys.exit("the registry has no table markers: not rebuilt")
table = text[text.index(export_run.REG_START):text.index(export_run.REG_END)].splitlines()
rows = [ln for ln in table if ln.startswith("| ") and not ln.startswith(("| Label", "| ---"))]
v4 = [ln for ln in rows if ln.startswith(("| v4-", "| nowork-v4-", "| hz-v4-", "| traj4-"))]
print(f"{len(rows)} batches listed ({len(v4)} of tonight's: v4, nowork-v4, hz-v4, traj4)")
PY
rc=$?; tail -3 "$TMP/b.out"
[ $rc = 0 ] && say "(b) registry: $(tail -1 "$TMP/b.out")" || say "(b) registry: FAILED (exit $rc): $(tail -1 "$TMP/b.out")"

step "(c) power with horizons -> $PH_JSON"
ARMS=$(python3 -I - "$CONFIG" <<'PY' 2>&1
import json, sys
c = json.load(open(sys.argv[1]))
print(c["before"][0], c["before"][1], c["afters"]["A"][0], c["afters"]["A"][1], c["afters"]["B"][0], c["afters"]["B"][1])
PY
)
if read -r BEF NWB AA NWA AB NWBB <<<"$ARMS" && [ -n "$NWBB" ]; then
  have=(); missing=()  # which batches (one per machine part) have exported records yet
  for lab in $(echo "$BEF,$NWB,$AA,$NWA,$AB,$NWBB" | tr ',' ' '); do
    [ -f "$EXP/runs/$lab/summary.json" ] && have+=("$lab") || missing+=("$lab"); done
  echo "batches with records: ${#have[@]} of $(( ${#have[@]} + ${#missing[@]} ))${missing:+; not yet: ${missing[*]}}"
  say "(c) batches with records: ${#have[@]} of $(( ${#have[@]} + ${#missing[@]} ))${missing:+; not yet: ${missing[*]}}"
  PH_ARGS=(--before "$BEF" --nowork-before "$NWB" --after "A=$AA" --nowork-after "A=$NWA" --after "B=$AB" --nowork-after "B=$NWBB")
  python3 -I "$HARNESS/power_horizons.py" "${PH_ARGS[@]}" --json "$TMP/ph.json" > "$TMP/ph.out" 2> "$TMP/ph.err"
  rc=$?
  if [ $rc = 0 ] && [ -s "$TMP/ph.json" ]; then
    mv "$TMP/ph.json" "$PH_JSON"
    { echo "# $(date '+%Y-%m-%d %H:%M %Z'): python3 harness/power_horizons.py ${PH_ARGS[*]}"
      sed "s|$TMP/ph.json|$PH_JSON|" "$TMP/ph.out"
      [ -s "$TMP/ph.err" ] && { echo; echo "# notes and warnings (stderr):"; cat "$TMP/ph.err"; }; } > "$PH_TXT"
    cat "$PH_TXT"
    say "(c) power: $(grep -m1 '^tasks:' "$TMP/ph.out"); $(grep -c WARNING "$TMP/ph.err") warning(s); table in $PH_TXT"
  else
    tail -5 "$TMP/ph.err"
    say "(c) power: FAILED (exit $rc), previous outputs kept: $(tail -1 "$TMP/ph.err")"
  fi
else
  say "(c) power: FAILED, can't read the arms from $CONFIG: $ARMS"
fi

step "(d) dashboard from $CONFIG"
( cd "$EXP/viz" && python3 -I build_dashboard.py --config "$CONFIG" "${DASH_ARGS[@]}" ) > "$TMP/d.out" 2>&1
rc=$?; tail -4 "$TMP/d.out"
DASH=$(grep -o '^written [^ ]*' "$TMP/d.out" | tail -1 | cut -d' ' -f2)
[ -z "$DASH" ] && DASH=$(grep -o 'status page at [^ ]*' "$TMP/d.out" | tail -1 | cut -d' ' -f4)
if [ $rc = 0 ]; then say "(d) dashboard: $(grep -m1 '^written' "$TMP/d.out" || tail -1 "$TMP/d.out")"
else say "(d) dashboard: FAILED (exit $rc): $(tail -1 "$TMP/d.out")"; fi

step "(e) secret scan"
SINCE=${SCAN_SINCE:-$(git -C "$EXP" -c safe.directory='*' log -1 --format=%ct 2>/dev/null)}
SINCE=${SINCE:-$(date -d '-24 hours' +%s)}
{ find "$EXP/runs" "$EXP/findings" -type f -newermt "@$SINCE" 2>/dev/null
  for f in "$REG_OUT" "$PH_JSON" "$PH_TXT" ${DASH:+"$DASH"}; do [ -f "$f" ] && echo "$f"; done; } | sort -u > "$TMP/scan.list"
"$PY" "$HERE/secret_scan.py" "$TMP/scan.list" > "$TMP/e.out" 2>&1
rc=$?
case $rc in 0|1) grep -E '^(HIT|UNREADABLE|scanned) ' "$TMP/e.out" ;; esac  # the scanner prints paths and kinds only
case $rc in
  0) say "(e) secret scan, files changed since $(date -d "@$SINCE" '+%m-%d %H:%M'): $(tail -1 "$TMP/e.out")" ;;
  1) say "(e) secret scan: HITS, don't commit before checking: $(grep -c '^HIT' "$TMP/e.out") file(s), listed above; $(tail -1 "$TMP/e.out")" ;;
  *) say "(e) secret scan: FAILED to run (exit $rc): $(tail -1 "$TMP/e.out" | cut -c1-200)" ;;
esac

step "(f) summary"
printf '%s\n' "${SUMMARY[@]}"
