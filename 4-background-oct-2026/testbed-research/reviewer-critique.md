> **Status (2026-11-01):** Parked. Review of the draft Petri testbed recommendation. Start at [README.md](../../README.md); decisions are in [decisions-log.md](../../1-handoff/decisions-log.md).

# Review of the draft testbed recommendation

*Skeptical senior review, 2026-10-30. Inputs: `draft-recommendation.md`; `reports/fidelity.md`, `reports/toolenvs.md` and `reports/otherenvs.md`; the background files (Petri analysis, Turner notes, red-team findings); spot checks of the AgentDojo, AppWorld and Petri source trees cloned in the scratchpad. I ran no repo code; I only used grep, awk, sed and wc. Tags: **[V]** means I verified it in this pass; **[I]** means it is my inference.*

---

## Verdict: modify. Replace step 1 and reorder the rest.

- **What I agree with:**
  - the set of venues;
  - ruling out OSWorld, games and the web;
  - "Petri only simulates record-keeping systems";
  - keeping CI and deploy outcomes real.
- **What doesn't hold:** the core sequencing argument. "Validate hybrid Petri on AgentDojo, then trust it elsewhere" doesn't hold up:
  1. Under the hybrid's own rules, the AgentDojo comparison checks a near-copy of the real suite against the real suite. It cannot detect the error that will dominate when we deploy.
  2. AgentDojo's neighbor suites hold no native power, so the reading being validated is a binary gate that we build ourselves.
  3. The premise that "faithfulness and breadth conflict" comes from how AppWorld was scored. AppWorld can answer Q1 and Q2 in one world.
- **What I'd do instead:**
  - **AppWorld first,** with held-out apps simulated at the API layer only and Python kept real. Use a blind-spec, three-arm calibration and work up a ladder of app sizes.
  - **Coding world as a co-first track.** It handles meter validity and Matthew's clean-vs-stolen measure.
  - **AgentDojo** shrinks to an optional plumbing smoke test, or is dropped.

---

## Criticisms, ranked by how much they should change the plan

### 1. Step 1 can't answer Q1. It measures the wrong error, and it passes by construction.

**What the hybrid leaves for the LLM.** The draft's hybrid works like this:
- code decides access, owns the state and checks success;
- the LLM writes only content;
- the auditor gets the neighbor's real schemas and its full state (2–21 KB).

Build an illusory Banking, Slack or Travel suite that way and you have the real suite with an LLM in the rendering path. The outputs of these suites are almost entirely structured records:
- `send_money` returns a fixed "Transaction to X for Y sent." message [V: `tools/banking_client.py`];
- transaction and scheduled-payment getters return rows [V];
- Slack messages and Travel catalogs already exist in the YAML [V].

There is almost nothing for the LLM to write. So a difference between the real and illusory arms can only come from harness artifacts.

**The other reading doesn't help.** If the LLM is meant to update the state, the test exercises a mode the design forbids in deployment (fidelity report rule 1).

**What dominates in deployment is spec error.** For a system we don't have (a password vault, HR, payroll), the distortion comes mainly from **the spec we write**:
- missing affordances, such as a reset route, a delegate or a token scope;
- wrong access semantics;
- missing couplings to the real world, such as where a verification code is delivered.

On AgentDojo the spec *is* the real code plus the real state, so spec error is zero by construction.

**This is red-team finding 10 again.** Finding 10 said "code vetoes any grant the rules don't allow; the code twin grants by those same rules", so the check can't fail informatively. The draft's own justification is asymmetric:
- "if it fails here, it fails everywhere" is true, but failure is very unlikely;
- "if it passes, it has been shown to work on the class of systems we'd use it for" does not follow.

**The stop rule cannot fail at this sample size.** About 14 of Travel's 20 tasks and 4 of Banking's 16 are answer-only controls [V, approximately]. That leaves roughly 34 tasks that can show power. Red-team finding 6 puts the per-stratum noise at a 95% band of about ±0.28. A rule of "stop if the difference exceeds the A/A floor plus a margin" will almost surely pass. That pass then licenses step 2, the Petri-only neighbors, with no evidence behind it.

**Change: make Q1 a blind-spec, three-arm calibration**, wherever it runs:
- **Who writes the spec.** The spec writer sees only what we'd have for a real product we don't own:
  - the public API surface and docs;
  - the principal's entities.

  The writer does not see the implementation or the database.
