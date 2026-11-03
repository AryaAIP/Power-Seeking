# Data map: where every piece of data lives

*Written 2026-11-03 at about 12:00 CST, from listings of this folder and of WSL (counts and sizes measured 11:35–12:00; no raw data file was opened, and nothing in WSL was changed). Update it when a new kind of data appears. The results are in [results-nov3.md](results-nov3.md); the folder index is [../README.md](../README.md).*

**The short version.**
- **Readable, redacted records** of every run are in this repository under [`runs/`](../runs/runs-registry.md), one folder per batch label. They're safe to commit and push.
- **Raw data** (the `.eval` logs, machine snapshots, database and bucket dumps, saved machine states) stays in WSL under `/root/power-v0/`. It's too big for OneDrive and it holds the environment's secrets. Never copy it into the repository.
- **Computed results** are in [`findings/`](.), and the pages built from them in [`viz/`](../viz/).

## 1. The readable records: `runs/`

119 MB in 1,050 batch folders, one per label, plus [runs/runs-registry.md](../runs/runs-registry.md) (every label with its purpose, settings and date). Written by `harness/export_run.py`; never edit them by hand, rerun the export.

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
| `v4-before-p1..p5` | 5 | Solver runs from the initial environment state, one per task, in 5 parts (parts 1–4: 15 tasks; part 5: 12 more) | Both configs |
| `v4-afterA-p1..p5`, `v4-afterB-p1..p5` | 10 | Pair 1's solver runs after A and after B | `viz/run-v4.json` |
| `v4-afterA2-p1..p5`, `v4-afterB2-p1..p5` | 10 | Pair 2's solver runs after A2 and after B2 | `viz/run-v4b.json` |
| `nowork-v4-S0-p1..p5` | 5 | No-work runs (H = 0) from the initial environment state; parts 1–4 also served as the free check of the candidate tasks | Both configs |
| `nowork-v4-afterA-p1..p5`, `nowork-v4-afterB-p1..p5`, `nowork-v4-afterB-p5r` | 11 | Pair 1's no-work runs. `-p5r` reruns one task whose scorer crashed under load at 04:27 | `viz/run-v4.json` |
| `nowork-v4-afterA2-p1..p5`, `nowork-v4-afterB2-p1..p5` | 10 | Pair 2's no-work runs | `viz/run-v4b.json` |
| `hz-v4-<arm>-p<k>-<task>-H<h>` | 776 | Per-step scoring: the solver run's first H turns replayed into a fresh machine, then the real scorer. Every 5 turns (H = 5…50). By arm: before 200, afterA 119, afterB 99, afterA2 188, afterB2 170. `<task>` is a short name from `harness/task_names.py` | Read by `power_horizons.py` through the solver run each one replays |
| `restorecheck-*` | 6 | Checks of starting a job from a saved trajectory state instead of a replay ([../plans/replay-free-scope.md](../plans/replay-free-scope.md)): `save-*` save a state, `restore-*` restore it, `default-*` checks the old path is unchanged | Validation only |
| `sr-v4-<arm>-p<k>-<task>` | 0 yet | **Coming:** the every-turn rescoring by score and roll back, one job per solver run: 130 jobs (5 arms × 26 tasks; the storage question is skipped), listed in WSL at `/root/power-v0/sr-validate/prod-jobs.tsv`. After-arm jobs start from the trajectory's saved state | Will be read by `power_horizons.py --rollback-rows` |
| `hzcheck-sr-*` | 6 | Score and roll back's validation jobs ([../logs/2026-11-03-score-and-rollback.md](../logs/2026-11-03-score-and-rollback.md)). `hzcheck-sr-v4-afterB-p1-backup` and `-quarantine` stopped after H = 1 (a bug, since fixed) and are kept as records of it, not as results. The later reruns (`hzcheck-sr2-*` and on) are in WSL and not yet exported | Never in the published numbers (`power_horizons.py` reads them only with `--rollback-rows --include-check-rows`) |
| **Nov 2 (superseded)** | | | |
| `traj2-control`, `traj2-power`, `traj3-power` | 3 | The Nov 2 trajectories on the RBAC task (A, the first B, B with the `keep` note) | [results-night-1.md](results-night-1.md) |
| `v2-before`, `v2-afterA`, `v3-afterB` | 3 | Nov 2 solver runs on the 6 original tasks | Same |
| `nowork-v2-S0`, `nowork-v2-afterA`, `nowork-v2-afterB`, `nowork-v3-afterB` | 4 | Nov 2 no-work runs | Same |
| `hz-v2-*`, `hz-v3-*` | 132 | Nov 2 per-step scoring, including the gap search. 39 of these are left out of every computation by [excluded-labels.txt](excluded-labels.txt) | Same |
| `hzcheck-dash`, `hzcheck-fav`, `probe-v2` | 3 | Nov 2 checks | Same |
| **Old runs (before Nov 2)** | | | |
| `pilot-*`, `check0*`, `check-dev*`, `final-probe-*`, `nowork-dev-*`, `pilotdev-*`, `prep-traj-nowork`, `replaycheck-*`, `traj-gentle`, `traj-neutral` | 24 | The root-solver pilot, and `dev` runs made while the database superuser password was still in `dev`'s environment. Kept as data, never in the new numbers | [../pilot-results/](../pilot-results/index.csv), [ab-trajectories.md](ab-trajectories.md) |

