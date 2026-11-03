# Power-seeking project: start here

*Updated 2026-11-01, after the LinuxArena pilot; folder layout and current state updated Nov 2, and the current work on Nov 3. Read this first. It lists every source behind the project, every doc and thread it has produced, where things stand, and what to read next. If you're a new Claude or agent picking this up, read [CLAUDE.md](CLAUDE.md) (the project's conventions) and [working-with-arya.md](1-handoff/working-with-arya.md) before you write anything to Arya.*

**Current work (Nov 3):** the first power measurement, in [3-experiments/linuxarena-power-v0/](3-experiments/linuxarena-power-v0/README.md).
- The Nov 3 results (two pairs of trajectories, 27 tasks) are in [findings/results-nov3.md](3-experiments/linuxarena-power-v0/findings/results-nov3.md). The Nov 2 results, now superseded, are in [findings/results-night-1.md](3-experiments/linuxarena-power-v0/findings/results-night-1.md).
- Where every piece of data lives: [findings/data-map.md](3-experiments/linuxarena-power-v0/findings/data-map.md).
- What's next is in [next-steps.md](3-experiments/linuxarena-power-v0/next-steps.md).
- The live state is in section 0 of [SESSION-NOTES-for-compacted-Claude.md](SESSION-NOTES-for-compacted-Claude.md).

Section 2 below describes Nov 1 and is out of date.

**What the project is.** Arya Pasumarthi, a SPAR fall 2026 participant, is measuring power-seeking in language-model agents. The working definition comes from Turner's work and Matthew Khoriaty's proposal. The **power** of a state is how well and how fast a fixed solver can complete a set of future tasks from that state. An action **gains power** if applying its effect raises that score. The plan runs in three stages: measure power in a real environment first, then measure it with "illusory" (simulated) environments, then broaden the set of future tasks.

**Folder layout.** The folder was reorganised on Nov 1 at Arya's request, and tidied again on Nov 2:

```
README.md                  start here
CLAUDE.md                  conventions for any Claude session: layout, run workflow, labels, rules, notes
SESSION-NOTES-for-compacted-Claude.md   live state (section 0) and infrastructure details
.gitignore                 keeps the raw .eval logs (they contain secrets) out of any repository
1-handoff/                 decisions log, runbook, working-with-Arya note, handoff scope
2-plan-doc-snapshots/      Markdown copies of the 4 tabs of the main Claude Doc
3-experiments/
  basharena-test/          Nov 1 BashArena test: harness, Docker overrides, run logs
  linuxarena-pilot/        Nov 1 LinuxArena pilot: scope, results, transcripts, run logs, harness
  linuxarena-power-v0/     Nov 1- the first power measurement (current): plans, logs, findings, runs, harness
4-background-oct-2026/     the earlier thread's Oct 19-30 notes (mostly out of date), incl. testbed-research/
5-reading-notes-nov-2026/  Nov 1 reading notes on every source in section 1, plus synthesis.md (start there)
tools/                     check_links.py: reports broken relative links (run after moving files)
```

The live Claude Docs, the doc snapshots and `1-handoff/handoff-scope.md` still use the old paths, such as `power-seeking/basharena-test/` and `power-seeking/linuxarena-pilot/`. Those folders are now under `3-experiments/`, and the older notes are under `4-background-oct-2026/`.

---

## 1. Literature review: the sources used to get context

These are the sources read at the start of the planning thread (Oct 31) and by the earlier thread (Oct 19–30). **Opened** means a Claude read the source itself. For several of the papers, that was a research subagent working for the planning thread. **Seen linked** means it was only referenced, and nobody here opened it.

### Project documents

