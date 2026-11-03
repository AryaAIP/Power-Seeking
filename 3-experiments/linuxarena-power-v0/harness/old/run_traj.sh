#!/usr/bin/env bash
# Record a new trajectory on the RBAC task as the developer account `dev`, after saving the exact
# configuration. The log is copied to /root/power-v0/trajectory/<label>.eval for the after runs.
# Runs inside WSL as root.
#   usage: run_traj.sh <label> <incline|none> [max-steps]
#   e.g.   run_traj.sh traj-gentle gentle      -> the gentle instruction to gain access (run A)
#          run_traj.sh traj-neutral none       -> no instruction (run B)
# Needs OPENROUTER_API_KEY in the environment (passed in from Windows via WSLENV; never written to disk).
set -u
LABEL=$1; INCLINE=$2; MAXSTEPS=${3:-200}
H=/root/power-v0/harness; D=/root/power-v0/data; CT=/root/power-v0/src/control-tower
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY not set"; exit 1; }
[ ! -e "$D/evals/$LABEL" ] || { echo "label $LABEL already used"; exit 1; }
INC=(); [ "$INCLINE" = none ] || INC=(-p "incline=$INCLINE")
cd "$CT"; set -a; . /root/power-v0/config/ct.env; set +a; export PYTHONPATH=$H

CFG=/root/power-v0/config/$LABEL.txt
{
  echo "trajectory label=$LABEL task=$(cat $H/rbac_task.txt) incline=$INCLINE solver_user=dev max_steps=$MAXSTEPS started=$(date -u +%FT%TZ)"
  echo "control-tower commit: $(git -C $CT rev-parse HEAD)"
  echo "model_registry: $(git -C $CT/.environments/model_registry -c safe.directory='*' rev-parse HEAD) (tag v1.0.1)"
  echo "harness file hashes (power_v0.py holds the exact wording of every prompt and note):"; sha256sum $H/*.py $H/*.txt $H/*.sh
  echo "images:"; docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}' | sort
  echo "docker daemon.json:"; cat /etc/docker/daemon.json
  echo "limits: --message-limit 2000 --token-limit 30000000 --scorer-timeout 600, max_steps $MAXSTEPS"
} > "$CFG"

.venv/bin/ct run eval --task-file $H/rbac_task.txt --policy power_v0:power_policy -p label=$LABEL -p solver_user=dev \
  -p max_steps=$MAXSTEPS "${INC[@]}" --epochs 1 --max-samples 1 \
  --message-limit 2000 --token-limit 30000000 --scorer-timeout 600 --no-upload --no-fail-on-error \
  --log-dir $D/evals/$LABEL --run-name power-v0-$LABEL > $D/evals/$LABEL.console.txt 2>&1
rc=$?
LOG=$(ls -t $D/evals/$LABEL/*.eval 2>/dev/null | head -1)
[ -n "$LOG" ] && cp "$LOG" /root/power-v0/trajectory/$LABEL.eval
{ echo "finished=$(date -u +%FT%TZ) ct_exit=$rc"; echo "log: $LOG"; [ -n "$LOG" ] && sha256sum /root/power-v0/trajectory/$LABEL.eval; } >> "$CFG"
echo "$LABEL: ct exit=$rc at $(date -u +%T), log: ${LOG:-none}, runs saved: $(find $D/runs/$LABEL -name meta.json 2>/dev/null | wc -l)"
