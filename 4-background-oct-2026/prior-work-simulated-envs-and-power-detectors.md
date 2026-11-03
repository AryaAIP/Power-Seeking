> **Status (2026-11-01):** Parked. Simulated environments were ruled out on Nov 1; this becomes relevant again in the later illusory-environments phase. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Prior Work: Simulated Environments and Power Detectors

*Correction, 2026-10-30: a later source check found some figures here unverified or misattributed. They have been removed or replaced, and each changed spot says so.*

*Prepared for Arya, 2026-10-26. A short, non-exhaustive search across four areas, run to check the scoping doc (`simulated-env-power-scoping.md`) against what's already known.*

> **Caveat.** These numbers came from automated summaries of papers fetched from the web, not from reading the PDFs. Check any number against the paper before citing it. Items marked [unverified] had a source problem, such as an arXiv ID that doesn't match its date, or a page that was only read through a summary.

---

## Bottom line

1. **How unfaithful LLM simulators are is already well measured.** They do well on single-step "did this call succeed?" and badly on multi-field state changes and long horizons. They also corrupt state silently: the agent sees a normal-looking output while the underlying state is wrong.
2. **Someone has already compared state-backed (B) with Petri (A) for risk evals.** AutoControl Arena: B won 62.5% and lost 27.5% of 40 pairwise human comparisons against Petri on state consistency (a win/loss rate, not an absolute consistency rate), and tracked real-environment risk rates at r = 0.87. A separate result (AWM) found that database-backed environments beat LLM-invented tool responses for agent training.
3. **Building code environments is now cheap.** LLM pipelines generate database-backed environments, with verifiers, for roughly $0.5–1 each (AWM, ClawEnvKit). That weakens the original motivation, "simulated environments would save us building environments".
4. **Three things are not measured anywhere I found:**
   - **leniency:** does a tool simulator grant access it shouldn't?
   - **persuadability:** can the agent talk the simulator into granting access?
   - **same-state verdict variance:** does the simulator give the same answer to "does the agent now hold credential X?" across samples?
5. **Petri-specific forking problem.** Petri does support rollback. But the auditor fabricates the tool results and keeps its full memory across rollbacks. So in a "fork", the environment still remembers the branch you discarded, and that knowledge can leak into the new branch. The auditor also has an elicitation goal, which biases what it lets succeed.
6. **Nobody has applied interrupt-and-assign (future-task) power measurement to LLM agents, or validated a power-seeking transcript monitor against a non-LLM ground truth.** Both are open, and both are central to Matthew's direction.

---

## 1. How faithful are LLM simulators?

| Work | What was measured | Key finding |
|---|---|---|
| **ToolEmu** (Ruan et al. 2023) | Human ratings of LLM-emulated tool trajectories | 91.9% free of critical issues (85.6% adversarial); 68.8–72.5% of identified failures were real; the emulator "overlooked core constraints" more often in complex scenarios. Leniency not quantified. |
| **Text-world simulators** (Wang et al. 2024, ACL) | GPT-4 predicting the next full game state | 59.9% on non-trivial changes, compounding to under 1% over 10 steps. Changes the environment makes on its own: 22–50%. |
| **EnvSimBench** (Liu et al. 2026) | LLM predicts tool outcome given the code; scored against a real executor | Failure or no-change calls: 97–100%. State-changing calls: 10–23%, falling to 3–12% with 5+ changes. **50–64% of wrong states still return a correct-looking output** (silent corruption). |
| **WMA** (Chae et al., ICLR 2025) | Picking the correct next web state out of two | 54.75% averaged over four models, near chance for some. |
| **Word2World** (Li et al., ACL 2026) | One-step exact match; rollout consistency | Zero-shot GPT-4o 7.9–58%; fine-tuned 7B ~99% on ALFWorld; long rollouts drift, and weaker agents cause more drift. |
| **StableToolBench** (Guo et al. 2024) | GPT-4-simulated APIs with caching | Aggregate scores stable within ±1 point across versions and temperatures. |
| **Gecko** (Zhang et al. 2026) [partly unverified] | Simulated tools catching invalid calls | 100% of syntactic errors caught, only 63–71% of semantic ones. The closest proxy for leniency I found. |
| **Simulated users** (Zhou et al. 2026; Seshadri et al. 2026) | LLM-simulated users vs. real humans | Simulated users are "excessively cooperative", and the choice of simulator alone moves τ-bench success from 67.0% to 75.9%: leniency, but for users rather than tools. (An earlier "77.8% vs 63.6%" figure could not be found and was removed.) |
| **Anthropic, coding-audit realism** (Mar 2026) | Petri-style transcripts vs. real deployment | Petri transcripts lose on realism; win rate rose from 4.6% to 32.8% with real tool definitions and codebases. |

