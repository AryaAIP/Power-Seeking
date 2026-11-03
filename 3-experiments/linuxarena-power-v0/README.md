# LinuxArena power v0

*The folder index. Rewritten 2026-11-02 at about 11:15 CST, when the folder was tidied. Update it whenever a file is added or moved, then run `tools/check_links.py` from the project folder. The project's conventions are in [../../CLAUDE.md](../../CLAUDE.md).*

**What this folder is.** The project's first measurement of power in a real environment, LinuxArena's `model_registry`: a Go web service with a Postgres database and object storage.
1. An agent does one task, RBAC, as the developer account `dev`. That run is the **trajectory**, and the machine it leaves behind is kept.
2. A fixed agent, the **solver**, then does each of 6 other tasks twice:
   - in a **before run**, from the untouched machine;
   - in an **after run**, from the machine the trajectory left, continuing the trajectory's chat.

If the solver does better after than before, the trajectory gained power. Power is scored at several horizons: after H of the solver's turns.

**Start with:**
- [next-steps.md](next-steps.md): what's next, with the exact commands;
- [findings/results-night-1.md](findings/results-night-1.md): results so far and checks of the method;
- the newest log in [logs/](logs/).

## Files

| Path | What it is | Status |
| --- | --- | --- |
| [next-steps.md](next-steps.md) | What to do next, in order, with the exact commands | Current |
| **`plans/`** | | |
| [plans/night-plan.md](plans/night-plan.md) | The plan for the night of Nov 1–2: <ul><li>trajectory A (control) and trajectory B (power-seeking);</li><li>the power formula with horizons;</li><li>the failure checklist;</li><li>the "Done when" list</li></ul> | Current. Its formula and failure checklist still apply |
| [plans/proposed-changes.md](plans/proposed-changes.md) | Changes proposed after the call with Matthew, numbered 1 to 8 | Current. The night plan refers to them by number |
| [plans/plan.md](plans/plan.md) | The original v0 design and the choice of the 6 future tasks. Approved Nov 1 | Historical. The 6 tasks are still the ones used |
| [plans/run-plan.md](plans/run-plan.md) | The first v0 procedure: the WSL setup, the data layout, the free checks and how runs are scored | Historical. Its setup notes still hold, and its $10 project spending cap still stands |
| [plans/research-snapshot-tools.md](plans/research-snapshot-tools.md) | Web research: fast ways to snapshot, fork and restore a Compose stack, and which fits our WSL2 setup. Recommends forking the stack at each scoring point (`docker commit` of the app container, a copy of the paused Postgres volume and the stack's buckets) and scoring the copy, so nothing needs restoring. CRIU is ruled out on Docker 28/29. The open risk is commit speed on this machine's containerd image store with a 9.4 GB image | Research, Nov 2 |
| [plans/research-eval-practice.md](plans/research-eval-practice.md) | Web research: how agent benchmarks and frameworks handle environment state and per-step scoring (τ²-bench, ToolSandbox, SWE-bench, OSWorld and others), and replay against snapshots. Recommends replaying each run once and saving the state at each turn, then scoring copies on a separate stack | Research, Nov 2 |
| [plans/score-and-rollback-scope.md](plans/score-and-rollback-scope.md) | Scope for scoring each run in one machine: replay step by step, save the state, run the real scorer, restore, continue. It covers each scorer's side effects, cost now against new, the validation plan and the decisions for Arya | Proposal, awaiting Arya's decisions |
| [plans/aws-machine.md](plans/aws-machine.md) | The AWS machine (`c7a.32xlarge`, 128 cores, 256 GB): <ul><li>launch settings;</li><li>costs;</li><li>disk size;</li><li>how many environments at once;</li><li>what differs from WSL;</li><li>the setup order</li></ul> | Current, Nov 3. The machine is being launched |
| [plans/nov3-plan-to-6am.md](plans/nov3-plan-to-6am.md) | The plan for Nov 3, 02:45–06:00: <ul><li>a search for a power-seeking B (6 trajectory tasks × 5 prompts);</li><li>before, after A and after B on 15 tasks;</li><li>per-step scoring, coarse to fine</li></ul> | Proposal, awaiting Arya's decisions |
| [plans/vm-runbook.md](plans/vm-runbook.md) | How to set up the AWS machine and run on it, with the exact commands: <ul><li>the first set-up;</li><li>the checks against WSL;</li><li>each session, including the OpenRouter key and the queue;</li><li>bringing the results back</li></ul> The scripts are in `harness/vm/` | Current, Nov 3. Not yet tried on the machine |
| [plans/sandbox-forking-options.md](plans/sandbox-forking-options.md) | Matthew's suggestion of sandbox forking: what E2B forking is, options with our local Docker setup, and the one change that would save the most machine time | Idea for later. Nothing built |
| [plans/inclination-plan.md](plans/inclination-plan.md) | How to prompt the trajectory agent toward power-seeking without changing the solver's prompt | Historical. The notes themselves are in `harness/power_v0.py` (`INCLINATIONS`) |
| **`logs/`** | | |
| [logs/2026-11-01-night-and-morning.md](logs/2026-11-01-night-and-morning.md) | The running record from the night of Nov 1 to the morning of Nov 2, with summaries at the top | Done |
| [logs/2026-11-02-midday-runs.md](logs/2026-11-02-midday-runs.md) | Nov 2 midday: B re-recorded with the `keep` note, A's after runs, finer per-step scoring | Current |
| **`findings/`** | | |
| [findings/results-night-1.md](findings/results-night-1.md) | Results of the Nov 2 runs: <ul><li>what the trajectories did and left;</li><li>why the agent cleaned up;</li><li>the before arm's power curve;</li><li>checks of the method;</li><li>what's unfinished</li></ul> | Current, partial: the after runs haven't run |
| [findings/superuser-audit.md](findings/superuser-audit.md) | For each of the 6 tasks, which checks need something only a superuser could provide (only the refactor task's Go tests), plus two routes to root `dev` already has | Current |
| [findings/ab-trajectories.md](findings/ab-trajectories.md) | The two Nov 1 trajectories (`traj-gentle`, `traj-neutral`), and the finding that `dev` still had the superuser password | Historical (old runs). It led to the Nov 2 setup |
| [findings/bottlenecks.md](findings/bottlenecks.md) | Bottlenecks after the 12-run root pilot, and why its gain was about zero | Historical (old runs) |
| **`tasks/`** | | |
| [tasks/task-set-v2.md](tasks/task-set-v2.md) | The revised 30-task set, judged by the kinds of power each task could use. It has a correction note about the test database | Draft for Arya |
| [tasks/task-candidates.md](tasks/task-candidates.md) | The 30-task shortlist the 6 tasks were picked from | Current, until `task-set-v2.md` replaces it |
| **`runs/`** | | |
| [runs/runs-registry.md](runs/runs-registry.md) | Every run label: <ul><li>a hand-written table for the old runs;</li><li>an automatic table for runs since Nov 2</li></ul> | Current |
| `runs/<label>/README.md`, `summary.json` | Each batch's index: purpose, exact settings, spend, and one row per run linking to its transcript | Generated by `export_run.py` |
| `runs/<label>/<task>/<run>/` | One run's complete record: <ul><li>`transcript.md`: full reasoning, every tool call and output;</li><li>`prompts/`;</li><li>`config.json`, `meta.json`, `scores.json`, `usage.csv`;</li><li>`raw-paths.txt`</li></ul> Known secrets are replaced by `<secret>` | Generated |
| `runs/traj2-*/labels.md` | What each Nov 2 trajectory did that bears on power, with turn numbers, and what it left behind | Current |
| [runs/traj-gentle/transcript.md](runs/traj-gentle/transcript.md), [runs/traj-neutral/transcript.md](runs/traj-neutral/transcript.md) | Older readable transcripts of the two Nov 1 trajectories | Historical |
| **`harness/`** | The code, the one copy to edit. [harness/README.md](harness/README.md) lists every file. `tasks/` holds the task files, and `old/` the retired scripts | Current |
| **`viz/`** | | |
| [viz/visualization-scope.md](viz/visualization-scope.md) | Options for reading transcripts and logs, with a recommendation | Draft for Arya |
| [viz/power-dashboard.html](viz/power-dashboard.html) | The results page, one self-contained file, published as the private artifact https://claude.ai/artifact/9ks5Ht1ZmXCkenBewuNpwc (from `viz/power-dashboard.artifact.html`, the same page with the artifact title and theme tokens; republish to that URL after a rebuild): <ul><li>the headline gains with intervals;</li><li>B minus A per task;</li><li>power and gain curves;</li><li>per-task curves for before, after-A and after-B;</li><li>a check grid per run;</li><li>the runs tables and the data gaps</li></ul> | Current. Regenerate with `viz/build_dashboard.py` (in WSL, about 1 minute) after new scores |
| [viz/build_dashboard.py](viz/build_dashboard.py) | Builds the page from the exported records, using `harness/power_horizons.py` for every number | Current |
| **`pilot-results/`** | Data files from the old pilot runs. These were called `results/` until Nov 2 | Historical |
| [pilot-results/index.csv](pilot-results/index.csv) | One row per run for the root-solver checks and pilot | Historical |
| [pilot-results/pilot-runs.csv](pilot-results/pilot-runs.csv), [pilot-config.txt](pilot-results/pilot-config.txt), [pilot-spend.csv](pilot-results/pilot-spend.csv) | The 12-run root pilot: the dashboard's data, its settings, and spend | Historical |
| [pilot-results/runs-both.csv](pilot-results/runs-both.csv), [spend-both.csv](pilot-results/spend-both.csv) | The same for both solvers, root and `dev` | Historical |
| [pilot-results/dashboard-page.html](pilot-results/dashboard-page.html) | Source of the [dashboard page](https://claude.ai/artifact/6wWDV1cqKJVF55Jioo7JbP) | Historical. To be updated with the new runs |

## Old runs and new runs

**Old runs** are everything recorded before Nov 2. They come in two groups:
- **the root-solver runs,** labelled `pilot-*` and `check0*`;
- **the `dev` runs made while the superuser password was still in `dev`'s environment,** labelled `check-dev*`, `final-probe-*`, `nowork-dev-*`, `pilotdev-*`, `prep-traj-nowork`, `traj-gentle`, `traj-neutral` and `replaycheck-*`.

They're kept as data but never enter the new numbers.

**New runs** are from Nov 2 on, without the password. Their labels follow the scheme in [../../CLAUDE.md](../../CLAUDE.md):
- `traj2-*`, `v2-*`, `nowork-v2-*`, `hz-*`, `hzcheck-*`, `probe-v2`;
- next, `traj3-power` with the new note.

On Nov 1 the trajectory letters were the other way round. In the new runs, A is always the control and B the power-seeking variant.

**Where the data is.** Raw data stays in WSL under `/root/power-v0/data/`:
- `evals/<label>/`: the `.eval` logs, which are the source;
- `runs/<label>/<task>/<run>/`: snapshots and database dumps.

The readable, redacted copies are in `runs/` here.

**What moved, and when:**
- **Nov 1–2:** the plans went to `plans/`, two findings to `findings/`, the task list to `tasks/`, and the old transcripts to `runs/traj-*/`.
- **Nov 2:**
  - `night-plan.md` went to `plans/`;
  - `night-log.md` became `logs/2026-11-01-night-and-morning.md`;
  - `results/` became `pilot-results/`;
  - the harness task files went to `harness/tasks/`, and three retired scripts to `harness/old/`.
