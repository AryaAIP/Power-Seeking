> **Status (2026-11-01):** Superseded. Written for the AgentDojo and Petri plan. Current setup knowledge is in runbook.md. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Infrastructure Plan

*Prepared for Arya, 2026-10-26. This is the system that runs `plan-environment-and-power-meter.md`. The facts below about Tinker, Petri, Inspect and AgentDojo were checked against their current repositories. The snapshot timings were measured on the stock AgentDojo workspace.*

---

## 0. Summary

- **Shape.** A small core of five pieces:
  1. World;
  2. model client;
  3. runner;
  4. narrator hook;
  5. meter.

  Plus run records, and two thin adapters:
  - one turns any World into a Tinker RL environment;
  - one exposes any World to Inspect and Petri.
- **Generality comes from one interface.** Every environment implements the same World interface, about a dozen methods. The runner, the meter and the adapters only talk to that interface, so adding an environment means writing one adapter and touching nothing else.
- **Models go through one client.** LiteLLM handles OpenRouter, any OpenAI-compatible server, and Tinker. Tinker works through the LiteLLM provider in Tinker's cookbook, which also returns the token IDs that training needs.
- **Mostly reuse:**
  - AgentDojo for the world, tools and task checkers;
  - LiteLLM and Tinker's cookbook for model access, the DeepSeek V4.1 renderer and the RL loop;
  - Inspect and Petri for the optional hybrid-Petri route.

  We build the power layer, runner, meter, narrator hook and records.
- **What I need from you** (§9):
  - approve the shape;
  - say where the code should live;
  - confirm API keys.

---

## 1. Requirements

These come from the plan and your messages.

1. **Many environments.** AgentDojo comes first. AppWorld, τ²-bench, TextWorld or a Petri-style world must not need changes to the core.
2. **Many model backends.** OpenRouter now, Tinker for the same model, and anything OpenAI-compatible.
3. **Forking.** Save and restore any state mid-trajectory cheaply, and resume a conversation from it.
4. **The meter**, with everything the plan specifies:
   - paired future-task runs per branch;
   - surgery;
   - the holdings list;
   - both inheritance modes;
   - the minimal-agent baseline.
5. **Hybrid.** An optional narrator whose proposals code validates.
6. **Tinker RL later,** without rewriting the environment.
7. **Petri-compatible.**
8. **Not overengineered:** no plugin system, no database, no services. Plain Python, files on disk.

---

## 2. The core

```
   Model client (LiteLLM)                          World (one interface)
   OpenRouter | Tinker | any OpenAI-compatible     e.g. AgentDojo workspace + power layer
            \                                        /
             +----------------> Runner <------------+
                        agent loop; resumes from any snapshot
                          |                     |
                   Narrator hook          Run records
              (LLM, or the code twin)    (JSONL + snapshots)
                                                |
                                              Meter
                          (forks, surgery, future tasks, statistics)

   Adapters:  World + runner  -> Tinker MessageEnv (RL training)
              World           -> Inspect tools (Inspect models, Petri auditor)
```

### 2.1 World: the interface every environment implements

```python
class World(Protocol):
    def reset(self, config: dict, seed: int) -> None
    def tools(self) -> list[ToolSpec]                        # OpenAI-format JSON schemas
    def call(self, actor: str, name: str, args: dict) -> ToolResult
                                                             # enforces permissions, appends to the audit log
    def snapshot(self) -> bytes                              # whole state: task data, power tables, audit log
    def restore(self, blob: bytes) -> None
    def power_state(self) -> dict                            # structured holdings, read from the power tables
    def holdings_list(self) -> str                           # fixed-template text built from power_state()
    def surgery(self, op: SurgeryOp) -> None                 # environment-specific removal operations
    def tasks(self) -> list[TaskSpec]                        # id, prompt, stratum, routes it depends on
    def score(self, task: TaskSpec, pre: bytes, post: bytes, final_text: str) -> float
                                                             # 0..1, ignores the power tables
    def needs_reply(self, call: ToolCall) -> ReplyRequest | None
                                                             # does this call go to a person (narrator)?
    def apply_proposal(self, proposal: dict, by: str) -> bool
                                                             # check the world's rules, then commit or reject
```

**AgentDojo's workspace fits this directly.**
- **Snapshots.** Its state is a pydantic object, so `snapshot` is a JSON dump. On the stock workspace that's 112 KB, 3 ms to save and 38 ms to restore, and the restored state equals the original.
- **Tools** are already Python functions with schemas.
- **Scoring.** `score` wraps the native `utility(...)` checkers, with the power tables excluded.

**Not every environment can fill every method.** A world with no code state, such as pure Petri, has an empty `power_state`, so only the transcript-based parts of the meter work there. That's a limit of such worlds, not of the design.

**`actor` lets one world serve several roles.** The same world serves the agent, the evaluator and the minimal agent. Narrated colleagues also act through it, so they pass the same permission checks.

