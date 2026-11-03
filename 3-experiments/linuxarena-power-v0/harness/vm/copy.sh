#!/usr/bin/env bash
# Copy what the cloud machine needs from WSL, or bring its results back (plans/vm-runbook.md). Runs in WSL as root.
#   copy.sh to <address>     the repository (a git bundle of the current branch: committed files only), uv, and the
#                            raw data: data/, trajectory/ and config/'s per-run settings. Raw data goes only over SSH.
#                            COPY_DATA=0 leaves out data/ (old runs' logs and snapshots): only trajectory/ and config/ go.
#   copy.sh venv <address>   WSL's Control Tower environment and its Python, only if uv sync fails on the machine
#   copy.sh back <address>   the machine's readable records into this repository's runs/, and its raw data into WSL
# The machine's login is ubuntu (with sudo) and the key ~/.ssh/Power1.pem; VM_USER and VM_KEY change them. Both sides
# use the same folders ($POWER_V0_HOME, default /root/power-v0), so paths inside the raw data stay valid.
set -euo pipefail
WHAT=${1:-}; ADDR=${2:-}
[ -n "$ADDR" ] && case "$WHAT" in to|venv|back) ;; *) false ;; esac || { sed -n 2,7p "$0"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../paths.sh"
EXP=$(dirname "$(dirname "$HERE")")
GIT=(git -C "$EXP" -c safe.directory='*')
REPO=$("${GIT[@]}" rev-parse --show-toplevel)
REMOTE_REPO=/root/Power-Seeking
REMOTE_EXP=$REMOTE_REPO/${EXP#"$REPO"/}
KEY=${VM_KEY:-$HOME/.ssh/Power1.pem}
DEST=${VM_USER:-ubuntu}@$ADDR
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$HOME/.ssh/known_hosts_power_vm"
RSYNC=(rsync -a --partial --mkpath --info=stats1 -e "$SSH" --rsync-path="sudo rsync")
[ -f "$KEY" ] || { echo "no key at $KEY"; exit 1; }
$SSH "$DEST" 'command -v rsync >/dev/null && command -v git >/dev/null ||
  { sudo cloud-init status --wait >/dev/null 2>&1; sudo apt-get -o DPkg::Lock::Timeout=600 update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y -qq rsync git >/dev/null; }'

case "$WHAT" in
to)
  BR=$("${GIT[@]}" rev-parse --abbrev-ref HEAD)
  b=$(mktemp -d)/power-seeking.bundle
  "${GIT[@]}" bundle create -q "$b" "$BR"
  "${RSYNC[@]}" "$b" "$DEST:/root/power-seeking.bundle"
  $SSH "$DEST" sudo bash -s -- "$BR" "$REMOTE_REPO" "$REMOTE_EXP" <<'EOF'
set -e; export HOME=~root; BR=$1; R=$2; X=$3
if [ -d "$R/.git" ]; then
  git -C "$R" fetch -q /root/power-seeking.bundle "$BR" && git -C "$R" merge -q --ff-only FETCH_HEAD
else
  git clone -q -b "$BR" /root/power-seeking.bundle "$R" && git -C "$R" remote set-url origin https://github.com/AryaAIP/Power-Seeking.git
fi
echo "repository on the machine: $(git -C "$R" log --oneline -1)"
[ -f "$HOME/power-v0/harness/exp-dir" ] && bash "$X/harness/sync.sh"  # once the machine is set up: refresh the copy that runs
true
EOF
  "${RSYNC[@]}" "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx" "$DEST:/root/.local/bin/"
  for d in $([ "${COPY_DATA:-1}" = 0 ] || echo data) trajectory; do "${RSYNC[@]}" "$POWER_V0_HOME/$d/" "$DEST:$POWER_V0_HOME/$d/"; done
  "${RSYNC[@]}" --exclude 'ct.env*' "$POWER_V0_HOME/config/" "$DEST:$POWER_V0_HOME/config/"
  echo "next, on the machine: sudo bash $REMOTE_EXP/harness/vm/setup.sh"
  ;;
venv)
  "${RSYNC[@]}" "$HOME/.local/share/uv/python/" "$DEST:/root/.local/share/uv/python/"
  "${RSYNC[@]}" "$POWER_V0_CT/.venv/" "$DEST:$POWER_V0_CT/.venv/"
  echo "next, on the machine: rerun setup.sh"
  ;;
back)
  # Into the OneDrive folder: compared by content, with no owners, permissions or times, so files that haven't changed
  # are left alone (the machine's checkout gives every file a new time, and OneDrive would upload them all again).
  rsync -rlc --partial --info=stats1 -e "$SSH" --rsync-path="sudo rsync" "$DEST:$REMOTE_EXP/runs/" "$EXP/runs/"
  # --update: a file that's newer here is kept. The machine may hold a stale copy (from copy.sh to) of a batch that
  # was still running here, e.g. a trajectory; without it, that copy would overwrite the live files (Nov 3).
  for d in data trajectory; do "${RSYNC[@]}" --update "$DEST:$POWER_V0_HOME/$d/" "$POWER_V0_HOME/$d/"; done
  "${RSYNC[@]}" --update --exclude 'ct.env*' "$DEST:$POWER_V0_HOME/config/" "$POWER_V0_HOME/config/"
  echo "records are in $EXP/runs: run the secret scan before committing"
  ;;
esac
