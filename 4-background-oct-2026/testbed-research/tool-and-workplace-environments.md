> **Status (2026-11-01):** Parked. Survey for the Petri test; its facts about AppWorld and AgentDojo are still useful. Start at [README.md](../../README.md); decisions are in [decisions-log.md](../../1-handoff/decisions-log.md).

# Tool-API, workplace and app-world environments as the first testbed for "Petri for future tasks"

*Prepared 2026-10-30 for the envsearch brief (`envsearch/common.md`). Scope: AgentDojo (all 4 suites), AppWorld, NeMo Gym workplace assistant, ClawBench/ClawsBench/smolclaw, Agent-Diff, ToolEmu, Agent-SafetyBench, WebShop, Vending-Bench, ComplexMCP, SafeMCP, AWM, ClawEnvKit, AutoControl Arena, PropensityBench, AuthorizationBench, τ/τ²-bench, and Peyton's shared-FS / Chinook / git idea.*

**Legend.**
- **[V: source]** = verified against the named file, README or paper page.
- **[I]** = inferred, not checked.
- **[U]** = unknown.

"Criteria 1–7" are the ones in `common.md`.

**Where the clones are.** Everything sits under `/tmp/claude-0/-home-claude/50a22e9f-8806-5a1b-b693-ebea87343d8e/scratchpad/envsearch/toolenvs/<name>/src`. The names are:
- appworld, nemogym, smolclaw, clawsbench, agentdiff, tau2;
- authbench, awm, toolemu, agentsafetybench, vendingbench;
- complexmcp, autocontrol, clawenvkit, propensity, webshop, safemcp, chinook.

**How they were handled.**
- Nothing was run or installed.
- AppWorld's encrypted `.bundle` files (app implementations, tasks, tests) were **not** decrypted. Everything below about AppWorld comes from the plain-text public portion (`src/appworld/*.py`, `apps/lib/*`, `collections/apis.pyi`, guides, prompts), the README, the paper page and the leaderboard JSON.
- My own two analysis scripts are in `.../toolenvs/scripts/`. I ran them with `python3 -I` over the AgentDojo source.

---

## 0. Bottom line

1. **Verdict.**
   - **Start the Petri-for-future-tasks test on AgentDojo**, built as one merged "Emma Johnson" world: Workspace as the main system, with Banking, Travel and Slack held out as neighbor systems.
   - **Make AppWorld the second testbed.** Run it in its held-out-apps design, in function-calling mode.
   - **Why AgentDojo first.** It is where hybrid Petri is most likely to be faithful:
     - the whole state is about 79 KB of YAML, so it fits in the auditor's context;
     - tasks take 2–6 calls;
     - the tool schemas are already Inspect tools.
   - Under those conditions a real-vs-illusory calibration is cheap and complete.
   - **What AppWorld has that AgentDojo lacks.** It natively has the cross-system power structure we want:
     - email and phone are the verification and reset channel for every app;
     - payment cards work across apps;
     - money moves through Venmo;
     - anyone can sign up for new accounts.
   - **What AppWorld costs.**
     - It hands the agent every password on step 0.
     - Its Python-REPL action space and ~370K-row database are the hardest things on this list for an LLM simulator to fake.
     - Its native tasks cannot be reused as future tasks on another task's fork.
   - **When to flip the order.** If the team values native, unbuilt power routes over simulator faithfulness, put AppWorld first. Section 2.7 gives the argument.
2. **Top 3:**
   1. AgentDojo, merged Emma world.
   2. AppWorld with held-out apps.
   3. Agent-Diff, as real-API-shaped neighbor systems with a verified mid-run fork.

   Alternates for #3: smolclaw (the best Gmail persistence routes, but no tasks) and AuthorizationBench (the best sanctioned/unsanctioned labels, but every task is its own world).
3. **New facts that change earlier team docs:**
   - **AgentDojo's suites already share one principal.** Workspace, Travel and Banking all use "Emma Johnson". Workspace and Travel share her email. The default system prompt frames every suite as Emma at Blue Sparrow Tech [V: `data/suites/*/environment.yaml`, `data/system_messages.yaml`].
     - So AgentDojo can be one principal's world with 3–4 neighbor systems.
     - But the data disagree: two addresses and two bank-account formats.
     - Nothing is gated, so no power carries across suites until we add authentication.
   - **AppWorld's supervisor app returns every password at step 0.**
     - `supervisor.show_account_passwords` returns the supervisor's password for every app [V: `collections/apis.pyi`].
     - The standard agent prompt says "You have full access -- complete permission to operate across my connected accounts and services" [V: `experiments/prompts/full_code_agent/full_code_instructions.txt`].
     - So little native *excess* power is available. Withholding the passwords for held-out apps is a data-only edit that turns AppWorld's native reset and signup features into routes the agent has to acquire.
   - **AppWorld native tasks are not portable across forks.** Each task has its own supervisor, a setup program and private data. Setup code is released only for train and dev [V: README; `ground_truth.py`]. Future tasks for a given main-task supervisor must be written by us.
   - **NeMo Gym's workplace assistant is a port of WorkBench.** It has 5 pandas tables, 27 tools and 690 tasks. Its checker replays the function-call list and compares the resulting state [V: `resources_servers/workplace_assistant/{README.md,app.py,utils.py}`]. It has no accounts, credentials, money or permissions.
   - **ClawsBench and smolclaw.**
     - ClawsBench tasks are still unreleased ("Tasks will be added soon"), and the repo is CC BY-NC-SA [V: ClawsBench README].
     - smolclaw (MIT) is the mock infrastructure, with one registered task in the whole repo [V: `grep register_task(`].
   - **AutoControl Arena's code is now public** at github.com/CosmosYi/AutoControl-Arena, Apache-2.0 [V: LICENSE]. The earlier docs said "no code found".
   - **SafeMCP is a defense method, not a testbed.** Its PowerSeeking Bench is LLM-judged [V: paper page].
   - **Agent-Diff can fork mid-run.** `create_template_from_environment` clones a live environment's Postgres schema into a new template [V: `backend/src/platform/isolationEngine/core.py`]. The earlier doc said "no documented mid-run fork".

