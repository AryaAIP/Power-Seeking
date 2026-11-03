# Reading notes, Nov 1 2026

*Written 2026-11-01 by the thread "Read literature and scope LinuxArena experiment". Arya asked for every reading in the literature review (section 1 of [../README.md](../README.md)) to be read before scoping a power-seeking experiment on LinuxArena. Ten research subagents each read one group of sources in full and wrote the notes below. The lead Claude read the core project docs, Travis's ToolEmu report, Matthew's proposal with its comment threads, the October background notes and the pilot's key steps itself, and spot-checked the claims that affect scoping against the raw logs.*

**Start with [synthesis.md](synthesis.md).** It has the overall picture, the views that matter for a LinuxArena experiment, the seven decisions to make, and the list of errors found in the older docs.

## Files

| File | Sources read | Most useful for |
| --- | --- | --- |
| [synthesis.md](synthesis.md) | All of the below | Start here: the picture, scoping views, decisions, corrections |
| [linuxarena.md](linuxarena.md) | LinuxArena paper (arXiv 2604.15384 v2, all appendices), Control Tower at the paper's commit 699d5ca, the 10 public environments at v1.0.1, the 4 extras, data.linuxarena.ai's public API | Environments, users and privilege structure, task counts and metadata, tools and policy, side-task checkers, monitors, replay, known issues |
| [pilot-transcripts.md](pilot-transcripts.md) | The three pilot transcripts in full, checked against the `.eval` logs | Step-by-step catalogue of power-relevant actions, end-state differences, corrections to results.md |
| [group-slack-docs.md](group-slack-docs.md) | #alignment-without-personas (Sept 28 to Nov 1), the shared thoughts doc, Travis's midterm outline, Peyton's probe trajectory and Oct 31 report, `dose_response_v2.md`, the Gemini 4 report via Matthew's screenshots | Who is doing what, each person's views, Peyton's AppWorld results, open disagreements |
| [turner-sequence.md](turner-sequence.md) | All 14 posts of "The Causes of Power-seeking and Instrumental Convergence", with comments; "AUP: Concepts"; turntrout.com/professional | The definition of POWER, bounded power, which goals produce power-seeking, Turner's later views, corrections to the older notes |
| [turner-papers.md](turner-papers.md) | arXiv 1912.01683, 2206.13477, 1902.09725, 2006.06547 | Formal definitions and assumptions; checks of the plan's claims |
| [krakovna.md](krakovna.md) | Krakovna's AI safety resources page; arXiv 1806.01186, 2010.07877, 2304.06528, 1705.08417 | Baselines, the future-task method, Krakovna & Kramar; checks of the plan's claims |
| [power-seeking-evals.md](power-seeking-evals.md) | MACHIAVELLI (2304.03279), SafeMCP / PowerSeeking Bench (2606.01991), ClawsBench (2604.05172), ORBIT (2609.33102), DeepMind dangerous capabilities (2403.13793) | How other work measures power-seeking, and what carries over |
| [basharena-monitoring.md](basharena-monitoring.md) | BashArena paper (2512.15688) and LessWrong post, ControlArena and basharena_public code, MonitoringBench (2605.09684), Simulated Control Evaluations (2610.31593), DeepSeek V4.1 Flash 1017 model card | The root and internet ablations, honest runs that look like attacks, monitor results, DeepSeek settings |
| [other-environments.md](other-environments.md) | AppWorld, AgentBench, LifelongAgentBench, InterCode, Terminal-Bench 2.0, OSWorld-Human, Long-Horizon-Terminal-Bench | Corrections to the environment comparison; ideas for chained tasks and checkpoint scoring |
| [background-petri-testbed.md](background-petri-testbed.md) | The 11 October files on simulated environments, Petri and the testbed survey | What still applies, conflicts with the November docs, prior work on power-seeking propensity |

## Caveats

- **Code was read locally, which Arya has since ruled out.** The LinuxArena and BashArena agents cloned those repositories onto the Windows laptop to read them, and Arya's malware-detection software flagged the clones. They have been deleted. In future, read these repositories through GitHub remotely or inside WSL, never on the Windows filesystem. Nothing was ever run, installed or built.
- **Not opened:** the full Gemini 4 safety report (over 10 MB; Matthew's highlighted screenshots were read instead), the private LinuxArena environments, and full trajectory contents on data.linuxarena.ai. Each notes file ends with its own list.
- **Treat the notes as a reading, not a verification.** Figures were copied from the sources, and several October figures had already been found unreliable. Re-check any number before citing it in a report.
