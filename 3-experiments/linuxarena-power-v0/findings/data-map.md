# Data map: where every piece of data lives

*Written 2026-11-03 at about 12:00 CST and brought up to date on 2026-11-05 at about 10:00 CST, from listings of this folder and of WSL (no raw data file was opened, and nothing in WSL was changed apart from the read cache). Update it when a new kind of data appears. The results are in [results-nov3.md](results-nov3.md); the folder index is [../README.md](../README.md).*

**The short version.**
- **Readable, redacted records** of every run are in this repository under [`runs/`](../runs/runs-registry.md), one folder per batch label. They're safe to commit and push.
- **Raw data** (the `.eval` logs, machine snapshots, database and bucket dumps, saved machine states) stays in WSL under `/root/power-v0/`. It's too big for OneDrive and it holds the environment's secrets. Never copy it into the repository.
- **Computed results** are in [`findings/`](README.md), the dataset for analysis in [`analysis/`](../analysis/README.md), and the pages in [`viz/`](../viz/).

## 1. The readable records: `runs/`

183 MB in 1,138 batch folders, one per label, plus [runs/runs-registry.md](../runs/runs-registry.md) (every label with its purpose, settings and date). Written by `harness/export_run.py`; never edit them by hand, rerun the export. Code finds a run by its label, so never rename or move a batch folder.

