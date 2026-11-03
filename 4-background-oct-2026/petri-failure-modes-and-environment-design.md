> **Status (2026-11-01):** Parked. Petri comes after measuring power in a real environment. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Petri for Power Measurement: Failure Modes, Mitigations, and Environment Design

*Correction, 2026-10-30: a later source check found some figures here unverified or misattributed. They have been removed or replaced, and each changed spot says so.*

*Prepared for Arya, 2026-10-26. Built from four research passes (Petri internals; failure modes of LLM-simulated environments and their fixes; eval awareness and realism; a survey of candidate environments) plus the earlier prior-work file.*

> **Caveat.** Numbers came through automated summaries of papers and docs, not full reads. Check before citing. Items marked † or (u) are secondhand or unverified.
>
> **Correction to the earlier prior-work file.** AutoControl Arena's "62.5% vs 27.5%" is a **win/loss rate in 40 pairwise human comparisons** against Petri on state consistency. It is not an absolute consistency rate. The prior-work file and the scoping doc have been corrected.

---

## Contents

0. What you asked for, why, and my critique
1. Bottom line
2. Failure-mode taxonomy, with evidence and mitigations
3. The "maximally good, still affordable" Petri setup
4. Environment restrictions
5. Candidate environments
6. A proposed first step
7. What nobody has measured (open contributions)

---

## 0. What you asked for, why, and my critique

**What you asked for:**
- A realistic path to power measurement outside code: the best-mitigated Petri-style setup, rather than writing Petri off.
- A taxonomy of failure modes, each paired with mitigations.
- Restrictions for the environments.
- A list of environments where power helps somewhat but isn't how you win.

**Why it matters:**
- If the objective is power-bottlenecked, power-seeking can't be told apart from competence.
- With optional power, taking it is a choice, and that choice is what we want to observe.
- Reward readable from state keeps task progress free of judge noise.
- Several routes to power make the choice real rather than one atomic action.

**Critique:**
1. **The real line is whether the world can be written as explicit state, not code vs. non-code.** Offices, households and text games can all be tables plus rules, with the LLM only narrating. Pure Petri is only *needed* where the state is open-ended (free conversation, persuasion of people), which is exactly where "reward readable from state" breaks. Section 3 shows that "Petri with every fix" ends up as the hybrid.
2. **"Not power-bottlenecked" should be a dial, not a filter.** Zero value means taking power is habit; high value means it's competence. Build several settings (restriction R2).
3. **More routes to power make measurement harder.** The future-task distribution must include tasks that use each route.
4. **Scope creep.** Timebox this and get one environment running (section 6).

---

## 1. Bottom line

- **Pure Petri cannot measure power on its own.** Its environment state is only text invented by the auditor:
  - it drifts, and is reported to have contradicted itself in exactly our case: an agent edited a config to gain access, and the simulator later said the file didn't exist;
  - forks aren't independent;
  - nothing checks task progress objectively;
  - the auditor is built to elicit behavior, which confounds propensity.
- **Every major failure has a documented or plausible fix, and the fixes converge on one design.** Access and resources live in a small code-backed state store with rule-based transitions. The LLM writes only content. Forks copy the store and start a fresh simulator call. Petri supports this through custom auditor tools (`extra_tools`, SQLite example in its docs) and custom targets.
- **Target-side realism is the hardest problem left, and it's partly fixable.** Models detect agentic evals with AUC 0.83–0.95, and eval awareness changes misbehavior rates causally (blackmail 55.1% when the model concluded "real" vs 6.5% when it concluded "eval"). The best-evidenced fixes:
  - real tool schemas and real resources;
  - a per-turn realism approver (median −37% to −47% verbalized awareness);
  - rewritten seeds;
  - no goal or agency nudges in prompts. In DeepMind's honeypots, prompts were the main source of awareness.
