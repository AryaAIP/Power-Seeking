#!/usr/bin/env bash
# Feed the gap search to the job queue round by round (make_search_jobs.py): when the queue has nothing running or
# waiting, generate the next round and append it; stop when no gap is left to narrow or the queue has exited.
# Runs inside WSL as root, detached, so it keeps going if the Claude session ends:
#   setsid nohup bash /root/power-v0/harness/search_rounds.sh >/dev/null 2>&1 &
# Progress: /root/power-v0/queue/search.log. The queue itself (night_queue.py) must be running.
set -u
Q=/root/power-v0/queue; H=/root/power-v0/harness
log() { echo "$(TZ=America/Chicago date +%T) $*" >> $Q/search.log; }
round=0
while true; do
  sleep 30
  grep -q "queue exits" $Q/queue.log 2>/dev/null && { log "queue has exited: stopping"; exit 0; }
  head -1 $Q/status.tsv 2>/dev/null | grep -q "running=0 envs=0/[0-9]* pending=0" || continue
  round=$((round + 1))
  python3 -I $H/make_search_jobs.py > $Q/search-round$round.tsv 2>> $Q/search.log
  n=$(wc -l < $Q/search-round$round.tsv)
  if [ "$n" -eq 0 ]; then log "round $round: no gap left to narrow: done"; touch $Q/stop; exit 0; fi
  cat $Q/search-round$round.tsv >> $Q/jobs.tsv
  log "round $round: queued $n jobs"
  sleep 60  # let the queue pick them up before checking again
done
