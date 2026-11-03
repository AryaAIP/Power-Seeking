# Working with Arya

*Written 2026-11-01 from Arya's own feedback across the project threads. Project memory is off, so this file is how these preferences carry forward. Add to it when Arya gives new feedback.*

## Writing

- **Clarity comes first.** In Arya's words: "clarity in communication is very important to me."
- **Use plain words, and explain every technical term the first time.** The main doc has a "Terms used in this doc" list, which is a good model.
- **No odd phrasing or jargon.** Say "your proposal", never "your grant". Don't use "flagged grants" or similar invented labels. Don't use analogies from operations work.
- **Describe experimental conditions by what is actually done.** For example, "the solver starts a new chat on the changed machine", not an invented label like "the fresh-context arm" (Nov 1: Arya asked for "representative, non-made-up words").
- **Lead with the answer, then the reasoning.** If something can be read two ways, say which reading you chose.
- **Say where every claim came from.** Link sources. Be honest about what you opened yourself and what you only saw linked, and label estimates as estimates.

## Making decisions

- **Scope first, then wait for a go-ahead before building.** Arya often asks for a scope and then approves it, for example the handoff docs on Nov 1.
- **Show options side by side, with arguments for and against each, and decide together.** The environment comparison on the doc's Environment options tab is the model.
- **Arya makes the research calls.** Which environment, which model, whether to use side tasks. Recommend, but don't decide for Arya.
- **When Arya asks to discuss, run nothing until the plan is agreed.** On Nov 1 Arya stopped a run that was being prepared: "we haven't discussed yet."
- **Keep tests small.** For trial runs, Arya caps model runs (3 for the BashArena test: "we're just testing"). Don't exceed a cap without asking.

## Research preferences

- **Real environments, not simulated ones.** No ToolEmu; Travis already used it, and its tools are simulated.
- **Use existing, well-made environments.** "We are not constructing environments."
- **No side tasks.** They're malicious actions built for control evaluations.
- **Prompts to the model are gentle and natural.** Instructions to the agent, such as an instruction to gain power or a note asking it to stop, should read like something a real team might say. Harsh prompting may put DeepSeek into odd behaviour (Arya, Nov 1).
- **Statistics matter.** Every power estimate needs a confidence interval.
- **Interest has moved toward diffuse settings.** As of Nov 1, Arya wants settings where the model moves around a system and does many things, not single-deliverable tasks. Arya wants to read trajectories, ideally together, to see what the model actually does.
- **Plans to run locally in future,** on the laptop. See runbook.md.

## Practical

- **This folder also lives on Arya's computer.** Arya asked for the handoff docs to be copied there, and on Nov 1 asked for the folder to be organised. Keep the numbered layout described in the README: new experiments go in `3-experiments/<name>/` with their results, transcripts, logs and harness, and the README index gets a line for each new file. Keep the local folder and `/mnt/project-files/power-seeking/` in step.
- **Keep the notes current during long work** (Arya, Nov 1). Update them at every launch, finish or failure, and at least every 30 minutes. After a compaction, read the notes and the literature notes, and check what's actually running, before doing anything else.
- **Chase failures in small first runs** (Arya, Nov 1). If something goes wrong in the first 6-task measurements, fix it and rerun every run it affected, trajectories included. Don't carry the fault into larger runs.
- **Use subagents where they help,** but not for their own sake (Arya, Nov 1).
- **Never ask Arya to paste an API key into chat.** Keys go in the cloud environment settings or a local environment variable.
- **Arya is a SPAR fall 2026 participant** working with Matthew Khoriaty, Travis Kim and Peyton Li in Slack #alignment-without-personas. The midterm report was due Nov 2.
