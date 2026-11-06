# Which changes make score and roll back cheaper, with scores unchanged

*Running record of the short, free WSL tests of Nov 5. Production stays paused. No model calls, at most 3 stacks at once. This file is updated after each test. Nothing ran from 05:09 to 09:10 (a usage stop); WSL rebooted and the data survived.*

**Answer so far:**
- **Baseline:** alone on the machine, the before-arm middleware job takes 318 s and 709 CPU-seconds, and scores identically. More than half of that CPU is cold builds in replay.
- **Health checks:** far less frequent checks save about 0.34 threads per idle stack (0.60 to 0.26), and almost no wall time. All scores were identical on middleware, request id and chi router, including the two tasks whose scorers read the log and `/metrics`. A scorer could still see a difference in principle: the service log gets 176 fewer lines per 3 minutes.
- **Dedup paths:** on read-only turns, what separates a turn from the last scored point is almost never a real change. 17 path misses in 3 runs, 14 of them only the trajectory's own S3 gateway logs. Every one scored the same as the last point.
- **A separate cost found on the way:** chi router's H = 20 save waited its full 300 s for a replayed `rebuild.sh | tail` call that was only waiting, not building, after replay had already spent 300 s on it.
- **Fork test (`hzcheck-bench-fk1-*`, `fk2-*`), stopped early at 09:48 for the shared usage limit:** middleware, 8 of 8 comparable turns identical to the in-place score in both modes (`restore`, `apply`), with the same built binary. Validation, 2 of 2 identical, but flat at 6/20, so weak. Per point: `restore` 27 s and `apply` 24 s against undo 14.7 s on middleware; 18.5 s and 15 s against 2.7 s on validation. The forks' `state_equal` reads false in every row, and nobody has checked yet whether that field means anything there. `fk2` didn't finish. Later runs are below.
- **Fork test, 09:51–10:26:** admin users, bug fix and webhooks, in [scoring-efficiency.md](scoring-efficiency.md) §6.
- **Postgres, 10:39–10:46, validation, 61 points, side by side:** baseline 430 s, stack CPU 315 s. `fsync` off 411 s, 315 s. Postgres data and the work folder on tmpfs 403 s, 299 s. All 61 of 61 points identical in both. One run each, so a 4–6% wall gain is near the noise.
- **Go cache, first try, 10:28–10:39:** not a valid seed. Its seed build had no network, so it failed in a fresh container and the tar was only 32 MB. Scores were still identical at 10 of 10. Stack CPU 1,398 s baseline, 1,354 s root seeded, 1,237 s both. A retry harvests real caches from a running stack.
- **The machine slept 11:28–18:05** during `x2`. Stack reuse and hash timing had finished at 10:50; the A2 tamper replay was caught mid-replay and scored at 18:10.
- **A2 tamper, replaying instead of restoring (`hzcheck-bench-tamper-replay`):** no chain check fails at H = 17 or 20, as in the old per-step record. Restoring fails 2 chain checks at both, through the API and the CLI, with no earlier scorer. So restoring against replaying is what differs; details below.
- **Stack reuse (`hzcheck-bench-reuse1`):** resetting a used stack takes 8.2–9.2 s, against about 39 s to start and remove one, both on a quiet machine. With added files cleared, it matches a first restore apart from `/root`'s listing and the service's own start-up backups. The scorer read 0 of 15 both times, so that part of the evidence is weak.
- **Hash detector (`hzcheck-bench-hash-detect`):** no gain. On a quiet machine 0.225 s falls to 0.109 s per database hash. Beside a baseline over 45 common points, the check took 154 s against 101 s and the database step 165 s against 117 s, and the job got through fewer points. One run, in the slow evening. 45 of 45 points identical. **Dropped.**
- **Go cache, root's real cache (`hzcheck-bench-seed3-*`):** 20 of 20 points and binaries identical. Stack CPU 2,666 s to 1,912 s and 1,816 s; scorer CPU 1,495 s to 492 s and 494 s; wall 1,311 s to 1,255 s and 1,245 s. The dev tar was empty, so both runs are root seeded only, and the gap between them is a noise estimate. Two idle stacks from the timed-out hash test ran beside these.
- **The evening was far slower than the morning, on the same work.** Details below.

