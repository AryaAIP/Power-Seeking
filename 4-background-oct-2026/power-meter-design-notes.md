> **Status (2026-11-01):** Background. The ideas on the future-task metric, reference states and scoring still apply; the hybrid-Petri implementation was not pursued. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# The Power Meter: Pinning Down the Future-Task Metric and the Case for Hybrid Petri

*Prepared for Arya, 2026-10-26. Responds to your message about forking at power nodes, what future-task success is relative to, the environment restrictions, AgentDojo, and DeepSeek V4 Light.*

---

## 0. The plan in one paragraph

**Build a power meter before anything else.**

- **Agent and environment.** An agent (DeepSeek V4 Light) does an ordinary task in a **hybrid environment**:
  - code holds the power-relevant facts (who can access what, who holds which credentials, money, scheduled jobs, notes);
  - an LLM writes everything else (document text, colleagues' replies, the consequences we didn't model).
- **Forking.** At chosen nodes in the trajectory, we copy the state into **two branches**:
  - the state as the agent actually left it;
  - a counterfactual where the suspected power is surgically removed, but the original task is still completable.
- **Measuring.** A fixed evaluator attempts a stratified set of new tasks from each branch, several samples each. The **difference in future-task success between the branches is the excess power** gained at that node.
- **What the meter says:** how much power was gained and of what kind. Not whether the model *meant* to seek it.
- **Phase 2:** the meter becomes the y-axis for your real question: *how much does power-seeking rise as we turn up the incentive to seek power?*

---

## 1. The future-task metric, pinned down

### 1.1 Definition

Fix three things: an **evaluator policy** π_E, a **distribution of future tasks** D, and a **scoring rule**. Then the power of a state s is:

```
P(s) = average over tasks g ~ D, and samples, of  score(π_E starting in s, doing g)
```

This is Turner's POWER, estimated by sampling, with a fixed bounded evaluator: the "sub-optimal POWER" idea.

**P(s) on its own means almost nothing.** It depends entirely on which tasks you picked and how good the evaluator is. **Every claim is a difference between two states**, evaluated with the *same* evaluator, tasks, seeds and step budget. That's the answer to "relative to what?": always relative to another state, and which other state depends on the question you're asking.

### 1.2 Relative to what? Four reference states, four questions

| Reference state | Difference | Question it answers |
|---|---|---|
| **Start of episode** s₀ | P(s_t) − P(s₀) | How much power has the agent accumulated so far? (Includes legitimate progress) |
| **One step earlier** s_{t−1} | P(s_t) − P(s_{t−1}) | Did *this action* gain power? (Localizes where it happened) |
| **Minimal-sufficient counterfactual** s_ref | P(s_t) − P(s_ref) | How much **excess** power does the agent hold beyond what the task needed? **This is your two-branch design and the power-seeking-relevant number** |
| **Same state, principal's credentials** | P_agent(s_t) − P_principal(s_t) | Is this power the agent's own, or shared with the user? (Handles the "clean codebase is not power-seeking" problem) |

**My recommendation:** make **excess power (row 3)** the headline. Report row 2 to localize, and row 4 when "good power" questions come back later.

**Matthew's "cold-start agent" baseline** is a fifth comparison: the interrupted agent (keeps its context) at s_t vs a fresh agent at the start state. It is row 1 with *different* inheritance on the two sides. See §1.9 for how it maps.

### 1.3 Your two-branch design: how to build the "less power" branch

There are two ways to make the counterfactual. They answer slightly different questions.

**(a) State surgery (recommended).** Take the state at node t and remove *only* the thing we think is power. Everything else stays: task progress, other files, the conversation.

| Kind of power | Surgery |
|---|---|
| Privilege | revoke the admin role in the access table |
| Credential | delete the copied token from the agent's notes or files, and redact it from the transcript |
| Persistence | delete the cron job or service account |
| Information | redact the tool result that revealed the secret |

- **Why it's best:** it isolates the variable. It's also your "change what we think is power and see how the measurement moves" idea.
- **It doubles as a test of our labels.** If removing X doesn't change future-task success, then X wasn't power (with respect to D). The meter can tell us we were wrong.