**Inside each batch folder:**
- `README.md` and `summary.json`: the batch's purpose, exact settings, spend, and one row per run.
- `<task>/<run>/`, one run each:
  - `transcript.md`: the full record (reasoning, every tool call and its output). Known secrets are replaced by `<secret>`;
  - `prompts/` (`system.txt`, `first-user.txt`, `handover.txt`);
  - `config.json`, `meta.json`, `scores.json` (the scorer's verdict and its test-case list), `usage.csv` (tokens per turn);
  - `raw-paths.txt`: where the raw data for this run is in WSL;
  - `horizon_scores.jsonl`: only in score-and-roll-back jobs, one row per scoring point.
- `power-actions.json`, in the run's folder (and at batch level for the `traj4-*` ones): what a trajectory or run did that bears on power, turn by turn. Present for 16 of the 42 Nov 3 trajectories (the 14 triaged at 03:30–03:54, plus `traj4-minio-keep` and `traj4-minio-none`), and for `traj2-*`, `traj3-power`, `v2-before`, `v2-afterA` and `v3-afterB`.
- `labels.md`: the older hand-written version, for `traj2-control`, `traj2-power` and `traj3-power`.

**The label families** (the scheme is in [../../../CLAUDE.md](../../../CLAUDE.md), "The label scheme"):

| Family | Batches | What they are | Used by |
| --- | --- | --- | --- |
| **Nov 3 (current)** | | | |
| `traj4-<task>-<note>` | 42 | The trajectory search: 6 trajectory tasks × 7 notes. Tasks: `deployenv`, `errors`, `minio`, `rbac`, `roles`, `sharing`. Notes: `none` (the controls), `side`, `blockers`, `roadmap`, `lean`, then `keep` and `strong` in the stronger round | Pair 1 uses `traj4-sharing-none` (A) and `traj4-sharing-side` (B); pair 2 uses `traj4-minio-none` (A2) and `traj4-minio-keep` (B2) |
| `v4-before-p1..p5` | 5 | Solver runs from the initial environment state, one per task, in 5 parts (parts 1–4: 15 tasks; part 5: 12 more) | All three configs |
| `v4-afterA-p1..p5`, `v4-afterB-p1..p5` | 10 | Pair 1's solver runs after A and after B | `viz/run-v4.json`, `viz/run-v4-both.json` |
| `v4-afterA2-p1..p5`, `v4-afterB2-p1..p5` | 10 | Pair 2's solver runs after A2 and after B2 | `viz/run-v4b.json`, `viz/run-v4-both.json` |
| `nowork-v4-S0-p1..p5` | 5 | No-work runs (H = 0) from the initial environment state; parts 1–4 also served as the free check of the candidate tasks | All three configs |
| `nowork-v4-afterA-p1..p5`, `nowork-v4-afterB-p1..p5`, `nowork-v4-afterB-p5r` | 11 | Pair 1's no-work runs. `-p5r` reruns one task whose scorer crashed under load at 04:27 | `viz/run-v4.json`, `viz/run-v4-both.json` |
| `nowork-v4-afterA2-p1..p5`, `nowork-v4-afterB2-p1..p5` | 10 | Pair 2's no-work runs | `viz/run-v4b.json`, `viz/run-v4-both.json` |
| `hz-v4-<arm>-p<k>-<task>-H<h>` | 776 | Per-step scoring: the solver run's first H turns replayed into a fresh machine, then the real scorer. Every 5 turns (H = 5…50). By arm: before 200, afterA 119, afterB 99, afterA2 188, afterB2 170. `<task>` is a short name from `harness/task_names.py` | Read by `power_horizons.py` through the solver run each one replays |
| `sr-v4-<arm>-p<k>-<task>`, with `-r<N>` for a rerun or rescore | 66 | **The every-turn rescoring by score and roll back, paused at 48 of 130 runs:** one job per solver run, listed in WSL at `/root/power-v0/sr-validate/prod-jobs.tsv`, with 5 arms × 26 tasks planned (the storage question is skipped). After-arm jobs start from the trajectory's saved state. 58 folders have rows (`horizon_scores.jsonl`), covering 48 runs. The 8 without `meta.json` are jobs that failed to start, kept as records of it (`sr-v4-afterA-p1-adminusers`, `sr-v4-afterA2-p1-backup`, `sr-v4-afterA2-p5-middleware`, `sr-v4-afterB-p1-adminusers`, `sr-v4-afterB-p5-middleware`, `sr-v4-afterB2-p5-middleware`, `sr-v4-afterB2-p5-middleware-r2`, `sr-v4-before-p1-adminusers`) | `power_horizons.py --rollback-rows`; `harness/vm/sync_rollback_pages.py` |
| **Checks (never in the published numbers)** | | | |
| `restorecheck-*` | 7 | Checks of starting a job from a saved trajectory state instead of a replay ([../plans/replay-free-scope.md](../plans/replay-free-scope.md)): `save-*` save a state, `restore-*` restore it, `default-*` checks the old path is unchanged | Validation only |
| `hzcheck-sr*-*` | 10 | Score and roll back's validation jobs ([../logs/2026-11-03-score-and-rollback.md](../logs/2026-11-03-score-and-rollback.md)). `hzcheck-sr-v4-afterB-p1-backup` and `-quarantine` stopped after H = 1 (a bug, since fixed) and are kept as records of it, not as results. `-at17-api` and `-at17-cli` are the A2 tamper checks. Some other reruns are in WSL and not exported | `power_horizons.py` reads their rows only with `--rollback-rows --include-check-rows` |
| `hzcheck-dd-*`, `hzcheck-fx-*` | 4 | More score-and-roll-back check jobs, Nov 3 (their lists are `jobs-dd.tsv` and `jobs-fx.tsv` in `sr-validate/`) | Same |
| `hzcheck-bench-*` | 13 so far | The efficiency tests of Nov 5 ([../plans/scoring-efficiency-tests.md](../plans/scoring-efficiency-tests.md)). More may land | Same |
| **Nov 2 (superseded)** | | | |
| `traj2-control`, `traj2-power`, `traj3-power` | 3 | The Nov 2 trajectories on the RBAC task (A, the first B, B with the `keep` note) | [results-night-1.md](results-night-1.md) |
| `v2-before`, `v2-afterA`, `v3-afterB` | 3 | Nov 2 solver runs on the 6 original tasks | Same |
| `nowork-v2-S0`, `nowork-v2-afterA`, `nowork-v2-afterB`, `nowork-v3-afterB` | 4 | Nov 2 no-work runs | Same |
| `hz-v2-*`, `hz-v3-*` | 132 | Nov 2 per-step scoring, including the gap search. 39 of these are left out of every computation by [excluded-labels.txt](excluded-labels.txt) | Same |
| `hzcheck-dash`, `hzcheck-fav`, `probe-v2` | 3 | Nov 2 checks | Same |
| **Old runs (before Nov 2)** | | | |
| `pilot-*`, `check0*`, `check-dev*`, `final-probe-*`, `nowork-dev-*`, `pilotdev-*`, `prep-traj-nowork`, `replaycheck-*`, `traj-gentle`, `traj-neutral` | 24 | The root-solver pilot, and `dev` runs made while the database superuser password was still in `dev`'s environment. Kept as data, never in the new numbers | [../pilot-results/](../pilot-results/index.csv), [ab-trajectories.md](ab-trajectories.md) |

## 2. Which batches each results page uses

| Config | Page | Before | Arms after a trajectory |
| --- | --- | --- | --- |
| [viz/run-v4-both.json](../viz/run-v4-both.json) | [viz/power-dashboard-v4-both.html](../viz/power-dashboard-v4-both.html), **the main page,** published at https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22 | `v4-before-p1..p5`, `nowork-v4-S0-p1..p5` | A1 and B1 as pair 1's A and B below, A2 and B2 as pair 2's |
| [viz/run-v4.json](../viz/run-v4.json) | [viz/power-dashboard-v4.html](../viz/power-dashboard-v4.html), pair 1 alone; no link of its own now | the same | A: `v4-afterA-p1..p5`, `nowork-v4-afterA-p1..p5`. B: `v4-afterB-p1..p5`, `nowork-v4-afterB-p1..p5` and `-p5r` |
| [viz/run-v4b.json](../viz/run-v4b.json) | [viz/power-dashboard-v4b.html](../viz/power-dashboard-v4b.html), pair 2 alone, published at https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh | the same | A: `v4-afterA2-p1..p5`, `nowork-v4-afterA2-p1..p5`. B: `v4-afterB2-p1..p5`, `nowork-v4-afterB2-p1..p5` |

All three list the same 27 tasks, set `"reward": "last-scored"`, `"strict": true` and `"rollback_rows": true`, and name the trajectories and B's hand-over note (`use`). The per-step batches aren't listed: `power_horizons.py` finds every `hz-*` run whose source log is one of the arm's solver runs, and with `--rollback-rows` every `sr-*` job the same way. `tools/power.sh pages` (`harness/vm/sync_rollback_pages.py`) rebuilds the tables and all three pages, using a task's `sr-*` rows only once all that page's arms have them. `harness/vm/finish_v4.sh` does one config, without that rule.

## 3. Computed results: `findings/` and `analysis/`

[README.md](README.md) lists every file in `findings/` by question. The ones code reads or writes:

| File | What it is | Status |
| --- | --- | --- |
| [power-horizons-v4.json](power-horizons-v4.json), [.txt](power-horizons-v4.txt) | Pair 1's output of `power_horizons.py`: per-task test-case lists, free passes, scored horizons, the POWER_H curves (H = 0…80), gains | Current: rewritten Nov 3 12:05 under `last-scored`, with the correction, every 5 turns. `tools/power.sh pages` rewrites it |
| [v4b/power-horizons-v4.json](v4b/power-horizons-v4.json), [.txt](v4b/power-horizons-v4.txt) | The same for pair 2 | Current: Nov 3 12:14, likewise |
| `both/` | The same for the combined page | Doesn't exist until `tools/power.sh pages` first runs |
| [score-corrections.json](score-corrections.json) | Scorer verdicts replaced by hand, with the evidence: one entry, B2's storage-question answer (Arya, Nov 3). Read by `power_horizons.py` | Current |
| [excluded-labels.txt](excluded-labels.txt) | 39 Nov 2 per-step labels left out of every computation (Arya, Nov 3 ~00:40); read by `power_horizons.py` | Current. Affects only the Nov 2 numbers |
| [solver-power-use/](solver-power-use/afterB.json) | One file per after arm (`afterA`, `afterB`, `afterA2`, `afterB2`): for each of the 27 solver runs, whether the solver used access beyond `dev`'s, what it was, the steps, whether the task needed it, and whether it helped or hurt. Written by Sonnet triage agents, 09:15–10:05; read by the pages | Current |
| [old/](old/power-horizons-partial.json) | The Nov 2 computations: `power-horizons-partial.json` ([results-night-1.md](results-night-1.md)'s numbers), `-current`, `-first-pass`, `-A-partial` | Historical |

**`analysis/`** ([README](../analysis/README.md)) is built from the records by [analysis/build_dataset.py](../analysis/build_dataset.py), or `tools/power.sh dataset`:
- `data/`: `runs.csv` (135 solver runs), `turns.csv` (4,552 model turns), `testcases.json`, `curves.json` (on turns and on tool calls, with and without the every-turn rows), `checks.json`, `summary.md`, and `task_power.json` (the 27 per-task reports' structured results);
- `digests/<task>/<arm>.md`: one short digest per solver run, and `_trajectories/`;
- `trajectories/`: the scripts and counts behind [nov5-what-power-seeking-looks-like.md](nov5-what-power-seeking-looks-like.md);
- `causal/`: the scripts and printed output behind [nov5-causal-factors.md](nov5-causal-factors.md).

Rerun `tools/power.sh dataset --refresh` when more every-turn rows land. Text in it comes only from the redacted `transcript.md`.

## 4. The raw data in WSL: `/root/power-v0/`

Read it only from WSL (`wsl.exe -d Ubuntu -u root -- bash -s`). Most of it holds the environment's secrets, so never print file contents, and never copy it to Windows or the repository. Sizes as of Nov 5, about 09:40.

| Path | Size | What it is |
| --- | --- | --- |
| `data/evals/<label>/` | 1.5 GB | The Inspect `.eval` logs, the source of every record: 1,177 label folders, 1,165 `.eval` files. Beside them, per label: `<label>.console.txt` (the launch's console output) and `<label>.export.txt` (the export's output). **Hold secrets** |
| `data/runs/<label>/<task>/<run>/` | 6.0 GB | Per-run raw extras, 1,150 label folders: `snapshot.txt` (the end-of-run machine snapshot), `db_s3.txt` (database and bucket dumps), `handover.txt`, `meta.json`. **Hold secrets** |
| `data/states/<trajectory>/` | 1.9 GB | **Saved end states,** for starting jobs without a replay, about 0.5 GB each: `traj4-sharing-none`, `traj4-sharing-side`, `traj4-minio-none`, `traj4-minio-keep` (the four trajectories of the two pairs). Each has `files.tar` (the app container's changed files), `pg.tar` (the Postgres data folder), `s3/` (both buckets), `manifest.json`, `fingerprint.tsv` and three `.nul` path lists. A state must be restored within about a day of being saved, so `resume_queue.py` and `refresh_states.py` re-save old ones. **Hold secrets** |
| `data/rollback/<label>/` | 6.4 GB | Score and roll back's working copies while a job runs (the host copy of the container's changed files, database dumps, bucket mirrors), owned by that session. The 11 folders here now look left over from jobs stopped on Nov 3 (my reading of their names against its log). **Hold secrets** |
| `data/checks/`, `data/dashboard/`, `data/transcripts/`, `data/index.csv`, `data/spend-AB.txt` | under 0.5 MB | Nov 1–2 leftovers: the `prep-AB` check, the old dashboard's data files, the two Nov 1 transcripts, the old run index and spend |
| `trajectory/*.eval` | 389 MB | The 48 trajectory logs every after-arm job replays: `run3`, `traj-gentle`, `traj-neutral`, `traj2-control`, `traj2-power`, `traj3-power` and the 42 `traj4-*`. **Hold secrets** |
| `lambda-nov3/` | 4.4 MB | What came home from the Lambda machine (03:15–08:30): `queue/` (`queue.log`, `status.tsv`, `jobs.tsv`, the load governor `governor.sh` and its log, the per-step feeder, `reorder.py`, `max_envs`, `deadline`, per-job `logs/`), `setup.log`, and `tmp/` (the job lists `*.tsv`, `hz.py`, `queue_after.py`, `*.err`, the machine's package list). Checked: no secrets |
| `queue/` | 2.2 MB | WSL's live queue (`jobs.tsv`, `status.tsv`, `queue.log`, `logs/`, `max_envs`, `deadline`, `deadline.before-drain`), dated `jobs.tsv.before-*` backups, and `archive-2026-11-03-trajectories/` |
| `queue-nov2-archive-0300/` | 0.8 MB | The Nov 2 queue, archived at 03:00 on Nov 3 |
| `sr-validate/` | 0.4 MB | Score and roll back's job lists and runner scripts (validation and production; `prod-jobs.tsv`, `status.log`, `watch-seen.json`), owned by that session |
| `restorecheck/` | 28 KB | The replay-free checks' runner and outputs |
| `bench/` | 3.1 GB | The Nov 5 efficiency tests' working data (`jobs/`, `logs/`, `samples/`, `states/`, `projects/`, `work/`), owned by the score-and-roll-back session. **May hold secrets** |
| `config/` | 8 MB | `ct.env` and Control Tower settings. **Holds secrets** |
| `src/control-tower/`, `src/linuxarena-paper/` | 1.1 GB, 272 MB | Control Tower with the `model_registry` environment; the LinuxArena paper's checkout. Never copy them to Windows |
| `src/envs-survey/`, `src/envs-survey-data/` | 1.4 GB, 13 MB | Clones of the other LinuxArena environments, and the published per-model data, read for [nov5-linuxarena-environments.md](nov5-linuxarena-environments.md). Never copy them to Windows |
| `harness/` | 1.8 MB | The synced copy of `harness/` (`sync.sh`); edit the repository's copy instead |
| `cache/` | 15 MB | The optional read cache of `runs/` (`records.sqlite`, `tools/record_cache.py`): compressed copies of the redacted record files, checked by size and modification time. Safe to delete |
| `tmp-analysis/` | 205 MB | `analysis/build_dataset.py`'s cache: a copy of `runs/` without `config.json` and the long prompts, plus structure files read from the raw logs. Safe to delete |
| `backup-power-actions/` | 40 KB | A backup of the Nov 2 `power-actions.json` files, from 00:47 on Nov 3 |
| `tmp-ph-check/`, `tmp-sr-old/` | about 1 MB | Temporary comparison folders from the score-and-roll-back work |
| `analysis/`, `states/` | empty | Unused |

`data/` in all is about 15.8 GB. A run's `raw-paths.txt` in `runs/` names its raw files.

## 5. Other data in the repository

- [../pilot-results/](../pilot-results/index.csv): the old pilot's data files (Nov 1).
- [../viz/](../viz/): the pages and the data files they read (`run-v4*.json`, `task-sections.json`, `run-stories-v4.json`, `nov3-prompt-power-extra.tsv`). See [../README.md](../README.md).
- `../harness/tasks/`: the task files each batch was launched with (`v4_tasks_p1..p5.txt`, `v4_free_check_p1..p5.txt`, `traj_*.txt`, `one_*.txt`).
- Not in the repository: the `.eval` logs anywhere (`.gitignore`), and `3-experiments/linuxarena-pilot/transcripts/` and `logs/`.
