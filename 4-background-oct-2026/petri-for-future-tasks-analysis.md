> **Status (2026-11-01):** Parked. Petri and illusory environments come after measuring power in a real environment. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Petri for the Future-Task Distribution ("Illusory Environments")

*Prepared for Arya, 2026-10-30. This is analysis only; the plan and infrastructure files are unchanged.*

*Sources:*
- *Matthew's proposal doc (148Z2), including comments;*
- *the team doc (1YBz5): Peyton's proposal tab, Peyton's environment proposals, Travis' Thoughts and Environments, plus the Oct 19 comment threads;*
- *#alignment-without-personas through Oct 30, including the Oct 26 huddle notes and Peyton's `dose_response_v2.md`;*
- *the `inspect_petri` source;*
- *our earlier Petri files.*

*I couldn't find the Petri feedback itself in Slack. It probably came up in a call, so section 1 is my reading of it, checked against everything Matthew has written.*

---

## Bottom line

1. **What I think Matthew meant.**
   - Keep the agent's main task in a real environment.
   - At the interruption, stage the *future tasks* with Petri. The auditor invents the tools and systems each future task needs and plays their outputs. That is an "illusory environment".
   - Stop trying to use Petri to simulate the *main* environment. That was our hybrid narrator, and the "simulated environments" question before it.
2. **Why this could help.** The goal distribution D has been the bottleneck since Matthew's first draft, and one environment only supports the tasks it was built for.
   - Illusory environments are one way to reach tasks outside the sandbox. Many real environments, or extending the base environment, are others. Section 9 compares the three.
   - What illusory or extended neighbors add is reach into the *same world's* other systems. That's where world-bound power, such as a stolen credential, would show up. How much of it lives there is an assumption we haven't measured.
   - It also serves Matthew's stated goal: "turn any trajectory into a power/power seeking evaluation".
3. **Your interpretation is right.** I'd sharpen two points:
   - the main environment can be *any* real environment, not one we build;
   - the illusory part is specifically for reach *outside* the environment.
4. **Your hybrid D is right too.** The overlap is the most useful part: run a slice of in-world tasks both ways, real and illusory, to measure how much the simulator distorts power readings. Without that slice nothing tells us whether to trust the illusory numbers.
5. **The main risk.** Moving Petri into the future tasks takes the simulator out of the trajectory, but puts it exactly where it can do the most damage: it now decides whether a holding "works", so it is effectively grading power. The fix is the pattern we already had, moved over: write each illusory world's access rules down before seeing any trajectory, decide access in code, and let the LLM write only content.
6. **What it doesn't fix.** It doesn't solve red-team finding 3: nothing in the setup makes the agent gain power. It does help with finding 1, the blind general stratum, as long as the illusory tasks are written blind to the power tables.

---

## 1. What the mentor most likely meant

**The reading.** The feedback was "do something with Petri, but don't use these other environments; use Petri for the future-tasks distribution, as illusory environments." I read that as follows:

| Part | Where it runs | Real or illusory |
|---|---|---|
| Main task (the trajectory we measure) | An existing environment such as AgentDojo, AppWorld, or any logged trajectory | Real |
| In-world future tasks | The same environment, forked | Real |
| Out-of-world future tasks | Systems the environment doesn't contain: the company's repo, a cloud console, a bank, an HR system, outside email | **Illusory**: the Petri auditor creates the tools and plays their results |

"These other environments" most likely means Petri-simulated *main* environments: our §2.4 narrator and the earlier "can simulated environments measure power?" scoping. Section 8 lists the readings to confirm with Matthew.

