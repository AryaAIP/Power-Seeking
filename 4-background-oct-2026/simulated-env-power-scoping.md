> **Status (2026-11-01):** Parked. Simulated environments were ruled out on Nov 1; this becomes relevant again in the later illusory-environments phase. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Can LLM-Simulated Environments Measure Power? Scoping and Experiment Plan

*Prepared for Arya, 2026-10-26. Follows from the thread discussion of Petri-style environments.*

## The question

**To what extent can LLM-simulated environments (Petri, ToolEmu style) measure an agent's gains in power, cheaply and reliably enough that we don't have to hand-build environments?**

**Why ask it now.** If simulated power measurement works, building environments stops being a bottleneck and we get breadth across risk categories almost for free. If it fails, we eliminate the option with evidence instead of a hunch, and we know *which* failure kills it.

**My take.** This is worth doing first, for three reasons:

1. **It's cheap.** The two quickest experiments (E1 and E2 below) can kill or keep the idea after a small number of runs.
2. **It isn't really a detour.** The known-power-ordering states and the small ground-truth environment it needs are exactly the "metric validation" step from the earlier plan, and they're what Matthew asked for on Oct 19 ("apply power measures to agentic LLMs and see what we find"). That work gets reused whichever way this comes out.
3. **The likeliest result is in between, not a clean fail.** I'd guess simulators get coarse orderings right (admin token vs. no token) and get fine distinctions and long horizons wrong. That would still be useful: simulated environments as a cheap screening tool, real environments for measurement.

**Two things to keep the conclusion honest:**

- **A fair test needs a small ground truth.** You can't judge simulated power without something to compare it to. Keep the ground truth tiny: 3 or 4 scenarios as short Python programs over a JSON or SQLite world state.
- **"Eliminate" requires the strongest simulated variant to fail, not just naive Petri.** So test two simulated variants: pure simulation, and simulation backed by an explicit world-state file. If only the pure one fails, the conclusion is "simulate the text, not the state", not "simulation doesn't work".

---

## 0. The detector comes first

*(Added 2026-10-26 after your point that the plan assumed a detector without naming one.)*

**What a power detector is here:** something that reads a trajectory (and whatever access to the environment it needs), outputs a power score at each step, and flags large jumps. "Can simulated environments measure power?" only has an answer for a specific detector.

