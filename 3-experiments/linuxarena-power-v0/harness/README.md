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
| `power_v0.py` | The policy `power_v0:power_policy`. It covers: <ul><li>the trajectory replay;</li><li>the `dev` setup: password emptied, test database, read-only login;</li><li>the solver;</li><li>per-step scoring (`prefix_log`, `prefix_turns`);</li><li>saving a trajectory's end state and starting jobs from it instead of replaying (`save_state`, `restore_state`, off by default);</li><li>score and roll back: one job replays a whole solver run and scores it partway at `score_every`/`score_at`, restoring the machine after each score (`rollback.py`; off by default; `score_min_timeout` sets a floor on command time limits while scoring);</li><li>the probe;</li><li>the end-of-run snapshot.</li></ul> Every prompt and note is defined here: `ONBOARDING`, `INCLINATIONS` (`gentle`, and `keep` for the re-recorded B), `HANDOVER` and `HANDOVER_NOTES`. Replays wait for the service to be healthy after a restart (`replay_health_gate`) |
| `launch.sh` | Runs one batch under a new label: `PURPOSE="why" launch.sh <label> tasks/<file>.txt <parallel> -p name=value ...`. It writes the exact configuration and exports the records, and it refuses a label that's already used |
| `night_queue.py` | Starts jobs from `~/power-v0/queue/jobs.tsv` in order, with a cap on environments and a deadline. **Set the deadline before each use:** write `YYYY-MM-DD HH:MM` (Chicago time) into `~/power-v0/queue/deadline`, or change `DEADLINE` in the code. The cap is in `queue/max_envs` |
| `night_stop.sh` | The hard stop: kills runs and removes containers. With `wait`, it waits until the time set in it |
| `make_hz_jobs.py` | Prints the queue lines for per-step scoring of one batch: `make_hz_jobs.py <label> --horizons 5,10 [--traj <eval>]` |
| `refresh_states.py` | Runs beside `night_queue.py` and keeps saved trajectory states fresh: a state must be restored within about a day of its save (the backup worker's one-day rule, 24 h tokens). When one that pending queue lines restore is older than `--max-age` hours (default 18), it queues a re-save job (`restorecheck-resave-<state>-rN`) before the first pending line, and once that save is complete points the pending lines at the new state. Log: `queue/refresh_states.log` |
| `make_v4_jobs.py` | Prints one machine's queue lines for a stage of the Nov 3 run (`start`, `before`, `after A B [notes]`). With `--restore-state`, the after stage's jobs restore each trajectory's saved state instead of replaying it; without it the output is as before |
| `make_v4_hz_jobs.py` | Prints the per-step scoring queue lines for every finished v4 solver batch on this machine, coarse first (H = 10 for every run, then 20, 30, 40, 5, 15, 25, 35); skips labels already in the data folder or the queue: `python3 -I make_v4_hz_jobs.py [--horizons ...] [--labels ...]`. Options, off by default: `--restore-state` (after batches start from the saved trajectory state); `--score-every N` / `--score-at H1,H2` (score and roll back: one job per run, labelled `<prefix>-<label>-<task>`, question tasks skipped); `--label-prefix` (default `hz`) |
| `sync.sh` | Copies this folder to `~/power-v0/harness/`, replacing files atomically, so running jobs are unaffected. Also records where the experiment folder is, in the copy's `exp-dir` file |
| `power_paths.py`, `paths.sh` | Every folder the scripts use, for Python and bash. See "Paths" above |
| `tasks/` | Task files for `--task-file`: <ul><li>`v0_tasks.txt`, the six future tasks;</li><li>`rbac_task.txt`, the trajectory task;</li><li>`one_<task>.txt`, one task each;</li><li>the probe and replay-check files</li></ul> |

## Reading results

| File | What it does |
| --- | --- |
| `export_run.py` | Writes each run's readable record into `../runs/<label>/`, with secrets redacted. Also writes each batch's `README.md` and `summary.json`, and rebuilds the table in `../runs/runs-registry.md`. A score-and-roll-back run also gets `horizon_scores.jsonl`, one row per scoring point, each score shaped like `scores.json`. Run by `launch.sh`; `--check` validates completeness |
| `test_export_redact.py` | 25 known-answer tests of `export_run.py`'s `redact()`, on fake values: the secrets it finds by pattern (access key ids, secret keys after their labels, private key blocks, API keys, GitHub tokens), and code that only names a secret, which it leaves alone. Needs Control Tower's Python, since `export_run.py` imports `inspect_ai` |
| `extract.py` | Parses scorer output into one row per run. It also holds the bug-fix task's target tests (`BUGFIX_TARGETS`) |
| `power_horizons.py` | Power with horizons, from the exported records only: the formula in `../plans/night-plan.md`. It reads the per-step records. With `--rollback-rows` (off by default, until both arms of a pair are rescored the same way) it also reads score and roll back's `horizon_scores.jsonl`: a row replaces a per-step record at the same H, and counts only up to the first restore that wasn't exact. Rows from check labels (`hzcheck-*`) also need `--include-check-rows` |
| `test_power_horizons.py` | 20 known-answer tests of `power_horizons.py`, with no environment |
| `rollback.py` | Score and roll back, run on the host: `save_point` before each scoring point, `restore_point` after it, which undoes only what scoring changed and then compares a state summary. Files go back from an incrementally updated host copy of the app container's upper folder, or from the image's layers. Changed tables are reloaded in place; the Postgres cluster is swapped back only if the schema, roles or databases changed. Changed buckets are mirrored back, processes scoring started are killed, and the service is restarted only if scoring replaced it. See [../plans/score-and-rollback-scope.md](../plans/score-and-rollback-scope.md) |
| `test_rollback.py` | Known-answer tests of `rollback.py`, with no environment: the scoring points, the database plan, and the file undo on a real overlay mount in WSL (needs root). With `--logs` (Control Tower's Python), it also checks the turn grouping against two stored solver runs |
| `compare_sr.py` | Compares a score-and-roll-back job's per-point scores with the per-step records at the same H (the check list in order, and the verdict), and its end score with the run's own. Also lists every restore whose state check failed: `python3 -I compare_sr.py LABEL ... [--json out]` |
| `state_store.py` | Saves a stack's state once (the app container's changed files, the Postgres data folder, the two buckets) and restores it into fresh stacks, for `power_v0.py`'s `save_state` and `restore_state` (off by default). `rollback.py` reuses its Postgres swap (`swap_pg`) and service restart (`restart_service`). See [../plans/replay-free-scope.md](../plans/replay-free-scope.md) |
| `env_fingerprint.py` | Fingerprints a running stack (changed files, Postgres, buckets, processes, the service, iptables) and compares two fingerprints, with no secret values. Used by `restore_state` to check each restore |
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
