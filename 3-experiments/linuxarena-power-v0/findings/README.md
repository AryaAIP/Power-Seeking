# Findings: what to read, by question

*Written 2026-11-05. Every report here comes from stored records, code or the literature unless it says otherwise. The folder's full list with each file's status is in [../README.md](../README.md); where the data behind them lives is in [data-map.md](data-map.md). Nov 5 reports are mostly one run per task and arm, so their task-level claims are judgment, marked as such in each.*

| Question | Read |
| --- | --- |
| **What does it all add up to, and what next?** | [nov5-what-power-looks-like.md](nov5-what-power-looks-like.md): the main session's synthesis |
| **What did the measurement find?** | [results-nov3.md](results-nov3.md): the design, the table, the audit, the caveats. Every 5 turns, under `last-scored` |
| **Why do the controls beat or match the power-seeking trajectories at low H?** | [nov5-causal-factors.md](nov5-causal-factors.md): each candidate cause against the records, and the experiment that would separate it |
| **How well do the Nov 5 conclusions hold up?** | [nov5-review.md](nov5-review.md): an independent attempt to refute them, a verdict per claim, and the strongest alternative story |
| **What exactly makes discounted power larger?** | [nov5-discounted-power.md](nov5-discounted-power.md): steps saved per test case, and how much of each gap comes from low H |
| **What does power mean, task by task?** | [task-power/](task-power/jwt_claims_wrong_field.md): one report per task (27), and `task-power/others/` for the other 56 main tasks (in progress). Tallies in [the Nov 5 log](../logs/2026-11-05-power-research.md); structured results in `../analysis/data/task_power.json` |
| **What do models do when they seek power here?** | [nov5-what-power-seeking-looks-like.md](nov5-what-power-seeking-looks-like.md): the 42 trajectories by category; the mismatch with what the tasks reward |
| **Did the solvers use the access they were left?** | [solver-power-use/](solver-power-use/afterB.json), one file per after arm; summary in [results-nov3.md](results-nov3.md), section 6 |
| **Which tasks would measure power better?** | [nov5-main-task-pool.md](nov5-main-task-pool.md): all 83 main tasks, task classes, three proposed sets. For the first 6 tasks: [superuser-audit.md](superuser-audit.md) |
| **Are side tasks a better measure?** | [nov5-side-tasks.md](nov5-side-tasks.md): categories and kinds of capability only |
| **What about other environments?** | [nov5-linuxarena-environments.md](nov5-linuxarena-environments.md): each environment, what power would mean there, a ranked comparison |
| **What do others do?** | [nov5-literature.md](nov5-literature.md) |
| **Where is everything?** | [data-map.md](data-map.md) |

## Files code reads or writes

- [score-corrections.json](score-corrections.json), [excluded-labels.txt](excluded-labels.txt): hand corrections and left-out labels, read by `power_horizons.py`.
- [power-horizons-v4.json](power-horizons-v4.json), [.txt](power-horizons-v4.txt) (pair 1), [v4b/](v4b/power-horizons-v4.txt) (pair 2), and `both/` once `tools/power.sh pages` has run: generated tables.
- [solver-power-use/](solver-power-use/afterB.json): read by the pages.

## Historical

- [results-night-1.md](results-night-1.md): the Nov 2 results, superseded by results-nov3.md.
- [old/](old/power-horizons-partial.json): the Nov 2 power computations.
- [ab-trajectories.md](ab-trajectories.md), [bottlenecks.md](bottlenecks.md): Nov 1 findings from the old runs.
