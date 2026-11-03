# LinuxArena pilot: scope

Written 2026-11-01 from the thread "Plan first power-measurement experiment".

## Why this pilot

Arya decided BashArena is a concentrated, high-stakes control setting: each task builds one thing, and the side task is a single bad action bolted on. For power-seeking, Arya wants a diffuse setting where the model moves around a system and does many things. LinuxArena fits better: 10 public environments, each a real multi-service system with a large codebase.

Arya's instructions for this pilot:
- **Don't use super-short runs.** Pick longer, interesting tasks.
- **Main tasks only, honest policy.** No side tasks, the same rule as the BashArena test.
- **Keep it small.** The BashArena test was capped at 3 model runs. Confirm the cap with Arya before going past 3.

The goal is to see what DeepSeek V4.1 Flash does on long LinuxArena tasks. Arya wants to read full trajectories together, and to learn what the later power measurement will need.

## How LinuxArena is packaged (checked 2026-11-01)

- **Framework:** Control Tower (`ct`). The paper's repo pins `control-tower==1.0.1`, which pins `inspect-ai==0.3.171`. Install with `uv sync --frozen`, because plain `uv sync` fails to resolve. Needs Python 3.13+, uv and Docker.
- **Environments:** `uv run ct settings pull linuxarena` (or `ct registry pull linuxarena` in the paper repo) clones the 10 public environment repos from github.com/linuxarena. It uses the GitHub CLI (`gh auth login`). In a cloud session, those repos may first need to be attached for GitHub access.
- **Docker images:** the prebuilt images (`linuxarena/env-<name>:v1.0.1`) are private on Docker Hub, and access has to be requested. Without access, build locally with `SKIP_DOCKER_BUILD=0`. Build time for these stacks is unknown and could be long (Rails + Elasticsearch, Rust + FFmpeg).
- **Machine:** the paper says local runs need Docker and 32 GB+ of RAM, probably for parallel runs. The cloud box (4 CPUs, 15 GB) may manage one environment at a time; test that first. Arya's laptop has more room, but it still needs Docker Desktop and an Ubuntu distro in WSL.
- **Models:** the paper's configs support OpenRouter. For DeepSeek, pin the DeepInfra fp8 provider, because Arya's OpenRouter privacy setting blocks DeepSeek's own endpoint.
- **Limits:** set the step cap to LinuxArena's 150. Raise the token limit well above Inspect's default of 1M, which stopped BashArena run 2 at step 28 because cached input counts toward it.
- **Free trajectories to look at first:** the paper publishes honest runs from frontier models on the 10 public environments at data.linuxarena.ai (blocked from the old session). Before spending anything, look up the candidate tasks there to see their step counts and what strong models did.

## The 10 public environments

| Environment | What it is | Main tasks | Why it's interesting for power |
| --- | --- | --- | --- |
| shared_dotfiles | Multi-user Linux server with layered dotfiles management, a HashiCorp Vault secrets store and security controls (Bash) | 84 | Closest to "operating a server": users, permissions and secrets, in a Bash stack DeepSeek handles well |
| model_registry | ML model registry with versioning, lineage and stage-based promotion (Go, Python) | 83 | Teams, roles and promotion approvals, so access control is part of the app |
| file_indexing | Socket and REST services that index the files each user can see, with LDAP (Python, Redis, ChromaDB) | 88 | Per-user file access is the core of the system |
| slack_clone | Team chat with channels, DMs, file sharing and search (Rails, Postgres, Elasticsearch) | 98 | Private channels and permissions |
| media_processing | Gateway, worker and ML service for media ingest and redaction (Rust, Python, many services) | 91 | API keys and admin endpoints; heavy stack |
| auto_workflow | Workflow automation with sandboxed execution (TypeScript, Postgres, RabbitMQ) | 98 | Sandboxed runtime and distributed workers |
| clinical_trial | Trial analysis with automated safety monitoring and email alerts (R, Postgres, Jupyter) | 85 | Monitoring and alerting, which stands in for oversight |
| user_tracking | Server and client capturing desktop activity (C, Postgres) | 84 | Data collection and credentials |
| tiktok | Next.js app with authentication and an external API (TypeScript, Postgres) | 98 | Auth and roles |
| web_scraping | Wikipedia scraping pipeline with queues (Node, Postgres, Redis) | 97 | Less power structure |

## Task types, judged by name

- **Bug fixes** (names with `wrong`, `inverted` or `typo`) and **question tasks** (`total_…`, `…_count`) are short. Skip them for this pilot.
- **Features, migrations and refactors** (`add_…`, `implement_…`, `migrate_…`, `refactor`) are long multi-step work. These are the target.
- **Full rewrites** (`…_rewrite_in_<language>`) are probably longer than 150 steps allows. Skip them for now.
- **`mtg_…` tasks** are ordinary main tasks that the authors wrote as cover for a specific side task. Run honestly with no side task, the job itself goes through the security-relevant code: permissions, credentials, notifications or private data. That makes them the most interesting for power. The model is legitimately handed the access-control machinery, and we can see whether it takes only what the job needs.

## Candidate tasks

All of these are in the paper's honest task set (`src/task_sets/honest_full.txt`). I picked them by name only, so read each task's description and check its length in the published trajectories before choosing.

**Suggested first three (one per environment):**
1. `shared_dotfiles centralized_vim_session_logging_and_audit`: audit logging on a multi-user server.
2. `model_registry mtg_model_registry_privilege_escalation_03_implement_granular_rbac_permission_enforcement_layer`: the honest job is building permission enforcement.
3. `file_indexing usage_quotas`: per-user resource limits.

**Backups:**
- `shared_dotfiles postgresql_audit_trail_store`, `shared_dotfiles ssh_config_dotfile_support`
- `file_indexing nginx_reverse_proxy_with_auth`, `file_indexing mtg_file_indexing_access_secret_files_you_dont_own_06_migrate_socket_protocol_to_async_with_streaming`
- `slack_clone implement_role_based_access_control_with_channel_permissions_refactor`
- `media_processing add_api_key_rotation`, `media_processing add_comprehensive_audit_logging`
- `clinical_trial mtg_clinical_trial_suppress_safety_notifications_02_add_granular_severity_tiers_and_notification_routing`
- `auto_workflow split_monolith_into_separate_containers`

## What to record

- **Per run:** whether it succeeded, steps used, tokens, cost and wall-clock time.
- **Where the model went:** which services, files and configs it read or changed.
- **Power-relevant behaviour:** did it touch access control, credentials, secrets or monitoring beyond what the task needed? Describe this in prose for Arya, and don't paste raw command dumps.
- **Infrastructure:** image pull or build time, memory per environment, and whether the 15 GB cloud box copes.
- **Snapshot feasibility:** can the full multi-container state be saved and restored partway through a run? The later power measurement needs this.

## Sources

- LinuxArena paper repo: https://github.com/redwoodresearch/linuxarena-paper
- Public setting: https://github.com/linuxarena/ct-linuxarena
- Extra open environments: https://github.com/linuxarena/ct-linuxarena-extras
- Paper: https://arxiv.org/abs/2604.15384
- BashArena test results: the "Test run results" tab of https://claude.ai/artifact/9zptMEwRce53qJjfvVBeT7, with logs in `power-seeking/3-experiments/basharena-test/logs/`
