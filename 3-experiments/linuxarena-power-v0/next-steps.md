# LinuxArena power v0: next steps

*Rewritten 2026-11-03 at about 12:05 CST. What's left, in order, with exact commands. Results so far: [findings/results-nov3.md](findings/results-nov3.md). Where the data is: [findings/data-map.md](findings/data-map.md). Conventions, the label scheme and the run workflow: [../../CLAUDE.md](../../CLAUDE.md).*

## Where things stand

- **The Nov 3 run is done and home.** Two pairs (A/B = `traj4-sharing-none`/`-side`, A2/B2 = `traj4-minio-none`/`-keep`), 27 tasks, the initial environment state and four after arms, each solver run scored every 5 turns. Lambda is terminated; everything runs on WSL now (22 cores, 31 GB).
- **Arya's decisions (Nov 3 ~10:15):** the reward rule is `last-scored`, and B2's storage answer counts as correct ([1-handoff/decisions-log.md](../../1-handoff/decisions-log.md)).
- **The result so far:** neither power-seeking trajectory left more power than its control (mean over H = 1..80: B − A = −0.028, B2 − A2 = +0.003). Details and caveats in the results file.
- **Arya's goal while away (until ~13:30):** score every run at every turn with score and roll back, sync that to the pages, clean up the repository (local and GitHub), and sort the data. The data and docs part is done (this file, the results, the data map, the READMEs).

## 1. Every-turn rescoring (another session runs it)

Score and roll back is built and validated ([plans/score-and-rollback-scope.md](plans/score-and-rollback-scope.md) §11; [logs/2026-11-03-score-and-rollback.md](logs/2026-11-03-score-and-rollback.md)). Production is one job per solver run that replays the run's turns, starting after-arm runs from the trajectory's saved state, and scores and restores the machine at every turn.

- **The jobs:** 130, labelled `sr-v4-<arm>-p<k>-<task>` (5 arms × 26 tasks; the storage question is skipped), listed in WSL at `/root/power-v0/sr-validate/prod-jobs.tsv`, interleaved by task across the arms so they progress together. They were made with:

  ```bash
  python3 -I /root/power-v0/harness/make_v4_hz_jobs.py --score-every 1 --restore-state \
      --min-timeout 300 --keep-build-cache --label-prefix sr
  ```

