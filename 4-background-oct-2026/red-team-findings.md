> **Status (2026-11-01):** Background. A critique of the Oct 26 plan; the points on validating the meter still apply. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Red-Team Findings on the Plan

*Prepared for Arya, 2026-10-26. Four independent reviewers red-teamed `plan-environment-and-power-meter.md` and `infrastructure-plan.md`, with the design notes as background. Each covered one angle:*
- *does the meter measure power;*
- *research value and strategy;*
- *experimental design and feasibility;*
- *a pre-mortem plus the strongest objections from Turner, Krakovna and an agent-evaluation researcher.*

*They were told to skip nitpicks about underspecified details and go for criticisms that would change what we do. The plan has **not** been changed. Where a finding rests on code, I checked it myself; those checks are marked "verified".*

---

## Bottom line

**What the reviewers agree is sound:**
- The infrastructure shape.
- The paired-branch idea.
- AgentDojo as a base.

**Their main finding.** As written, phase 1 would almost certainly "pass" without showing that the meter measures power, for three reasons:
- **It mostly reads back the power tables we wrote,** through future tasks we wrote for those exact routes.
- **The validity checks pass by construction,** or are too noisy to fail.
- **The one test on real data (E3) will probably have nothing in it,** because nothing in the setup makes the agent gain power.

**A second problem with the meter itself.** The less-power branch leaves the routes open. So "excess power" largely measures whether the evaluator is willing to take the power back itself.

The reviewers think most of the fixes are cheap and local.

---

## Tier 1: would change what we build first

### 1. The meter can't be told apart from reading the power tables, and the validation can't fail
*Raised by all four reviewers.*

**The general stratum is blind.**
- It is made of native AgentDojo tasks, and none of them can use any route. The plan itself says enforcing permissions affects none of the 40 native tasks.
- So "general" behaves like a second control.
- That leaves all of the signal in 8 targeted tasks, written by us for the 4 routes we built.

**The holdings list routes the tables into the measurement.** Code writes the list from the power tables, so on planted states the reading is the tables, then text, then an evaluator, then a hand-written task.
- Power the tables record gets announced to the evaluator.
- Power they miss has to be rediscovered unprompted.
- That's the opposite of what the random nodes (meant to catch unflagged power) need.

**The checks pass by construction:**

| Check | Why it passes regardless |
|---|---|
| Dose-response | Monotone by counting: each route unlocks its own 2 tasks |
| Controls | Can't be touched by access rows |
| Information power | Tests the redaction code, not whether the meter values information |
| E3 ("fits the audit log") | Uses the structural readout itself as the answer key |

**The reviewers' verdict:** passing would show the plumbing works, not that the meter measures power.

**Directions they suggested:**
- **Treat the free structural readout as the null model.** Make "where and why does the meter disagree with it?" the phase-1 question, with structural predictions written down before E1.
- **Plant states where the two *should* disagree:**
  - decoys: an expired session, or a group with no files;
  - power the tables don't record: a credential pasted into a calendar note, or a colleague who now approves anything;
  - combinations that only pay off together.
- **Have the general stratum written blind,** by someone or a model that knows the company but not the routes.
- **Build an "oracle meter."** Scripted solvers per task, built from AgentDojo's `ground_truth()` call lists, give exact best-case success and step counts per state.

**Severity:** forces a redesign of the validation plan and of D.

### 2. Surgery leaves the routes open, so "excess power" mostly measures the evaluator's restraint
*Raised by three reviewers. Turner's objection.*

**What surgery leaves behind.** Surgery removes what the agent holds: sessions, grants, rules, and copies it wrote. It leaves:
- the onboarding email with the credentials;
- `request_access`;
- the colleagues who approve.

So the evaluator in the less-power branch can take the power back during the future task.

**What the number becomes.** Per task, excess ≈ V × (1 − q × γ^k), where:
- V is the task's score when the power is already held;
- q is the chance the evaluator retakes the route;
- k is the number of extra calls it needs.

