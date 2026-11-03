# Run investigation: the style it borrows

How the dashboard presents one agent run, borrowing layout patterns from METR's write-up of the
OpenAI / Hugging Face incident (2026-08-26), section "July 11th afternoon". We borrow layout and styling only: none of
METR's text, branding, logo, robot icon or fonts. Colours and type come from our page's own `:root` tokens
(`--ink`, `--ink-2`, `--muted`, `--line`, `--axis`, `--wash`, `--surface`, `--critical`, `--font`, `--mono`), so light
and dark mode follow the page. The code is `run_investigation.py`; `run-investigation-preview.html` shows both runs.

## Patterns we use

1. **Lead with the finding.** METR opens each phase with a dense paragraph that says what happened before any figure.
   Each investigation starts with one plain paragraph: what the agent did, at which steps, and what it kept.
2. **Phase headings that state a claim.** METR's headings read "when: who did what" ("July 11th afternoon: X achieves
   ..."). Ours read "Steps 16–22: a wrapper and the build script give the agent root". Each phase is a collapsible
   `<details open>` with a small rotating triangle, as METR's sections are.
3. **A to-scale overview strip.** METR's agent-timeline figure shows each agent's active span, coloured by stage.
   We show one bar for the run, step 0 to the last step, with a marker per action (coloured by outcome) and the most
   concerning action labelled. Each marker links to its entry below.
4. **A vertical timeline by step.** Not to scale: a left rail with the step number in tabular figures, a dot on a
   vertical line, and the action card to its right. Actions at the same step share one dot.
5. **Monospace for what the agent touched or ran.** METR sets agent identifiers and commands in monospace and quotes
   agent output in a separate excerpt block with a speaker icon. We set file paths and backticked commands in `--mono`,
   and repeat each quoted command in a small excerpt line marked with a terminal glyph and `$`.
6. **Outcome as a severity cue, colour plus words.** METR's annotation cards carry a 4px coloured left border by
   category on a lightly tinted background. Our card's left border and dot show the outcome: hollow grey and a dashed
   border for "didn't work", solid `--ink-2` for "worked, not kept", `--critical` for "worked and kept at the end". The
   words are always in a badge, so colour is never the only cue.
7. **One highlighted action.** The most concerning action gets the tinted `--critical` card, an eyebrow line ("Most
   concerning action") and a labelled marker on the strip. It is picked by rule (worked and kept, then kind, then
   root/superuser wording, then earliest) unless the caller names a step.
8. **Badges, not prose, for the labels.** Kind, "Worked" / "Didn't work" / "Partly worked", "Kept at the end" /
   "Undone before the end" / "Still there at the end", in pill badges like METR's legend chips.
9. **Side notes for the labelling notes.** METR keeps evidence and caveats out of the running text (footnotes,
   annotation cards). The labelling agent's note sits beside the action on a wide screen and under it on a narrow one,
   in smaller `--ink-2` text.
10. **Linked evidence.** METR cross-links its sections and footnotes. Step mentions in the notes ("reverted at step
    50", "see step 21") become links to that step's entry when one exists, and each item in the closing box links
    back to its step.
11. **A closing box.** METR ends sections with what it means for the reader. We end with "What it kept at the end":
    the actions that worked and lasted, then what was still there though the agent tried to remove it, then (quieter)
    what it undid before finishing.
12. **Restrained type and spacing.** METR's headings are medium weight, not bold; body text is ~16px with generous line
    height; panels have 1px borders and 8–12px radii. We keep the page's 15px body (15.5px for the lead paragraph),
    `--r` radius and 1px `--line` borders, with semibold (600) headings no larger than 21px, and small uppercase
    eyebrows ("Run investigation", "Most concerning action", the note labels) as METR uses for figure labels.

## Layout

The fragment is a container (`container-type: inline-size`), so it adapts to the panel it sits in, not the window:
side notes move beside the action at 760px and wider, and the step column narrows below 520px. Checked at 1200px and
375px, in light and dark mode, under the dashboard's own global styles.

## Wording

- The page's terms: "the agent", "step" (one model turn, the unit of the step budget H), "test cases", "initial
  environment state". The labels' `turn` is shown as the step; their transcript `step` number is only a tooltip, and
  "step N" in a note is converted from the transcript's numbering when the two differ.
- No secret values. The labels are already redacted; the module also removes anything that looks like a connection
  string with a password, a JWT, an access key, a private key or a long token before rendering.
