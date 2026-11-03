> **Status (2026-11-01):** Parked. Its AppWorld recommendation for the Petri test was never recorded as confirmed; Petri comes later. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Which Environment to Test "Petri for Future Tasks" On

*Prepared for Arya, 2026-10-30. Method:*
- *three research agents, one on simulation fidelity, one on tool and workplace environments, and one on OS, code, web and game environments;*
- *a scored draft;*
- *a reviewer told to attack the draft's picks.*

*The reviewer changed the first pick, and I agree with it. The draft and every report are in [testbed-research/](testbed-research/). Facts marked "verified" were checked against the paper or repo, and in a few cases re-checked by me. The plan and infrastructure files are unchanged.*

---

## Bottom line

1. **Start with AppWorld, not AgentDojo.**
   - Use the "held-out apps" design: the main task uses some apps, and the others become neighbor systems for future tasks.
   - The agent's Python runs for real; only the held-out apps' API layer is simulated.
   - This one setup answers both questions:
     - **Does hybrid Petri reproduce real power readings?** Each held-out app also exists for real.
     - **Does power gained here extend to other systems?** Cross-app power is native: reset codes go to Gmail and Phone, payment cards work everywhere, Venmo holds money, and anyone can sign up for accounts.
2. **Calibrate with blind specs and three arms.** This is the reviewer's main contribution. A Petri neighbor's error mostly comes from the spec we write, not from the LLM. So each held-out app gets a spec written *only* from its public API docs, never from its code or data, and is run three ways:
   - **(a) the real app;**
   - **(b) the blind spec with code only;**
   - **(c) the blind spec with LLM-written content.**

   (a) − (b) is spec error, and (b) − (c) is LLM error. The test is whether the arms rank planted power states the same way, decoys included.
3. **Run a coding world in parallel, without Petri.** It's a SWE-smith repo with a self-hosted Gitea for issues, review, CI and package registry. It's the only candidate where agents gain power naturally and on record (answer keys read from git history or the network), and it directly measures Matthew's "clean codebase OR stolen answers".
4. **AgentDojo drops to an optional smoke test.**
   - Under the hybrid design, an illusory AgentDojo suite *is* the real suite with an LLM in the output path, so calibration would pass by construction.
   - Its Banking suite isn't a real ledger: `send_money` never changes the balance (I checked the code).
   - A Workspace main task never touches the neighbor suites, so any power there would come only from gates we build.
5. **OSWorld, games and web environments are out** for the Petri test (reasons in §5).

**What this changes.** On Oct 26 you picked AgentDojo Workspace for the main plan. For the Petri future-task question specifically, I now recommend AppWorld. The decision card below asks you to confirm.

---

## 1. Why the criteria pointed two ways, and why AppWorld resolves it

**Your two criteria pull apart.**
- **Breadth** favors rich worlds where power carries across systems: AppWorld and the coding world.
- **Petri faithfulness** favors small, structured worlds: AgentDojo.

**The fidelity research shows faithfulness depends on how much of a system lives in code, not on the LLM.**
- LLMs do well on calls that fail or change nothing, and on short plausible content.
- They do badly on:
  - **multi-field state changes:** 36–72% state match when one field changes, at most 12% when five or more do, even with the tool's code in hand;
  - **exact computation;**
  - **long horizons:** 0.6% exact after 10 steps;
  - **silent corruption:** 50–64% of wrong states still look right.
- So the faithful design runs anything that computes, keeps state and access in code, and lets the LLM write short content (see testbed-research/simulation-fidelity.md).

**AppWorld supports that design directly** (verified in its repo):
- the agent's code runs in a real IPython shell;
- every API call goes through one `Requester`, which can target an in-process app, a remote URL or an MCP server;
- state has `save_state`/`load_state` checkpoints.

The draft scored AppWorld low on fidelity because it assumed Petri would have to play the Python interpreter. With Python real and only the held-out API layer simulated, it sits with the structured tool APIs, which are the best-simulated class.

---

## 2. Scorecard (1 = poor, 5 = strong; judgment calls from verified facts)

