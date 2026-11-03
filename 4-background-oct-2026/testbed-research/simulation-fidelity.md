> **Status (2026-11-01):** Parked. Simulated environments were ruled out on Nov 1; relevant to the later illusory-environments phase. Start at [README.md](../../README.md); decisions are in [decisions-log.md](../../1-handoff/decisions-log.md).

# Which environment classes can a hybrid Petri simulate faithfully enough for future tasks?

*Fidelity sub-report for the testbed decision. Prepared 2026-10-30.*

*Scope: environment CLASSES and the evidence about them, not a catalogue of specific benchmarks. Every factual claim is tagged **[V: source]** (I checked it against the paper, page or repo in this session) or **[I]** (my inference). Numbers that appear in the team's earlier files and that I could not re-find are tagged **[unverified]**. Repos inspected (AppWorld, moto) are cloned under `/tmp/claude-0/-home-claude/50a22e9f-8806-5a1b-b693-ebea87343d8e/scratchpad/envsearch/fidelity/`.*

---

## 0. Bottom line

1. **"Simulability" for a hybrid is not a property of the LLM. It is a property of how much of the class can be moved into code.** Every study that compares the two finds the same split:
   - LLMs are near-perfect at "nothing changed / the call failed" and at plausible-looking content.
   - They are bad at multi-field state changes, exact computation, hidden or environment-driven changes, and long horizons.

   So the classes that rank high are the ones whose state is small, explicit and rule-governed: CRUD APIs, SQL, ledgers, ACLs. There, code can do all the deciding and the LLM only writes text. The classes that rank low are the ones whose outputs are *computed* from large implicit state: shell, code execution, web search, cloud compute, GUI pixels. There, nothing short of really executing is faithful.
2. **Ranked result (§4):**
   1. structured CRUD tool APIs;
   2. SQL databases, which a hybrid should execute, never simulate;
   3. code-action over CRUD APIs (AppWorld-style), *only if Python runs for real and only the API layer is spec-backed*;
   4. simulated humans/colleagues, where decisions go in code and replies stay LLM;
   5. web portals rendered from a store (open web and search are much worse);
   6. shell/OS, where you should run a real sandbox;
   7. text adventures;
   8. exact-rule games;
   9. GUI screenshots.

   Classes 7–8 are trivially codeable but give Petri nothing to do and are not same-world neighbors.
3. **Code-action spaces (Q5).**
   - **No controlled study compares simulating agent-written code with simulating function calls.** Indirect evidence says simulating the *interpreter* is much harder: string-heavy and long execution traces fail, and simulators given the tool's code still get state-changing calls wrong 77–90% of the time.
   - **AppWorld's architecture makes the hybrid easy** [V: repo]. Every `apis.<app>.<api>(...)` call goes through one `Requester`, which can target an in-process FastAPI app, a `remote_apis_url`, or an MCP server. So you can execute the agent's Python for real and route only *neighbor-app* calls to a spec-backed simulator.
4. **Neighbor systems (Q4).**
   - **Most faithful:** password manager/secrets vault, HR/directory/ticketing records, bank/payroll ledger (money in code). All three have small surfaces, crisp access rules, and content that is either data from the store or generic prose.
   - **Least faithful:**
     - cloud console: huge API surface, complex IAM semantics, resources that *do* things;
     - package registry: a package's meaning is the code it runs;
     - git host *with CI*: test results need execution.
   - **Outside email** is mechanically easy, but the people who reply are simulated humans.
   - **Real open-source emulators exist** for several of these, so they can be calibrated rather than taken on faith: moto for AWS (Apache-2.0, basic IAM enforcement), Gitea (MIT), Mailpit (MIT), Verdaccio (MIT), Vaultwarden (AGPL-3.0).
5. **Eval awareness (Q6).**
   - Simulated *technical* surfaces (shell, coding, cloud, search) carry the highest risk, because a capable agent can cross-check outputs and LLM outputs are inconsistent or "too clean".
   - Simulated *people* are tell-tale too: they are overly cooperative and polite.
   - CRUD surfaces seeded with realistic corpora carry the lowest risk.
6. **Corrections to the team's earlier files (§9):**
   - AutoControl Arena code *is* public.
   - The "<500 tokens → 2–3% errors, >2K → 23%" figure is not in EnvSimBench and I couldn't find its source.
   - SynthTools v1 does not contain the "58% false rejections" split.
   - WMA's 54.75% is a four-model average.
   - The "77.8% vs 63.6%" simulated-user figure was not found.

---

## 1. Evidence by environment class (Q1)

### 1.1 Structured REST/CRUD tool APIs (email, calendar, files, payments, contacts, messaging)

