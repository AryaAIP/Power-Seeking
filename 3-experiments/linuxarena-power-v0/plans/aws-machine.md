# The AWS machine

*Written 2026-11-03, while launching it. What we're running on, what it costs, and what to watch. Prices are AWS's list prices for US East (N. Virginia), so check the region in the console's top-right corner.*

## The machine

| | |
| --- | --- |
| Instance type | `c7a.32xlarge` (4th-generation AMD EPYC) |
| Cores | 128 vCPUs, each a full physical core (one thread per core). The CPU options stay at their defaults |
| Memory | 256 GiB |
| Disk | EBS only: this type has no local disk |
| Purchasing | On-demand ("None") for now. Spot can come later for long batches of free jobs |
| Operating system | Ubuntu Server 26.04 LTS, 64-bit x86, the same as WSL (26.04.1, x86_64) |
| Key pair | `Power1` (a `.pem` file) |

For comparison, WSL has 22 cores and 31 GB of memory.

**Launch settings still to confirm:**

| Setting | Value |
| --- | --- |
| Allow SSH traffic from | My IP (the screenshot showed Anywhere) |
| HTTP, HTTPS | Unticked |
| Storage | 300 GB gp3 at the included 3,000 IOPS and 125 MB/s (see "How big a disk") |
| Shutdown behavior (Advanced details) | Stop, the default |

## What it costs

| Item | Rate | Charged |
| --- | --- | --- |
| Compute, on-demand | About $6.57 an hour | Only while running |
| Disk: 300 GB gp3 | About $24 a month ($0.08 per GB) | Always, running or stopped, until the volume is deleted |
| Public IPv4 address | $0.005 an hour | While running |
| Data out to the internet | $0.09/GB after the first 100 GB a month | Copying results back, about 1–2 GB a session |
| Model calls | OpenRouter, as now | Per run |

- **A correction:** I earlier suggested 1 TB with 10,000 IOPS and 500 MB/s, at "$80–100 a month". That would really cost about $130 a month, and it's far more than we need.
- **The credits:** $100–200 covers about 15–30 hours of on-demand compute.

## How big a disk

**300 GB is plenty, and the disk can be enlarged later.**
- **What WSL uses now:** 24 GB in all, measured on Nov 3:
  - 13.2 GB of images;
  - 5.9 GB of left-over volumes from about 28 past environments;
  - 1.4 GB of raw data.
- **At about 25 environments at once:** each running environment adds its database, its storage and its build files. Allowing generously 3 GB each makes about 75 GB.
- **Add:** the operating system (about 5 GB) and room for the raw data to grow.
- **Making it bigger:** an EBS volume can be enlarged while the machine runs, but never shrunk, so it's cheaper to start small.
- **Speed:** start at the included 3,000 IOPS and 125 MB/s. If the disk turns out to slow the runs, both can be raised while running, once every 6 hours.

## Things to watch

1. **Stop it when idle.** Forgotten, on-demand costs $158 a day.
   - Stop it, don't terminate it: stopping keeps the disk.
   - The machine can also power itself off when a batch ends. A shutdown from inside stops it, because the shutdown behavior is Stop.
2. **Set a budget alert.** Billing → Budgets, with alerts at, say, $50 and $100, so a forgotten machine sends an email.
3. **The vCPU quota.** A new account may be limited to fewer than 128 on-demand vCPUs.
   - If the launch fails with `VcpuLimitExceeded`, request 128 in Service Quotas under "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances". Approval takes minutes to a day or two.
   - Spot has its own quota, "All Standard Spot Instance Requests".
4. **The plan.** A machine this size needs AWS's Paid plan, and the credits carry over. Don't create an AWS Organization ("Create project"), which can forfeit them.
5. **The address changes.**
   - Without an Elastic IP, the public address changes every time the machine starts, so send the new one each session.
   - "My IP" lets in only your current address. If your home address changes, or you work from elsewhere, edit the SSH rule in the security group.
6. **The key file.**
   - Keep `Power1.pem` out of OneDrive, which would sync it to the cloud. `C:\Users\arya\.ssh\` is a good place.
   - It gets copied into WSL's `~/.ssh` with permissions 400: SSH refuses a key others can read, and files under `/mnt/c` can't be restricted.
   - Its contents never get pasted anywhere.
7. **The API key.** You put the OpenRouter key on the machine yourself, over SSH, with a command that doesn't echo it.
8. **Raw data goes over SSH, not GitHub.**
   - The replays need the raw data in WSL's `/root/power-v0/data/`: 1.4 GB, of which 240 MB is `.eval` logs and 1.1 GB snapshots and database dumps.
   - The raw logs contain secrets, so they go straight from WSL to the machine with `rsync` over SSH.
   - GitHub gets only the code and the redacted records. The repository is the private `AryaAIP/Power-Seeking`, pushed Nov 3. The machine gets the code as a git bundle from the laptop, so it needs no GitHub access.
9. **Control Tower is cloned on the machine itself** at commit `699d5ca`. It's Linux, so the rule against that code on the Windows filesystem still holds.

## How many environments at once

**About 25 to begin with, not 128.** Each environment's scorer compiles Go, which is CPU-heavy.
- **What WSL showed:** 10 environments drove the load to about 50 on 22 cores, about 5 cores each, and the scorer's 60-second `go build` timed out ([the Nov 2 log](../logs/2026-11-02-midday-runs.md)).
- **What that implies here:** about 25 at once on 128 cores, roughly 3 times WSL's 7–10.
- **The plan:** start at 16, then raise the cap in steps while the load stays under about 128 and memory has room. 256 GB across 25 environments is about 10 GB each, which is probably enough but hasn't been measured.

## Docker: what differs from WSL

- **Docker itself:** install Ubuntu's `docker.io`, the same 29.1.3 package WSL uses.
- **`/etc/docker/daemon.json`:**
  - Don't copy WSL's `mtu: 1350` (a WSL network workaround) or `max-concurrent-downloads: 1` (for the flaky home connection).
  - Add `default-address-pools`. Docker's built-in ranges allow only about 30 networks, and each environment creates its own.
  - The range must not overlap the network AWS gives the machine. The default VPC is `172.31.0.0/16`.
- **The internet-simulator image name:** keep `localhost/env-internet-simulator:v1.0.1` in `ct.env`. Control Tower still pulls that image every time an environment starts.
- **Images:** about 13 GB to download (the app 9.4 GB, the storage setup 2.5 GB, plus Postgres, MinIO, nginx and the internet simulator). That takes minutes on AWS's network.

## Setup order

1. **You:** send the public IPv4 address and say where `Power1.pem` is.
2. **Claude:**
   - connect and install Docker and Control Tower;
   - configure the daemon, download the images and add the image name;
   - copy the harness and the raw data.
3. **You:** set the OpenRouter key.
4. **Claude:**
   - run a free probe with no model calls, to check that environments start and score;
   - measure the load per environment and set the cap.
5. **Paid runs** only after that, with your go-ahead.

The exact commands for each step, and for every later session, are in [vm-runbook.md](vm-runbook.md).

## Sources

- [EC2 on-demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [EBS pricing (gp3)](https://aws.amazon.com/ebs/pricing/)
- [VPC pricing (public IPv4 addresses)](https://aws.amazon.com/vpc/pricing/)
- [Supported CPU options for EC2 instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/cpu-options-supported-instances-values.html)
- [cloudprice.net: c7a.32xlarge](https://cloudprice.net/aws/ec2/instances/c7a.32xlarge)
