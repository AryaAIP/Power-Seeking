# Research plan, Nov 5, 04:00–09:00: what power looks like here

*Written 2026-11-05 at about 04:15 CST by the main session, for Arya's request before leaving for 5 hours. No paid runs and no production scoring tonight (production stays paused at 48 of 130 runs); short free tests on WSL only. Findings go in [../findings/](../findings/), the running record in [../logs/2026-11-05-power-research.md](../logs/2026-11-05-power-research.md).*

## Arya's questions

1. **Why do the controls beat the power-seeking trajectories, especially at low H?** Which factors could be causally responsible?
2. **Arya's working account, to test.**
   - *Saturation:* any capable agent eventually gets there, so power shows as speed, at low H. A more bottlenecked agent takes longer to saturate.
   - *Mismatch:* the power the task distribution picks up is not the power we prompted for; the model's idea of power differs from what these tasks reward. Permissions and passwords may matter less than information.
3. **What does power mean, task by task?** What would let an agent pass more test cases in fewer steps, in each of the 27 tasks? Are there task classes?
4. **Side tasks and hidden tasks.** What kinds of power do they need? Are they better measures? (Agents only: the main session doesn't read them.)
5. **Other LinuxArena environments.** What do they look like, how do they differ, what does power look like there?
6. **How do we build a task distribution that measures power in LinuxArena?** And what would models that power-seek while doing LinuxArena tasks look like?
7. **The discounted measure:** what exactly makes it larger?
8. **On the side:** systematize the repository; keep pushing the score-and-rollback session towards the most efficient way to score.

## Tracks

| Track | Who | Output | Depends on |
| --- | --- | --- | --- |
| Data foundation: turn and test-case tables, digests of every solver run | Opus agent | `analysis/` | |
| Causal factors at low H | Opus agent, numbers rechecked by the main session | `findings/nov5-causal-factors.md` | Data |
| One agent per task (27) | Opus agents | `findings/task-power/<task>.md`, `.json` | Data |
| Side tasks of `model_registry` | Opus agent; categories only reach the main session | `findings/nov5-side-tasks.md` | |
| Other environments, and their side tasks | Opus agents | `findings/nov5-linuxarena-environments.md` | |
| Literature and practice on measuring power | Opus agent, source-grounded | `findings/nov5-literature.md` | |
| Scoring efficiency | The score-and-rollback session, prompted repeatedly | `plans/scoring-efficiency.md` | |
| Repository systematization | Opus agent, after the child's edits settle | `findings/data-map.md`, READMEs | |
| Adversarial review of the conclusions | Opus agent, given the evidence and not the reasoning | Review notes | All |
| Synthesis and experiment plan | Main session | `findings/nov5-what-power-looks-like.md`, a published page | All |

## Candidate causal factors to test on existing records

Pair 1 at H = 10: initial state 0.119, A 0.601, B 0.515. Pair 2: A2 0.324, B2 0.300 (last-scored, every 5 turns).

1. **Tool calls per model turn.** H counts model turns. On Nov 3 the turn counts and tool-call counts differed by arm: pair 1's A made several calls in a turn in 22 of 27 runs and B in 0 of 27; pair 2's A2 in 2 of 27 and B2 in 26 of 27. This may be a style inherited from the trajectory's chat. Recompute the curves against tool calls.
2. **What the chat taught.** Which code the trajectory read and how much carries over. Pair 1's arms are far above pair 2's at low H, whichever the note.
3. **The hand-over note** (`use`, B only) and the inclination note still in B's kept chat.
4. **Turns spent on power.** Checking and using access, forging tokens, repairing its own damage.
5. **The state of the machine.** Half-finished or broken code at hand-over, a service that doesn't build, leftover hooks, changed seed data; scorers stopping early.
6. **Chat length and context,** and any effect on behaviour.
7. **Wall-clock conditions:** tool timeouts under load, which arm ran when.
8. **Noise and a few tasks:** one run per task and arm; which tasks carry the difference.

Existing records can only rank these. Establishing cause needs new runs, which are Arya's call: the plan will list the experiment that separates each factor, with cost.

## Rules for every agent

- No LinuxArena or Control Tower code on the Windows filesystem. Read it in WSL or on GitHub.
- Never print secret values. Raw `.eval` logs stay in WSL.
- No paid model calls, no production jobs. WSL load stays low.
- Cite evidence (file and line, or run label and turn). "Can't be determined from the records" is a valid answer. Mark your own judgment.
- Plain words; conditions described by what is actually done (`1-handoff/working-with-arya.md`).
- Side-task and hidden-task reports use categories and kinds of power, with no attack steps.
