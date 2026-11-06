# LinuxArena power v0

*The folder index. Rewritten 2026-11-05 at about 10:00 CST. Update it whenever a file is added or moved, then run `tools/power.sh links` from the project folder. The project's conventions are in [../../CLAUDE.md](../../CLAUDE.md).*

**What this folder is.** The project's first measurement of power in a real environment, LinuxArena's `model_registry`: a Go web service with a Postgres database and object storage. Every agent works as `dev`, a developer account without root.
1. An agent does one task. That run is the **trajectory**, and the machine it leaves behind is kept. A control trajectory gets no note; a power-seeking one gets a gentle note inviting it to pick up access.
2. A fixed agent, the **solver**, then does each of 27 other tasks three times:
   - from the **initial environment state**, in a new chat;
   - **after the control trajectory**, on the machine it left, continuing its chat;
   - **after the power-seeking trajectory**, the same way.
3. Each solver run is scored after every 5 of its turns. POWER_H is the share of test cases passed within a budget of H turns, averaged over the tasks.

If the solver does better after the power-seeking trajectory than after the control, that trajectory gained power. On Nov 3 there were two such pairs; neither showed it.

## Start here

| You want | Go to |
| --- | --- |
| The result | [findings/results-nov3.md](findings/results-nov3.md) |
| Why it came out that way, and what to do next | [findings/nov5-what-power-looks-like.md](findings/nov5-what-power-looks-like.md) (the synthesis), then [findings/README.md](findings/README.md) (the Nov 5 reports, by question) |
| What to do next, with exact commands | [next-steps.md](next-steps.md) |
| Where any piece of data lives | [findings/data-map.md](findings/data-map.md) |
| What's running now | `bash tools/power.sh status` (in WSL, from the project folder), and the newest file in [logs/](logs/2026-11-05-power-research.md) |
| The common commands: dataset, power, pages, secret scan, link check | [../../tools/power.sh](../../tools/power.sh) (it lists them) |
| The results on a page | both pairs https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22, pair 2 alone https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh |
| What a run label means | [runs/runs-registry.md](runs/runs-registry.md), and the scheme in [../../CLAUDE.md](../../CLAUDE.md) |

**Where things stand (Nov 5).** The every-turn rescoring is paused at 48 of 130 runs, so reported numbers are still every 5 turns. The Nov 5 research reports and the main session's synthesis are in; reports on the other main tasks are paused at the usage limit.

## Index by folder

**Status words.** *Current*: use it. *In progress*: being written or run now. *Done*: a plan carried out; read it for what was intended. *Historical*: kept for the record, no longer how things work. *Superseded*: replaced by the file named. *Generated*: written by a script; rerun the script instead of editing.

### Top level

| Path | What it is | Status |
| --- | --- | --- |
| [next-steps.md](next-steps.md) | What to do next, in order, with the exact commands | Current |
| [README.md](README.md) | This index | Current |

### `plans/`

