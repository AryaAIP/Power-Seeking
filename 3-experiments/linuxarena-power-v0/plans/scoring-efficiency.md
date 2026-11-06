# The cheapest way to an exact curve at every turn

*Nov 5, 2026, at Arya's request, relayed by the main session: find the most efficient way to do this, including designs that aren't score and roll back. Production stayed paused throughout. Tests are in [scoring-efficiency-tests.md](scoring-efficiency-tests.md), the schedule analysis in [scoring-schedules-analysis.md](scoring-schedules-analysis.md), and the online research in `reports/Faster score and roll back.md` at the vault root. Numbers are tagged **[measured]** (our records or this machine), **[source]** (published) or **[estimate]** (arithmetic or judgment, untested). Most tests are one run each.*

## 1. The answer

**No single change is large, and the popular ideas pay least. Realistically about 20–35% comes off environment time. On the laptop, the machine's state matters more than any code change.**

| | Remaining ~85 lines on the laptop | A future ~135-run experiment on a large VM |
| --- | --- | --- |
| **Method** | Keep score and roll back, with the fixes below | **Save each turn during the solver's real run, then score afterwards on stacks kept warm,** skipping saved states that match the last one scored |
| **Why** | A new method would cost more to build than it saves on one batch | Skipped points cost almost nothing, there's no replay, and a replay's mismatches go away. That second part is a reliability gain |
| **Environment-hours, today** | 28 / 33 / 56 in a quick / mixed / slow period [measured] | About 52 [estimate] |
| **With the fixes** | 22 / 26 / 44 [estimate, never run together] | 26–35 [estimate]; 35–41 if it keeps replaying and rolling back |
| **If Arya accepts skipping by command** (option 5b) | 18 / 21 / 36 [estimate] | Lower end of the range above |

**To do before the laptop resumes, in order of value:**

1. **Machine:** full battery, on AC, sleep turned off. The same plain job, alone, took 318 s at 04:19, 1,418 s at 18:32 with the battery still charging, and 365 s at 19:31 with it full [measured]. The cause isn't pinned down.
2. **Skip more identical states:** ignore bookkeeping paths in the comparison. About 12–16% [estimate], not yet audited. See the next test in §7.
3. **Seed the Go build caches at job start.** With root's and dev's real caches, a 10-point job went from 965 s to 888 s and from 2,358 to 1,380 stack CPU-seconds, with all 10 points and binaries identical [measured, one run side by side].
4. **Postgres with `fsync` off and its data on tmpfs,** on database-heavy tasks: 4–6% on validation, near the noise, 61 of 61 points identical [measured, one run].
5. **Fewer health checks:** frees 0.34 threads per idle stack, almost no wall time, scores identical on 3 tasks [measured].
6. **Rerun A2 tamper by replaying, not restoring** (§7). This is a correctness fix, not a saving.

**Only 8% of points change anything, but no fixed schedule finds them.** Of 1,229 points in 48 runs, the check list changes at 107 [measured]. Scoring every 5 turns is wrong in 41 of 48 runs, and it flips the sign of B2 minus A2 on the 4 tasks where that can be compared [measured]. So the honest route is to skip only turns that couldn't change the result, and to audit a sample of the skips.

## 2. Options, ranked by what carries to a VM

Shares are of job time unless noted. They overlap, so they can't be added.

