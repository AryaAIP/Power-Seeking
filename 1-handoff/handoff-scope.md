# Handoff docs: scope for approval

*Drafted 2026-11-01 for Arya. Nothing below has been added yet. This is the proposal.*

The goal is that a new Claude, or any other agent, can read the docs and get fully up to speed without asking you anything. They should also be able to trace every claim back to where it came from. Following your note, I'll keep the docs we already have and add a few new ones around them, instead of merging everything into one new doc.

## What exists today

| Where | What | Status |
| --- | --- | --- |
| `power-seeking/*.md`, 11 files (Oct 19–30) | Earlier thread "Power-seeking environment plan": channel analysis, power-meter design, Phase 1 plan, infrastructure plan, red-team review, Petri and simulated-environment scoping, prior work, Turner notes | Background. Several recommendations are now out of date (Petri, simulated environments, ToolEmu, AgentDojo, Tinker) |
| `power-seeking/testbed-research/`, 5 files (Oct 30) | Environment survey for the Petri test | Background |
| Claude Doc "First power-measurement experiment: plan and map", 4 tabs (Oct 31–Nov 1) | Plan and map, environment options, BashArena test plan, test results | Current |
| `power-seeking/basharena-test/` | Harness code, Docker overrides, logs from the 3 runs | Current |
| `power-seeking/linuxarena-pilot/scope.md` | LinuxArena pilot scope | Current, pilot running |

## The gaps

1. **No starting point.** Nothing says which docs exist, what order to read them in, or which are current and which are out of date.
2. **The original sources aren't listed anywhere I can point to.** The main doc has no Sources section, and the sources I read at the start are scattered or missing.
3. **Your decisions live only in chat.** For example: no ToolEmu, no simulated environments, no building environments, no side tasks, DeepSeek V4.1 Flash as the solver, 3-run caps, BashArena chosen and then the pivot to LinuxArena.
4. **The concentrated-versus-diffuse reasoning behind the LinuxArena pivot is only in chat.** I also promised to add it to the doc.
5. **Practical setup knowledge is mostly in chat.** That covers the cloud box's limits and workarounds, what your laptop still needs for local runs, provider and token-limit settings, how to read the run logs, AppWorld facts, and how LinuxArena is packaged.
6. **How you like to work is only in chat.** For example: plain words, explain every term, show arguments for and against and decide together, scope first and wait for your go-ahead. Project memory is off, so nothing carries this forward.
7. **Agents without the docs tools can't read the Claude Doc.** A Claude running locally, or in a session without the docs connector, sees only the files.
8. **There's no record of who's who or of which thread did what.**

## What I'd add

**New files in `power-seeking/`:**

1. **`README.md`, the starting point.** It opens with a **literature review** that links every source I used to get context at the start, each with one line on what it contributed. I'll note honestly which ones I actually opened and which I only saw linked. After that: the project goal in a few lines, where things stand as of today, a reading order, an index of every doc (date, which thread made it, current or out of date), a map of the five threads, the people involved, and what's open next.
2. **`decisions-log.md`.** Every decision so far, dated, with the reason and who made it.
3. **`runbook.md`.** Practical setup knowledge in one place: the cloud workspace's limits and fixes, the local-run checklist, model and provider settings, the token limit, run time and cost figures, how to read Inspect logs, BashArena and LinuxArena setup notes, and key handling. No keys go in any file.
4. **`working-with-arya.md`.** How you like work done and communicated, so a new agent starts out right.
5. **`2-plan-doc-snapshots/`.** A dated Markdown export of each Claude Doc tab, so agents without the docs tools can read them. The live doc stays the source of truth.

**Changes to existing material (small, additive):**

6. **A one-line status note at the top of each older file**, for example "Background; the recommendation to use Petri was replaced on Nov 1, see decisions-log.md". No other text in them changes.
7. **In the Claude Doc:** add the concentrated-versus-diffuse section and the LinuxArena decision to the Environment options tab, plus a short sources section on the main tab.

## Sources for the literature review

I opened all of these at the start of this thread unless marked otherwise:

- **Travis Kim**, "Measuring Power Along Agent Trajectories in ToolEmu", SPAR progress report, Oct 31 (Google Doc 17olc1…)
- **Matthew Khoriaty**, "[DRAFT] Shaping LLM Personality via its Behavior on Future Tasks", with its comment threads (Google Doc 148Z2…)
- **Slack #alignment-without-personas** (SPAR workspace): threads from Peyton Li, Matthew and Travis, Oct 26–31; the Oct 26 huddle notes; Peyton's `dose_response_v2.md`; the midterm-outline thread
- **Turner's sequence** "The Causes of Power-seeking and Instrumental Convergence", all 14 posts, plus the AUP concepts post and his research page
- **Victoria Krakovna's** AI safety resources page and papers: side effects, future tasks, and power-seeking being probable and predictive
- **Turner's power papers**, plus the other papers cited in the main doc. I'll pull exact titles from the record when building.
- **The earlier thread's 11 research files**, which themselves cite the Slack channel, Peyton's Oct 17 thread and two arXiv papers
- **Not opened by me:** the shared "thoughts" doc you linked in the earlier thread (Google Doc 1YBz5…) and the midterm outline doc (1erDP6…). I'll link them and mark them as such.

## Not included

- No API keys or credentials, anywhere.
- No raw command logs from the runs that probed permissions. Those stay summarised in prose, as they are now.