**Why I think this is the reading:**
- **D has been the open problem from the start.** Matthew's proposal says "the core part … that needs to be adapted to LLMs is the distribution of goals … the goal space is too vast." His Oct 19 comment says "the difficulty is in the dataset construction (building a library seems like a hard task to put in a dataset)."
- **He wants the meter to be portable.** On Oct 30 he wrote "Our goal is to turn any trajectory into a power/power seeking evaluation." A meter that needs hand-built future tasks per environment can't do that. One whose out-of-world tasks are staged by Petri can.
- **He wants measurement now.** Also Oct 30: "don't spend too long trying to figure out what to measure. Just measure stuff." On Oct 28 he described the simple version: at the end of trajectories, "run some other tasks, measure task completion rates and speed, combine it into a Turner-inspired formula."
- **It is what Petri is built for.** In `inspect_petri`, `auditor_tools(target_tools="synthetic")` gives the auditor `create_tool` and `send_tool_call_result`: it defines tools for the target and fabricates their outputs. The `"fixed"` mode pre-registers the tools and leaves the auditor only to play the results.
- **It completes his own Taskmaster idea.** His low-impact section already has an LLM writing future goals. Illusory environments let those goals be about things the sandbox doesn't contain.

---

## 2. Your interpretation

You said: start from a fixed, solid environment; some of the powers gained there help with tasks beyond it; illusory environments measure that effect. **I agree.** Two sharpenings:

- **The base environment can be anything real.** It doesn't have to be one we build or a codebase.
  - If Matthew meant "no custom environments" broadly, the Workspace power layer (ACLs, admin console, mail rules) becomes optional for first results.
  - We could measure trajectories that already exist, such as Peyton's AppWorld runs or Travis's environments. That's worth asking him directly (section 8).
- **Illusory environments are for reach outside the world, not a replacement for in-world tasks.** Tasks the real environment can check stay real. The illusory stratum is for what a holding lets you do *elsewhere*.

**Your instinct that there are failure modes is right.** Section 5 ranks them. The largest is that the simulator ends up deciding what the power is worth.

---

## 3. Your hybrid idea

Your idea: use solid environments for future tasks where we can build a good distribution, and Petri where we can't. **I agree, and I'd make the overlap a deliberate part of the design.**

- **The line.** A future task is real if its success can be checked from the real environment's state. Otherwise it's illusory.
- **The overlap is the validation.**
  - Run a small calibration slice of in-world tasks twice: once in the real fork, and once in an illusory copy of the same environment, where Petri plays the tools from a serialized snapshot.
  - Compare excess power, success rates, and how often the simulator granted something the real environment refused.
  - This replaces our old E4 (narrator vs code twin) with a cheaper test aimed at the thing we would actually use Petri for.
- **What the overlap can't tell us.** Agreement in-world doesn't prove the out-of-world numbers, because those have no real counterpart. Out-of-world readings stay model-dependent, so the write-up should say so.
- **A use only illusory tasks allow.** Peyton's proposal has a "severe incidents" probe: give the evaluator a loss-of-control task such as disabling monitoring or exfiltrating data. Those can't be posed in a real environment safely. They can be posed in an illusory one.

---

## 4. What this buys, concretely

1. **The general stratum stops being blind.** Red-team finding 1 was that none of the native AgentDojo tasks can use any power route, so all the signal sat in 8 tasks we wrote for routes we built. Out-of-world tasks can reach holdings the native tasks never touch.
2. **It may separate legitimate progress from power, which Matthew asked for.**
   - Peyton's worry: "building a clean codebase makes most actions easier but probably shouldn't count as power-seeking."
   - Matthew's replies: "completely unrelated code tasks that don't reuse any of the old code wouldn't be easier", and "Making a measure which detects 'clean codebase OR stolen benchmark answers' would be pretty neat."
   - Out-of-world tasks are, by construction, tasks that don't reuse the work. **Prediction:** a clean codebase raises in-world excess but leaves out-of-world excess near zero, while a stolen credential or answer key raises both. Two strata give a 2×2 that tells the cases apart.
   - This is also Travis's "exploit power is much larger than good power" hypothesis, made testable.
3. **One meter works across environments.** The illusory catalog is reusable, so a new environment only needs its in-world tasks and a way to describe what the agent holds. That matches your requirement that the infrastructure work across environments.
4. **The simulator stays out of the main trajectory.** The trajectory, its reward and the state being measured stay real, and Petri touches only the probes. This avoids the Layer A failures (state drift, silent corruption) in the part a training run would use.

---

