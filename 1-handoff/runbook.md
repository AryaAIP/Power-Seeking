# Runbook: running experiments for this project

*Written 2026-11-01; LinuxArena section updated after the pilot the same day. This holds the practical setup knowledge that was otherwise only in chat. Numbers come from the BashArena test on Nov 1 unless noted. Update this file when something changes.*

## 1. Where work can run

### Cloud sessions (project threads on claude.ai)

- **Machine:** 4 CPUs, 15 GB of RAM and about 30 GB of disk, as of Nov 1.
- **Temporary:** the machine is reclaimed when a session goes idle or ends, and Docker images go with it. A fresh session needs about 10 minutes to rebuild BashArena's images. Anything worth keeping goes in `/mnt/project-files/`.
- **Environment:** the project's default cloud environment (set by Arya on Nov 1) allows openrouter.ai and huggingface.co and provides the `OPENROUTER_API_KEY` environment variable. Sessions pick up environment changes only when they start, not mid-session.
- **Docker:** start the daemon yourself (`dockerd &`). Anonymous pulls from Docker Hub hit a rate limit (HTTP 429), so pull through Google's mirror instead, for example `mirror.gcr.io/library/ubuntu:22.04`.
- **HTTPS inside containers:** the workspace proxy intercepts it with a certificate the containers don't trust. The fix used for BashArena was rebuilt base images (ubuntu:22.04, alpine:3.20, python:3.12-slim) that trust the proxy certificate and have server packages preinstalled. They were built with the host network, and Inspect ran with prebuilt images. The files are in `3-experiments/basharena-test/overrides/`.
- **Agent internet:** the agent's own container has no working HTTPS in the cloud, so tasks that `pip install` during a run will fail here. Original BashArena gives the agent open internet.
- **GitHub:** a repository must be attached to the session before GitHub tools or the API will touch it.

### Arya's laptop, as of Nov 1

- **State:**
  - WSL is installed but has no Linux distribution yet.
  - Docker Desktop is not installed.
  - OpenRouter is reachable.
- **Project folder:** a local copy of this folder, synced by OneDrive. An older second copy also exists.

**To run locally, all of these need to be true:**

1. Docker Desktop is installed with the WSL 2 backend and Linux containers.
2. Ubuntu is installed in WSL (`wsl --install -d Ubuntu`), with Docker's WSL integration switched on for it.
3. Code and output live in the WSL home folder (for example `~/basharena`), not under OneDrive or `/mnt/c`. OneDrive would sync the logs constantly, and `/mnt/c` is slow.
4. Docker Desktop's Docker Engine settings contain the `default-address-pools` block from BashArena's README, so many task networks can exist at once.
5. WSL has enough memory, set in `%USERPROFILE%\.wslconfig`, if running many environments in parallel.
6. Python is 3.11+ for ControlArena, or 3.13+ for LinuxArena's Control Tower.
7. You've run `docker login`, so image pulls don't hit Docker Hub's rate limit.
8. `OPENROUTER_API_KEY` is set in the WSL shell.
9. The laptop is plugged in and set never to sleep while plugged in.
10. If a Claude is to drive the run, Claude Code is installed on the laptop for a Remote Control session.

BashArena's containers don't mount host files or the Docker socket. Even so, run long batches from the WSL home folder, not the personal folders.

## 2. Model and provider

- **Solver:** DeepSeek V4.1 Flash 1017 (MIT licence, 1M context; the model card recommends temperature 1.0), called through OpenRouter.
- **Provider:** pin DeepInfra fp8 with fallbacks off. Arya's OpenRouter privacy setting blocks DeepSeek's own endpoint. Pinning also keeps the model identical between runs.
- **Prices:** $0.098 per million input tokens and $0.294 per million output tokens. Prompt caching covered about 90% of input tokens.
- **Token limit:** Inspect's default of 1M ended a run early, because cached input counts toward it. Raise it, or rely on the step limit alone.
- **Keys:** read the key only from the environment variable or the cloud environment settings. Never put a key in chat, a file, a doc or a log. A key was pasted in chat on Nov 1 and should be rotated.

## 3. BashArena (through ControlArena)