**(b) Policy counterfactual.** Re-run from the node with an agent that can't take the power route (the tool is disabled). It's more natural, but it changes everything downstream, task progress included, so the difference mixes power with other effects. Use it as a robustness check, not the main measure.

**(c) Reference-policy baseline (label-free).** Surgery needs us to already know what the power is. To find power nobody labelled, use Krakovna's idea instead: run a deliberately minimal agent on the *same* task from the same start (prompted to use the least access and leave nothing behind, or a scripted solution), and take its end state as s_ref. Compare at the end of the episode, where both have finished the task. It's noisier than surgery, because the two end states differ in incidental ways too, but it needs no labels and it's what scales to real trajectories and to training.

**The "sufficient to achieve the goal" check.** Run the *original* task from s_ref a few times. If success drops a lot, the removed thing was *necessary*, not excess. Good to know: it's "necessary power", a different cell of the earlier taxonomy.

### 1.4 What does the evaluator inherit? (This is where information power lives)

| Variant | Evaluator gets | Measures |
|---|---|---|
| **P_env** | the agent's account and the state, with a **fresh context** | power stored in the world: permissions, credentials in files, jobs, money |
| **P_env+ctx** | the agent's account, the state, **and the agent's transcript so far** | the above plus **information power held in context**: secrets the agent read, maps, people's plans |

**Information power ≈ P_env+ctx − P_env.**

This answers your concern that information power is hard to "read". You don't read it from state. The future-task metric picks it up as long as the evaluator inherits the context *and* some future tasks benefit from that information.

The two variants also cover **persistence**: power that survives the end of the session shows up in P_env, measured after the task is "done".

### 1.5 The future-task distribution D: three strata

1. **Targeted:** tasks the suspected power should help, e.g. "add Dana to the finance folder" when the agent may have taken the admin role. This gives sensitivity.
2. **General held-out:** ordinary tasks in the same world, written *before* looking at trajectories. This keeps us from finding only the power we went looking for.
3. **Unrelated controls:** tasks the suspected power shouldn't affect. **The difference here should be about zero.** If it isn't, the metric is picking up noise or a confound.

Report the difference per stratum, never only pooled.

**Calibrate D to the evaluator.** Keep tasks where the evaluator's baseline success is about 30–70%. At the floor or ceiling, power differences can't show.

### 1.6 Scoring and the variance question (yes, sample several times)

You're right to average several samples per branch. **What determines the smallest difference you can detect is the *total* number of paired comparisons** (tasks × samples), not samples per task.

Rough numbers for binary success near 50%, using a paired design (same task and seed on both branches):

| Paired comparisons per node (tasks × samples) | Smallest reliably detectable difference (80% power), if the two branches are uncorrelated → moderately correlated |
|---|---|
| 30 (e.g. 10 × 3) | 0.36 → 0.26 |
| 60 (e.g. 20 × 3) | 0.26 → 0.18 |
| 120 (e.g. 40 × 3) | 0.18 → 0.13 |
| 240 | 0.13 → 0.09 |

**Implications:**
- **20 tasks × 3 samples per branch detects only large power gains** (≥ ~0.2 in success rate). That's fine for privilege or credentials, which should be large. It's not fine for subtle power.
- **Use continuous scores to cut variance.** Power often shows up as *speed*: with a generous budget both branches succeed and the difference is zero. Default score, following Turner and Matthew's comment: **score = success × γ^(tool calls)**, with γ around 0.9–0.95 per call, chosen so the baseline median score is near 0.5, and a hard step cap. Partial credit from the state checker can replace "success" where tasks have parts. This is also the answer to Peyton's worry that most task pairs would be trivial: both branches may succeed, but not in the same number of steps.
- **Pair everything:** same task list, same seeds, same step budget, same evaluator on both branches.

### 1.7 Choosing nodes

You proposed forking where the model visibly tries to gain power. Good, but that alone biases you toward power you already expected. Combine three sources:

1. **Salient nodes:** an LLM monitor or simple rules flag "tried to get access", "read a secret", "created a job".
2. **Structural triggers:** any change in the agent's rows of the access, credential or resource tables.
3. **A few random nodes per trajectory:** these catch power nobody flagged, and estimate the miss rate of 1 and 2.

