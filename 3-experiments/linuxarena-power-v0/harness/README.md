# Harness

The code for LinuxArena power v0. **This folder is the one copy to edit.** `sync.sh` copies it to `~/power-v0/harness/`, where it runs, and checks the hashes. On the laptop everything runs inside WSL as root, so `~` is `/root`. The setup is described in section 3 of the session notes (`../../../SESSION-NOTES-for-compacted-Claude.md`). LinuxArena and Control Tower code stays inside WSL and is never copied here.

**Paths.** No script names a machine-specific folder. Python scripts take every location from `power_paths.py`, and bash scripts from `paths.sh`; the two have the same defaults. To run somewhere else, set these environment variables, or leave them unset to keep the defaults:
- `POWER_V0_HOME`, the working folder outside the repository (data, queue, config, trajectories, the synced harness, Control Tower). Default `~/power-v0`;
- `POWER_V0_DATA`, default `$POWER_V0_HOME/data`;
- `POWER_V0_CT`, default `$POWER_V0_HOME/src/control-tower`;
- `POWER_V0_EXP`, the experiment folder in the repository. It's found automatically: from this folder's location, or, in the synced copy, from the `exp-dir` file `sync.sh` writes there.

## Running things

| File | What it does |
| --- | --- |
| `power_v0.py` | The policy `power_v0:power_policy`. It covers: <ul><li>the trajectory replay;</li><li>the `dev` setup: password emptied, test database, read-only login;</li><li>the solver;</li><li>per-step scoring (`prefix_log`, `prefix_turns`);</li><li>the probe;</li><li>the end-of-run snapshot.</li></ul> Every prompt and note is defined here: `ONBOARDING`, `INCLINATIONS` (`gentle`, and `keep` for the re-recorded B), `HANDOVER` and `HANDOVER_NOTES`. Replays wait for the service to be healthy after a restart (`replay_health_gate`) |
| `launch.sh` | Runs one batch under a new label: `PURPOSE="why" launch.sh <label> tasks/<file>.txt <parallel> -p name=value ...`. It writes the exact configuration and exports the records, and it refuses a label that's already used |
| `night_queue.py` | Starts jobs from `~/power-v0/queue/jobs.tsv` in order, with a cap on environments and a deadline. **Set the deadline before each use:** write `YYYY-MM-DD HH:MM` (Chicago time) into `~/power-v0/queue/deadline`, or change `DEADLINE` in the code. The cap is in `queue/max_envs` |
| `night_stop.sh` | The hard stop: kills runs and removes containers. With `wait`, it waits until the time set in it |
| `make_hz_jobs.py` | Prints the queue lines for per-step scoring of one batch: `make_hz_jobs.py <label> --horizons 5,10 [--traj <eval>]` |
| `make_v4_hz_jobs.py` | Prints the per-step scoring queue lines for every finished v4 solver batch on this machine, coarse first (H = 10 for every run, then 20, 30, 40, 5, 15, 25, 35); skips labels already in the data folder or the queue: `python3 -I make_v4_hz_jobs.py [--horizons ...] [--labels ...]` |
| `sync.sh` | Copies this folder to `~/power-v0/harness/`, replacing files atomically, so running jobs are unaffected. Also records where the experiment folder is, in the copy's `exp-dir` file |
| `power_paths.py`, `paths.sh` | Every folder the scripts use, for Python and bash. See "Paths" above |
| `tasks/` | Task files for `--task-file`: <ul><li>`v0_tasks.txt`, the six future tasks;</li><li>`rbac_task.txt`, the trajectory task;</li><li>`one_<task>.txt`, one task each;</li><li>the probe and replay-check files</li></ul> |

## Reading results

| File | What it does |
| --- | --- |
| `export_run.py` | Writes each run's readable record into `../runs/<label>/`, with secrets redacted. Also writes each batch's `README.md` and `summary.json`, and rebuilds the table in `../runs/runs-registry.md`. Run by `launch.sh`; `--check` validates completeness |
| `extract.py` | Parses scorer output into one row per run. It also holds the bug-fix task's target tests (`BUGFIX_TARGETS`) |
| `power_horizons.py` | Power with horizons, from the exported records only: the formula in `../plans/night-plan.md` |
| `test_power_horizons.py` | 13 known-answer tests of `power_horizons.py`, with no environment |
| `compare_snapshots.py` | Diffs end-of-run machine snapshots. It's the replay check, and shows what a trajectory left behind |
| `power.py`, `make_runs_csv.py` | The older power numbers and the dashboard's data file, for the root and `pilotdev` runs |

## `old/`

Scripts retired on Nov 2, kept because the old runs were made with them:
- `run_arms.sh`, `run_traj.sh` and `run_after.sh`, replaced by `launch.sh` and the queue;
- `jobs-next-session.tsv`, the night's job list, now run.

They aren't copied into WSL.

## `vm/`: the cloud machine

How they're used is in `../plans/vm-runbook.md`. `sync.sh` doesn't copy this folder: these run from the repository.

| File | What it does |
| --- | --- |
| `vm/setup.sh` | Sets up a fresh Ubuntu 26.04 machine to run like WSL: Docker and its settings, Control Tower `699d5ca` with WSL's exact packages, `model_registry` `v1.0.1`, the images by digest, `ct.env`, and the harness. Run on the machine as root; safe to rerun |
| `vm/copy.sh` | Runs in WSL. `to <address>` sends the code (a git bundle), uv and the raw data over SSH; `venv` sends WSL's Control Tower environment if installing fails; `back` brings the records and raw data home |
| `vm/finish_v4.sh` | Runs in WSL. Nov 3, one command: copy back from Lambda, rebuild the registry, `power_horizons.py` on the v4 arms (`findings/power-horizons-v4.json`, `.txt`), the dashboard (`--config viz/run-v4.json`), the secret scan, a summary. `bash vm/finish_v4.sh [address] [key]` |
| `vm/secret_scan.py` | Scans a list of files for the environment's secret values and secret-looking patterns; prints paths and kinds only. Needs Control Tower's Python |
| `vm/compare_runs.py` | Compares two batches task by task, by check name: the machine's checks against WSL's runs |
| `vm/ct-packages.txt` | WSL's Control Tower packages, which `setup.sh` checks the machine's against |

## The gap search (Nov 2 evening)

| File | What it does |
| --- | --- |
| `make_search_jobs.py` | Prints the next round of per-step jobs. For each gap between scored horizons whose results differ, it picks the middle turn. Crashed horizons are retried up to 3 times, then the nearest other turn is used. It skips the question task |
| `search_rounds.sh` | Runs detached in WSL and appends each new round to the queue when the queue empties, stopping when no gap is left |