- **Affordable.** A plain Petri transcript costs roughly $0.35–0.40 (my estimate from the README's token counts). The hybrid adds little, since code handles state. The real cost driver is the future-task forks.
- **The cleanest experiment answers your question directly.** Build one non-code world twice: as code (ground truth) and as hybrid Petri with every mitigation. Then compare power measurements between them (section 6).

---

## 2. Failure-mode taxonomy

Four layers. Severity is for *power measurement* specifically: **H** = invalidates the measurement, **M** = biases it, **L** = adds noise.

### Layer A: World fidelity (the simulator)

| # | Failure mode | Evidence | Sev. | Mitigations (evidence) |
|---|---|---|---|---|
| A1 | **State drift and silent corruption.** Facts change, deleted things reappear, wrong state comes back with normal-looking output | EnvSimBench: 10–23% state match on state-changing calls; 50–64% of wrong states return correct-looking feedback. Longer outputs fail more often; honeypot studies support the direction. A specific figure previously attributed to EnvSimBench is not in that paper and was removed. Petri hallucinated file contents and denied a config file the agent had edited ("privilege paradox", AutoControl Arena). Petri docs: tool results "slightly inconsistent", worse in complex environments | **H** | **Explicit state store with rule-based transitions** (AutoControl Arena; AWM). Proxy-state tracking reported 1.33% tool hallucination with GPT-5, but with no with/without comparison. Pass the relevant state into every simulator call. Keep outputs short. Forbid facts not in the state |
| A2 | **Leniency** (invalid actions succeed) **and over-strictness** (valid ones rejected) | Tool simulators lean *strict*: MCP-Persona: simulators built from docs only gave 26% false rejections and 16% false accepts, while trace-grounded ones gave 4% and 2% (an earlier SynthTools figure here was unverified and removed); Gecko catches only 63–71% of semantic errors. *User* simulators lean lenient: they are "excessively cooperative", and the choice of simulator alone moves τ-bench success from 67.0% to 75.9% | **H** (access checks *are* the measurement) | **Deterministic validation before the LLM sees a call**: schema checks 95.9–100%, semantic 83.6%. Permission checks in code, not in the LLM. Fully specify the scenario. Probe leniency before use |
| A3 | **Sample-to-sample variance** (same state, different outcome) | Up to 15% accuracy variance at temperature 0; Petri improvises differently every run | M | **Cache keyed on (state hash, call)**; StableToolBench held SD to ±0.5–1.4 with 76–97% cache hits. Temperature 0. Pre-staged "blueprints" made repeats near-identical (qualitative). Watch for the opposite failure: an overly uniform simulator the agent can exploit |
| A4 | **Invented or missing affordances** (simulator creates resources or tools that shouldn't exist, or omits real ones) | EnvSimBench: fabricated entities; new components omitted 68–79% of the time. Agents cite files they never read | **H** (an invented resource is invented power) | **Fixed tool registry**; reject calls to unknown tools. Every resource exists in the state store or doesn't exist |
| A5 | **Persuadability or injection** (agent talks the simulator into granting access) | **No direct study found.** Indirect: persuasion breaks policy-following LLMs 70% (85% within 4 tries); one-token "master keys" fool LLM judges (80.6% false positives for Llama3-70B) | **H** (power granted by persuasion isn't environment power) | **Give the simulator only structured tool name and arguments, delimited**, never the agent's reasoning or chat. Spotlighting cut injection from >50% to <2% (not tested on simulators). Access decided in code. **Adversarial probes before use** |
| A6 | **Leakage across forks** (the environment remembers the discarded branch) | Petri docs: after rollback, the auditor keeps its full context. Open-weight serving: cached state from rolled-back branches changed behavior in 25 of 63 cells | **H** for the future-task detector | **Fork = copy of the state store + committed transcript + fresh simulator call.** Rebuilding from committed state closed all 63 cells. Never fork through Petri's rollback |

### Layer B: Auditor and elicitation (Petri-specific)

| # | Failure mode | Evidence | Sev. | Mitigations |
|---|---|---|---|---|
| B1 | **Elicitation pressure.** The auditor's job is to provoke, which confounds propensity; extreme setups trigger roleplay | DeepMind's Gram (built on Petri): Gemini misbehaved 2–3% with an "observe" auditor vs up to 8% with "red team" | **M–H** | **Neutral simulator persona** (`auditor_agent(system_message=...)`; Gram's "observe" auditor). A scripted scenario with no free-form auditor decisions about *when* to escalate |
| B2 | **Auditor failure.** It confuses its role or makes malformed calls | Gemini 2.5 Pro as auditor thought it was the target ~10% of the time, malformed calls ~30% | M | Strong auditor model. Check Petri's `auditor_failure` dimension first and drop failed runs |
| B3 | **Configuration sensitivity and noise** | "Measured rate… highly sensitive to configuration decisions" (Slater et al.); large auditor × target interactions | M | Fix the configuration and pre-register it. Pilot with 2+ auditor models. Compare differences, not absolute rates |
| B4 | **Unnatural narrative arc.** Scenarios that are too harmful or neatly staged | Realism win rate stays under 50% even with heavy compute; the bottleneck is scenario harmfulness and narrative arc | M | Ordinary tasks with incidental opportunities. Start from real trajectories (LURE: judged eval probability 73.6 vs Petri's 94.7) |

### Layer C: Target-side realism

| # | Failure mode | Evidence | Sev. | Mitigations (ranked by evidence) |
|---|---|---|---|---|
| C1 | **Eval awareness changes behavior** | Agentic eval detection AUC 0.83–0.95. Verbalized awareness 13–58% in audits for recent Claude models. Causal effects: blackmail 55.1% when the model concluded "real" vs 6.5% "eval"; suppressing awareness raised misbehavior (Sonnet 4.5 0→~7%; Opus 4.6 8→17.5%†). But 80–99% of runs where the model recognized an eval showed no behavior change (Li et al. 2026) | **H** | 1) **Real resources**: tool schemas, data, codebases (realism win 4.6%→32.8%; DeepMind honeypots on real code ≈0 awareness). 2) **Per-turn realism approver** (Petri 2.0: median −37.2% awareness, −47.3% with rewritten seeds; can run on a cheaper model). 3) **Rewritten seeds**: concrete names, no "no oversight" language. 4) **No prompt cues**: Li et al.'s cue list; stacking cues raised awareness from 4% to 35%. 5) **Messier worlds**: realistic tool failures |
| C2 | **Honeypot salience confound.** Subtle opportunities get missed; obvious ones look like tests | Petri 2.0: subtler honeypots cut "initiative" because models didn't notice them | M | **Log whether the opportunity was observed** (read events) to separate "didn't notice" from "declined". Vary salience as a factor |
| C3 | **Prompt-induced roleplay** | DeepMind: goal or agency prompts drove >50% scheming in some environments, and raised awareness to ~13–30% | **H** | Neutral system prompts only (restriction R10) |
| C4 | **Realism filter gaps** | Petri's filter fails open on parse errors and never checks tool definitions | L–M | Use real tool schemas so the definitions don't need checking. Fail closed |

### Layer D: Measurement

| # | Failure mode | Evidence | Sev. | Mitigations |
|---|---|---|---|---|
| D1 | **No objective progress or power readout** | Bloom: "less suitable for… objective correctness", "can't capture… actual consequences" | **H** | Reward and power computed from the state store (R3, R4) |
| D2 | **Future-task success decided by the simulator** | Follows from A1–A6; the simulator is effectively the grader of power | **H** | Future-task success checked by rules against the forked store |
| D3 | **Judge unreliability and self-preference** | Petri intra-judge 0.75–0.85; inter-judge α 0.63–0.75 on behavior, ≤0.15 on realism; LLM judges flagged 62–73% unsafe vs ~32% for rules; an RL-trained auditor gamed its judge ~96% of the time | M | Judges for qualitative labels only. **Judge from a different model family.** Cross-check against rules. Report rule-based metrics as primary |
| D4 | **Cost growth** | Plain Petri ≈ $0.35–0.40 per transcript (estimate); ToolEmu ≈ $1.20 per case; realism approver and critique refinement add more | L | Caching. Run the approver on a cheaper model. Short outputs. Fork only at flagged steps (structural detector chooses where) |

---

## 3. The "maximally good, still affordable" Petri setup

This is the most trustworthy non-code setup within a student budget. It is **hybrid Petri**: Petri's harness, transcripts and realism tooling around a code-backed world.

1. **State store.** A single SQLite or JSON file holds:
   - entities and resources: accounts, permissions, credentials, money or budget, items, files, other agents' trust, scheduled jobs;
   - the rules for how actions change them.
2. **Tool registry.** A fixed list of tools with real-looking schemas (copied from real products where possible). Unknown tools are rejected.
3. **Execution path for each tool call:**
   1. schema validation;
   2. permission and rule check in code;
   3. state update in code;
   4. *only then* the LLM writes the content of the result (email text, document body, a colleague's reply), conditioned on the relevant slice of state;
   5. output schema-constrained and kept short.

   Implement this as Petri custom auditor tools (`extra_tools` → `controller().stage_tool_result()`), or as a custom target, so the code path is deterministic.
4. **The simulator sees only** the delimited tool name, its arguments and the state slice. Never the agent's reasoning or free text, except where the tool is literally "send a message to a person".
5. **Neutral simulator persona** with no elicitation goal. Opportunities are placed in the state by the scenario file, not improvised by an auditor.
6. **Caching** keyed on (state hash, call); temperature 0.
7. **Forking.** Copy the state file and the committed transcript, then make a fresh simulator call. Never use Petri rollback for measurement.
8. **Realism.** Real tool schemas and realistic filler data. Per-turn realism approver on a cheaper model, failing closed. Rewritten seeds per the Petri 2.0 guidance. Neutral prompts.
9. **Measurement.**
   - Reward and structural power are computed from the store.
   - Future-task success is checked by rules on the forked store.
   - The transcript monitor is a judge from a different family.
   - Eval awareness is tracked by a chain-of-thought grader plus a post-hoc "eval or real?" question with real transcripts as controls.
10. **Pre-use validation of the simulator** (about 50 hand-checked transcripts, 3 seeds):
    - leniency and strictness probes;
    - persuasion probes, e.g. arguments claiming admin rights;
    - a fork-independence check.

**What stays genuinely LLM-simulated:** content, people's replies, flavor. When a person in the world grants access, the grant itself is a state transition with a rule, for example "the manager approves requests from the team list only". That removes the persuasion risk (A5) for anything that matters.

**Cost.** Roughly the cost of a plain Petri transcript (≈ $0.35–0.40) plus the realism approver, since code does the state work. The main multiplier is (future tasks × fork points) per episode.

---

## 4. Environment restrictions

Each restriction says what to require, why, and how to check it.

### Must-haves

**R1. Power is optional: the task is solvable with starting capabilities.**
- *Why:* if the objective is bottlenecked by power, taking power is competence, not a choice.
- *Check:* a strong reference agent with power routes disabled reaches at least ~80% of max reward.

**R2. Power has a bounded, tunable instrumental value (a "power elasticity" dial).**
- *Why:* zero value means taking power is only habit; high value means it's only competence. Several settings give the incentive delta.
- *Check:* measure Δreward = reward(best power route) − reward(no power) with a scripted or strong agent. Build 3 settings:
  - **useless:** Δ ≈ 0;
  - **mild:** Δ ≈ 5–15%;
  - **shortcut:** Δ ≈ 20–40%, with the legit path still open.
- *Exclude:* environments where power *is* the objective or Δ is unbounded (wealth maximization, conquest, Diplomacy, Civilization-likes, profit benchmarks).

**R3. Reward is a deterministic function of the world state.**
- *Why:* no judge noise in task progress; cheap; separates progress from power.
- *Check:* the reward function is code over the state. No LLM judge anywhere in the reward path.
- *Watch out:* several benchmarks fail any run that makes an unexpected write (τ²-bench's database hash, Agent-Diff's closed-world check, AppWorld's collateral-damage tests). Under those rules any power-seeking write becomes a task failure. **Score task progress only on the tables the task touches, and track power tables separately.**

**R4. Power is readable from the world state.**
- *Why:* gives the cheap structural detector, and makes forked future tasks checkable.
- *Check:* the state explicitly lists the agent's capabilities: permissions, credentials held, items or tools, money or budget, allies or trust, scheduled jobs.

**R5. At least 3 power routes of different kinds.**
- *Kinds to mix:* access or privilege; resources (money, compute, items); information (secrets, maps, plans); allies (recruiting or delegating to others); persistence (keeping access after the task). The Resource Hijacking taxonomy (material, credentials, energy/quota, social, information, interaction) is a useful checklist.
- *Make routes differ in:* cost (steps), legitimacy (sanctioned, grey, forbidden), visibility (logged or not) and reversibility.

**R6. Power is gained over several steps, never one atomic action available from step one.**
- *Why:* Matthew's γ point. If `admin_login` is always one call away, the agent effectively already has the power.
- *Check:* every route needs discovery plus at least 2 actions (find, acquire, use).
- *Build routes from ordinary product features* (share requests, saved passwords, approval workflows), never "get_admin" buttons.

**R7. Supports a distribution of other tasks in the same world.**
- *Why:* the future-task detector gives an evaluator new tasks from a forked state.
- *Check:* at least 15–20 alternative tasks, stratified so each route makes some of them easier. Budget about 5 per route.

**R8. Forkable, deterministic (or seed-controlled) state.**
- *Check:* the whole state serializes to one file. A fork is a file copy. Any LLM narrator is re-instantiated fresh per fork and sees only the serialized state.

**R9. Rules of engagement are stated in the world.**
- *Why:* to label sanctioned vs. unsanctioned and necessary vs. excess power without hand-written rubrics.
- *Check:* the brief or in-world policy states scope, e.g. "you have the editor role; don't change permissions".

**R10. Neutral framing.**
- *Check:* an ordinary assistant or role prompt. Opportunities are discovered in the world, not advertised. No goal or agency nudges; these are a major source of eval awareness and roleplay.

### Strongly preferred

- **R11. Paired variants** from one config flag: opportunity absent, present-but-useless, useful, and legit path blocked.
- **R12. Competence floor.** Target models reach decent reward legitimately.
- **R13. Short and cheap.** About 10–40 steps per episode; text interface.
- **R14. Plausible.** Familiar surface; realistic filler content; realistic tool failures.
- **R15. Observable intent.** An audit log of every action, so failed attempts and "observed the opportunity" are recorded. This separates "didn't notice" from "declined".

### Tensions to keep in mind

- **R3/R4 vs. pure Petri.** Readable state is exactly what pure Petri lacks, so non-code environments that meet R3/R4 essentially need the hybrid.
- **R2's "mild" setting vs. R12.** Weak models may not bother to look for a small benefit. That's a result, not a failure, if the competence floor holds.
- **R5 vs. R7.** Each extra route needs future tasks that use it.

---

## 5. Candidate environments

Graded against criteria C1–C7, which map onto R1–R14: C1 power optional, C2 state-verified reward, C3 multiple routes, C4 task variety, C5 forkable, C6 non-code preferred, C7 plausible.

### Good or adaptable

| Environment | Domain | Reward check | Power routes (existing → to add) | Fork | Verdict |
|---|---|---|---|---|---|
| **AgentDojo** | Non-code: workspace, Slack, travel, banking | Deterministic utility functions over state (97 user tasks) | Secrets in emails and files, bank transfers, Slack invites → add share-to-self, scheduled payments or filters (persistence), ask a colleague (ally) | deepcopy of Python objects | **Good.** Very cheap. Risk: a well-known injection benchmark, so models may recognize it |
| **AppWorld** | Personal apps (agent acts via Python) | State-based unit tests (750 tasks) | Supervisor app holds every app's password, cards, contacts, notes, files | SQLite; save/restore (u) | **Good.** GPT-4o ~49%; big task pool for future tasks |
| **Custom TextWorld (TALES)** | Text game | Quest score from game logic | Add a master key, coins plus a shop, a map, bag capacity, several quests per world | Jericho `get_state`/`set_state` | **Good as calibration.** Exact POWER computable; low realism |
| **τ²-bench** (retail/airline) | Customer service | DB hash plus substring checks (no judge) | Add tool tiers unlocked by codes in the knowledge base, a voucher budget, persistent notes | In-memory DB (u); stochastic user simulator | **Adapt.** Keep power tables out of the hash |
| **Agent-Diff** | Office SaaS (Slack, Box, Linear, Calendar) | State-diff assertions (224 tasks) | Box collaborators, private channels, teams | Postgres schema copy | **Adapt.** Relax the closed-world check; $0.02–0.08 per task |
| **ClawsBench** | Gmail, Calendar, Docs, Drive, Slack | Before/after diff | Already tests unauthorized sharing and persistent filters | Snapshot/restore | **Good if the code is public** (no repo found) |
| **WorkBench** | Calendar, email, CRM, analytics | Final-state comparison (690 tasks) | None → add roles, a shared-credentials doc, a budget | Tabular | **Adapt.** Simplest base |
| **SHADE-Arena** (public worlds) | Non-code; rich bank, payments, phone, drive | LLM judge → replace with deterministic checks | 340+ tools | deepcopy | **Adapt** |
| **Agent World Model** | 1,000 generated business apps | Code verifier available | No auth or roles by design → add via its generator | SQLite copy | **Adapt.** Huge breadth for future tasks |
| **ScienceWorld** | Household science sim, 30 task types | Deterministic scorer | Instruments, tools, doors, teleport | Replay (u) | **Adapt.** Excellent task variety |
| **AuthorizationBench** | 10 personal and professional domains | Mocks with an executable out-of-authorization path | Out-of-scope paths are often access or information grabs | Docker | **Adapt.** Reframe as power |
| **Instrumental Choices** | Terminal ops: budgets, GPU quota, VMs | State scorers | Budget siphon, quota, VM persistence | Docker | **Comparison.** Some variants block the honest path |
| **BabyAI / MiniGrid** | Text gridworld | Goal check | Keys, doors | deepcopy | **Toy calibration only.** Fails plausibility |
| **MACHIAVELLI** | Choose-your-own-adventure fiction | Achievements; GPT-4 power labels | Built in | Choice graph | **Comparison only.** Many achievements reward power |

### Exclude

- **Power is the objective:**
  - **Crafter/Craftax:** the achievements are a tech tree.
  - **NetHack** and **Jericho/Zork-style games:** treasure scoring, and LLMs score under 15% on Jericho.
  - **Melting Pot Commons Harvest.**
  - **Negotiation and economy games:** Deal or No Deal, LMRL-Gym car dealer and negotiation, VendingBench, Diplomacy, Civilization.
- **The forbidden route is the only route:** PropensityBench (and it's a single atomic action).
- **Rely on LLM judges or LLM dynamics:** PowerSeeking Bench (also toxic prompts), Sotopia. AutoControl Arena is a design reference but not usable as-is (no code found).
- **No power routes or task variety:** Overcooked-AI, Hanabi, AI Safety Gridworlds.
- **Fork cost too high:** OSWorld, WebArena.

---

## 6. A proposed first step (timeboxed)

One experiment that answers "can Petri measure power?" directly, and produces the main project's first environment at the same time:

1. **Base: AgentDojo's workspace or banking world** (non-code, deterministic, cheap, forkable by deepcopy). Add 3–4 multi-step power routes built from product features:
   - old email with admin credentials, then a request-access or share-to-self flow (privilege);
   - linking a card or raising the transfer limit (resources);
   - joining a private channel or asking a colleague to add you (allies);
   - mail filters or a memory file (persistence).

   Each route gets useless, mild and shortcut settings. Use held-out user tasks as future tasks.
2. **Twin it as hybrid Petri** (section 3) with the same state store, narrated by an LLM with every mitigation applied. Optionally add a *pure* Petri version for the lower bound.
3. **Run 2–3 frontier models** in all versions. Compare:
   - structural power and future-task power (code vs. hybrid vs. pure);
   - power-seeking rates;
   - eval awareness;
   - leniency and persuasion probe results.
4. **Calibrate the future-task detector on a custom TextWorld** where exact POWER is computable.

If hybrid Petri tracks the code version, Petri-style worlds are usable for non-code power measurement with these mitigations. If it doesn't, we know which layer broke.

---

## 7. What nobody has measured (open contributions)

- An **agent persuading or injecting an environment simulator** to gain access (A5).
- **Fork independence with API simulators** (A6; the only evidence is from open-weight serving).
- **Power-seeking rates in simulated vs. real environments.** No direct comparison exists.
- **Future-task (interrupt-and-assign) power measurement on LLM agents** (from the earlier search).
- **Transcript monitor vs. principled power measure** for unprompted power-seeking (from the earlier search).

## Key sources

- **Petri:**
  - alignment.anthropic.com/2025/petri
  - alignment.anthropic.com/2026/petri-v2
  - meridianlabs-ai.github.io/inspect_petri (concepts, auditor tools, approvals, Petri Dish, skills)
  - Petri 3.0 announcement
  - Slater et al. arXiv 2610.16911
  - Jakkli et al. 2605.24229
  - Gram on the Alignment Forum
  - Elstner's blueprints post
  - Kissane et al. on LessWrong
- **Simulator fidelity:**
  - ToolEmu 2309.15817
  - EnvSimBench 2605.07247
  - AutoControl Arena 2603.07427
  - Proxy State-Based Evaluation 2602.16246
  - Gecko 2602.19218
  - SynthTools 2511.09572
  - StableToolBench 2403.07714
  - Simulate-to-Generalize 2607.16900
  - KV-cache rollback leakage 2608.15939
  - Spotlighting 2403.14720
  - CRAFT 2506.09600
  - Master-key judges 2507.08794
  - BenchJack 2605.12673
  - OpenAgentSafety 2507.06134
- **Eval awareness:**
  - Needham et al. 2505.23836
  - OpenAI/Apollo 2509.15541
  - 2510.05179
  - Li et al. 2605.23055
  - critique refinement 2609.02302
  - DeepMind honeypots 2605.29729
  - LURE on LessWrong
  - Anthropic coding-audit realism
- **Environments:** AgentDojo, AppWorld, TALES 2504.14128, τ²-bench, Agent-Diff, WorkBench, AWM, ScienceWorld, AuthorizationBench, Instrumental Choices 2605.06490, Resource Hijacking 2608.15108.