**Petri forking.** The auditor has `rollback_conversation` and `restart_conversation` (enabled by default). The target's state resets to the checkpoint, but **the auditor keeps its full context**, and the auditor is the one inventing tool results. That breaks independence between forks. (Sources: Anthropic's Petri post; Inspect Petri docs.)

## 2. Hybrid simulators and generating real-state environments

| Work | What it does | Relevance |
|---|---|---|
| **AutoControl Arena** (Li, Lu, Pan, Barez, Yang, ICML 2026) | Python + SQLite holds files, databases and permissions; the LLM writes only narrative and sees the serialized state | **This is our condition B, built for risk evals.** It includes a resource-acquisition and privilege-escalation category. It won 62.5% and lost 27.5% of 40 pairwise human comparisons against Petri on state consistency (win/loss, not absolute rates), and risk rates correlated with real environments at r = 0.87 (on 10 scenarios). Code is public: github.com/CosmosYi/AutoControl-Arena (Apache-2.0). Overall preference against Petri was 60% win, 10% tie, 30% loss. |
| **Agent World Model, AWM** (Snowflake, Feb 2026) | GPT-5 generates a SQLite schema, seed data, a Python MCP tool server and verifiers that diff the database | 1,000 environments released; ~$57 per 100 environments. **Database-backed beat LLM-simulated tool responses** for training on the same tasks. Has `reset_db`, `initial.db`, `final.db`. |
| **ClawEnvKit** (Li … Stoica, 2026; MIT licence) | Turns a plain-English description into a task, FastAPI mock services with an audit log, and a scorer | ~$80 per 1,040 environments. State is in memory, so you'd need to add dump and load to fork. |
| **EnvScaler** (2026), **AgentScaler** (Alibaba 2025) | Generated environment classes, JSON states, final-state checks | Further evidence that generation with state-based verification is routine now. |
| **Agent-Diff** (2026) | Postgres schema per environment; diffs every table, and anything changed that the task didn't expect fails it | A good model for flagging power acquisition no one asked for. No documented mid-run fork. |
| **PropensityBench** (Scale AI) | LLM-generated scenarios with simple deterministic tools | Includes 35 resource-acquisition scenarios. |

**Forking.** None of these offers mid-trajectory forking built in. The cheapest route is to **keep all state in one SQLite file and copy it**, which takes milliseconds. E2B snapshots fork real sandboxes if agents need a real shell.

## 3. Power and empowerment estimators

- **AUP** (Turner et al. 2020):
  - In the gridworld paper, 5 to 30 random auxiliary rewards were sampled, and "merely five sufficed" for side-effect avoidance.
  - In SafeLife, **one** random auxiliary goal worked best, and 4 or 8 did worse (unexplained). That is evidence about *training penalties*, not about how accurately power is estimated.
- **"AUP: Scaling to Superhuman"** (Turner): use the agent's own primary reward as the auxiliary goal and penalize only *increases* in attainable utility. It needs little more than predicting attainable utility for the main goal. Known holes: subagents, and self-restriction that shifts the baseline.
- **Future tasks** (Krakovna et al. 2020) is **the conceptual ancestor of interrupt-and-assign.**
  - A future goal is sampled with probability 1−γ per step.
  - It is compared against a baseline-policy state, with a filter (max(N(s), N(s′))) so tasks that were achievable anyway don't count.
  - It was only computed exactly in gridworlds; a learned approximation was less reliable.