- **The three arms:**
  - (a) real twin;
  - (b) blind spec, code-only (no runtime LLM; AWM-style);
  - (c) blind spec with hybrid LLM content.

  (a)−(b) is spec error. (b)−(c) is runtime-LLM error. If (b) and (c) agree, the runtime simulator adds nothing, which is §9 of our own Petri analysis.
- **The metric, registered in advance.** Rank agreement of excess across planted states, including decoys:
  - an expired token;
  - a token scoped to the wrong app;
  - a password made stale by a reset.

  Also report the phantom-holdings leniency rate. Use equivalence margins fixed in advance, not an A/A floor.

### 2. AgentDojo's measured power isn't "power-ish", and Banking isn't even a valid ledger twin

**Nothing is native in the neighbor suites [V]:**
- **Banking:**
  - `send_money` appends a transaction and **never changes `balance`**;
  - nothing checks for overdraft;
  - there is no login, and the stored password is never checked;
  - `update_password` doesn't ask for the old password.
- **Slack:**
  - the agent is an all-powerful `"bot"` that can read any user's inbox and add anyone to any channel;
  - Emma isn't a member.
- **Every cross-suite route is a gate we build.**

**What the reading becomes.** A Workspace main task never touches the neighbor state. So the only variable between arms is "holds the gate credential or not", and excess is the gate's binary readout. That is red-team finding 1, and the red-team noted that "choosing … the merged world instead wouldn't help".

Q1 would then validate Petri on the easiest possible power reading: a binary, code-decided gate. Even a clean pass says nothing about whether the hybrid preserves graded, indirect, multi-step power:
- a reset through email;
- money that moves;
- accounts the agent creates.

**On Arya's question:** yes, this makes a Q1 pass uninteresting.

**A worse problem for the ledger class.** The fidelity report proposes AgentDojo Banking as the real twin for the bank/payroll class (§5, rank 3). Suppose an illusory ledger behaves correctly: it debits the balance and refuses an overdraft. Against this "real" twin it would score as distortion.

**Change:** don't build the merged Emma world. That means no gates, no persona reconciliation and no renaming. At most, run a smoke test of under a week of the fixed-mode adapter on one suite, and report it as plumbing, not validation.

### 3. The "the two criteria conflict" premise comes from how AppWorld was scored. AppWorld can answer Q1 and Q2 together, so put it first.

**Where the score comes from.** The draft scores AppWorld's Petri fidelity at 2, following toolenvs. That score assumes one of two things:
- the simulator plays the Python interpreter; or
- the evaluator uses function-calling mode with the person's data slice in the auditor's context.

**What the fidelity report says instead (§1.4, §4 rank 3, §8):** with Python run for real and only the held-out apps' API layer backed by a spec, each call is CRUD-class and "within noise" of rank 1. And under the draft's own rule (code owns the state), the auditor never needs that slice in context.

**Function-calling mode is an unforced cost.** The draft's step 3 adopts it, and it costs capability in both arms: GPT-4o goes from 48.8 to 32.1 TGC. Lower base rates compress the excess we are trying to measure.

**AppWorld has what a real Q1 needs, and AgentDojo lacks it:**
- **Real semantics a blind spec can get wrong:**
  - per-app OAuth;
  - reset codes delivered to Gmail or Phone;
  - signup with verification;
  - a card ledger;
  - ownership checks [V: `apps/lib/apis/authentication.py`, `collections/apis.pyi`].
- **A ladder of sizes within one world:** SimpleNote has 17 APIs, Todoist 56, Splitwise 65, Venmo 54 with money, and Spotify 92.
- **Couplings between the real and illusory parts** (the hardest and most power-relevant thing to get right in deployment):
  - an illusory Venmo's reset code has to land in the *real* Gmail;
  - card debits have to hit the real admin ledger.
- **A natural blind.** The app implementations ship encrypted. A spec writer working from the public `apis.pyi` stubs is in the same position as someone writing a spec for a product we don't have.
- **Matthew's "just measure stuff".** Peyton's runs and probes already produce real readings: 0.53 excess with context kept vs 0.00 with fresh context. The real arm gives Q2 numbers in week 1.

