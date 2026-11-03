# Snapshot and fork tools for per-step scoring

*Written 2026-11-02 by a research subagent at Arya's request: "this is a much simpler problem than we've made it, and others have solved it before." Nothing was launched and no model was called. Tags: **[docs]** official documentation, **[vendor]** a provider's own claim, **[paper]** a research paper, **[code]** read in the Inspect 0.3.171, Control Tower or LinuxArena code in WSL, or our harness, **[checked]** a read-only command on this laptop today, **[inference]** my judgment. Sources I only saw in search summaries are marked in section 5. Background: [score-and-rollback-scope.md](score-and-rollback-scope.md), [sandbox-forking-options.md](sandbox-forking-options.md).*

## 1. The answer in 6 lines

1. **Fork the stack; don't roll it back.** At each scoring point: freeze the stack for a few seconds, `docker commit` the app container, and copy the Postgres volume and the stack's two buckets. Then unfreeze it and keep replaying. Start a scratch Compose project from the copies, run the real scorer there, and delete it. The original is never scored, so nothing needs restoring.
2. **Why this approach:** it's the standard local method, which agent-systems papers use as their baseline ("container commits", Xu et al. 2025 [paper]). It uses only Docker features we already run. What it loses (processes and memory) the scorer throws away anyway when it rebuilds and restarts the service. The tools that keep memory don't fit our setup: CRIU is broken on Docker 28–29, and VM forks would mean moving the stack to a cloud provider.
3. **Time per scoring point (estimate):** the original is frozen for about 5–50 s, mostly the commit, which isn't measured yet (see step 0). The scratch copy then takes about 30–60 s to start, plus the scorer (15–90 s) and about 10 s to delete. That second part can run alongside the continuing replay.
4. **Effort:** about one day. That's a fork function in the harness (~150 lines), a Compose override file, and a trimmed copy of the S3 setup script, followed by the 28-pair validation already designed in the scope.
5. **A surprise from checking the laptop [checked]:** Docker 29.1.3 here uses the **containerd image store**, not overlay2, and the app image is 9.4 GB. Commits on that store can take time that grows with the image's size, not the size of the change. So time one commit before building anything.
6. **The answer others use at scale:** a whole-VM fork (E2B, Daytona, Morph) that keeps memory and takes under a second to a few seconds. But our whole Compose stack would have to run inside one VM, and none of the Inspect providers exposes a fork.

## 2. The options compared