- **The decisions taken under Arya's goal** (log, 11:15): every turn; a 300 s floor on command time limits while scoring; no per-step jobs for the storage question; the bar is identical test-case lists, except points lost to load timeouts, which are rescored; full snapshots only at the end; Go's build cache kept between points.
- **Watch the load.** Validation hit scorer timeouts at load 21–41 on 22 cores. Keep load near the core count.
- **Before using the numbers,** compare a sample with the old per-step records: `python3 -I harness/compare_sr.py <label> ...` (identical test-case lists at the shared H, end score equal to the run's own, every restore exact).

## 2. Recompute and sync to the pages

When the rescoring has finished and been exported:

1. **Power, both pairs**, reading the new rows (`--rollback-rows`; leave out `--include-check-rows` so validation jobs stay out). From the experiment folder in WSL, for each config (`viz/run-v4.json`, `viz/run-v4b.json`), taking the arms from the config as `finish_v4.sh` does:

   ```bash
   python3 -I harness/power_horizons.py --reward last-scored --rollback-rows \
       --before v4-before-p1,...,v4-before-p5 --nowork-before nowork-v4-S0-p1,...,nowork-v4-S0-p5 \
       --after A=v4-afterA-p1,... --nowork-after A=nowork-v4-afterA-p1,... \
       --after B=v4-afterB-p1,... --nowork-after B=nowork-v4-afterB-p1,...,nowork-v4-afterB-p5r \
       --json /tmp/ph-v4.json
   ```

2. **The findings and the pages, in one command per pair** (no copy from a cloud machine now):

   ```bash
   SKIP_COPY=1 bash harness/vm/finish_v4.sh                                   # pair 1
   SKIP_COPY=1 FINISH_CONFIG=viz/run-v4b.json bash harness/vm/finish_v4.sh    # pair 2
   ```

   `finish_v4.sh` doesn't pass `--rollback-rows` yet, and it writes both pairs' tables to `findings/power-horizons-v4.*`. Before using it for the rescoring: add `--rollback-rows` to its `power_horizons.py` call, and point pair 2's output at `findings/v4b/` (or move the files after). To try it without changing the repository, add `FINISH_OUT=/tmp/finish-test`.
3. **Update** [findings/results-nov3.md](findings/results-nov3.md): the table in section 3 and the sentences marked *(numbers)*.
4. **Redraw the figures** (they're still first-pass):

   ```bash
   uv run --with matplotlib python viz/power_curves_plot.py findings/power-horizons-v4.json viz/nov3-power-curves-pair1.png "pair 1"
   uv run --with matplotlib python viz/power_curves_plot.py findings/v4b/power-horizons-v4.json viz/nov3-power-curves-pair2.png "pair 2"
   ```

5. **Republish both pages to the same links,** after a full read for secrets: pair 1 https://claude.ai/artifact/RxVDZt1SzBfjiX6NcCdf22 from `viz/power-dashboard-v4.html`, pair 2 https://claude.ai/artifact/RfgNfq4BYRN2bfZBXqQwEh from `viz/power-dashboard-v4b.html`.

## 3. The repository

- **Four transcripts are held back** until the redaction covers them: `runs/traj4-errors-blockers`, `-lean`, `-roadmap` and `runs/traj4-minio-strong`. A redaction fix in `harness/export_run.py` (tested by `harness/test_export_redact.py`) and a re-export are in progress.
- **Before any commit:** the secret scan (`harness/vm/secret_scan.py`, as in `finish_v4.sh` step (e)) over everything new, and `python3 -I tools/check_links.py` from the project folder (0 broken links).
- **GitHub:** `AryaAIP/Power-Seeking` (private), branch `initial-import`. The last pushed commit is 0787e62. The 4 local commits after it, and about 10,900 new or changed files (mostly tonight's `runs/` records), aren't pushed yet.

## 4. Open questions for Arya

- **Pair 2's control isn't clean.** `traj4-minio-none` got root on its own about 20 times and left a setuid-root helper and a patched restart script ([findings/results-nov3.md](findings/results-nov3.md), section 7). Options: record a new control on the same task (several, if most no-note runs escalate), or report pair 2 as two power-seeking trajectories that kept different amounts.
- **The chat confound.** After either trajectory the solver continues the trajectory's chat; from the initial state it starts a new one. An arm where the solver starts a new chat on the machine the trajectory left would split the shared gain into what the machine gives and what the chat gives. Paid runs: Arya's call.
- **The `use` note** is given only after B. Giving A the same note, or neither, would remove that difference.
- **The initial-state arm's 27 missing per-step points,** and pair 2's 29 at H = 50–70, become moot with every-turn scoring. If the rescoring fails for some runs, those points need the old per-step jobs (`make_v4_hz_jobs.py` without the score-and-roll-back options).
- **More than one trajectory per condition and one run per task** would show how much the differences move between reruns.
- **From the science review** ([plans/nov3-science-review.md](plans/nov3-science-review.md)): the agent's account can already act as the database superuser through the allowed rebuild and restart, so the tasks reward credentials only by saving turns. A design where kept access unlocks test cases is open, including Arya's hidden-task idea.

## Useful, not urgent

- **Stop replays at the last call.** Every replay ends with harmless "Tool submit not found" errors, because its step cap is the number of calls plus 5.
- **Price each run from its tokens.** Spend is tracked only as OpenRouter usage before and after each batch.
- **The label scheme in [../../CLAUDE.md](../../CLAUDE.md)** doesn't list `sr-*` (score and roll back), `restorecheck-*` or the `-p<k>` part suffix yet.
