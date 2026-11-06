#!/usr/bin/env bash
# One efficiency test's jobs side by side (plans/scoring-efficiency-tests.md), with the sampler running beside them.
#   bench_launch.sh <test name> <seconds between starts> <interval> -- <file of jobs>
# Each line of the file: <label>\t<POWER_BENCH JSON, or "-">\t<purpose>\t<task file>\t<-p options...>
# Waits for the load to fall under 12 before each start, for all jobs at the end, then stops the sampler and prints the
# report. Output stays in $POWER_V0_HOME/bench. Prints no secrets: launch.sh's own summary line and the report only.
set -u
TEST=$1; GAP=$2; IV=$3; JOBS=$5
H=$(cd "$(dirname "$0")" && pwd); . "$H/paths.sh"
B=$POWER_V0_HOME/bench; mkdir -p "$B/logs" "$B/samples"
S=$B/samples/$TEST.jsonl
python3 -I "$H/bench_sample.py" run "$S" --interval "$IV" --minutes 40 & SP=$!
trap 'kill $SP 2>/dev/null' EXIT
PIDS=(); LABELS=()
while IFS=$'\t' read -r LABEL SPEC PURP TASK OPTS; do
  [ -n "${LABEL:-}" ] || continue
  while [ "$(cut -d. -f1 /proc/loadavg)" -ge 12 ]; do sleep 10; done
  echo "$(date +%T) start $LABEL (load $(cut -d' ' -f1 /proc/loadavg))"
  (
    [ "$SPEC" = "-" ] && SPEC="{\"label\": \"$LABEL\"}"
    export POWER_BENCH="$SPEC"
    export PURPOSE="$PURP"
    TIMEFORMAT="$LABEL wall=%R user=%U sys=%S"
    { time bash "$H/launch.sh" "$LABEL" "$TASK" 1 $OPTS ; } >> "$B/logs/$TEST.launch.txt" 2>&1
  ) &
  PIDS+=($!); LABELS+=("$LABEL")
  sleep "$GAP"
done < "$JOBS"
wait "${PIDS[@]}"
kill $SP 2>/dev/null
echo "$(date +%T) all finished"
tail -n $((2 * ${#LABELS[@]})) "$B/logs/$TEST.launch.txt" | cut -c1-200
python3 -I "$H/bench_sample.py" report "$S" "${LABELS[@]}" --json "$B/samples/$TEST.report.json"
docker ps --format '{{.Names}}' | grep -vE '^(shared-minio|internet-simulator)$' | wc -l