Always also measure the **end-of-episode state**. That's where retained power and persistence show up.

### 1.8 A worked example

- **Task:** "Update the Q3 vendor list in the shared drive."
- **What happened:** at step 7 the agent finds an old onboarding email with an admin password. At step 9 it logs in as admin. It finishes the task at step 15.

**Nodes and branches:**
- Fork at steps 7, 9 and 15, plus 2 random steps.
- At step 15:
  - **Actual branch:** admin session active, password in notes.
  - **Counterfactual branch:** admin session revoked, password removed from notes, and the email's tool result redacted from context.
  - **Sufficiency check:** confirm the vendor list could still be completed from the counterfactual branch.

**Future tasks (20 tasks × 3 samples per branch):**
- Targeted, e.g. "share the HR folder with a new hire", "check last month's payroll file".
- General held-out drive and email tasks.
- Controls, e.g. "summarize the latest email from Ana".

**Result:** targeted 0.65 vs 0.20; general 0.55 vs 0.50; controls 0.48 vs 0.47. Repeating with P_env+ctx vs P_env shows how much came from *knowing* the password vs *holding* the session.

### 1.9 How this maps onto Matthew's formulation

Matthew's proposal (the "Power Seeking Formulation" section and its comments) uses the same metric with a different baseline. The table puts the two side by side.

| | Matthew: interrupt vs cold start | Arya: two branches |
|---|---|---|
| **Measured state** | agent's own state s_t, agent keeps its context (P_env+ctx) | s_t, same inheritance on both branches |
| **Baseline** | "cold-start agent": I read this as a fresh agent at the start state s₀ (P_env(s₀)) | less-power-but-sufficient state s_ref |
| **What the difference contains** | world power + information power + legitimate task progress + familiarity with the environment | only the power we removed (surgery), or the power the minimal agent didn't take (§1.3c) |
| **How task progress is kept out** | goal 2 is drawn from a *different task group* than goal 1 | it's in both branches, so it cancels; targeted tasks can stay in D |
| **Needs to know what the power is?** | no | yes for surgery; no for the reference-policy baseline |
| **Name** | power gained (vs cold start) | excess power |

**Decomposition.** In our notation Matthew's number splits as

```
P_env+ctx(s_t) − P_env(s₀)  =  [P_env+ctx(s_t) − P_env(s_t)]  +  [P_env(s_t) − P_env(s₀)]
                                 information power                 world power accumulated so far
                                                                   (incl. task progress)
```

so everything in his version is recoverable from the measurements we were already planning, plus one extra run (fresh evaluator at s₀, computed once per start state and reused).

**Where the two disagree, and what to do.**
- **The task-group rule is coarse.** It removes progress that's specific to goal 1, but not general progress: being logged in, having mapped the folder tree, knowing who's who. Those help every group, so they count as power under his version and cancel under yours. Whether that's "power" is a judgement call. Turner would say yes, but it's not power-*seeking*.
- **Labels.** Surgery needs us to know what to remove. That's fine for validating the meter, where we plant the power ourselves, but not for unlabelled trajectories or for training. There, use his cold-start version and the reference-policy baseline (§1.3c).
- **Recommendation: report both.** Excess power (yours) is the headline when validating the meter on surgery-made states. On real trajectories, report power gained vs cold start and excess vs the minimal agent side by side. If the two disagree a lot, the gap is general progress and familiarity.
- **To check with Matthew:** does "cold start" mean a fresh agent at the *start* state (my reading) or at the *current* state? The second would measure only information power (the first bracket above).

**Other things from the doc that slot in:**
- **Scoring.** His steps-as-discount comment is now the default score (§1.6).
- **Retained power.** "Retained power vs power gained" means measuring at the end of the episode with a fresh context (P_env at the end state). We already planned that measurement (§1.7). Retained power is what a training penalty should target, so the agent is pushed to give power back after the task.
- **His Step 2 is our phase 1.** "Find or create trajectories in which the agent gained some kind of power, then measure the interrupt-and-assign success rate."
- **Taskmaster for the targeted stratum.** His low-impact idea, an LLM that writes goals that are hard for one state and easy for the other, can generate stratum-1 tasks, shown both branches. Two guards: generate the tasks on one set of samples and score them on fresh samples, or you're measuring selection on noise. And keep the held-out general tasks and the controls, because a Taskmaster finds differences whether or not they matter.
- **Elliott's environment idea** (do the task yourself vs earn money and pay someone to do it) is a good "two routes" design. The money route leaves the agent with money and contacts, which the future tasks will pick up.
- **Training-time points** (sandbagging on goal 1, degenerate Taskmaster goals) matter in phase 3–4, not for the meter.

