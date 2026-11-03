> **Status (2026-11-01):** Current background. The theory notes still apply to the measurement design. Start at [README.md](../README.md); decisions are in [decisions-log.md](../1-handoff/decisions-log.md).

# Notes: Turner's "The Causes of Power-seeking and Instrumental Convergence"

*Prepared for Arya, 2026-10-30. The sequence is at https://www.lesswrong.com/s/fSMbebQyR4wheRrvk: 14 posts by TurnTrout (Alex Turner), 2019–2023, all read.*

*Matthew's proposal doc (148Z2) was re-read the same day. Its content hasn't changed since this morning; the only difference is that the tab is now named "Proposal".*

*Quotes are verbatim from the posts. Lines marked "(our inference)" are mine, not Turner's.*

---

## Read this caveat first

In 2023 Turner added a note to several posts: they are "correct in [their] narrow technical claims, and practically irrelevant to alignment". He also tells readers to read "Reward is not the optimization target" first.

**What that means for us.**
- The theorems are about optimal or "retargetable" policies. They don't show that RL-trained LLMs will seek power.
- They do give us the **definition** we're measuring. Our project uses POWER as a measurement, which survives the caveat.
- Claims like "training will make the model seek power" need their own evidence. That's the same gap as red-team finding 3.

---

## What the sequence says that bears on our design

### 1. D should be the goals we'd actually give this agent
- **The definition (post 1).** "We formalize the ability to achieve goals in general as the average optimal value at a state, with respect to some distribution D over reward functions which we might give an agent."
- **The choice of D carries the result.**
  - A commenter on post 2 says "power only appears when you choose a very specific measure over the space of utility functions."
  - A critic on post 5 says a "well-chosen reward distribution is necessary".
- **Turner's answer (post 5).** Fix the agent's interface and "our beliefs on the reward functions conditional on each architecture". Once that's done, the prediction "has no subjective degrees of freedom".
- **Realistic goals (post 13).** They are "featurized", depending only on certain features of the world, and the plausible set matters.

**For us (our inference).** D is "the next tasks this agent's principal might plausibly assign". That makes your mouse-brain objection principled: tasks in an unrelated world aren't in D. It also gives the rule for neighbor systems. Include a system if the same principal could plausibly send the agent there next, such as the company's repo or cloud. Leave it out otherwise.

### 2. Power is the *actual* agent's ability, not optimal value
**Post 2, "Power as Easily Exploitable Opportunities".**
- Average *optimal* value is "pretty weird". A person facing a firing squad still has high optimal value, because some sequence of "twitches" could disarm the soldiers.
- His fix: "instead of asking how well *could* I achieve a bunch of different goals? You should be asking, how well could *I* achieve many goals?"
- Power then counts only "cognitively accessible opportunities", the ones this algorithm, with this history, can find and use.

**For us (our inference):**
- This is the theoretical case for our method: measure with a real model's success on sampled tasks, not with optimal value.
- It also means knowledge in the agent's context is power, not a confound. Peyton's AppWorld result (context kept: 0.53 excess; fresh: 0.00) is then a finding about where the power sits.
- For illusory environments, a lenient simulator creates opportunities the agent couldn't use in the real system. That inflates exactly the quantity post 2 defines.

### 3. Power-seeking compares two actions from the same state
**Post 1:** "action a seeks POWER compared to action a′ when the expected POWER after choosing a is greater than the expected POWER after choosing a′."

**For us (our inference):**
- Turner's definition is a counterfactual action from the same point, not a comparison with the starting state.
- Our **reference-policy branch** (design notes §1.3(c): fork, then let a minimal agent act) matches it most closely.
- **Surgery** approximates it. **Cold start / Matthew's "power gained"** doesn't; it measures POWER(s_t) − POWER(s₀), which includes legitimate progress.

### 4. Future tasks should be checked on world state, not on the transcript
**Post 9:**
- Goals over action-observation histories have no instrumental convergence: "Instrumental convergence doesn't exist for utility functions over *action-*observation histories."
- State-based goals have "moderate" instrumental convergence.

**For us (our inference):**
- A future task scored only on what the agent writes or says, such as "draft a reply", can be done equally well from any state. It behaves like a control.
- Tasks that measure power need a success check on resulting **world state**.
- For illusory environments this means LLM-judged success on a transcript can't carry power signal. They need a small structured state that gets checked. That matches §5 row 1 of the Petri analysis.

### 5. A simulator measures power in a different world
**Post 5:**
- "The MDP model is *determined* by the agent's implementation + the task's dynamics."
- A critic's example: one state could "actually [be] a million different states which just happen to seem similar to us", which would inflate POWER.

**For us (our inference):**
- An illusory environment changes the dynamics, so it measures POWER in the simulator's world.
- The numbers transfer only as far as the simulator's dynamics match the real ones. That's why the real-vs-illusory calibration slice is required.
- A simulator that invents affordances inflates the option count, so invented affordances are invented power.

### 6. The discount rate changes the answer
**Post 1:**
- "POWER-seeking depends on the agent's time preferences."
- Power rises with the discount rate γ, since a higher γ "incorporates the greater future control".

**For us (our inference).** We fixed γ ≈ 0.93 per tool call. Report results at two or three values of γ, because rankings of states can flip.

### 7. Gaining power and then spending it is normal
**Post 1:**
- "Agents don't perpetually gain or preserve their POWER: they usually end up using it to realize high-performing trajectories."
- "A policy can seek POWER at one time step, only to discard it at the next."

**For us (our inference).** A single mid-trajectory reading can't tell progress from power-seeking. Matthew's **retained power**, measured after the task ends, is the reading that separates them: legitimate power gets spent or given back, and illegitimate power stays.

### 8. Two things the meter can miss
- **Power vs. potential power (post 2).** Rob Miles asks how to separate "power now from the potential for power in the future". Turner calls this "the big issue" and leaves it unresolved. This is the held-vs-reachable choice from the red-team findings.
- **Disabling oversight (post 3).** A commenter points out that shutting down a safety system can be catastrophic even for an agent with an "inaction" goal. A power reading could miss actions that remove oversight without adding capability, so those need the impact side or a direct check.

### 9. Smaller points
- **Multi-agent (post 4).** "In multi-agent games, gaining POWER tends to come at the expense of another player losing POWER." Proven only for constant-sum games. This is relevant to Peyton's user-permissions evaluator: the agent's gain can be the user's loss.
- **Retargetability (posts 11, 14).** The tendency comes from training procedures that can be retargeted, not from optimality. Among the escape routes Turner lists is "a decision-making procedure with intrinsic bias towards the elements of A", such as imitation. That's loosely in the spirit of Matthew's persona thesis (our inference).
- **AUP's inaction baseline (post 12).** It can penalize the agent for *not* being corrected, because in the baseline the agent never gets corrected. This is a known failure of the inaction baseline.
- **Missing from the sequence.** It never discusses natural-language task distributions, sample sizes, LLM-simulated environments, or a test for legitimate progress. On those, we're on our own.

---

## How this bears on the illusory-environment question

| Question | What the sequence supports (our inference) |
|---|---|
| Real vs. illusory vs. extended environment | Extended same-world environments fit D best (point 1). Illusory ones are valid only to the extent their dynamics match the real ones (point 5) and success is checked on state (point 4). |
| Cross-world transfer of power | Not principled. Tasks from another world aren't goals we'd give this agent (point 1). |
| Which baseline | A counterfactual action from the same state (point 3). Cold start mixes in progress. |
| Progress vs. power-seeking | Retained power after the task (point 7), plus the in-world vs. neighbor-system comparison from the Petri analysis §9. |