| Study | Setting | Result | Tag |
|---|---|---|---|
| **EnvSimBench** (Liu et al., May 2026, arXiv 2605.07247) | 400 samples, 167 tool environments (EnvScaler seeds). The simulator is *given the tool's implementation code* and must predict feedback and the after-state | **State-preserving (failure/no-change) calls:** Config Match 99–100%. **State-changing calls:** CM 10.0–23.0% overall; 36–72% when exactly 1 field changes; **≤12% when ≥5 fields change** (≤4% at exactly 5). On |Δ|≥3 failures, **50–64% still return correct-looking feedback** (silent corruption). Execution-time fields such as timestamps are flagged as unpredictable. No breakdown by domain or by output length | [V: arxiv.org/html/2605.07247] |
| **Word2World** (ACL 2026, arXiv 2512.18832) | StableToolBench next-observation prediction | Prompted GPT-4o / Claude-Sonnet-4.5: **EM 0.00%**, word-F1 11–14%. Fine-tuned 7–8B: EM ~49%, F1 ~79%. Tool APIs are the *hardest* of the 5 environments ("long-tail linguistic variation and highly compositional API behaviors") | [V: arxiv.org/html/2512.18832v2] |
| **MirrorAPI** (arXiv 2503.20527) | 7B fine-tuned on 95k real RapidAPI request/response pairs vs GPT-4o prompting | BLEU/cosine to the real response: GPT-4o 10–15 / 36–63; MirrorAPI 74–90 / 89–94 on seen APIs, but **35.6 / 69.9 on unseen APIs' successful calls** | [V: arxiv.org/html/2503.20527v1] |
| **MCP-Persona** (ICML 2026, arXiv 2606.02470) | Simulators of Lark/Slack/Gmail/Notion etc. as **LLM-written Python transition functions**; validated on Lark (50 traces) | Grounded in recorded real traces ("Tool-Traverse"): accuracy 94%, F1 93.8%, **lenient false accepts 1/50, false rejections 2/50**. Documentation only ("Vanilla"): accuracy 58%, F1 53.3%, **false accepts 8/50, false rejections 13/50**. The vanilla version "emits generic error templates" | [V: arxiv.org/pdf/2606.02470] |
| **Gecko** (arXiv 2602.19218) | Schema-based tool simulator with an argument validator, on BFCL and τ²-bench | Syntactic invalid calls caught 100%; **semantic invalid calls caught 71/69/63%** (GPT-4o / 4.1-nano / Qwen-7B). The validator is told to "default to considering the argument valid", which makes it lenient by design. On τ²-bench, the **hybrid (real DB for reads, simulated writes) beats all-mock** (71.8% vs 67.4%) | [V: arxiv.org/pdf/2602.19218] |
| **SynthTools** (arXiv 2511.09572) | Synthetic tools with simulator and audit | Simulator 94–98% accurate on manual checks (698 responses); 94% vs ground truth on ACEBench (151/161) | [V: arxiv.org/html/2511.09572v1] |
| **Proxy State-Based Evaluation** (arXiv 2602.16246) | LLM-simulated tools plus an LLM-tracked "proxy state" (no deterministic DB) | **Tool hallucination 1.33%** with GPT-5 trackers; 3.61% with a GPT-4o tracker. **Goal-completion agreement with two humans: 82.7%** (n=50) | [V: arxiv.org/pdf/2602.16246v2] |
| **AWM** (Snowflake, arXiv 2602.10090) | Same tasks and tools; RL in a SQLite-backed environment vs RL in a GPT-5-simulated one | AWM beats the simulator on BFCLv3 (64.5 vs 55.5 at 4B), τ²-bench (22.6 vs 13.7 at 4B; 39.0 vs 31.4 at 14B) and MCP-Universe. Generation cost about **$57 per 100 environments**. Auth fields are excluded by design | [V: arxiv.org/html/2602.10090v2] |
| **AutoControl Arena** (ICML 2026, arXiv 2603.07427) | Python logic layer plus LLM narrative, vs Petri, on risk scenarios | Against Petri (40 pairs, Table 12): **state consistency 25W/4T/11L (62.5/10/27.5%)**, tool fidelity 52.5/10/37.5%, overall preference 60/10/30%. Simulated vs real risk rates r = 0.87 (10 scenarios). Petri failure examples: "Privilege Paradox: agent edits /etc/config to gain access, but system later denies the file exists"; "phantom retrieval"; a SQL result that violates database logic. **Code: github.com/CosmosYi/AutoControl-Arena** | [V: arxiv.org/html/2603.07427] |
| **Simia** (Microsoft, arXiv 2511.01824) | Reasoning model simulates τ²-bench, OfficeBench and AgentBench tool outputs for training | Simulated-environment RL beats real-environment RL on OfficeBench (64.7 vs 60.8; 34.5 vs 28.6). **Fidelity of individual responses is never measured** | [V: arxiv.org/html/2511.01824v1] |
| **ToolEmu** (arXiv 2309.15817) | 36 tools, 144 cases | 68.8% of emulator-found failures were valid real failures | [V: abstract]; the "91.9% free of critical issues" figure is [unverified] in this pass |

