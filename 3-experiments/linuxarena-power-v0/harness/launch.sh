#!/usr/bin/env bash
# Launch one batch of runs under a new label, after writing its exact configuration, then export each
# run's complete readable record into the project folder. Refuses a label that is already used, so no
# run can overwrite or mix with another. Runs inside WSL as root.
#   usage: [PURPOSE="why this batch runs"] launch.sh <label> <task-file, relative to the harness> <max-samples> [-p name=value ...]
#   e.g.   launch.sh v2-before tasks/v0_tasks.txt 6 -p solver_user=dev
#          launch.sh traj2-power tasks/rbac_task.txt 1 -p solver_user=dev -p incline=gentle -p max_steps=200
# Model runs need OPENROUTER_API_KEY in the environment (passed in from Windows via WSLENV; never written
# to disk). Runs with -p solve=false make no model calls and get a placeholder key.
set -u
LABEL=$1; TASKS=$2; PAR=$3; shift 3
H=$(cd "$(dirname "$0")" && pwd); . "$H/paths.sh"; D=$POWER_V0_DATA; CT=$POWER_V0_CT
[ -e "$D/evals/$LABEL" ] || [ -e "$D/runs/$LABEL" ] && { echo "label $LABEL already used: refusing"; exit 3; }
case "$TASKS" in /*) TF=$TASKS ;; *) TF=$H/$TASKS ;; esac
[ -f "$TF" ] || { echo "no task file $TF"; exit 1; }
case " $* " in *" solve=false "*) export OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-placeholder-no-model-calls} ;; esac
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY not set"; exit 1; }
mkdir -p "$D/evals/$LABEL"
cd "$CT"; set -a; . "$POWER_V0_HOME/config/ct.env"; set +a; export PYTHONPATH=$H

usage(){ case "$OPENROUTER_API_KEY" in placeholder*) echo "n/a (no model calls)" ;; *)
  curl -s -m 15 https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["usage"])' 2>/dev/null || echo unknown ;; esac; }

CFG=$POWER_V0_HOME/config/$LABEL.txt
{
  echo "label=$LABEL tasks=$TF max_samples=$PAR started=$(date -u +%FT%TZ)"
  echo "purpose: ${PURPOSE:-not given}"
  echo "policy args: $*"
  echo "openrouter usage at start: $(usage)"
  echo "control-tower commit: $(git -C $CT rev-parse HEAD)"
  echo "model_registry: $(git -C $CT/.environments/model_registry -c safe.directory='*' rev-parse HEAD) (tag v1.0.1)"
  echo "harness file hashes (power_v0.py holds the exact wording of every prompt and note):"; sha256sum $H/*.py $H/*.txt $H/*.sh
  echo "images:"; docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}' | sort
  echo "docker daemon.json:"; cat /etc/docker/daemon.json
  echo "limits: --message-limit 2000 --token-limit 30000000 --scorer-timeout 600"
} > "$CFG"

.venv/bin/ct run eval --task-file "$TF" --policy power_v0:power_policy -p label=$LABEL "$@" \
  --epochs 1 --max-samples "$PAR" --message-limit 2000 --token-limit 30000000 --scorer-timeout 600 \
  --no-upload --no-fail-on-error --log-dir $D/evals/$LABEL --run-name power-v0-$LABEL > $D/evals/$LABEL.console.txt 2>&1
rc=$?
LOG=$(ls -t $D/evals/$LABEL/*.eval 2>/dev/null | head -1)
case "$TF" in *rbac_task.txt) [ -n "$LOG" ] && cp "$LOG" "$POWER_V0_HOME/trajectory/$LABEL.eval" ;; esac
{ echo "finished=$(date -u +%FT%TZ) ct_exit=$rc"; echo "log: ${LOG:-none}"; echo "openrouter usage at end: $(usage)"; } >> "$CFG"
.venv/bin/python $H/export_run.py "$LABEL" --check 2>&1 | grep -v -E "No tool calls associated|No pricing|Unknown policy|attempts fields|WARNING" > $D/evals/$LABEL.export.txt
echo "$LABEL: ct exit=$rc at $(date -u +%T), runs saved: $(find $D/runs/$LABEL -name meta.json 2>/dev/null | wc -l), export: $(grep -c complete $D/evals/$LABEL.export.txt) complete, $(grep -c MISSING $D/evals/$LABEL.export.txt) incomplete"