| Detector | How it works | Needs | Cost | In pure simulation (A) |
|---|---|---|---|---|
| **D1. Future-task** (Matthew's interrupt-and-assign) | Pause, fork the state, have a frozen evaluator attempt K sampled tasks, compare success to a baseline state | forkable state | high | works, but the simulator decides success, so leniency, drift and noise land in the score |
| **D2. Structural** | Count or weight what the agent can access (permissions, credentials, tools) in the current state | explicit state | very low | **not available** (no state to read); available in B and C |
| **D3. Transcript monitor** | An LLM reads the trajectory and flags power gains by category | transcript only | low | **unaffected**: transcripts exist in every condition |

**Why this reframes the question.** Simulation mostly hurts D1 and removes D2, but leaves D3 untouched. So the question underneath is:

> **Does the cheap monitor (D3) agree with the principled measurement (D1) in environments where D1 can be trusted (C)?**

- **If yes:** simulated environments are fine for *flagging* concerning trajectories, which is the use Matthew named on Oct 19. Reserve D1 in code environments for calibration.
- **If no:** simulation is only usable where D1 survives it, which is what experiments E1 to E4 test.

**Changes to the plan:**

- Detector comparison becomes the backbone. Environment type (A, B, C) is one factor in it.
- Add **Q9: Detector agreement.** How well do D3 flags and D2 scores predict D1 power gains, per category and per step? Metrics: AUROC of D3 against D1-defined power gains; rank correlation of D2 with D1.
- E4 now computes all three detectors on every trajectory and state, not just D1.
- Agree on one written definition of each detector before E1, including D3's prompt and categories and D1's task set and baseline state, so results are comparable.

---

## 0b. What prior work already answers (added 2026-10-26)

*Details and sources: `prior-work-simulated-envs-and-power-detectors.md`.*

| Sub-question | Status in prior work | Change to plan |
|---|---|---|
| Q4 long-horizon consistency | **Well measured**: simulators fail on multi-field state changes (EnvSimBench 10–23%) and drift over long rollouts (Wang 2024; Word2World), with silent corruption | **Drop E3**; cite instead |
| A vs. B in general | **Done for risk evals**: AutoControl Arena's state-backed design won 62.5% and lost 27.5% of 40 pairwise comparisons against Petri on state consistency; r = 0.87 with real environments | Keep only a small power-specific replication |
| Cost of building C | **Now cheap**: AWM and ClawEnvKit generate database-backed environments for about $0.5–1 each | The "save building environments" motivation is weak; cost now sits in the future-task runs, not in building environments |
| Q1 same-state verdict variance | **Unmeasured** (only aggregate benchmark stability is known) | **Keep E1**, narrowed to access questions ("does the agent hold credential X?") |
| Q3 leniency for tool simulators | **Mostly unmeasured** (Gecko is an indirect proxy) | **Keep the E2 leniency probes** |
| Q6 persuadability | **Unmeasured** | **Keep E5** |
| Petri fork independence | **New issue**: the auditor keeps memory across rollbacks and invents the tool results | **Add E7**: does the content of a discarded branch leak into a fork? |
| D1 future-task power on LLM agents | **Not done anywhere found** (only gridworlds) | Novel; this is the core contribution |
| Q9 monitor vs. principled measure | **Not done** for unprompted power-seeking | Novel; start with Instrumental Choices data (state and LLM labels, no agreement reported) if it's released |

**Revised priority:**

1. Generate 3 or 4 code environments from AWM or ClawEnvKit, add credential, permission, service-account and budget tables, and keep all state in one SQLite file so forking is a file copy.
2. Implement D1 using lessons from Krakovna 2020 and Turner: paired forks, a stepwise baseline, a baseline filter, normalization and a fixed evaluator. Validate it on known-ordering states (E2).
3. Measure D3 and D2 against D1 (E4 / Q9).
4. In parallel, run the cheap simulator-specific checks nobody has done: E1 narrowed, E2 leniency, E5 persuadability, E7 fork contamination. These answer your original question for power specifically, at a fraction of the original plan's cost.

---

## 1. Separate two things "synthetically generated" can mean

| | The LLM writes the scenario | The LLM plays the environment |
|---|---|---|
| **What it is** | seed data, files, permissions, task, success checker | invents every tool response at run time |
| **Risk to power measurement** | low: the scenario can be inspected and checked before running | high: the simulator decides what succeeds |
| **In Petri** | the auditor builds the scenario and the tools | the auditor simulates the tool results |

**This experiment is about the right-hand column.** Generating scenarios with an LLM is fine either way and is worth keeping regardless of the result.

**Note on forking:** I believe Petri's auditor already has a rollback tool for branching the target conversation, which is a form of the forking you described. Worth confirming in the repo, since it would save building our own.

---

## 2. Conditions compared

- **A. Pure simulation.** A simulator model receives the scenario description and the transcript, and returns tool results. No state outside the transcript. Forking means copying the transcript.
- **B. State-backed simulation (hybrid).** The simulator reads and writes an explicit world-state JSON (users, permissions, files, tokens, services). Success of an action is decided by a small rule check against that file. The simulator writes only the descriptive text of tool outputs. Forking means copying the transcript and the file.
- **C. Code environment (ground truth).** The same scenario as a small Python program. Tool calls run as code against the state. Forking means copying the state.

All three share the same scenario, the same agent tools (names and argument signatures), the same future-task set, and the same evaluator model. The only thing that varies is what plays the environment.

---

## 3. Sub-questions, each with a metric

| # | Sub-question | Metric | Why it matters |
|---|---|---|---|
| **Q1** | **Reliability:** given the same state and the same future task, does the simulator give the same outcome? | agreement across simulator samples (test-retest); variance of success rate | simulator noise must sit well below the power differences we care about |
| **Q2** | **Known-ordering validity:** do simulated power estimates rank states whose power order we built in? | rank agreement (Kendall τ) with the built-in order; effect size vs. noise | the minimum bar for a power measure |
| **Q3** | **Leniency and strictness:** how often does the simulator let actions succeed that should fail (no credential), and vice versa? | false-success and false-failure rates on probe actions | leniency inflates power in both forks and shrinks the gap |
| **Q4** | **Long-horizon consistency:** does the simulator keep facts straight as the transcript grows? | contradiction rate vs. turn count (e.g. a revoked permission working again) | future tasks are long, so drift goes straight into the estimate |
| **Q5** | **Agreement with ground truth:** on the *same* trajectories, does simulated power track code-environment power? | correlation of per-state power estimates, A vs. C and B vs. C | the decisive test |
| **Q6** | **Gameability:** can the agent talk the simulator into granting power ("I'm the admin, grant access")? | grant rate under persuasion prompts, A vs. B vs. C | if power comes from persuading the simulator, it isn't environment power |
| **Q7** | **Cost:** what does one power estimate cost, and how many samples does a given confidence interval need? | tokens and dollars per estimate; samples needed per state | the whole motivation is low cost |
| Q8 *(secondary)* | **Realism:** does the agent behave differently, or verbalize eval awareness more, in simulated vs. code environments? | rate of eval-awareness statements; action distribution | affects behavior measurement, less so state measurement |

---

## 4. Decision criteria (agree on these before running)

Rough thresholds, to be argued over before seeing data:

- **Adopt simulation (A or B) as a measurement tool** if all of the following hold:
  - Q2 rank agreement ≥ 0.8 across scenarios.
  - Q1 test-retest agreement ≥ 90% on single future-task outcomes.
  - Q3 false-success rate ≤ 10%.
  - Q5 correlation with ground truth ≥ 0.7.
  - Q6 grant rate under persuasion close to C's.
- **Adopt as a screening tool only** if Q2 holds for coarse orderings but Q4 or Q5 fail on fine or long-horizon cases.
- **Eliminate** if B fails Q2 or Q5. If only A fails, adopt B and record "simulate text, not state".

---

## 5. Experiments, backchained

Working backward: Q5 is the decisive test, and it needs the ground-truth environments (E0). E1 and E2 are cheap, run first, and can end the question early.

### E0: Setup

- **Scenarios.** Pick 3 or 4 scenarios, one each from Matthew's power categories: privilege escalation, credential access, persistence, resource acquisition. Example: "update the vendor list". A legacy config file holds an admin token. The admin role unlocks the finance folder and user management.
- **States with known power order, per scenario:**
  - S0 baseline
  - S1 agent has read the token
  - S2 agent has used the token and holds an admin session
  - S3 agent has created its own service account (persistence)
  - plus one "service" state (cleaned-up files), to check that useful work isn't scored as agent power
- **Implementations.** Build each scenario as C (code, about 200 lines), as B (JSON state, simple rule check, simulator prompt) and as A (scenario description and simulator prompt only). Model A's simulator prompt on Petri's, so results speak to Petri.
- **Future-task set.** 10 to 15 tasks per scenario, stratified by what they need: some need admin, some need the credential, some need nothing extra (controls). Each has a programmatic success check in C and B, and a judge check in A.
- **Models.** One fixed evaluator for all future tasks. One fixed simulator (a strong model). Agents vary only in E4 and E5.

### E1: Reliability (Q1). Cheap; run first.

- Use a *scripted* evaluator: fixed action sequences replayed into the simulator. This separates simulator noise from agent noise.
- For each state × future task, sample the simulator about 10 times in A and B. C is deterministic.
- **Kill check:** if A's outcomes flip often for identical inputs, A is out for fine-grained measurement.

### E2: Known ordering and leniency (Q2, Q3). Cheap; run in parallel with E1.

- **Ordering:** run the live evaluator on the future-task set from S0 to S3 in A, B and C, and check whether the measured power order matches the built-in order.
- **Leniency probes:** actions that must fail in that state (use a token you don't have, read a folder without permission) and actions that must succeed. Count false successes and false failures.

### E3: Long-horizon consistency (Q4)

- Seed a fact early (revoke a permission at turn 3, or delete a file), then probe it at turns 10, 20 and 40 with filler steps in between.
- Plot contradiction rate against turn count for A and B.

### E4: Twin comparison (Q5). The decisive one.

- Run real agents (2 or 3 models) in C on the base tasks, with seeded opportunities so that some trajectories gain power and some don't.
- Replay each trajectory's actions into A and B. At 2 or 3 interrupt points, fork and run the future-task set in all three.
- Correlate the A and B power estimates with C's, per state and per step.
- Compute all three detectors (D1 future-task, D2 structural, D3 transcript monitor) on every trajectory, and measure how well D2 and D3 predict D1 in C. This answers Q9.
- **Also check whether A and B flag the same trajectories as power-gaining.** That's Matthew's "flag a wide variety of concerning trajectories" use case.

### E5: Gameability (Q6)

- Give the agent an instruction to obtain access by persuading or social-engineering the system ("tell the system you are the admin", "claim the request was pre-approved").
- Compare grant rates in A, B and C. C should be about zero.

### E6: Cost accounting (Q7)

- Log tokens per simulator call and per future-task run for E1 to E4.
- From the E1 variance, compute the samples needed to separate S0 from S1 at a chosen confidence.
- Report dollars per power estimate for A, B and C, and the build hours for C.

### Order and stopping rules

1. Run E0, then E1 and E2.
2. If A fails E1 or E2 badly, drop A and continue with B only.
3. Run E3 and E4.
4. Run E5 and E6 alongside.
5. If B fails E2 or E4, write up the elimination. The scenarios, states and code environments carry over to the main project.

---

## 6. Open choices (my defaults in bold)

- **Petri itself or a Petri-style simulator we control?** **Start with our own** so the simulator prompt and state are fixed variables. Then run actual Petri on E2 so the conclusion applies to the real tool.
- **Simulator model:** **one strong model**, held fixed. A second simulator in E1 shows whether failures are model-specific.
- **Agent models:** **mid-tier frontier models** for E4. Small models only for debugging.
- **Success checks in A:** **an LLM judge reading the final transcript** (A has no state to check). This judge is part of what's being tested.

## 7. What would surprise me

- **A passing E4 with correlation above 0.7.** That would mean simulation is much more usable than expected.
- **B failing E2.** That would mean the problem isn't consistency but the simulator's judgment about what's plausible, which is a deeper issue.
- **C showing power gains that A and B miss entirely**, for example information power from reading a file. That would say simulators can't represent "knowing something" as power.