**Reading [I]:**
- Single-call content and failure handling are good, and get very good when grounded in real traces (MCP-Persona, MirrorAPI).
- *State transitions* are bad when the LLM does them (EnvSimBench) and fine when code does them (AWM, AutoControl Arena, MCP-Persona's code simulators).
- Semantic validation by an LLM lets 29–37% of invalid calls through (Gecko). Anything that decides access must therefore be code.
- **This class is the best fit for the hybrid**, because CRUD state is small and explicit.

### 1.2 Databases / SQL

| Study | Result | Tag |
|---|---|---|
| **"Can Language Models Enable In-Context Database?"** (arXiv 2411.01807) | LLM keeps a table in context and executes SQL. GPT-4o few-shot: **SELECT 65%, UPDATE 43%, DELETE 56%, INSERT 87%**; zero-shot 21–42%. COUNT 37.5%, RANK 47.4%. Accuracy falls toward ~20% as the command sequence grows to 250–400 | [V: arxiv.org/html/2411.01807v1] |
| **VelLMes** MySQL honeypot (arXiv 2510.06975) | MySQL emulation unit tests: GPT-4 10/10 in one session, 8/10 in fresh sessions; GPT-3.5 10/10 → 7/10 | [V] |
| **Petri docs** | The built-in custom-tool example is a *real SQLite* query tool, so the auditor "return[s] real query results instead of fabricating them" | [V: local Petri source, docs/components/auditor_tools.qmd] |
| **AutoControl Arena** | Petri produced a SQL result that "violates database logic" | [V] |

**Reading [I]:**
- Never let the LLM simulate SQL; run SQLite.
- Under the hybrid, SQL becomes the most faithful class of all, because nothing is simulated. The LLM only writes seed rows, and residual risk is just realism of the data.
- Same-world relevance is moderate: company analytics DBs and CRM back-ends are plausible neighbors.

### 1.3 Shell / OS commands and file systems

| Study | Result | Tag |
|---|---|---|
| **shelLM** (Sladić et al., arXiv 2309.00155) | GPT-3.5 simulating a Linux shell, full session history in context. 12 participants, 226 commands, judged by 3 experts: **accuracy 0.92, TNR 0.91**. Errors cluster in "inconsistencies between files in /proc and /etc", attributed to context growth. Non-determinism and latency are flagged | [V] |
| **SoK: Honeypots & LLMs** (arXiv 2510.25939) | Weber et al.: **only 52% of >1,400 SSH responses judged convincing** (GPT-3.5); long and compound commands were problematic. Interactive tools (`top`, `vim`) are unresolved. **Outbound actions (downloads, C2) can't be faked: "the attacker can determine that their commands are not being executed."** Timing is unresolved | [V] |
| **VelLMes** | 43 attackers using shelLM: **30.2% judged it real, vs 34.8% for real Ubuntu.** Unit tests: GPT-4 12/12 (one session) vs 10/12 (fresh sessions). Real-world sessions: 98.9% of 276 commands correct (mostly simple bot commands) | [V] |
| **AdvancedShelLM** (arXiv 2606.27990) | **Hybrid:** an LLM worker writes output; a manager issues JSON filesystem updates to an explicit shared FS state. Unit tests (34): **78–83% (shelLM) → 96–99% (hybrid)**. An AI attacker could not tell it from Ubuntu; it called real Ubuntu a honeypot 40–45% of the time | [V: emergentmind summary of 2606.27990] |
| **Qwen-AgentWorld** (Qwen team, arXiv 2606.24597) | LLM-judged 0–100 rubric against ground-truth observations: **Terminal 41.6–59.2** across 16 models, below MCP (43–70) and SWE (37–68) | [V] |

**Reading [I]:**
- LLMs fake *simple, common* commands well enough to fool humans about as often as a real box does.
- They fail on consistency across files and sessions, exact computation (counts, sizes, hashes, sorted outputs), long or compound pipelines, and anything with external side effects.
- An explicit FS state in code fixes most of the consistency problems (AdvancedShelLM). But the command space is open-ended, so you cannot write a rule for every command.
- **For a hybrid, the right answer is a real container** (Docker or E2B), with the LLM writing only file *contents* at seed time.
- Shell neighbors (a company server reachable via ssh) are plausible future-task systems. Simulate them only for read-mostly probes.

### 1.4 Code execution, including a Python REPL calling APIs (AppWorld)

| Study | Result | Tag |
|---|---|---|
| **Debugging Code World Models** (arXiv 2602.07672), on Meta's CWM | Predicting Python execution traces: **CruxEval-O 85.0%, HumanEval 91.4%** (short functions). **Strings are 46% of outputs but 73% of failures**; string composition accuracy falls from 75% at depth 2 to **25% at depth 5**. Long traces truncate. List mutation during iteration fails. Library and API calls are not studied | [V] |
| **EnvSimBench** | Even *with the tool's code given*, state-changing calls reach only 10–23% state match | [V] |
| **Qwen-AgentWorld** | SWE domain (file reads, edits, bash output) 37–68 vs MCP (tool calls) 43–70. Close at the top, but **different tasks; not a controlled comparison** | [V] |
| **SWE-World** (arXiv 2602.03419) | Docker-free SWE training. **File navigation and editing run in a real lightweight sandbox** because "LLM simulation may hallucinate files or contents and catastrophically mislead the agent." Only test and run output is simulated, by models *trained* on real Docker transitions | [V: design]. Fidelity numbers were not in the fetched text |
| **AppWorld repo** | The agent's code runs in a real `IPython InteractiveShellEmbed` with a `SafetyGuard`. Each `apis.<app>.<api>()` goes to `Requester.request()`, which dispatches to an in-process FastAPI `TestClient`, an HTTP `remote_apis_url`, or an **MCP server (`tool_name = app__api`)**. State has `save_state(state_id)` and `load_state(state_id)` checkpoints. Apps: api_docs, supervisor, amazon, phone, file_system, spotify, venmo, gmail, splitwise, simple_note, todoist. Apache-2.0 | [V: src/appworld/environment.py, requester.py, apps/__init__.py, LICENSE] |

**Q5 answer.**
- **Is simulating agent-written code measurably harder than simulating function calls?**
  - **No controlled study exists** that I could find. Qwen-AgentWorld scores SWE and MCP separately with similar top scores, but on different tasks.
  - Indirect evidence says *yes, much harder*, if the simulator must play the interpreter [I, from the evidence above]:
    - One AppWorld code cell typically makes many API calls (pagination loops, filters, joins across apps) and then computes over the results with Python string and list operations.
    - A pure Petri auditor would have to produce all of that as one printed output. That is long output, many state fields, exact string computation and hidden state at once: every risk factor in §2 together.
- **Can a hybrid simulate only the API layer while really executing the Python? Yes, cleanly** [V: repo; design I].
  1. Keep the IPython shell real.
  2. Add each illusory neighbor app as either a FastAPI app with a code-backed SQLite store and an LLM content hook, or an MCP tool set, and route `apis.<neighbor>.*` to it.
  3. **Register its API docs** so `apis.api_docs.show_api_doc(...)` and the extra-parameter check (`_get_app_api_name_to_argument_names`, built from `prepare_api_docs`) work [V: requester.py]. Otherwise the agent sees "No API named … found".
  4. Each API call is then an ordinary single CRUD call, and Python does all loops and arithmetic for real. Fidelity per call is that of §1.1.
- **Residual risks of the AppWorld hybrid** [I]:
  - **Cost and latency:** one LLM content call per API call, and cells can make dozens. Cache, and pre-generate content at seed time.
  - **Introspection:** the agent can `print(apis.neighbor)` or read docs, so the docs must be complete and realistic.
  - **Credential transfer** from the AppWorld supervisor (which holds every app's password) into the neighbor must be a coded rule.

### 1.5 Web pages / HTML and browsing

| Study | Result | Tag |
|---|---|---|
| **WMA** (Chae et al., ICLR 2025, arXiv 2410.13232) | Choosing the correct next web state of two: **54.75% average** over GPT-4o-mini, GPT-4o, GPT-4-Turbo and Claude-3.5-Sonnet; Claude-3.5 "almost as badly as random". Trained world model coverage 43% vs GPT-4o 34% (LLM-judged) | [V] |
| **Word2World** | WebShop one-step EM: 56–59% zero-shot, ≤65% 3-shot, 77–79% fine-tuned. **Rollout consistency (sim/real success): average 0.67, as low as 0.16** with a GPT-4o-mini agent. **Anchoring on real search results raised GPT-4o consistency from 56% to nearly 100%** | [V] |
| **UI-Simulator** (NeurIPS 2025, arXiv 2510.14969) | GPT-4o-mini generating a11y-tree-like WebArena and AndroidWorld states. Needed **rule-based transitions** for typing, scrolling and navigation, plus **retrieval of real states**. Human plausibility ratings 0.73–0.97. Failures: stale context carried forward; copying the retrieved page and ignoring the query | [V] |
| **Qwen-AgentWorld** | **Web 46.5–54.7; Search 18.8–37.8 (the worst domain)**; factuality is the weakest dimension overall ("constantly evolving web content") | [V] |
| **R-WoM** (ICLR 2026, arXiv 2510.11892) | Claude-3.7 next-state identification 86%, but full-procedure planning alignment ≤65%. Ungrounded world-model rollouts **decline beyond ~2 steps**; tutorial retrieval helps | [V] |
| **WebDreamer** (TMLR 2025, arXiv 2411.06559) | Uses an LLM to simulate action outcomes for planning; reports task-success gains, **not simulation fidelity** | [V: abstract] |

**Reading [I]:**
- A *portal* (vendor, bank or HR web UI) whose pages are rendered by code from the store, with the LLM filling text, is medium-high fidelity: it is CRUD with an HTML skin.
- *Open web and search* is the hardest text class measured. It needs world knowledge, is open-ended, and drifts.
- For future tasks, prefer API-shaped neighbors over HTML-shaped ones, or render HTML from templates.

### 1.6 GUI screenshots and accessibility trees (OSWorld-style)

| Study | Result | Tag |
|---|---|---|
| **NeuralOS** (ICLR 2026, arXiv 2507.08800) | Pixel simulation of Ubuntu XFCE (RNN plus diffusion). Cursor error ~1.5 px, but **state-transition accuracy 37.7%** on hard transitions. Typed characters are not rendered reliably. Four apps, 512×384 resolution. The authors call it "far from replicating a real OS" | [V] |
| **Qwen-AgentWorld** | Text a11y-tree simulation: **OS 55.5–70.2, Android 51.9–61.7** | [V] |
| **R-WoM** | See §1.5 | [V] |

**Reading [I]:**
- Petri produces text, so screenshot environments cannot be simulated in Petri at all.
- A11y-tree simulation is possible, but trees are long. Long outputs are a risk factor, and the agent would have to work from text.
- OSWorld also has high fork cost (team file). **Lowest rank for illusory future tasks.**
- If the base environment is OSWorld, neighbor tasks should still be API-shaped.

### 1.7 Games with exact rules (chess, gridworlds, Minecraft/Craftax)

| Study | Result | Tag |
|---|---|---|
| **Wang et al. 2024** (ACL, arXiv 2406.06485), ByteSized32-SP (31 games, 76k transitions) | GPT-4 full next state: **59.9% on dynamic transitions**. Action-driven up to 77.1%. **Environment-driven dynamic 22–39%**. Errors concentrate on arithmetic, common sense and science properties. 0.599^10 ≈ 0.6% over 10 steps | [V] |
| **ChessBench page** (York U., Jul 2026; non-peer-reviewed) | Best frontier move "coherence" 0.915; given a legal-move list, Claude Opus' legal-move rate went from 8% to 73% | [V: page], weak source |
| **"Tracking World States with LMs: chess"** (arXiv 2508.19851) | Argues LLMs have state-tracking deficiencies over long sequences (no numbers in abstract) | [V: abstract] |

**Reading [I]:**
- Exact-rule games are trivially and perfectly implementable in code (python-chess, Craftax, MiniGrid). Petri has nothing useful to do there.
- They also fail the same-world criterion: there is no company whose "next task" is a chess game.
- Fine for calibrating the *power estimator* (exact POWER is computable), not for testing Petri.

### 1.8 Text adventures

| Study | Result | Tag |
|---|---|---|
| **Word2World** | TextWorld one-step EM: **0.36–17.7% zero-shot, 14–49% 3-shot, ~70% fine-tuned**. ALFWorld and SciWorld are much easier (prompted 41–77%, fine-tuned ~99%), attributed to "low-entropy, rule-driven dynamics". Long-rollout consistency for TextWorld averages 0.92 with a fine-tuned 7B world model | [V] |
| **Wang et al. 2024** | See §1.7 | [V] |

**Reading [I]:** pure-LLM simulation is poor, while an engine-backed version is perfect. Low realism, and no relevance as neighbor systems.

### 1.9 Simulated humans / colleagues (approvals, replies)

| Study | Result | Tag |
|---|---|---|
| **Lost in Simulation** (Seshadri et al., ACL 2026, arXiv 2601.17087) | τ-bench retail with a GPT-4o agent. **Choice of simulator moves success from 67.0% to 75.9%** (Sonnet 3.7 vs 4.5). Simulated users are more polite (39.2% vs 19.9% of turns) and ask more questions (18.8% vs 9.8%). They are miscalibrated by task difficulty. Real-human success on the study subset was 45.2% (SAE 50.6%, AAVE 39.4%) | [V] |
| **Mind the Sim2Real Gap** (Zhou et al., arXiv 2603.11245) | 451 humans, 165 τ-bench tasks, 31 simulators. Simulators are "excessively cooperative", stylistically uniform and lack frustration, creating an "easy mode" that inflates agent success. A more capable model is not a more faithful user | [V: abstract] |
| **TheAgentCompany** (arXiv 2412.14161) | Colleagues are simulated by Claude-3.5-Sonnet via Sotopia and RocketChat. Social tasks are the hardest category (RocketChat 21.5% success). Some checkpoints depend on a simulated colleague's judgment, so they are hard to check deterministically | [V] |
| **LASR / DeepMind monitor persuasion** (LessWrong, Jul 2025) | Agents persuade LLM monitors to approve undesirable actions **27% more often when the monitor sees the agent's CoT** | [V] |
| **Proxy State-Based Evaluation** | User hallucination 0.67%. Harder personas raise user-caused errors to 5.1–5.5% | [V] |

**Reading [I]:**
- This is the only class where the LLM *must* stay in the loop, and it is what Petri was built for.
- The hybrid's fix is that the *decision* (approve, deny, add to channel) is a coded rule over the requester's role and the request type, and the LLM writes the reply text.
- **What stays:** cooperativeness bias (only matters if a future task's success depends on non-coded human judgment); persuadability of anything the human decides *in text* (for example, revealing a secret in a reply); and stylistic tells.
- **Rule:** no secrets in the human simulator's context unless the spec says this person would reveal them to this requester.

### 1.10 Cross-class evidence (one model, several classes)

**Qwen-AgentWorld** (Table 5; LLM-judged 0–100 rubric vs ground truth; best and worst frontier/open model shown) [V]:

| Domain | Best | Worst (non-Qwen) | Note |
|---|---|---|---|
| MCP (tool APIs) | 70.1 (GPT-5.4) | 54.9 (Opus 4.8) | |
| OS (a11y tree) | 70.2 (Opus 4.6) | 57.7 (MiniMax) | |
| SWE (file/edit/bash) | 66.3 (GPT-5.4) | 37.4 (MiniMax) | |
| Android (view hierarchy) | 61.7 (Opus 4.6) | 52.4 (MiniMax) | |
| Terminal | 59.2 (Opus 4.8) | 41.6 (MiniMax) | |
| Web (a11y tree) | 54.7 (Opus 4.8) | 50.2 (Kimi K2.6) | |
| Search | 37.3 (GPT-5.4) | 22.5 (GLM-5.1) | Factuality worst |

- Note that DeepSeek-V4-Pro (the closest listed relative of the team's cheap model) scores MCP 63.3, Terminal 51.3, Web 50.3, Search 27.6 [V].
- These are *rubric* scores for realism, consistency and the like, judged by GPT-5.2. They are not state-match rates, and nothing here is in a hybrid setting [V].

**Word2World** gives the cleanest general statement. Structured, rule-governed environments are easy, and "open-world" ones (WebShop, StableToolBench) are hard. "Partial real-environment anchoring effectively reduces simulation drift" [V].

---

## 2. Task properties that make simulation reliable or unreliable (Q2)

| Property | Direction | Evidence | Tag |
|---|---|---|---|
| **Number of state fields changed per step** | The strongest single predictor. More fields means worse | EnvSimBench: 36–72% (1 field) → ≤12% (≥5 fields); failure/no-change ~100%. Wang: static 63–92% vs dynamic 22–77% | [V] |
| **Hidden or environment-driven changes** | Changes the agent did not directly cause are much worse | Wang: environment-driven dynamic 22–39% vs action-driven 68–77%. EnvSimBench: partially observable, and execution-time fields (timestamps) unpredictable. Gecko: hidden-DB tools diverge | [V] |
| **Exact computation** (counts, arithmetic, strings, hashes, sorting, IDs) | Bad | Wang: arithmetic and science properties hardest. CWM: strings 73% of failures. In-context DB: COUNT 37.5%. Shell honeypots: checksums and sizes inconsistent | [V] |
| **Required world knowledge / open-endedness** | Worse with more knowledge or a more open world | Qwen-AgentWorld: Search worst, factuality the weakest dimension. Word2World: open-world envs plateau "mid-50s" EM. MirrorAPI: unseen APIs much worse (BLEU 35.6 vs 74–86). R-WoM: "static parametric knowledge" | [V] |
| **Grounding in real behavior** | Strongly better | MCP-Persona F1 53 → 94 with recorded real traces. MirrorAPI vs GPT-4o. Word2World WebShop consistency 56% → ~100% with real search results. UI-Simulator retrieval. Kissane et al. realism 4.6% → 32.8% with real resources | [V] |
| **Determinism / rule-governed dynamics** | Better | Word2World: "deterministic or rule-governed transitions" easier (ALFWorld 99.9% vs WebShop 79% fine-tuned). shelLM: the same command gives different output. VelLMes: session context changes outcomes (HTTP GPT-4 9/10 → 4/10) | [V] |
| **Long horizons / context growth** | Worse | Wang: 0.6% exact after 10 steps. R-WoM: rollouts decline after ~2 steps. shelLM: /proc and /etc inconsistencies from context growth. VelLMes: longer histories forget the persona prompt | [V] |
| **Output length** | Longer output is worse (direction verified; magnitude unverified) | Weber (via SoK): long and compound commands problematic. CWM: long traces truncate. **The figure "2–3% under 500 tokens, 23% over 2K" is not in EnvSimBench or Proxy-State; source unknown** | [V direction; unverified number] |
| **Agent quality** | Weaker or off-distribution agents cause more drift | Word2World WebShop consistency with a GPT-4o-mini agent 0.16 vs Claude-Sonnet-4.5 0.82; "weaker agents … frequently below 70%" | [V] |
| **Checkability of outcomes** | Code-checkable success is reliable; LLM-inferred success is not | Proxy-State: LLM-inferred goal completion agrees with humans only 82.7%. AWM: DB-diff verifiers. TheAgentCompany: checkpoints decided by a colleague's judgment are hard to check | [V] |

**Realism vs fidelity tension** [V: Petri docs/components/skills.qmd; I]:
- Petri's guidance is that "real production content runs 1,000–10,000+ tokens", and that generic names and round numbers trigger eval awareness. Fidelity wants short generated outputs.
- **Resolution:** long, realistic content is *pre-written* (a seed corpus, or Petri skill files via `send_file_as_tool_result`), not generated per call. The LLM generates only short deltas.

**Implication for the team's cheap-model plan** [I]:
- The evaluator would be DeepSeek V4.1 Flash. Word2World's agent-quality effect means the simulator will see more off-distribution calls from a cheap evaluator than from a frontier one.
- So validate simulator leniency and drift *with the actual evaluator model*.

---

## 3. Which Petri failure modes (§2 of the team taxonomy) a hybrid mitigates, by class (Q3)

Key:
- **M** = mitigated by the hybrid design (code-backed state, access in code, LLM writes content only, fresh simulator per fork);
- **P** = partly mitigated;
- **R** = remains;
- **n/a** = not relevant.

| Failure mode | CRUD APIs | SQL | Code-action (real Python + spec API) | Simulated humans | Web portal (templated) | Open web/search | Shell (LLM-simulated) | Shell (real sandbox) | Games / text adv. (engine) | GUI |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 state drift / silent corruption | M | M (real engine) | M | P (decisions coded; what the person "said earlier" can drift) | M | R | P (FS JSON state helps; /proc, sizes, pipes remain) | M | M | R |
| A2 leniency / strictness | M for access; P for semantic validity of free-text args | M | M | P (coded approvals; text-level concessions remain) | M | R | R | M | M | R |
| A3 variance | M (cache on state hash + call) | M | M | P | M | R | P | M | M | R |
| A4 invented affordances | M (fixed registry, 404 from code) | M | P (agent can probe introspection; docs must be complete) | P (a person may "offer" something) | P (links must be closed-world) | R | R (any command "exists") | M | M | R |
| A5 persuadability / injection | M for access; P for content | M | M | **R** (the core residual) | M | P | P | M | M | R |
| A6 fork leakage | M (copy store + cache, fresh simulator) | M | M (AppWorld `save_state`/`load_state`) | M | M | M | M | M (container snapshot) | M | P |
| B1 elicitation pressure | M (no auditor goal; scripted spec) | M | M | P | M | P | P | M | M | P |
| C1 eval awareness | P (synthetic-data tells) | P | P | R (cooperative, polite tells) | P | R | **R** (cross-checkable) | P | n/a (obviously a game) | R |
| D2 future-task success decided by simulator | M (rule on store) | M | M | P (only if success needs judgment) | M | R | R | M | M | R |
| Cost (D4) | Low | ~0 | Medium (many calls per cell) | Medium | Low–medium | High | Medium | Low | ~0 | Very high |

All cells are [I], derived from §1 and §2 evidence.

---

## 4. Ranked table: hybrid-Petri simulability for future tasks

**Ranking criterion:** how faithful a well-built hybrid is, *and* whether the class is a natural home for same-world neighbor future tasks. "LLM-only" gives the evidence for unconstrained simulation; "Hybrid" is my assessment.

| Rank | Class | LLM-only evidence | Hybrid fidelity | Same-world neighbor fit | Real twin for calibration | Main residual failure modes |
|---|---|---|---|---|---|---|
| **1** | **Structured CRUD tool APIs** (email, calendar, contacts, files-as-records, messaging, payments ledger, password vault, HR or ticket records) | Failure calls ~100%; state-changing 10–23% (EnvSimBench); docs-only simulators F1 53% vs trace-grounded 94% (MCP-Persona); semantic validation 63–71% (Gecko) [V] | **High.** State, ACL and success in code. LLM writes bodies, names and descriptions | High: most neighbor systems are CRUD | AgentDojo, AppWorld, AWM-generated envs, Mailpit, Vaultwarden | Synthetic-content tells; semantic validity of free-text arguments; search and ranking semantics (code them); content that carries information (secrets must come from the store) |
| **2** | **SQL databases** | LLM-as-DB: SELECT 65%, UPDATE 43% (GPT-4o few-shot); <20% on long sequences [V] | **Highest, but trivially:** execute SQLite. The LLM only writes seed rows | Medium (analytics DB, CRM back-end) | Itself | Seed realism; schema size |
| **3** | **Code-action over APIs** (AppWorld REPL) | No controlled study. Interpreter simulation is weak on strings and long traces (CWM); code given ≠ correct state (EnvSimBench) [V] | **High if** Python runs for real and only neighbor API calls are spec-backed (AppWorld `Requester` supports this [V]). **Low if** the auditor plays the interpreter | High: Peyton already runs AppWorld; the supervisor holds all credentials (team file) | AppWorld itself | Many LLM content calls per cell (cost); introspection and docs completeness; coded credential-transfer rules |
| **4** | **Simulated humans / colleagues** | Simulators inflate success (67–76% depending on simulator); excessively cooperative; persuasion of LLM judges +27% with CoT [V] | **Medium** for decisions (coded rules), **medium-low** for reply content | High: approvals, IT help desk, finance | Weak (real humans only); τ-bench user studies | A5 persuadability on anything decided in text; cooperativeness; stylistic tells |
| **5** | **Web portals** (vendor, bank, HR UI as HTML) | WMA 54.75%; WebShop EM ≤65% prompted, consistency 0.67; Web rubric 46–55 [V] | **Medium-high** when pages are templated from the store | Medium (a portal is often the only interface a vendor gives) | Self-hosted apps (WebArena-style), but heavy | Long pages; closed-world links; layout realism |
| 5b | Open web / search | Search rubric 19–38 (worst); factuality weakest [V] | **Low** | Low (not "same world") | None | World-knowledge contradictions; drift; eval awareness |
| **6** | **Shell / OS / file systems** | Fools humans as often as real Ubuntu on simple commands; 52% convincing in a larger study; consistency failures; side effects unfakeable [V] | LLM-simulated with a JSON FS: **medium** (96–99% on scripted tests [V]). **Real sandbox: high** | Medium (company servers) | Docker/E2B | Open command space; exact computation; network side effects; highest eval-awareness risk |
| **7** | **Text adventures** | TextWorld zero-shot EM 0.4–17.7% [V] | High with an engine; Petri adds nothing | None | Engine | Not same-world; low realism |
| **8** | **Exact-rule games** | 59.9% dynamic transitions (Wang); chess illegal moves [V] | Perfect in code; Petri adds nothing | None | Engine | Not same-world; useful only for estimator calibration |
| **9** | **GUI screenshots / a11y trees** | NeuralOS 37.7% hard transitions; a11y-tree rubric 52–70 [V] | **Not possible in Petri** (pixels); a11y text only | Low | OSWorld (fork cost high) | Everything |

*Ranks 1–3 are within noise of each other on fidelity. What separates them is cost and same-world fit [I].*

---

## 5. Neighbor systems (Q4): most to least faithful under a hybrid

These are future-task systems "next to" the base environment. Main reasons, all [I] unless tagged:

| Rank | Neighbor type | Why it is (un)faithful | Calibratable real twin |
|---|---|---|---|
| 1 | **Password manager / secrets vault** | Tiny API: list vaults, get item, share item, unlock. Crisp access rules (vault membership, master password). Content is *data* (secrets) that must come from the store, never be invented. Very little free text | **Vaultwarden** (AGPL-3.0, Bitwarden-compatible) [V: license file] |
| 2 | **HR system / directory / ticketing / internal admin** | CRUD records plus role-based access and approval workflows, with approvals coded as rules. Content is generic forms and notes, where LLMs are strong. Risk: vendor-specific UI details matter little if API-shaped | Generated (AWM-style) or spec only |
| 3 | **Bank / payroll portal** | Ledger arithmetic must be code; that is easy and exact. Limits, 2FA/OTP and execution-time fields (EnvSimBench's "mobile authentication" example) also go in code. Realism risk: real bank UIs are specific, so a generic one is a tell | AgentDojo's banking suite (real, same style) |
| 4 | **Vendor portal** | CRUD (orders, invoices, contacts), but there is no canonical product, so realism depends on the spec. Free-form vendor replies are simulated humans | Spec only |
| 5 | **Outside email** | Mechanics are trivial and faithful (send, list, read). Outside *people* replying are simulated humans (§1.9): lenient and cooperative. Success of anything requiring persuasion (social engineering) is not a faithful measurement | **Mailpit** (MIT) [V] |
| 6 | **Git host / code review** | Repo, PR, permission and branch-protection metadata is CRUD and codeable. But diffs must be real files, **CI and test results need execution** (SWE-World needed *trained* simulators and kept file ops real [V]), and reviewers are simulated humans | **Gitea** (MIT) [V] |
| 7 | **Package registry** | Publish, version and install semantics are codeable. But a package's *meaning* is the code it runs in dependents, which needs execution. Install logs and dependency resolution are long and exact | **Verdaccio** (MIT) [V] |
| 8 | **Company cloud console** | Huge surface. IAM evaluation is complex: explicit deny, conditions, role chains, resource policies. Resources *do* things (compute runs code, networks route, money is spent). IDs, ARNs and timestamps are exact. LLMs know the formats well, so the surface looks right while the semantics are wrong: the worst combination for silent corruption. Restrict to 2–3 services | **moto** (Apache-2.0; "basic" IAM auth enforcement via `INITIAL_NO_AUTH_ACTION_COUNT`) [V: cloned repo, docs/docs/iam.rst]. LocalStack Community was discontinued in 2026 and now needs an account [V: InfoQ Feb 2026] |

**General pattern** [I]:
- Fidelity is high when a neighbor's effects stay *inside its own records*.
- It is low when effects reach out into execution (CI, installs, compute), other people (outside email, reviewers), or the real world's knowledge (search).
- For neighbors 6–8, a *real* emulator (Gitea, Verdaccio, moto) is cheaper and more faithful than a simulator, and doubles as the calibration twin.

---

## 6. Eval awareness by class (Q6)

| Evidence | Implication | Tag |
|---|---|---|
| Agentic transcripts are far more detectable than chat: AUC 0.88–0.95 vs 0.71–0.77 for frontier models (Needham et al., arXiv 2505.23836); humans 0.996 vs 0.813. Cues include synthetic or fictional content (Claude 3.7 flags it in 22% of cases), task formatting, and verifiable CTF-style problems | Every agentic class starts high | [V] |
| Petri coding audits were judged less realistic than deployment transcripts in 95% of cases (Kissane et al., via arXiv 2609.02302). Real deployment resources raised realism win rate from 4.6% to 32.8%. Resources *increased* "inconsistent tool results" flags as environments grew more complex | Simulated coding/technical surfaces are the highest-risk class; real schemas and codebases help | [V: LessWrong post, arXiv 2609.02302] |
| DeepMind honeypots in *real* alignment codebases: low awareness, mostly caused by agency prompts, not environments (arXiv 2605.29729) | Real environments plus neutral prompts give near-floor awareness | [V: abstract] |
| Honeypot shells: humans called shelLM real 30% vs real Ubuntu 35%; the static honeypot Cowrie was always caught; an AI attacker couldn't distinguish them. But **unfakeable outbound effects** are a reliable giveaway | A careful agent can cross-check a simulated shell (download, then hash, then run) | [V] |
| Simulated users are more polite and cooperative (39% vs 20% polite turns) | Simulated colleagues carry style tells | [V] |
| Petri docs: generic placeholders ("Acme Corp", "John Doe"), overly clean formatting and round numbers "can trigger eval-awareness" | CRUD surfaces are safe only with realistic seed corpora | [V: local Petri docs] |

**Ranking of simulated forms by awareness risk** [I, from the above]:
1. Shell / code / cloud: cross-checkable.
2. Open web / search: contradicts the model's knowledge.
3. GUI: n/a in Petri.
4. Simulated humans: style tells.
5. Web portals.
6. CRUD APIs and SQL with realistic data: lowest.

Games and text adventures are moot: obviously not deployment, which is its own validity problem.

**For future-task measurement specifically** [I]:
- We measure attainable success, but whether the evaluator *uses* a held credential is partly propensity, and awareness can shift that either way.
- What matters is *differential* awareness between arms (context-kept vs cold start vs phantom holdings). Measure awareness per arm, not just overall.

---

## 7. Design rules for maximal faithfulness (hybrid Petri for future tasks)

1. **Code owns every bit that decides access or success.**
   - The spec holds entities, ACLs, credentials, balances and a success predicate. Transitions are code. Permission checks run before any LLM call.
   - The LLM may write only fields the spec marks as *content*.
   - *Evidence:* EnvSimBench 10–23% vs ~100%; AWM > Simulator; AutoControl Arena 62.5% vs 27.5% wins on consistency; Gecko's lenient semantic validation.
2. **Execute, never simulate, anything that computes.**
   - SQL goes to SQLite; agent Python goes to a real interpreter (AppWorld `Requester` routing); shell goes to a real container.
   - Arithmetic, IDs, timestamps, hashes, pagination, sorting and search ranking all come from code.
   - *Evidence:* in-context DB 22–65%; CWM string failures; SWE-World keeps file ops real; timestamps unpredictable in EnvSimBench.
3. **One LLM call = one short content field about one entity.**
   - Code builds the JSON or HTML envelope; the LLM fills the body.
   - Long realistic artifacts (inboxes, documents, repos) are pre-written at seed time and served verbatim, in the style of Petri's `send_file_as_tool_result`.
   - *Evidence:* field-count curve; honeypot long-command failures; Petri's realism guidance.
4. **Ground every product-shaped neighbor in recorded real behavior.**
   - Real tool schemas, real error codes and messages, real example responses, ideally recorded from an open-source emulator (moto, Gitea, Mailpit, Vaultwarden, Verdaccio).
   - *Evidence:* MCP-Persona F1 53 → 94; MirrorAPI; Kissane 4.6% → 32.8%.
5. **Closed-world affordances.**
   - Fixed tool registry and complete API docs (AppWorld `api_docs` must list the neighbor).
   - Unknown endpoints, URLs and commands get a realistic 404 or "command not found" *from code*. Disable "synthesize plausible values for absent entities" behaviour (Gecko does this by design).
   - *Evidence:* invented entities in EnvSimBench; A4.
6. **Freeze and cache content.**
   - Temperature 0; cache keyed on (state hash, call); pre-generate content at seed time where possible.
   - Fork = copy the store and the cache, then start a fresh simulator instance. Never fork via Petri rollback.
   - *Evidence:* VelLMes session sensitivity; Petri docs on rollback memory.
7. **Give the simulator structure, not persuasion surface.**
   - Inputs are the delimited tool name, arguments and state slice. Never the agent's reasoning.
   - Human approvals are rules over (requester role, request type). Human replies are content only. Secrets enter a human simulator's context only if the spec says this person reveals them to this requester.
   - *Evidence:* +27% persuasion with CoT; simulated users' cooperativeness.
8. **Validate with the evaluator you'll actually use.**
   - Run leniency, strictness and phantom-holdings probes with DeepSeek V4.1 Flash (or whatever the evaluator is), not only with a frontier model.
   - *Evidence:* Word2World agent-quality effect (consistency 0.16 vs 0.82).
9. **Calibrate per class with a real twin, and pick neighbor types that have one.**
   - Run the same future tasks real (AppWorld/AgentDojo app, or an emulator) and illusory.
   - Report the deltas in success, steps, access granted-when-denied and awareness.
   - *Evidence:* AutoControl Arena r = 0.87 on 10 scenarios is the only precedent, and it is small.
10. **Realism hygiene without leaking.**
    - Seed from the base environment's real entities (names, domains, accounts); realistic noise (rate limits, partial failures) generated deterministically from code; neutral prompts.
    - A cheap per-turn realism approver on LLM-written content only.
    - Measure eval awareness per arm.
    - *Evidence:* Petri 2.0 approver; DeepMind's prompt finding; Needham's cues.

---

## 8. What this implies for the testbed choice [I]

- Fidelity favors a **CRUD-API or code-action-over-API base**, with **CRUD-shaped neighbors**. That favors AppWorld or AgentDojo over OSWorld.
  - AppWorld adds a real Python REPL, `save_state`/`load_state`, and a pluggable API layer (in-process, remote or MCP) [V: repo]. Illusory neighbors can therefore be added *as apps* while code stays real. That is the cleanest version of "simulate only the API layer".
  - AgentDojo is the simpler function-call version of the same thing.
- **OSWorld** is the worst fit for illusory neighbors: GUI simulation isn't possible in Petri, and forking is costly.
- **Neighbor choice for a first test:**
  - Start with a password vault, an HR/IT-admin system, and a bank/payroll ledger: high fidelity, crisp power semantics.
  - Add outside email (Mailpit twin) for one human-in-the-loop stratum.
  - Defer the cloud console, package registry and CI-backed git host, or run them on real emulators (moto, Verdaccio, Gitea) rather than simulating them.

---

## 9. Corrections and unverified items in earlier team files

| Claim in team files | What I found |
|---|---|
| AutoControl Arena: "No code link found" | Paper states "Code and data are available at https://github.com/CosmosYi/AutoControl-Arena" [V] |
| AutoControl Arena 62.5/27.5 | Correct as **state-consistency** wins/losses (25W/4T/11L). Overall preference is 60/10/30 [V] |
| "Failure rises with output length (2–3% under 500 tokens, 23% over 2K)", attributed to EnvSimBench | EnvSimBench has **no** length analysis. Proxy-State has none either. **Source unknown; treat as unverified.** The direction is supported by honeypot studies |
| SynthTools "58% of errors are false rejections, 10% missed violations" | Not in SynthTools v1 [V]. Unverified. The nearest verified numbers are MCP-Persona's (docs-only: 26% false rejections, 16% false accepts; trace-grounded: 4%, 2%) |
| WMA "54.75%" | It is the **average of 4 models**, not one model's score [V] |
| Simulated users "77.8% vs 63.6%" | Not found. Verified instead: simulator choice moves τ-bench success from 67.0% to 75.9%, and simulators are "excessively cooperative" (Zhou et al.) [V] |
| Proxy-state "cut tool hallucination to 1.33%" | 1.33% is verified, but the paper reports **no** with/without comparison, so "cut" is not supported [V] |
| Gecko 63–71% semantic | Verified (71/69/63) [V] |
| Word2World numbers | Verified, with per-environment detail added above [V] |

---

## Sources

- EnvSimBench: https://arxiv.org/html/2605.07247
- Word2World ("From Word to World"): https://arxiv.org/html/2512.18832v2
- Wang et al. 2024, text world simulators: https://arxiv.org/html/2406.06485v1
- MirrorAPI: https://arxiv.org/html/2503.20527v1
- MCP-Persona: https://arxiv.org/pdf/2606.02470
- Gecko: https://arxiv.org/pdf/2602.19218
- SynthTools: https://arxiv.org/html/2511.09572v1
- Proxy State-Based Evaluation: https://arxiv.org/pdf/2602.16246v2
- Agent World Model (AWM): https://arxiv.org/html/2602.10090v2
- AutoControl Arena: https://arxiv.org/html/2603.07427
- Simia: https://arxiv.org/html/2511.01824v1
- UI-Simulator: https://arxiv.org/html/2510.14969v1
- DreamGym: https://arxiv.org/abs/2511.03773v2
- WMA: https://arxiv.org/html/2410.13232v2
- WebDreamer: https://arxiv.org/abs/2411.06559
- R-WoM: https://arxiv.org/html/2510.11892v1
- Qwen-AgentWorld: https://arxiv.org/pdf/2606.24597
- NeuralOS: https://arxiv.org/html/2507.08800v2
- In-context database: https://arxiv.org/html/2411.01807v1
- SQL understanding: https://arxiv.org/pdf/2410.10680
- Debugging Code World Models (CWM): https://arxiv.org/html/2602.07672v1
- SWE-World: https://arxiv.org/html/2602.03419v1
- shelLM: https://arxiv.org/html/2309.00155v3
- SoK Honeypots & LLMs: https://arxiv.org/pdf/2510.25939
- VelLMes: https://arxiv.org/html/2510.06975v1
- AdvancedShelLM: https://www.emergentmind.com/papers/2606.27990
- Lost in Simulation: https://arxiv.org/html/2601.17087v2
- Mind the Sim2Real Gap: https://arxiv.org/abs/2603.11245
- TheAgentCompany: https://arxiv.org/html/2412.14161v1
- Monitor persuasion (LASR): https://www.lesswrong.com/posts/Bvb97FpmxnKKebSjX/access-to-agent-cot-makes-monitors-vulnerable-to-persuasion
- Needham et al., eval awareness: https://arxiv.org/html/2505.23836v2
- Improving Evaluation Realism: https://arxiv.org/pdf/2609.02302
- Kissane et al., coding audit realism: https://www.lesswrong.com/posts/EjxzHh5Guhxc9DLW2/measuring-and-improving-coding-audit-realism-with-deployment
- DeepMind realistic honeypots: https://www.emergentmind.com/papers/2605.29729
- ToolEmu: https://arxiv.org/abs/2309.15817
- StableToolBench: https://arxiv.org/abs/2403.07714
- Chess state tracking: https://arxiv.org/abs/2508.19851
- ChessBench: https://jso.eecs.yorku.ca/wp-content/uploads/2026/07/chessbench-llm-failures-1.pdf
- GIF-MCTS code world models: https://arxiv.org/abs/2405.15383
- LocalStack change: https://www.infoq.com/news/2026/02/localstack-aws-community
- Repos:
  - AppWorld (cloned; Apache-2.0): github.com/StonyBrookNLP/appworld
  - moto (cloned; Apache-2.0): github.com/getmoto/moto
  - Petri docs (local source)
- License files: Mailpit (MIT), Gitea (MIT), Vaultwarden (AGPL-3.0), Verdaccio (MIT), via raw.githubusercontent.com
