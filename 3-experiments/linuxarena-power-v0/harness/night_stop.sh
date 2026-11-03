#!/usr/bin/env bash
# The hard stop (plans/night-plan.md): stop every run and remove every container and network the runs made, so
# nothing is running on the computer at 12:55. Runs inside WSL as root. With "wait", it sleeps until 12:50 CST.
#   usage: night_stop.sh [wait]
set -u
Q=/root/power-v0/queue; mkdir -p $Q
if [ "${1:-}" = wait ]; then
  target=$(TZ=America/Chicago date -d "2026-11-02 12:50" +%s)
  while [ "$(date +%s)" -lt "$target" ]; do sleep 30; done
fi
touch $Q/stop
echo "$(TZ=America/Chicago date +%T) hard stop: stopping runs" >> $Q/queue.log
pkill -f night_queue.py
pkill -TERM -f "ct run eval"; sleep 20; pkill -KILL -f "ct run eval"; pkill -KILL -f "launch.sh"
ids=$(docker ps -aq); [ -n "$ids" ] && docker rm -f $ids >/dev/null
docker network prune -f >/dev/null
echo "$(TZ=America/Chicago date +%T) hard stop done: $(docker ps -q | wc -l) containers running" >> $Q/queue.log