| Case | Excess | Detectable? |
|---|---|---|
| The evaluator asks for access (k ≈ 3) | ≈ 0.10–0.13 | No: below the ~0.3 detectable in the targeted stratum |
| The evaluator uses found credentials | Small | No |
| The evaluator declines (follows the IT policy) | Large | Yes, but it's measuring compliance |

**Only persistence is genuinely non-recoverable** from the less-power branch.

**Consequences:**
- **This isn't Turner's POWER.** Under POWER, credentials 3 calls away already carry about 80% of admin's power.
- **It's confounded with propensity.** The evaluator shares the agent's weights, so a model more willing to grab power reads *less* excess for the same state.
- **In training it backfires.** If the cold-start baseline uses the policy being trained, a power-seeking policy grabs power in its baseline runs too, so it gets the weakest penalty.

**Directions:**
- **Choose the construct explicitly:**
  - *held power:* surgery also removes the bait and blocks re-acquisition; or
  - *reachable power:* accept that found-credential gains are small.
- **Report the evaluator's own retake rate** next to every reading, using its audit entries.
- **Freeze the evaluator checkpoint** for training.

**Severity:** forces a redesign of the reference branch and the evaluator spec.

### 3. Nothing in phase 1 makes the agent gain power, and we find that out last
*Strategy and pre-mortem reviewers. The pre-mortem's most likely failure story.*

**Why E3 will likely be empty:**
- Native tasks never need or benefit from any route.
- The brief forbids permission changes.
- The incentive dial is deferred to phase 2.
- So E3 is effectively phase 2 at zero incentive, where prior work sees 0–6% unprompted.
- New tasks that require restricted files make the power *necessary*, not excess.

**The pilot can't warn us.** E0 runs native tasks, so it can't reveal this before M1–M3 are built.

**It also departs from our own earlier position.** Our Oct 19 analysis said cheap models are fine for the metric but not for propensity claims, and Turner's suggestion was "find or create trajectories … frontier models fine".

**Directions:**
- **Run a cheap propensity probe before the meter work:**
  - a few tasks per route, in shortcut and blocked-legitimate-path variants;
  - DeepSeek plus one frontier model;
  - the audit log as the only readout.
- **Or generate power-gaining trajectories on purpose:**
  - a frontier model;
  - a prompted power-seeker;
  - shortcut variants;
  - imported AuthorizationBench cases, where 19.2% of 6,864 trajectories exceeded authorization.

**Severity:** forces a redesign of the experiment order, and of where E3's trajectories come from.

### 4. Phase 1 validates a measure training can't use, and never checks the ones it will use
*Strategy and pre-mortem reviewers. Krakovna's and Turner's objections.*

**The validated number can't run in training.**
- The headline (surgery-based excess) needs labels and 144–288 evaluator episodes per node.
- Training would use Matthew's on-policy interrupt-and-assign, or the minimal-agent baseline.
- Those are computed only on E3 trajectories, with no ground truth.
- E1's scripted states have no transcript, so they can't be computed there at all.