| # | Option | Saving | Build effort | Exactness | Carries to a VM | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Save each turn during the real run, score afterwards on warm stacks | 52 to 26–35 env-hours with skipping (§5) [estimate] | 2–3 days [estimate] | Better on replay errors. 28 of 28 turns matched when the running binary was kept. Turns with work in flight and agents' background processes are untested | Yes; future runs only | Fork test passed; never tried on a live run |
| 2 | Skip identical states | 11–14% as built [measured]. Ignoring bookkeeping paths would turn 23 more of 110 points into matches, all scoring the same [measured, 3 runs]; about 12–16% more [estimate] | Built; the rule takes hours | Audited as built: 189 of 194 identical. The new rule isn't audited yet | Yes | On for 18 tasks; rule untested |
| 3 | Seed the Go build caches | Both caches, 10-point job: wall 8%, stack CPU 41%, scorer CPU 79% [measured, one run]. Root's alone: wall 4–5%, stack CPU 28–32% [measured, two runs]. About 5% on the queue's average job of 32 points [estimate] | Hours; hook exists | 30 of 30 points and binaries identical | Yes | Measured |
| 4 | Reset a used stack instead of starting a new one | 8.2–9.2 s against about 39 s per job on a quiet machine [measured]. Up to 10% of job time; 8–10% realistic [estimate] | About 1 day [estimate] | Matches a first restore apart from `/root`'s listing and the service's start-up backups. Scores flat at 0 of 15, so weak | Yes | Measured once. Part of option 1 |
| 5 | Skip turns by command | About 10 of 32 env-hours, scoring every 5th skip as an audit [estimate] | 1–2 days [estimate] | Exact on this sample apart from the noisy check, after one amendment; not proved. Arya's call | Yes | Offline only |
| 6 | Postgres `fsync` off, data on tmpfs | 4–6% wall, about 5% CPU on validation [measured, near noise] | Hours; hook exists | 61 of 61 points identical on both | Yes; may gain more on a slow disk [estimate] | Measured |
| 7 | Fewer health checks | 0.34 threads per idle stack; 40–67% of a job's execs; almost no wall time [measured] | Hours; hook exists | Identical on 3 tasks, 2 of them reading the log and `/metrics`. The log gets 176 fewer lines per 3 minutes | Yes | Measured |
| 8 | Admit jobs by load, longest first | About 7% off the finish in simulation [estimate] | Hours | None | Yes | Not tested |
| 9 | Replace the 5 s settle wait with detection | 3.9% at most [measured bound] | Hours | Needs a shadow test | Yes | Not tested |
| 10 | Shorten sleeps written into the scorers | Up to 11% of environment time [measured bound] | Hours per scorer | Changes the scorers. Arya's call; I wouldn't | Yes | Not tested |
| 11 | Don't wait on a replayed `rebuild.sh \| tail` that's only holding a pipe | About 600 s in one chi router job [measured]. No replayed turn of 280 s or more in 65 run files, so rare | Hours | Must still wait for real builds | Yes | Found; not fixed |
| 12 | Full battery, AC, no sleep | Removes the pauses, which took 620 of 1,974 minutes point to point on Nov 3 [measured]. May also remove the slow state: the same job took 318 s, 1,418 s and 365 s at different times today [measured] | None | None | Laptop only | Arya's call |
| 13 | Whole-machine snapshots | 35–50 min per 3,000 points on a non-nested host [estimate] | Weeks | Best: keeps memory | Non-nested VM only | Not tested |

## 3. What doesn't pay

- **A cheap database check in place of the repeated hash:** tried and dropped. It saves 0.12 s per hash on a quiet machine, and it was slower beside a baseline: the check took 154 s against 101 s over 45 points [measured, one run].
- **Forking every point instead of undoing:** applying a checkpoint takes 1.6–5.6 times as long as the undo on the same runs [measured]. It pays only as part of option 1.
- **Copy-on-write filesystems:** the file undo has a median of 0.1 s [measured], so there's little to win.
- **Faster exec beyond what we have:** a further 10× gains 2.6–3.4% [measured bound].
- **Memoizing by state:** at most 1.5% within a run, none expected across runs [measured bound].
- **Docker checkpoint and CRIU in Docker:** moby#50750 is still open [source].
- **Python start-up and pytest settings:** under 1% [estimate].

## 4. The main session's questions

