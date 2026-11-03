# Reading runs: scope for transcript, log and data views

*Written 2026-11-01 (night) by the visualisation side agent, for [night-plan.md](../plans/night-plan.md) and changes 3, 6, 8 and 9 in [proposed-changes.md](../plans/proposed-changes.md). Status: scope only. Nothing is built, and Arya decides. I read `traj-gentle.eval` in WSL, Control Tower's docs and code in WSL, and the web pages linked below. Anything marked [my judgment] is my own view.*

## Built since: the results page (Nov 2, evening)

- **[power-dashboard.html](power-dashboard.html), "Power experiment results":** the Nov 2 numbers as one self-contained page (data embedded, works offline, phone width, light and dark). It has a glossary, the setup, the headline gains for A and B minus before and B minus A with 95% intervals, the POWER_H and gain curves, one chart per task, a check grid for any arm and task, the runs table and the data gaps. It is not the run reader sketched below: it has no step lists or transcript text. Not published yet; Arya reviews and publishes.
- **[build_dashboard.py](build_dashboard.py)** writes it from `runs/`, taking every number from `harness/power_horizons.py`. It checks the page against that script's printed output and refuses to write if it finds a secret-looking string. Rerun it in WSL after new per-step scores are exported (the command is in its docstring); nothing needs editing.
- **Added later on Nov 2 (Arya's follow-ups):**
  - A γ slider (0.80 to 1.00), with the earlier pilot page's sections redone on the horizon data: power by task at the chosen γ, how the answer depends on γ, steps used, gain with no work done, and "How to read this". The browser recomputes the discounted gains and their bootstrap intervals from the embedded per-task curves. At γ = 0.90, 0.95 and 0.98 the page checks itself against `power_horizons.py`, and the build runs the same check in node.
  - A smooth view, the default: each band's midpoint is drawn with monotone cubic interpolation through the scored turns, with dots where turns were scored. An "Exact steps" toggle switches every H chart back to the step drawing.
  - The formula page's rule (`power_horizons.py`'s `REWARD = "first-pass"`): a check counts once it has first passed. The page adds a step-budget slider (H = 1 to 80, the page's option 1), marks H on the power and gain curves, and labels each headline number with its option. The check grid marks checks that count because they passed earlier. The browser bootstrap is a copy of Python's generator, so its intervals equal `power_horizons.py`'s.

- **Nov 3:** the confidence intervals are removed (one trajectory of each kind and one run per task, so the page shows none; the build checks values only). The page now opens with a plain account of the experiment for readers with no context (the notes quoted from `harness/power_v0.py`), uses plain names throughout, and ends with a "Trajectories and runs" viewer: a vertical timeline of each trajectory or run, with the actions that sought or gave power (from each run's `power-actions.json`) beside the tests passed by each turn. The "Every run", "Data gaps" and "How to read this" sections are gone.
## Short answer

**My recommendation [my judgment]** comes in two parts.

1. **For Arya alone, now, and free: use Inspect's own viewer.** That is the web page Inspect ships for reading its `.eval` logs, run in WSL. Nothing to build, and it shows everything exactly, including the raw request sent to the model and the raw reply. Use it to check that other views are faithful. Don't share it, because it shows the database passwords.
2. **To read runs together with Matthew, build one "run reader" page.** It's a Claude artifact, like the dashboard. It has one row per step, a grid showing which checks pass at each scored horizon, the power-step labels, the machine changes, and a mode that puts two runs side by side. It's fed by a redacted export made in WSL. This is about 7 to 9 hours of work (estimate).

**Hold off on Docent for now.** It would upload unredacted logs to a third party, and its search features make model calls. It's worth another look when there are about 30 tasks and too many runs to read by hand.

**One decision comes first: what counts as a "step"?** In `traj-gentle`, the step cap counted 49 model turns, but the agent made 63 tool calls, because 13 of its 50 turns made more than one call. The current transcripts number steps by model turn, while change 1 scores "after each tool call". The reader page and the horizons H must use the same step, so this is Arya's call.

## Options side by side

| Option | What it shows | Effort | Can Matthew get it? | Privacy | Offline on the laptop | For | Against |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Inspect viewer** (`inspect view`, in Control Tower's environment in WSL) | Each run's messages: the system and task prompts, reasoning, tool calls and outputs. Also every logged event (each recorded happening: a model call, a tool call, a command, the scoring), with the raw request and reply, token use and the scorer's list of checks | None. It's installed (inspect-ai 0.3.171) | Not directly. Sharing means sending him the `.eval` file, or a bundle (next row) | Shows everything, passwords included | Yes. It's a local web server in WSL, opened in the Windows browser | Exact and complete. Answers "exactly what goes in and out". Good for checking the other views | No per-step check results, no labels, no side-by-side. It's slow to scan 60 to 80 steps, and he can't paste it into Claude |
| **Inspect static bundle** (`inspect view bundle --output-dir …`, which exists in 0.3.171) | The same as above, as a folder of web files | Low: one command, plus somewhere to host it | Only once it's hosted somewhere (GitHub Pages, S3, Netlify, Hugging Face). It needs a web server that supports "range requests" (fetching part of a file), so opening it straight from disk won't work ([Inspect docs](https://inspect.aisi.org.uk/log-viewer.html)) | Everything in the log goes up. We'd have to write redacted copies of the `.eval` files first | Only with a local server | Matthew sees exactly what Arya sees | Hosting raw logs, and redacting `.eval` files reliably is fiddly. The same gaps as the viewer |
| **Docent** (Transluce's hosted tool, with uploads built into Control Tower: `ct docent upload`) | A transcript viewer for many runs at once, with search and sorting by model-written criteria, and shared collections | Low: an account, an API key, one upload command | Yes: `ct docent collaborator-add <email>` (Control Tower's `docs/docent.md`) | Weak. Control Tower's uploader (`trajectories/docent/upload.py`) has no redaction, so whole logs go to Transluce's servers. Its search features call model providers. Self-hosting is "not a generally supported path" ([Docent docs](https://docs.transluce.org/self-hosting), seen in search results only) | No | Built for exactly this. It scales to hundreds of runs | Privacy. Its features make model calls (Arya caps runs). Too much tool for 2 to 20 runs. No per-step check results |
| **Inspect Scout** (open-source "scanners" over Inspect logs) | Steps that match a rule, such as a text pattern ("grep scanner", no model calls) or a model's judgment | Medium | Its results could go into the page below | Local. Its model-judged scanners send text to a provider | Yes, for pattern scanners | Could suggest candidate power steps automatically when there are many runs ([Inspect Scout docs](https://meridianlabs-ai.github.io/inspect_scout), seen in search results only) | It flags steps but isn't a reading view. Not needed for 2 trajectories |
| **Control Tower's own viewers** (the `ct traj tui` terminal view, and its private and public viewer websites) | Trajectories in LinuxArena's own format | High: the websites need MongoDB and a JavaScript build | No | Unredacted | WSL only | Already knows LinuxArena's format | Heavy. It runs LinuxArena code, which has to stay in WSL. Built for their datasets, not ours |
| **Generated markdown transcripts** (`dump_run.py`, change 3, being built tonight) | A header, the prompts, then every step: reasoning, the call and its output | Already being built. Redaction would add about 1 hour | Yes. It's plain text, so he can paste it into his Claude | **The current ones contain database credentials.** `runs/traj-gentle/transcript.md` and `runs/traj-neutral/transcript.md` have `PGPASSWORD`, `postgres://` and `.pgpass` lines in them. Redact them before sharing | Yes | Plain text, easy to copy and quote. Also works as the input to Claude | Long (127 to 150 KB each). No pass/fail picture, no side-by-side |
| **Run reader page** (recommended: a Claude artifact, or the same HTML opened locally) | One row per step. Each step's reasoning and output open on demand, with the hand-over point marked. A grid of checks by scored horizon. Labels. Machine changes. Two runs side by side | About 7 to 9 hours (estimate, steps below) | Yes. The artifact is shared with his Gmail, and the redacted JSON behind it can be pasted into Claude | Only what the export writes, redacted in WSL before anything leaves. The artifact lives on claude.ai and is private until shared | The artifact needs internet. The same file opened locally works offline if its data is built in | Shows the things Matthew asked for: in and out, the power step, a run that takes power next to one that doesn't | Build time, and the redaction has to be right. For exact raw requests it links back to the Inspect viewer instead of repeating them |

**Parts of the run reader page.** Each could also be built on its own.

| Part | Shows | Effort (estimate) | For | Against |
| --- | --- | --- | --- | --- |
| Two runs side by side | Two step lists in columns, with their check grids lined up by H. Pairs: trajectory A and B, or the before and after runs of one task (change 8) | About 1.5 h | Matthew's "one that takes power, one that doesn't" | Step k of one run and step k of another usually do different things. Lining them up by step number only makes sense for the check grids |
| What changed on the machine | Changes by section, from `compare_snapshots.py` (which already exists): users, sudo rules, set-user-ID files (programs that run with their owner's rights), cron jobs (scheduled commands), Go module cache, files, database roles and rows, storage | About 1 h | Gives change 6's labels something concrete to point to | Only at scored horizons, not every step. The `credentials_file` and `db_url_found` sections hold secrets, so show only "changed" or "unchanged" for those |
| Labels on power-relevant steps | Change 6's labels, such as "read the superuser database password (step 14)", taken from `runs/traj2-*/labels.md` | About 0.5 h | Marks the step where power was taken, as Matthew asked | Labels are added after measuring and must never feed the number (change 6) |

## What the data looks like (checked on `traj-gentle.eval`)

An `.eval` file is a zip archive holding `header.json` and one `samples/<task>_epoch_1.json`. Inspect calls each run of a task a "sample".

**Per step, from the messages:**
- the model turn number, and any visible text;
- the reasoning text, not marked redacted: 72,503 characters in all, against 16,290 reasoning tokens billed;
- the tool calls (`bash` with `cmd`, or `submit`);
- each tool's output and error field. Outputs total 188,205 characters, the longest 16,515.

**Per step, from the events:**
- a timestamp and working time for every call;
- token use for every model call: input, output, tokens read from the cache, and reasoning;
- the raw request and reply (`call.request`, `call.response`, including the provider).

The 118 `sandbox` events are commands run by the harness and the scorer, not by the agent.

**Per run:**
- **From the log:**
  - the header: model, inspect_ai 0.3.171, Control Tower version, run arguments;
  - the task, scorer and environment descriptions;
  - the scorer's list of passed and failed checks, by name.
- **`meta.json`:** label, trajectory, step cap, provider, `dev_setup`, instruction, `solver_first_message_index` (where an after run's own part begins), tool-call count and `ended_by`.
- **`snapshot.txt`** (about 4.8 MB) and **`db_s3.txt`:** the machine sections listed in the parts table above, plus database roles, row counts and tables.
- **Soon, `horizons.csv`:** H, check, pass or fail.

**Size.** The zip is 3.5 MB, but the sample unpacks to 19.4 MB, because every model event repeats the whole chat so far. The page should be built from the messages. The events are only needed for spot checks.

**Secrets.** I counted these without printing them. In this one log, `TEST_DATABASE_URL` appears 475 times, `PGPASSWORD` 351 times and `.service-credentials` 817 times, most of them repeats inside the raw requests. There's no OpenRouter key: there are 0 matches for `sk-or-` or `OPENROUTER`, and the only extra request header is `x-irid`.

## Sketch of the recommended page

The numbers below are made up, for layout only.

```
Run: [traj2-power ▾]  Compare with: [none | traj2-control | v2-before/<task> ▾]   [ ] reasoning  [ ] labelled steps only
traj2-power · RBAC task · trajectory · account dev · DeepSeek via OpenRouter · ended by submit · 63 calls / 49 turns · 23 of 26 checks
▸ System prompt   ▸ Task prompt   ▸ Hand-over note (after runs)          ← exact text, redacted

Checks by horizon        H=0   20   40   60   end      (filled = passes; a check that breaks shows the break)
  Go binary builds        ·    ■    ■    ■    ■
  Admin can list models   ·    ·    ■    ■    ■
  …                                                      Δ_H curve beside the grid

Step  Turn  Call                               Output             Label
 13    11   bash: env | grep -i …              312 chars          
 14    11   bash: psql "[REDACTED: superuser]" 1.2k chars         ● read the superuser database password   ← power step
        ▸ reasoning (392 chars)   ▸ full output   ▸ raw request in the Inspect viewer
 ── H=20 scored: 9 of 26 checks · machine since H=0: +1 database role, sudo rules unchanged, Go cache +38 modules ──
```

With "Compare with" set, the page shows the two runs' grids and step lists in two columns.

## Steps to build it (estimates)

1. **Arya decides (10 minutes):**
   - what one step is: a tool call or a model turn;
   - whether Matthew sees the prompts in full;
   - artifact only, or a local file as well.
2. **An export script in WSL (1.5 to 2 hours).** It reads the `.eval` with `inspect_ai`, plus `meta.json`, `horizons.csv`, `labels.md` and `compare_snapshots.py`'s output, and writes one redacted JSON per run. Only that redacted JSON comes into this folder; the `.eval` files stay in WSL. It lives in `harness/` and is synced to WSL by `sync.sh`.
3. **Redaction that fails safe (1 hour).**
   - Read the actual secret values inside WSL: `TEST_DATABASE_URL`, `.pgpass`, the credentials file.
   - Replace every occurrence, plus pattern matches (`postgres://user:…@`, `PGPASSWORD=…`), with a named placeholder.
   - Then search the output for the known values, and refuse to write it if any remain.
   - Run the same redaction on the markdown transcripts.
4. **The page (2 to 3 hours):** the header, the prompts, the check grid, the step list and the labels.
5. **Side-by-side mode (1.5 hours).**
6. **The machine-changes panel (1 hour).**
7. **Publish and check (30 minutes).**
   - Publish as an artifact, linked from the dashboard, and shared with Matthew once Arya says yes.
   - Arya checks it by hand, with a short checklist.
