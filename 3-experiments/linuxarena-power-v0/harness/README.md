# Harness

The code for LinuxArena power v0. **This folder is the one copy to edit.** `sync.sh` copies it into WSL at `/root/power-v0/harness/`, where it runs, and checks the hashes. Everything runs inside WSL as root. The setup is described in section 3 of the session notes (`../../../SESSION-NOTES-for-compacted-Claude.md`). LinuxArena and Control Tower code stays inside WSL and is never copied here.

## Running things

| File | What it does |
| --- | --- |
| `power_v0.py` | The policy `power_v0:power_policy`. It covers: <ul><li>the trajectory replay;</li><li>the `dev` setup: password emptied, test database, read-only login;</li><li>the solver;</li><li>per-step scoring (`prefix_log`, `prefix_turns`);</li><li>the probe;</li><li>the end-of-run snapshot.</li></ul> Every prompt and note is defined here: `ONBOARDING`, `INCLINATIONS` (`gentle`, and `keep` for the re-recorded B), `HANDOVER` and `HANDOVER_NOTES`. Replays wait for the service to be healthy after a restart (`replay_health_gate`) |
| `launch.sh` | Runs one batch under a new label: `PURPOSE="why" launch.sh <label> tasks/<file>.txt <parallel> -p name=value ...`. It writes the exact configuration and exports the records, and it refuses a label that's already used |
| `night_queue.py` | Starts jobs from `/root/power-v0/queue/jobs.tsv` in order, with a cap on environments and a deadline. **Set `DEADLINE` before each use** |
| `night_stop.sh` | The hard stop: kills runs and removes containers. With `wait`, it waits until the time set in it |
| `make_hz_jobs.py` | Prints the queue lines for per-step scoring of one batch: `make_hz_jobs.py <label> --horizons 5,10 [--traj <eval>]` |
| `sync.sh` | Copies this folder into WSL, replacing files atomically, so running jobs are unaffected |
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

## The gap search (Nov 2 evening)

| File | What it does |
| --- | --- |
| `make_search_jobs.py` | Prints the next round of per-step jobs. For each gap between scored horizons whose results differ, it picks the middle turn. Crashed horizons are retried up to 3 times, then the nearest other turn is used. It skips the question task |
| `search_rounds.sh` | Runs detached in WSL and appends each new round to the queue when the queue empties, stopping when no gap is left |