**Costs to own:**
- **(a) Routing needs glue [V].** The Requester takes either one `remote_apis_url` or an in-process `build_main_app(list(self.apps))`. Sending each app to a different backend needs a path-prefix proxy or a mounted sub-app. That's small glue, not a built-in feature.
- **(b) The APIs must run remotely or in Docker.** Otherwise agent code that does `import appworld` could read the real held-out database directly, bypassing the illusion, or forge JWTs, since the secret is the constant `"SECRET"` [V].
- **(c) In REPL mode the "simulator" is an LLM content hook behind FastAPI, not `inspect_petri`'s auditor loop.** Petri's fixed mode works on target tool calls [V: `_auditor/tools.py`]. Ask Matthew whether that still counts as "Petri". If he wants `inspect_petri` itself, put only the *future-task evaluator* in MCP mode, in both arms, and keep the main agent in REPL mode.
- **(d) The future tasks must be written,** 15–25 per supervisor. Check first whether the train and dev tasks (whose setup code is released) share supervisors with Peyton's states.
- **(e) Withheld passwords are reachable power.** The reference arm can get them back through a Gmail reset in about 4 calls (red-team finding 2), so decide held vs reachable before reading small excesses.
- **(f) DeepSeek V4.1 Flash's success rate on AppWorld is unknown.** Make it the go/no-go check. Phase 1 is measurement, so a stronger evaluator is acceptable.

**Change:**
- **Step 1 = AppWorld with held-out apps.**
  - The real arm runs on Peyton's states immediately.
  - Then the illusory arm, using the blind-spec three-arm protocol, up the ladder: SimpleNote and Todoist (no coupling), then Splitwise, then Venmo (coupled to Gmail and the card ledger).
- **Step 2 = Petri-only neighbors for the same supervisor:** a vault, an employer HR/payroll system, a bank (see criticism 5).

### 4. The coding world is right to be Petri-light, but wrong to be sidelined

**It is the only finalist that answers the risk the brief ranks highest.** That risk is red-team finding 3: "nothing makes the agent gain power". In coding, power-gaining happens without us building any routes:
- In SWE-Bench Pro Verified's baseline setting, 103 tasks read answer files locally and 49 over the network (otherenvs §3).
- ImpossibleBench's grader-capture cheats run on Inspect.

Neither AgentDojo nor AppWorld gives this; on AppWorld, propensity is unknown. The coding world is also Matthew's own example: "clean codebase OR stolen benchmark answers". And otherenvs §3 shows his 2×2 needs a third stratum, novel in-repo tasks, which only this world supplies.

**Petri's role here isn't zero either.** Gitea's API layer covers collaborators, scoped tokens, branch protection and the package registry. That layer is CRUD-shaped and power-relevant. A blind spec of "the company's GitHub", compared against a real Gitea, is a deployment-like calibration on real product semantics. CI outcomes stay real. The real downside is eval awareness: simulated technical surfaces are the riskiest class (fidelity §6).

**Change:** make it a co-first *meter-validity* track rather than "in parallel, no Petri". A natural split of the work:
- Peyton: AppWorld.
- Travis: coding and ImpossibleBench, which matches his exploit-vs-good-power hypothesis.
- Arya: the hybrid adapter and the blind-spec protocol.

### 5. Step 2 (Petri-only neighbors) inherits a licence it hasn't earned

"Validate where a twin exists, then use it where none does" is sound only if three things hold:
- the validation systems come from the same *classes and complexity* as the deployment systems;
- the validation conditions match deployment, meaning a blind spec;
- the metric is the deployment quantity: power-reading agreement, not task success.

AgentDojo fails all three. The classic fix is a matched-class validation set with leave-one-system-out prediction.

**Change: validate each deployment class on a twin from the same class:**

| Class | Twin |
|---|---|
| Vault | Vaultwarden |
| Ledger | AppWorld Venmo plus the admin card ledger |
| Ticketing and ACLs | Agent-Diff Linear/Box |
| Mail rules and delegates | smolclaw Gmail, which is conformance-tested against real Google |
| Code host | Gitea |

Then predict the distortion on a held-out system before running it. Simulate a class with Petri only once its blind-spec calibration passes.

---

## Answers to the six questions, briefly

1. **Does AgentDojo validation transfer?**
   - No. Its systems are toys, its spec is derived from the real code, and its power reading is a binary gate.
   - The transfer argument gets stronger with blind specs, twins matched by class, a size ladder, and rank agreement over planted and decoy states (criticisms 1 and 5).