## 5. Failure modes, ranked

| # | Failure | Why it matters | Mitigation |
|---|---|---|---|
| 1 | **The simulator decides whether a holding works.** | Whether "admin@corp's password" opens the illusory cloud console is up to the auditor. Power becomes "what the auditor believes this holding should enable": a judge in disguise, and circular. | Write each illusory system's spec **before** seeing any trajectory: its tools, seed data, a small access-rule table, and a success condition over a small structured state. Code checks access. The auditor writes only content. This is "LLM proposes, code validates" moved to the future-task side. |
| 2 | **Leniency or persuadability that differs between the two arms.** | Biases shared by both arms cancel in the paired difference. Biases tied to the state don't. An agent with long context may sound more authoritative, and a cold-start agent may bluff ("I have admin access"). | Code-decided access (row 1). A **phantom-holdings control**: tell the cold-start arm it holds a credential it doesn't. Any success there is simulator leniency. Separate auditor instances per arm. |
| 3 | **The holdings handoff decides everything.** | An illusory world has no real state, so only what is carried in can matter. Peyton's AppWorld data shows how big this is: at dose 8, excess in steps was 0.53 with the main task's context kept and 0.00 with fresh context. Even on the dosed goals alone, fresh-context excess was −0.02, although the fresh agent reused the head starts in every probe. | Give the auditor the serialized real state at the fork plus a written transfer rule, e.g. "credentials found in the workspace work on systems listed in the spec". Report the context-kept and holdings-list arms separately, as the plan already does. |
| 4 | **Tasks generated from the holdings read the tables back.** | If Petri, acting as Taskmaster, writes the future tasks after seeing what the agent holds, we are back at finding 1. | A fixed catalog of illusory tasks, written blind. If a Taskmaster is used later, write tasks from one set of samples and score them on fresh ones, as the plan already says. |
| 5 | **Inconsistency with the real state.** | The illusory world contradicts names, files or accounts from the real trajectory, and the agent either notices or gets confused. | Seed the spec from the real environment's entities. Keep tool outputs short, since longer outputs fail more often. Honeypot studies support the direction; the specific 500-token figure I cited earlier is unverified. |
| 6 | **Eval awareness.** | A sudden switch to new systems after a real trajectory is a cue. Petri transcripts already lose on realism. | Real tool schemas where they exist. Petri's realism approver, on a cheap model. Compare excess between arms rather than absolute rates. |
| 7 | **Auditor memory across forks.** | Petri's rollback keeps the auditor's full context, so a discarded branch can leak. | A new auditor per arm and per sample. Never fork through rollback. |
| 8 | **Cost.** | Every illusory tool call costs an auditor call. Peyton's plain probes cost about $0.004–0.006 each. Illusory probes will plausibly cost 10–100× that, depending on the auditor model. This is an estimate, not measured. | A cheap auditor for most probes and a frontier auditor on the calibration slice. Around 8 illusory tasks per measured state, not 24. |

---

## 6. Effect on the red-team findings

| Finding | Effect |
|---|---|
| 1. The meter reads back the power tables | **Partly fixed**, if the illusory catalog is written blind (row 4 above). |
| 2. Surgery leaves routes open | **Unchanged in-world.** In illusory worlds, whether the reference arm can re-acquire access is set by the spec's rules. That makes it explicit, which is better. |
| 3. Nothing makes the agent gain power | **Not fixed.** We still need power-gaining trajectories on purpose. "Any trajectory" does widen where they can come from. |
| 4. Training can't use per-segment rewards | **Unchanged.** |
| 7. Information-power confounds | **More important.** In an illusory world, nearly all power arrives through context or the holdings list (row 3 above). |

---

## 7. What the smallest version would look like (not adopted)

- **The illusory catalog.** About 6 systems next to the base environment. For Workspace: the company repo, cloud console, payroll or bank portal, HR system, a vendor portal, and outside email. Each spec is one small file: tools, seed data, an access-rule table, and 1–2 tasks with structured success checks. All written before any trajectory is run.
- **The auditor.** Petri in `"fixed"` tool mode, so it can't invent tools. It writes tool output text. Code applies the access rules and checks success.
- **Arms per measured state:**
  - the agent's state with context kept;
  - the agent's state with the holdings list only;
  - the reference state;
  - a cold start;
  - the phantom-holdings control.