### 2.2 Model client

**One call:** `chat(model_cfg, messages, tools)`. It returns:
- the assistant message;
- usage and cost;
- token IDs, when the backend provides them.

**Built on LiteLLM:**
- **OpenRouter:** `openrouter/<model>`.
- **Tinker:** the LiteLLM provider in Tinker's cookbook, model `tinker/<label>` with `base_model` set to Tinker's DeepSeek-V4.1-Flash.
  - It uses Tinker's native sampler.
  - It supports tool calls for models whose renderer declares tools, and the DeepSeek V4.1 renderer does.
  - It returns prompt and completion token IDs.
- **Anything OpenAI-compatible,** such as vLLM or Tinker's own OpenAI-compatible endpoint: set the base URL in the config.

**`model_cfg` pins everything that changes behavior:**
- model;
- backend;
- temperature;
- max tokens;
- reasoning mode (DeepSeek V4.1 has thinking and non-thinking modes);
- system-prompt ID.

The agent, evaluator, minimal agent, narrator and monitor are just different `model_cfg`s.

**Cost.** LiteLLM reports usage. The client keeps a running total per run and stops at a cap.

### 2.3 Runner (the agent loop)

**One call:** `run_episode(world, model_cfg, messages, max_calls, start_snapshot=None) -> EpisodeRecord`.

**The loop:**
1. Ask the model.
2. Run each tool call through `world.call`.
3. If `world.needs_reply`, ask the narrator.
4. Append the results.
5. Stop on a final answer, the call cap, or too many errors.

**It saves a snapshot after every step,** along with the power-state diff and the audit entries. Snapshots are stored by content hash, so unchanged states cost nothing. This is what makes forking at any node possible later.

**It can resume from any (snapshot, messages) pair.** That one feature covers:
- forks;
- both inheritance modes;
- the interrupt message;
- the minimal-agent baseline.

**Operational details:**
- asynchronous, with a concurrency limit;
- retries on API errors;
- malformed tool calls go back to the model as tool errors, and are counted.

### 2.4 Narrator hook (hybrid)

**Interface:** `reply(state_view, thread, persona) -> (text, proposal or None)`.

**Two implementations:**
- **LLM narrator.** A fresh call every time, seeing only the serialized state view and the thread, so forks can't leak into each other.
- **Code twin.** Templates, with the decision made by the same rules.

**Either way, `world.apply_proposal` decides what's committed.** Every proposal is recorded, whether accepted or rejected. That gives the leniency and persuadability numbers for free.

### 2.5 Meter

The meter is plain functions over the World interface and the records:

| Function | What it does |
|---|---|
| `make_reference(snapshot, ops)` | Surgery, then the consistency and sufficiency checks; returns a new snapshot |
| `minimal_agent_reference(task)` | Runs the runner with the minimal-agent config; returns its end snapshot |
| `measure(snapshot, transcript, tasks, evaluator_cfg, samples, mode)` | Scores the evaluator on D from that state. `mode` is either the holdings list or the transcript plus the interrupt |
| `compare(a, b)` | Per-stratum paired differences, intervals, and the noise floor |
| `choose_nodes(record)` | Power-table changes, route-related audit entries, 2 random steps, and the end state |

Meter results are records too, so every number traces back to its episodes.

### 2.6 Run records

**Each run is a directory:**
- `config.yaml`;
- `episodes.jsonl`, one line per episode;
- `snapshots/<hash>.json`;
- `meter.jsonl`.

**An episode record holds:**
- run and episode IDs;
- world name, version and config;
- model config;
- parent snapshot and fork info: which node, which branch, which inheritance mode;
- the messages;
- per step: tool calls, results, audit entries, the power-state diff, and the snapshot hash;
- score, usage and cost;
- token IDs, when available.

**Analysis reads only these files, never an environment.** Viewing starts with a small notebook. Exporting to Inspect's log format, so that `inspect view` works, is an optional extra for later.

---

## 3. Adapters

### 3.1 Tinker RL (later, but the core is shaped for it now)

**What Tinker's cookbook provides:**
- **`MessageEnv`:** a message-level environment interface. Initial messages go in; for each assistant message, it returns tool results and a reward.
- **`EnvFromMessageEnv`:** a wrapper that turns a `MessageEnv` into the token-level environment the RL loop trains on, using the model's renderer.

**Our adapter is one class:** a `MessageEnv` holding a World. It does what the runner's loop does:
- run tool calls;
- call the narrator;
- compute the reward from `world.score` at the end.

**Matthew's interrupt-and-assign training** becomes an environment that runs goal 1, interrupts, then runs goal 2, with per-step rewards:
- goal-2 steps get the task reward;
- goal-1 steps get the power penalty, from a cheap version of the meter.

Tinker's transitions carry per-step rewards, so this fits.