**Four trajectory transcripts are not to be committed until they're re-redacted:** `traj4-errors-blockers`, `traj4-errors-lean`, `traj4-errors-roadmap` (storage access keys made at run time) and `traj4-minio-strong` (a private key block). A redaction fix in `harness/export_run.py` and a re-export are in progress (log, 11:15).

## 2. Which batches each results page uses

| Config | Page | Before | After A | After B |
| --- | --- | --- | --- | --- |
| [viz/run-v4.json](../viz/run-v4.json) | [viz/power-dashboard-v4.html](../viz/power-dashboard-v4.html), published at https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22 | `v4-before-p1..p5`, `nowork-v4-S0-p1..p5` | `v4-afterA-p1..p5`, `nowork-v4-afterA-p1..p5` | `v4-afterB-p1..p5`, `nowork-v4-afterB-p1..p5` and `-p5r` |
| [viz/run-v4b.json](../viz/run-v4b.json) | [viz/power-dashboard-v4b.html](../viz/power-dashboard-v4b.html), published at https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh | the same | `v4-afterA2-p1..p5`, `nowork-v4-afterA2-p1..p5` | `v4-afterB2-p1..p5`, `nowork-v4-afterB2-p1..p5` |

Both configs list the same 27 tasks, set `"reward": "last-scored"` and `"strict": true`, and name the trajectories and B's hand-over note (`use`). The per-step batches aren't listed: `power_horizons.py` finds every `hz-*` run whose source log is one of the arm's solver runs. `harness/vm/finish_v4.sh` reads a config's arms (`FINISH_CONFIG`) to rebuild the registry, the power table and the page.

## 3. Computed results: `findings/`

| File | What it is | Status |
| --- | --- | --- |
| [results-nov3.md](results-nov3.md) | The Nov 3 results, written up | Current |
| [power-horizons-v4.json](power-horizons-v4.json), [.txt](power-horizons-v4.txt) | Pair 1's output of `power_horizons.py`: per-task test-case lists, free passes, scored horizons, the POWER_H curves (H = 0…80), gains | Written 08:38 under the **first-pass** rule; `finish_v4.sh` rewrites it under `last-scored` on its next run. The current numbers are in results-nov3.md |
| [v4b/power-horizons-v4.json](v4b/power-horizons-v4.json), [.txt](v4b/power-horizons-v4.txt) | The same for pair 2 | Same (08:40, first-pass) |
| [score-corrections.json](score-corrections.json) | Scorer verdicts replaced by hand, with the evidence: one entry, B2's storage-question answer (Arya, Nov 3). Read by `power_horizons.py` | Current |
| [excluded-labels.txt](excluded-labels.txt) | 39 Nov 2 per-step labels left out of every computation (Arya, Nov 3 ~00:40); read by `power_horizons.py` | Current. Affects only the Nov 2 numbers |
| [solver-power-use/](solver-power-use/afterB.json) | One file per after arm (`afterA`, `afterB`, `afterA2`, `afterB2`): for each of the 27 solver runs, whether the solver used access beyond `dev`'s, what it was, the steps, whether the task needed it, and whether it helped or hurt. Written by Sonnet triage agents, 09:15–10:05 | Current |
| [results-night-1.md](results-night-1.md), [power-horizons-partial.json](power-horizons-partial.json), [power-horizons-current.json](power-horizons-current.json), [power-horizons-first-pass.json](power-horizons-first-pass.json), [power-horizons-A-partial.json](power-horizons-A-partial.json) | The Nov 2 results (6 tasks, `traj2`/`traj3` trajectories) and their computations | Historical |
| [superuser-audit.md](superuser-audit.md), [ab-trajectories.md](ab-trajectories.md), [bottlenecks.md](bottlenecks.md) | Earlier audits and findings | See [../README.md](../README.md) |

## 4. The raw data in WSL: `/root/power-v0/`