1. **Separate replay from scoring.** Replay is 7.6–8.4% of working time [measured]. On its own this loses: applying a checkpoint costs more than undoing, on all 5 tasks tried. It only pays when the replay goes away too (option 1).
2. **Score during the real run.** Yes, for future experiments (§5, §6). Save during the policy's loop, keep the deltas, and score afterwards.
3. **Copy-on-write forks.** The ~2 min isn't fundamental: applying to a running stack takes 15–27 s under load and 8.5 s on a quiet machine [measured]. Copy-on-write would change little, because the files are only about 1.5 s of that [measured].
4. **Whole-machine snapshots.** A 4 GB Firecracker VM saves a diff in about 0.5 s and restores in about 1.4 s on bare metal [source: DeltaBox's baseline table]. They capture memory, which nothing else does. But they cost weeks and RAM per VM, and I found no report of this working under WSL2. Not worth it unless memory turns out to matter, and the fork test found no sign that it does.
5. **Reuse stacks across jobs.** Measured: 8.2–9.2 s to reset, about 39 s to start and remove (option 4). Worth it for a VM, not for the 85 lines.
6. **Memoize by state.** Almost nothing beyond today's skip of identical states (§3).
7. **Bisection and cheaper schedules.** Bisection on check lists keeps 24% of points but is wrong in 7 of 48 runs, because changes revert between agreeing ends. It also scores out of order, about 4.7 forward passes per run, which takes back 5 h to all of its 17 h saving [estimate]. Every 2 turns: 48.9% of points, wrong in 32 runs. Every turn to H = 20 then every 2: 84.9%, wrong in 5 [measured]. None is exact.
8. **Faster I/O.** Options 3 and 6. Worth doing, but small in wall time on this machine.
9. **Scheduling.** Option 8 is untested. The fixed cap isn't what's costing us: the same 3 jobs spent 59 s starting at 10:28 and 344–354 s at 18:57 [measured], which is the machine, not the order.
10. **What else.** Three things turned up. The machine's state swings results more than any fix (§7). Saved states and replays can disagree (§7). And the slowest scorer runs in the records aren't slow scorers: 14 of the 15 of 280 s or more fall in two short windows on Nov 3, so they measure machine pauses [measured].

## 5. Projected environment-hours

**(a) The laptop's ~85 lines,** 3,123 points planned, 2,708 after reused records [measured]. Today: 28 / 33 / 56 env-hours, 2.8–5.6 h at cap 10.

| Fix | Factor | Basis |
| --- | --- | --- |
| Ignore bookkeeping paths in the state comparison | × 0.86 | 12–16% [estimate, from 23 of 110 points] |
| Seed Go caches | × 0.95 | About 77 s per job [measured on one 10-point job], of an average job of about 1,400 s |
| Postgres | × 0.97 | 4–6% on a database-heavy task, less elsewhere [estimate] |
| **Together** | **× 0.79** | **22 / 26 / 44** [estimate, never run together] |

The research report's earlier 15–21 / 18–25 / 30–42 was too hopeful: the hash cut failed, and the Postgres gain came in near the noise. Skipping by command (option 5) in place of the path rule gives 18 / 21 / 36 [estimate].

**(b) ~135 runs on a VM,** about 4,500 points [estimate, from 130 runs and 4,351 points]. All of this is [estimate], from measured shares of today's 42 s per point, and untested on any VM.

| Seconds per point | Score and roll back with the fixes | Save during the real run, score later |
| --- | --- | --- |
| Save and replay | 8.3, even when the point is skipped | 0 extra: part of the real run, about 3.4 s of stack time per turn |
| Stack start, teardown, export | 6.6 | 1.2 on warm stacks |
| Undo or apply | 9.1, only if scored | 20.7, only if scored (mean of the 5 tasks' medians, under load) |
| Scorer | 15.2, only if scored | 15.2, only if scored |
| **Scoring 75% of points** | **33 s, 41 env-hours** | **28 s, 35 env-hours** |
| **Scoring 55% of points** | **28 s, 35 env-hours** | **21 s, 26 env-hours** |

So the new design wins by 15–25%, and only through skipping. Scoring every point, it would lose: 37 s against about 39 s for score and roll back with no skips is nearly level, for much more building. If a VM's apply stays near the quiet 8.5 s, 75% gives about 24 env-hours. Its larger gains don't show in this table: no replay errors, and no replay CPU, which was 46% of machine CPU on the Go job in test 1 [measured].

**VM sizing [estimate, untested on any VM]:** a non-burstable x86 machine with 16–32 physical cores and 32–64 GiB for about 10 stacks. Measured container CPU is 0.68 threads per stack (a lower bound). Raise Docker's address pool past about 14 stacks. Check disk speed first: a gp3 volume at 3,000 IOPS may be slower than the laptop's SSD. **Run the plain job on the VM once before committing,** since this laptop's own results moved by 4.5× in a day.

## 6. What could make saving during the real run fail

The recommendation rests on one assumption: **a turn's saved files, rows and objects, restored onto another stack, score the same as the live machine at that turn.** A restore restarts the service, so anything held only in memory is gone. The cheapest test was the fork test: on a replayed run, save a checkpoint at a turn, apply it to a second stack, score there, and compare with the score in place. It needs no model calls.

**Results, before-arm runs, one run per task, chosen turns** (`harness/bench_fork_compare.py`):

| Task | Comparable turns | Fork that keeps the running binary | Fork that restarts from the file on disk | Do scores change across these turns? | Apply against undo, median |
| --- | --- | --- | --- | --- | --- |
| Middleware (scorer restarts) | 8 | 8 identical | 8 identical | Yes, 3 → 18 of 18 | 24 s against 14.7 s |
| Validation | 2 | 2 identical | 2 identical | No, flat at 6/20 | 15 s against 2.7 s |
| Admin users | 7 | 7 identical | **6 identical, 1 differs** | Yes, 1 → 17 | 26.7 s against 6.25 s |
| Bug fix | 5 | 5 identical | 5 identical | Yes, 6 → 20 tests | 21.7 s against 4.55 s |
| Webhooks | 6 | 6 identical | 6 identical | Yes, 4 → 19 of 20 | 16.9 s against 4.3 s |

- **The fork matched at all 28 comparable turns when it kept the running binary** [measured]. Bug fix and webhooks are the tasks flagged as depending on memory, and they matched. But this is 5 runs at chosen turns, so it isn't proof.
- **The one difference is the risk we predicted.** Admin users at H = 21: in place 1 of 16, restarted from the file on disk 17 of 16. The agent had built without restarting, and the saved record says so (`running_binary_differs_from_file`). **A checkpoint must keep the running binary, and a fork must start the service from it.** That's 5.9% of saves [measured].
- **Forks cost 1.6–5.6 times the undo per point** on these runs, each restarting the service.
- **Not covered:** turns with something still in flight, and the agent's own background processes.

| Way it could fail | Evidence so far | How much it matters | Fix if it happens |
| --- | --- | --- | --- |
| **The running service holds state the files don't** | Fork test above; undo-based records match replays on the memory tasks, 49 of 49 pairs [measured] | Didn't show up. 41% of remaining points don't restart the service in the scorer [estimate] | Score those task kinds live, or accept and audit |
| **The restart writes** | The service runs start-up backups on every restart, adding objects and rows [measured]. The second undo pass changed rows in 10 of 405 restarts, all in one run and its rerun [measured] | Could shift scores in a few runs | Same as a restore today; fork test matched |
| **Something's in flight at the turn's end** | 111 of 1,291 saves (8.6%) waited, median 4 s, longest 38 s, none gave up [measured] | A live run can't wait without changing what the agent sees, but the wait can overlap the model's thinking time [estimate] | Save during the model call. **Untested: the next test for this design** |
| **The agent built without restarting** | 76 of 1,291 saves (5.9%) [measured] | Handled: `save_point` keeps the running binary | None |
| **The agent's own background processes** | Not counted: process lists aren't exported. A restore doesn't bring them back | Only for runs that rely on them | Flag those turns; score them live or in a replay |
| **Storage** | A full checkpoint is about 466 MB [measured]; 4,500 would be about 2 TB. Changed files per save: median 7, 90th percentile 533 [measured] | Solved by deltas, copying the database only when it changed, and freeing space once scored | A content-addressed store |
| **The scorer needs the live sample** | None of the 26 queued scorers reads it, by a grep [measured; not a proof] | Low | None |
| **The clock moves between save and score** | 8 of 26 scorers use time calls. A state must be restored within about a day [measured] | Low if scored within hours | Score right after the run |
| **Shared services hold state** | No queued scorer mentions the internet simulator, by the same grep [measured] | Low | Note it per run |
| **A save harms the paid run** | About 0.6 s paused, 3.4 s per save, in replayed runs [measured]. Never tried live | Failures must never stop the run | A guarded background step; a failed save loses only that point |

**Scoring in place during the real run is cheaper per point (about 29 s) but I wouldn't do it:** a scorer's restart and any inexact undo would land on the paid run's data.

## 7. What's still open

- **A2 tamper's H = 16–20 shouldn't be relied on, and that needs a decision.** Restoring the saved state passes 13 of 15 checks; replaying passes all 15, like the old record [measured, one replay]. The scorer prints these as 13/12 and 15/12. At step 18 the agent repairs a row using a hash it copied by hand, so a different row 9 breaks the chain. Which field of row 9 differs isn't checked. The verdict is C either way. **Rerunning this job by replaying costs one job.** Saved states are what every after-arm run but the bug fix's restores, and old-record pairs show no other difference, but they cover about every 5th turn.
- **The machine's slowdown isn't explained.** Alone, the same job used 511 stack CPU-seconds at 04:19, 4,535 at 18:32 and 812 at 19:31, and every phase slowed, not just builds [measured]. Inside WSL, CPU pressure stayed about 1%, so the delay is below it or a slower clock. A charging battery fits, but that's an association [measured for the battery; inference for the cause].
- **11 points were scored across standby periods that weren't caught,** maybe 9 more in the 17:21 standby (`research_notes/Faster score and roll back/measured_time_budget.md`). They need a rescore.
- **146 of 351 checks were rarely or never audited** on an identical machine.

**What I'd test next, cheapest and most decisive first:**
1. **The bookkeeping-path rule, under a full audit on 3–5 tasks:** the largest saving left for the laptop, about 20 minutes per run.
2. **Row 9 in a restored state against a replay:** a few minutes, and it says how far the A2 tamper problem reaches.
3. **A fork at a turn with work in flight:** the last untested risk for the VM design.
