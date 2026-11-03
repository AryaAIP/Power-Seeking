# Sandbox forking: could it make the power measurement faster?

*Written 2026-11-02 at about 12:30 CST by a research subagent, at Arya's request after Matthew's message. Matthew wrote: "Let's not do premature optimization… but if we were to optimize the measurement of power, sandbox forking is a thing". He linked https://docs.e2b.dev/sandbox/fork and a Claude conversation (https://claude.ai/share/95e19e95-add6-4d6c-9728-b988c2f7c629). Tags: **[docs]** is linked documentation, **[ours]** is our run records, harness and the Control Tower code, and **[inference]** is the agent's judgment. Not verified further. Status: an idea for later, nothing built.*

## Why it matters

Two steps of the measurement rebuild a machine by **replaying** recorded tool calls into a fresh Docker Compose stack:
- **After runs:** each trajectory is replayed 6 times, once per future task, at 4–8 minutes each. Replays can also diverge: one did, in a restart race that's now fixed with a health wait.
- **Per-step scoring:** a solver run's first H turns are replayed for every horizon. That's 30–50 jobs per arm at 4–10 minutes each, the biggest machine-time cost.

## E2B forking

- **What it copies:** files, running processes, memory and loaded variables. The original is paused, snapshotted once and resumed, and each fork then diverges. Connections into the sandbox drop. [docs: [fork](https://docs.e2b.dev/sandbox/fork)]
- **Speed:** no figure for forks. Pausing takes about 4 s per GiB of RAM, and resuming about 1 s. [docs: [persistence](https://docs.e2b.dev/sandbox/persistence)]
- **Limits:**
  - 20 forks per SDK call, or 100 through the [API](https://docs.e2b.dev/api-reference/sandboxes/fork-sandbox);
  - forks count against the concurrency limit;
  - sandboxes max out at 8 vCPU and 8 GiB. [docs]
- **Docker:** a [template example](https://docs.e2b.dev/template/examples/docker.md) runs Docker Compose inside a sandbox [docs]. Containers inside should survive a fork, since the whole virtual machine is snapshotted. [inference]
- **Pricing:**
  - Hobby: free, $100 credit, 20 concurrent sandboxes, 1-hour sessions.
  - Pro: $150/month, 100 concurrent, 24-hour sessions. [docs: [pricing](https://e2b.dev/pricing)]
  - About $0.33/hour at 4 vCPU and 8 GiB. [inference]
- **Self-hosting:** possible. It's open source (Apache-2.0), deployed with Terraform or on one Linux host with KVM. [[infra](https://github.com/e2b-dev/infra)]

## What Matthew's linked conversation proposes

- **Three options:**
  - `docker commit`, then start N copies (files only);
  - CRIU (fragile with open sockets);
  - whole-machine fork (E2B, Morph, Modal).
- **Its warning:** all forks start with the same random-number state.
- **Its advice:** commit if the services can be restarted; fork the whole machine if live processes matter.
- **Inspect can't fork partway through a sample** ([docs](https://inspect.aisi.org.uk/sandboxing.html)). Inspect's [checkpointing](https://inspect.aisi.org.uk/checkpointing.html) only restores files when the same sample is retried, and our version (0.3.171) doesn't have it. Control Tower has nothing either. [ours]

## Time it could save, if we used E2B [inference]

- **After runs:** forking the live trajectory 6 ways replaces 6 replays. That saves 24–48 machine-minutes per trajectory, and replays can no longer diverge.
- **Per-step scoring:** a fork taken at each H only needs the scorer, about 1–2 minutes. 30–50 jobs per arm drop from 2–8 h to about 0.5–1.7 h.
- **The catch:** Inspect has no E2B provider. One would need writing, with Compose inside the VM and forks partway through a run, and Control Tower would need adapting. Weeks of work.

## Options with the local Docker setup

| Option | What it captures | Notes |
| --- | --- | --- |
| CRIU / [`docker checkpoint`](https://docs.docker.com/reference/cli/docker/checkpoint/) | One container's memory and processes | Not installed, and Docker's experimental mode is off [ours]. Works one container at a time, so links between the app, Postgres and MinIO would break [inference]. Not worth it |
| `docker commit` plus copying data | The app container's files | The compose file takes the app image tag from `ENV_IMAGE_TAG_MODEL_REGISTRY`, so a committed image can be swapped in. Postgres data is in an unnamed volume that commit doesn't capture, and MinIO is shared, with buckets named per project, so both need copying [ours] |
| Postgres dump and restore | The database | Seconds; our existing export takes about 10 s. Use `pg_dumpall` to keep roles. Template databases don't help, since they only copy within one server [inference] |

**Risks of restoring files instead of replaying** [inference]:
- **Background processes are lost.** Any process a trajectory left running doesn't come across. B, which is told to keep what it set up, is the likeliest to leave some. Our snapshot lists processes, so this is checkable.
- **The service starts fresh.** A restart resets its in-process backup workers.
- **Builds can change what runs.** After a rebuild with no restart, the original machine still runs the old binary, while the restored stack runs the new one.

## Recommendation [inference]

- **The one change worth the most:** score each horizon from a saved state instead of a replay.
  - During each live run, at each H, save the app container's changed files (`docker diff` then tar, keeping owners, setuid bits and deletions), a `pg_dumpall` and the two buckets.
  - To score, restore them into a fresh stack and run the scorer.
  - The scorer rebuilds and restarts the service anyway, so losing in-memory state barely matters there.
  - Jobs drop to about 3–4 minutes. After-arm jobs, which also replay the trajectory first, save about two-thirds.
- **Now:** at most, start saving those states during runs. It's cheap and changes no measurement. Before switching, score about 4 (run, H) pairs both ways and compare them with `compare_snapshots.py`.
- **Later:** restore instead of replaying for after runs whose trajectory left no running processes. Consider E2B if we scale up to the 30-task set.
- **Not worth it:** CRIU, template databases, or moving to E2B now.
