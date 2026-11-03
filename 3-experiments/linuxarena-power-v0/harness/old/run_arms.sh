#!/usr/bin/env bash
# Run the before (S0, fresh context) and after (S1 = run 3 replayed, kept context) arms of v0
# side by side, after saving the exact configuration. Runs inside WSL as root.
#   usage: run_arms.sh <name> <epochs> [max-samples-per-arm] [solver-user]
#   e.g.   run_arms.sh pilot 1 3          -> labels pilot-S0 and pilot-S1, root solver
#          run_arms.sh pilotdev 1 3 dev   -> the constrained (non-root developer) solver in both arms
# Needs OPENROUTER_API_KEY in the environment (passed in from Windows via WSLENV; never written to disk).
set -u
NAME=$1; EPOCHS=$2; PAR=${3:-3}; SOLVER_USER=${4:-root}
H=/root/power-v0/harness; D=/root/power-v0/data; CT=/root/power-v0/src/control-tower
R3=/root/power-v0/trajectory/run3.eval
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY not set"; exit 1; }
cd "$CT"; set -a; . /root/power-v0/config/ct.env; set +a; export PYTHONPATH=$H

CFG=/root/power-v0/config/$NAME.txt
{
  echo "name=$NAME epochs=$EPOCHS max_samples_per_arm=$PAR solver_user=$SOLVER_USER started=$(date -u +%FT%TZ)"
  echo "control-tower commit: $(git -C $CT rev-parse HEAD)"
  echo "model_registry: $(git -C $CT/.environments/model_registry -c safe.directory='*' rev-parse HEAD) (tag v1.0.1)"
  echo "harness file hashes:"; sha256sum $H/*.py $H/*.txt $H/*.sh
  echo "trajectory: $(sha256sum $R3)"
  echo "images:"; docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}' | sort
  echo "docker daemon.json:"; cat /etc/docker/daemon.json
  echo "limits: --message-limit 2000 --token-limit 30000000 --scorer-timeout 600, solver max_steps 80"
} > "$CFG"

LIMITS="--message-limit 2000 --token-limit 30000000 --scorer-timeout 600"
arm(){ label=$1; shift
  .venv/bin/ct run eval --task-file $H/v0_tasks.txt --policy power_v0:power_policy -p label=$label -p solver_user=$SOLVER_USER "$@" \
    --epochs "$EPOCHS" --max-samples "$PAR" $LIMITS --no-upload --no-fail-on-error \
    --log-dir $D/evals/$label --run-name power-v0-$label > $D/evals/$label.console.txt 2>&1
  echo "$label: ct exit=$? at $(date -u +%T), runs saved: $(find $D/runs/$label -name meta.json 2>/dev/null | wc -l)"; }

arm "$NAME-S0" &
arm "$NAME-S1" -p traj=$R3 -p context=kept &
wait
echo "finished=$(date -u +%FT%TZ)" >> "$CFG"
.venv/bin/python $H/extract.py 2>&1 | grep -v -E "No tool calls associated|No pricing|Unknown policy|attempts fields|WARNING" | grep -E "rows ->|$NAME-"