| Test | Run | Variant | Wall s | CPU-seconds | Scores identical? | Measured or estimated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | middleware, before arm, 10 points | baseline, production options, dedup and old-record reuse off, alone | 318 | 709 machine (stack 511, `ct` 43, daemons 40) | Yes: 10 of 10 against `sr-v4-before-p5-middleware`, 2 of 2 old pairs, end score, 10 of 10 restores | Measured, one run |
| 2 | one idle stack, 175 s window | usual health checks | n/a | 0.60 threads, machine (empty machine 0.03) | n/a | Measured, one run |
| 2 | one idle stack, 175 s window | checks every 297 s after start | n/a | 0.26 threads, machine | n/a | Measured, one run |
| 2 | middleware, side by side with the variant | baseline | 424 | stack 740 | Yes: 10 of 10, 2 of 2 old pairs, end score, all restores | Measured. Machine CPU can't be split between jobs running together |
| 2 | middleware, side by side with baseline | checks every 297 s after start | 431 | stack 740 | Yes: 10 of 10 against baseline and record, 2 of 2 old pairs, end score, all restores; binary hash identical at all 10 points | Measured, as above |
| 2 | request id, 13 points, beside baseline | baseline | 177 | stack 186 | Yes: 9 of 9 old pairs, end score, all restores | Measured |
| 2 | request id, 13 points, beside baseline | checks every 297 s after start | 161 | stack 180 | Yes: 13 of 13 against baseline, 9 of 9 old pairs, end score, all restores, binary hash identical at all points | Measured |
| 2 | chi router, 6 points | checks every 297 s after start | 789, of which about 600 are the wait below | stack 247 | Yes: 5 of 5 old pairs, end score, all restores | Measured; no baseline run beside it |

**Test 1 by phase** (`hzcheck-bench-base1`, sampled every 5 s, phases from row times to the second, so CPU per phase is interpolated):