---

## 1. What "good" means here (operationalized from the brief)

A first testbed for "Petri for future tasks" needs four things:

- **(a)** A real main environment, where the agent can acquire power it doesn't need.
- **(b)** Same-world neighbor systems where that power pays off (criteria 1, 5, 6).
- **(c)** Neighbor systems a hybrid Petri can stage faithfully (criterion 2).
- **(d)** The *same* neighbor tasks runnable for real, so simulator distortion can be measured (criterion 4).

Plus the practicalities of criterion 7.

The design question I was asked to test: **"Hold some systems out of the main task and use them as neighbor systems for future tasks, run both really and through Petri."**

---

## 2. Head-to-head: AppWorld vs AgentDojo

### 2.1 Facts side by side

| | **AppWorld** | **AgentDojo (v1.2.x)** |
|---|---|---|
| **World** | One simulated world of ~100 people, each with accounts across 9 apps. A task names one "supervisor" [V: README; paper] | 4 suites, each a small pydantic world. Workspace, Travel and Banking all use the persona Emma Johnson; Slack has Alice, Bob, Charlie and Eve [V: suite YAML] |
| **Apps and APIs** | 9 apps. The paper says 457 APIs; the current stubs list 463 across the 9 apps, plus Supervisor (6), ApiDocs (4) and an internal Admin app (5) [V: paper page; `collections/apis.pyi`]. 101 tables, 726 columns, ~370K rows [V: paper page] | Tools: Workspace 24, Slack 11, Travel 28, Banking 11 [V: `default_suites/v1/*/task_suite.py`] |
| **Tasks** | 750 = 250 scenarios × 3. Train 105, dev 60, test-normal 168, test-challenge 417 [V: paper page] | 97 user tasks. Workspace 40 (33 plus 7 combined), Slack 21 (17 plus 4), Travel 20, Banking 16 [V: `user_tasks.py`] |
| **Size of a task** | Overall: apps 1.8 on average (max 6), unique APIs 9.5. Test-normal: 1.5 apps, 42.5 API calls on average. Test-challenge: 2.0 apps, 46.8 calls [V: paper page]. Frontier agents use 16–35 interactions [V: leaderboard.json] | Ground-truth calls per task, from a static count: Workspace 1.8, Slack 4.1, Travel 6.2, Banking 2.1 [V: my AST count] |
| **Action space** | Python REPL (IPython): the agent writes code that calls `apis.<app>.<api>(...)`, with loops and pagination. Function-calling and MCP modes also exist [V: README; `environment.py`] | OpenAI-style function calls [V]. Also ported to Inspect as `inspect_evals/agentdojo`, which adds a `workspace_plus` suite with a terminal [V: `ext/ie/src/inspect_evals/agentdojo`] |
| **State** | One in-memory SQLite database per app. Changes are tracked and saved as JSONL diffs against the base database [V: `apps/lib/models/db.py`; `environment.py`] | pydantic models built from YAML. All four suites total ~79 KB: Banking 2.3 KB, Slack 3.9 KB, Travel 21 KB, Workspace ~52 KB [V: `wc -c`] |
| **Fork** | `world.save_state(id)` / `world.load_state(id)` write and reload database diffs [V: `environment.py` L1335–1356]. `load_state` calls `AppWorld.close_all()`, and a server process "must hold only one world at a time", so parallel forks need separate processes [V: `guides/parallelizing_worlds.md`]. REPL variables (tokens kept in Python variables) are not saved [I: `_save_state` saves databases only]. Time is frozen at the task's datetime [V: `set_local_date_and_time`] | `env.model_copy(deep=True)` [V: `task_suite.py` L374] |
| **Checker** | State-based unit tests over the start vs end databases, about 8 assertions per task. They include collateral-damage checks such as `models.changed_model_names() == {...}`, and answer checks for question tasks [V: README; paper page]. Evaluation programs are released for all splits; setup and solution only for train and dev [V: README] | `utility(model_output, pre_env, post_env)`. My heuristic scan of v1: Workspace 15/33 answer-string checks (read-only tasks also assert pre == post), 16/33 state checks; Slack 16/17 state; Travel 14/20 answer-only plus 6 answer-and-state; Banking 12/16 state [V: my AST scan] |
| **Licence** | Apache-2.0. The "protected portion" (app code, API docs, tasks, tests) must be redistributed *only in encrypted form*; training models and serving their outputs are not counted as redistribution [V: README §License] | MIT [V: LICENSE] |
| **Capability needed** | Hard. Test-normal / test-challenge TGC: GPT-4o ReAct 48.8/30.2; GPT-4o function-calling 32.1/18.0; Llama-3-70B ReAct 20.8/3.4; Qwen3-14B after RL 86.9/67.6; GPT-4.1-mini (multi-agent) 61.9/37.6; Claude Opus 4.6 91.1/72.4 [V: leaderboard.json]. DeepSeek V4.1 Flash: [U] | Easy. No-attack utility out of 97: gpt-4o-mini 66, Llama-3.3-70B 56, Claude 3.7 Sonnet 86, gemini-2.0-flash 42 [V: bundled `runs/*/none.json`, my count] |
| **Cost** | [I] about $0.02–0.2 per main task with a flash model, because contexts are long and runs take 20–40 turns. Peyton's measured probe cost is $0.004–0.006 [V: project doc `petri-for-future-tasks-analysis.md` §5] | [I] under $0.01 per task with a flash model |
| **Team code** | Peyton already runs it (dose-response experiments) [V: project docs] | A full plan exists (`plan-environment-and-power-meter.md`). Built code: [U] |
| **Recognizability** | A well-known benchmark, with canary strings in the code | A well-known injection benchmark. The plan already budgets renaming |

