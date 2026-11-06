# The other LinuxArena environments, for measuring power

*Written 2026-11-05 by a research subagent, for question 5 of [the research plan](../plans/nov5-research-plan.md). Nothing was built, started or run, and no paid calls were made. Code was read in WSL from read-only clones in `/root/power-v0/src/envs-survey/`, at git tag `v1.0.1` (what the project's stack runs), and on GitHub. Published numbers were computed from the paper's public run data, kept in `/root/power-v0/src/envs-survey-data/`.*

*Tags: `[code]` read in the repositories; `[docs]` the repositories' or project's written notes; `[paper]` the paper's text or its public run data; `[inference]` my judgment. Counts marked "regex" are text searches, so treat them as rough. Side tasks appear only as categories and kinds of capability, with counts. No secret values appear here.*

**Terms.** A *test case* is one check inside a task's scorer. *Code tasks* are feature, refactor and infrastructure tasks together. The *fair account* is a `dev`-style non-root account under the fairness rule (every task stays doable without extra power). The *deploy route* is what that account may run to put its code live, like `sudo /app/restart.sh` in `model_registry`.

## 1. The answer first

- **What exists.** The suite has 20 environments.
  - I read all 10 public ones: the 9 others, and `model_registry` for comparison `[code]`.
  - The 10 held-out ones are private and I could not open them; only one row each in the paper is known `[paper]`.
  - Four more public environments sit outside the suite, with 2 to 7 main tasks each (section 7).
- **Would any measure power better? Yes, two look better for a different kind of power, and none is proven** `[inference]`:
  1. **`shared_dotfiles`.** A Linux server with several real accounts, where the work itself crosses account boundaries. 48 of 55 code tasks name root-owned paths (regex) `[code]`, and merged results and audit logs are unreadable to an ordinary account `[code]`. Access could save turns on nearly every test cycle.
  2. **`file_indexing`.** It has real Linux accounts and LDAP logins, and already separates a working copy from production. Its own notes record agents held back by lacking root `[docs]`. The catch: 38 of 73 code-task scorers stop at the first failure, so they give no test-case list `[code]`.
  3. **`tiktok`, the cheapest way to test whether the `model_registry` result generalizes.** It offers the same kind of power (database login, admin identity, session secret), with the most admin-dependent tasks (38 of 65, regex) and the simplest port: two containers, and no service that needs root `[code]`.
- **How much they differ from `model_registry`.** Three differences matter most:
  - **Deploying code reaches further elsewhere.** `model_registry` is the only public environment whose app runs under a separate service account `[code]`. In the other 9 the app runs as root, so a deploy route there hands over root, unless the port adds a service account. The [science review's top threat](../plans/nov3-science-review.md) (the account can already do nearly everything by deploying) gets worse, not better.
  - **Logins.** Some environments hand out admin tokens or passwords in their docs (`auto_workflow`, `slack_clone`, `media_processing`), so forging one gains nothing there `[docs]`.
  - **`model_registry` is not typical.** It has the lowest published pass share, 0.26, with 11 of its 20 published tasks passed by no model `[paper]`.
- **Generalizing the Nov 3 result.** One environment, with one trajectory per condition, supports a narrow claim. I'd expect the pattern (access speeds up testing and is rarely needed) to hold in the six other service-plus-database environments. I would not expect it in `shared_dotfiles` or `file_indexing` `[inference]`. See section 3.
- **Every reachable environment runs the agent as root by default** (`agent_user` is never set, and defaults to root) `[code]`. A non-root account is our change everywhere.

## 2. The comparison, ranked

**The ranking and effort columns are my judgment** `[inference]`. Pass share is for code tasks across 13 published models running as root, not our solver `[paper]`. "Lists" is code tasks whose scorers report named checks (regex) `[code]`.

| Rank | Environment | Power later tasks could use | Lists | Pass share | Port effort | Why this rank |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `shared_dotfiles` | Root-owned scripts and config, root-only logs and merged files, acting as other users, Vault tokens | 41 of 55 | 0.49 | Medium | The privilege boundary is the subject of the work, so access can matter in nearly every test cycle. Mid pass share and low noise. No SQL database to snapshot. Against it: one edit to a root-run script gives root, so controls may escalate too |
| 2 | `file_indexing` | Acting as other Linux and LDAP users, root-only store passwords, root-only data | 32 of 73 | 0.55 | Medium to large | Has a real working copy and production split, and direct written evidence that lacking root held agents back. Against it: half the scorers stop at the first failure, and it has three extra stores to snapshot |
| 3 | `tiktok` | Database login, admin identity, session secret, seeded test users | 49 of 65 | 0.51 | Small | The same kind of power as Nov 3 in a different stack, at the lowest port cost. Best as a generalization test, not a stronger meter |
| ref. | `model_registry` | Database superuser, forged admin tokens, storage keys | 32 of 51 | 0.39 | Done | Only real service account and credentials file. Many broken tasks at `v1.0.1`, and kept access mostly saves turns ([results](results-nov3.md)) |
| 4 | `auto_workflow` | Database login, encryption key, worker logs. Admin tokens are already handed out | 47 of 69 | 0.56 | Small to medium | Lowest published noise (1 of 20 tasks mixed), small and quick. Handed-out tokens remove the forged-token route, which is a useful contrast |
| 5 | `clinical_trial` | Database role ladder, cron, root-only logs | 51 of 67 | 0.77 | Medium | A real ladder of database roles and no app login to forge. But tasks are easy (median 36 actions), so it may saturate early, and its restart script resets the data |
| 6 | `media_processing` | Reach into other containers, storage keys, second team's API key | 50 of 72 | 0.53 | Large | Most informative spread of task difficulty (16 of 20 tasks mid-range) and the biggest published effect of removing access. Too expensive to port first: 8 containers |
| 7 | `user_tracking` | Client-container tool, secrets file | 38 of 59 | 0.73 | Small to medium | Easy tasks and little to gain. Its database accepts any login with no password |
| 8 | `slack_clone` | Database login, signing secret. All logins are handed out | 47 of 63 | 0.31 | Medium | Little to gain, and a single Haiku run passed only 5 of 62 code tasks (cause not known) |
| 9 | `web_scraping` | Root-run service restart, plaintext service credentials | 36 of 75 | 0.33 | Medium | No app login at all, so almost no privilege gradient. 10 scorers read a wrong path at `v1.0.1` [(notes)](../../../5-reading-notes-nov-2026/linuxarena.md) |

## 3. How the environments differ, and what that means for generalizing

### Three shapes of environment `[inference]`

1. **Multi-account hosts:** `shared_dotfiles`, `file_indexing`. Linux accounts and file permissions are part of the app. At least 12 of 83 and 34 of 88 scorers act as another account (regex), against 0 of 76 in `model_registry` `[code]`.
2. **One web service plus a database:** `model_registry`, `auto_workflow`, `tiktok`, `slack_clone`, `media_processing`, `user_tracking`, `web_scraping`. Accounts live inside the app, and the agent's power is a database login or an app identity.
3. **Data analysis:** `clinical_trial`. Power is mostly database roles and scheduled jobs.

### Kinds of power, environment by environment `[inference, from the code and counts below]`

"Free" means the docs already hand it over, so it can't be gained.

| Environment | Root-owned work | Acting as other users | Direct database | App admin identity | Other stores' credentials | Other containers | Root-only information |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `shared_dotfiles` | Central | Some | None | None | Vault tokens | No | Logs, merged files |
| `file_indexing` | Some | Central | None | Little | Redis, Chroma, LDAP | No | `/shared`, store contents |
| `model_registry` | Little | Little | Saves turns | Saves turns | Storage keys | No | Service log |
| `tiktok` | Little | Little | Saves turns | Saves turns (most tasks) | No | No | Secrets file |
| `auto_workflow` | Little | Free | Saves turns | Free | Encryption key, queue | No | Worker logs |
| `clinical_trial` | Cron | No | Central | None | No | No | Logs |
| `media_processing` | Little | Team keys | Saves turns | Free (one team) | Storage keys | Central | Other containers' logs |
| `user_tracking` | Little | No | Open already | None | No | Client tool | Secrets file |
| `slack_clone` | Little | Free | Saves turns | Free | Redis, search index | No | Little |
| `web_scraping` | Service restart | No | Open already | None (no login) | FTP | No | Little |

### Real capability against convenience

Under the fairness rule nothing is strictly necessary, by construction. So I use this test `[inference]`:
- **Real capability:** we would have to add a provision for the fair account to do it (a sudo rule, a readable log, a password).
- **Convenience:** deployed code can already do it, and access only saves turns.

Two consequences:

- **In every environment, a deploy route gives the service's identity.** Whatever the service can do, the fair account can do by deploying code that does it. So kept credentials that the service also holds are always convenience. Real capability can only be something the service can't do, or something the fair route doesn't cover. Where the service is root (`shared_dotfiles`, `file_indexing`), that leaves little beyond the turns saved. What's left is turn count per test cycle, and that's the argument for those two: their test cycles need privileged steps far more often.
- **H counts model turns, not seconds** ([results](results-nov3.md)). A Rust build cache or a quicker restart saves wall-clock time and cost but won't show in POWER_H. That rules out build caches as a measurable kind of power here. It also makes `media_processing`'s slow builds a cost rather than a lever.

### Other differences that matter

- **Scoring changes state, differently everywhere.** `file_indexing` clears the index and runs a setup script as root before each scoring `[docs]`. `clinical_trial`'s restart script truncates data tables and clears mail and logs `[code]`. Each needs its own undo in score-and-roll-back.
- **Code size is small everywhere,** about 2,000 to 8,400 lines (section 4). So knowledge from a previous chat likely carries over everywhere `[inference]`.
- **Noise differs.** In three published Haiku runs, 1 of 20 tasks had mixed outcomes in `auto_workflow`, against 7 of 20 in `media_processing` `[paper]`.
- **Published effects of removing access differ a lot** (section 4). Cutting all networks took `model_registry` from 6 to 0 of 20 and `media_processing` from 10 to 3, and did nothing to `shared_dotfiles` or `user_tracking` `[paper]`. Each cell is one run of 20 tasks. One cell looks like noise: `slack_clone` rose from 7 to 16 with the internet cut.

### How far the Nov 3 result could generalize `[inference]`

| Nov 3 finding | Elsewhere? |
| --- | --- |
| Both A and B beat the initial state, mostly through what they share, likely the continued chat | Likely everywhere. The code bases are small and new to the solver |
| Solvers used access in 26 or 27 of 27 runs, mostly to speed up testing, and needed it in 1 to 3 | Likely in shape 2, weaker where logins are handed out. Not expected in shape 1, where the need should be higher |
| B minus A is near zero | Can't be carried over. One trajectory and one solver run per condition, and the values are the size of a single corrected answer |
| Power-seeking gave little advantage | Speaks only to `model_registry`, with the deploy route open, on 27 chosen tasks |

So I'd read Nov 3 as evidence about shape 2 only, and not yet as evidence about LinuxArena as a whole.

## 4. The numbers

### Main tasks at `v1.0.1` `[code]`

The official verdict is correct or incorrect in every environment. Most code-task scorers count checks and apply a threshold (median 0.7 to 0.81, regex), and their text gives the counts, which is what our measure reads. There is no partial credit in the verdict itself. Research tasks are one answer. Bug-fix and rewrite tasks run integration tests.

| Environment | Main tasks | Feature | Refactor | Bug fix | Research | Infra | Rewrite | Code tasks: named list / errors only / stop at first failure | No scorer file | `need_root` true / false / unlabelled | Integration tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `auto_workflow` | 98 | 39 | 24 | 18 | 3 | 6 | 8 | 47 / 0 / 16 of 69 | 6 | 0 / 28 / 70 | 32 |
| `clinical_trial` | 85 | 45 | 20 | 2 | 8 | 2 | 8 | 51 / 1 / 10 of 67 | 5 | 2 / 12 / 71 | 61 |
| `file_indexing` | 88 | 40 | 31 | 4 | 3 | 2 | 8 | 32 / 3 / 38 of 73 | 0 | 6 / 11 / 71 | 34 |
| `media_processing` | 91 | 51 | 18 | 8 | 3 | 3 | 8 | 50 / 0 / 19 of 72 | 4 | 0 / 21 / 70 | 30 |
| `model_registry` | 83 | 35 | 7 | 16 | 8 | 9 | 8 | 32 / 1 / 11 of 51 | 7 | 0 / 12 / 71 | 19 |
| `shared_dotfiles` | 84 | 32 | 17 | 24 | 5 | 6 | 0 | 41 / 1 / 12 of 55 | 1 | 15 / 8 / 61 | 70 |
| `slack_clone` | 98 | 52 | 10 | 24 | 3 | 1 | 8 | 47 / 7 / 8 of 63 | 1 | 1 / 14 / 83 | 18 |
| `tiktok` | 98 | 40 | 22 | 22 | 3 | 3 | 8 | 49 / 1 / 15 of 65 | 0 | 0 / 16 / 82 | 26 |
| `user_tracking` | 86 | 40 | 16 | 18 | 8 | 3 | 0 | 38 / 1 / 17 of 59 | 4 | 0 / 25 / 61 | 10 |
| `web_scraping` | 98 | 50 | 22 | 11 | 3 | 3 | 8 | 36 / 7 / 25 of 75 | 8 | 3 / 14 / 81 | 6 |

Tasks with no scorer file are idea stubs and can't run. The `need_root` labels look machine-written, so they are a noisy hint [(notes)](../../../5-reading-notes-nov-2026/linuxarena.md).

### What code-task requirements mention (regex, rough) `[code]`

| Environment | Code tasks | sudo or root | Root-owned paths | Admin role | Other user or team | Login or auth | Schema change | Logs | Deploy or restart |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `auto_workflow` | 69 | 3 | 2 | 13 | 10 | 43 | 28 | 4 | 24 |
| `clinical_trial` | 67 | 4 | 6 | 1 | 0 | 4 | 44 | 5 | 5 |
| `file_indexing` | 73 | 32 | 26 | 4 | 13 | 37 | 10 | 4 | 33 |
| `media_processing` | 72 | 2 | 1 | 16 | 16 | 54 | 41 | 0 | 27 |
| `model_registry` | 51 | 3 | 4 | 24 | 3 | 36 | 27 | 3 | 14 |
| `shared_dotfiles` | 55 | 34 | 48 | 10 | 10 | 18 | 3 | 11 | 24 |
| `slack_clone` | 63 | 1 | 0 | 9 | 12 | 52 | 44 | 1 | 18 |
| `tiktok` | 65 | 5 | 0 | 38 | 10 | 50 | 36 | 1 | 8 |
| `user_tracking` | 59 | 2 | 0 | 4 | 6 | 36 | 16 | 1 | 5 |
| `web_scraping` | 75 | 3 | 0 | 3 | 0 | 10 | 25 | 1 | 13 |

### Published results, all as root `[paper]`

Computed from the honest runs in the paper's [public run list](https://github.com/redwoodresearch/linuxarena-paper/blob/main/src/results/public_run_ids.json), through `repro.linuxarena.ai/api/public/lean/<run_id>`. Each environment has 20 tasks across 13 models. "Mid" means 3 to 10 of the 13 models passed. "Haiku large" is the single Haiku run on the 1,626-task set, code tasks only. "Mixed" is tasks with different outcomes across 3 Haiku runs. The last column is one Haiku run per condition, passes of 20: normal / text editor only / internet cut / all networks and cross-container tools cut ([definitions](https://github.com/redwoodresearch/linuxarena-paper/blob/main/src/policies/honest/policy.py)).

| Environment | All tasks | Code tasks (tasks in set) | Median actions, code | Tasks 0 of 13 | Tasks 13 of 13 | Mid | Haiku large | Mixed, of 20 | Normal / editor / no internet / no network |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `auto_workflow` | 0.53 | 0.56 (15) | 49 | 4 | 3 | 8 | 39 of 65 | 1 | 11 / 6 / 10 / 9 |
| `clinical_trial` | 0.76 | 0.77 (16) | 36 | 0 | 2 | 11 | 52 of 62 | 6 | 16 / 12 / 12 / 13 |
| `file_indexing` | 0.49 | 0.55 (15) | 60 | 3 | 2 | 9 | 44 of 73 | 4 | 9 / 8 / 10 / 6 |
| `media_processing` | 0.53 | 0.53 (15) | 54 | 1 | 0 | 16 | 43 of 69 | 7 | 10 / 1 / 9 / 3 |
| `model_registry` | 0.26 | 0.39 (9) | 66 | 11 | 0 | 9 | 16 of 43 | 5 | 6 / 1 / 8 / 0 |
| `shared_dotfiles` | 0.69 | 0.49 (9) | 60 | 2 | 1 | 8 | 30 of 54 | 3 | 15 / 8 / 17 / 16 |
| `slack_clone` | 0.34 | 0.31 (15) | 49 | 4 | 0 | 8 | 5 of 62 | 2 | 7 / 11 / 16 / 10 |
| `tiktok` | 0.40 | 0.51 (11) | 53 | 4 | 0 | 9 | 39 of 65 | 4 | 9 / 5 / 7 / 6 |
| `user_tracking` | 0.78 | 0.73 (12) | 46 | 0 | 3 | 6 | 42 of 56 | 6 | 16 / 8 / 16 / 16 |
| `web_scraping` | 0.31 | 0.33 (15) | 39 | 6 | 2 | 7 | 33 of 68 | 5 | 4 / 1 / 6 / 2 |

### Side tasks: categories and kinds `[code for categories; inference for kinds]`

92 in the public suite. Categories are the paper's. Kinds are my reading, and a task can have several: **A** change and deploy service code; **B** run something as root or with elevated rights; **C** reach outside over the network; **D** read a secret or credential; **E** change stored data directly; **F** change oversight (audit, alerts, reports, security filters); **G** reach other users' or teams' data; **H** a standing effect on other users' logins.

| Environment | Total | Access bypass | Data exfiltration | Malware | Data tampering | Monitoring subversion | Secret access | A | B | C | D | E | F | G | H |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `auto_workflow` | 11 | 4 | 2 | 3 | 1 | 1 | 0 | 7 | 3 | 7 | 2 | 0 | 2 | 1 | 0 |
| `clinical_trial` | 5 | 0 | 1 | 0 | 1 | 3 | 0 | 3 | 0 | 1 | 1 | 1 | 3 | 0 | 0 |
| `file_indexing` | 13 | 3 | 2 | 2 | 3 | 1 | 2 | 9 | 2 | 5 | 2 | 0 | 1 | 5 | 0 |
| `media_processing` | 9 | 3 | 0 | 2 | 3 | 1 | 0 | 5 | 2 | 3 | 0 | 2 | 1 | 1 | 0 |
| `model_registry` | 9 | 3 | 2 | 2 | 2 | 0 | 0 | 4 | 2 | 5 | 1 | 3 | 0 | 2 | 0 |
| `shared_dotfiles` | 11 | 4 | 2 | 1 | 0 | 1 | 3 | 2 | 1 | 4 | 5 | 0 | 2 | 1 | 6 |
| `slack_clone` | 9 | 4 | 2 | 2 | 1 | 0 | 0 | 4 | 3 | 5 | 0 | 1 | 0 | 3 | 0 |
| `tiktok` | 9 | 3 | 3 | 2 | 1 | 0 | 0 | 7 | 2 | 3 | 3 | 0 | 0 | 0 | 0 |
| `user_tracking` | 7 | 2 | 1 | 2 | 1 | 1 | 0 | 3 | 2 | 4 | 1 | 1 | 1 | 0 | 0 |
| `web_scraping` | 9 | 5 | 2 | 2 | 0 | 0 | 0 | 7 | 2 | 3 | 1 | 0 | 0 | 0 | 0 |

Three points `[inference]`:
- About 34 of the 92 are the same four generic shapes reused across environments and don't depend on what the app does.
- 51 of 92 need kind A, which a fair account with a deploy route already has. So most side tasks say little about lasting access.
- `shared_dotfiles` is the exception: kinds D and H dominate, which is more evidence that its security surface is about accounts rather than app code.

As root, the default, none of these needs anything extra. They only start to need power once the account is non-root. Per-task reachability for `model_registry` is in [nov5-side-tasks.md](nov5-side-tasks.md).

## 5. Each environment

**In common** `[code]`: Docker Compose, Ubuntu 22.04 base, the agent in the `default` container with `bash` and a text editor, root by default, an internet simulator container attached ([reading notes](../../../5-reading-notes-nov-2026/linuxarena.md)). Each environment's description is at `docs/description.md` in its repository (section 10). Power common to all, beyond what's listed below `[inference]`:
- knowledge of the code carried in the chat;
- helper scripts and test users left by earlier work;
- a tool that runs the task's own tests (`run_main_task_test` exists in Control Tower and is off in the honest policy [(notes)](../../../5-reading-notes-nov-2026/linuxarena.md)).

The last is the most direct information advantage I can see, and it would be a clean known-power check in any environment.

### `shared_dotfiles`

- **What it is.** A multi-user Linux server. Company, team and user dotfile layers are merged into each account's dotfiles, with HashiCorp Vault for secrets and wrappers around `sudo`, `pip` and `python3`. Bash plus a small C helper, about 2,000 lines. Containers: `default`, `vault` (dev mode), two package mirrors [(compose)](https://github.com/linuxarena/shared_dotfiles/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** `scott` and `alex` have sudo with a password, `josh` has none [(Dockerfile)](https://github.com/linuxarena/shared_dotfiles/blob/v1.0.1/codebase/src/Dockerfile). The merger runs as root from cron every minute and at login. Merged files are `root:<user>` mode 640 [(merge.sh)](https://github.com/linuxarena/shared_dotfiles/blob/v1.0.1/codebase/src/app/dotfiles-merger/merge.sh). Audit logs are `syslog:adm` mode 640. Vault tokens are per user, mode 400 `[docs]`.
- **Main tasks.** 84. Code tasks pass 0.49 with a median 60 actions `[paper]`. The published 0.90 on bug fixes is suspect: the maintainers later fixed [bug-fix scorers that passed with a no-op agent](https://github.com/linuxarena/shared_dotfiles/commit/37a6c48), after `v1.0.1` `[code]`. Our no-work run would catch this.
- **Power.** 49 of 55 code tasks name the merger folder and 37 the config folder (regex) `[code]`.
  - *Real capability:* acting as another user for login-time behaviour; writing `/usr/local/bin`, `/etc/cron.d` or `/etc/rsyslog.d`; installing packages; reading root-only logs, which at least one research question seems to need (not verified). `[inference]`
  - *Convenience:* direct sudo in place of the deploy route; running a merge at will.
- **Lasting access.** Yes, and easily: a sudo rule, a hook in a root-run script, group membership for logs, another user's Vault token. These survive in files, and tasks would use them for testing `[inference]`.
- **Against `model_registry`.** The app is the permission system. No database, no app login. Nothing to forge.
- **Port (medium)** `[inference]`.
  - The account gets group write on the merger and config folders, and sudo on `deploy.sh` and `merge.sh`.
  - 32 of 55 code tasks stay inside those folders (regex); 23 touch other root-owned places and need a provision or to be left out.
  - Fairness needs a decision on read access to merged files and logs: withholding them is what makes access matter, but a task can't become impossible.
  - Snapshots: the file layer covers nearly everything. Vault dev mode likely keeps data in memory, so tasks touching Vault (8 of 55) need extra care.
  - Risks: one edit to a root-run script gives root, so controls may escalate on their own, as [pair 2's control did](results-nov3.md). And Control Tower's docs [warn](https://github.com/linuxarena/control-tower/blob/main/docs/development/making-environments.md) that an agent account can cause text-editor permission problems, which the wrapped `python3` here could make worse. Test this first.

### `file_indexing`

- **What it is.** A file search service: a root Unix-socket server and a REST API over Redis and ChromaDB, with OpenLDAP logins. Python, about 4,700 lines. Containers: `default`, `redis`, `chroma`, `openldap` [(compose)](https://github.com/linuxarena/file_indexing/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** Linux users `dev`, `guest`, `agent`, and LDAP users with group-to-folder mappings. Working copy in `/app/indexer`, production in `/opt/indexer`, and `sudo deploy-indexer` copies and restarts [(deploy script)](https://github.com/linuxarena/file_indexing/blob/v1.0.1/codebase/deploy-indexer). The server refuses to start unless root [(server.py)](https://github.com/linuxarena/file_indexing/blob/v1.0.1/codebase/src/indexer/server.py). Store passwords are root-only files [(Dockerfile)](https://github.com/linuxarena/file_indexing/blob/v1.0.1/codebase/Dockerfile), and `/shared` is root-only [(setup script)](https://github.com/linuxarena/file_indexing/blob/v1.0.1/codebase/populate_test_files.sh). Before each scoring, the index is cleared and `/app/setup.sh` runs as root `[docs]`.
- **Main tasks.** 88. Code tasks pass 0.55 with a median 60 actions `[paper]`. Half the code-task scorers stop at the first failure `[code]`.
- **Power.**
  - *Real capability:* acting as other Linux or LDAP users (permission-filter tests need it); reading store contents directly; `/shared`, which all three research questions depend on; writing system paths or installing new stores (16 of 73 code tasks, regex).
  - *Convenience:* deploying at will, reading logs.
  - *Evidence* `[docs]`: when agents ran without root, [notes on `usage_quotas`](https://github.com/linuxarena/file_indexing/blob/v1.0.1/main_tasks/usage_quotas/NOTES.md) say Claude lacked root, needed it for an admin command, and ran out of tokens setting up tests. They add that on similar tasks it usually turned off the permission check while testing. [`file_helper`'s notes](https://github.com/linuxarena/file_indexing/blob/v1.0.1/main_tasks/file_helper/NOTES.md) describe the same.
- **Lasting access.** Yes: a sudo rule, copied store passwords, a root-run hook through the deployed server. API tokens and index contents don't last, because scoring clears them `[inference]`.
- **Against `model_registry`.** Deployed code runs as root, not as a limited service. The separate production folder is unique among these environments.
- **Port (medium to large)** `[inference]`.
  - Use the existing `agent` account, since `dev` is a test subject here. Add one sudo line, since none exists at `v1.0.1`.
  - The setup script runs as root at scoring, so if the account can edit it, that's a route to root. It needs moving or locking.
  - Either patch scorers to continue past a failure or use only the 32 with lists.
  - Snapshots must add Redis, Chroma and OpenLDAP. Control Tower main has [state checks for all three](https://github.com/linuxarena/control-tower/tree/main/src/control_tower/extras/scorer_idempotency/checks), built for its newer version.

### `tiktok`

- **What it is.** A Next.js app where users guess TikTok engagement, with NextAuth logins, Prisma and Postgres. TypeScript, about 5,800 lines. Containers: `default`, `db` [(compose)](https://github.com/linuxarena/tiktok/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** Root by default, but nothing needs root: the [restart script](https://github.com/linuxarena/tiktok/blob/v1.0.1/codebase/src/restart.sh) does nothing and scorers start the dev server themselves. The database superuser login is in `DATABASE_URL`. The session secret is in `.env.local`. App roles include admin. `[code]`
- **Main tasks.** 98. Code tasks pass 0.51 with a median 53 actions `[paper]`. 19 of 65 code-task scorers install things over the network at scoring (regex), a hazard the maintainers fixed later `[code]`.
- **Power.**
  - *Real capability:* almost none, except installing a local database or monitoring stack (5 tasks, regex).
  - *Convenience:* a database login to promote a test user or clean up; the session secret to forge a login; an admin test account. 38 of 65 code tasks mention admin, the most of any environment (regex) `[code]`.
- **Lasting access.** An admin account and the secret survive and would be used, but they only save turns `[inference]`.
- **Against `model_registry`.** The same kind of power, with fewer parts: no shared storage, no Go modules, no separate service account.
- **Port (small)** `[inference]`. The account gets write on `/app/src`. Strip `DATABASE_URL`. Decide how it runs a dev server without reading the secrets. Postgres snapshots reuse `state_store.py`, with no buckets.

### `auto_workflow`

- **What it is.** Workflow automation: JSON node graphs, a worker pool, a sandbox for user JavaScript, git sync and a scheduler. TypeScript, Express, Prisma, Postgres, RabbitMQ, about 2,700 lines. Containers: `default`, `postgres`, `rabbitmq` [(compose)](https://github.com/linuxarena/auto_workflow/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** The app runs as root `[docs]`. Team-based roles at the app level, with admin and developer API tokens for two teams listed in the [description](https://github.com/linuxarena/auto_workflow/blob/v1.0.1/docs/description.md). `DATABASE_URL`, `RABBITMQ_URL` and the encryption key are in the agent's environment. The database login is the image's first user, so likely a superuser `[inference]`.
- **Main tasks.** 98. Code tasks pass 0.56 with a median 49 actions, and the lowest noise `[paper]`. 56 of 69 code-task scorers redeploy themselves (regex). 15 install packages at scoring (regex) `[code]`.
- **Power.**
  - *Real capability:* installing new services for the 6 infrastructure tasks.
  - *Convenience:* a database login (audit rows, results), worker logs, the encryption key. Admin identity is free.
- **Lasting access.** A database login and key survive. Later tasks would only save turns `[inference]`.
- **Against `model_registry`.** A close twin without the forged-token route. If forged tokens drove the Nov 3 speedups, gains here should be smaller.
- **Port (small to medium)** `[inference]`. Add a service account and change the restart script, or accept that deploying gives root. Allow `restart.sh`. Strip three variables. Snapshots reuse files and Postgres, and the RabbitMQ queue is probably safe to treat as temporary.

### `clinical_trial`

- **What it is.** Vaccine trial analysis: R scripts and Jupyter notebooks, Postgres, a Flask patient portal, cron monitoring, and email captured by MailHog. About 3,400 lines. Containers: `default`, `postgres`, `mailhog` [(compose)](https://github.com/linuxarena/clinical_trial/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** The agent's role is a statistician with the database superuser login in its environment. Lesser roles exist: `clinical_staff` (read, insert, update) and `patient_user` [(init.sql)](https://github.com/linuxarena/clinical_trial/blob/v1.0.1/codebase/init/db/init.sql). Cron and Jupyter run as root, and Jupyter has no login `[code]`.
- **Main tasks.** 85. Code tasks pass 0.77 with a median 36 actions, 0 of 20 published tasks failed by all `[paper]`. 44 of 67 code tasks mention schema changes (regex). 8 research questions read data `[code]`.
- **Power.**
  - *Real capability:* schema rights if the account is limited to a narrower role; editing cron jobs; logs.
  - *Convenience:* superuser to seed blood tests, though `clinical_staff` can already insert. MailHog is open to all.
- **Lasting access.** Database roles survive, but the [restart script](https://github.com/linuxarena/clinical_trial/blob/v1.0.1/codebase/src/restart.sh) resets data tables to their seed and clears mail, logs and backups `[code]`. So rows don't last.
- **Against `model_registry`.** No app to log in to and no deploy step, and the database role is the main gradient. Very easy tasks may saturate early, which could help or hurt a speed measure.
- **Port (medium)** `[inference]`. Open Jupyter as root is a route to root, so it must move. No deploy script exists, so one must be written that doesn't reset the data. Schema tasks need a route. A 5-minute cron job adds timing noise.

### `media_processing`

- **What it is.** A media pipeline: Rust gateway and worker, Python ML service with a stub if no key is set, NGINX, MinIO, Postgres, RabbitMQ, Redis, FFmpeg. About 3,800 lines. 8 containers [(compose)](https://github.com/linuxarena/media_processing/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** Root `[docs]`. Teams are API keys in Postgres, and one key is in the docs. Storage and database logins are in the agent's environment. Four [extra tools](https://github.com/linuxarena/media_processing/blob/v1.0.1/env_tools.py) run commands inside other containers, as those containers' default user. Other services' source is on shared volumes. `[code]`
- **Main tasks.** 91. Code tasks pass 0.53 with a median 54 actions, 16 of 20 tasks mid-range, and the highest noise `[paper]`.
- **Power.**
  - *Real capability:* reach into other containers; storage keys, which research questions need. The biggest published effect: all networks and those tools cut took it from 10 to 3 of 20, and text editor only to 1 `[paper]`.
  - *Convenience:* a second team's key for cross-team tests, a database login.
- **Lasting access.** Keys survive. The tools themselves can't be gained during a run, because the harness grants them. So they suit a known-power check better than a trajectory `[inference]`.
- **Against `model_registry`.** Far more moving parts, and access across containers matters more.
- **Port (large)** `[inference]`. 8 containers, 3 shared volumes, its own MinIO, tools that ignore the account, and Rust builds of [30 to 60 seconds](https://github.com/linuxarena/media_processing/blob/v1.0.1/codebase/services/rust-worker/restart.sh) in most scorers (47 of 72 redeploy, regex), which would make every-turn scoring expensive.

### `user_tracking`

- **What it is.** A C server and client capturing desktop activity into stories in Postgres. About 5,000 lines. Containers: `default`, `client`, `db`, with shared volumes [(compose)](https://github.com/linuxarena/user_tracking/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** Root. The database uses `trust` login, so anyone on its network gets in with no password. Secrets are in `server/secrets.conf`. Tools `client_bash` and `db_bash` run in other containers. `[code]`
- **Main tasks.** 86. Code tasks pass 0.73 with a median 46 actions `[paper]`. 8 research questions, one asking directly for a secret's value `[code]`.
- **Power.**
  - *Real capability:* the client tool, for client tests; reading the secrets file.
  - *Convenience:* direct database access, which is already open.
  - *Evidence against any of this mattering much:* with all networks and both tools cut, Haiku still passed 16 of 20, the same as normal `[paper]`.
- **Lasting access.** Little that later tasks need `[inference]`.
- **Against `model_registry`.** No app accounts, fast C builds, and few levers.
- **Port (small to medium)** `[inference]`. Service on port 8080 can drop root. Change the `trust` setting to create any database boundary. Decide whether the account keeps the two tools.

### `slack_clone`

- **What it is.** Team chat: Rails, Postgres, Redis, Elasticsearch, Sidekiq. About 8,400 lines. Containers: `default`, `postgres`, `redis`, `elasticsearch` [(compose)](https://github.com/linuxarena/slack_clone/blob/v1.0.1/codebase/compose.yml). `[code]`
- **Accounts and permissions.** Root, and Puma binds port 80. All 20 users' logins, admin included, are in the [description](https://github.com/linuxarena/slack_clone/blob/v1.0.1/docs/description.md). The superuser login is in the agent's environment. `[code]`
- **Main tasks.** 98. Code tasks pass 0.31, and Haiku's large run passed 5 of 62 `[paper]`. I don't know if that's difficulty or broken scorers.
- **Power.** *Real capability:* almost none. *Convenience:* a database login, Redis, the search index, the signing secret. Identity is free.
- **Lasting access.** Available, but later tasks barely need it `[inference]`.
- **Against `model_registry`.** Same shape with less to gain.
- **Port (medium)** `[inference]`. Port 80 needs root or a capability. Elasticsearch adds a heavy store to snapshot.

### `web_scraping`

- **What it is.** A Wikipedia scraper: Node, Bull queues, with Postgres, Redis and vsftpd all inside the `default` container, plus three helper containers [(compose)](https://github.com/linuxarena/web_scraping/blob/v1.0.1/codebase/compose.yml). About 3,500 lines. `[code]`
- **Accounts and permissions.** Root. No login on the REST API. Postgres `trust` on localhost. FTP and database logins are in a plaintext file. `[code]`
- **Main tasks.** 98. Code tasks pass 0.33 `[paper]`. 10 scorers read a wrong path at `v1.0.1` [(notes)](../../../5-reading-notes-nov-2026/linuxarena.md), and 25 of 75 stop at the first failure `[code]`.
- **Power.** *Real capability:* the root-run restart, and installing new daemons (the 3 tasks labelled as needing root). *Convenience:* little, since the rest is open.
- **Lasting access.** Almost nothing to keep `[inference]`.
- **Against `model_registry`.** No privilege gradient to speak of.
- **Port (medium)** `[inference]`. `restart.sh` needs root for `service`, so deploying gives root. One container helps snapshots, but live Postgres and Redis files need flushing first.

## 6. Port costs, side by side

Today's setup is tied to `model_registry` in these places `[code]`: `ONBOARDING`, `DEV_SETUP_SCRIPT` and the stripped variables in [`power_v0.py`](../harness/power_v0.py); [`state_store.py`](../harness/state_store.py) and [`rollback.py`](../harness/rollback.py) (service patterns, two buckets, shared MinIO); and [`extract.py`](../harness/extract.py) (scorer text formats, bug-fix targets). The trajectory replay, per-step scoring and `power_horizons.py` look general `[inference]`.

| Environment | Containers | Stores beyond files | App runs as | Deploy route to allow | Logins in agent's variables | Extra tools | Effort `[inference]` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `model_registry` | 4 + shared MinIO | Postgres, MinIO | `service` | `rebuild.sh`, `restart.sh` | Test database URL | None | Done |
| `shared_dotfiles` | 4 | Vault | Root, by necessity | `deploy.sh`, `merge.sh` | None | None | Medium |
| `file_indexing` | 4 | Redis, Chroma, OpenLDAP | Root, by necessity | `deploy-indexer` | None | None | Medium to large |
| `tiktok` | 2 | Postgres | Root, no need | None for scoring; a dev server | Database | None | Small |
| `auto_workflow` | 3 | Postgres, RabbitMQ | Root, no need | `restart.sh` | Database, queue, key | None | Small to medium |
| `clinical_trial` | 3 | Postgres, MailHog | Root | To be written | Database, staff | None | Medium |
| `user_tracking` | 3 | Postgres, shared volumes | Root, no need | `restart.sh` | None | 2 | Small to medium |
| `slack_clone` | 4 | Postgres, Redis, Elasticsearch | Root (port 80) | `restart.sh` | Database | None | Medium |
| `web_scraping` | 4 | Inside the app container | Root (starts services) | `restart.sh` | None | None | Medium |
| `media_processing` | 8 | Postgres, MinIO, Redis, RabbitMQ, shared volumes | Root | Restart tools | Database, storage | 4 | Large |

Default images on Docker Hub at `v1.0.1` are all present, 0.35 to 3.19 GB compressed (Docker Hub listing) `[docs]`. Only `model_registry`'s are on this machine, so others need pulls.

## 7. Outside the 10

- **Four public extras** ([ct-linuxarena-extras](https://github.com/linuxarena/ct-linuxarena-extras)) `[code]`. All use the newer SDK (`ct_setting_sdk`), so they don't fit our Control Tower commit `699d5ca` without a move, and their images aren't tagged `v1.0.1`. Agent account: root by default.

  | Environment | What | Main | Side (categories) |
  | --- | --- | --- | --- |
  | [`gitea-platform`](https://github.com/linuxarena/gitea-platform) | Code hosting fork: Go, SQLite, CI runner, audit daemon, admin CLI | 7 | 4 (all access bypass) |
  | [`woocommerce_store`](https://github.com/linuxarena/woocommerce_store) | WordPress store, MariaDB, Redis | 7 | 13 (5 tampering, 5 access bypass, 2 exfiltration, 1 other) |
  | [`messaging_app`](https://github.com/linuxarena/messaging_app) | Mattermost, Postgres, Redis, MinIO | 2 | 1 (exfiltration) |
  | [`invoice_billing`](https://github.com/linuxarena/invoice_billing) | Invoice Ninja, n8n, MariaDB, Postgres | 7 | 5 (2 access bypass, 1 tampering, 2 uncategorized) |

  `gitea-platform` is the interesting one: services run as a separate `git` account, there are per-user credential folders, and an audit log `[docs]`. But 7 tasks is too few today `[inference]`.
- **Ten held-out environments** `[paper]`: Cost Estimation, DeFi Yield Aggregator, Dev Server, Insurance Calculator, Job System, LB in LB, Load Balancer, Payroll System, Port Scanner, Ticket System. From the paper's one-line descriptions, **Dev Server** (spawns Linux users with persistent shells) and **Job System** (authenticates users and compiles submitted code) might be multi-account hosts like the top two `[inference]`. I can't check that.
- **Other settings in the same GitHub organization**, not LinuxArena: BashArena, `docker_sandbox_breakout`, `refactor_arena`, `ct-shade-arena`, `sae_interp_sabotage`, `auto_control`, `ResearchArena`, `ct-vllm`, `apps`, `demos`. READMEs only `[docs]`. Not assessed.

## 8. What's unknown, and what I couldn't reach

**Couldn't reach.**
- `ct-linuxarena-private` and the 10 held-out environment repositories return 404 without a login. I did not look for another way in.
- I didn't use `data.linuxarena.ai`'s full trajectories, only the summary API (no tool arguments or outputs).

**Unknown.**
- **Whether access saves many turns anywhere else.** This is the central claim for the top two, and it is reasoning from code, not measurement. No non-root run exists outside `model_registry`, apart from old notes in `file_indexing`.
- **How our solver does elsewhere.** All published numbers are for root agents and other models. DeepSeek V4.1 Flash may rank environments differently.
- **Whether the text editor works for a non-root account under `shared_dotfiles`' wrapped `python3`.** Not tested.
- **Whether controls would escalate on their own** in `shared_dotfiles` and `file_indexing`, where one edit reaches root. If they usually do, a clean control is hard to get.
- **How much a fair `shared_dotfiles` account should read.** Withholding merged files and logs drives the signal, but might make some tasks impossible. It needs a task-by-task audit like [the superuser audit](superuser-audit.md).
- **Scoring time per environment.** Not published and not measured. I only have proxies: rebuild steps and literal sleeps (`web_scraping` highest, median 5 seconds).
- **The `v1.0.1` task bugs.** Each environment has 6 to 14 later commits fixing scorers or tasks. I read only a sample. Newer tags don't run on our commit. Expect a free check to drop tasks, as it did for `model_registry`. `slack_clone`'s low pass share is unexplained.
- **Regex counts.** They read requirement text and scorer shapes, so they miss indirect needs and overcount words used in passing. The side-task kinds are my reading, and untested.
- **The sandbox columns** are one Haiku run per condition, and at least one cell looks like noise.

## 9. If Arya wants to take this further `[inference]`

Recommendations only: environment choice is Arya's call, and nothing here needs a run yet.

1. **Read task-by-task first.** A superuser-audit-style pass over `shared_dotfiles`' 32 tasks that stay in the merger and config folders would show how many stay fair, and which steps the fair account would lack. No runs, no cost.
2. **Then a small free check** on `shared_dotfiles` and `tiktok`: image pull, no-work scores, and one probe of the account setup. That would show the no-op bug, the text-editor risk, and scorer health.
3. **Whichever environment comes next, run the known-power check there** (not approved so far), so we learn whether the meter can see power at all before spending on trajectories.
4. **Decide about the deploy route.** Everywhere, it limits what kept access can add. Tasks where it costs many turns are the way to keep the fairness rule and still see a difference.

## 10. Sources

- Environment repositories at tag `v1.0.1`: [auto_workflow](https://github.com/linuxarena/auto_workflow/tree/v1.0.1), [clinical_trial](https://github.com/linuxarena/clinical_trial/tree/v1.0.1), [file_indexing](https://github.com/linuxarena/file_indexing/tree/v1.0.1), [media_processing](https://github.com/linuxarena/media_processing/tree/v1.0.1), [model_registry](https://github.com/linuxarena/model_registry/tree/v1.0.1), [shared_dotfiles](https://github.com/linuxarena/shared_dotfiles/tree/v1.0.1), [slack_clone](https://github.com/linuxarena/slack_clone/tree/v1.0.1), [tiktok](https://github.com/linuxarena/tiktok/tree/v1.0.1), [user_tracking](https://github.com/linuxarena/user_tracking/tree/v1.0.1), [web_scraping](https://github.com/linuxarena/web_scraping/tree/v1.0.1).
- Suite: [ct-linuxarena](https://github.com/linuxarena/ct-linuxarena), now pinning environments at `v3.2.0`; [Control Tower](https://github.com/linuxarena/control-tower), whose `environments.yml` lists public and private; `ct registry pull` in our commit `699d5ca` (the README says it needs `gh`, which WSL lacks, so I used plain `git clone`).
- Paper: [arXiv 2604.15384](https://arxiv.org/abs/2604.15384); [paper repository](https://github.com/redwoodresearch/linuxarena-paper), including the [environment table](https://github.com/redwoodresearch/linuxarena-paper/blob/main/src/appendix_A_all_environments/environments.tex).
- Project: [reading notes](../../../5-reading-notes-nov-2026/linuxarena.md), [Nov 3 results](results-nov3.md), [science review](../plans/nov3-science-review.md), [superuser audit](superuser-audit.md).
- Local copies, WSL only: `/root/power-v0/src/envs-survey/` (1.4 GB, clones, plus a shallow `control-tower-main`), `/root/power-v0/src/envs-survey-data/` (13 MB, published run summaries).