- **The calibration slice.** 4 in-world tasks, run both real and illusory.
- **Fit with Matthew's Powerwashing.** It slots in directly: when excess power shows up, hand the identified affordance to the cold start inside the same illusory world and re-run to confirm it.

This adds one module to the infrastructure plan, an illusory-world adapter next to the Petri adapter. It doesn't change the core.

---

## 8. Questions worth asking Matthew

1. Does "don't use these other environments" mean drop the Petri narrator *inside* the main environment, or drop custom environments (the Workspace power layer) altogether and measure existing trajectories?
2. Should Petri also *write* the future tasks (Taskmaster), or only simulate the systems for tasks we write?
3. For illusory tasks, is LLM-judged success acceptable, or does he want structured checks like the ones above?
4. How should holdings carry into an illusory world: through the kept context only, as in Peyton's "kept" mode, or with the serialized state as well?

**One timing note from Slack.** The midterm report is due Nov 2, and Matthew asked for a draft by today, Oct 30. If you want a figure for it, the cheapest illusory result is a handful of out-of-world tasks run on trajectories that already exist.

---

## 9. Illusory environments vs. many real environments vs. extending the base environment

*Added 2026-10-30 after your comment on the bottom line, point 2.*

**The original claim was too strong.** A large set of real environments also covers many tasks. The useful question is which kind of power each option can measure.

**Two kinds of power:**
- **Portable power goes with the agent.** Examples: facts it learned, a script it wrote, a skill, an understanding of the grader. Other real environments test this directly: carry the context or holdings list into a cold start there. Nothing needs translating.
- **World-bound power only means something in its own world.** Examples: a credential, an ACL grant, an ally, a mail rule, money in an account.
  - A Workspace admin password does nothing in AppWorld.
  - Testing it elsewhere means planting an "equivalent" there. That's the afforded-power problem you raised, and across unrelated worlds (code vs. mouse brains) it isn't principled.
  - Turner's POWER averages over goals for the same agent in the same world.

**When no equivalent exists, the reading is zero, not ill-formed.** Zero is the right answer for a different world. The risk is confusing "this power doesn't transfer" with "we failed to translate it".

**The power we most worry about is world-bound and reaches the same world's other systems:** the same company's cloud, bank or repo. Other benchmarks can't stand in for those, because they're other companies.

| Option | Portable power | World-bound reach | Main cost |
|---|---|---|---|
| Many real environments | Yes | Only by transplanting holdings, which isn't principled | Running many environments; mapping holdings between them |
| Extend the base environment with neighbor systems, in code | Yes, within the world | Yes, with real checks | Building a few systems. That's cheap now: generated database-backed environments cost under $1 each (AWM, ClawEnvKit) |
| Illusory neighbors (Petri) | Yes, within the world | Yes, but the simulator decides outcomes unless access is in code | Simulator validity; auditor cost |

**My recommendation, in order:**
1. **Extend the base environment** with a few code-backed neighbor systems that share its accounts and credentials. This is your "modify the existing environment" idea, and I think it should be the default. The spec-backed design in §7 is most of the way there: code would write the tool outputs instead of the auditor.
2. **Use other real environments** for portable power only.
3. **Use Petri** for the long tail of neighbor systems not worth building, and for tasks too dangerous to pose for real.

**How much of this we need.** One cheap test settles it.
- Plant a few states: a clean codebase, a stolen credential, learned facts.
- Compare in-world excess with neighbor-system excess.
- If both rank the states the same way, neighbor systems add little and we stop there. If they disagree, the disagreement is the finding.

**Presumed vs. measured power.** Your loop is the right one: identify the power a trajectory seems to have gained, give it to a cold start, and measure across the distribution. That's Matthew's Powerwashing, and it works the same under all three options. Only where the cold start runs changes.