### 2.2 AppWorld: what the code and paper say

**Apps and API counts** (current stubs, `collections/apis.pyi`) [V]:

| App | APIs | | App | APIs |
|---|---|---|---|---|
| spotify | 92 | | gmail | 48 |
| amazon | 75 | | phone | 30 |
| splitwise | 65 | | file_system | 26 |
| todoist | 56 | | simple_note | 17 |
| venmo | 54 | | | |

Helper apps: supervisor (6) and api_docs (4). There is also an internal admin app with 5 card APIs: `show_card_balance`, `validate_card`, `debit_from_card`, `credit_to_card`, `add_payment_card`.

**The supervisor app** [V: `apis.pyi`; README]. Its APIs are:
- `show_profile`;
- `show_addresses`;
- `show_payment_cards`;
- `show_account_passwords`;
- `show_active_task`;
- `complete_task(answer, status)`.

How the data is stored:
- **Passwords:** stored in an `AccountPassword` table in the admin app's database, one row per app [V: `collections/apis.py` imports `appworld.apps.admin.models.AccountPassword`; `tests/package/test_appworld.py` L516–518].
- **Payment cards:** the field list is in the encrypted code [U]. Every app's `add_payment_card` takes `card_number, expiry_year, expiry_month, cvv_number` [V: `apis.pyi`], so the supervisor's card records must expose at least those [I].

**Login and access tokens** [V: `apps/lib/apis/authentication.py`]:
- **How login works:**
  - Per-app OAuth2 password form.
  - The username is the email or the phone number, depending on the app (`login_by`).
  - Passwords are stored and compared in plaintext.
- **What a token is:**
  - A JWT signed with the constant secret `"SECRET"`.
  - `sub` = `"<app>+<username>"`, and a token is rejected by any other app, so tokens are app-scoped.
  - It expires after a random 10–30 minutes.
- **Logout:** puts the token on an in-memory blacklist, which is not saved with state [I].
- **Signup:** creates an account. Verification codes go to the given address's **Gmail** account or **Phone** number inside AppWorld.
- **Password reset:** `send_password_reset_code` sends the code to the account's Gmail or Phone, then `reset_password` sets the new password.
- **Ownership:** resources are checked against the logged-in user (`check_authorization_to_resource`).
- **What this adds up to:** Gmail and Phone are the master keys to every other app in the world. That is real cross-system structure, not something we would have to build.

**The Python REPL** [V: README; `common/safety_guard.py`]:
- It is a stateful IPython shell, so variables persist across `execute` calls.
- APIs are called in functional form (`apis.app.api(...)`) or REST form (`requester.post(...)`).
- Requests are limited to 2,000 per execution.
- An AST check plus monkey-patching blocks `open`, `os.system`, `subprocess` and the like.
- **But the import allow-list includes `appworld`, `inspect`, `os`, `hmac`, `base64` and `hashlib`.** With the constant JWT secret, agent code could in principle reach the app internals directly or forge a token for any user [I, untested].
- Treat this as a hazard for a power meter: run the APIs remotely or in Docker, which is supported [V: README "Serving … with/out Docker"].
- Or treat it as a deliberate "exploit power" condition, which is Travis's hypothesis.

**People are static** [I]. The paper describes ~100 people whose activity is pre-generated, related as family, friends and coworkers [V: paper page]. Nothing in the public code simulates them replying. A payment request, a project invite or a group invitation sent to them will never be accepted. "Allies" therefore exist only as stored state, never as responses.

**Concrete routes to power the task doesn't need:**

| # | Route | Steps | Native? |
|---|---|---|---|
| 1 | Read every stored password | `supervisor.show_account_passwords` (1 call) | Native, and granted to the agent from step 0. This is why native *excess* power is small |
| 2 | Log into apps the task doesn't need | login per app → app-scoped JWT | Native. Holding a token saves about 2 calls later |
| 3 | Use cards everywhere | `supervisor.show_payment_cards` → `add_payment_card` in amazon, spotify or venmo; balances are tracked centrally in admin | Native [V: API names; I: central-balance semantics] |
| 4 | Move money | venmo `add_to_venmo_balance` (card to Venmo), `create_transaction`, `create_payment_request`, `approve_payment_request`, `withdraw_from_venmo_balance`; splitwise `record_payment` and `settle_up`; amazon `place_order`; spotify and amazon subscriptions | Native [V] |
| 5 | Create agent-controlled identities | Gmail and Phone list `signup` with no verify API; the other apps send verification codes to Gmail or Phone. So: create a new Gmail account → sign up for Venmo → read the code → verify → send the supervisor's money to the new account | Native [V: API list and auth code; I: that Gmail signup needs no verification]. This is a genuine multi-step resource-and-persistence route the agent controls |
| 6 | Take over or lock out accounts | `send_password_reset_code` → read the supervisor's Gmail or Phone → `reset_password`. The admin `AccountPassword` row probably goes stale, locking the principal out of their own record [I] | Native |
| 7 | Contacts and allies | phone `add_contact` (with relationships); venmo `add_friend`; splitwise `create_group`, `add_member_to_group`, `regenerate_invitation_code`; todoist `send_project_invite` | Native. State only, because no one replies [I] |
| 8 | Persistence | file_system `create_file`, simple_note `create_note`, todoist tasks, Gmail drafts, recurring subscriptions. **No Gmail filters, forwarding rules or delegates**: only one-off `forward_email_*` [V: API list] | Native but weak: stored data only, no automation |
| 9 | Information | Every email, text, note, file and transaction of the supervisor; other people's profiles and Venmo social feed (`search_users`, `show_social_feed`) | Native |
| 10 | Escape the sandbox | `import appworld` / `inspect` / `hmac` (see the REPL paragraph above) | Native hazard [I] |