Read it only from WSL (`wsl.exe -d Ubuntu -u root -- bash -s`). Most of it holds the environment's secrets, so never print file contents, and never copy it to Windows or the repository.

| Path | Size | What it is |
| --- | --- | --- |
| `data/evals/<label>/` | 1.5 GB | The Inspect `.eval` logs, the source of every record: 1,074 label folders, 1,062 `.eval` files. Beside them, per label: `<label>.console.txt` (1,074, the launch's console output) and `<label>.export.txt` (1,045, the export's output). **Hold secrets** |
| `data/runs/<label>/<task>/<run>/` | 5.8 GB | Per-run raw extras, 1,056 label folders: `snapshot.txt` (the end-of-run machine snapshot), `db_s3.txt` (database and bucket dumps), `handover.txt`, `meta.json`. **Hold secrets** |
| `data/states/<trajectory>/` | 1.9 GB | Saved end states, for starting jobs without a replay, about 0.5 GB each: `traj4-sharing-none`, `traj4-sharing-side`, `traj4-minio-none`, `traj4-minio-keep` (the four trajectories of the two pairs). Each has `files.tar` (the app container's changed files), `pg.tar` (the Postgres data folder), `s3/` (both buckets), `manifest.json`, `fingerprint.tsv` and three `.nul` path lists. **Hold secrets** |
| `data/rollback/<label>/` | empty at 12:00 (3.3 GB at 11:40) | Score and roll back's working copies while a job runs (the host copy of the container's changed files, database dumps, bucket mirrors), owned by that session. Its validation jobs' copies were cleared at about 11:55 |
| `data/checks/`, `data/dashboard/`, `data/transcripts/`, `data/index.csv`, `data/spend-AB.txt` | under 0.5 MB | Nov 1–2 leftovers: the `prep-AB` check, the old dashboard's data files, the two Nov 1 transcripts, the old run index and spend |
| `trajectory/*.eval` | 389 MB | The 48 trajectory logs every after-arm job replays: `run3`, `traj-gentle`, `traj-neutral`, `traj2-control`, `traj2-power`, `traj3-power` and the 42 `traj4-*`. **Hold secrets** |
| `lambda-nov3/` | 4.4 MB | What came home from the Lambda machine (03:15–08:30): `queue/` (`queue.log`, `status.tsv`, `jobs.tsv`, the load governor `governor.sh` and its log, the per-step feeder, `reorder.py`, `max_envs`, `deadline`, per-job `logs/`), `setup.log`, and `tmp/` (the job lists `*.tsv`, `hz.py`, `queue_after.py`, `*.err`, the machine's package list). Checked: no secrets |
| `queue/` | 0.1 MB | WSL's live queue (`jobs.tsv`, `status.tsv`, `queue.log`, `logs/`, `max_envs`, `deadline`) |
| `queue-nov2-archive-0300/` | 0.8 MB | The Nov 2 queue, archived at 03:00 on Nov 3 |
| `sr-validate/` | 0.3 MB | Score and roll back's job lists and runner scripts (validation and production), owned by that session |
| `restorecheck/` | 28 KB | The replay-free checks' runner and outputs |
| `config/` | 7.3 MB | `ct.env` and Control Tower settings. **Holds secrets** |
| `src/` | 1.3 GB | Control Tower and the LinuxArena environment checkout. Never copy it to Windows |
| `harness/` | 1.1 MB | The synced copy of `harness/` (`sync.sh`); edit the repository's copy instead |
| `backup-power-actions/` | 40 KB | A backup of the Nov 2 `power-actions.json` files, from 00:47 on Nov 3 |
| `tmp-ph-check/`, `tmp-sr-old/` | about 1 MB | Temporary comparison folders from the score-and-roll-back work |
| `analysis/`, `states/` | empty | Unused |

`data/` in all is 7.3 GB at 12:00. A run's `raw-paths.txt` in `runs/` names its raw files.

## 5. Other data in the repository

- [../pilot-results/](../pilot-results/index.csv): the old pilot's data files (Nov 1).
- [../viz/](../viz/): the pages and the data files they read (`run-v4*.json`, `task-sections.json`, `run-stories-v4.json`, `nov3-prompt-power-extra.tsv`). See [../README.md](../README.md).
- `../harness/tasks/`: the task files each batch was launched with (`v4_tasks_p1..p5.txt`, `v4_free_check_p1..p5.txt`, `traj_*.txt`, `one_*.txt`).
- Not in the repository: the `.eval` logs anywhere (`.gitignore`), and `3-experiments/linuxarena-pilot/transcripts/` and `logs/`.
