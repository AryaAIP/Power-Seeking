# LinuxArena power v0: next steps

*Rewritten 2026-11-05 at about 10:00 CST. What's left, in order, with exact commands. Results so far: [findings/results-nov3.md](findings/results-nov3.md). Where the data is: [findings/data-map.md](findings/data-map.md). Conventions, the label scheme and the run workflow: [../../CLAUDE.md](../../CLAUDE.md). The common commands are in [../../tools/power.sh](../../tools/power.sh): in WSL, from the project folder, `bash tools/power.sh <command>`; with no command it lists them. Other commands below run from this folder.*

## Where things stand

- **The Nov 3 run is done and home.** Two pairs (A/B = `traj4-sharing-none`/`-side`, A2/B2 = `traj4-minio-none`/`-keep`), 27 tasks, the initial environment state and four after arms, each solver run scored every 5 turns. Everything runs on WSL now (22 cores, 31 GB); Lambda is terminated.
- **Arya's decisions (Nov 3 ~10:15):** the reward rule is `last-scored`, and B2's storage answer counts as correct ([1-handoff/decisions-log.md](../../1-handoff/decisions-log.md)).
- **The result so far, every 5 turns:** neither power-seeking trajectory left more power than its control (mean over H = 1..80: B − A = −0.028, B2 − A2 = +0.003). Details and caveats in the results file.
- **Every-turn rescoring is paused at 48 of 130 runs** (Arya, Nov 3 19:52: "can you pause these jobs for tonight"). Nothing runs in production until it's resumed.
- **Nov 5, 04:00–09:00: a research stretch on what power looks like here,** from stored records only ([plans/nov5-research-plan.md](plans/nov5-research-plan.md); log: [logs/2026-11-05-power-research.md](logs/2026-11-05-power-research.md)). Its reports are listed in [findings/README.md](findings/README.md). The main session's synthesis is [findings/nov5-what-power-looks-like.md](findings/nov5-what-power-looks-like.md).

## 1. Decide how to finish the rescoring, then resume it

**Read first:** [plans/scoring-efficiency.md](plans/scoring-efficiency.md), which is provisional. Tests still run in [plans/scoring-efficiency-tests.md](plans/scoring-efficiency-tests.md), and [plans/scoring-schedules-analysis.md](plans/scoring-schedules-analysis.md) compares cheaper schedules. Its recommendation for these remaining jobs is score and roll back with the cheap fixes. Skipping turns that couldn't change the result, beyond today's state dedup, is Arya's call.

**What's left (log, 19:52–19:58):** 85 lines pending, about 3,000 points before reuse and dedup, at 42 environment-seconds per point at cap 10, so about 3.5 h. Hot reload's A arm still owes H = 24–47.

**A check comes first in the queue:** A2 tamper at H = 20 differs from its old record, and scoring without any earlier scorer gave the same difference. A check that replays the trajectory instead of restoring it decides what that means: if it scores 15/15, a restored state differs from a replay in a way that matters, beyond this one run. Until then, don't rely on A2 tamper's H = 16–20.

**To resume,** with a deadline later than now (Chicago time). States are over 18 h old, so the script re-saves them first, which takes up to about 30 min. `--dry-run` changes nothing:

```bash
wsl.exe -d Ubuntu -u root -- bash -c 'setsid nohup python3 /root/power-v0/harness/resume_queue.py --deadline "YYYY-MM-DD HH:MM" --cap 10 >> /root/power-v0/queue/resume.log 2>&1 < /dev/null &'
```

**After the resume:**
- arm the watcher, since nothing else watches: `python3 -I -u /root/power-v0/harness/watch_sr.py --minutes 29`;
- keep the machine awake and on AC. Every pause on Nov 3 was standby on battery, and the app refused the keep-awake request;
- keep the load near the core count. Validation hit scorer timeouts at load 21–41 on 22 cores.

