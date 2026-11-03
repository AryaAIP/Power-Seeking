> **Status (2026-11-01):** Parked. Draft environment survey for the Petri test, superseded by petri-testbed-recommendation.md. Start at [README.md](../../README.md); decisions are in [decisions-log.md](../../1-handoff/decisions-log.md).

# Which Environment to Test "Petri for Future Tasks" On

*DRAFT for review, 2026-10-30. A synthesis of three research reports in this folder: reports/fidelity.md, reports/toolenvs.md, reports/otherenvs.md.*

## Bottom line (draft)

1. **Arya's two criteria pull in opposite directions.**
   - **Breadth** (power that extends to many future tasks) favors rich, native worlds: AppWorld and a coding world.
   - **Petri faithfulness** favors small worlds with structured state, short calls and real twins: AgentDojo.
   - No candidate is top on both.
2. **They are two different questions, so answer them in sequence.**
   - **Q1: can hybrid Petri reproduce real future-task power readings at all?** It needs a neighbor system that exists for real, so every illusory task has a real twin. It also needs the easiest conditions for the simulator.
   - **Q2: does power gained in a realistic world extend to many future tasks,** including ones only Petri can stage?
3. **Recommendation:**
   1. **AgentDojo, as one merged "Emma Johnson" world, for Q1.**
      - Workspace is the main system; Banking, Slack and Travel are held out as neighbors.
      - Petri plays each neighbor from its real schemas and full state (2–21 KB).
      - Every neighbor task runs both real and illusory.
   2. **AppWorld with held-out apps and withheld passwords, for Q2.**
      - Its cross-app power is native: Gmail and Phone receive reset and verification codes, payment cards work everywhere, Venmo holds money, and anyone can sign up for new accounts.
      - Peyton already runs it.
      - It is also the hard stress test for Petri.
   3. **The coding world (SWE-smith plus Gitea) as a separate, Petri-free track.** It is for Matthew's "clean codebase OR stolen answers" measure. CI and deploy outcomes can't be simulated, so Petri adds little there.
   4. **Not OSWorld, games or web environments** for the Petri test.
4. **Petri should only ever simulate record-keeping systems.** Good targets are a password vault, HR/IT admin records, a bank or payroll ledger, a ticketing system, and email mechanics. CI results, deploy outcomes, package contents, code execution, open web search and GUIs need real execution or real emulators.

## Scorecard (1 = poor, 5 = strong; judgment calls from the reports' verified facts)

