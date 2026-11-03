> **Snapshot.** Exported on 2026-11-01 from the live Claude Doc "First power-measurement experiment: plan and map" (https://claude.ai/artifact/9zptMEwRce53qJjfvVBeT7), rev 3. The live doc is the source of truth; this copy exists so agents without the docs tools can read it. Chips (dates, mentions, tab links) became plain text and diagrams became placeholders.

# DeepSeek test run on short BashArena tasks

Short version: three DeepSeek runs on one short task, plus checks that need no model. Together they exercise and time every step of the future power measurement once: building and starting environments, applying a change before the solver starts, running the hidden tests, model calls, cost, and running many environments at once. This workspace can already run BashArena's containers. What's missing is network access to OpenRouter and Hugging Face, plus an OpenRouter API key in the environment settings.

## What I already checked

- **Docker runs in this workspace.** The Docker daemon starts here. Docker Hub refused anonymous pulls (rate limit), but Google's mirror of it (mirror.gcr.io) works, including the ubuntu:22.04 image BashArena builds on. The machine has 4 CPUs, 15 GB of memory and about 30 GB of free disk.
- **ControlArena installs from PyPI** (version 20.1.1, MIT license) and contains BashArena 1.1.
- **BashArena's tasks load from Hugging Face** (the dataset Eccentricity/bashbench2), which this workspace's network settings block.
- **OpenRouter is blocked too,** and there's no API key in the environment.
- **Each task environment is 5 containers:** the agent's container (1 GB memory limit), a router (128 MB), a logging server (384 MB), and database and malware servers. ControlArena's README says to widen Docker's network address pools before running many environments in parallel.
- **Agent tools:** bash and python, each with a 300-second timeout, and a file editor.
- **How the hidden tests run:** the scorer writes the tests into the container, runs them with pytest, then deletes them, installing pytest first if it's missing. So scoring can change the container slightly, which matters if we score in the middle of a run.
- **There's no built-in regular-user mode.** The base image creates a regular user called app and has limited sudo rules for some service accounts. Inspect's bash tool can run commands as a chosen user, so a regular-user mode is a small harness setting rather than a change to the environment.

## Picking the task

No per-task lengths are published, so pick by metadata alone. Rank tasks by description length and number of tests, prefer tasks without a custom server, and take the top one plus two backups in case a build fails.

## The checks and runs, and what each tells us

Checks that need no model. They cost nothing in model calls, so they stay:

| Check | What | What it tells us |
| --- | --- | --- |
| C1 Setup | Install ControlArena, then build the base image and the 3 task images | Build time and disk use per image, and any build failures |
| C2 Empty submission | Start each environment and run the tests with no work done | Startup time, test runtime, and which tests pass for free |
| C3 Test repeatability | Run the tests twice on the same untouched state, and compare the container before and after | Whether tests give the same answer twice, and whether running them changes the state |
| C4 Parallel load | Start 4, then 8 environments at once | Memory and CPU per environment, and how many fit on one machine |
| C5 Container copy | Copy a running container, restore it, and run the tests on the copy | How long a copy takes, needed for scoring at checkpoints and for Travis-style step measurement |

The three DeepSeek runs, all on the same task with a 30-action limit:

| Run | Setup | What it tells us |
| --- | --- | --- |
| Run 1 | As root, BashArena's default | Whether its tool calls parse (Travis's Nemotron often wrote prose instead), latency and tokens per step, steps to submit, the score, and cost per run |
| Run 2 | As the regular user app | Whether the regular-user mode works, and how much of the task a regular user can still do |
| Run 3 | As app, with passwordless sudo applied before the solver starts | That applying a change works end to end. Run 3 minus Run 2 is a first power reading, but from a single pair of runs it shows the pipeline works, not the size of the effect |

What three runs can't tell us: the run-to-run spread the confidence-interval formula needs, DeepSeek's success rate across tasks, or how many tasks give partial scores. Those wait for the first real pilot.

Total model use: 3 runs, at most 90 actions.

## What we record for every run

- Timestamps for build, start, applying the change, every step, the tests and teardown.
- For each step: input and output tokens, latency, whether the tool call parsed, the command and its exit code.
- The final score (tests passed out of total), steps used, and whether the solver submitted or hit the limit.
- The container's file changes at the end, the model and provider version, and the seed.

Inspect's logs hold most of this already.

## Go or no-go for the power runs

1. Tool calls parse in at least 95% of steps across the three runs.
2. Run 1 gets a partial or full score within 30 actions, so the task is within reach.
3. Environment overhead per run (start, apply the change, tests, teardown) stays under about 2 minutes.
4. The tests give the same answer when run twice on the same state.
5. Cost per 30-action run, multiplied by about 1,100 runs, fits the budget.
6. At least 4 environments start in parallel on one machine without failures.

## What it needs

- **Network and key:** this project runs on the built-in cloud environment, which has no settings. To allow the run here, open Project settings, then Cloud environment, and choose Add cloud environment. Under network access, add openrouter.ai and huggingface.co as allowed domains, keeping package managers ticked, and add an environment variable named OPENROUTER\_API\_KEY with your key. Sessions started after that pick it up.
- **Or your own machine:** any machine with Docker can run it through a Remote Control session instead.
- **Provider:** pin one OpenRouter provider for DeepSeek V4.1 Flash 1017, so the model doesn't change between runs.
- **Time:** a few hours for setup and runs once access exists. I can drive it.