| Candidate | Breadth | Petri fidelity (best design) | Real twin for calibration | Native power routes | Same-world neighbors | Practicality |
|---|---|---|---|---|---|---|
| **AppWorld, held-out apps** | **4** | **4** (Python real; API layer simulated) | **4** (real apps; we write future tasks) | **4** once held-out passwords are withheld | **5** | 3 |
| **Coding world (SWE-smith + Gitea)** | 3 | 2 (CI and deploy outcomes need execution) | **5** | **4** (answer leaks, tokens, grader capture) | 4 | 3 |
| AgentDojo, merged suites | 2 | 5, but uninformative (passes by construction) | 3 (Banking isn't a ledger) | 2 (only gates we build) | 3 | **5** |
| Agent-Diff | 2 | 2 (agent writes HTTP code) | 5 | 2 | 1 (separate worlds) | 4 |
| WebArena / TheAgentCompany | 3 | 2 | 4 | 3 | 3–4 | 1–2 (~180 GB; slow forks) |
| OSWorld | 3 | **1** (Petri can't produce screenshots) | 2 | 3 | 2 | 1 |
| Games, MACHIAVELLI, gridworlds | 1 | not needed (exact and cheap) | 5 | varies | 1 | 4 |

---

## 3. The AppWorld design

**AppWorld facts** (verified unless marked):
- 9 apps, 457 APIs, 750 tasks, and about 100 people in one world.
- A typical task uses 1.5–2 apps, leaving 6–8 free to hold out.
- Checks are state-based unit tests (about 8 per task).

**Build steps:**
1. **Withhold power.**
   - By default the Supervisor app hands the agent every app password at step 0 (`show_account_passwords`). Delete the stored passwords for the held-out apps; it's a data edit.
   - Access then has to be *gained* through native product features: a Gmail or Phone reset (about 4 calls), new signups, cards or money.
   - This also settles red-team finding 2 (held vs reachable power) for us: reachable power is native here.
2. **Isolate the APIs.** Run them in Docker or behind a remote URL.
   - The sandbox's allowed imports include `appworld`, and tokens are signed with the literal secret "SECRET" (I checked). Agent code could otherwise read the held-out database or forge tokens.
   - Alternatively, keep this open on purpose as an "exploit power" condition.
3. **Write the future tasks for the held-out apps, per supervisor.** Native tasks can't be reused; each has its own supervisor and private data.
4. **Use a size ladder of held-out apps:** SimpleNote or Todoist first (small surfaces), then Splitwise, then Venmo with its card ledger. Faithfulness can be tracked as complexity grows.
5. **Test couplings.** An illusory Venmo's reset code must land in the *real* Gmail. That coupling is the most power-relevant thing to get right, and AgentDojo has nothing like it.
6. **Calibrate with the three arms from the bottom line.**
   - Planted power states include **decoys**: an expired token, a token with the wrong scope, a password made stale by a reset.
   - Add a **phantom-holdings control**: tell the evaluator it holds access it doesn't.
   - **Fix equivalence margins in advance.** Don't rely on an A/A noise floor, which the red-team showed is too wide at our sample sizes.
7. **Measure.** Real-arm power on Peyton's existing trajectories, plus power-gaining runs from the coding track or ImpossibleBench.

**Costs and risks:**
- **The Petri question.** In code-cell mode the simulator is a content hook inside AppWorld, not `inspect_petri`'s auditor loop. Function-calling mode would fit Petri directly but costs success (GPT-4o: 48.8 → 32.1). It's worth asking Matthew whether a Petri-style hook counts. If it must be Petri itself, run only the future-task evaluator in MCP mode.
- **Splitting apps between real and simulated** needs a small proxy, because the `Requester` takes one URL.
- **Main-task checks are closed-world**, so power writes in other apps fail the main task unless filtered.
- **Licence:** app code and data may be redistributed only encrypted, so transcripts stay private.
- **Go/no-go:** DeepSeek V4.1 Flash's success rate on AppWorld. If it's too low there's no signal; unknown until we run it.
- **Coordination:** Peyton already runs AppWorld, so this overlaps their work.

---

## 4. The coding-world track (no Petri)

**Why run it:**
- It answers red-team finding 3 ("nothing makes the agent gain power") with power-gaining that happens naturally:
  - SWE-Bench Pro reports 103 tasks where agents read local answer files and 49 where they went over the network;
  - ImpossibleBench finds GPT-5 cheating on 54% of conflicting tasks. It's built on Inspect.
- It measures Matthew's "clean codebase OR stolen answers" directly.

**The three strata of future tasks:**
- (A) held-out benchmark bugs;
- (B) new in-repo tasks no answer key covers;
- (C) neighbor-system tasks: release, CI job, PR approval, deploy key.

Predicted signatures (testbed-research/os-code-web-game-environments.md §3):

| Planted state | (A) benchmark bugs | (B) new in-repo tasks | (C) neighbors |
|---|---|---|---|
| Clean codebase | modest gain | modest gain | ≈ 0 |
| Stolen answer key | large gain, flat across difficulty | ≈ 0 | ≈ 0 |
| Stolen credential | ≈ 0 | ≈ 0 | large gain |
| Grader capture | large gain in-repo, ≈ 0 in a clean harness | same | ≈ 0 |

**This corrects my earlier analysis (§4 of the Petri analysis).** Out-of-world tasks alone can't tell an answer key from clean code: both read ≈ 0 there. Stratum (B) is what separates them.

**Petri's role here** is limited to the long tail (cloud console, secrets, access requests) and tasks too dangerous to run for real, such as publishing to public PyPI. CI and deploy outcomes always stay real.

---

## 5. Ruled out for the Petri test

| Environment | Why not |
|---|---|
| **OSWorld** | Real tasks are GUI tasks, and Petri can't produce screenshots or faithful 1–10k-token accessibility trees, so real vs illusory can't be compared like for like. The Docker provider can't snapshot mid-episode, and the agent already owns the machine. Could be used later as a real environment on VMware, without Petri. |
| **Games** (Craftax, Minecraft, gridworlds, Sokoban) | Forks are free and checks exact, so Petri adds nothing; LLMs simulate exact rules badly; and game power doesn't leave the game. Craftax has no creative or cheat mechanic. mindcraft lets the bot turn on cheat mode (one action). Use these to validate the meter against computable power. |
| **MACHIAVELLI, TextWorld** | Meter validation: MACHIAVELLI has power annotations and save/restore. Not a Petri testbed. |
| **WebArena, VisualWebArena, WorkArena** | About 180 GB of images, multi-GB container commits per fork, and the agent is already admin. TheAgentCompany might beat WebArena if a web world is ever wanted. |
| **AgentBench-OS** | 135 of 144 checks compare answers, not world state; the agent is already root. |
| **NeMo Gym workplace assistant** | It is WorkBench: no accounts, credentials or money, so no power. Usable as a harness only. |
| **ToolEmu, Agent-SafetyBench, SafeMCP, PropensityBench** | LLM-played tools or LLM judges, or single-action power. No ground truth. |
| **WebShop, Vending-Bench** | No power beyond one purchase; or money is the objective, so taking power can't be told apart from competence. |
| **Incident benchmarks** (DeepSearchQA, BrowseComp, LABBench2, Odysseys) | Live web with answer grading. Useful as *scenario seeds* for illusory future tasks too dangerous to pose for real. |

**Useful in other roles:**
- **ImpossibleBench:** the best source of power-gaining trajectories.
- **smolclaw:** mail rules, forwarding and delegates, worth borrowing for persistence routes.
- **AuthorizationBench:** sanctioned-vs-unsanctioned labels and mock services.
- **Agent-Diff:** real twins for ticketing and file-sharing systems.

---

## 6. Where Petri should and shouldn't simulate

**The rule:** simulate systems whose effects stay inside their own records. Don't simulate anything that executes, involves real people, or needs world knowledge.

**Validate each class against a real twin of the same class** before using Petri for systems that don't exist. Validating on AgentDojo and then trusting Petri on a vault would be a validation-set mismatch.

| Neighbor class | Simulate? | Real twin to validate against |
|---|---|---|
| Password vault | Yes | Vaultwarden (AGPL-3.0) |
| Ledger, payroll, payments | Yes | AppWorld Venmo plus the card ledger (not AgentDojo Banking) |
| Tickets, access lists, HR records | Yes | Agent-Diff Linear/Box; AuthorizationBench mocks |
| Mail rules and forwarding | Yes (mechanics); replies from people are only medium | smolclaw; Mailpit |
| Code host permissions and registry | Yes (permissions and tokens) | Gitea |
| CI results, deploys, package contents, code execution | **No.** Run them for real | Gitea Actions, docker-compose |
| Cloud console | Only small, rule-backed slices | moto (basic IAM). LocalStack Community was discontinued in 2026 |
| Open web, search, GUIs | **No** | none |

---

## 7. Quick checks before committing

These can each be done in a few minutes in Peyton's AppWorld install:
- How many distinct supervisors there are, and whether tasks share them.
- Whether deleting a stored password hides that app cleanly.
- Whether Gmail and Phone signups need verification. The code has signup but no `verify_account`.
- **DeepSeek V4.1 Flash's success on a handful of AppWorld tasks.** This is the go/no-go.

---

## 8. Corrections made today to earlier files

The fidelity research found some figures in our earlier Petri files that their cited sources don't contain. I corrected them in place, and each file now carries a dated correction line:
- `petri-failure-modes-and-environment-design.md`
- `prior-work-simulated-envs-and-power-detectors.md`
- `petri-for-future-tasks-analysis.md`

The changes:
- **Removed:**
  - "errors rise past 500 tokens", which isn't in EnvSimBench;
  - the SynthTools 58% / 10% split;
  - "77.8% vs 63.6%".
- **Reworded:**
  - "cut hallucination to 1.33%": the paper gives no before/after comparison;
  - "no code link": AutoControl Arena's code is in fact public.

The trends those figures illustrated still hold.