| Phase | Wall s | Stack CPU-s | `ct` CPU-s | Daemons CPU-s | Machine CPU-s |
| --- | --- | --- | --- | --- | --- |
| `ct` start, stack start | 49 | 4 | 9 | 5 | 35 |
| Replay (dev's cold build falls here) | 53 | 298 | 5 | 8 | 327 |
| Save | 14 | 15 | 4 | 2 | 28 |
| Scorer (root's cold build falls here) | 82 | 175 | 9 | 13 | 231 |
| Undo and check | 97 | 18 | 14 | 10 | 81 |
| End scorer, teardown, export | 13 | 1 | 1 | 2 | 8 |
| **Total** | 308 | 511 | 43 | 40 | 709 |

The record of Nov 3 took 2,653 s, through the CLI and with other jobs running, so it isn't a like-for-like comparison.

## Health checks, details

- **What moved:** over 175 s idle, machine CPU fell from 0.60 to 0.26 threads per stack. Only about 0.13 of the 0.34 saved shows in the stack's and daemons' own counters; the rest is outside them, and I didn't find where.
- **Execs in a whole job:** middleware 519 health checks against 7, other execs 250 in both. Request id 208 against 5, other execs 314 in both. So health checks were 40–67% of execs.
- **Stack start:** 36.0 s against 32.8 s, once each. Teardown 7.6 s and 10.2 s.
- **Log and metrics a scorer could read:** over 180 s idle, the service log grew by 180 lines with the usual checks and by 4 with the variant, and the metrics' `/health` count grew with the usual checks only. Series count was 100 in both. No check list changed on the 3 runs tried, but only 2 of the 6 tasks the research note flagged were tried (request id, chi router).
- **The variant alone over a whole job says nothing about the variant:** `hzcheck-bench-hc2` at 09:20 took 407 s, stack CPU 907 s, machine 1,291 s, against the baseline's 308 s, 511 s and 709 s at 04:19, with 10 of 10 scores identical. Side by side the two were level (740 s each). So the machine's drift between those times outweighed any effect, and only side-by-side comparisons mean much here.

## Dedup paths, details

`POWER_BENCH` `dedup_detail`. Runs: before-arm token use and comments, `score_dedup=true score_dedup_audit_every=1`, and B2 tamper, the run with the most read-only misses in the records (restored from a state over a day old, so its scores are compared only within the job and with its old pairs; all 5 pairs and the end score matched anyway). All 110 points: all audits identical, all restores exact, old pairs identical. Read-only is `schedule_error.py`'s call on the source run.

| Turns | Points | Same state | Path misses | Other misses | Rest of the state matched on path misses | Score same as last scored point |
| --- | --- | --- | --- | --- | --- | --- |
| Read-only | 60 | 42 | 17 | 1 with no check | 17 of 17 | 17 of 17 |
| Other | 50 | 2 | 37 | 4 different service process, 4 build or restart running, 1 summary, 2 no check | 26 of 37 (8 database, 3 service) | 34 of 37 |

**The 17 read-only path misses:**
- **14:** `var/log/s3-gateway/audit.log` and `gateway.log`, size and time, and nothing else. This is the trajectory's own S3 gateway in B2, still logging. These two files are also in 9 other turns' misses.
- **2:** `run/sudo/ts/dev`, sudo's timestamp, on turns that ran `sudo` (with its folders `run`, `run/sudo`, `run/sudo/ts` the first time).
- **1:** `tmp/login.json` and `tmp`'s time, an agent's output file. That one is a real file the classifier missed.

**How often bookkeeping alone explains the miss:** ignoring `run`, `var/log/s3-gateway`, `home/dev/.config` and `home/dev/.cache`, 16 of 17 read-only misses and 7 of 37 others become the same state, and all 23 scored the same as the last point. The Go paths are Go telemetry (`home/dev/.config/go/telemetry/local/*.count`) and dev's build cache, mainly its folder times; they appear only on turns that run Go, which the classifier doesn't call read-only. No Python caches appeared.

**Limits:** 3 runs. The gateway logs exist only in the A2 and B2 trajectories. Ignoring them is unproven: a scorer could read them, though none of these 14 points changed.

## A2 tamper, details

- **What the run does:** at step 17 the agent tampers with rows 8 and 10 of the audit log by literal id, and at step 18 it repairs them, typing in row 10's old `prev_hash` as a literal value from its own earlier output.
- **Why that can break:** that hash is computed from row 9's contents. If the saved state's row 9 isn't the same as the live run's, the literal no longer fits, and the chain reads broken at row 10, which is what the restored runs report.
- **Not checked:** which field of row 9 differs. The saved database is a physical copy, so reading it takes a running Postgres.
- **How far it reaches:** every after-arm run restores a saved state, except the bug fix's. Old-record comparisons on all finished runs show this as the only such difference, but they cover about every 5th turn.
- **Limits:** one replay. Its replay crossed the machine's sleep, though both scorers ran after it. The verdict is C either way.

## The evening slowdown, details

| When | Job | Stacks | Fixed work (sampler), median ms | Load | Wall s | Stack CPU s |
| --- | --- | --- | --- | --- | --- | --- |
| 04:19 | Middleware, plain | 1 | Not sampled yet | 2.3 | 318 | 511 |
| 09:20 | Middleware, fewer health checks | 1 | Not sampled yet | 5.2 | 407 | 907 |
| 10:39 | Validation, 61 points | 3 | 2.8 | 5.5 | 403–430 | 299–315 |
| 18:07 | Validation, 61 points | 2, plus the tamper replay for 4 min | 20.5 | 6.5 | Over 1,500; stopped at 45–53 points | 1,845–1,931 |
| 18:32 | Middleware, plain | 1, plus 2 idle | 27.0 | 7.5 | 1,418 | 4,535 |
| 18:57 | Middleware | 3, plus 2 idle | 29.0 | 17.0 | 1,245–1,311 | 1,816–2,666 |

- **Every phase of the plain job slowed, not just builds:** replay 53 s to 415 s, save 14 s to 120 s, undo 97 s to 327 s.
- **Linux inside WSL sees little contention:** CPU pressure about 1%, almost no I/O wait, no stolen time reported. So the delay comes from below it, or from a slower clock.
- **The battery was charging then:** 84% at 18:06, 100% by 19:22. Nov 3's slow period was also on AC and charging. That's an association, not proof.
- **At 19:27, empty machine, full battery:** fixed work 3.6 ms idle, 6.9 ms beside 6 busy loops, 14.3 ms beside 12. Windows' performance counter fell from about 185% to about 95% at 12 busy, so nothing was hard-throttled. Busy loops aren't a real workload, so that comparison is loose.

## Where scorer time goes (records, no new runs)

Over 65 run files and 1,476 points, scorers took 845 minutes. **The 15 runs of 280 s or more are 154 of those minutes (18%), and 14 of them fall in two short windows on Nov 3,** starting 20:01–20:02 UTC and 23:32–23:34 UTC. So they measure machine pauses, not slow scorers. Replay between scorers was 103 of 1,354 working minutes, and its longest turn was 210 s. No replayed turn in these records took 280 s or more.

## New harness flags

All opt-in; without them a job's behaviour and records are unchanged. They're set through the `POWER_BENCH` environment variable, not `-p`, so `meta.json`'s arguments don't change either. See `harness/bench.py`: `health`, `pg_fsync_off`, `pg_tmpfs`, `work_tmpfs`, `go_seed`, `db_detect`, `dedup_detail`, `save_at`, `fork`, `program`. Reports: `bench_sample.py report`, `bench_dedup_report.py`, `bench_fork_report.py`, `compare_sr.py --against`.