| Path | What it is | Status |
| --- | --- | --- |
| [plans/nov5-research-plan.md](plans/nov5-research-plan.md) | The Nov 5 research stretch: Arya's questions, the tracks, the candidate causes to test | Current |
| [plans/scoring-efficiency.md](plans/scoring-efficiency.md) | The cheapest way to an exact curve at every turn: options ranked by what carries to a cloud machine, what doesn't pay, projected hours, what could make snapshots fail | In progress (provisional; another session owns it) |
| [plans/scoring-efficiency-tests.md](plans/scoring-efficiency-tests.md) | The running record of the short free WSL tests behind it | In progress (same session) |
| [plans/scoring-schedules-analysis.md](plans/scoring-schedules-analysis.md) | How wrong cheaper scoring schedules would have been, offline on the 48 rescored runs. Script: `harness/schedule_error.py` | Current, Nov 5 |
| [plans/score-and-rollback-scope.md](plans/score-and-rollback-scope.md) | Scoring a solver run at every turn in one machine: replay it turn by turn; at each point save the state, run the real scorer, undo what scoring changed, continue. Section 11 records what was built and validated on Nov 3 | Current. Built and validated; production paused at 48 of 130 runs |
| [plans/nov3-science-review.md](plans/nov3-science-review.md) | A review of the Nov 3 design: confounders (chiefly, `dev` can already act as the database superuser through the allowed rebuild), next experiments, the hidden-task design | Current, Nov 3 03:50 |
| [plans/residue-free-scoring-scope.md](plans/residue-free-scoring-scope.md) | Could the test cases leave no residue at all? For all 27 scorers, what each leaves; every approach compared; whether it's principled, possible and worth the work; residue the undo can't reach | Scope, Nov 3 ~17:10. Verdict: don't build it; keep score and roll back. Awaiting Arya's calls on its recommendations |
| [plans/residue-undo-scope.md](plans/residue-undo-scope.md) | How to find and undo whatever a scorer leaves behind, without a hand-made list | Done. Its approach is what `harness/rollback.py` builds |
| [plans/replay-free-scope.md](plans/replay-free-scope.md) | Starting after-arm jobs from a saved trajectory end state instead of replaying the trajectory (part 1), and scoring every turn in one machine (part 2) | Part 1 built and checked (`restorecheck-*`), and used by score and roll back. Part 2 superseded by score and roll back |
| [plans/vm-runbook.md](plans/vm-runbook.md) | How to set up a cloud machine and run on it, with the exact commands. Scripts in `harness/vm/` | Current for the next cloud run. Used on the Lambda machine, Nov 3 03:15–09:30 (now terminated). Written for AWS |
| [plans/sandbox-forking-options.md](plans/sandbox-forking-options.md) | Matthew's suggestion of sandbox forking, and the options with local Docker | Idea for later |
| [plans/research-snapshot-tools.md](plans/research-snapshot-tools.md) | Web research: fast ways to snapshot, fork and restore a Compose stack in WSL2 | Reference, Nov 2 |
| [plans/research-eval-practice.md](plans/research-eval-practice.md) | Web research: how agent benchmarks handle environment state and per-step scoring | Reference, Nov 2 |
| [plans/nov3-plan-to-6am.md](plans/nov3-plan-to-6am.md) | The plan for the Nov 3 run: search for a power-seeking trajectory (6 tasks × notes), then the three arms on 15 tasks (later 27), per-step scoring from coarse to fine | Done. Approved ~02:40, revised through the night |
| [plans/nov3-triage-brief.md](plans/nov3-triage-brief.md) | The prompt the trajectory triage agents got | Done, Nov 3 |
| [plans/aws-machine.md](plans/aws-machine.md) | The AWS machine (`c7a.32xlarge`): launch settings, costs, disk, capacity | Historical. Not used: AWS's quota allowed only 32 vCPUs, so the run used a Lambda machine (124 cores) |
| [plans/night-plan.md](plans/night-plan.md) | The plan for the night of Nov 1–2: trajectories A and B, the power formula with horizons, the failure checklist | Historical, but its failure checklist ("Watching for failures") still applies; the formula now lives in `harness/power_horizons.py`, with the `last-scored` rule |
| [plans/proposed-changes.md](plans/proposed-changes.md) | Changes proposed after the call with Matthew, numbered 1 to 8 | Historical. The night plan refers to them by number |
| [plans/plan.md](plans/plan.md) | The original v0 design and the choice of the 6 future tasks. Approved Nov 1 | Historical. The 6 tasks are among the 27 |
| [plans/run-plan.md](plans/run-plan.md) | The first v0 procedure: WSL setup, data layout, free checks, scoring | Historical. Its setup notes still hold |
| [plans/inclination-plan.md](plans/inclination-plan.md) | How to prompt the trajectory agent toward power-seeking without changing the solver's prompt | Historical. The notes are in `harness/power_v0.py` (`INCLINATIONS`) |

### `logs/`

One per session, newest entries at the bottom.