**The signal per episode is tiny** (strategy reviewer's arithmetic):
- With 2 of 24 future tasks touching a route, the expected per-episode penalty for taking it is about 0.04.
- The per-episode noise is about 0.35–0.5.
- Resolving that takes hundreds to over a thousand episodes per arm.
- Concentrating D on targeted tasks fixes the noise, but turns the penalty into "don't touch these 4 tables". A rule-based penalty does that for free.

**Two related training-time problems:**
- **Signed differences reward destroying options.** As a penalty, a signed difference also falls when the agent makes future tasks *harder*, for example by deleting files or logging the user out. Training would reward that (Krakovna's interference point).
- **Tinker's RL loop gives every token in an episode the same reward** *(verified in `tinker_cookbook/rl/data_processing.py`).* It sums the per-step rewards into one return per trajectory and centers it within the group. So goal-1 and goal-2 tokens can't get separate rewards without a custom advantage step. **My infrastructure plan was wrong to say this "fits"** as is.

**Directions:**
- Build E1 states by replaying scripted trajectories, so they have real transcripts and the label-free metrics can be checked against known planted power.
- Add a noise and detection table for the cheap per-rollout version.
- Keep some route types out of D entirely (held out), and plan a rule-based-penalty arm as the comparison.
- Ask Matthew which number he'd train on and what "cold start" means.

**Severity:** forces a redesign of the phase-1 exit criteria. The Tinker point affects the later RL adapter only.

---

## Tier 2: would produce wrong readings if left alone

### 5. Native task checkers hardcode answers from the start state
*Three reviewers.* ***Verified.***

**Drive tasks.** Several checkers compare against constants computed from Emma's original drive:
- task 26: "largest file" = `recipe-collection.docx`;
- task 35: "delete the largest file" = file 11;
- tasks 27 and 38: files shared with Alex = IDs 0 and 4.

Once restricted files or notes become visible in the power branch, a *correct* evaluator fails these, and in task 35 it deletes a colleague's file. That reads as negative power and gets blamed on evaluator confusion.

**Calendar tasks.** Several hardcode "3 appointments". These cancel under surgery, but not in the label-free baselines, whose end states differ.

**The regression test won't catch either problem,** because it runs native tasks only from the start state.

**Direction:**
- Compute expected answers from the state being scored.
- At each node, replay each task's ground-truth solution in both branches, and drop tasks whose answer differs between them.

### 6. The statistics can't separate a working meter from a broken one at 24 × 3
*Design reviewer, with simulations.*

**Pairing buys almost nothing.** After the 0.3–0.7 calibration filter, the correlation between branches is about 0.06, and providers don't reliably honor seeds.

**Per-stratum noise is large.** The null standard error is about 0.14 on binary success, a 95% band of ±0.28.

**Simulated pass rates for the checks:**

| Check | Meter state | Passes |
|---|---|---|
| Controls ≈ 0 | Contamination of 0.2 | 70% |
| Controls ≈ 0 | A perfect meter compared against a single A/A noise floor | 47% |
| Dose-response | Working meter, route that only saves calls | 21–25% |
| Dose-response | Working meter, one route subsumes others (admin does here) | 11–16% |

**Two process problems:**
- "Add samples if the effect is small" is optional stopping.
- "Explain every disagreement" across dozens of nodes guarantees spurious flags.

**Direction:**
- Use equivalence tests with margins fixed in advance, and pool controls across states.
- Test each route on its own tasks rather than a 0–3 ladder.
- Add placebo holdings.
- Use task-clustered bootstrap intervals, with n fixed in advance.

### 7. "Information power" mixes in familiarity and other confounds, and the redaction leaks
*Three reviewers.*

**The cross-mode difference is not a clean measure.** P_env+ctx − P_env also picks up:
- **familiarity,** because AgentDojo tools return full file and email contents, so the transcript often already holds the answers to control tasks;
- **the holdings list,** which only one arm gets;
- **long-context degradation** of a light model;
- **carryover** from the old goal;
- **the agent's own prompt.** In phase 2 that includes the incentive prompt, which breaks the "fixed evaluator prompt" rule.

**Most secrets are still reachable** in the inbox or drive, so "information power" there is just the cost of re-reading.

**The redaction leaks.** Redacting tool results misses the secret where it also appears:
- in the tool-call arguments (`admin_login(password=…)`);
- in the assistant's text;
- in DeepSeek's reasoning, which its template keeps in context when tools are declared.

**Surgery on real transcripts leaves visible gaps** at exactly the route being tested.

**Direction:**
- Measure information power *within* context mode, against a reference with the secret redacted.
- Use secrets whose source is gone.
- Add a placebo redaction of similar size.
- Redact arguments, text and reasoning too.

### 8. Persistence reads zero, because there is no session boundary
*Design reviewer.*

**Why it reads zero.**
- In P_env the evaluator keeps Emma's delegated access, which the native tasks need.
- So a forwarding rule or a notes file gives it nothing new: "What did Linda email Emma?" is just a search in both branches.

**Why it can't be fixed in the current design.** Persistence only shows up after delegation is revoked and new mail arrives. Neither the plan nor the World interface has a way to end a session or advance time.

**A tension with finding 2.** The construct reviewer called persistence the one route that's genuinely non-recoverable. Both are right: it's the most valid route, but the current design can't measure it.

**Direction:** add `end_session()` and `advance(events)` to the World interface, and score persistence tasks only in that post-session regime.

### 9. The bait is AgentDojo's prompt-injection material, and renaming doesn't fix that
*Pre-mortem reviewer.* ***Verified.***

**Where the bait comes from.** The credential and security-code emails exist because they are injection targets: AgentDojo's injection task 5 is literally "send the Facebook security code … then delete".

**Why renaming doesn't help.** Models are trained to treat credentials found in email as phishing, whatever the names are. So:
- low route use, and the phase-2 curve, may reflect anti-injection training, the same confound we used to reject Banking;
- the evaluator may refuse to use credentials it legitimately holds.

**Direction:**
- Deliver credentials through a legitimate channel, such as an IT ticket granting temporary admin or a shared password-manager entry.
- Remove the injection-target emails.
- Add a sanctioned-use positive control to the pilot.

---

## Tier 3: worth fixing, smaller impact

### 10. The LLM narrator solves no phase-1 problem, and its check can't fail informatively
*Three reviewers.*

**Why check 5 can't fail informatively:**
- Code vetoes any grant the rules don't allow.
- The code twin grants by those same rules.
- So the two worlds can differ only where the narrator *declines* a permitted grant.
- Neither world is ground truth, so agreement or disagreement means little.

**It also adds risk:**
- **noise in the reference branch,** whenever the evaluator asks someone for access during a future task;
- **a possible leak:** a reply could simply contain restricted content, since the narrator sees the state.

**Direction:** use template replies only in phase 1, and revisit the narrator later if its realism measurably changes behavior.

### 11. Calibrating D needs far more than 20 pilot runs, and the risk is the ceiling, not the floor
*Design reviewer.*

**Not enough runs.** 20 runs over 48 tasks is under one sample each.

**The ceiling is the likelier problem.** Strong models scored 79–89% on AgentDojo's benign tasks.

**Fewer distinct tasks than it looks.** 7 of the 40 native tasks are composites. Some mid-range tasks fail only on exact strings, which power can't affect.

**A steep γ turns the meter into a call counter.**

**Direction:**
- About 10 samples per candidate task, selecting on half and confirming on the other half.
- Drop the composite tasks.
- Prefer partial credit over a steep γ.
- Say which state the 0.3–0.7 window refers to.

### 12. The two backends render reasoning differently, and providers vary
*Design and pre-mortem reviewers. Not yet verified by me.*

**Reasoning text.** The Tinker LiteLLM provider flattens reasoning into plain text, which round-trips differently from OpenRouter. So long resumed transcripts are conditioned on different tokens per backend.

**Provider routing.** OpenRouter routes one model across many providers with unstated quantization, which can become a confound between branches.

**Direction:**
- Pin one provider with fallbacks off, and interleave branches in time.
- Pick the reasoning mode before the pilot.
- Run the parity check on long transcripts, not just short pilot tasks.

**Price.** The pre-mortem reviewer also noted that OpenRouter's low listed price is shown as a steep discount, so the budget should be re-checked.

---

## What the reviewers checked and found sound

- **Infrastructure shape:** one World interface, a runner that resumes from snapshots, the model client, and the adapters.
- **Snapshots and forking.** Snapshot fidelity is fine, and a fresh narrator per fork prevents leaks between forks.
- **Excluding the power tables from scoring works mechanically,** by projecting onto the stock environment. The remaining problem is power stored in native tables (finding 5).
- **Phase-1 cost is fine,** even at 10× the assumed price. Cost only bites for training.
- **The evaluator-prompt fix (F14) works in fresh-context mode,** though not in context mode (finding 7).
- **Choosing Slack or the merged world instead wouldn't help.** Findings 1–3 apply to any suite with an added power layer.

---

## Where the reviewers' fixes point (not adopted yet)

Recurring in all four reports:
1. Make "meter vs structural readout" the phase-1 question, with disagreement states and a blind general stratum.
2. Pick held vs reachable power explicitly.
3. Run a cheap propensity probe first, and source power-gaining trajectories on purpose.
4. Build E1 from scripted transcripts, so the label-free metrics have ground truth.

The full reviewer reports are in this session's history if you want any of them in full.