**Already in the design, so this works later:**
- tools as OpenAI-format schemas (the cookbook converts them);
- rewards computed by code;
- worlds built from config inside `make_envs` (Tinker requires these builders to be picklable);
- the same reasoning mode on OpenRouter and Tinker.

### 3.2 Inspect and hybrid Petri

A small function wraps a World's tools as Inspect tools. That gives two things.

**1. Inspect's models and logs.**
- The agent runs inside Inspect with any Inspect model.
- That includes Tinker models, through the cookbook's Inspect bridge (`InspectAPIFromTinkerSampling`).
- Inspect also has its own AgentDojo port (`inspect_evals/agentdojo`), useful as a cross-check.

**2. Hybrid Petri.**
- Petri's auditor accepts extra tools, and it can stage tool results for the target (`controller().stage_tool_result`).
- We give it two tools:
  - `world_call` runs the real tool against the code state;
  - `world_propose` sends a state change through `apply_proposal`.
- The auditor narrates and stages results, and the code state stays the source of truth. That's the hybrid design, running inside Petri itself.
- **For measurement, each fork starts a fresh auditor.** Petri's rollback keeps the auditor's memory, so we don't use it.

**Our own narrator (§2.4) is the default,** because it's simpler and cheaper. The Petri route is for when we want Petri's auditor, realism filter or judge.

---

## 4. Reuse vs build

| Piece | Reuse | Build |
|---|---|---|
| Workspace world, tools, task checkers | AgentDojo (MIT licence) | Power layer, renamed data, targeted tasks, surgery operations, the World adapter |
| Model access | LiteLLM; Tinker cookbook's LiteLLM provider and DeepSeek V4.1 renderer | Model configs, cost cap |
| Agent loop and forking | — | Runner (small) |
| Narrator | Petri's auditor (optional route) | Narrator hook, code twin |
| Meter | — | Meter functions, statistics |
| RL | Tinker cookbook (`MessageEnv`, RL loop) | One adapter class (later) |
| Records and viewing | Inspect's log viewer (optional, later) | Record schema, notebook |

---

## 5. Adding another environment

Implement the World methods. Nothing in the runner, the meter or the adapters changes.

| Environment | Snapshot | Scoring | Note |
|---|---|---|---|
| **AppWorld** | SQLite file copy | Its unit tests become `score` | |
| **τ²-bench** | JSON dump of its in-memory database | Its checks | Keep the power tables out of its database hash |
| **TextWorld / Jericho** | `get_state` / `set_state` | Quest score | Exact POWER is computable, which makes this the calibration world |
| **Petri-only scenario** | The transcript | Transcript-based only | No code state, so `power_state` is empty |

---

## 6. Build order (tied to the experiments)

| Milestone | Builds | Unlocks |
|---|---|---|
| **M0** | World interface; AgentDojo workspace adapter (no power layer yet); model client with OpenRouter; runner; records | E0 pilot on native tasks |
| **M1** | Power layer; per-step snapshots; surgery; holdings list; meter | E0 with the power layer; E1; E2 |
| **M2** | Tinker backend through the same client; parity check on the pilot tasks | The same model on both backends |
| **M3** | Narrator hook and code twin | E3 with social routes; E4 |
| **M4** (when needed) | Inspect wrapper and Petri auditor tools | Hybrid inside Petri |
| **M5** (later) | Tinker `MessageEnv` adapter | Training (Matthew's steps 3–4) |

---

## 7. Code layout

```
powermeter/
  core/        world.py  models.py  runner.py  narrator.py  records.py
  meter/       measure.py  surgery.py  nodes.py  stats.py
  worlds/
    agentdojo_workspace/   world.py  power_layer.py  tasks.py  surgery_ops.py  rules.py  data/
  adapters/    tinker_env.py  inspect_tools.py  petri_tools.py
  configs/     models/  runs/
  notebooks/
runs/          (outputs, not committed)
```

---

## 8. Risks

| Risk | Response |
|---|---|
| **The two backends may not serve the same model the same way.** OpenRouter's providers and Tinker's renderer may differ in chat template or reasoning mode | M2's parity check catches this. Until then, every result names its backend |
| **Seeds.** Not every provider honors a seed | Pair by task and sample index, not by identical random draws. The analysis already assumes this |
| **Large tool outputs.** File listings in the workspace include file contents | Watch tokens in the pilot. If outputs need trimming, trim them in the adapter, identically on both branches |
| **Tinker's tool-use library is marked experimental** in the cookbook | The RL adapter may need changes by the time we reach M5 |

---

## 9. Decisions needed

1. **Approve the shape:** our own thin core plus adapters, rather than building everything inside Inspect. Inspect would give logging and providers for free, but it makes mid-trajectory forking and Tinker RL awkward.
2. **Where the code lives:** a new GitHub repository, or your Power-Seeking folder for now.
3. **Accounts:** an OpenRouter key now, and a Tinker key by M2.
