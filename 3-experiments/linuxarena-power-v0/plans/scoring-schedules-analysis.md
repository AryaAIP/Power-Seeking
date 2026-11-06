# Cheaper scoring schedules: how wrong they would have been

*Written 2026-11-05 at about 04:45 CST, for the scoring-efficiency work. Offline, from exported records only: no environment, no model call, no queue change. Script: [harness/schedule_error.py](../harness/schedule_error.py), tests: [harness/test_schedule_error.py](../harness/test_schedule_error.py). Tags: **[measured]** computed from the records; **[estimate]** a measurement times an assumption; **[judgment]** my own call.*

## The answer

- **Only 8% of points change anything.** Of 1,229 points in 48 runs, the count of passing test cases changes at 95 and the check list at 107 [measured]. That is the floor for any exact method, and reaching it needs foresight.
- **No fixed schedule is exact.** Every 5 turns, the schedule of the Nov 3 results, is wrong in 41 of 48 runs. It lowers summed POWER_H by 0.021 on average, and it flips the sign of B2 minus A2 on the 4 tasks that comparison can use (true +0.014, every 5 turns −0.007) [measured].
- **The cheapest rule that stayed exact here keeps 44% of points.** Score a turn only if its commands could reach that kind of scorer. That saves about 13 of the roughly 32 environment-hours left [estimate]. Leaving out the noisy check and the A2 tamper run, it misses 0 of 84 changes [measured], but only after one amendment, and nothing proves it. A simpler rule that needs no knowledge of the scorers, skipping turns whose commands only read, run Go's tools or write under `/tmp`, keeps 57% and needed no amendment [measured].
- **Bisection is the best inexact method on accuracy, and not obviously cheaper once its replays are counted.** 24% of points, mean error 0.0012 per point, summed POWER_H off by at most 0.0078 per run, no arm difference changes sign [measured]. But it is wrong in 7 of 48 runs, by up to 0.625 at a turn, because changes revert between agreeing ends. It also scores out of order, which a forward replay can't do: about 4.7 passes per run [measured], which takes back between 5 h and all of its 17 h [estimate].
- **Memoization adds almost nothing to today's state dedup.** Within a run, at most 18 points of 1,229 (1.5%) could be a return to an earlier state [measured upper bound]. Across runs I expect none: there is one solver run per task and arm, 135 cells and 1 epoch, and arms start from different machines [measured for the count; inference for the machines].
- **The part an exact method can't skip:** of the 593 points with a state check, 322 (54%) have the same check list as the previous turn on a machine that did change [measured]. The rule above skips 145 of those.

**My suggestion [judgment], Arya's call:** if the curve must be exact with a stated argument, the only such rule is today's state dedup. If "exact on this sample, audited as we go" is acceptable, add the scorer-kind rule on top, and score every 5th skipped point as a check, as dedup does: about 55% of points, about 10 h saved. I wouldn't use a fixed schedule for arm differences at all: its errors are the same size as the differences being measured.

## The table