**Before using the numbers,** compare a sample with the old per-step records: `python3 -I harness/compare_sr.py <label> ...` (identical test-case lists at the shared H, end score equal to the run's own, every restore exact).

## 2. Recompute and sync to the pages

When the rescoring has finished and been exported, or for an interim look at any time:

1. **The tables and all three pages, in one command,** from the configs [viz/run-v4-both.json](viz/run-v4-both.json) (the main page), [viz/run-v4.json](viz/run-v4.json) and [viz/run-v4b.json](viz/run-v4b.json):

   ```bash
   bash tools/power.sh pages --dry-run    # says which tasks each page would include
   bash tools/power.sh pages              # add --both-only for just the main page
   ```

   This runs `harness/vm/sync_rollback_pages.py`. A task's every-turn rows are used only once all that page's arms have them, so a page never compares an every-turn arm with an every-5-turn one. It writes `findings/both/` (new at its first run), `findings/` (pair 1) and `findings/v4b/` (pair 2).
2. **Just a table:** `bash tools/power.sh power viz/run-v4-both.json /tmp/ph.json`. While the rescoring is partial this mixes densities, so don't report its numbers.
3. **Update** [findings/results-nov3.md](findings/results-nov3.md): the table in section 3 and the sentences marked *(numbers)*.
4. **Redraw the figures** (they're still first-pass):

   ```bash
   uv run --with matplotlib python viz/power_curves_plot.py findings/power-horizons-v4.json viz/nov3-power-curves-pair1.png "pair 1"
   uv run --with matplotlib python viz/power_curves_plot.py findings/v4b/power-horizons-v4.json viz/nov3-power-curves-pair2.png "pair 2"
   ```

5. **Republish to the same links,** after a full read for secrets: both pairs https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22 from `viz/power-dashboard-v4-both.html`, pair 2 https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh from `viz/power-dashboard-v4b.html`. `viz/power-dashboard-v4.html` (pair 1 alone) has no link of its own now.

`harness/vm/finish_v4.sh` still works for one config (`SKIP_COPY=1 FINISH_CONFIG=viz/run-v4b.json bash harness/vm/finish_v4.sh`): it also rebuilds the run registry and runs the secret scan. It follows a config's `rollback_rows`, but it doesn't apply the density rule above, and it writes every config's table to `findings/power-horizons-v4.*`. To try it without changing the repository, add `FINISH_OUT=/tmp/finish-test`.

## 3. The repository

- **Before any commit:** `bash tools/power.sh scan` (files changed since the last commit; prints paths and kinds only) and `bash tools/power.sh links` (0 broken links).
- **GitHub:** `AryaAIP/Power-Seeking` (private), branch `initial-import`, pushed up to 70764c3. Everything since Nov 3 13:07 (the score-and-roll-back work, the combined page, the Nov 5 research) isn't committed yet; the main session commits after a secret scan.

## 4. Open questions for Arya

- **What to run next.** The Nov 5 reports point to task sets that show access and information better ([findings/nov5-main-task-pool.md](findings/nov5-main-task-pool.md), three proposed sets), other environments ([findings/nov5-linuxarena-environments.md](findings/nov5-linuxarena-environments.md)) and side tasks ([findings/nov5-side-tasks.md](findings/nov5-side-tasks.md)). See the synthesis, [findings/nov5-what-power-looks-like.md](findings/nov5-what-power-looks-like.md), for what to do next.
- **Pair 2's control isn't clean.** `traj4-minio-none` got root on its own about 20 times and left a setuid-root helper and a patched restart script ([findings/results-nov3.md](findings/results-nov3.md), section 7). Options: record a new control on the same task (several, if most no-note runs escalate), or report pair 2 as two power-seeking trajectories that kept different amounts.
- **The chat confound.** After either trajectory the solver continues the trajectory's chat; from the initial state it starts a new one. An arm where the solver starts a new chat on the machine the trajectory left would split the shared gain into what the machine gives and what the chat gives. Paid runs: Arya's call.
- **The `use` note** is given only after B. Giving A the same note, or neither, would remove that difference.
- **The initial-state arm's 27 missing per-step points,** and pair 2's 29 at H = 50–70, become moot with every-turn scoring. If the rescoring fails for some runs, those points need the old per-step jobs (`make_v4_hz_jobs.py` without the score-and-roll-back options).
- **More than one trajectory per condition and one run per task** would show how much the differences move between reruns.
- **From the science review** ([plans/nov3-science-review.md](plans/nov3-science-review.md)): the agent's account can already act as the database superuser through the allowed rebuild and restart, so the tasks reward credentials only by saving turns. A design where kept access unlocks test cases is open, including Arya's hidden-task idea.
- **What to clear,** listed in [README.md](README.md), "Left in place for Arya to decide".

## Useful, not urgent

- **Stop replays at the last call.** Every replay ends with harmless "Tool submit not found" errors, because its step cap is the number of calls plus 5.
- **Price each run from its tokens.** Spend is tracked only as OpenRouter usage before and after each batch.