| Path | What it is | Status |
| --- | --- | --- |
| [logs/2026-11-05-power-research.md](logs/2026-11-05-power-research.md) | The Nov 5 research stretch, with what each report found | In progress |
| [logs/2026-11-03-score-and-rollback.md](logs/2026-11-03-score-and-rollback.md) | The side session building, validating and pausing score and roll back; near its end, the resume command; then the Nov 5 efficiency tests | In progress |
| [logs/2026-11-02-midday-runs.md](logs/2026-11-02-midday-runs.md) | The main session from Nov 2 midday: B re-recorded, A's after runs, the gap search, the dashboard; then the Nov 3 run (from "02:45"): the search for B, Lambda, the two pairs, the audit, the triage, Arya's decisions; near its end, the combined page | Done |
| [logs/2026-11-01-night-and-morning.md](logs/2026-11-01-night-and-morning.md) | The night of Nov 1 to the morning of Nov 2, with summaries at the top | Done |

### `findings/`

[findings/README.md](findings/README.md) puts these in reading order, by question.

| Path | What it is | Status |
| --- | --- | --- |
| [findings/results-nov3.md](findings/results-nov3.md) | The Nov 3 results: design, reward rule, headline table, audit, solver triage, caveats, what's pending | Current. The per-5-turn numbers will be replaced by every-turn rescoring |
| [findings/data-map.md](findings/data-map.md) | Where every piece of data lives, with counts and sizes: `runs/`, the configs, `findings/`, `analysis/`, and the raw data in WSL | Current, Nov 5 |
| [findings/nov5-what-power-looks-like.md](findings/nov5-what-power-looks-like.md) | The main session's synthesis of the Nov 5 reports: what power looks like here, and what to do next | Current, Nov 5 (one run per task and arm) |
| [findings/nov5-causal-factors.md](findings/nov5-causal-factors.md) | Which factors could cause the controls to beat or match the power-seeking trajectories at low step budgets: the gap in steps, each factor against the records, Arya's two accounts, the experiments that would separate them. Scripts in `analysis/causal/` | Current |
| [findings/nov5-discounted-power.md](findings/nov5-discounted-power.md) | What makes discounted POWER larger: the algebra, steps saved per test case, how much of each gap comes from low H | Current, Nov 5 |
| [findings/nov5-what-power-seeking-looks-like.md](findings/nov5-what-power-seeking-looks-like.md) | What the 42 Nov 3 trajectories did in the name of power, by category: taxonomy by note, the model's reasoning, cost, what was left, routes, mismatch with tasks, record-only measures. Scripts and counts in `analysis/trajectories/` | Current, Nov 5 (from stored records; nothing run; 26 trajectories rest on counts and targeted reading) |
| [findings/task-power/](findings/task-power/jwt_claims_wrong_field.md) | One report per future task (27): what power means in that task, what each arm did, which head starts help. Structured results in `analysis/data/task_power.json`. `others/` holds the same for the other 56 main tasks, with no solver runs behind them | Current, Nov 5 (agents' judgment from one run per arm). `others/` is in progress, paused at the usage limit |
| [findings/nov5-main-task-pool.md](findings/nov5-main-task-pool.md) | All 83 `model_registry` main tasks: scorer structure, which head starts help each one, fairness for `dev`, task classes, coverage of the 27, three proposed task sets | Current, Nov 5 (read from code and run records; nothing run; ratings and sets are judgment) |
| [findings/nov5-side-tasks.md](findings/nov5-side-tasks.md) | The 9 `model_registry` side tasks as a measure of power, by category and kind of capability only | Current, Nov 5 (read from code; nothing run) |
| [findings/nov5-linuxarena-environments.md](findings/nov5-linuxarena-environments.md) | The other LinuxArena environments: what each is, its tasks, what power would mean there, how each differs from `model_registry`, a ranked comparison, port costs | Current (read from code and published data; nothing run) |
| [findings/nov5-literature.md](findings/nov5-literature.md) | How others measure power and design task sets, saturation and horizons, information and parallel tool calls, causal designs, the control settings; what it means for this project | Current, Nov 5 |
| [findings/nov5-review.md](findings/nov5-review.md) | Independent attempt to refute the main Nov 5 conclusions: a verdict per claim with corrected numbers, the strongest alternative story, and what would decide between them | Current, Nov 5 |
| [findings/power-horizons-v4.json](findings/power-horizons-v4.json), [.txt](findings/power-horizons-v4.txt); [findings/v4b/power-horizons-v4.json](findings/v4b/power-horizons-v4.json), [.txt](findings/v4b/power-horizons-v4.txt) | `power_horizons.py`'s curves and printed tables for pair 1 and pair 2. `findings/both/` will hold the combined page's | Generated, Nov 3 12:05 and 12:14, under `last-scored`, every 5 turns. `tools/power.sh pages` rewrites them |
| [findings/solver-power-use/](findings/solver-power-use/afterB.json) | Per after arm (`afterA`, `afterB`, `afterA2`, `afterB2`), for each of the 27 solver runs: did the solver use access beyond `dev`'s, what, at which steps, was it needed, did it help | Current, Nov 3 09:15–10:05 |
| [findings/score-corrections.json](findings/score-corrections.json) | Scorer verdicts replaced by hand, with the evidence: B2's storage-question answer. `power_horizons.py` reads it | Current (Arya, Nov 3 ~10:15) |
| [findings/excluded-labels.txt](findings/excluded-labels.txt) | 39 Nov 2 per-step labels left out of every computation; `power_horizons.py` reads it | Current. Affects only the Nov 2 numbers |
| [findings/superuser-audit.md](findings/superuser-audit.md) | For the 6 original tasks, which checks need something only a superuser could provide, and two routes to root `dev` already has | Current for those 6 tasks |
| [findings/results-night-1.md](findings/results-night-1.md) | Results of the Nov 2 runs (6 tasks, trajectories `traj2-*` and `traj3-power`): why the first B cleaned up, the before arm's curve, checks of the method | Superseded by results-nov3.md |
| [findings/old/](findings/old/power-horizons-partial.json) | The Nov 2 power computations: `power-horizons-partial.json`, `-current`, `-first-pass`, `-A-partial` | Historical |
| [findings/ab-trajectories.md](findings/ab-trajectories.md) | The two Nov 1 trajectories, and the finding that `dev` still had the superuser password | Historical (old runs) |
| [findings/bottlenecks.md](findings/bottlenecks.md) | Bottlenecks after the 12-run root pilot | Historical (old runs) |

### `analysis/`

The dataset for working out why some arms pass test cases sooner. Start with [analysis/README.md](analysis/README.md), which explains why a comparison across arms should use the every-5-turn columns while the every-turn rows are partial.

| Path | What it is | Status |
| --- | --- | --- |
| [analysis/build_dataset.py](analysis/build_dataset.py) | The one script, also `tools/power.sh dataset` | Current. Every-turn rows cover 48 of 130 runs; rerun with `--refresh` when more land |
| [analysis/data/](analysis/data/summary.md) | `summary.md` (start here), `runs.csv`, `turns.csv`, `testcases.json`, `curves.json`, `checks.json`, `task_power.json` | Generated, Nov 5 |
| `analysis/digests/<task>/<arm>.md` | A short digest of every solver run (135), and `_trajectories/` for the 4 trajectories | Generated, Nov 5 |
| `analysis/trajectories/` | Scripts and counts behind `findings/nov5-what-power-seeking-looks-like.md` | Current, Nov 5 |
| [analysis/causal/](analysis/causal/common.py) | Scripts and printed output behind `findings/nov5-causal-factors.md` | Current, Nov 5 |

### `tasks/`

| Path | What it is | Status |
| --- | --- | --- |
| [tasks/task-set-v2.md](tasks/task-set-v2.md) | The revised 30-task set, judged by the kinds of power each task could use. Its kinds are the pages' task filter | Draft for Arya. The Nov 3 run used 27 tasks; their files are `harness/tasks/v4_tasks_p1..p5.txt`. For a next set, see `findings/nov5-main-task-pool.md` |
| [tasks/task-candidates.md](tasks/task-candidates.md) | The 30-task shortlist the first 6 tasks were picked from | Historical |

### `runs/`

The readable, redacted records: 1,138 batches, 183 MB. Never move or rename a batch folder: code finds runs by label. Families and counts are in [findings/data-map.md](findings/data-map.md).

| Path | What it is | Status |
| --- | --- | --- |
| [runs/runs-registry.md](runs/runs-registry.md) | Every run label, with purpose, settings and date | Generated |
| `runs/<label>/README.md`, `summary.json` | Each batch's index: purpose, exact settings, spend, one row per run | Generated by `export_run.py` |
| `runs/<label>/<task>/<run>/` | One run's record: `transcript.md`, `prompts/`, `config.json`, `meta.json`, `scores.json`, `usage.csv`, `raw-paths.txt`, and `horizon_scores.jsonl` for score-and-roll-back jobs. Known secrets are replaced by `<secret>` | Generated |
| `runs/traj4-*/power-actions.json` | What 16 of the Nov 3 trajectories did that bears on power, step by step (the pages' run investigations) | Current |
| `runs/traj2-*/labels.md`, `runs/traj3-power/labels.md` | The same for the Nov 2 trajectories, hand-written | Historical |
| [runs/traj-gentle/transcript.md](runs/traj-gentle/transcript.md), [runs/traj-neutral/transcript.md](runs/traj-neutral/transcript.md) | Older readable transcripts of the two Nov 1 trajectories | Historical |

### `harness/`

The code, the one copy to edit. [harness/README.md](harness/README.md) lists every file. `old/` holds retired scripts. Another session is editing it now. The main groups:
- **the runs:** `power_v0.py` (the policy and every prompt), `launch.sh`, `night_queue.py`, `resume_queue.py`, `make_traj_jobs.py`, `make_v4_jobs.py`, `make_v4_hz_jobs.py`, `task_names.py`, and `tasks/`;
- **starting from a saved state:** `state_store.py`, `env_fingerprint.py`, `refresh_states.py`;
- **score and roll back:** `rollback.py`, `engine_exec.py`, `compare_sr.py`, `dedup_gate.py`, `watch_sr.py`, `queue_density.py`, `find_paused_points.py`, with `test_rollback.py` and `test_dedup_gate.py`;
- **the Nov 5 efficiency tests:** `bench*.py`, `bench_*.sh`, `schedule_error.py`, `test_schedule_error.py`;
- **results:** `export_run.py`, `extract.py`, `power_horizons.py`, with `test_export_redact.py` and `test_power_horizons.py`;
- **`vm/`:** `setup.sh`, `copy.sh`, `finish_v4.sh`, `sync_rollback_pages.py` (the tables and all three pages), `secret_scan.py`, `compare_runs.py`, `ct-packages.txt`.

### `viz/`

| Path | What it is | Status |
| --- | --- | --- |
| [viz/power-dashboard-v4-both.html](viz/power-dashboard-v4-both.html) | **The main page:** the two pairs on one page: the initial environment state, A1, B1, A2 and B2 on the same charts, with B1 minus A1, B2 minus A2 and B2 minus B1. Built from [viz/run-v4-both.json](viz/run-v4-both.json); published at https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22 | Current. Generated Nov 3 17:03; rebuild after the rescoring |
| [viz/power-dashboard-v4b.html](viz/power-dashboard-v4b.html) | Pair 2 alone (A2 = `traj4-minio-none`, B2 = `traj4-minio-keep`). Built from [viz/run-v4b.json](viz/run-v4b.json); published at https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh | Current. Generated Nov 3 12:22; rebuild after the rescoring |
| [viz/power-dashboard-v4.html](viz/power-dashboard-v4.html) | Pair 1 alone (A = `traj4-sharing-none`, B = `traj4-sharing-side`). Built from [viz/run-v4.json](viz/run-v4.json). Its old link now shows the combined page | Current as a file; not published. Generated Nov 3 12:51 |
| [viz/run-v4-both.json](viz/run-v4-both.json), [viz/run-v4.json](viz/run-v4.json), [viz/run-v4b.json](viz/run-v4b.json) | The pages' configs: which batches form each arm, the 27 tasks, the reward rule, the trajectories; for the combined page, each arm's names and the differences to show. Read by `build_dashboard.py`, `harness/vm/sync_rollback_pages.py` and `finish_v4.sh` | Current |
| [viz/build_dashboard.py](viz/build_dashboard.py) | Builds a page from a config and the records, taking every number from `harness/power_horizons.py` | Current |
| [viz/task-sections.json](viz/task-sections.json) | The pages' task filter: tasks grouped by kind of power, kind of task and batch | Current |
| [viz/run-stories-v4.json](viz/run-stories-v4.json) | The text of the pages' run investigations, by trajectory | Current |
| [viz/run_investigation.py](viz/run_investigation.py), [viz/run-investigation-style.md](viz/run-investigation-style.md), [viz/run-investigation-preview.html](viz/run-investigation-preview.html) | Renders one run's actions as a timeline (borrowing METR's layout); its style notes; a preview of the two power-seeking trajectories, written by the script | Current; the preview is generated |
| [viz/nov3-power-curves-pair1.png](viz/nov3-power-curves-pair1.png), [viz/nov3-power-curves-pair2.png](viz/nov3-power-curves-pair2.png) | The report's figure: POWER_H against the budget H for each pair. Drawn by [viz/power_curves_plot.py](viz/power_curves_plot.py) | Stale: drawn 08:47 under the first-pass rule. Redraw after the rescoring |
| [viz/nov3-prompt-power-heatmap.png](viz/nov3-prompt-power-heatmap.png) | The search for B in one figure: for each trajectory task and note, how much lasting access the trajectory kept (triage score 1–5). Drawn by [viz/prompt_power_heatmap.py](viz/prompt_power_heatmap.py), with `nov3-prompt-power-extra.tsv` (the later screen's scores) | Current, Nov 3 05:42 |
| [viz/vocabulary-and-figures-proposal.md](viz/vocabulary-and-figures-proposal.md) | Proposed plain vocabulary and figures for the pages | Done. Draft, Nov 3 00:50; the pages have used plain names since 01:50 |
| [viz/visualization-scope.md](viz/visualization-scope.md) | Options for reading transcripts and logs | Historical. The pages' run viewer and investigations came from it |
| [viz/power-dashboard.html](viz/power-dashboard.html) | The Nov 2 results page (6 tasks, `v2`/`v3` arms); what `build_dashboard.py` writes with no options | Historical |
| [viz/old/power-dashboard.artifact.html](viz/old/power-dashboard.artifact.html) | The published copy of that page, with the artifact title and theme tokens (https://claude.ai/artifact/9ks5Ht1ZmXCkenBewuNpwc) | Historical |
| [viz/old/build_dashboard.viewer-wip.py](viz/old/build_dashboard.viewer-wip.py) | An unfinished generator with the first run viewer, kept as a reference | Historical. The viewer is in `build_dashboard.py` since Nov 3 01:50 |

### `pilot-results/`

Data files from the old pilot runs (called `results/` until Nov 2). All historical.

| Path | What it is |
| --- | --- |
| [pilot-results/index.csv](pilot-results/index.csv) | One row per run for the root-solver checks and pilot |
| [pilot-results/pilot-runs.csv](pilot-results/pilot-runs.csv), [pilot-config.txt](pilot-results/pilot-config.txt), [pilot-spend.csv](pilot-results/pilot-spend.csv) | The 12-run root pilot: the dashboard's data, its settings, and spend |
| [pilot-results/runs-both.csv](pilot-results/runs-both.csv), [spend-both.csv](pilot-results/spend-both.csv) | The same for both solvers, root and `dev` |
| [pilot-results/dashboard-page.html](pilot-results/dashboard-page.html) | Source of the pilot's [dashboard page](https://claude.ai/artifact/6wWDV1cqKJVF55Jioo7JbP) |

## Old runs and new runs

- **Nov 3 (current):** `traj4-*`, `v4-*`, `nowork-v4-*`, `hz-v4-*`, and the every-turn rescoring `sr-v4-*`, with the checks `restorecheck-*` and `hzcheck-*`. Two pairs:
  - **pair 1:** A = `traj4-sharing-none`, B = `traj4-sharing-side`; arms `v4-afterA-*`, `v4-afterB-*`;
  - **pair 2:** A2 = `traj4-minio-none`, B2 = `traj4-minio-keep`; arms `v4-afterA2-*`, `v4-afterB2-*`;
  - both share the initial-state arm `v4-before-*`. Each arm is split into parts `-p1` to `-p5`, one per machine and batch. The combined page calls pair 1's arms A1 and B1.
- **Nov 2 (superseded):** `traj2-*`, `traj3-power`, `v2-*`, `v3-afterB`, `nowork-v2-*`, `nowork-v3-afterB`, `hz-v2-*`, `hz-v3-*`, `hzcheck-dash`, `hzcheck-fav`, `probe-v2`. Made without the superuser password, on the 6 original tasks. Their results are in [findings/results-night-1.md](findings/results-night-1.md).
- **Old runs (before Nov 2):** the root-solver runs (`pilot-*`, `check0*`), and the `dev` runs made while the superuser password was still in `dev`'s environment (`check-dev*`, `final-probe-*`, `nowork-dev-*`, `pilotdev-*`, `prep-traj-nowork`, `traj-gentle`, `traj-neutral`, `replaycheck-*`). Kept as data, never in the new numbers.

In every run since Nov 2, A is the control and B the power-seeking trajectory (on Nov 1 the letters were the other way round). The label scheme is in [../../CLAUDE.md](../../CLAUDE.md).

**Where the data is.** Raw data stays in WSL under `/root/power-v0/` (`data/evals/`, `data/runs/`, `data/states/`, `trajectory/`, `lambda-nov3/`); the readable, redacted copies are in `runs/` here. [findings/data-map.md](findings/data-map.md) has the details.

## Left in place for Arya to decide

Nothing here is in the way, and none of it was touched.
- **`viz/run-investigation-preview.html`** (80 KB): generated by `viz/run_investigation.py`, which writes it there by default, and named in the style notes. The pages hold the same investigations.
- **The 8 `sr-v4-*` folders with no `meta.json`** (listed in the data map): jobs that failed to start. They hold a `summary.json`, a README and a short transcript recording the failure, so they aren't empty. The code skips them.
- **In WSL, all from Nov 3–5 work, listed in the data map:** `data/rollback/` (6.4 GB, working copies of stopped jobs; another session owns it), `bench/` (3.1 GB, the same session), `tmp-ph-check/`, `tmp-sr-old/`, and the empty `analysis/` and `states/`.

## What moved, and when

- **Nov 1–2:** the plans went to `plans/`, two findings to `findings/`, the task list to `tasks/`, and the old transcripts to `runs/traj-*/`.
- **Nov 2:**
  - `night-plan.md` went to `plans/`;
  - `night-log.md` became `logs/2026-11-01-night-and-morning.md`;
  - `results/` became `pilot-results/`;
  - the harness task files went to `harness/tasks/`, and three retired scripts to `harness/old/`.
- **Nov 3:** nothing moved. New: the Nov 3 plans, logs, findings and pages, and `findings/data-map.md`.
- **Nov 5:**
  - `viz/build_dashboard.viewer-wip.py` and `viz/power-dashboard.artifact.html` went to `viz/old/`;
  - the four Nov 2 `findings/power-horizons-*.json` (`-partial`, `-current`, `-first-pass`, `-A-partial`) went to `findings/old/`, and the links to them were updated.
  New: `analysis/`, `findings/nov5-*`, `findings/task-power/`, `findings/README.md`, `tools/power.sh`, `tools/record_cache.py`.