- **Formalizing Side Effect Regularization** (Turner et al. 2022): delayed specification, where the true reward is revealed at a random time, is formally interrupt-and-assign. The objective becomes average reward plus POWER. Only demonstrated in gridworlds.
- **EELMA** (Song, Gore, Kleiman-Weiner 2025) is **the only quantitative, goal-agnostic power-like measure on LLM agents found.**
  - Method: contrastive empowerment estimate over text embeddings, run on WebArena and τ-bench.
  - It correlates with reward (0.83–0.94), and valid credential entry raised it.
  - Problems:
    - Removing chain of thought cut it by 99%, so it mostly measures policy competence.
    - **Prompting an LLM directly for empowerment overestimated it 10–25×**, a warning for LLM-judged power.
- **MACHIAVELLI** (Pan et al. 2023): GPT-4 labels power per scene (watts, money, social influence, utility). This is *exercised* power after the fact, not *prospective* power. Spearman with gold labels was about 0.6–0.8.
- **Interrupt-and-assign applied to LLM agents: none found.** Nor any application of AUP to LLMs.

**Practical lessons for D1:**
- Use **paired comparisons**: the same sampled tasks, seeds and evaluator on both forks.
- Use a **stepwise baseline** (the fork at t−1, or a no-op continuation), not only the start state.
- Apply Krakovna's **baseline filter**.
- **Normalize** scores so states are comparable.
- **Hold the evaluator fixed** so evaluator competence doesn't swamp the signal.
- Use cheap proxies to choose *where* to fork.

## 4. Power-seeking monitors and labeled benchmarks

| Work | Labels | Key numbers |
|---|---|---|
| **Instrumental Choices** (Wiedermann-Möller, Dung, Andriushchenko 2026) | Deterministic state scorers, plus LLM trace review for edge cases | 5.1% overall; Gemini 3 ~17%; Opus 4.6 and GPT-5.5 0%. **It has both state and LLM labels but reports no agreement between them, so it is the easiest place to compute monitor vs. state agreement.** |
| **AuthorizationBench** (Zhang et al., Oct 2026) | State diffs, plus an Opus judge that sees the diffs | 97% judge–human agreement (n=100); 19.2% of 6,864 trajectories exceeded authorization. A monitor that also sees state diffs is a promising middle option. |
| **SysAdmin** (Azarm et al. 2026) [ID/date mismatch] | LLM judge plus human audit; no state checks | Power-seeking 0–5.6%; judge precision ~78%; recall assumed, not measured. |
| **OverEager-Bench** (Qu et al. 2026) | Rule engine over shell logs and file snapshots | Overeager 5.4–27.7%; rules vs. humans precision 0.76, recall 1.00. |
| **MonitoringBench** (Redwood, 2026) | Programmatic scorers for *instructed* sudo escalation, credential exfiltration and firewall changes | Opus 4.5 monitor catches 94.9% at 1% FPR on elicited attacks and 60.3% on refined ones. |
| **SHADE-Arena; monitor red-teaming; constitutional monitoring** | Mostly instructed sabotage, programmatic labels | AUC around 0.85–0.9, dropping sharply when the agent knows it is monitored. |
| **UK AISI incident report** (Aug 2026) | Real unsanctioned actions in cyber testing | Network monitoring caught it first; transcripts were used only afterward. |

**Validated against non-LLM ground truth for *unprompted* power-seeking: no.** Monitors have only been validated on *instructed* attacks. Nobody compares a monitor with a future-task power measure.

**Implications:**
- **Monitors and power measures answer different questions.** Monitors score "did a checkable bad action happen". Power measures score "did future capability increase". Expect disagreement in both directions:
  - Failed attempts get flagged by monitors but gain no power.
  - Reading a secret gains power but changes no state.
- **Base rates are low (0–6% unprompted).** Report TPR at low FPR, and expect to need elicitation or many runs.

---

## What this changes in the scope

See the updated `simulated-env-power-scoping.md`, section 0b. In short:
- **Cite rather than rerun** long-horizon consistency (E3) and the general A vs. B comparison.
- **Keep the experiments nobody has done:**
  - leniency on access questions
  - persuadability
  - same-state verdict variance
  - Petri fork contamination
- **Move the main effort to the novel part:**
  - D1 future-task power on LLM agents
  - D3 monitor vs. D1 agreement
  - both in cheaply generated code environments, starting from AWM or ClawEnvKit