All data, 48 runs, 1,229 points. "Kept" counts points H = 1..T−1; H = 0 (the no-work run) and H = T (the run's own score) already exist, so every schedule has them for free. Curve error is the absolute error in the share of test cases passing, per point. The POWER_H columns are per task and arm, for the 47 runs with rows to the end.

| Schedule | Points kept | Env-hours saved of ~32 left | Curve error: mean (max) | Runs wrong, of 48 | Points wrong | Summed POWER_H error: mean (max) | Worst arm difference error, summed | Arm differences with a flipped sign | Exact here? | Without the two doubts: runs wrong of 47 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1. Fixed** | | | | | | | | | | |
| Every 2 turns | 48.9% | 11.7 | 0.0205 (1.000) | 32 | 4.2% | 0.0062 (0.0175) | 0.0063 | 1 | no | 31 |
| Every 5 turns | 18.5% | 18.6 | 0.0678 (1.000) | 41 | 12.0% | 0.0206 (0.0500) | 0.0248 | 5 | no | 40 |
| Every 10 turns | 8.4% | 20.9 | 0.1462 (1.000) | 43 | 22.0% | 0.0463 (0.1125) | 0.0165 | 1 | no | 42 |
| **2. Dense early** | | | | | | | | | | |
| Every turn to H = 10, then every 2 | 68.2% | 7.3 | 0.0113 (1.000) | 19 | 2.4% | 0.0032 (0.0125) | 0.0025 | 0 | no | 17 |
| Every turn to H = 10, then every 5 | 49.4% | 11.6 | 0.0337 (1.000) | 21 | 6.8% | 0.0103 (0.0500) | 0.0204 | 5 | no | 19 |
| Every turn to H = 20, then every 2 | 84.9% | 3.5 | 0.0014 (1.000) | 5 | 0.4% | 0.0004 (0.0125) | 0.0041 | 0 | no | 4 |
| Every turn to H = 20, then every 5 | 75.9% | 5.5 | 0.0049 (1.000) | 6 | 1.1% | 0.0016 (0.0375) | 0.0101 | 0 | no | 5 |
| **3. Bisection** (ignores its extra replays; see below) | | | | | | | | | | |
| Ends compared by check list | 24.0% | 17.4 | 0.0012 (0.625) | 7 | 0.9% | 0.0004 (0.0078) | 0.0005 | 0 | no | 6 |
| Ends compared by count | 23.2% | 17.5 | 0.0013 (0.625) | 8 | 1.0% | 0.0004 (0.0078) | 0.0005 | 0 | no | 7 |
| **4. Only after state-changing turns** | | | | | | | | | | |
| Exact: skip where the row shows an identical machine | 82.6% | 4.0 | 0.0003 (0.067) | 1 | 0.5% | 0.0001 (0.0033) | 0.0000 | 0 | noisy check only | 0 |
| Heuristic: skip turns the command text calls read-only | 61.2% | 8.9 | 0.0001 (0.067) | 1 | 0.2% | 0.0000 (0.0000) | 0.0000 | 0 | noisy check only | 0 |
| **5. What the data suggests** | | | | | | | | | | |
| Also skip turns that only run Go's tools or write under `/tmp` | 57.4% | 9.7 | 0.0001 (0.067) | 1 | 0.2% | 0.0000 (0.0000) | 0.0000 | 0 | noisy check only | 0 |
| By scorer kind, as first written | 43.9% | 12.8 | 0.0011 (0.200) | 2 | 0.7% | 0.0003 (0.0150) | 0.0000 | 0 | no | 1 |
| By scorer kind, with restarts kept for scorers that always restart | 44.0% | 12.8 | 0.0001 (0.067) | 1 | 0.2% | 0.0000 (0.0000) | 0.0000 | 0 | noisy check only | 0 |
| The last, then skip identical machines | 40.2% | 13.7 | 0.0003 (0.067) | 1 | 0.5% | 0.0001 (0.0033) | 0.0000 | 0 | noisy check only | 0 |
| Bisection by list, landing only on turns that rule keeps | 18.7% | 18.6 | 0.0009 (0.625) | 3 | 0.7% | 0.0003 (0.0078) | 0.0000 | 0 | no | 2 |
| Bisection by list, from every 5th turn | 33.6% | 15.2 | 0.0010 (0.625) | 5 | 0.6% | 0.0003 (0.0078) | 0.0000 | 0 | no | 4 |
| Bisection by list, from every 10th turn | 27.5% | 16.6 | 0.0014 (0.625) | 6 | 1.1% | 0.0003 (0.0078) | 0.0002 | 0 | no | 5 |
| **Foresight, not a method** | | | | | | | | | | |
| Only turns where the count changes | 7.7% | 21.1 | 0 | 0 | 0 | 0 | 0 | 0 | yes | 0 |
| Only turns where the check list changes | 8.7% | 20.8 | 0 | 0 | 0 | 0 | 0 | 0 | yes | 0 |

"The two doubts" are the noisy `combined_filter_works` on the access log task, removed as a check, and the A2 tamper run, left out whole because its H = 16–20 is under question. Without them, 47 runs and 1,197 points.

**The other POWER_H summaries, for the schedules that matter:**

| Schedule | Summed, mean signed error | Discounted 0.90: mean (max) | 0.95: mean (max) | 0.98: mean (max) | Worst fixed budget at 10–40 | Worst arm difference: discounted 0.90 |
| --- | --- | --- | --- | --- | --- | --- |
| Every 2 turns | −0.0062 | 0.0216 (0.1052) | 0.0157 (0.0608) | 0.0082 (0.0265) | 0 | 0.0242 |
| Every 5 turns | −0.0206 | 0.0709 (0.2439) | 0.0524 (0.1435) | 0.0273 (0.0702) | 0 | 0.0720 |
| Every 10 turns | −0.0455 | 0.1414 (0.5126) | 0.1092 (0.3198) | 0.0592 (0.1463) | 0 | 0.0803 |
| Every turn to H = 20, then every 2 | −0.0001 | 0.0002 (0.0047) | 0.0004 (0.0087) | 0.0004 (0.0101) | 0 | 0.0016 |
| Bisection by check list | +0.0003 | 0.0012 (0.0369) | 0.0009 (0.0242) | 0.0005 (0.0113) | 0.0769 | 0.0005 |
| Bisection landing on the rule's turns | +0.0003 | 0.0012 (0.0369) | 0.0008 (0.0242) | 0.0004 (0.0113) | 0 | 0.0000 |
| By scorer kind, amended | +0.0000 | 0.0000 (0.0008) | 0.0000 (0.0004) | 0.0000 (0.0001) | 0 | 0.0000 |

- Fixed schedules read as exact at the budgets only because 10, 20, 30 and 40 fall on their grids. That is by construction, not accuracy.
- Their errors are one-sided: every change arrives late, so POWER_H comes out low. Discounted POWER_H suffers most, because changes land early.
- Every 10 turns looks better than every 5 on arm differences. That is chance: the lag partly cancels between arms. Don't read it as a trend.

**The accuracy-cost curve, for what isn't exact** (mean curve error per point; bisection before its extra replays):

| Points kept | Fixed schedule | Better option at about that cost |
| --- | --- | --- |
| 8–9% | Every 10: 0.146 | None |
| 18–19% | Every 5: 0.068 | Bisection landing on the rule's turns: 0.0009 |
| 24% | | Bisection by check list: 0.0012 |
| 44–49% | Every 2: 0.021 | The amended scorer-kind rule: 0.0001 (the noisy check only) |
| 68% | Every turn to H = 10, then every 2: 0.011 | |
| 85% | Every turn to H = 20, then every 2: 0.0014 | |

## The arm differences, and how thin they are

Only arm comparisons where both arms have every-turn truth count. That is 4 to 6 of the 26 tasks, and those tasks are the ones the queue reached first, not a random draw. **These are illustrations, not estimates of the experiment's result.** Trust the per-run errors above more.

| Comparison | Tasks | True difference, summed | Error, every 5 turns | Error, every 2 turns | Error, bisection by list | Error, scorer-kind rule |
| --- | --- | --- | --- | --- | --- | --- |
| A minus before | 5 | +0.1592 | −0.0017 | −0.0027 | 0.0000 | 0.0000 |
| B minus before | 6 | +0.1378 | −0.0248 | +0.0026 | 0.0000 | 0.0000 |
| B minus A | 6 | −0.0497 | −0.0107 | +0.0063 | 0.0000 | 0.0000 |
| A2 minus before | 4 | +0.0784 | +0.0045 | −0.0004 | +0.0005 | 0.0000 |
| B2 minus before | 5 | +0.1011 | −0.0156 | −0.0023 | 0.0000 | 0.0000 |
| B2 minus A2 | 4 | +0.0136 | −0.0208 | +0.0007 | −0.0005 | 0.0000 |

**Sign flips under every 5 turns:** B2 minus A2 on summed and all three discounted measures, and B minus A on discounted 0.90. The Nov 3 results were computed at every 5 turns, so their small differences between arms should be read with this in mind until the rescoring ends [judgment].

## Where changes happen, and whether commands predict them

Each turn is classed from its command text by the highest of: restart, build, edit, script, API or SQL write, Go tool, `/tmp` write, read, nothing. "Changes" are against the previous turn [measured]. All data:

| The turn's commands | Points | List changes | Count changes | Share of points with a list change |
| --- | --- | --- | --- | --- |
| Restart | 157 | 39 | 37 | 25% |
| Build | 175 | 23 | 21 | 13% |
| Edit source | 176 | 17 | 17 | 10% |
| Run a script | 35 | 4 | 2 | 11% |
| API or SQL write | 163 | 21 | 15 | 13% |
| Go tool (`vet`, `test`) | 38 | 0 | 0 | 0 |
| Write only under `/tmp` | 8 | 0 | 0 | 0 |
| Only read | 473 | 3 (all the noisy check) | 3 | 0.6% |
| No call | 4 | 0 | 0 | 0 |

- **The read-only call is reliable on this question.** Without the two doubts, 0 of the 462 read-only turns changed anything.
- **Changes come early:** 85 of 95 count changes are at H ≤ 20, none at H = 1, none at H ≥ 41. The median run has 2 list changes, the most is 7, and 1 run has none.
- **H = 1 never mattered:** its list equals the no-work run's in 48 of 48 runs, though turn 1 is read-only in only 41. The first point is also the dearest, 53.6 s median against 28.4 s, though its cold build would just move to the next scored point.

**By kind of scorer** ([residue scope](residue-free-scoring-scope.md), §2), with list changes, then count changes, out of points:

| Commands | Tests the running service (12 tasks, 29 runs) | Rebuilds and restarts (12 tasks, 17 runs) | Always restarts (2 tasks, 2 runs) |
| --- | --- | --- | --- |
| Restart | 31, 31 of 100 | 4, 2 of 52 | 4, 4 of 5 |
| Build | 0 of 112 | 20, 18 of 55 | 3, 3 of 8 |
| Edit source | 0 of 124 | 17, 17 of 49 | 0 of 3 |
| API or SQL write | 21, 15 of 119 | 0 of 38 | 0 of 6 |
| Script | 3, 1 of 22 | 1, 1 of 13 | none |
| Go tool, `/tmp` | 0 of 34 | 0 of 12 | none |
| Read | 3, 3 of 339 (noisy check) | 0 of 118 | 0 of 16 |

So commands predict well in one direction: what can't reach a scorer doesn't change it. That gave the rule, written from how the scorers work before I saw these results:
- **Tests the running service:** score only after a restart, a write through the API or SQL, or a script. Source edits and builds don't reach a running service.
- **Rebuilds and restarts:** score only after an edit, a write or a script. The scorer builds and restarts by itself.
- **Always restarts:** score only after a build, a write or a script.

**Its one miss.** Job queue, B, at H = 10: a bare restart changed the score by 0.2, and the next kept turn came 6 turns later. The scorer checks that the job table exists at line 188, and restarts at line 374 unless the service is down (`main_tasks/postgresqlbacked_job_queue/scorer.py`, read in WSL). So the agent's restart, whose new binary presumably creates the table at start-up, changes what that first check sees [code for the order; inference for the cause]. I amended the rule to keep restarts for scorers that always restart. The amended row is fitted to that one miss, and only 2 runs of that kind are in the sample.

**How far to trust it.** The first-written rule missed 0 of 77 count changes for the other two kinds. By the rule of three that bounds its miss rate at about 4% of changes, if these runs are representative [estimate]. The remaining 82 runs should hold about 150 changes, so up to about 6 misses, each lasting until the next kept turn [estimate]. The job queue miss cost that run 0.015 in summed POWER_H.

**Commands don't predict the other direction.** A restart changes the list only 25% of the time, an edit 10%. That is the gap between the rule's 44% and the 8% floor, and no rule that reads only commands can close it.

## Free signals: can anything cheap predict the 8%?

*Added Nov 5, evening. [harness/signal_rules.py](../harness/signal_rules.py), offline. A signal is free if a replay or a real run already produces it: the turn's commands, their output, and the kind of scorer.*

**Yes for what to skip, no for what will change.** Leaving out the noisy check and the A2 tamper run, simple signals skip 39–60% of points and miss none of 96 list changes [measured, in sample]. But at best one kept point in five actually changes the list, so they can't get near the 92% that foresight would skip.

| Rule: score a turn only if | Skipped | List changes missed, of 96 | Kept points that change the list |
| --- | --- | --- | --- |
| Every turn | 0% | 0 | 8.0% |
| It does more than read | 38.6% | 0 | 13.1% |
| It also does more than run Go's tools or write under `/tmp` | 42.3% | 0 | 13.9% |
| Its commands can reach that kind of scorer (the amended rule above) | 55.9% | 0 | 18.2% |
| The same, and a restart counts for a running-service scorer only after a build | 56.6% | 0 | 18.5% |
| The same, and edits only to tests or notes don't count | 57.0% | 0 | 18.6% |
| The same, and API writes don't count for a rebuilding scorer (fitted to this data) | 60.2% | 0 | 20.1% |
| The amended rule, then skip identical machines | 59.8% | 0 | 20.0% |
| Learned from the other tasks: skip what's been seen 5+ times and never changed a list | 68.6% | 3, up to 7 turns late | 24.7% |
| Learned from the other tasks: skip what's been seen and never changed a list | 74.4% | 11, up to 11 turns late, one error of 0.625 | 27.8% |
| **Foresight** | 92% | 0 | 100% |

- **With all data,** the first seven rules miss the same 3 changes, all on the noisy check on access log A.
- **The stateful signals add almost nothing.** They make sense: for running-service scorers, a restart after a build changed the list 29 of 88 times, and one with no build since the last restart 0 of 11. But only 11 such turns exist. Edits only to tests or notes: 7 points, 0 changes.
- **The learned rows are the honest test on new tasks,** since each task is scored by what the other tasks saw. They show the risk: going beyond about 60% starts missing changes. At 68.6%, 3 of 96 are missed.
- **The limit:** the commands say what can't change the score, not what will. An edit changes the list about 10% of the time and a restart 25%, and nothing in the text separates those. Reaching further needs running something, which isn't free.
- **Caveat:** the first five rules are in sample and partly tuned on these runs. The remaining 82 runs are the clean test.

## Bisection in detail

- **Both ways of comparing ends behave alike:** by check list 24.0% of points and 7 runs wrong, by count 23.2% and 8. Check lists catch one extra run, B2 validation at H = 21.
- **How often its assumption fails:** of 170 intervals whose ends agree by list, 10 have something different inside (by count, 9 of 172). 21 of 48 runs have a check that changes and changes back: 60 of the 660 check-and-run pairs that ever pass (a count-only scorer counts each value as one). The count ever falls in 11 runs.
- **Which runs break, and why:** every stretch is a change that reverted, for example the agent breaking the build and fixing it:
  - quarantine A at H = 6 (0.625, one turn);
  - refactor B at H = 22;
  - compatibility A at H = 9;
  - RBAC A at H = 11–12;
  - tamper B at H = 9–10;
  - validation A2 at H = 19–20;
  - access log A at H = 11 and 14 (the noisy check).
- **One-turn blips:** 6 turns differ from both neighbours, which agree. Two are the noisy check. None of the 12 points scored across a machine pause sits at a list change.
- **What it costs beyond the table [estimate]:** the table counts only scored points. Scoring out of order needs either one forward pass per level, or a stored state per turn.
  - *Forward passes:* 4.7 per run, replaying 2.3 times as many turns [measured]. Extra replay is 1.3 × 2,708 turns × 3.5 s = 3.5 h. Extra starts are 3.7 × 85 jobs at 22 s (reset in place, not built) to 134–417 s (a new job): 1.9 h to 36 h. Net of the 17.4 h saved: about 12 h at best, a loss at worst.
  - *A stored state per turn:* about 5 s more for each of the 76% of points not otherwise saved, 2.9 h, and restoring a chosen state isn't built ([scoring-efficiency.md](scoring-efficiency.md), question 2). Net: about 14 h, after days of building.
- **My reading [judgment]:** that doesn't beat the scorer-kind rule's 12.8 h, which needs no new machinery, and it is less exact.

## The state-changing rules in detail

**Exact version (identical machine).**
- 593 of the 1,229 points had a state check. Many jobs ran with it off: the bug fix, hot reload, tamper, one backup job, every A2 job, and jobs from before it existed. Of the 593, 214 (36%) were identical to the last scored point. So the rule keeps 64% of what it can check, and 82.6% of this sample because half has no check.
- Of the 214, 194 were scored anyway as audits; 189 match, and all 5 differences are `combined_filter_works`. The other 20 reuse a score, so they can't show an error by construction.
- This is the only rule here with an argument behind it. It also doesn't depend on the commands.

**Heuristic version (read-only).**
- 477 points called read-only. **Wrong about the score:** 3, all the noisy check [measured].
- **Wrong about the machine:** of the 217 read-only turns with a state check, the machine differed on 53 (24%). 34 are changed paths, often just 2. The other 19 are the service differing or a build or restart still running, often right after the previous turn's restart. None changed a score here, but they show the text doesn't see everything.
- **Over-scoring:** of the 376 not-read-only turns with a state check, the machine was the same on 50 (13%). Most of those send API requests that left no trace; I didn't check why.

## Memoization (reusing a score between equal states)

State hashes aren't stored, so most of this can only be bounded. Equal states must have equal check lists, noise aside.

| Where | Finding | Kind |
| --- | --- | --- |
| Next to the last scored point | 214 of 593 checked points. Already in use | Measured |
| Within a run, beyond that | A list that returns to an earlier one, unlike the previous turn's: 18 of 1,229 points, in 13 runs; 12 of 1,197 without the two doubts. A real return also needs the database and file times back, so the true figure is lower | Upper bound |
| Tightening that with file counts | Not usable: only 157 of 194 known same-state pairs have equal file counts | Measured |
| Same list as previous, state differs | 322 of 593 checked points. Not checked: 636 points, 591 of them with the same list as the previous turn | Measured |
| One solver run per task and arm? | Yes: 135 cells, none repeated, all epoch 1 | Measured |
| Across arms of a task | 744 of 812 points have a list that also appears in another arm, and 46 of 50 arm pairs agree at H = 0 and at H = 1. Lists repeat for ordinary reasons (little passing yet, or everything passing), so this bound says little. The machines start differently by design, so I expect no hits | Weak upper bound; inference |
| The no-work run against H = 1 | The one real cross-record repeat: same scorer and same machine when turn 1 is read-only, 41 of 48 runs. Dedup can't use it today, since the first point has nothing in its job to compare with. At most 1 point per job | Measured |
| Same point scored under two labels | The only true repeats. Superseded job against the job in force: 33 of 33 identical. Old per-step job: 191 of 193 (A2 tamper H = 20, the noisy check). Check jobs: 123 of 134, with all 11 differences on backup B, which the log ties to the replay-build fault fixed since; I didn't recheck that | Measured |
| No-work run repeated for one cell | 7 cells, 6 identical; one differs by one in a count | Measured |

To measure this properly: store a content-only state hash per row, as [incremental_evaluation.md](../../../../../research_notes/Faster%20score%20and%20roll%20back/incremental_evaluation.md) proposes.

## The sample

- **48 runs:** before 6, A 20, B 13, A2 4, B2 5, covering all 26 tasks. 1,229 points: 1,182 scored in these jobs, 26 reused from old per-step records, 20 by same state, 1 only in an old record.
- **Truly scored at every turn: 41 of the 47 runs with rows to the end.** The other six:
  - before validation: 10 reused, 14 same state;
  - A validation: 5 reused, 6 same state;
  - B2 validation: 6 reused;
  - A backup: 5 reused;
  - B backup: H = 26 has no record, since its row carries an error and `power_horizons.py` leaves it out;
  - B refactor: H = 10 only from an old record.
- **A hot reload is treated as a shorter run:** H = 0..23 in the per-run tables, with H = 23 as its end, and left out of everything using POWER_H. 22 points.
- **Labels in force, checked:** `sr-v4-afterB-p2-jwt` is fully replaced by `-r2`; A2's runs use only post-fix labels (`adminusers-r2`, `middleware-r3`, `tamper-r2`, `validation-r2`).

## What's measured and what's estimated

**Measured,** on these 48 runs:
- points kept, every error, every change count, the classifier's hit rates;
- truth agrees with `power_horizons.py --reward last-scored --rollback-rows`, run for each pair: the same scored points for all 47 full runs, and per-task gains equal to 1e-16 on the tasks whose before run is also in the sample;
- every 5 turns was recomputed by a separate script that imports neither `schedule_error.py` nor `power_horizons.py`: same points wrong (148), same total error (83.29).

**Estimated:**
- **Env-hours.** A skipped point saves scorer, save and undo: 30.4 s of the 42 s all-in, since the turn's replay and the job's start and end still happen ([measured_time_budget.md](../../../../../research_notes/Faster%20score%20and%20roll%20back/measured_time_budget.md)). "~32 left" is 2,708 points × 42 s. At the slow-period costs in that file, every saving could about double.
- **Weighting by each point's measured time** moves the hours by at most about 2: the scorer-kind rule saves 52% of point time against 56% of points, because kept turns are dearer. Same-state points are cheap: 17% of points but 10% of time.
- **The hours overlap with today's plan.** Dedup is already on for 68 of 85 pending lines, estimated at 5.8 h. So the scorer-kind rule with dedup, 13.7 h, adds about 8 h to that plan.

**Not known:** POWER_H error on all 26 tasks in all arms, since 82 runs have no every-turn truth.

## Caveats

- **This sample is what's validating the rules, and part of it tuned the classifier.** I adjusted the command patterns after looking at this data: fixing bugs, and to stop calling logins and JSON-parsing one-liners writes. Those changes aimed at turns needlessly kept, not at misses, but the read-only result is partly in-sample. The remaining 82 runs are a clean test: run the rule on them as they finish.
- **Six runs (156 points) store only a count, not a check list:** quarantine, search, constitution, token use, refactor, request id. There, "same list" means same count, so a swap of two checks would be invisible. The curve itself is unaffected, since it uses the same count.
- **Turn boundaries come from the transcripts,** which number tool calls, not turns, using `usage.csv` to place them. Against the raw logs' structure, 45 of 48 runs are exact, and the other 3 differ by a few calls within ambiguous stretches. Using the raw boundaries changes classes at 2 turns and none of the command rules' results.
- **Thin spots:** always-restart scorers have 2 runs. A2 has 4. The before arm has 6 tasks. Runs are one model on one environment: another model's habits, such as builds left running in the background, could change what a read-only turn does.
- **Truth has noise of its own.** `combined_filter_works` flips on an identical machine, so no schedule can be exact on it. A2 tamper's scores at H = 16–20 differ from its old record, and its count swings 0.54, 0.38, 0.85, 0.46 across H = 15–21. 12 points scored across machine pauses were kept.
- **Skipping removes the evidence.** A skipped point can't show the rule failed unless some are audited, which is why I'd keep auditing.

## To rerun

From WSL. It takes about 3 minutes on `/mnt/c`, and seconds with `POWER_V0_EXP` pointing at a copy in WSL:

```bash
python3 -I harness/schedule_error.py --json /tmp/schedule-error.json
python3 -I harness/test_schedule_error.py
```

The script reads exported records and `viz/run-v4-both.json`, and writes only the `--json` file. That file has every number here, per schedule and comparison, with the broken runs and why they broke. It holds check names and counts only, no scorer text or commands. As more runs finish, rerunning covers them with no change.
