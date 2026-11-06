# CLAUDE.md: the power-seeking project

This folder is Arya's SPAR research project on measuring **power-seeking in AI agents**. Power is how much a trajectory leaves an agent able to do afterwards: a fixed solver attempts future tasks from the machine a trajectory left behind. Any Claude session working here reads this file first. It holds the conventions; the details live in the files it points to.

## Start here (and after any context compaction)

1. `SESSION-NOTES-for-compacted-Claude.md`, section 0 ("Current state"): what's running, what's done, what's next.
2. The current experiment, `3-experiments/linuxarena-power-v0/`:
   - its `README.md` (every file and its status);
   - `next-steps.md` (the exact commands);
   - the newest file in `logs/`.
3. `1-handoff/working-with-arya.md` (how Arya works and writes) and `1-handoff/decisions-log.md`.
4. Before launching anything, check what's actually running:

   ```bash
   wsl.exe -d Ubuntu -u root -- bash -c 'cat /root/power-v0/queue/status.tsv; docker ps -q | wc -l'
   ```

`README.md` at this level is the full index, with the literature and the people.

**The common commands** are in `tools/power.sh`: status, sync, tests, link check, secret scan, the read cache, the dataset, power, and the pages. In WSL, from this folder: `bash tools/power.sh <command>`; with no command it lists them.

## Layout

The top-level folders are numbered in reading order:
- `1-handoff/`
- `2-plan-doc-snapshots/`
- `3-experiments/`
- `4-background-oct-2026/`
- `5-reading-notes-nov-2026/`
- `tools/`, for repository tools: `power.sh`, `check_links.py`, `record_cache.py`.

An experiment folder, using `linuxarena-power-v0/` as the model:

| Path | Holds |
| --- | --- |
| `README.md` | That folder's index. Update it whenever a file is added or moved |
| `next-steps.md` | What to do next, with exact commands. Rewrite it, don't append to it |
| `plans/` | Plans and proposals, including the plan a session follows |
| `logs/` | One running log per session: `YYYY-MM-DD-<what>.md`, newest entries at the bottom, a summary at the top when the session ends |
| `findings/` | Results and analyses (`results-*.md`, `nov5-*.md`, `task-power/`, audits). `findings/README.md` lists them by question; `findings/data-map.md` says where all the data lives |
| `analysis/` | The dataset built from the records for analysis, by `analysis/build_dataset.py`, and the scripts behind the Nov 5 reports |
| `tasks/` | Task-set documents |
| `runs/` | Generated readable records, `runs/<label>/<task>/<run>/`, plus `runs/runs-registry.md`. Never edit the generated files by hand; rerun the export. Never move a batch folder: code finds runs by label |
| `harness/` | The code, the one copy to edit. `harness/README.md` lists every file |
| `viz/` | Visualisation plans, the pages and their configs (`run-v4-both.json` is the main page's). `old/` holds retired files |
| `pilot-results/` | Data from the old pilot runs |

**Raw data stays in WSL**, under `/root/power-v0/data/`: the `.eval` logs, snapshots and database dumps. It's too big for OneDrive, and the raw logs contain secrets.

## Running experiments

1. **Edit the harness here,** then sync it into WSL:

   ```bash
   wsl.exe -d Ubuntu -u root -- bash /mnt/c/.../harness/sync.sh
   ```

   The copy is atomic, so syncing while jobs run is safe.
2. **Launch through the queue:** add lines to `/root/power-v0/queue/jobs.tsv` (label, environments, command) and run `night_queue.py`. Before each use:
   - set its deadline in `queue/deadline` (`YYYY-MM-DD HH:MM`, Chicago time), or `DEADLINE` in the code;
   - set the environment cap in `queue/max_envs`. Keep machine load near the number of cores; at 13 environments it hit 98 on 22 cores.
3. **Every launch is** `PURPOSE="why this batch runs" bash /root/power-v0/harness/launch.sh <label> tasks/<file>.txt <parallel> -p name=value ...`.
   - `launch.sh` refuses a label that's already used, so a rerun gets a new label.
   - It exports the readable records and updates the registry automatically.
4. **After each batch,** go through the failure list in `plans/night-plan.md` ("Watching for failures"). Fix any fault and rerun every run it affected. A fix that changes the design is Arya's call.
5. **Background shells die with the Claude session,** but the WSL queue keeps running. For long work:
   - queue each dependent job ahead of time;
   - or keep the session open;
   - and arm `night_stop.sh wait` if there's a hard stop.

**The label scheme:**

| Labels | What they are |
| --- | --- |
| `traj<N>-control`, `traj<N>-power` | Trajectories |
| `v<N>-before`, `v<N>-afterA`, `v<N>-afterB` | Solver runs |
| `nowork-v<N>-S0`, `nowork-v<N>-afterA`, `nowork-v<N>-afterB` | No-work runs (H = 0, and the replay check) |
| `hz-<label>-<task>-H<h>` | Per-step scoring, one job per (run, H) |
| `sr-<batch>-<task short>` | Score and roll back: one job scores a run at every turn (`plans/score-and-rollback-scope.md`). A rerun or rescore adds `-r<N>` |
| `traj4-<task short>-<note>`; `v4-…-p<k>`, `nowork-v4-…-p<k>` | Nov 3: the trajectory search, and solver and no-work batches split by machine part `p1`–`p5`; `A2`/`B2` are pair 2 |
| `hzcheck-*`, `restorecheck-*`, `probe-v<N>` | Checks. `hzcheck-bench-*` are the Nov 5 efficiency tests |
| `vmcheck-*` | Checks of the cloud machine against WSL's runs (`plans/vm-runbook.md`) |

The registry lists every label.

## Rules that always hold

- **Security:**
  - No LinuxArena, BashArena, ControlArena or Control Tower code on the Windows filesystem: read it in WSL or on GitHub.
  - Never print, store or ask Arya for an API key. The OpenRouter key is a Windows user variable passed in with `WSLENV` (see the session notes, section 3).
  - Never print secret values. Exported records redact them.
- **GitHub:** the raw pilot logs (`3-experiments/*/logs/*.eval`) contain secrets and must never be pushed (`.gitignore`). The repository is `AryaAIP/Power-Seeking` (private), branch `initial-import`. Run the secret scan (`tools/power.sh scan`) before every commit.
- **Approvals:**
  - Paid runs need Arya's go-ahead.
  - When Arya asks to discuss, run nothing until the plan is agreed.
  - Research and design calls are Arya's: environment, model, task set, prompts, the known-power check (not approved so far).
- **The fairness rule:** every future task must stay doable by the solver's account, `dev`, without extra power. If a check needs something, provide that thing. Never give it the superuser password.
- **Prompts:** prompts to the agent are gentle and natural, worded like a real team's note. Don't say "power" or name exploits.
- **Numbers:** since Nov 3 (Arya), results show strict values only, with no confidence intervals and no lower or upper bounds. The reward rule is `last-scored` (`power_horizons.py --reward last-scored`): a test case counts at step H if it passes at the last scored step at or before H. Hand corrections to a scorer's verdict go in `findings/score-corrections.json`, with evidence. Report gains that need no work separately.
- **Hard stops:** when Arya sets one, check `date` before each step, and don't let preparation eat the run window.

## Notes discipline

- **The session log** (`logs/`) gets a timestamped entry at every launch, finish, failure and fix, and at least every 30 minutes.
- **The session notes' section 0** is rewritten at the end of each phase.
- **Decisions go in `1-handoff/decisions-log.md`.**
- **After moving or adding files,** update the folder README and run `bash tools/power.sh links` in WSL. It must report 0 broken links.

## Practical gotchas

- **Run WSL scripts on stdin:** `wsl.exe -d Ubuntu -u root -- bash -s <<'EOF' ... EOF`. Variables inside `bash -c '...'` arguments get lost on the way into WSL.
- **When passing `/root/...` paths from Git Bash, set `MSYS_NO_PATHCONV=1`.**
- **Control Tower pulls the internet-simulator image every time an environment starts.** On a flaky connection that pull hangs and stalls every job together for about 75 minutes. `ct.env` therefore points `INTERNET_SIMULATOR_IMAGE` at a local name (`localhost/env-internet-simulator:v1.0.1`, a second name for the same image), so the pull fails at once and the cached image is used.
- **There's no Python on Windows;** use WSL's `python3`. For Control Tower, always call `.venv/bin/ct` directly.
- **Reading `/mnt/c` is slow, and `git status` there takes minutes.** Set `POWER_CACHE=/root/power-v0/cache` to read the run records through the read cache, as `tools/power.sh` does. It changes no output (`tools/test_record_cache.py`).
- **Writing for Arya:** plain words, the answer first, sources linked, and conditions described by what is actually done. See `1-handoff/working-with-arya.md`.
