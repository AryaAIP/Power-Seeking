#!/usr/bin/env bash
# Set up a fresh Ubuntu 26.04 (x86_64) machine to run the experiment the way WSL does (plans/vm-runbook.md). Run it as
# root on the machine, after vm/copy.sh has copied over the repository, the raw data and uv:
#   sudo bash /root/Power-Seeking/3-experiments/linuxarena-power-v0/harness/vm/setup.sh
# Safe to rerun: every step skips what's already done. It ends with a list of checks.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
export HOME=~root
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../paths.sh"
CT_REPO=https://github.com/linuxarena/control-tower.git
CT_COMMIT=699d5ca5c26ab3126fa29c6fa73dbf898aa0ca53
ENV_REPO=https://github.com/linuxarena/model_registry.git
ENV_COMMIT=b44867727eb2fbcf23ce50c4b9c96a864d924ef9  # tag v1.0.1
UV=$HOME/.local/bin/uv
UV_VERSION=0.13.6
# Docker's address ranges for the environments' networks: room for about 1,000 networks (its built-in ranges allow
# about 30, and each environment makes its own), clear of AWS's default VPC, 172.31.0.0/16.
POOL=10.200.0.0/14
# The images WSL runs, by registry digest, under the names Control Tower and the environment use.
IMAGES="linuxarena/env-model_registry:v1.0.1@sha256:1e33a98bf66caad05dc1b155739662c0a9c24dc8734598020e49138709cfb37f
linuxarena/env-model_registry-s3-init:v1.0.1@sha256:969d0dac8072a15d51d573c136e738dba851e4a17e4908d948d408af3e1ffe13
linuxarena/env-internet-simulator:v1.0.1@sha256:7e78c63719787104b7cdfcdf0e3c8f1d0e03e415da1cd4939b46a75dcd1f9bd3
postgres:16.12@sha256:23af655ba1ddf74eaa002e3deaf5fce022ab8791672336a7c1fb0ef2d57efb7f
nginx:1.29.5-alpine@sha256:1eff5a5f3fcf8431a0abb7eddf5471fec24e5e1905a2581aeacdb07a4479b92b
nginx:alpine@sha256:785835ea65db4bba6f021acc0f3be91b0fef76a53fe41f8588c6698d2aed0606
pgsty/minio:latest@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372"
# Second names, as in WSL: MinIO's own image is replaced by pgsty's build, and the internet simulator gets a local name
# so Control Tower's pull at every start fails at once and the cached image is used (ct.env).
RETAGS="pgsty/minio:latest minio/minio:latest
linuxarena/env-internet-simulator:v1.0.1 localhost/env-internet-simulator:v1.0.1"
step() { echo; echo "== $*"; }

step "1. The machine"
. /etc/os-release
echo "$PRETTY_NAME $(uname -m), $(nproc) cores, $(free -g | awk '/^Mem/ {print $2}') GB memory"
[ "$VERSION_ID" = 26.04 ] && [ "$(uname -m)" = x86_64 ] || echo "WARNING: WSL runs Ubuntu 26.04 on x86_64, and this machine differs"

step "2. Packages"
export DEBIAN_FRONTEND=noninteractive
cloud-init status --wait >/dev/null 2>&1 || true  # a fresh EC2 machine updates its packages at boot and holds the lock
apt-get -o DPkg::Lock::Timeout=600 update -qq
apt-get -o DPkg::Lock::Timeout=600 install -y -qq docker.io docker-compose-v2 git rsync python3 tmux curl >/dev/null
dpkg-query -W -f='${Package} ${Version}\n' docker.io docker-compose-v2 containerd runc python3
echo "(WSL: docker.io 29.1.3-0ubuntu4.1, docker-compose-v2 2.40.3+ds1-0ubuntu1, containerd 2.2.2-0ubuntu1.2, runc 1.4.0-0ubuntu1, python3 3.14.3-0ubuntu2)"

step "3. Docker and kernel settings"
python3 - "$POOL" <<'PY'
import ipaddress, subprocess, sys
pool = ipaddress.ip_network(sys.argv[1])
for line in subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True, text=True).stdout.splitlines():
    dev, net = line.split()[1], ipaddress.ip_interface(line.split()[3]).network
    if net.overlaps(pool) and not dev.startswith(("br-", "docker")):
        sys.exit(f"{pool} overlaps this machine's network {net} ({dev}): change POOL in setup.sh")
print(f"{pool} is clear of this machine's networks")
PY
# Not WSL's settings: its MTU 1350 and one download at a time were fixes for WSL's network and the home connection.
want='{
  "max-download-attempts": 10,
  "features": { "containerd-snapshotter": true },
  "default-address-pools": [ { "base": "'$POOL'", "size": 24 } ]
}'
if [ "$(cat /etc/docker/daemon.json 2>/dev/null)" != "$want" ]; then
  [ -f /etc/docker/daemon.json ] && cp /etc/docker/daemon.json "/etc/docker/daemon.json.bak-$(date +%s)"
  mkdir -p /etc/docker && echo "$want" > /etc/docker/daemon.json
  systemctl restart docker && echo "wrote /etc/docker/daemon.json and restarted Docker"
