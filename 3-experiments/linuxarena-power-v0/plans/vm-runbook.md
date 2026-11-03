# Running on the cloud machine

*Written 2026-11-03. How to set up the AWS machine and run the experiment on it, with the exact commands. The machine itself, what it costs and what to watch are in [aws-machine.md](aws-machine.md). The scripts are in `../harness/vm/`, listed at the end.*

**In short.** The machine gets the same folders as WSL, `/root/power-v0`, so everything runs as it does now.
- **Code** goes over as a git bundle of the current branch.
- **Raw data** goes over SSH.
- **Nothing secret** passes through GitHub.
- **Results** come back to the laptop, where they're scanned and committed.

**Not yet tried on a real machine.** So far the scripts have only been checked for syntax and against WSL's values.

## What goes where

| On the machine | What it is | Where it comes from |
| --- | --- | --- |
| `/root/Power-Seeking/` | The repository | A git bundle from the laptop (`copy.sh to`): committed files only, with the full history |
| `/root/power-v0/` | The same layout as WSL: `data/`, `queue/`, `config/`, `trajectory/`, `harness/` (the synced copy) and `src/control-tower/` | The raw data from WSL over SSH. `setup.sh` makes the rest |

**Why a bundle, not a clone from GitHub.** The repository is private, so a clone would need a key on the machine with access to your GitHub. A bundle needs nothing.

## First set-up