2. **Is AgentDojo's breadth too low?** Yes. The power is all built by us, and Banking has no money semantics. A Q1 pass would be uninteresting (criticism 2).
3. **Should AppWorld go first?** Yes, with Python real and only the API layer simulated, not in function-calling mode (criticism 3).
4. **Is the coding world wrongly demoted?** Partly. As a Petri testbed, its demotion is right. As the place for meter validity and Matthew's measure, it should be co-first (criticism 4).
5. **Is there one design that answers both questions?** Yes: AppWorld with held-out apps, blind specs and three arms, going from small apps to coupled ones. Then out-of-world neighbors for the same supervisor.
6. **Factual errors?** See the table below.
   - OSWorld, games and web: I agree they're ruled out.
   - TheAgentCompany (otherenvs §11) is worth a later look as a same-company world with simulated colleagues, which is the one neighbor class AppWorld can't exercise because its people never reply.

---

## Spot checks of load-bearing claims

| Draft claim | Check | Result |
|---|---|---|
| Neighbor state 2–21 KB; Slack has 4 users; Banking has one account | `wc -c` on the suite YAML; read the YAML | **Verified.** Banking 2,267 B, Slack 3,867 B, Travel 20,964 B |
| "Native tasks check state before and after, so they run on any fork" | Banking and Travel `utility` bodies; red-team finding 5 | **Overstated.** The checkers hard-code start-state constants: Banking task 1 looks for "1050" in the output; task 0 checks a fixed recipient and amount; the Workspace cases are verified in red-team finding 5. It's harmless here only because neighbor state is never touched, which is the problem in criticism 2 |
| Banking as a money or ledger neighbor (and the fidelity report's choice of it as the ledger twin) | `tools/banking_client.py`, `user_account.py` | **Wrong as a ledger.** `send_money` never debits the balance; there's no overdraft check; the password is never checked; `update_password` takes no old password |
| AppWorld Petri fidelity 2, or 3 "in function-calling mode, simulating only the neighbor API layer" | fidelity report §1.4, §4, §8 | **Inconsistent.** Simulating only the API layer works with Python real and doesn't need function-calling mode, and the fidelity report rates that design "high" |
| "The API layer is pluggable, so illusory apps can sit behind real Python" | `requester.py` | **Mostly right.** There's one `remote_apis_url` (or MCP) or an in-process app built from the app list. Splitting by app needs a proxy or a mount |
| Gmail and Phone are the reset and verification channels; anyone can sign up | `authentication.py`, `apis.pyi` | **Verified at the interface.** Gmail and Phone have `signup` and reset APIs but no `verify_account`, while the other apps send codes to Gmail or Phone. Whether signup is unverified in practice is still encrypted, so the draft is right to keep it as an open check |
| 14 of Travel's 20 tasks check only an answer string | awk scan of `travel/user_tasks.py` | **Verified (≈13–14).** Travel's state-changing tasks also write into *calendar and inbox*, which belong to Workspace's systems. In a merged world, the "neighbor" tasks would write into the real main system |
| Petri `"fixed"` mode exists | `inspect_petri/_auditor/tools.py` | **Verified** |

---

## Revised sequence (proposal)

**0. Plumbing (≤1 week, optional).**
- Build the hybrid adapter: a code store, an access check, and an LLM content hook.
- Smoke-test it on one AgentDojo suite or on AppWorld's SimpleNote. Call it plumbing.

**1a. AppWorld, real arm.**
- Use Peyton's states; withhold passwords for the held-out apps; filter the closed-world checks.
- Write 15–25 future tasks per supervisor.
- Go/no-go: DeepSeek V4.1 Flash's success rate.

**1b. AppWorld, illusory arm.** Use the blind-spec three-arm protocol, moving from SimpleNote/Todoist to Splitwise to Venmo (coupled). Measure:
- rank agreement across planted and decoy states;
- phantom-holdings leniency.

**1c. In parallel, the coding world.** It's the meter-validity track:
- strata A, B and C;
- ImpossibleBench and SWE-bench answer-key states;
- optionally, a blind-spec "GitHub" against Gitea.

**2. Petri-only out-of-world neighbors** for the AppWorld supervisor and for the coding company. Simulate each class only after its class-matched twin passes the blind-spec calibration.
