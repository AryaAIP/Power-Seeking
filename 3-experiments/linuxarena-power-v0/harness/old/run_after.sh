#!/usr/bin/env bash
# The after runs for a trajectory recorded as `dev` with this harness (run_traj.sh): each of the 6 v0
# tasks starts from a fresh environment, the trajectory is replayed as dev, and the solver continues
# the trajectory's own conversation, optionally with a note before the hand-over. Runs inside WSL as root.
#   usage: run_after.sh <label> <trajectory .eval> [handover-note|none] [max-samples]
#   e.g.   run_after.sh after-gentle  /root/power-v0/trajectory/traj-gentle.eval  stop   -> run A
#          run_after.sh after-neutral /root/power-v0/trajectory/traj-neutral.eval none   -> run B
# Needs OPENROUTER_API_KEY in the environment (passed in from Windows via WSLENV; never written to disk).
set -u
LABEL=$1; TRAJ=$2; NOTE=${3:-none}; PAR=${4:-3}
H=/root/power-v0/harness; D=/root/power-v0/data; CT=/root/power-v0/src/control-tower
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY not set"; exit 1; }
[ -f "$TRAJ" ] || { echo "no trajectory at $TRAJ"; exit 1; }
[ ! -e "$D/evals/$LABEL" ] || { echo "label $LABEL already used"; exit 1; }
NP=(); [ "$NOTE" = none ] || NP=(-p "handover_note=$NOTE")
cd "$CT"; set -a; . /root/power-v0/config/ct.env; set +a; export PYTHONPATH=$H

CFG=/root/power-v0/config/$LABEL.txt
{
  echo "after runs label=$LABEL handover_note=$NOTE solver_user=dev traj_user=dev context=kept max_samples=$PAR started=$(date -u +%FT%TZ)"
  echo "control-tower commit: $(git -C $CT rev-parse HEAD)"
  echo "model_registry: $(git -C $CT/.environments/model_registry -c safe.directory='*' rev-parse HEAD) (tag v1.0.1)"
  echo "harness file hashes (power_v0.py holds the exact wording of every prompt and note):"; sha256sum $H/*.py $H/*.txt $H/*.sh
  echo "trajectory: $(sha256sum $TRAJ)"
  echo "images:"; docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}' | sort
  echo "docker daemon.json:"; cat /etc/docker/daemon.json
  echo "limits: --message-limit 2000 --token-limit 30000000 --scorer-timeout 600, solver max_steps 80"
} > "$CFG"

.venv/bin/ct run eval --task-file $H/v0_tasks.txt --policy power_v0:power_policy -p label=$LABEL -p solver_user=dev \
  -p traj=$TRAJ -p traj_user=dev -p traj_cmd_bug=false -p context=kept "${NP[@]}" \
  --epochs 1 --max-samples "$PAR" --message-limit 2000 --token-limit 30000000 --scorer-timeout 600 \
  --no-upload --no-fail-on-error --log-dir $D/evals/$LABEL --run-name power-v0-$LABEL > $D/evals/$LABEL.console.txt 2>&1
rc=$?
echo "finished=$(date -u +%FT%TZ) ct_exit=$rc" >> "$CFG"
echo "$LABEL: ct exit=$rc at $(date -u +%T), runs saved: $(find $D/runs/$LABEL -name meta.json 2>/dev/null | wc -l)"
.venv/bin/python $H/extract.py 2>&1 | grep -v -E "No tool calls associated|No pricing|Unknown policy|attempts fields|WARNING" | grep -E "rows ->|$LABEL"