1. **Arya:**
   - launch the machine (see [aws-machine.md](aws-machine.md));
   - save `Power1.pem` in `C:\Users\arya\.ssh\`;
   - send the public IPv4 address.
2. **Claude, in WSL:** put the key where SSH accepts it, then copy everything over. The 1.4 GB of raw data takes a while on the home connection.

   ```bash
   install -D -m 400 /mnt/c/Users/arya/.ssh/Power1.pem ~/.ssh/Power1.pem
   ```

   ```bash
   bash /mnt/c/Users/arya/OneDrive/Desktop/AI-Safety/Projects/Power-Seeking/3-experiments/linuxarena-power-v0/harness/vm/copy.sh to <address>
   ```

3. **Claude, set up the machine:**

   ```bash
   ssh -i ~/.ssh/Power1.pem ubuntu@<address> sudo bash /root/Power-Seeking/3-experiments/linuxarena-power-v0/harness/vm/setup.sh
   ```

   It's safe to rerun, and it ends with a list of checks. It:
   - installs Docker and the other packages, and prints their versions next to WSL's;
   - writes Docker's settings and raises the kernel's inotify limits;
   - writes `ct.env`, the same as WSL's, and sets the queue cap to 16;
   - clones Control Tower at `699d5ca` and installs its exact packages, then compares them with WSL's list;
   - clones `model_registry` at `v1.0.1`;
   - downloads the 7 images by digest, about 13 GB, and adds the two second names;
   - syncs the harness.

   **If installing Control Tower fails:** the pinned inspect-ai 0.3.171 is no longer listed on PyPI, though its file still downloads. Run `copy.sh venv <address>` in WSL, which copies WSL's environment (about 1 GB), and rerun `setup.sh`.
4. **Claude, checks with no model calls.** Two no-work batches, compared with WSL's. On the machine, as root (`sudo -i`):

   ```bash
   cd ~/power-v0/harness
   PURPOSE="Cloud machine check: no-work runs from the untouched machine, to compare with nowork-v2-S0" \
     bash launch.sh vmcheck-nowork tasks/v0_tasks.txt 6 -p solver_user=dev -p solve=false
   PURPOSE="Cloud machine check: replay traj3-power, then no-work runs, to compare with nowork-v3-afterB" \
     bash launch.sh vmcheck-nowork-afterB tasks/v0_tasks.txt 6 -p solver_user=dev -p solve=false \
       -p traj=/root/power-v0/trajectory/traj3-power.eval -p traj_user=dev -p traj_cmd_bug=false
   V=/root/Power-Seeking/3-experiments/linuxarena-power-v0/harness/vm
   python3 -I $V/compare_runs.py nowork-v2-S0 vmcheck-nowork
   python3 -I $V/compare_runs.py nowork-v3-afterB vmcheck-nowork-afterB
   ```

   - **Every task should say "same."** Any difference gets looked into before any paid run.
   - **These checks never enter the power numbers.** They're no-work runs, not per-step scores, and `power_horizons.py` only uses no-work runs it's named on its command line.
5. **Claude, the queue cap.** Watch `uptime` and `free -g` during the checks and the first batch. Raise `~/power-v0/queue/max_envs` in steps while the load stays under about 128 and memory has room ([aws-machine.md](aws-machine.md), "How many environments at once").
6. **Paid runs** only with Arya's go-ahead, through the queue Arya starts ("Each session", step 3).

## Each session

1. **Arya:** start the machine in the EC2 console and send its new address.
2. **Claude, in WSL:** if the code changed, commit it on the laptop, then run `copy.sh to <address>`.
   - It updates the machine's repository, refreshes the synced harness, and copies any new raw data.
   - Unchanged files are skipped.
3. **Arya: the key and the queue.** Use a tmux session, so the queue survives the connection closing. From WSL:

   ```bash
   ssh -i ~/.ssh/Power1.pem ubuntu@<address>
   ```

   Then, on the machine:

   ```bash
   sudo -i
   tmux new -s queue
   read -rs OPENROUTER_API_KEY && export OPENROUTER_API_KEY
   ```

   At the third line, paste the key and press Enter: nothing is shown. Then set the deadline (Chicago time: nothing starts after it) and start the queue:

   ```bash
   echo "2026-11-04 08:00" > ~/power-v0/queue/deadline
   cd ~/power-v0/harness && python3 night_queue.py; shutdown -h +10
   ```

   Then press Ctrl-b, then d, to leave tmux with the queue running.
   - **The key lives only in that shell** and the jobs it starts. It's never written to disk, and it's gone when the machine stops.
   - **Paid runs can only start from that queue.** Claude's own connections don't have the key, so they can run only free jobs, which get a placeholder key.
   - **`shutdown -h +10` stops the machine ten minutes after the queue exits,** at the deadline or when `queue/stop` is touched. The shutdown behaviour is Stop, so the disk is kept. Cancel it with `shutdown -c`.
4. **Claude: queue jobs as on WSL.** Append lines to `~/power-v0/queue/jobs.tsv`. `make_hz_jobs.py` and the other scripts work unchanged.
5. **Claude, bring the results back, in WSL:**

   ```bash
   bash /mnt/c/Users/arya/OneDrive/Desktop/AI-Safety/Projects/Power-Seeking/3-experiments/linuxarena-power-v0/harness/vm/copy.sh back <address>
   ```

   - **What it copies:** the readable records into `runs/` here, and the raw data into WSL's `/root/power-v0`.
   - **Then, on the laptop:** the secret scan of the new records, a dashboard rebuild, a commit and a push.
   - **Run batches on one machine at a time.** `copy.sh back` replaces `runs/runs-registry.md` with the machine's, which lists only the batches the machine knows about.
6. **Stop the machine:** in the console, or let the queue's `shutdown` do it. Stop it, never terminate it.

## What differs from WSL

| | WSL | The machine |
| --- | --- | --- |
| Docker settings | MTU 1350 and one download at a time, fixes for WSL's network and the home connection | Neither. Instead, about 1,000 network ranges in `10.200.0.0/14` (Docker's own allow about 30), and the containerd image store set explicitly |
| Kernel | Defaults | inotify limits raised for many environments at once |
| Queue cap | 7–10 environments | 16 to start, then raised |
| OpenRouter key | Read from the Windows variable for each command | Typed by Arya into the queue's shell |
| Queue deadline | Set in `night_queue.py` | `queue/deadline`, which works in WSL too |

**The same on both:**
- Ubuntu 26.04 and the Docker 29.1.3 packages (`setup.sh` prints the versions);
- Control Tower `699d5ca` and its exact packages (checked against `ct-packages.txt`);
- `model_registry` `v1.0.1` and the same image digests;
- the same folders, so paths inside the raw data stay valid.

## Files

| File | What it does |
| --- | --- |
| `../harness/vm/setup.sh` | Sets the machine up, as above. Run on the machine as root |
| `../harness/vm/copy.sh` | Runs in WSL. `to` copies the code, uv and the raw data over; `venv` copies WSL's Control Tower environment; `back` brings the records and raw data back |
| `../harness/vm/compare_runs.py` | Compares two batches task by task (check names only, never scorer output) |
| `../harness/vm/ct-packages.txt` | WSL's Control Tower packages, exactly. `setup.sh` compares the machine's with it |