| Candidate | Breadth | Petri fidelity | Real twin for calibration | Native power routes | Same-world neighbors | Practicality | Best use |
|---|---|---|---|---|---|---|---|
| AgentDojo, merged Emma world | 2 | **5** | **5** | 2 (4 once gated) | 3 | **5** | **Q1: validate Petri** |
| AppWorld, held-out apps | **4** | 2 (3 in function-calling mode, simulating only the neighbor API layer) | 4 | 3 (4 with passwords withheld) | **5** | 3 | **Q2: power breadth; Petri stress test** |
| SWE-smith + Gitea coding world | 3 | 2 (CI and deploy outcomes can't be simulated) | **5** | 4 (answer leaks, tokens, grader capture) | 4 | 3 | **Real-environment track** (clean code vs answer key) |
| Agent-Diff | 2 | 2 (agent writes HTTP code) | 5 | 2 | 1 (separate worlds) | 4 | A source of real neighbor systems |
| WebArena / TheAgentCompany | 3 | 2 | 4 | 3 | 3–4 | 1–2 (~180 GB, slow forks) | Later, if at all |
| OSWorld | 3 | **1** (Petri can't produce screenshots; trees are long) | 2 | 3 | 2 | 1 (Docker can't snapshot mid-episode) | Real-only, later |
| Games, MACHIAVELLI, gridworlds | 1 | not needed (exact and cheap) | 5 | varies | 1 | 4 | Validating the meter against computable power |

Sources for less obvious entries:
- **ImpossibleBench:** the best source of power-gaining trajectories, which addresses red-team finding 3. It's built on Inspect, the same framework as Petri.
- **smolclaw:** its mail rules, forwarding, delegates and send-as give persistence routes worth porting into AgentDojo's mail.
- **AuthorizationBench:** a source of mock services and sanctioned-vs-unsanctioned labels.

## The case for each finalist

### AgentDojo, merged Emma world (Q1)

**For:**
- Small, fully visible state.
- 2–6 calls per task.
- Real tool schemas, already Inspect tools.
- Native tasks check state before and after, so they run on any fork.
- The whole neighbor set can serve as the calibration slice.
- Cheap models succeed (gpt-4o-mini 66/97).
- MIT licence; forking is a deep copy.
- The same persona already spans three suites.

**Against:**
- **Nothing is gated, so we build every cross-suite route.** This is red-team finding 1's circularity.
- **The worlds are small:** Slack has 4 users, Banking one account.
- **14 of Travel's 20 tasks check only an answer string,** so they act as controls.
- **The persona data disagree;** reconciling them is a YAML edit.
- **The benchmark is recognizable.**

**Why it's still first:** if hybrid Petri fails here, it fails everywhere. If it passes, it has been shown to work on the class of systems we'd use it for.

### AppWorld, held-out apps (Q2)

**For:**
- Native, product-feature power routes, with no gates to build. That reduces red-team finding 1.
- Its 9 apps share one person.
- State-based unit tests, with real neighbor apps.
- `save_state`/`load_state` exist.
- The API layer is pluggable (a `Requester` that can point at FastAPI or MCP), so illusory apps can sit behind real Python.
- Peyton's code and trajectories exist.

**Against:**
- Supervisor's `show_account_passwords` hands every password to the agent at step 0. Fix: delete the held-out apps' rows.
- Tasks average more than 40 API calls, and a person's slice of the data may not fit the auditor's context.
- Function-calling mode lowers success (GPT-4o 48.8 → 32.1).
- We have to write the future tasks ourselves.
- Main-task checks are closed-world and include collateral-damage tests.
- The licence forbids plain-text redistribution, so transcripts must stay private.
- **Sandbox hazard:** allowed imports plus a constant token secret could probably let agent code forge tokens. Run the APIs in Docker, or study it on purpose as exploit power.

### Coding world (separate track)

**For:**
- Natural power routes are documented: answer keys in git history, network leaks, grader capture.
- Credentials reach CI, the registry and deploy.
- Three strata separate a clean codebase, a stolen answer key, a stolen credential and grader capture (otherenvs §3):
  - held-out benchmark bugs;
  - novel in-repo tasks;
  - neighbor tasks.
- Gitea gives cheap real twins for every neighbor.

**Against as a Petri testbed:**
- CI and deploy outcomes need execution.
- Petri's marginal value is the smallest of all candidates.
- SWE-bench is heavily trained on.

## Recommended sequence (draft)

1. **AgentDojo merged world.**
   - Run hybrid Petri vs real on the neighbor suites.
   - Report real-vs-illusory differences in success, discounted steps and leniency, with a phantom-holdings control.
   - Stop if the differences exceed the A/A noise floor by more than an agreed margin.
2. **If that passes, add Petri-only neighbors of the same class:** a password vault, HR/IT admin, payroll.
3. **AppWorld held-out apps** with withheld passwords, run in function-calling mode for both arms. Measure on Peyton's trajectories plus ImpossibleBench-style power-gaining runs.
4. **In parallel, no Petri:** the coding world's three-stratum measure for Matthew's detector.

## Open checks (quick, in Peyton's install)
- How many AppWorld supervisors there are, and whether tasks share them.
- Whether deleting a stored password hides that app cleanly.
- Whether Gmail signup needs verification.
- DeepSeek V4.1 Flash's success rate on AppWorld and on AgentDojo.
