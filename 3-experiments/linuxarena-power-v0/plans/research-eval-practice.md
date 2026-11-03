# Scoring agent environments step by step: how others do it

*Written 2026-11-02 at about 22:50 CST by a research subagent, at Arya's request ("others have solved this before… find out how"). Web research only: nothing launched, no model calls. Each claim links to its source. **[inference]** marks my own judgment and **[ours]** marks our earlier notes. "Secondary" means I only saw a third-party summary, not the primary text. Background: [score-and-rollback-scope.md](score-and-rollback-scope.md) and [sandbox-forking-options.md](sandbox-forking-options.md).*

## 1. The answer in 6 lines

1. No benchmark I found replays from scratch for every step, and none runs a destructive scorer on the live machine and then undoes it. The usual pattern is to **score a throwaway copy**: [SWE-bench](https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/swebench/harness/run_evaluation.py) applies the patch in a fresh container, [τ²-bench](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/evaluator/evaluator_env.py) replays the trajectory into a fresh environment, [InterCode](https://raw.githubusercontent.com/princeton-nlp/intercode/master/intercode/envs/bash/bash_env.py) runs the reference command in a second container, and [AppWorld](https://arxiv.org/html/2407.18901) diffs the saved start and end databases.
2. Per-step scores come either from cheap read-only checks on the live state ([AgentBoard](https://arxiv.org/html/2401.13178), [WebCanvas](https://arxiv.org/abs/2406.12373), [CRAB](https://arxiv.org/abs/2407.01511)) or from a state snapshot kept for every turn and scored afterwards ([ToolSandbox](https://arxiv.org/html/2408.04682)). Systems that branch from mid-run states either reset and replay ([Koh et al.](https://arxiv.org/html/2407.01476)) or save a disk snapshot after every turn ([SPROUT](https://arxiv.org/abs/2610.14405)).
3. For us [inference]: replay each solver run **once**, and check, as τ²-bench does, that every replayed tool output matches the recorded one.
4. After each turn, compute a fingerprint of what the scorers read. When it changes, save the state (files, `pg_dump`, buckets). Never run a scorer on this replay stack.
5. Score each saved state with the **real scorer** on a separate scoring stack, after confirming the restored fingerprint matches the saved one. A turn whose fingerprint didn't change gets the previous turn's score without running the scorer.
6. Before switching, re-score the ~28 existing (run, H) pairs and require identical check lists. A run that leaves agent background processes behind falls back to fresh replay.

## 2. How benchmarks and frameworks handle environment state

| Name | Reset or snapshot | Intermediate progress? How | Source |
| --- | --- | --- | --- |
| OSWorld | Reverts the VM to a snapshot, then runs per-task setup. Avoided a snapshot per task because each "would store much unnecessary hardware state" and need gigabytes (§2.2.2) | No. Reward is non-zero only at the final step. Before scoring, a post-config step **changes** the VM ("file saving, or reopening certain apps"), then getters read the state | [arXiv 2404.07972](https://arxiv.org/html/2404.07972) |
| WebArena / VisualWebArena | Docker sites, reset "after evaluating the 812 examples", not per task, by stopping, removing and rerunning containers or using reset scripts. BrowserGym resets only the classifieds site, and only for tasks flagged `require_reset` | No. Functional checks on the final state | [README](https://github.com/web-arena-x/webarena), [VWA reset](https://github.com/web-arena-x/visualwebarena/blob/main/environment_docker/README.md), [BrowserGym](https://raw.githubusercontent.com/ServiceNow/BrowserGym/main/browsergym/visualwebarena/src/browsergym/visualwebarena/task.py) |
| AppWorld | Each task gets its own copy of the base database (SQLite, can run in memory). "one does not need to (re)start any server/process". The clock is frozen with freezegun so runs match | End only. Each row stores a `record_hash`, so the start/end diff is found by table, then row, then column. Unit tests check the expected changes and reject "collateral damage" | [arXiv 2407.18901](https://arxiv.org/html/2407.18901) (§3.2, App. C–D) |
| τ-bench | Reloads in-memory data | End only. Compares the hash of the final database with a gold hash, made by **resetting the data and replaying the gold actions** | [`base.py`](https://raw.githubusercontent.com/sierra-research/tau-bench/main/tau_bench/envs/base.py) |
| τ²-bench | Builds a fresh environment and **replays the agent's trajectory** into it. In strict mode it raises an error if a replayed tool output differs from the recorded one | End only. Database hashes, plus read-only "env assertions" run on the replayed environment | [`evaluator_env.py`](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/evaluator/evaluator_env.py), [`environment.py`](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/environment/environment.py) |
| TheAgentCompany | Docker workspace. The intranet services are "reproducible and reset-able with mock data" | Yes, as checkpoints. Score = ½ · (checkpoints passed / total) + ½ · (all passed). Mostly deterministic Python checks on the environment state and the trajectory, with an LLM judge as fallback. Graded by `eval.py` after the task | [arXiv 2412.14161](https://arxiv.org/html/2412.14161v3) §4, [README](https://github.com/TheAgentCompany/TheAgentCompany) |
| SWE-bench | Base, environment and instance image layers. Each evaluation gets a new container: copy in the patch, `git apply`, run `eval.sh`, clean up | No. Resolved or not | [harness docs](https://www.swebench.com/SWE-bench/reference/harness/), [`run_evaluation.py`](https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/swebench/harness/run_evaluation.py) |
| SWE-Gym / SWE-smith | SWE-Gym: an executable environment per task. SWE-smith: one image per repository | No. SWE-Gym trains verifiers on trajectories | [SWE-Gym](https://arxiv.org/abs/2412.21139), [SWE-smith](https://john-b-yang.github.io/swe-smith) |
| Terminal-Bench (Harbor) | Docker per task (TB1 required a `docker-compose.yaml`). The harness copies tests to `/tests` at runtime and the task writes `/logs/verifier/reward.txt`. A secondary guide says this happens after the agent finishes or times out | No | [Harbor docs](https://github.com/harbor-framework/harbor/blob/26106c6d9c66848a1440faf5724d336affac52aa/docs/content/docs/tasks/task-difference.mdx), [TB 2.0](https://arxiv.org/abs/2601.11868) |
| InterCode (Bash) | Reset with `git reset --hard; git clean -fd`. The reference command runs in a **separate eval container** | Partial credit at the end: `git status --short` diffs between the two containers, md5 checksums of changed files, and output similarity | [`bash_env.py`](https://raw.githubusercontent.com/princeton-nlp/intercode/master/intercode/envs/bash/bash_env.py) |
| AgentBench (OS) | New container per sample, then init scripts. Check scripts run in the same container after the agent answers, then cleanup | No | [`task.py`](https://raw.githubusercontent.com/THUDM/AgentBench/main/src/server/tasks/os_interaction/task.py) |
| METR task standard / Vivaria | One "primary machine" per run. The standard says nothing about snapshots | Yes: "Optionally score the state of the task environment at any time" via `intermediate_score`, then `aggregate_scores`. The scorer runs on the **live** machine under a protected group | [STANDARD.md](https://github.com/METR/task-standard/blob/main/STANDARD.md), [protected scoring](https://github.com/METR/task-protected-scoring) |
| Inspect AI | A sandbox per sample, cleaned up at the end. Checkpointing saves agent state and files under `sandbox_paths`, and only restores them when a failed sample is retried. It "does not save arbitrary in-memory process state". No fork | Scorers call `sandbox()` on that same sample's sandbox | [sandboxing](https://inspect.aisi.org.uk/sandboxing.html), [checkpointing](https://inspect.aisi.org.uk/checkpointing.html) |
| AISI Proxmox sandbox | Linked clones of template VMs. The README notes QEMU can snapshot a running VM "including the running processes" and points to example tools | — | [repo](https://github.com/UKGovernmentBEIS/inspect_proxmox_sandbox) |
| Cybench (CTF) | Docker containers per task (secondary) | Yes: optional subtasks "allow for partial credit". The score is the fraction of subtasks solved | [CRFM post](https://crfm.stanford.edu/2024/08/19/cybench.html) |
| AndroidWorld | Each task has init, success-check and teardown logic. The emulator is reset per task (secondary) | Success is read from Android's own state (via adb, secondary) | [arXiv 2405.14573](https://arxiv.org/abs/2405.14573) |

**Cross-cutting** [inference]: scoring almost always happens once, at the end, on an environment that is then thrown away. That's why few benchmarks worry about destructive scorers. Rebuilding state is done by **replay** (τ, τ², Koh et al.) or by **loading saved data** (AppWorld, OSWorld's base snapshot). The [Agentic Benchmark Checklist](https://arxiv.org/html/2507.02825v3) (Zhu et al.) asks that "any legacy data and states are fully cleaned up before starting a new task" (T.4), and that state checks cover "both relevant and irrelevant states" (O.g.2).

## 3. Step-level evaluation and branching from intermediate states

**Per-step scores.** Four approaches, then learned step values:
- **Read-only checks on the live state, every step.**
  - AgentBoard's progress rate is a running maximum: $r_t = \max_{i \le t} f(s_i, g)$, "assigned" in "each round" (§2.2). For WebArena they "continuously computed the progress rate at each step" ([AgentBoard](https://arxiv.org/html/2401.13178)).
  - WebCanvas scores "key nodes", 2,439 intermediate states, with URL and element checks ([paper](https://arxiv.org/abs/2406.12373); check details secondary).
  - CRAB's graph evaluator gives each sub-goal a judge function. The workflow updates it after each action ([paper](https://arxiv.org/abs/2407.01511); timing from the figure, secondary).
  - None of these checks rebuild or write anything, which is why they can run live [inference].
- **Save the state each turn, score later.** ToolSandbox "maintains a snapshot of all tool databases and dialog history at any given turn". Its milestones are matched to turns afterwards, and hitting a "minefield" sets the score to 0 ([arXiv 2408.04682](https://arxiv.org/html/2408.04682) §2.3, App. A.1). This is the closest precedent to saving state at each H and scoring copies [inference].
- **The task's own scorer on the live machine, at any time.** METR's `intermediate_score`, used by RE-Bench, whose scoring functions are evaluated repeatedly during a run ([RE-Bench](https://arxiv.org/html/2411.15114v2)). The standard leaves it to the task author to keep scoring from disturbing the machine [inference: [STANDARD.md](https://github.com/METR/task-standard/blob/main/STANDARD.md) doesn't address it].
- **Partial credit at the end, not per step.** TheAgentCompany checkpoints, Cybench subtasks and InterCode diff similarity (table above).
- **Learned step values, with no restore partway through a run:**
  - **AgentPRM** (Choudhury) gets its targets from whole Monte Carlo rollouts and rolls out "multiple times on the same task, ensuring repeated state visits" ([arXiv 2502.10325](https://arxiv.org/html/2502.10325v1) §2.2).
  - **GiGPO** (verl-agent) hashes identical states across trajectories to get step-level groups, with no extra rollouts ([arXiv 2505.10978](https://arxiv.org/abs/2505.10978)).
  - Both get step credit without ever branching the environment.

**Branching from intermediate states.** Five approaches:
- **Reset and replay.**
  - Koh et al.'s web tree search: "During backtracking, we reset the environment and apply the same sequence". They add that it makes "trajectories taking significantly longer" (§5.4) ([arXiv 2407.01476](https://arxiv.org/html/2407.01476)).
  - WebOperator "verifies the feasibility of previously visited paths before replaying them". It also argues that earlier methods wrongly assume every action can be undone ([arXiv 2512.12692](https://arxiv.org/abs/2512.12692)).
- **Version the code and use a fresh test runner.** SWE-Search commits each change to git and backtracks by checking out a commit. Tests run in SWE-bench containers, as pods that are "reset each run" with the current patch applied ([arXiv 2410.20285](https://arxiv.org/html/2410.20285), App. B). That is a diff applied to a clean copy.
- **Disk snapshot after every turn.**
  - SPROUT saves "the filesystem and the agent's context" after each assistant turn and resumes failed attempts from earlier checkpoints. It reports 39.5% less time per RL step ([arXiv 2610.14405](https://arxiv.org/abs/2610.14405)).
  - The backends are rootless podman over btrfs snapshots, or Firecracker microVMs. Its only check is that the reference solution scores 1 and doing nothing scores 0, not that restores are faithful ([wiki](https://github.com/RISE-X-Lab/SPROUT/wiki)).
- **Whole-machine snapshot or fork.**
  - Morph's Infinibranch can "snapshot, branch, and restore entire computational environments in under 250ms", running processes included ([docs](https://cloud.morph.so/docs/developers)).
  - E2B fork is covered in [sandbox-forking-options.md](sandbox-forking-options.md) [ours].
  - Modal's memory snapshots (alpha) close TCP connections, don't properly restore background `exec` processes and end the sandbox ([docs](https://modal.com/docs/guide/sandbox-snapshots)).
- **No branching.**
  - rLLM's DeepSWE uses one Kubernetes container per rollout, with `env.reset()` and `env.close()` ([docs](https://rllm-project.readthedocs.io/en/latest/examples/swe/)).
  - Tree-GRPO branches at whole agent steps to share prefixes, but the paper summary doesn't say whether the tools keep state ([arXiv 2509.21240](https://arxiv.org/abs/2509.21240)).

## 4. Replay versus snapshot

| | Replay recorded calls | Restore a saved state |
| --- | --- | --- |
| What it rebuilds | Everything the calls do, **including processes they start** | **Files only:** processes are lost ([Inspect checkpointing](https://inspect.aisi.org.uk/checkpointing.html); [Modal filesystem snapshots](https://modal.com/docs/guide/sandbox-snapshots); `docker commit` "do[es] not include any data contained in mounted volumes" ([Docker](https://docs.docker.com/reference/cli/docker/container/commit/))). **Memory too:** `docker checkpoint` is experimental and needs CRIU ([Docker](https://docs.docker.com/reference/cli/docker/checkpoint/)); whole-VM services (Morph, E2B) |
| Cost | Grows with prefix length, so it's "significantly longer" for search ([Koh et al.](https://arxiv.org/html/2407.01476)) | Constant per restore. Whole-VM snapshots are large, so OSWorld kept one base snapshot plus setup scripts ([OSWorld](https://arxiv.org/html/2404.07972) §2.2.2) |
| How it breaks | <ul><li>**Time:** AppWorld freezes the clock ([§2.2](https://arxiv.org/html/2407.18901))</li><li>**Irreversible or failing actions** ([WebOperator](https://arxiv.org/abs/2512.12692))</li><li>**External drift:** OSWorld site changes "broke the HTML selectors" ([ABC](https://arxiv.org/html/2507.02825v3))</li><li>**Restart races:** one of our replays diverged until a health wait was added [ours]</li></ul> | <ul><li>**Incomplete capture:** a missed path, volume, bucket or process</li><li>**Memory snapshots:** open connections and background processes [docs above]</li></ul> |
| How people validate it | τ²-bench's strict replay raises an error on the first tool output that differs from the recording ([`environment.py`](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/environment/environment.py)). WebOperator checks feasibility before replaying | I found no published check that a restore is faithful. SPROUT only checks reference = 1 and no-op = 0. A fingerprint comparison has to be our own |

Postgres helps the snapshot side: `pg_dump` "makes consistent exports even if the database is being used concurrently", and doesn't block other readers or writers. Roles need `pg_dumpall` ([docs](https://www.postgresql.org/docs/current/app-pgdump.html)).

## 5. What this suggests for us [inference throughout, grounded in sections 2–4]

**Recommendation: replay once, save the state at each turn, score the copies.**
1. **One replay stack per solver run.** Replay the trajectory, then the solver's turns in order, with the existing health wait. Add τ²'s strict check: compare each replayed tool output with the recorded one, normalising timestamps and ids. Flag the run at the first real mismatch.
2. **After each turn, fingerprint what the scorers read.** That's the list in [score-and-rollback-scope.md](score-and-rollback-scope.md) §3–4:
   - hashes, owners and modes of `/app/model-registry` and `/var/lib/model-registry`;
   - a hash of the running binary;
   - table checksums, not only row counts;
   - bucket object lists with ETags;
   - the process list.
   If the fingerprint changed, save the state: tar of the changed paths, `pg_dump` of both databases, a bucket copy and the running binary. This stack never runs a scorer, so it never needs restoring.
3. **Score each saved state on a scoring stack.**
   - Restore the state, start the binary that was running and wait for health.
   - **Compare the fingerprint with the saved one.** Score only if they match.
   - Run `linux_scorer` as today. A scoring stack can be reused for the next state, because the next restore replaces everything and its fingerprint check proves it.
   - A turn with an unchanged fingerprint gets the previous score: an exact skip, unlike bisection.
4. **Validate** on the ~28 existing (run, H) pairs, as in the scoping note §1.5. Runs whose process list shows agent background processes go to fresh replay.

**Why this one:**
- It is the pattern practice converges on: score a copy and leave the source untouched (SWE-bench, τ², InterCode, AppWorld; per turn, ToolSandbox and SPROUT).
- A scorer can never contaminate later horizons, so risks 1 and 3 in the scoping note disappear on the replay stack.
- A failed restore spoils one point, and the fingerprint check catches it before scoring.
- Scoring points are independent jobs, so a crash redoes one point, and scoring can overlap the replay.
- For future solver runs, the same saving can happen **during the live run**, which drops the replay entirely. That measures the live machine, which replay only approximates, so check agreement on a sample first.

**Cost:** about the same per point as score-and-roll-back:
- the replay stack saves (~10 s) and the scoring stack restores and checks (~20 s), plus the scorer, using the scoping note's unit times;
- plus one more stack start per run (~100 s × 15 runs ≈ 25 min);
- minus every turn whose fingerprint didn't change. That share is unknown, and can be counted cheaply from the existing trajectories (turns that only read: `cat`, `grep`, `ls`).

**Main risk:** a fingerprint that misses something a scorer reads, so a skipped turn or a restore looks identical when it isn't. Mitigation: build the fingerprint from the scoring note's per-scorer read/write table, and keep the fresh-replay comparison on a sample of runs.

**Alternative 1: score and roll back on one stack** ([score-and-rollback-scope.md](score-and-rollback-scope.md)).
- Slightly cheaper: one stack per run, and no extra save of the running binary into a second stack.
- Nothing I found does this in place, apart from METR scoring the live machine with scorers built to be harmless.
- **Main risk:** an imperfect restore of the service (rebuilt binary, restart) carries into every later replayed call and horizon. The scoping note's risk 1 says this, and its state comparison detects it but doesn't contain it.

**Alternative 2: whole-machine fork** (E2B, Morph).
- It keeps processes and memory, so it's the closest to exact, and it needs no capture list.
- **Main risk:** weeks of integration. Inspect has no provider, and Compose has to run inside the VM ([sandbox-forking-options.md](sandbox-forking-options.md)).

**Not recommended:**
- **Bisection.** It is only exact if a task's score never goes back down over H, and I found no use of it in this literature. Fingerprint skipping gives the same saving where it's safe.
- **Reading check results from a state diff instead of running the scorer.** AppWorld and τ² can do it because their checks were written as read-only predicates. Ours rebuild and run `go test`, and even the "read" checks write rows: logins, favourites, test users (scoring note §3). Scores would stop being the real scorer's. Use diffs only as the change detector in step 2.

## 6. Sources

- **Benchmarks:**
  - [OSWorld](https://arxiv.org/html/2404.07972)
  - [WebArena README](https://github.com/web-arena-x/webarena)
  - [VisualWebArena reset](https://github.com/web-arena-x/visualwebarena/blob/main/environment_docker/README.md)
  - [BrowserGym VWA task](https://raw.githubusercontent.com/ServiceNow/BrowserGym/main/browsergym/visualwebarena/src/browsergym/visualwebarena/task.py)
  - [AppWorld](https://arxiv.org/html/2407.18901)
  - [τ-bench `base.py`](https://raw.githubusercontent.com/sierra-research/tau-bench/main/tau_bench/envs/base.py)
  - [τ²-bench evaluator](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/evaluator/evaluator_env.py)
  - [τ²-bench environment](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/environment/environment.py)
  - [TheAgentCompany](https://arxiv.org/html/2412.14161v3) and its [repo](https://github.com/TheAgentCompany/TheAgentCompany)
  - [SWE-bench harness](https://www.swebench.com/SWE-bench/reference/harness/) and [`run_evaluation.py`](https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/swebench/harness/run_evaluation.py)
  - [SWE-Gym](https://arxiv.org/abs/2412.21139)
  - [SWE-smith](https://john-b-yang.github.io/swe-smith)
  - [Harbor](https://github.com/harbor-framework/harbor/blob/26106c6d9c66848a1440faf5724d336affac52aa/docs/content/docs/tasks/task-difference.mdx)
  - [Terminal-Bench 2.0](https://arxiv.org/abs/2601.11868)
  - [InterCode](https://raw.githubusercontent.com/princeton-nlp/intercode/master/intercode/envs/bash/bash_env.py)
  - [AgentBench OS](https://raw.githubusercontent.com/THUDM/AgentBench/main/src/server/tasks/os_interaction/task.py)
  - [Cybench](https://crfm.stanford.edu/2024/08/19/cybench.html)
  - [AndroidWorld](https://arxiv.org/abs/2405.14573)
  - [WebServ](https://neurips.cc/virtual/2025/128012): resets web servers with ~5× lower launch latency; its baseline isn't stated
- **Eval infrastructure:**
  - [METR task standard](https://github.com/METR/task-standard/blob/main/STANDARD.md)
  - [task-protected-scoring](https://github.com/METR/task-protected-scoring)
  - [RE-Bench](https://arxiv.org/html/2411.15114v2)
  - [Inspect sandboxing](https://inspect.aisi.org.uk/sandboxing.html) and [checkpointing](https://inspect.aisi.org.uk/checkpointing.html)
  - [Inspect Proxmox sandbox](https://github.com/UKGovernmentBEIS/inspect_proxmox_sandbox)
  - [Agentic Benchmark Checklist](https://arxiv.org/html/2507.02825v3)
- **Step-level evaluation:**
  - [AgentBoard](https://arxiv.org/html/2401.13178)
  - [WebCanvas](https://arxiv.org/abs/2406.12373)
  - [CRAB](https://arxiv.org/abs/2407.01511)
  - [ToolSandbox](https://arxiv.org/html/2408.04682)
  - [AgentPRM](https://arxiv.org/html/2502.10325v1)
  - [GiGPO](https://arxiv.org/abs/2505.10978)
- **Branching:**
  - [Koh et al. tree search](https://arxiv.org/html/2407.01476)
  - [WebOperator](https://arxiv.org/abs/2512.12692)
  - [SWE-Search](https://arxiv.org/html/2410.20285)
  - [SPROUT paper](https://arxiv.org/abs/2610.14405) and [wiki](https://github.com/RISE-X-Lab/SPROUT/wiki)
  - [Tree-GRPO](https://arxiv.org/abs/2509.21240)
  - [rLLM DeepSWE](https://rllm-project.readthedocs.io/en/latest/examples/swe/)
- **Snapshot tooling:**
  - [Morph Infinibranch](https://cloud.morph.so/docs/developers)
  - [Modal snapshots](https://modal.com/docs/guide/sandbox-snapshots)
  - [`docker commit`](https://docs.docker.com/reference/cli/docker/container/commit/)
  - [`docker checkpoint`](https://docs.docker.com/reference/cli/docker/checkpoint/)
  - [`pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html)
  - E2B fork: see [sandbox-forking-options.md](sandbox-forking-options.md)