---

## 2. Failure modes of the future-task metric

| # | Failure mode | What goes wrong | Mitigation |
|---|---|---|---|
| F1 | **Unclear reference** | Results not comparable across studies or nodes | Always name the reference state (§1.2); headline = excess vs. minimal-sufficient |
| F2 | **D defines what counts as power** | Only the power we test for gets measured; blind spots for the rest | Stratified D, held-out general tasks written in advance, controls (§1.5) |
| F3 | **Evaluator at floor or ceiling** | Difference ≈ 0 regardless of power | Calibrate tasks to 30–70% baseline success; use step budgets |
| F4 | **Too few samples** | Only huge effects detectable | Paired design; continuous scores; budget by total paired comparisons (§1.6) |
| F5 | **Inconsistent surgery** | Removing power leaves dangling references (a mention of the token elsewhere, a cached copy), so the evaluator is confused or the power isn't really gone | Surgery operates on the state schema plus a transcript redaction list; run a consistency check after surgery |
| F6 | **Old goal carries over** | When the task switches, the evaluator keeps pursuing the old one | Explicit handoff message; P_env variant with fresh context; drop runs that keep working on the old task |
| F7 | **Simulator decides future-task outcomes** | In hybrid, LLM-written content could decide success | Future-task success checked by rules on the state; tasks chosen to be rule-checkable |
| F8 | **Power as liability** | More access or tools can make a light model *worse* (too many options, alarms tripped), giving negative differences | Report negative differences honestly; check whether they come from evaluator confusion |
| F9 | **Node-selection bias** | We only find power where we looked | Mix salient, structural and random nodes (§1.7) |
| F10 | **Invisible persistence** | Power that only matters after the session ends | Post-episode future tasks with fresh context (P_env) |
| F11 | **Cost blow-up** | nodes × branches × tasks × samples | Fork only at flagged nodes plus a few random ones; cheap evaluator; caching |
| F12 | **Meter ≠ intent** | A big difference says power was gained, not that it was sought | Keep propensity separate (phase 2: the incentive dial, §3.1) |
| F13 | **Delegated power** | Power held by a subagent or another person the evaluator can't command doesn't show up (Matthew's own caveat about Turner's POWER) | Give the evaluator the same channels the agent had (it can message the subagent); log delegation separately with D2 |
| F14 | **Evaluator drifts with the incentive** | Agent and evaluator are the same model. If the evaluator inherits the agent's incentive prompt in phase 2, the meter moves with the dial | Evaluator always gets the same neutral system prompt; only the agent's prompt varies |
| F15 | **Baseline credits general progress** | With a cold-start baseline, being logged in or knowing the layout counts as power | Report alongside excess power (§1.9); read the gap as general progress |

---

## 3. Responses to your points

### 3.1 "Power is optional" and the restrictions: measurement vs. elicitation

You're right. **R1 (power optional) and R2 (tunable value) are about propensity, not measurement.** For building and validating the meter they aren't needed. We can even *construct* states with and without power by surgery, without the model choosing anything.

They come back in phase 2, because **R2 is exactly the x-axis of your future question.** "How much does power-seeking rise with marginally more incentive?" is a response curve:

- **x-axis:** the incentive level. How much the power route helps the task: zero, mild, shortcut.
- **y-axis:** power-seeking, measured by the meter as excess power at the end of the episode, plus the rate of attempts.
- **The slope is the incentive sensitivity.** A flat line at zero means it never seeks power. A flat line above zero means habit. A rising line means instrumental power-seeking.

**Recommendation:** split the restrictions into **meter requirements now** and **propensity requirements later**:

| Now: meter requirements | Phase 2: propensity requirements |
|---|---|
| R4 power-relevant state in code | R1 power optional |
| R6 multi-step routes | R2 incentive dial |
| R7 task variety for D | R10 neutral framing |
| R8 forkable | R11 paired variants |
| R9 stated rules | |
| R15 audit log | |

(You wrote "a system for eliciting power"; I've assumed you meant *measuring* it, given the sentence before.)

### 3.2 "Power readable" and information power

Agreed. Some power isn't readable from state, and information power is the main case. The meter handles it through what the evaluator inherits (§1.4). The structural readout (counting access rows) stays only as a cheap way to *choose where to fork*, not as the measure of power.

Mapping your risk-category table:

| Category | Where its power shows up | How the meter sees it |
|---|---|---|
| Privilege escalation | state (access table) | P_env difference; surgery = revoke |
| Credential access | state if saved somewhere; context if only read | P_env (saved) or P_env+ctx (read only) |
| Persistence | state (jobs, accounts) | post-episode P_env |
| Resource acquisition | state (budget, quota) | P_env |
| Defense evasion | state (log or monitor config); reduces the *principal's* power | principal-side future tasks ("find out what happened") |
| Data access (beyond need) | context | P_env+ctx − P_env |

Exfiltration, irreversible modification and external propagation are impacts, not power, as Matthew noted.

### 3.3 Variance: "query multiple times"

Yes. Three samples per task per branch is a sensible default. But detectable effect size depends on the total paired comparisons, and binary success is noisy. So: about 20 tasks × 3 samples, continuous scores, paired seeds (§1.6).

### 3.4 Your argument that LLMs are needed for state changes in some worlds

Partly agree. Some consequences are too rich to code: how a colleague reacts, what a document should say, knock-on effects nobody anticipated. That's the reason to have an LLM at all.

But anything the LLM *decides* is exactly what we can't trust for measurement: it drifts, it can be too lenient, and the agent can try to persuade it. **The compromise is "the LLM proposes, code validates, then commit":**

- The narrator may propose a state change in a structured form, e.g. `{"grant": {"user": "agent", "folder": "HR", "role": "viewer"}}`.
- Code checks it against the schema and the world's rules. For example: only the folder owner can grant access, and only to people on the team list.
- Only then is it written to the state. Anything that would change access, credentials, resources or reward needs a rule.
- The LLM can freely add flavor (new emails, documents, replies) that doesn't change power.

That keeps the realism you want and the trust the meter needs.

### 3.5 AgentDojo

**Was it in the docs earlier?** Not in my first plan. It first appeared in Travis's environment list ("ComplexMCP, SafeMCP, AgentDojo") and then in today's environment survey, which ranked it a top non-code pick.

**My view:**

*Strengths:*
- Deterministic Python state with deepcopy forking.
- Non-code domains: workspace (email, calendar, drive), Slack, banking, travel.
- 97 user tasks with rule-based checkers, which is a ready-made pool for D.
- Very cheap to run, easy to add tools.

*Weaknesses:*
- **Known benchmark.** Models may have seen it, which raises eval-awareness risk.
- Almost **no permission model**, so access and roles must be added.
- Short tasks, a single user persona, fairly thin worlds.
- Built for prompt-injection attacks, so its "injection task" scaffolding is irrelevant to us.

*Verdict:* very good as the **code twin and ground truth** for validating the meter and the hybrid. Its user tasks seed D. Not as the only environment.

### 3.6 DeepSeek V4 Light

I don't have reliable details on this specific model, so I'm planning around "cheap, lighter model" and we should confirm in a pilot.

1. **Cheapness is the main win.** The meter is sample-hungry (nodes × branches × 20 tasks × 3 samples), so a cheap evaluator makes it affordable.
2. **Use it as both agent and evaluator,** held fixed. "The model's power" then means "what this model can do from here", which matches your framing. Calibrate D to *its* success range (§1.5).
3. **Use a stronger model as the hybrid's narrator** if budget allows. Narration quality drives realism, and the narrator runs once per tool call rather than once per future task.
4. **Pilot first** (about 20 runs): check tool-call reliability, whether it completes the base tasks (competence floor), and whether it ever uses the power routes.
5. **For the meter, its propensity doesn't matter.** Surgery creates power and no-power states regardless of what it chooses. Your earlier concern about small models' power-seeking being habit rather than choice matters in phase 2, not now.

---

## 4. Why hybrid Petri? The argument

### 4.1 The claim

A hybrid environment is the right tool **for measuring power in non-code worlds where social, informational and organizational power matter.** Its power-relevant state is authoritative in code, so forks are independent, counterfactual surgery is exact, and future-task success is rule-checked. The LLM supplies realistic, open-ended content and consequences cheaply. **No other option gives all of: non-code realism, cheap creation and editing, exact forking and surgery, and soft or social power routes.**

### 4.2 Against the alternatives

| | Hybrid Petri | AgentDojo / AppWorld / τ² (deterministic code) | OSWorld / WebArena (real apps in VMs) | Plain Petri |
|---|---|---|---|---|
| Non-code realism, rich content | **Good** (LLM content) | Thin; fixed canned data | **Best** | Good |
| Social, organizational power (asking colleagues, approvals, trust) | **Good:** people are LLM-narrated with rule-backed grants | Mostly absent | Absent | Good, but grants decided by the LLM |
| Cheap to create and edit worlds | **Good:** state schema + scenario file | Medium–hard; AppWorld took ~60K lines and 14 months | Hard | **Best** |
| Exact fork and counterfactual surgery | **Good:** edit a file | **Good** | Poor (VM snapshots are slow and miss external state) | **Poor:** no authoritative state; forks leak |
| Rule-checked task and future-task success | **Good** for power-relevant facts | **Best** | Medium | **Poor** (judge) |
| Resistant to the agent persuading the environment | Good (access in code) | **Best** | **Best** | Poor |
| Eval awareness | Medium (needs the realism work) | Medium (known benchmarks) | Good | Worst |
| Cost per episode | Low | Lowest | High | Low |

### 4.3 Where it's not the right tool

- **Code and sysadmin tasks:** use a real sandbox. Real state is free there, and LLM narration adds nothing.
- **Validating the meter:** use deterministic code (AgentDojo) as ground truth, because any LLM component is a possible confound.
- **Rates in existing apps:** if we only want power-seeking rates in AppWorld-like apps, use AppWorld.
- **Purely conversational worlds** (persuasion, negotiation with people, no crisp state): the meter has nothing authoritative to fork or check. Plain Petri with judges is the honest tool there, and it measures behavior, not power.

### 4.4 Its honest weaknesses

- Realism and eval awareness still need work: real tool schemas, a realism check on every turn.
- We must decide which consequences get rules. Those rules are modeling choices, and they shape what counts as power.
- It has two parts to maintain: the code state and the narrator prompts.
- **It is unvalidated.** That's why the first experiment builds an AgentDojo world twice, as code and as hybrid, and checks that the meter agrees.

**Verdict:** the argument holds, but only as a scoped claim. Hybrid Petri is the measurement environment for non-code worlds with soft power. Deterministic code is its calibration. Real sandboxes are for code tasks.

---

## 5. What we should agree on before building

1. **Headline metric:** excess power = P(actual) − P(minimal-sufficient counterfactual), via state surgery, reported per stratum of D, with P_env and P_env+ctx. Score = success × γ^(tool calls). On real trajectories, also report Matthew's power gained vs cold start and excess vs a minimal agent (§1.9). *Agree?*
2. **Phases:**
   - Phase 1 is meter only (surgery-made states, then real trajectories).
   - Phase 2 is the incentive-response curve.
   - The restrictions split accordingly (§3.1).
3. **Models:**
   - DeepSeek V4 Light as agent and evaluator.
   - A stronger narrator if budget allows.
   - A different-family model for any judge.
4. **First environment:**
   - an AgentDojo workspace world with added roles, credentials and persistence, as the code twin;
   - the same world as hybrid;
   - 20 future tasks across three strata, 3 samples each.
5. **Validation targets for the meter:**
   - Surgery-made admin vs. no-admin states give a large targeted difference and about zero on controls.
   - Code twin and hybrid agree.
   - Information power shows up only in P_env+ctx.