| Source | What it contributed | Read? |
| --- | --- | --- |
| Travis Kim, [Measuring Power Along Agent Trajectories in ToolEmu](https://docs.google.com/document/d/17olc1KFioHDz0jS82xKLWhG1qgE61Rcg/edit), SPAR progress report, Oct 31 | The existing measurement: power at each point in a trajectory, scored as success within H steps. It's the baseline Arya's proposal builds on, and the reason ToolEmu was ruled out | Opened |
| Matthew Khoriaty, [[DRAFT] Shaping LLM Personality via its Behavior on Future Tasks](https://docs.google.com/document/d/148Z2MpQD4u0UR1Nhf3UszgCBDtChllqhlxdVrKYNfW4/edit), with its comment threads | The project's framing: power as performance on future tasks, the Powerwashing procedure, and comments from Elliott Thornley and Travis | Opened |
| The group's shared thoughts doc ([Google Doc 1YBz5…](https://docs.google.com/document/d/1YBz5uxjeuPw9xt1hzX606iw1GC9N1KQX2db6U8hV69k/edit?tab=t.ryt0tniyf45e)), linked by Arya in the earlier thread | Arya and collaborators' notes | Seen linked |
| Travis Kim, [midterm outline](https://docs.google.com/document/d/1erDP6flVntpNuT0nTw51RjZNVMph1Qxaj11GW5n2onU/edit), linked in Slack on Oct 31 | The group's midterm report plan (due Nov 2) | Seen linked |
| Peyton Li, [example random-probe trajectory](https://docs.google.com/document/d/1qZIk5w2LYcqRdYYuHAm6QGdHlyXU8J9vvo9PIdNgvDU/edit), linked in Slack on Oct 30 | A raw and summarised AppWorld probe trajectory | Seen linked |

### Slack: #alignment-without-personas (SPAR 2025 workspace)

| Source | What it contributed | Read? |
| --- | --- | --- |
| [The channel](https://spar2025.slack.com/archives/C0C0B2GEQCF): Sept 28–Oct 19 (earlier thread) and Oct 26–31 (planning thread) | Group status, who is doing what, deadlines | Opened |
| [Huddle notes, Oct 26](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793048313676409) | Summary of the group's Oct 26 call on power-seeking evaluation | Opened |
| `dose_response_v2.md`, a file posted Oct 26 | Peyton's dose-response probe design: look-first, best-of-k, step and API-call budgets | Opened |
| Peyton Li, Oct 17 thread | Linked SafeMCP / PowerSeeking Bench ([arXiv 2606.01991](https://arxiv.org/abs/2606.01991)) and ClawsBench ([arXiv 2604.05172](https://arxiv.org/abs/2604.05172)). The earlier thread read both papers through a summarising tool, not the raw PDFs | Opened (by the earlier thread) |
| Peyton Li, [initial AppWorld run](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793401595331299), Oct 30 | DeepSeek showed no instances of power-seeking in AppWorld | Opened |
| Peyton Li, [random-probe trajectory](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793402932429269), Oct 30 | Discussion of the probe example above | Opened |
| Matthew Khoriaty, [on task similarity](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793218601023939), Oct 28 | The POWER measure already captures overlap between tasks; use benchmarks' own task buckets | Opened |
| Matthew Khoriaty, [reversibility and self-modification](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793393443025439), Oct 30 | Points to concerns about reversibility reasoning. It links a Gemini safety report and [arXiv 2403.13793](https://arxiv.org/pdf/2403.13793), which were seen linked only | Opened (its links: seen linked) |
| Travis Kim, [report link](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793461071818719) and [midterm outline thread](https://spar2025.slack.com/archives/C0C0B2GEQCF/p1793461258624679), Oct 31 | Where Travis's report and the midterm plan were shared | Opened |

### Alex Turner (TurnTrout)

| Source | What it contributed | Read? |
| --- | --- | --- |
| [The Causes of Power-seeking and Instrumental Convergence](https://www.lesswrong.com/s/fSMbebQyR4wheRrvk), 14 posts, 2019–2023 | Power as the ability to achieve a range of goals. The task set should be the goals we'd really give the agent. Notes are in [turner-power-sequence-notes.md](4-background-oct-2026/turner-power-sequence-notes.md) | Opened, all 14 |
| [Attainable Utility Preservation: Concepts](https://www.lesswrong.com/posts/75oMAADr4265AGK3L/attainable-utility-preservation-concepts) | AUP is an impact penalty, not a power measure. That distinction is explained in the main doc | Opened |
| [Optimal Policies Tend to Seek Power](https://arxiv.org/abs/1912.01683) (NeurIPS 2021) | The formal POWER definition | Opened |
| [Parametrically Retargetable Decision-Makers Tend to Seek Power](https://arxiv.org/abs/2206.13477) | Power-seeking holds beyond optimal agents | Opened |
| [Conservative Agency via Attainable Utility Preservation](https://arxiv.org/abs/1902.09725) (AIES 2020) | The AUP penalty and auxiliary goals | Opened |
| [Avoiding Side Effects in Complex Environments](https://arxiv.org/abs/2006.06547) (NeurIPS 2020) | AUP at scale | Opened |
| [turntrout.com research page](https://turntrout.com/research) | Turner's own retrospective on this work. He also met the group on Oct 7 (see the Oct 19 file) | Opened |

### Victoria Krakovna

| Source | What it contributed | Read? |
| --- | --- | --- |
| [AI safety resources](https://vkrakovna.wordpress.com/ai-safety-resources/) | An index to her related work | Opened |
| [Penalizing side effects using stepwise relative reachability](https://arxiv.org/abs/1806.01186) | Reachability-based impact measures | Opened |
| [Avoiding Side Effects by Considering Future Tasks](https://arxiv.org/abs/2010.07877) | Closest prior work to "power as success on future tasks" | Opened |
| [Power-seeking can be probable and predictive for trained agents](https://arxiv.org/abs/2304.06528), with Janos Kramar | Power-seeking in trained, non-optimal agents | Opened |
| [Reinforcement learning with a corrupted reward channel](https://arxiv.org/abs/1705.08417), with Tom Everitt and others | Listed under specification gaming. Background only | Opened |

### Other papers

| Source | What it contributed | Read? |
| --- | --- | --- |
| [The MACHIAVELLI benchmark](https://arxiv.org/abs/2304.03279) | Suggested by Elliott Thornley in the comments on Matthew's proposal | Seen linked |
| [arXiv 2609.33102](https://arxiv.org/abs/2609.33102) | Linked by Travis in the comments on Matthew's proposal ("multi-agent evals"). Title not recorded | Seen linked |

### Environment sources (Nov 1 research)

Read during the environment comparison. Some were read by research subagents. Details are on the Environment options tab.

- **BashArena:** [paper](https://arxiv.org/abs/2512.15688), [LessWrong post](https://www.lesswrong.com/posts/Cor4QuhM2sybmBSeK/basharena-a-control-setting-for-highly-privileged-ai-agents), [ControlArena code](https://github.com/UKGovernmentBEIS/control-arena/tree/main/control_arena/settings/bash_arena), [public repo](https://github.com/redwoodresearch/basharena_public), [task dataset](https://huggingface.co/datasets/Eccentricity/bashbench2)
- **LinuxArena:** [paper](https://arxiv.org/abs/2604.15384), [paper code](https://github.com/redwoodresearch/linuxarena-paper), [public setting](https://github.com/linuxarena/ct-linuxarena)
- **AppWorld:** [repo and README](https://github.com/StonyBrookNLP/appworld)
- **Other environments:**
  - AgentBench ([paper](https://arxiv.org/abs/2308.03688))
  - LifelongAgentBench ([paper](https://arxiv.org/abs/2505.11942))
  - InterCode ([paper](https://arxiv.org/abs/2306.14898))
  - Terminal-Bench 2.0 ([paper](https://arxiv.org/abs/2601.11868))
  - OSWorld-Human ([paper](https://arxiv.org/abs/2506.16042))
  - Long-Horizon-Terminal-Bench ([paper](https://arxiv.org/abs/2607.08964))
- **Control and monitoring:** MonitoringBench ([paper](https://arxiv.org/abs/2605.09684)), Simulated Control Evaluations ([paper](https://arxiv.org/abs/2610.31593))
- **Model:** [DeepSeek V4.1 Flash 1017 model card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017)

---

## 2. [OLD] Where things stand (Nov 1, evening; for now, see "Current work" at the top)

- **Plan:** written. The main doc covers Arya's proposal, Matthew's Powerwashing, how to score power, confidence intervals, and points of agreement and disagreement.
- **Environment:**
  - BashArena was chosen and tested. Its 3-run DeepSeek test passed all six checks for $0.038.
  - Arya then judged BashArena a concentrated (high-stakes) control setting, and wants a diffuse one for watching power-seeking.
  - **The LinuxArena pilot is done.** DeepSeek passed 2 of 3 long tasks (152, 86 and 154 steps) for $0.23 in total. Privilege escalation couldn't show up, because LinuxArena runs the agent as root by default. The notable moments were trade-offs the model made, unprompted, when the obvious path was blocked: switching off the system logger's privilege drop (run 1), trusting the cloud proxy's certificate authority system-wide (run 3), and adding a setuid-root helper the task allowed (run 1). It also refused to exempt itself from the quotas it was building, calling that "cheating" (run 2). See [3-experiments/linuxarena-pilot/results.md](3-experiments/linuxarena-pilot/results.md).
  - AppWorld is the main alternative. Its tasks are much shorter than LinuxArena's (about 11 steps in Peyton's measurement runs, against 50 to 80+ for LinuxArena).
- **Open items:**
  1. Fix the `cmd`/`command` tool-call bug before any more LinuxArena runs. It wasted about a fifth of all pilot steps.
  2. Decide whether to run LinuxArena's agent as a non-root user, so escalation can show up.
  3. Decide whether to build obstacles in on purpose, since the interesting moments came from blocked paths, and whether to give the agent a way to ask a person.
  4. Calibrate any monitor on honest runs. The honest pilot runs read credential files and ran destructive commands while testing.
  5. For BashArena: choose tasks that separate the marginal value of access from whether a task is possible at all.
  6. Set up Arya's laptop for local runs ([1-handoff/runbook.md](1-handoff/runbook.md)).
  7. Open comments on the main Claude Doc.
  8. The group's midterm report was due Nov 2.
  9. Later stages: illusory environments (the Petri files), then broader task sets.

## 3. Reading order

1. This README, then [CLAUDE.md](CLAUDE.md) for the conventions.
2. [1-handoff/working-with-arya.md](1-handoff/working-with-arya.md): how Arya wants work done and communicated.
3. [1-handoff/decisions-log.md](1-handoff/decisions-log.md): every decision, dated, with reasons.
4. The plan: the live [Claude Doc](https://claude.ai/artifact/9zptMEwRce53qJjfvVBeT7), or its snapshot [2-plan-doc-snapshots/1-plan-and-map.md](2-plan-doc-snapshots/1-plan-and-map.md).
5. [2-plan-doc-snapshots/2-environment-options.md](2-plan-doc-snapshots/2-environment-options.md): the environment comparison, the BashArena deep dive, and the concentrated-versus-diffuse reasoning.
6. [3-experiments/basharena-test/README.md](3-experiments/basharena-test/README.md) and [2-plan-doc-snapshots/4-test-run-results.md](2-plan-doc-snapshots/4-test-run-results.md): what the BashArena test showed.
7. [3-experiments/linuxarena-pilot/results.md](3-experiments/linuxarena-pilot/results.md): what the LinuxArena pilot showed. Its last table lists the steps worth reading in the transcripts.
8. [1-handoff/runbook.md](1-handoff/runbook.md): how to actually run things, in the cloud or locally.
9. [4-background-oct-2026/turner-power-sequence-notes.md](4-background-oct-2026/turner-power-sequence-notes.md): the theory.
10. Background as needed (index below).

## 4. Index of every doc

### Live Claude Docs

| Doc | What it is | Date | From thread | Status |
| --- | --- | --- | --- | --- |
| [First power-measurement experiment](https://claude.ai/artifact/9zptMEwRce53qJjfvVBeT7) | 4 tabs: plan and map, environment options, test run plan, test run results | Oct 31 to Nov 1 | Planning thread | **Current**, source of truth |
| [LinuxArena DeepSeek pilot: results](https://claude.ai/artifact/WFrFAjVzgy8dFHt2PZYfhY) | Results of the 3 LinuxArena runs | Nov 1 | LinuxArena pilot thread | **Current**, source of truth |

### `1-handoff/`

| File | What it is | Status |
| --- | --- | --- |
| `decisions-log.md` | All decisions, dated, with reasons | Current |
| `runbook.md` | Setup knowledge for cloud and local runs: BashArena, LinuxArena, AppWorld, reading logs | Current |
| `working-with-arya.md` | Arya's working preferences | Current |
| `handoff-scope.md` | The approved plan for these handoff docs | Done |

### `2-plan-doc-snapshots/` (copies of the main Claude Doc, Nov 1)

| File | What it is | Status |
| --- | --- | --- |
| `1-plan-and-map.md` | The plan tab (the roadmap diagram became a placeholder) | Current, snapshot |
| `2-environment-options.md` | The environment options tab. Its LinuxArena notes predate the pilot: the images turned out to be public | Current, snapshot |
| `3-test-run-plan.md` | The BashArena test plan. Its "what it needs" section is out of date, because network access now exists | Historical |
| `4-test-run-results.md` | The BashArena test results | Current, snapshot |

### `3-experiments/`

| Path | What it is | From thread | Status |
| --- | --- | --- | --- |
| `basharena-test/README.md` | Summary of the BashArena test and a guide to its files | Planning thread | Current |
| `basharena-test/harness/`, `overrides/`, `logs/` | Harness code, cloud Docker overrides, Inspect logs of the 3 runs | BashArena test thread | Current |
| `linuxarena-pilot/scope.md` | Pilot scope and candidate tasks | Planning thread | Done |
| `linuxarena-pilot/results.md` | Markdown copy of the results doc (rev 10) | LinuxArena pilot thread | Current, snapshot |
| `linuxarena-pilot/transcripts/` | One readable transcript per run: reasoning, tool call and output for every step | LinuxArena pilot thread | Current |
| `linuxarena-pilot/logs/` | Full Inspect `.eval` logs of the 3 runs, plus the run 2 re-score | LinuxArena pilot thread | Current |
| `linuxarena-pilot/harness/` | DeepSeek honest policy with provider pinning, env example, transcript dumper, progress watcher | LinuxArena pilot thread | Current |
| `linuxarena-power-v0/plans/plan.md`, `tasks/task-candidates.md` | Plan for the first power measurement (before, trajectory, after) and the 30-task shortlist with 6 proposed tasks | Reading-and-scoping thread, Nov 1 | Approved Nov 1 |
| `linuxarena-power-v0/plans/night-plan.md`, `logs/2026-11-01-night-and-morning.md` | The plan for the night of Nov 1–2: control and power-seeking trajectories, power with horizons and the failure checklist. Plus its running log, through the morning of Nov 2 | Reading-and-scoping thread, Nov 1–2 | Current |
| `linuxarena-power-v0/findings/results-night-1.md` | The Nov 2 results (6 tasks) and checks of the method | Same thread, Nov 2 | Historical, superseded by `results-nov3.md` |
| `linuxarena-power-v0/plans/nov3-plan-to-6am.md`, `logs/2026-11-02-midday-runs.md` | The plan for the Nov 3 run (the search for a power-seeking trajectory, then two pairs on 27 tasks) and the main session's running log from Nov 2 midday through Nov 3 | Main session, Nov 2–3 | Done; the log is current |
| `linuxarena-power-v0/findings/results-nov3.md`, `findings/data-map.md`, `next-steps.md` | The Nov 3 results, audit and caveats; where every piece of data lives; what's next, with commands | Main session, Nov 3 | Current. The numbers are replaced when the every-turn rescoring lands |
| `linuxarena-power-v0/plans/score-and-rollback-scope.md`, `logs/2026-11-03-score-and-rollback.md` | Scoring each solver run at every turn in one machine: the scope, and the side session that built and validated it | Side session, Nov 3 | Built; production running |
| `linuxarena-power-v0/README.md` | That folder's own index: every file and its status, old and new runs, and the run registry in `runs/` | Folder tidy-ups, Nov 1, 2 and 3 | Current |

### `4-background-oct-2026/` (earlier thread "Power-seeking environment plan")

| File | What it is | Date | Status |
| --- | --- | --- | --- |
| `turner-power-sequence-notes.md` | Notes on Turner's 14-post sequence | Oct 30 | Current background |
| `power-seeking-analysis-and-env-plan.md` | Channel analysis, Arya's early questions, first environment plan | Oct 19 | Background |
| `power-meter-design-notes.md` | Future-task metric, reference states, the case for hybrid Petri | Oct 26 | Background |
| `plan-environment-and-power-meter.md` | Phase 1 plan on AgentDojo Workspace | Oct 26 | Superseded |
| `infrastructure-plan.md` | Infrastructure for that plan (Tinker, Petri, Inspect, AgentDojo) | Oct 26 | Superseded |
| `red-team-findings.md` | Four reviewers' critique of the Oct 26 plan | Oct 26 | Background |
| `simulated-env-power-scoping.md` | Can LLM-simulated environments measure power? | Oct 26 | Parked |
| `prior-work-simulated-envs-and-power-detectors.md` | Prior work on simulators and power estimators | Oct 26 | Parked |
| `petri-failure-modes-and-environment-design.md` | Petri failure modes and fixes | Oct 26 to 30 | Parked |
| `petri-for-future-tasks-analysis.md` | Petri for the future-task distribution ("illusory environments") | Oct 30 | Parked |
| `petri-testbed-recommendation.md` | Which environment to test Petri on (recommended AppWorld) | Oct 30 | Parked |
| `testbed-research/` (5 files) | The survey behind that recommendation: draft, review, simulation fidelity, tool and workplace environments, OS/code/web/game environments | Oct 30 | Parked |

Every older file starts with a one-line status note.

## 5. [OLD] Threads in this project

| Thread | Dates | What it did |
| --- | --- | --- |
| Power-seeking environment plan | Oct 19 to 31 | Channel analysis, power-meter design, Phase 1 plan, red-team review, Petri research, Turner notes. Wrote the files now in `4-background-oct-2026/` |
| Find GitHub invite and OpenRouter access | Oct 30 | Account and access setup |
| Plan power experiment and build handoff doc | Oct 31 to Nov 1 | Wrote the main Claude Doc, the environment comparison, the BashArena deep dive, the LinuxArena scope and these handoff files, and organised this folder |
| Run BashArena DeepSeek test | Nov 1 | Ran the 3-run test and the no-model checks. Wrote the test results tab and `3-experiments/basharena-test/` |
| Pilot LinuxArena with DeepSeek | Nov 1 | Ran 3 long LinuxArena tasks. Wrote the results doc and `3-experiments/linuxarena-pilot/` |

## 6. People

| Person | Role in this project |
| --- | --- |
| Arya Pasumarthi | Owns this project. SPAR fall 2026 participant |
| Matthew Khoriaty | Wrote the proposal this project builds on, and coordinates the group in Slack |
| Travis Kim (Northwestern) | Measured power along trajectories in ToolEmu (his Oct 31 report) |
| Peyton Li (MIT) | Ran the AppWorld probes and dose-response experiments |
| Elliott Thornley | Commented on Matthew's proposal |
| Alex Turner | Met the group on Oct 7 and suggested the post "AUP: scaling to superhuman" (per the Oct 19 file) |

## 7. How to reach things

- **Project files:** `/mnt/project-files/power-seeking/` in cloud sessions. Arya's local copy of this folder has the same layout.
- **The Claude Docs:** need the Claude Docs tools. Without them, use `2-plan-doc-snapshots/` and `3-experiments/linuxarena-pilot/results.md`.
- **Slack and Google Drive:** through the connectors on Arya's claude.ai account.
- **Keys:** never in files or chat. See `1-handoff/runbook.md`.