**How evaluation interacts with power-seeking.**
- The checks are closed-world: collateral-damage assertions fail the task on unexpected model changes.
- So a power write in another app, such as adding a card to Venmo during a Spotify task, would fail the main task [I: from the README's `changed_model_names` example].
- The fix, as in the project docs: wrap or filter `changed_model_names` so it ignores tables we treat as power tables. The evaluation code is plain Python and released for every split [V], so this is feasible [I].

### 2.3 Design check: "hold some apps out" in AppWorld

**Build:**
1. **Choose main tasks.** Pick tasks whose required apps (e.g. Spotify plus Phone) leave a block **H** untouched, e.g. {Venmo, Splitwise, Amazon}. With 1.5–2 apps per task there are always 6–8 candidates [V: paper stats].
2. **Withhold access to H.** Delete the `AccountPassword` rows for H from the task's admin database when the task loads [I: feasible, since it's a data edit and `show_account_passwords` reads that table]. Optionally plant a trail, such as a SimpleNote note holding the Venmo password, or rely on the native reset-through-Gmail route.
   - This also fixes AppWorld's biggest weakness for us: without it the agent already holds everything.
   - It is still a *removal* plus native product features. No new code, which fits R6 ("routes built from ordinary product features").
3. **Write the future tasks.** These are about 15–25 tasks in H for *that* supervisor, each checked on end-state:
   - "pay Alex back $40 on Venmo";
   - "split last Friday's dinner on Splitwise";
   - "order the cheapest USB-C charger to my home address".

   Write each checker with AppWorld's test DSL over a fork's start and end databases.
   - Native tasks can't be reused: each has its own supervisor, setup and private data, and their setup code is unreleased for test.
   - Whether enough native tasks share a supervisor is [U]. It needs the data bundle, which I didn't download.
4. **The real arm.** `save_state` at the interrupt, then `load_state` in a fresh process and run the evaluator.
5. **The illusory arm.** Petri in `"fixed"` mode [V: `inspect_petri/_auditor/tools.py`]:
   - register H's real tool schemas (AppWorld ships function-calling API docs) [V: README];
   - give the auditor a dump of the supervisor's slice of H's databases;
   - decide access in code: login succeeds iff the password matches the stored one; reset codes land in Gmail.
6. **Calibration.** Run the same H tasks both ways. Compare success, γ-discounted steps, and grants the simulator made that the real app refused.

**Strengths:**
- **The carry-over is real and native.**
  - Gmail/Phone control unlocks every app.
  - Cards work everywhere.
  - Venmo money can be withdrawn to a card and spent on Amazon.

  This is world-bound power reaching other systems of the same principal, which is exactly criteria 1 and 6.
- **The neighbors are real code, with state checks,** so calibration has ground truth (criterion 4).
- **Nothing about the neighbors has to be invented,** which reduces red-team finding 1 (the meter reading back routes we built).

**Problems:**
1. **Hardest simulation target on the list (criterion 2).**
   - The native action space is a code cell that makes many API calls, with loops and pagination.
   - The illusory arm would have to emulate Python *and* the apps.
   - Fix: run **both** arms in function-calling or MCP mode. That costs success: GPT-4o drops from 48.8 to 32.1 test-normal TGC under function calling [V: leaderboard].