fi
systemctl enable -q docker containerd
docker info --format 'Docker {{.ServerVersion}}, storage {{.Driver}} {{.DriverStatus}}'
# Many environments at once: the containers' processes all count against root's inotify limits.
printf '%s\n' "# The power experiment: many environments at once (harness/vm/setup.sh)" \
  "fs.inotify.max_user_instances = 8192" "fs.inotify.max_user_watches = 1048576" > /etc/sysctl.d/90-power-v0.conf
sysctl -q --system

step "4. Folders and Control Tower's settings"
mkdir -p "$POWER_V0_HOME"/{data/evals,data/runs,queue,config,trajectory,src}
[ -f "$POWER_V0_HOME/queue/max_envs" ] || echo 16 > "$POWER_V0_HOME/queue/max_envs"
ct_env="SKIP_DOCKER_BUILD=1
ENV_IMAGE_TAG_MODEL_REGISTRY=v1.0.1
INTERNET_SIMULATOR_IMAGE=localhost/env-internet-simulator:v1.0.1
DISABLE_TUI=1
INSPECT_LOG_LEVEL=warning
POWER_V0_DATA=$POWER_V0_DATA"
f=$POWER_V0_HOME/config/ct.env
if [ "$(cat "$f" 2>/dev/null)" != "$ct_env" ]; then
  [ -f "$f" ] && cp "$f" "$f.bak-$(date +%s)"
  echo "$ct_env" > "$f" && echo "wrote $f"
fi
echo "queue cap: $(cat "$POWER_V0_HOME/queue/max_envs") environments"

step "5. uv"
[ -x "$UV" ] && "$UV" --version | grep -q " $UV_VERSION " || { echo "uv $UV_VERSION isn't at $UV: run vm/copy.sh to <address> in WSL first"; exit 1; }
"$UV" --version

step "6. Control Tower"
CT=$POWER_V0_CT
[ -d "$CT/.git" ] || git clone -q "$CT_REPO" "$CT"
[ "$(git -C "$CT" rev-parse HEAD)" = "$CT_COMMIT" ] || git -C "$CT" checkout -q --detach "$CT_COMMIT"
if [ ! -x "$CT/.venv/bin/ct" ]; then
  # --frozen installs exactly the lockfile. inspect-ai 0.3.171 is no longer listed on PyPI, but its file is still there.
  (cd "$CT" && "$UV" sync --frozen) || { echo "uv sync failed: in WSL run vm/copy.sh venv <address>, which copies WSL's environment, then rerun"; exit 1; }
fi
"$UV" pip freeze --python "$CT/.venv/bin/python" > /tmp/ct-packages.machine.txt
if diff -q "$HERE/ct-packages.txt" /tmp/ct-packages.machine.txt >/dev/null; then
  echo "packages: the same $(wc -l < "$HERE/ct-packages.txt") as WSL"
else
  echo "WARNING: packages differ from WSL's (< WSL, > this machine):"; diff "$HERE/ct-packages.txt" /tmp/ct-packages.machine.txt | head -20 || true
fi

step "7. The environment, model_registry"
E=$CT/.environments/model_registry
[ -d "$E/.git" ] || git clone -q "$ENV_REPO" "$E"  # a real folder: a symlink breaks Control Tower's module loader
[ "$(git -C "$E" rev-parse HEAD)" = "$ENV_COMMIT" ] || git -C "$E" checkout -q --detach "$ENV_COMMIT"
lock="# Auto-generated by ct registry. Do not edit unless pinning versions.
environments:
  model_registry:
    path: $E
    ref: local"
[ "$(cat "$CT/.environments.lock.yml" 2>/dev/null)" = "$lock" ] || echo "$lock" > "$CT/.environments.lock.yml"
(cd "$CT" && timeout 120 .venv/bin/ct registry status 2>&1 | tail -4) || true

step "8. Images (about 13 GB the first time)"
while read -r ref; do
  name=${ref%@*}; digest=${ref#*@}; repo=${name%:*}
  if [ "$(docker image inspect --format '{{.Id}}' "$name" 2>/dev/null)" = "$digest" ]; then echo "have $name"; continue; fi
  docker pull -q "$repo@$digest" >/dev/null && docker tag "$repo@$digest" "$name" || { echo "couldn't pull $ref"; exit 1; }
  echo "pulled $name"
done <<< "$IMAGES"
while read -r from to; do docker tag "$from" "$to"; done <<< "$RETAGS"
docker images --format '{{.ID}} {{.Repository}}:{{.Tag}}' | sort -k2

step "9. The harness"
bash "$HERE/../sync.sh"

step "10. Checks"
echo "Control Tower $(git -C "$CT" rev-parse --short HEAD), model_registry $(git -C "$E" describe --tags 2>/dev/null || git -C "$E" rev-parse --short HEAD)," \
  "Python $("$CT/.venv/bin/python" --version 2>&1 | cut -d' ' -f2) (WSL: 3.13.18)"
echo "raw data: $(find "$POWER_V0_DATA/evals" -mindepth 1 -maxdepth 1 -type d | wc -l) labels, $(du -sh "$POWER_V0_DATA" | cut -f1);" \
  "trajectories: $(ls "$POWER_V0_HOME/trajectory" | tr '\n' ' ')"
echo "free disk: $(df -h --output=avail / | tail -1 | tr -d ' ')"
[ -n "${OPENROUTER_API_KEY:-}" ] && echo "OpenRouter key: set in this shell" \
  || echo "OpenRouter key: not set here. Arya sets it in the queue's tmux session before paid runs"
echo "set-up done"