| Option | What it captures | Speed | Works on our setup? | Setup effort | Known pitfalls | Sources |
| --- | --- | --- | --- | --- | --- | --- |
| **Fork by copying:** `docker commit` + copy of the Postgres volume + copy of the buckets | The app's files (code, binary, Go caches, SQLite file), the whole Postgres cluster, the bucket objects. Not processes, memory, `/etc/hosts` or firewall rules | Commit plus restart took 0.4 s with no changed files and 5–7 s with 1–2 GB changed (Docker 27) [paper]. On the containerd store, a 1 KB change took 39 s on a 10 GB image [vendor blog]. Volume and bucket copies take about 1–5 s for our ~50 MB + 24 MB [inference] | **Yes** | ~1 day | Commits leave out volumes [docs]. Commit speed on the containerd store. Postgres must be frozen while it's copied. IP addresses and Docker-managed files change | [commit](https://github.com/docker/cli/blob/master/docs/reference/commandline/container_commit.md), [Xu](https://arxiv.org/html/2510.05556v1), [Sealos](https://sealos.io/blog/sealos-devbox-commit-performance-optimization/) |
| `docker checkpoint` (CRIU) | One container's memory and processes | 0.06 s with no memory changed, about 1.4 s for 2 GB [paper] | **No.** CRIU's own test script says "Docker 28.x and 29.x has a known regression that breaks" checkpoint and restore ([moby#50750](https://github.com/moby/moby/issues/50750)). We run 29.1.3 with experimental mode off and CRIU not installed [checked] | Hours, and may not work | One container at a time. CRIU's option for keeping open TCP connections, here the app's connections to Postgres, "can't be set through Docker's CLI" [docs]. WSL2 users report other CRIU failures (search only) | [CRIU CI](https://github.com/checkpoint-restore/criu/blob/criu-dev/scripts/ci/docker-test.sh), [criu.org/Docker](https://criu.org/Docker) |
| Podman checkpoint and restore | Memory, processes and the container's files | 0.8 s with nothing changed [paper] | **No**, unless Podman replaced Docker under Inspect and Control Tower | Days | One container at a time. Restoring into a pod needs the same shared namespaces. The TCP option must be used both when saving and when restoring (search only) | [criu.org/Docker](https://criu.org/Docker) (recommends Podman) |
| gVisor (`runsc`) checkpoint | One container's memory | n/a | **No.** It isn't installed, and "Docker currently expects the container which created the checkpoint to be the same container used to restore" [docs] | Hours | Apps "must reconnect after restore" [docs] | [gVisor](https://gvisor.dev/docs/user_guide/checkpoint_restore/) |
| Disk snapshots of Docker's data folder (btrfs, LVM thin, ZFS, XFS copy-on-write copies) | Everything on that disk: layers and volumes | Near-instant | **Not as set up.** `/var/lib/docker` is on ext4, which can't make copy-on-write copies. The WSL kernel has btrfs and LVM thin as modules and XFS built in, but no ZFS [checked] | Half a day, plus re-pulling the images | Docker's data would have to move to a new disk image. Every Postgres file must be in one simultaneous snapshot [docs] | [Postgres](https://www.postgresql.org/docs/16/backup-file.html) |
| Postgres: copy the volume while frozen | The whole cluster: both databases and the roles | Under 1 s for tens of MB [inference] | **Yes** | Minutes | A plain copy of a running server isn't usable. A frozen snapshot is, and the server "will replay the WAL log" when it starts [docs]. `docker pause` freezes the processes with the freezer cgroup [docs]; that this equals a frozen snapshot is my inference | [Postgres](https://www.postgresql.org/docs/16/backup-file.html), [pause](https://github.com/docker/cli/blob/master/docs/reference/commandline/container_pause.md) |
| Postgres: `pg_dump` and restore, or `CREATE DATABASE … TEMPLATE` | Databases (roles only with `pg_dumpall`) | 1–4 s (scope's estimate) | Partly | Hours | The scratch copy's empty Postgres would first run `init.sql`. A template copy works only inside one server, with "no other sessions" connected to the source [docs]. Testcontainers uses templates for in-server snapshots (search only) | [templates](https://www.postgresql.org/docs/16/manage-ag-templatedbs.html) |
| MinIO: copy the buckets (`mc mirror` or `mc cp --recursive`) | Objects | Seconds for 24 MB [inference] | **Yes** | Minutes | Bucket names come from the Compose project name (`models-<project>`) [code]. Turning on versioning would allow `mc cp --rewind <time>` [docs], but it isn't needed | [mc cp](https://docs.min.io/community/minio-object-store/reference/minio-mc/mc-cp.html) |
| Inspect checkpointing (added in 0.3.241, Jun 2026) | The agent's state and chosen sandbox folders; "does not save arbitrary in-memory process state" [docs] | n/a | **No.** It restores into a fresh container only when a sample is retried, with no fork. Nothing up to 0.3.281 (Oct 15) adds a fork [docs] | n/a | We run 0.3.171 | [checkpointing](https://inspect.aisi.org.uk/checkpointing.html), [changelog](https://inspect.aisi.org.uk/CHANGELOG.html) |
| E2B fork | Files, "running processes, loaded variables, and data" [docs] | Pausing takes about 4 s per GiB of RAM and resuming about 1 s; up to 20 forks per call [docs] | **Cloud only.** Compose runs inside via a Docker template. An Inspect provider runs Compose with two or more services as Docker inside one VM, but exposes no fork [docs] | Weeks (earlier plan) | Pausing "disconnects the original's active connections" [docs]. The shared MinIO and the internet simulator would have to move inside the VM | [fork](https://docs.e2b.dev/sandbox/fork), [persistence](https://docs.e2b.dev/sandbox/persistence), [provider](https://github.com/meridianlabs-ai/inspect_sandboxes/blob/main/docs/e2b.qmd) |
| Daytona fork and memory snapshots | Files and memory, for VM sandboxes only [docs] | Not stated | **Cloud only.** Its Inspect provider also runs Compose as Docker inside one VM, but says "Daytona does not support snapshotting a running sandbox" [docs] | Weeks | No volumes. Each sample starts a fresh Docker with no image cache [docs] | [scale](https://www.daytona.io/docs/en/scale), [persistence](https://www.daytona.io/docs/en/persistence), [provider](https://github.com/meridianlabs-ai/inspect_sandboxes/blob/main/docs/daytona.qmd) |
| Morph Cloud "Infinibranch" | "the entire system state, including running processes" [vendor] | "under 250ms" [vendor]; I found no independent benchmark | Cloud only; I found no Inspect provider | Weeks | Unknown | [Morph](https://cloud.morph.so/docs/developers) |
| Modal snapshots | Files (mounted volumes excluded). Memory snapshots are experimental, expire after 7 days and end the sandbox [docs] | Not stated | Cloud only. Docker needs Modal's VM runtime, and its Inspect provider allows only one service [docs] | Weeks | Open TCP connections close at a memory snapshot [docs] | [snapshots](https://modal.com/docs/guide/sandbox-snapshots), [Docker](https://modal.com/docs/guide/docker-in-sandboxes) |
| CodeSandbox (now Together), Runloop | CodeSandbox: memory, cloned from a snapshot in about 3 s, but that SDK is deprecated. Runloop: "Only disk state" [docs] | Seconds | Cloud only | Weeks | n/a | [Together](https://docs.together.ai/docs/together-code-sandbox-legacy), [Runloop](https://docs.runloop.ai/docs/devboxes/lifecycle) |
| Firecracker microVMs, self-hosted | Memory and device state; "block device files… have to be handled by the user" [docs] | Fast restores, with memory loaded on demand [docs] | Possible: `/dev/kvm` exists in WSL [checked]. But the stack would have to be rebuilt inside a microVM | Weeks | Network "not guaranteed" after resume, and clones repeat the same random values [docs] | [Firecracker](https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md) |
| Kubernetes (GKE Pod Snapshots via agent-sandbox) | Memory and files | n/a | **No.** It needs "GKE Autopilot cluster with a gVisor node pool" [docs] | n/a | n/a | [agent-sandbox](https://agent-sandbox.sigs.k8s.io/docs/sandbox/snapshots/) |

**What the research says.** Xu et al. find that generic tools like CRIU and container commits "crumble entirely in real deployments" where agents share files, sockets and cloud services [paper]. Our case is easier, because the scorer restarts the service anyway. DeltaBox reports 14 ms saves and 5 ms rollbacks, but it's a research system, not a tool ([arXiv 2605.22781](https://arxiv.org/abs/2605.22781)) [paper].

## 3. The recommended approach, step by step

**Names used below.** P is the job's Compose project (for example `inspect-power-v0-hz--ibbhvpy`). F is the scratch copy's project. Name F in Inspect's pattern, `inspect-<name>-i<6 random characters>`, so Inspect's cleanup tools recognise it [code].

**Step 0: time one commit first.** This takes about 30 minutes: one stack left over after a solver run, no model calls.
- Run `time docker commit` on the app container.
- **If it takes more than about 30 s,** there are two ways round it:
  - **Switch Docker back to the classic overlay2 driver.** Its commit packs only the folder of changed files ([moby code](https://github.com/moby/moby/blob/master/daemon/graphdriver/overlay2/overlay.go)). On the containerd store, commit hands the work to containerd's diff service and writes a gzip layer ([moby code](https://github.com/moby/moby/blob/master/daemon/containerd/image_commit.go)). The cost of switching: existing images "become hidden" [docs], so the 9.4 GB and 2.5 GB images must be pulled or loaded again.
  - **Pack the container's changed-files folder directly.** Untested [inference].

**One-time setup.**
1. **`harness/fork/fork-override.yml`,** layered on the environment's `compose.yml`:
   ```yaml
   services:
     default:  { image: "power-fork/app:${FORK}" }       # the committed image
     postgres: { volumes: ["pgfork:/var/lib/postgresql/data"] }
     s3-init:  { command: ["/fork/s3-init-fork.sh"], volumes: ["/root/power-v0/harness/fork:/fork:ro"] }
   volumes:
     pgfork: { external: true, name: "${FORK}-pg" }
   ```
   - Don't set the image tag through `ENV_IMAGE_TAG_MODEL_REGISTRY`: the s3-init image uses the same variable [code].
   - Because the copied data folder isn't empty, Postgres skips `initdb` and `init.sql` [inference, standard behaviour of the image].
   - Inspect's `ComposeProject` takes a single file [code], so flatten the two files into one with `docker compose -f compose.yml -f fork-override.yml config > F.yml`.
2. **`s3-init-fork.sh`:** LinuxArena's `init/s3/init.sh` with two parts removed. The first is the starting-data upload. The second is the `sync_checksums.py` call, which writes into Postgres [code]. Everything else stays. That includes connecting the shared MinIO to `F_default` as `minio-backend`, which the S3 proxy needs before it starts [code]. The proxy strips the `Authorization` header and the buckets are public, so a copied bucket needs no new credentials [code].

**At each scoring point H** (run from the WSL side, as `_setup_dev` already does):
```bash
# a. note the process list, and whether the running service's binary equals the file on disk
#    (sha256 of /proc/<pid>/exe against the file), as in the scope's state summary
docker compose -p "$P" pause                       # freezes app, postgres and proxy
docker commit --pause=false "$P-default-1" "power-fork/app:$F"   # the docs also list --no-pause
PGV=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$P-postgres-1")
docker volume create "$F-pg" && cp -a "/var/lib/docker/volumes/$PGV/_data/." "/var/lib/docker/volumes/$F-pg/_data/"
mc mb local/models-$F local/backups-$F && mc mirror local/models-$P local/models-$F && mc mirror local/backups-$P local/backups-$F
docker compose -p "$P" unpause                     # the replay continues from here
docker compose -p "$F" -f F.yml up -d --no-build --wait default
```
- **Where `mc` comes from:** run it from the s3-init image on the `minio-shared` network, with the MinIO admin account that the environment's scorer helpers name. Never print that account.
- **Bucket names:** the s3-init script lowercases the project name and replaces odd characters [code]. Use the same cleaning for P and F.

**Then, in the job's Python:**
1. **Reconnect the internet simulator.** Call Control Tower's `setup_internet_simulator(F, …)` with the sample's settings, as `LBDockerSandboxEnvironment._connect_internet_simulator` does [code]. It rewrites `/etc/hosts`. A commit never keeps `/etc/hosts`, because Docker regenerates it at every start (old Docker docs, search only).
2. **Re-add `dev`'s internet block.** The rule lives in the container's network namespace, not in a file (`power_v0.py`, lines 347–351) [code], so a commit doesn't carry it.
3. **Restore the old binary if needed.** If at H the running binary differed from the file on disk (the agent built but never restarted), put the running one in place in F and restart the service.
4. **Point Inspect at F and score.** This mirrors how Inspect's own `sample_init` builds environments [code]; calling it from inside the policy is untested [inference]:
   ```python
   from inspect_ai.util._sandbox.context import sandbox_environments_context_var as envs_var
   from inspect_ai.util._sandbox.docker.util import ComposeProject
   orig = sandbox()
   proj = await ComposeProject.create(F, config="F.yml", sample_id=..., epoch=..., env=orig._project.env)
   token = envs_var.set({"default": type(orig)("default", proj, orig._working_dir)})
   try:
       score = await linux_scorer(600)(state, state.target)
   finally:
       envs_var.reset(token)
   ```
5. **Delete everything.** Call `disconnect_and_cleanup_shared_containers(F)` (Control Tower), then `docker compose -p F down -v`. Remove the volume, `mc rb --force` both buckets, and remove the image.

**Running forks in parallel.** Build it serially first. Later, run steps 1–5 as a background task so the replay goes on in the meantime. Context variables are per task in Python's asyncio, so the swap can't leak into the replay [inference]. Cap it at 1–2 forks in flight per job: each fork is another full stack, and overload is what broke the scorers' short time limits.

**What's lost, and whether it matters:**
- **Processes and memory.** The scratch copy's entrypoint restarts the service from the file on disk [code]. The backup, dashboard and refactor scorers rebuild and restart it anyway. For the favourites and bug-fix scorers, it matters only if:
  - the agent built without restarting, which is handled above;
  - or the agent left background processes running. Compare the process lists and flag those points.
- **`/etc/hosts`, `/etc/hostname`, `/etc/resolv.conf` and firewall rules.** All are re-created above.
- **IP addresses.** The copy gets new subnets. Names like `postgres` and `s3` resolve as before, but an address the agent hard-coded would break [inference]. Search the changed files for the original networks' addresses.
- **Gained:** the original stack never meets a scorer. So the scope's leftover problems can't carry into later points: the test-database row, the Go test cache, root's module downloads, and processes killed by `pkill`.

**Checks before trusting it:**
1. **Is the copy faithful?** At a few points, compare the original with the copy just after it starts:
   - a hash of `/app`;
   - `pg_dump` of both databases;
   - bucket listings with ETags (the hashes S3 stores for each object).

   Only the expected differences above are allowed.
2. **Postgres recovery:** the copy's Postgres log should show WAL recovery, then "ready".
3. **The scope's 28 (run, H) pairs** give identical check lists.
4. **Each job's end score** equals its run's own score. That also shows the forks left the original untouched.
5. **Timing:** commit time, and `docker compose exec … true` latency at the chosen parallel cap.

## 4. Options worth it only at larger scale

- **Fork during the live run,** with the same commands at each H. Replays are then needed only for runs already done. It costs a few seconds per point inside a paid run.
- **Faster copies.** Put Docker's data folder on an XFS or btrfs disk image, both of which this kernel supports [checked]. Volume copies then become copy-on-write copies. With Postgres 18, `file_copy_method = clone` makes `CREATE DATABASE … STRATEGY FILE_COPY` near-instant: about 200 ms for 6 GB in one blog (search only). It doesn't work on ext4. We run Postgres 16.
- **Whole-VM forks in the cloud,** for the 30-task set. E2B is the best documented; Daytona and Morph are the alternatives. Each needs:
  - the shared MinIO and the internet simulator moved inside the VM;
  - an Inspect provider that exposes fork, which none does today;
  - Control Tower changes.
- **Gap search.** Each point is cheap once forking works, so scoring every turn in one pass becomes affordable, and gap search becomes optional rather than necessary [inference].

## 5. Sources

Opened and read:
- Docker: [commit](https://github.com/docker/cli/blob/master/docs/reference/commandline/container_commit.md), [pause](https://github.com/docker/cli/blob/master/docs/reference/commandline/container_pause.md), [containerd image store](https://github.com/docker/docs/blob/main/content/manuals/engine/storage/containerd.md), [Engine v29 blog](https://www.docker.com/blog/docker-engine-version-29/), and moby's [overlay2 driver](https://github.com/moby/moby/blob/master/daemon/graphdriver/overlay2/overlay.go) and [containerd commit](https://github.com/moby/moby/blob/master/daemon/containerd/image_commit.go) code
- [Sealos: commit time on containerd](https://sealos.io/blog/sealos-devbox-commit-performance-optimization/)
- CRIU: [its Docker test script](https://github.com/checkpoint-restore/criu/blob/criu-dev/scripts/ci/docker-test.sh), [criu.org/Docker](https://criu.org/Docker), and [gVisor checkpoint and restore](https://gvisor.dev/docs/user_guide/checkpoint_restore/)
- PostgreSQL 16: [file-system backup](https://www.postgresql.org/docs/16/backup-file.html), [template databases](https://www.postgresql.org/docs/16/manage-ag-templatedbs.html)
- MinIO: [mc cp](https://docs.min.io/community/minio-object-store/reference/minio-mc/mc-cp.html)
- Papers: Xu, Zhou, Wu, Kaffes, [Toward Systems Foundations for Agentic Exploration](https://arxiv.org/html/2510.05556v1) (2025); Dong et al., [DeltaBox](https://arxiv.org/abs/2605.22781) (2026)
- Inspect: [checkpointing](https://inspect.aisi.org.uk/checkpointing.html), [changelog](https://inspect.aisi.org.uk/CHANGELOG.html), [sandboxing](https://inspect.aisi.org.uk/sandboxing.html), and [inspect_sandboxes](https://github.com/meridianlabs-ai/inspect_sandboxes) with its provider pages for [E2B](https://github.com/meridianlabs-ai/inspect_sandboxes/blob/main/docs/e2b.qmd), [Daytona](https://github.com/meridianlabs-ai/inspect_sandboxes/blob/main/docs/daytona.qmd) and [Modal](https://github.com/meridianlabs-ai/inspect_sandboxes/blob/main/docs/modal.qmd)
- Cloud providers:
  - E2B: [fork](https://docs.e2b.dev/sandbox/fork), [persistence](https://docs.e2b.dev/sandbox/persistence), [Docker template](https://docs.e2b.dev/template/examples/docker.md)
  - Daytona: [scale](https://www.daytona.io/docs/en/scale), [persistence](https://www.daytona.io/docs/en/persistence)
  - [Morph](https://cloud.morph.so/docs/developers)
  - Modal: [snapshots](https://modal.com/docs/guide/sandbox-snapshots), [Docker](https://modal.com/docs/guide/docker-in-sandboxes)
  - [Together/CodeSandbox](https://docs.together.ai/docs/together-code-sandbox-legacy)
  - [Runloop](https://docs.runloop.ai/docs/devboxes/lifecycle)
- Firecracker and Kubernetes: [Firecracker snapshots](https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md), [agent-sandbox snapshots](https://agent-sandbox.sigs.k8s.io/docs/sandbox/snapshots/)

Seen only in search summaries, not opened:
- Podman: [criu.org/Podman](https://www.criu.org/Podman) (the fetch failed), the [podman restore man page](https://manpages.ubuntu.com/manpages/noble/man1/docker-container-restore.1.html), and [Red Hat on Podman checkpointing a SQL Server container](https://www.redhat.com/en/blog/podman-checkpoint-restore-and-sql-server-2019)
- CRIU failures on WSL2: [criu#2391](https://www.github.com/checkpoint-restore/criu/issues/2391) and related issues
- [Old Docker docs text](https://git.coopcloud.tech/p4u1/docker-cli/commit/09240bd7680b903f691bfa4e71e9ef49bd1638c0) saying edits to `/etc/hosts` aren't saved by commit
- Postgres 18 cloning: [Vonng](https://blog.vonng.com/en/pg/pg-clone/), [thebuild.com](https://thebuild.com/blog/all-your-gucs-in-a-row-file_copy_method/)
- [Testcontainers Postgres snapshots](https://node.testcontainers.org/modules/postgresql/)

Checked on this laptop, read-only:
- **Software:** Docker 29.1.3, containerd 2.2.2, Docker Compose 2.40.3.
- **Docker:** the containerd store (`io.containerd.snapshotter.v1`), runc only, experimental mode off.
- **Not installed:** criu, podman, runsc.
- **Kernel:** 6.18 (WSL2), with `CONFIG_CHECKPOINT_RESTORE=y`, btrfs and LVM thin as modules, XFS built in, no ZFS.
- **Disks and devices:** `/var/lib/docker` is on ext4, and `/dev/kvm` is present.
- **Images:** the app image is 9.42 GB and the s3-init image 2.52 GB.
- **Code read in WSL:** `compose.yml`, `init/s3/init.sh` and the S3 proxy config; Control Tower's `sandbox/docker.py` and `internet_simulator/runtime.py`; Inspect's `_sandbox/context.py` and `_sandbox/docker/`.