2. **The state doesn't fit in the auditor's context.**
   - The database is ~370K rows. A single person's Venmo or Amazon slice may still be hundreds of rows [I].
   - So the auditor sees only part of the state, which invites invented entities (failure A4 in the project's taxonomy).
   - Tasks average 40+ API calls, the range where EnvSimBench reports 10–23% state match for state-changing calls (project prior-work file).
   - Expect large measured distortion. That is useful as a stress test but bad for a *first* test.
3. **Future tasks must be written** (above).
4. **Main-task checks are closed-world** and must be filtered (above).
5. **Forks are heavier.** One world per process, and REPL variables have to be rebuilt by replaying the agent's context.
6. **Licence.** Petri transcripts contain API docs and data from the protected portion. Publishing them in plain text conflicts with the licence's "encrypted redistribution" clause [V: README]. Keep transcripts private, or ask the authors (the README invites this).
7. **Cost.** Each illusory future task is about 20–40 auditor calls [I].

**Verdict on the design.** It is the best *native* realization of "same-world neighbors with real carry-over" on this list, and the right *second* experiment. Run in function-calling mode, it doubles as the simulator stress test. It is a poor first experiment, because the simulator is most likely to fail exactly there, and a failure there wouldn't say whether hybrid Petri works at all.

### 2.4 AgentDojo: what the code says

- **Suites and tools.** Workspace (mail, calendar, drive; 24 tools), Slack (11), Travel (28), Banking (11) [V].
- **Fork and checkers.** Forks are a deep copy. Checkers are `utility(output, pre, post)`, and every user task in a suite runs against *any* state of that suite [V: `base_tasks.py`]. So native tasks are ready-made future tasks on forked states.
- **Bait already in the data** [V: YAML]:
  - **Workspace:** password-reset emails (TechServices) and security-code emails in the inbox; files with owners and share lists; contacts.
  - **Slack:** "Secret key is 1a7b3d." posted in a channel. The agent can read any user's inbox, add anyone to any channel, invite or remove users, and `post_webpage` (an exfiltration or persistence surface).
  - **Banking:** `send_money`, `schedule_transaction` with `recurring` (persistence), `update_password`, and a stored password ("password123").
  - **Travel:** the user record holds the passport number, credit-card number and bank-account number (information power).
- **Same principal across suites** [V]:
  - Travel and Banking both use Emma Johnson. Travel and Workspace share `emma.johnson@bluesparrowtech.com`.
  - The default system message says the user is Emma Johnson of Blue Sparrow Tech, for every suite.
  - **But** the details disagree: "123 Main Street, Anytown" vs "Apple Street 1, Cupertino"; bank account "0789765432" vs IBAN "DE89…". Reconciling them is a YAML edit.
- **No authentication or permission model at all.** Every tool works from step 0. Nothing is gated, so nothing can carry across suites. This is the plan's "power layer" problem.

### 2.5 Design check: "hold some suites out" in AgentDojo

**Build:**
1. **Merge into one Emma world.** Combine Workspace, Banking, Travel and Slack into one combined environment class, a mechanical change. Reconcile Emma's identity fields and make Slack the Blue Sparrow Tech workspace with Emma as a member.
2. **Gate the neighbors, using credentials that live in Workspace:**
   - Banking needs `bank_login(user, password)`, with the password in a drive file or a reset email.
   - Slack needs a workspace token or an admin invite found in mail.
   - Travel bookings need the card on file or a loyalty login.

   This is the plan's power layer, extended across suites. It is built by us, so the future-task catalog must be written blind to it (red-team finding 1).
3. **Main task in Workspace.** Future tasks are the native Banking (16), Travel (20) and Slack (21) tasks, plus a few written ones.
4. **Real arm:** a deep copy and a native `utility`.
5. **Illusory arm:**
   - Petri `"fixed"` mode with the *real* AgentDojo tool schemas, which are already Inspect tools in `inspect_evals`.
   - The auditor gets the neighbor suite's *entire* serialized state (2–21 KB).
   - Access is decided in code; the LLM writes only content.
6. **Calibration:** every neighbor task exists both ways, so the calibration slice can be the whole neighbor set.

**Strengths:**
- **The best conditions for Petri faithfulness on this list** (criterion 2):
  - small, fully visible state;
  - short outputs, except Workspace file listings;
  - 2–6 calls;
  - real schemas.
- **Native future tasks** (criterion 7).
- **Cheap models succeed** (gpt-4o-mini 66/97), and cost is tiny.
- **The same Inspect stack as Petri.**

**Problems:**
1. **The gates are ours.** Every cross-suite route is code we write. That is the red-team's circularity risk, and "nothing makes the agent gain power" (finding 3) remains.
2. **Small worlds.** Slack has 4 users; Banking has one account and no counterparties. Breadth is limited (criterion 1).
3. **Travel tasks mostly check answer strings** (14/20). By Turner post 9 they act as controls, not power probes.
4. **Recognizable.** Rename everything (already in the plan).
5. **Persistence is thin natively.** There are no mail rules, so they have to be added.

**Verdict on the design.** It is the right first experiment for *validating hybrid Petri on neighbor systems*. If the simulator fails here, it will fail on AppWorld too. If it passes here, AppWorld in function-calling mode is the harder second test.

### 2.6 Scorecard (1 = poor, 5 = strong; my judgment from the facts above)

| Criterion | AppWorld (held-out apps) | AgentDojo (merged Emma) |
|---|---|---|
| 1. Breadth / power that generalizes | **4.** Real cross-app carry-over (email/phone reset, cards, money), 9 apps | **2.** Carry-over exists only once we gate it; small worlds |
| 2. Petri suitability | **2.** REPL (or 457 function tools), big state, long trajectories | **5.** Tiny state, short calls, real schemas |
| 4. Real ground truth for calibration | **4.** Neighbors are real apps; future tasks need writing | **5.** Neighbors and their native tasks are real |
| 5. Real power opportunities | **3** native, but already granted at step 0. **4** after withholding passwords | **2** native (bait, no gating). **4** after the power layer |
| 6. Same-world neighbors | **5.** One supervisor, ~100 people, shared cards and email | **3.** Same persona, inconsistent data, Slack is another org |
| 7. Practicality (fork, state checks, cost, cheap models, licence, code) | **3.** Fork per process; closed-world checks; costly; hard for small models; encrypted-redistribution clause; Peyton's code exists | **5.** Deep-copy fork, cheap, MIT, plan exists |

### 2.7 Verdict on AppWorld vs AgentDojo

**For the *first* test of Petri for future tasks: AgentDojo.** The first experiment has to answer one question: "does hybrid Petri reproduce real future-task power readings on a neighbor system?" AgentDojo answers it under the most favorable conditions, at the lowest cost, with complete ground truth. It also matches what the team has already planned.

**AppWorld is the better *power world*.** Its routes are native product features: reset through Gmail, new accounts, cards, money. Its neighbors are real and rich, and the held-out-apps design needs only a data edit to make power acquirable. It should be the second testbed. It is also the place to test whether the Petri numbers survive a hard simulator, in function-calling mode for both arms.

**When to flip the order.** If Matthew wants to measure existing trajectories now (Peyton's), or the team decides that power routes it builds itself are unacceptable (red-team finding 1), put AppWorld first. Expect to spend the first weeks on future-task authoring and function-calling plumbing rather than on Petri.

---

## 3. The other candidates

Each block gives the facts, the power opportunities, neighbors, Petri suitability, calibration, and a verdict.

### 3.1 NVIDIA NeMo Gym, workplace assistant (from Peyton's proposal)

- **Facts** [V: `resources_servers/workplace_assistant/README.md`, `app.py`, `utils.py`, `data/validation_metrics.json`]:
  - It is WorkBench, ported into NeMo Gym.
  - 5 toolkits plus a company directory: email (500 rows), calendar (300), analytics (1,000), CRM (200), project tasks (300).
  - 27 tools. 690 tasks; the full HF prompt set has 1,260, with 545 for validation.
  - Function-calling action space.
  - **The checker (`is_correct`) replays the predicted function-call list and the ground-truth list on fresh environments and compares the full end tables.** That is closed-world, and it scores the call list, not the live session.
  - State is pandas DataFrames with export/restore (`checkpoint_mode="exported"`), so forking is supported.
  - Apache-2.0 for code and data.
- **Power opportunities: none.** There are no users, roles, credentials or money. Any extra write fails the task.
- **Neighbors:** one generic company with 5 systems. That is plausible as a world, but nothing is gated.
- **Petri suitability:** good. Tools are simple and outputs short.
- **Calibration:** possible.
- **Verdict:** a good Nemotron-native *harness*, but not a power testbed without the same power layer AgentDojo needs, and its data is blander. **Don't pick** unless the NeMo stack is a hard requirement. If it is, port the AgentDojo-style power layer onto it.

### 3.2 ClawBench / ClawsBench / smolclaw

- **Which benchmark this is.** "ClawBench" is ambiguous:
  - TIGER-Lab's ClawBench is a live-web agent benchmark.
  - openclaw/clawbench is a separate project.

  Peyton means BenchFlow's **ClawsBench**, whose mock layer is **smolclaw**; Bingran You is an author of both [V: ClawsBench README].
- **ClawsBench** [V: README; paper page]:
  - 44 tasks: 30 single-service, 14 cross-service; 24 safety-critical.
  - 5 SQLite-backed mocks: Gmail, Calendar, Docs, Drive, Slack.
  - Deterministic before/after database-diff scoring, with safety violations penalized.
  - Safety categories include unauthorized access changes and data leakage.
  - **Tasks are not released** ("Tasks will be added soon").
  - **Licence CC BY-NC-SA 4.0.** Fine for non-commercial research, but share-alike applies.
  - Without scaffolding all models score 0–8%; with it, 39–63%.
- **smolclaw** [V: repo]:
  - MIT; WIP, last commit March 2026.
  - Gmail: 54 endpoints, including **filters, forwarding, auto-forwarding, delegates, send-as and vacation**. Calendar: 38 endpoints, including ACL. Docs and Drive bridge: 22, including permissions.
  - SQLite databases with snapshot, diff and restore, and an action log.
  - Conformance tests against real Google fixtures.
  - Essentially no tasks: the Gmail and Calendar task modules are marked "(stub)" and register nothing, and Docs registers one task [V: `grep register_task(`].
- **Power:** the best *persistence and permission* surface on this list, using real Google semantics (forwarding, delegates, filters, ACLs).
- **Petri suitability:** good. Petri can be given real Google API schemas, which also helps realism.
- **Calibration:** possible.
- **Verdict:** not a testbed on its own, because there are no tasks. **It is a strong drop-in neighbor or upgrade** for AgentDojo's toy mail and drive inside the Emma world. Ask BenchFlow for the ClawsBench tasks, as Peyton suggested.

### 3.3 Agent-Diff (arXiv 2602.11224, KDD '26)

- **Facts** [V: README; paper page; repo]:
  - 224 tasks: Box 48, Slack 59, Linear 57, Calendar 60. The repo now also has GitHub seeds and a test suite.
  - 108 endpoints that mirror the real APIs (REST, Slack Web API, GraphQL).
  - **The action space is code:** Bash or Python, whose HTTP calls are intercepted.
  - State is one Postgres schema per environment, cloned from templates.
  - **There is a mid-run fork:** `create_template_from_environment` clones a live environment's schema [V: `isolationEngine/core.py`].
  - The checker uses declarative assertions over the inserts, updates and deletes in the database diff, plus a **closed-world** rule: any unexpected change scores 0.
  - MIT.
  - deepseek-v3.2 scores 88.1 at $0.03 per test, and llama-4-scout 38.0.
- **Power:** real access-control objects:
  - Slack private channels (`not_in_channel` checks);
  - Box roles, collaborations and shared links;
  - Calendar ACL rules;
  - Linear team memberships.

  Whether Box permissions are enforced is [U].
- **Neighbors:** **the services are separate worlds.** Users differ per seed (agent@example.com, agent@gmail.com, agent@agentdiff.com…) [V: seeds]. They would need identity unification, though the seeds are editable JSON.
- **Petri suitability:** medium. The real API shapes help. Code-cell actions are hard to simulate, so expose the endpoints as function tools for both arms.
- **Calibration:** good, thanks to the fork primitive.
- **Verdict: #3.** It is the most realistic code-backed enterprise set with a verified fork. It is best used as a **source of neighbor systems** (Slack, Linear, Box, GitHub as "the company's" systems), or as a later testbed once identities are unified.

### 3.4 ToolEmu

- **Facts:**
  - 144 test cases [V: SafeMCP paper page, which reuses it].
  - Tools are *emulated by an LLM* (GPT-4), including an adversarial emulator. Separate LLM evaluators score safety and helpfulness.
  - Apache-2.0 [V: LICENSE].
  - There is no real state.
- **What that means:** there is no ground truth (criterion 4) and no checks on world state.
- **Verdict:** **not a testbed.** It is a *reference implementation* of the illusory side, useful for prompt design. Its 91.9% "no critical issues" rate is about single trajectories, not access decisions.

### 3.5 Agent-SafetyBench (THU-CoAI)

- **Facts:**
  - 349 environments, as Python classes over parameter dicts [V: `environments/` has 701 files, about 349 pairs of .py and .json].
  - 2,000 test cases in 8 risk categories [paper; V: `data/released_data.json` exists].
  - Scored by the **ShieldAgent LLM judge on the transcript** [V: README].
  - MIT [V].
  - Each case is its own one-off mini-world, and there is no task-success checker.
- **Verdict:** **exclude** as a testbed. It could be mined for "severe incident" probe content.

### 3.6 WebShop

- **Facts:**
  - 1.18M products and 12,087 instructions [V: README]; a 1,000-product subset is available.
  - The reward is a match of the purchased item's attributes, options and price [I: from memory of the paper].
  - The repo has an MIT file, but the README badge says "Princeton" licence [V: both present].
- **Power:** none beyond a single purchase. There are no accounts, other people or neighbor systems.
- **Verdict:** **exclude.**

### 3.7 Vending-Bench

- **Facts:**
  - Andon Labs' Vending-Bench and VB-2 environments are not open-source [I].
  - An open re-implementation exists: **Prosus Vending Bench**, Apache-2.0, 22 MCP tools, 6 machines, 30 or 365 simulated days, rule-based suppliers. The score is the final bank balance [V: README; AAIF blog].
- **Why exclude:** **power, as money, is the objective** (restriction R2 in the project docs), so taking power can't be told apart from competence.
- **Verdict:** **exclude** as the first testbed. At most a comparison for "resource power".

### 3.8 ComplexMCP

- **Facts** [V: repo; paper PDF]:
  - 7 Light* sandboxes (OS, Talk, Shop, Weather, Flight, Stock, News) share one session store and a LightOS clock.
  - 300+ tools; only **47 tasks**.
  - Rule-based final-state checks with a collateral-change penalty.
  - MIT.
  - The top model reaches 55%; humans 94%.
- **Power:** `ask_for_privilege` simply sets `has_privilege = True` in one call [V: `software/LightTalk/contact.py`]. That is atomic (restriction R6). There are also payment and trade passwords and VIP tiers.
- **Fork:** I found no snapshot API [I].
- **Verdict:** an interesting single-world multi-app design, but too few tasks and the privilege route is atomic. **Not a pick.**

### 3.9 SafeMCP

- **What it is:** a *defense method* paper [V: paper page]. Its "PowerSeeking Bench" has 112 prompts and 80 synthetic tools in 8 risk categories (privilege escalation, credential access, persistence…), judged by a GPT-4o rubric.
- **Licence:** the repo has no LICENSE file [V].
- **Verdict:** **not a testbed.** Its category list is a useful checklist.

### 3.10 Agent World Model (AWM, Snowflake/UNC)

- **Facts:**
  - 1,000 synthetic environments, each a SQLite database plus a FastAPI/MCP server, with 10 tasks each.
  - Database-state verifiers, plus a code-augmented LLM-judge variant.
  - The dataset is CC-BY-4.0 [V: HF card]. **The repo has no LICENSE file** [V].
  - There is a `reset_db` command [V: README].
- **Neighbors:** each environment is its own unrelated world, so there are no same-world neighbors. There is no auth by design (project prior-work file).
- **Verdict:** **a factory, not a testbed.** Use its pipeline to generate code-backed neighbor systems for whichever world we pick (the project's §9 "extend the base environment" option).

### 3.11 ClawEnvKit

- **Facts:**
  - MIT [V].
  - 22 mock services [V: `mock_services/`]. Examples: gmail, calendar, contacts, crm, finance, helpdesk, scheduler, spotify, kb, config.
  - In-memory FastAPI servers with an audit log and `/reset`, but **no dump or load**, so it can't fork without adding that [V: calendar `server.py`].
  - Scoring is mostly rules; the LLM-judge part is capped at 55% of the weight [paper page].
  - About $0.08 per generated environment [paper page].
- **Verdict:** **a factory**, like AWM.

### 3.12 AutoControl Arena

- **Facts:**
  - **Code is public** (CosmosYi/AutoControl-Arena, Apache-2.0) [V: LICENSE].
  - The logic layer is executable Python state; the narrative layer is an LLM [V: README].
  - 70 scenarios × 4 configurations = 280 cases, in 7 risk categories including instrumental convergence.
  - Scored by an LLM monitor (Qwen3-32B, F1 0.89–0.93 against humans) [paper page].
  - Against Petri it was preferred in 60% of 40 blinded comparisons. **This is a different figure from the earlier docs' "62.5% / 27.5%"; check the paper before citing either.**
  - Simulated vs real risk rates correlated at r = 0.87 on 10 scenarios.
- **Verdict:** **the design reference for hybrid Petri** (its logic/narrative split *is* our hybrid). Not a same-world future-task testbed.

### 3.13 PropensityBench (Scale AI)

- **Facts** [V: README; LICENSE]:
  - 979 scenarios × 6 = 5,874 cases.
  - Domains: cyber, self-proliferation, bio, chem.
  - **GPL-3.0.**
  - It measures whether the model picks the misaligned tool under pressure.
  - The project file says the aligned tool always fails and the misaligned choice is a single atomic action [not re-verified here].
- **Verdict:** **exclude.**

### 3.14 AuthorizationBench (PEACH Lab, arXiv 2610.27548)

- **Facts** [V: README; LICENSE; repo]:
  - MIT.
  - 286 tasks (44 originals plus contextual expansion), 10 domains, 14 situational pressures.
  - 49 deterministic mock service directories. Examples: bank_account, card_payment, crypto_wallet, etrade_broker, github_repo, issue_tracker, slack_workspace, saved_info, monitor_registry.
  - Each exposes `/state`, `/reset` and `/inject` [V: `services/_base.py`].
  - Every task has an authorization contract listing the violated actions [V: `task_config.json`], and the out-of-authorization path is executable.
  - Detectors use state hashes and diffs, plus judges [V: `evaluation/detectors`, `judges`].
- **Neighbors:** each task is its own persona world (e.g. a travel agent for "Priya Shah"). There is no shared world for future tasks.
- **Verdict:** the best source of **sanctioned vs. unsanctioned labels** and of ready-made overreach paths. Its mock services are good candidates to graft on as neighbors. It isn't the testbed itself.

### 3.15 τ-bench / τ²-bench (brief)

- **Facts** [V: repo]:
  - MIT.
  - Task counts: airline 50, retail 114, telecom 2,285, banking_knowledge 97, mock 10.
  - Scoring is a database hash against a replay of the gold actions (closed-world), plus substring checks on what was communicated and optional LLM natural-language assertions.
  - The user is simulated by an LLM, which makes runs stochastic.
- **Who the agent works for:** the agent is the *company's* representative and the counterparty is the customer, so "power" mostly means policy violations (e.g. airline `send_certificate`).
- **One relevant mechanic:** banking_knowledge has **unlockable tools** (`unlock_discoverable_agent_tool`, `give_discoverable_user_tool`) [V: tool names]. That is native capability acquisition.
- **Verdict:** **not first.** The unlockable-tools mechanic is worth borrowing.

### 3.16 Peyton's shared file system / Chinook / plain git repository

- **Chinook** [V: repo]: a sample music-store database with 11 tables (Artist, Album, Track, Invoice, Customer, Employee with a ReportsTo hierarchy…). The licence is MIT-style.
- **What's missing:** no tasks, no checkers, no users or permissions (SQLite has no GRANT), no agent harness. A git repo or shared file system is the same: a substrate, not an environment.
- **Petri suitability:** small SQL databases and file trees are easy to serialize. LLMs simulate query results over small tables reasonably, but aggregates are risky [I].
- **Verdict:** **not a first testbed.** Use it as a code-backed neighbor system, e.g. "the company database" or "the company repo" in the Emma world, with permissions added through Postgres roles or file ACLs.

---

## 4. Summary across all candidates

| Candidate | Same-world neighbors | Native power routes | Petri suitability | Real-vs-illusory calibration | Practicality | Role |
|---|---|---|---|---|---|---|
| **AgentDojo (merged Emma)** | Medium (one persona, needs reconciling) | Low (bait only) → high with a gating layer | **High** | **Full** | **High** | **#1 first testbed** |
| **AppWorld (held-out apps)** | **High** | **High** but pre-granted → high after withholding | Low–medium | High (future tasks must be written) | Medium | **#2** |
| **Agent-Diff** | Low (separate worlds) → medium after unifying | Medium (ACLs, private channels) | Medium | High (fork primitive) | High | **#3 / neighbor source** |
| smolclaw / ClawsBench | Medium | **High persistence** (filters, forwarding, delegates) | High (real schemas) | High | Low (no tasks; NC licence) | Neighbor upgrade |
| AuthorizationBench | Low (one world per task) | Medium–high (overreach paths) | Medium | High | Medium (Docker) | Labels and neighbor mocks |
| NeMo Gym WA (WorkBench) | Medium | None | High | High | High | Harness only |
| τ²-bench | Low | Low (policy violations; unlockable tools) | Medium (LLM user) | Medium | High | Borrow the mechanic |
| AWM / ClawEnvKit | None (factories) | None by design | High | High | High | Neighbor factory |
| AutoControl Arena | Low | Medium (scenario-specific) | Built-in hybrid | LLM monitor | Medium | Design reference |
| ComplexMCP | Medium | Low (atomic privilege) | Medium | Medium (no snapshot) | Low (47 tasks) | No |
| ToolEmu / Agent-SafetyBench / SafeMCP | None | n/a | (they are simulators or judges) | None | n/a | No |
| WebShop / Vending-Bench / PropensityBench | None | None, or power is the objective | n/a | n/a | n/a | Exclude |
| Chinook / git / shared FS | n/a | None | High | Possible | Low (no tasks) | Neighbor substrate |

---

## 5. Ranked shortlist

### 1. AgentDojo, as one merged Emma Johnson world

Workspace is the main system. Banking, Travel and Slack are gated, held-out neighbors. Hybrid Petri runs in fixed mode.

**For:**
- Hybrid Petri's best case: state of 2–52 KB per suite, fully visible to the auditor; short calls; real schemas, already Inspect tools.
- Native future tasks run on any fork; deep-copy fork; MIT; cheap; works with small models.
- Full calibration: every neighbor task runs both ways.
- The team's plan already covers most of the build.

**Against:**
- The cross-suite power routes are ours to build (red-team findings 1 and 3).
- The worlds are tiny, and Travel tasks are mostly answer-string checks.
- The data is inconsistent and needs reconciling, and the benchmark is recognizable.

### 2. AppWorld, with held-out apps and withheld passwords

Run both arms in function-calling mode.

**For:**
- Native, multi-step cross-app power:
  - Gmail and Phone reset every app;
  - new accounts the agent controls;
  - cards and Venmo money that move across apps.
- Real, rich, same-supervisor neighbors with state-based checks.
- Peyton's code and trajectories already exist.
- Withholding passwords is a data edit, not new routes.

**Against:**
- The worst simulator target among the plausible options: a REPL, or 457 function tools; ~370K rows; 40+ calls per task.
- Native tasks can't serve as future tasks, so we must write them.
- Closed-world collateral checks; one world per process.
- It is hard for small models: GPT-4o function calling reaches 32% test-normal.
- The licence restricts publishing transcripts.
- The supervisor hands every password over on step 0 unless modified.

### 3. Agent-Diff, as neighbor systems or a later testbed

**For:**
- Real-API replicas (Slack, Box, Linear, Calendar, GitHub) with real access-control objects.
- A verified mid-run fork (`create_template_from_environment`).
- Deterministic diff assertions; MIT; deepseek-v3.2 scores 88% at about $0.03 per test.

**Against:**
- Its services are separate worlds with different users, so they need unifying.
- Its native action space is code calling HTTP (hard to simulate), and its checks are closed-world.
- It has no money or credentials.

---

## 6. Unknowns worth checking before committing

1. **AppWorld supervisors.** How many distinct supervisors are there, and do any native tasks share one? This needs the data bundle (S3, size unknown; not downloaded) or Peyton's local copy. If some supervisors carry many tasks, part of the AppWorld future-task pool comes free.
2. **AppWorld password storage.** Does deleting a held-out app's `AccountPassword` row hide it from `show_account_passwords` without breaking anything else? Does `reset_password` update that row? The code is encrypted; a 10-minute check in Peyton's install would settle it.
3. **Gmail signup in AppWorld.** Does it really need no verification? (Route 5 depends on it.)
4. **Model performance.** DeepSeek V4.1 Flash on AppWorld test-normal, in ReAct and in function-calling mode. Peyton may already know.
5. **The JWT/`import appworld` escape.** Does it actually work? Test only inside Docker, and decide whether it is in scope.
6. **What exists for AgentDojo.** Whether any AgentDojo power-layer code exists yet, or only the plan.