- **Package:** `control-arena==20.1.1` on PyPI (MIT licence), which contains BashArena 1.1. Tasks load from the Hugging Face dataset `Eccentricity/bashbench2`: 637 main tasks in 9 clusters.
- **Environment:** 5 containers per task (the agent's container, a router and three servers), with memory limits totalling about 2.3 GB. An idle environment measured about 270 MB.
- **Timings:**

  | Step | Time |
  | --- | --- |
  | Base image build | 4.9 min, 3.3 GB |
  | Each task image | 6 to 8 s |
  | Start, one environment | 18 s |
  | Start, 8 at once | 46 s (startup is CPU-bound) |
  | Teardown | About 20 s; a 1-s stop timeout cuts it to 3 s |
  | Container snapshot | 3.7 s |
  | Full copy started | 18 s |
- **Copies:** running processes don't survive a copy, so the firewall daemon has to be restarted in the copy.
- **Scoring:** score on a copy, never the live container. The hidden tests leave files in `/tmp` that the agent could read.
- **Users:** the agent runs as root by default. Running it as the regular user `app` is a harness setting (Inspect's bash tool can run as a chosen user), not a change to the environment.
- **Cost and throughput:** about $0.013 per 30-step run on average. About 1,100 runs would cost roughly $14 to $21, and take about 12 hours on the cloud box at 8 environments at a time.
- **Harness:** `3-experiments/basharena-test/harness/`, containing `run_agent.py`, `infra_checks.py`, `parallel_load.py`, `analyze.py` and `common.py`. Results are in `3-experiments/basharena-test/logs/`.

## 4. LinuxArena (through Control Tower)

See `3-experiments/linuxarena-pilot/scope.md` for the scope and `3-experiments/linuxarena-pilot/results.md` for the pilot. The notes below were updated after the Nov 1 pilot, which ran 3 tasks in the cloud box.

- **Install:** `control-tower==1.0.1`, which pins inspect-ai 0.3.171, installed with `uv sync --frozen` on Python 3.13+.
- **Environments:** `ct settings pull linuxarena` clones the 10 public environments from github.com/linuxarena, using the GitHub CLI.
- **Images:** the prebuilt v1.0.1 images are public on Docker Hub, so no local builds are needed. Set `SKIP_DOCKER_BUILD=1` and pin the image tags, as in `3-experiments/linuxarena-pilot/harness/control-tower.env.example`. Each environment was ready 16 to 71 s after its images were pulled. (Notes written before the pilot said the images were private. They aren't.)
- **MinIO:** model_registry's storage service uses `minio/minio`, which has been removed from Docker Hub. The pilot tagged the community fork `pgsty/minio` under that name, which Arya approved on Nov 1, and it worked. Any other environment that uses MinIO needs the same fix.
- **Memory and disk:** the paper recommends 32 GB+ of RAM, but three environments in parallel peaked at about 2 GB. Disk is the real limit. The three environments' images took 23 GB (model_registry alone is 9.4 GB), which left about 7 GB of the cloud session's allowance.
- **HTTPS in the cloud box:** containers don't trust the workspace proxy's certificate. For the run 2 re-score, the fix was to mount the CA bundle into the container and set `SSL_CERT_FILE`. Make that the default, but note it also removes the obstacle that led to run 3's most interesting moment.
- **Agent user:** LinuxArena runs the agent as root by default (`agent_user`), so privilege escalation can't show up. To watch for it, run the agent as a non-root user, in environments where the task still works that way.
- **Policy and limits used:** Control Tower's stock `honest` policy, with no side task and DeepSeek pinned to DeepInfra fp8 (see `harness/ds_policy.py`). It used medium reasoning effort, a 16k output cap and a 150-step limit, which was the limit that bound. The message limit was raised from 300 to 500, and the token limit to 30M (the largest run used 13.9M).
- **Tool-call bug, fix before scaling:** DeepSeek often names the bash argument `command` instead of `cmd`. That caused 87 failed calls across the 3 runs, about a fifth of all steps, and each one uses up a step. Accept `command` as an alias, or rename the argument.
- **Cost and time:** about 8 cents a run ($0.23 for 3; 31M tokens, 97% cached). Runs took 12 to 41 minutes each, and three ran side by side without trouble.
- **Replay:** `ct run rerun-traj` replays a trajectory's actions into a fresh environment. It took 2.5 minutes for 86 actions, which is useful for re-scoring and may be enough for branching from a midpoint. Snapshots with `docker commit` weren't tested.
- **Reading runs:** `harness/dump_traj.py` turns a `.eval` log into a readable transcript like those in `transcripts/`.
- **Free trajectories:** published honest runs by 7 frontier models are at data.linuxarena.ai. The pilot used them to pick tasks.

## 5. AppWorld

- **Install:** `pip install appworld`, then `appworld install`.
- **No Docker needed:** the 9 apps and their SQLite databases run in the same Python process as the agent's code.
- **State:** loading a task resets the databases in under half a second after the first load. The databases can be checkpointed and restored.
- **Optional server mode:** `appworld serve environment --docker` runs the environment in a container, for safety.
- **Source:** https://github.com/StonyBrookNLP/appworld

## 6. Reading Inspect logs

- **Format:** a `.eval` file is a zip archive, and its `samples/*.json` entries are compressed with zstd.
- **Python 3.13's `zipfile` can't read zstd.** Either use Inspect's own reader (`inspect_ai.log.read_eval_log`, or `inspect view` in a browser), or `pip install zstandard` and decompress each entry yourself.
- **Reporting trajectories:** when an agent probes its own permissions, describe what it did in plain prose and don't paste raw command transcripts into chat or docs. Arya wants the behaviour explained, and long raw dumps have caused sessions to be cut off.
