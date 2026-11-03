> **Status (2026-11-01):** Current. Reading notes written by a research subagent in the thread "Read literature and scope LinuxArena experiment". Faithful summary unless marked [Agent judgment]. Start at [README.md](README.md) in this folder.

# Turner papers: POWER, retargetability, AUP (reading notes)

Read 2026-11-01 for the SPAR power-seeking meter (LinuxArena). Everything below is attributed to the authors unless it is marked **[Agent judgment]**. Quotes are short and located by section.

**Source access**

| # | Paper | What was read |
| --- | --- | --- |
| 1 | Turner, Smith, Shah, Critch, Tadepalli, *Optimal Policies Tend To Seek Power* (NeurIPS 2021), arXiv 1912.01683 | arXiv HTML (v10), characters 0 to ~200K of ~249K: all of the main text and Appendices B and C, plus part of D and E. The last ~49K characters (the remaining proof appendices) were not read. |
| 2 | Turner & Tadepalli, *Parametrically Retargetable Decision-Makers Tend To Seek Power* (NeurIPS 2022) | **The ID in the brief, 2206.11831, is Turner's PhD thesis** (*On Avoiding Power-Seeking by Artificial Intelligence*, 287 pp.), not this paper. The paper is **arXiv 2206.13477** (v2). Read its HTML for the main text, Section 6 and Appendix A up to A.7. Appendices B to D (proofs, the Montezuma's Revenge (MR) details and D.11) were truncated and not read. |
| 3 | Turner, Hadfield-Menell, Tadepalli, *Conservative Agency via Attainable Utility Preservation* (AIES 2020), arXiv 1902.09725 | Full text, from the v3 PDF and the HTML. The arXiv header title is just "Conservative Agency". Figure 4 is a plot: only its axis ticks could be extracted. |
| 4 | Turner, Ratzlaff, Tadepalli, *Avoiding Side Effects in Complex Environments* (NeurIPS 2020), arXiv 2006.06547 | Full text from the v2 PDF and the HTML. Figures 3 to 5 are plots, so only the text descriptions of them were read. |
| + | Turner (TurnTrout), *Seeking Power is Convergently Instrumental in a Broad Class of Environments*, LessWrong, 2021-08-08 | Full post via the LessWrong API. Read only because the plan cites it for claim (c). |

---

## 1. Optimal Policies Tend To Seek Power (arXiv 1912.01683)

### Setting
- The setting is a rewardless finite MDP with stochastic transitions allowed. Reward functions are **state-based**, R ∈ ℝ^|S| (Sec. 3, Def. 3.1).
- The discount γ ∈ [0, 1] is treated as a variable, and γ = 1 is handled as the average-reward limit.
- Policies are stationary and deterministic. F(s) is the set of visit-distribution functions available from s.

### POWER (Def. 5.2)
$$\mathrm{POWER}_{\mathcal D_{bound}}(s,\gamma) = \frac{1-\gamma}{\gamma}\,\mathbb E_{R\sim\mathcal D_{bound}}\big[V^*_R(s,\gamma) - R(s)\big]$$

- **D_bound** is *any* probability distribution with bounded support over ℝ^|S|, i.e. over state reward functions. The worked example uses uniform IID rewards: the empty-state example has POWER 1/2, and a state with more options has 2/3 (Sec. 5 figure).
- **Why the normalisation (Sec. 5).** The authors first define the average optimal value E[V*_R(s, γ)] (Def. 5.1) and then reject it as a power measure, for two reasons:
  - It rewards "initial presence at state s (over which it has no control)", which is why R(s) is subtracted.
  - It diverges as γ → 1, because ‖f(γ)‖₁ = 1/(1−γ). The factor (1−γ)/γ fixes this.
- **[Agent judgment]** Because V*(s) − R(s) = γ·max_a E_{s′}[V*(s′)], POWER equals (1−γ)·E_R[max_a E_{s′∼T(s,a)} V*_R(s′)]. In words, it is the (1−γ)-normalised optimal value counted from the *next* step on.
- **Properties:**
  - POWER is Lipschitz continuous in γ (Lemma 5.3).
  - POWER ≤ E[max_s R(s)] (Prop. 5.4).
  - If s and s′ reach each other in one step with probability 1, then |POWER(s) − POWER(s′)| ≤ (c − b)(1−γ), where [b, c] is the reward support (Prop. 5.5).
- **Distribution dependence.** The authors state that POWER depends on the choice of distribution, and some distributions give unintuitive states maximal POWER (Sec. 5). They also note that high POWER need not mean "good" in the everyday sense.

### Power-seeking and optimality probability
- **Power-seeking (Def. 5.6)** is relative. At (s, γ), action a seeks more POWER than a′ if E_{s′∼T(s,a)}[POWER(s′, γ)] ≥ E_{s′∼T(s,a′)}[POWER(s′, γ)].
- **Optimality probability (Def. 4.3 and 4.4).** P_D(s, a, γ) is the probability over R ∼ D that *some* optimal policy takes a at s. In the paper, "tend to" refers to this quantity.
- **Orbit (Def. 6.4).** The orbit of D is the set of all pushforwards of D under state permutations, {ϕ·D : ϕ ∈ S_|S|}. Permuting only changes which states get which rewards.
- **"Most" (Def. 6.5).** f₁(D) ≥_most f₂(D) means that in D's orbit, at least as many elements have f₁ > f₂ as have f₁ < f₂. A footnote to Prop. 6.6 says "at least half of each orbit must agree", and Lemma B.2 makes this precise. For one-element orbits, e.g. IID rewards, "most" reduces to the plain inequality (Lemma B.3).
- The authors flag that **weighting the orbit uniformly is an assumption** (footnote 4).

### Theorems and their assumptions
| Result | Claim | Assumptions | γ |
| --- | --- | --- | --- |
| Prop. 6.6 | More options means more POWER: if F(s) contains a copy of F_nd(s′) via an involution ϕ, then POWER(s) ≥_most POWER(s′). | A symmetry: a copy of the other state's non-dominated visit distributions. The converse fails when there are extra non-dominated options. | All γ ∈ [0, 1] |
| Prop. 6.9 | Keeping options open. Suppose F_a contains a copy of F_{a′}. (1) If s ∉ Reach(s, a′), then a seeks POWER ≥_most a′. (2) Under a reachability condition, P(a) ≥_most P(a′). | Environmental symmetry between action-subtrees, plus reachability conditions. | All γ ∈ [0, 1] |
| Prop. 6.12 | Recurrent-state-distribution (RSD) version at γ = 1. | A copy of the RSDs. | γ = 1 |
| Thm. 6.13, Cor. 6.14 | Average-optimal policies tend to end up in "larger" RSD sets, and tend not to end in any given 1-cycle (e.g. a shutdown state) when a third RSD exists. | The RSD sets have pairwise orthogonal vector supports. | γ = 1. Strict POWER inequalities extend to γ near 1 by continuity, but **not** the optimality-probability claims (Sec. 6.2). |

- All results hold for degenerate distributions, i.e. single reward functions, and then "most" is a statement about that function's permuted variants (Sec. 6.2).
- Shutdown-avoidance relies on **modelling shutdown as a terminal state** (Sec. 6.3).

### POWER and optimality are not the same (Appendix B, "Seeking Power can be a detour")
- **Prop. B.1.** Greater POWER does not imply greater optimality probability. In the Fig. 10 environment at γ = 1, action N leads to higher POWER (3/4 against 2/3), yet P(N) = 1/3 < 2/3 = P(NE).
- **Prop. B.4.** An action that tends to seek POWER need not tend to be optimal.

### POWER for an actual policy (Appendix C, "Sub-optimal Power")
- **Def. C.1.** POWER^pol_D(s, γ) = E over R ∼ D, a ∼ pol(R, γ)(s) and s′ ∼ T(s, a) of lim_{γ*→γ} (1−γ*)·V^{pol(R,γ)}_R(s′, γ*).
- Here pol maps each (reward function, γ) to a policy, meant as the best policy the agent knows about. The normalisation is the same (1−γ) factor.
- Standard POWER is the special case where pol always returns an optimal policy (Lemma E.36).
- The authors say POWER^pol "increases as the policies returned by pol are improved". Their example: a random policy gives E[X], a partly informed policy gives E[max of 3], and the optimal policy gives E[max of 5].
- A bounded agent maximising its sub-optimal POWER may head to a *different* state than an optimal agent would.

### Authors' stated limitations (Sec. 7 and Conclusion)
- Learned policies are rarely optimal. The authors expect this to "seriously constrain the applicability of this theory" (Sec. 7).
- Reward acts as a gradient signal under policy-gradient training, not as an optimisation target (Sec. 7, footnote 1).
- The results cover only finite, fully observable MDPs. Generalisation to partial observability is expected but not shown.
- The symmetry conditions can be hard to satisfy under "irregular stochasticity" (Sec. 7).
- Sub-optimal policies and "almost similar" RSD sets are left open.
- It is not formally understood whether, when or why power-seeking disempowers other agents.
- Resource accumulation when γ ≈ 1 is a *conjecture*.
- Designers specify rewards with prior information, so "most" does not bound the risk of any particular reward.
- The results "do not mathematically prove" that superintelligent AI will seek power (Conclusion).

### Usable for an LLM power meter
- POWER is a normalised average of attainable value over a goal distribution. Its sub-optimal version (App. C) is exactly "how well this particular solver does, averaged over goals".
- The comparison is between actions from the same state (Def. 5.6).
- Two definitional choices deserve copying:
  - Exclude credit for the current state (subtract R(s)).
  - Normalise by (1−γ).
- The paper says nothing about approximating POWER by sampling a few reward functions. It is defined as an exact expectation.

---

## 2. Parametrically Retargetable Decision-Makers Tend To Seek Power (arXiv 2206.13477; not 2206.11831)

### Core idea
The authors argue that power-seeking tendencies are "not unique to reward maximizers" (Sec. 1). The key sufficient condition is retargetability: "retargetability is sufficient to cause power-seeking tendencies" (Abstract).

### Definitions
- **Setting.** A decision-maker f(X | θ) gives the probability of choosing an outcome in set X, given a parameter θ ∈ Θ. Θ might be a utility function over outcomes, a reward function, or a featurised reward.
- **Pac-Man example (Sec. 2).** A = {die} is one outcome, and B = {eat apple, eat cherry} is two. Most utility functions over these 3 outcomes make staying alive optimal, because the agent "can't do anything when dead".
- **Orbit (Def. 3.1).** The orbit of θ is the set of its permuted variants. If Θ is not closed under permutation, the orbit is intersected with Θ (footnote 3).
- **"Most" (Def. 3.2).** f(B | θ) ≥ⁿ_most f(A | θ) means that in every orbit, the number of elements strictly favouring B is at least n times the number strictly favouring A.
- **Simple retargetability (Def. 3.3).** There is a permutation ϕ such that whenever θ makes the agent prefer A over B, ϕ·θ makes it prefer B over A.
- **n-fold retargetability (Def. 3.5).** There are n distinct such permutations, each keeping ϕᵢ·θ inside Θ.
- **Thm. 3.6.** n-retargetable from A to B implies f(B | θ) ≥ⁿ_most f(A | θ). Equivalently, at least n/(n+1) of each orbit favours B. **[Agent judgment]** That fraction is my arithmetic. The LessWrong posts state it in that form.

### What is covered
- **Retargetable decision-makers (Appendix A):** optimal, anti-optimal, Boltzmann-rational, satisficing (uniform over lotteries above a threshold), random, "numerical", greedy state-action reward maximisation, and an ε-greedy bandit (4-retargetable).
- **Learned agents:** a generic RL algorithm on featurised reward in Montezuma's Revenge (Sec. 4.3 and 5).
- **Explicitly not retargetable:** a "stubborn" decision-maker.
- **What the results don't need:**
  - Optimality: "orbit-level incentives do not require optimality" (App. A).
  - A finite environment, for Thm. 3.6 (Sec. 6.2). The authors don't yet know how to apply it to infinite-state POMDPs.
- **Theorems.** Prop. A.11 covers optimal, anti-optimal, Boltzmann and satisficing agents. Thm. A.13 covers any expected-utility-determined decision function.

### Actions versus outcomes
- **Sec. 4.1.** The paper shows retargetability over the *initial action* in MR. A random policy picks the 4 non-down actions with probability 4/5.
- **Sec. 4.2.** Reward is over final observations, and optimal policies "are not retargetable across the agent's immediate choice of action, but rather across future consequences".
- **Sec. 4.2 bound.** With horizon T = 1000, |O_stay| ≪ |O_leave|, so n = ⌊|O_leave| / |O_stay|⌋ is huge. This is "extremely retargetable".
- **Sec. 6.2 (when the argument does not apply):**
  - The agent is aligned.
  - The decision-making is not retargetable.
  - The decision-making is retargetable only "over e.g. actions" rather than final outcomes. This "seems less concerning, but also less practically useful".

### Learned agents (Sec. 4.3 and 5.2)
- Retargetability depends on capability and exploration. DQN does not leave the first room, so it is not retargetable in this sense. Go-Explore is argued to be more retargetable.
- Sec. 5.2 is speculative: trained agents "may be retargetable towards power-requiring outcomes" through the reward.
- Footnote 1: "reward function" is used loosely, citing *Reward is not the optimization target*.

### Limitations (Sec. 6.2)
- The results don't *prove* that unaligned power-seeking agents will be built.
- Infinite-state POMDPs and other training regimes are open questions.
- The MR proofs are long.

### Usable for a power meter
- This paper is about **propensity** (what decision-makers tend to choose), not measurement. Its contribution to a meter is the vocabulary:
  - "Power" is having a larger set of reachable outcomes, with n copies of the other action's outcome set.
  - A goal set closed under permutation is what the "most" claims quantify over.
- **[Agent judgment]** It is the better formal citation for claim (c), rather than the 2021 blog post.

---

## 3. Conservative Agency via Attainable Utility Preservation (arXiv 1902.09725)

### AUP definition (Sec. 3.1)
- **Penalty (Eq. 1):** PENALTY(s, a) = Σ_{i=1}^{|R|} |Q_{R_i}(s, a) − Q_{R_i}(s, ∅)|, where ∅ is a no-op. The authors describe it as the L1 distance from the no-op, in an embedding where each dimension is an auxiliary value function ("attainable utility").
- **Scale (Eq. 2):** SCALE(s) = Σ_i Q_{R_i}(s, ∅), "the total ability to optimize the auxiliary set". Alternatively, the designer can scale by the penalty of some mild action.
- **AUP reward (Eq. 3):** R_AUP(s, a) = R(s, a) − λ·PENALTY(s, a) / SCALE(s), where λ ≥ 0 expresses the designer's belief about misspecification.
- **Auxiliary rewards** are over state-action pairs (R ⊂ ℝ^{S×A}), and the auxiliary set "does not necessarily" contain the true reward.

### Baselines (Sec. 3.2, Fig. 1)
The paper compares three baselines:
- **Starting state.** This penalises natural evolution of the environment.
- **Inaction.** The state had the agent never acted. This produces offsetting: rescue the vase, then put it back to break.
- **Stepwise inaction.** Compare acting with not acting at each time step. This is the default.

### Deviation metric (Sec. 3.2)
- AUP uses the **absolute value**, so it penalises *increases* in attainable utility as well as decreases.
- Reason: an agent that avoids shutdown *raises* auxiliary Q-values, so a decrease-only penalty would not stop it. "Decrease AUP" fails the Correction environment.

### Delayed effects (Sec. 3.2)
- The single-step no-op comparison under-penalises delayed effects.
- Planning agents therefore compare no-op rollouts up to time step 9 (Fig. 2).

### Experiments (Sec. 4 and 5)
- **Environments:** five tabular AI-safety gridworlds (Options, Damage, Correction, Offset and Interference). Each has one designed side effect, scored at −2 when it happens.
- **Agent setup:**
  - Actions are up, down, left, right and no-op. Episodes last at most 20 steps.
  - Auxiliary rewards are "randomly selected from [0,1]^S" each trial.
  - Q-functions are learned by **tabular Q-learning**: 4,000 random-exploration episodes, then 2,000 ε = .2 greedy episodes.
  - Defaults: α = 1, γ = .996, λ = .67, **|R| = 30**.
  - Planning variants are 9-step optimal planners with perfect models, using Model-free AUP's learned auxiliary Q-values.
- **Sweep.** The authors vary γ, λ and |R| for Model-free AUP (Fig. 4, 50 trials per setting). The |R| axis ticks are 0, 15, 30 and 45. The exact |R| values tested and the per-|R| tallies are only in the plot.
- **The "five" claim (Sec. 5.1, full context).** If value functions were uncorrelated, one would need "an enormous number" of random auxiliary rewards to sample one resembling "don't have side effects". "However, merely five sufficed. This supports the notion that these value functions are correlated."
  - The text doesn't say which environment the number refers to.
  - The NeurIPS 2020 SafeLife paper (§6) later says Options "required |R| ≈ 5 for good performance".
- **Other sweep findings:**
  - Low γ produces a movement penalty. The best γ for Options is ≈ .996.
  - Small λ produces side effects in Options.
  - When λ > 1, the agent never finishes the episode.
- **Ablation (Table 1):**
  - AUP passes all five environments.
  - Model-free AUP fails Correction (delayed effects).
  - Starting-state AUP fails Correction and Interference.
  - Inaction AUP fails Offset.
  - Decrease AUP fails Correction.
  - Relative reachability fails Correction and Offset.
  - Standard Q-learning fails Options, Damage and Correction.

### Theory (Appendix A)
- PENALTY and R_AUP converge with probability 1 (Lemmas 1 and 2), and Q_{R_AUP} converges (Thm. 1), under standard Q-learning assumptions.
- AUP is invariant to positive affine transformations (Prop. 1).
- **There is no theorem linking AUP to POWER in this paper.**

### Limitations
- The authors only ablated AUP. They "expect" relative reachability would pass with AUP's design choices.
- They "speculate" that a small sample of somewhat task-relevant auxiliary rewards would work under partial observability.
- The environments are tiny and tabular.
- The conclusion says misspecification "may be inevitable".

---

## 4. Avoiding Side Effects in Complex Environments (arXiv 2006.06547)

### AUP as used here (Sec. 3, Def. 1)
- R_AUP(s, a) = R(s, a) − (λ/|R|)·Σ_i |Q*_i(s, a) − Q*_i(s, ∅)|. The penalty is **averaged over |R|** rather than scaled by SCALE, and auxiliary rewards are over states (R ⊂ ℝ^S).
- The learned Q_i "is a stand-in for the optimal Q-function".
- **Prop. 1 (App. A).** If s and s′ can reach each other with probability 1 in k₁ and k₂ steps, then max over R ∈ [0, 1]^S of |V*_R(s) − V*_R(s′)| < (1−γ^{max(k₁,k₂)})/(1−γ). So easily reversible actions are only lightly penalised.

### Auxiliary reward (Sec. 4 and 5.1, App. B.1)
- **AUP condition:**
  - Explore uniformly at random for 100K steps.
  - Train a continuous Bernoulli VAE (CB-VAE) with a **1-dimensional latent**. "The auxiliary reward function is then the output of the encoder E."
  - Learn its Q-network for 1M steps.
  - Train PPO on R_AUP for 3.9M steps, with λ ramped from .001 to .1. That is 5M steps in total.
- **AUP_proj condition:** the auxiliary reward is a random projection of a downsampled observation.
- **Sweep conditions (Sec. 5.2):** with Z > 1, linear functionals are drawn uniformly from (0, 1)^Z.
- **Why not uniformly random rewards.** The authors explain that Q-functions for rewards drawn uniformly over observations would have "extreme sample complexity" in SafeLife (Sec. 4).
- **[Agent judgment]** The abstract calls the auxiliary reward "a single randomly generated reward function". The main condition's reward is actually a learned one-dimensional encoding, not a random draw.

### Environments, baselines and metrics
- **Tasks:** four SafeLife (Game of Life) tasks: append-spawn, append-still, append-still-easy and prune-still-easy.
- **Training:** curricula of 8 randomly generated levels, 4 curricula × 5 seeds.
- **Baselines:** PPO, DQN, AUP_proj, and Naive (an L1 penalty for changes from the initial state).
- **Side-effect score:** the Wasserstein-1 distance between green-cell patterns and their natural evolution. Each disturbed pattern adds about 4.
- **Scale contrast (Table 1):** the earlier gridworlds had "dozens of states" with deterministic dynamics. SafeLife has "billions of states" with stochastic dynamics.

### Results (Sec. 5)
- **append-still-easy:** AUP has 27.8% of PPO's side effects.
- **prune-still-easy:** AUP removes only about a quarter of PPO's side effects. Naive does better there.
- **append-still:** AUP has 63% of PPO's side effects but lower reward.
- **append-spawn:** AUP gets 111% of PPO's reward with 39% of its side effects.
- **Default configuration:** 98% of PPO's return with just over half its side effects.
- **AUP_proj:** weak on three tasks, but good on append-spawn.
- **Sweep (Sec. 5.2):**
  - "Surprisingly, AUP does well with a single auxiliary reward function". |R| ranged over {1, 2, 4, 8}.
  - "We were surprised by the results for |R| = 4 and |R| = 8." In the 2019 gridworlds, more auxiliary rewards had reduced side effects without hurting reward.
  - The Discussion asks "why does |R| > 2 perform poorly?" and gives no answer.
  - Larger latent dimension Z also hurt. Appendix E says higher-dimensional auxiliary rewards are harder to learn.
- **Correlation is framed as a suspicion.** The authors write: "we suspect that optimal value at a state is heavily correlated across reward functions" (Sec. 5.2).
- **The paper does not mention POWER or power-seeking.**

### Limitations (Sec. 6, App. E)
- AUP needs a no-op action.
- It can miss spatially distant effects.
- Training the auxiliary networks separately is costly.
- Harder SafeLife tasks and partial observability are untested.
- AUP only regularises the learned policy, so mistakes during training are still possible.
- Performance is sensitive to the randomly generated curriculum (App. E).

---

## 5. Claim checks against the plan (`1-plan-and-map.md`)

### (a) "In the AUP experiments about five random goals were enough" (Part 3, *Limits of a finite task set*)
**Verdict: the number is accurate for one setting, but the claim is overstated as used.**

What the papers support:
- *Conservative Agency* §5.1 says "merely five sufficed".
- The SafeLife paper §6 says the gridworld Options environment "required |R| ≈ 5 for good performance".

Caveats the sentence drops:
1. It is the gridworld paper only, with one designed side effect per level, "dozens of states" and deterministic dynamics.
2. The auxiliary goals were dense random rewards over *every* state, drawn from [0, 1]^S. They were not sparse, hand-written tasks.
3. Success meant avoiding a side effect (impact), not detecting power.
4. In the other AUP paper (SafeLife), one *learned* auxiliary reward was used, not five random ones. Four or eight did *worse*, and the authors couldn't explain why.
5. The authors present "five sufficed" as support for correlated value functions, and the SafeLife paper still calls this a suspicion.

**[Agent judgment]** This is weak, indirect evidence for "a modest task set catches most general-purpose power". The plan's own held-out-family test is the real evidence.

Suggested wording: "In Turner's gridworld AUP experiments, about five uniformly random reward functions were enough to avoid the designed side effects (Conservative Agency §5.1). In SafeLife, one learned auxiliary reward worked and more did worse. This is suggestive at best for task coverage."

### (b) "Turner's theorems say power-seeking actions help most goals" (Part 3)
**Verdict: overstated.**

What the theorems say (1912.01683 Prop. 6.6 and 6.9, Thm. 6.13, Def. 6.5; 2206.13477 Thm. 3.6):
- They hold *given an environmental symmetry*: one action's reachable options contain a copy (or n copies) of the other's.
- Under that condition, the option-preserving action is POWER-seeking, and at least as often optimal, for at least half (or n/(n+1)) of the **state-permuted variants of every reward distribution**.
- The agents covered are optimal agents, or retargetable decision-makers in the 2022 paper.

Caveats the sentence drops:
1. Without the symmetry, there is no such guarantee.
2. "Most" is orbit-counting, which the authors flag as an assumption (footnote 4). It is not a fraction of any realistic goal set.
3. Appendix B (Props. B.1 and B.4) shows that a POWER-seeking action can be *less* often optimal, "a detour".
4. Ties are allowed ("weakly prefer"), so nothing is said about how *much* each goal is helped.

**[Agent judgment]** The step from this to "a modest task set catches most power" does not follow from the theorems.

Suggested wording: "Turner et al. prove that when one action keeps a superset of another's options, most permutations of any goal distribution favour it."

### (c) "The pull toward power appears for goals about the state of the world and disappears for goals about the exact sequence of actions" (Part 4, *Write tasks as checks on the environment's end state*)
**Verdict: accurate in substance, with refinements.**

What the post says (LessWrong, 2021-08-08):
- It has a section titled "Instrumental Convergence Disappears For Utility Functions Over Action-Observation Histories".
- Its ranking is: utility over action-observation histories (u-AOH) "No IC", utility over observation histories (u-OH) "Strong IC", and state-based objectives "Moderate IC".
- Optimal action for u-AOH "will tend to look like random twitching".

Refinements:
1. The result is for *optimal* agents in *deterministic* environments. For the stochastic case Turner writes "I think", without proof.
2. It is about utility over whole action-observation histories, which in a deterministic world is the same as goals over action sequences.
3. Goals about the world state give only "moderate" pull, weaker than goals over whole observation histories.
4. In a 2023-05-16 edit, Turner calls the post "practically irrelevant to alignment" because reward is not the optimisation target.

The formal, peer-reviewed counterpart is 2206.13477:
- Sec. 4.2: optimal policies are retargetable "across future consequences", not across immediate actions.
- Sec. 6.2: retargetability only over actions is "less concerning, but also less practically useful".

**[Agent judgment]** The plan's design conclusion, to score tasks as checks on the end state, is sound. Cite the NeurIPS paper alongside the post, or instead of it.

### (d) Comparison-table rows
**"Turner, POWER" — mostly accurate. Fixes:**
- "What is compared" and "Baseline: the other action" match Def. 5.6.
- "Optimal values (the actual policy in the appendix version)" is accurate. App. C Def. C.1 uses a policy function pol(R, γ), "the best policy which the agent knows about".
- "Average discounted value over goals" is imprecise. It should read: (1−γ)/γ-normalised average optimal value that **excludes the current state's reward**, which is equivalent to (1−γ)-normalised value from the next step on.
- "Random reward functions" should read: any bounded-support distribution over **state-based** reward functions (the example uses uniform IID). The theorems quantify over all state-permutations of it.

**"Turner, AUP (impact, not power)" — mostly accurate. Fixes:**
- "Baseline: doing nothing" is right for the default stepwise-inaction baseline. The paper also tests starting-state and inaction baselines, which fail some environments.
- "Optimal values" should read: learned Q-values standing in for optimal ones (tabular in 2019, networks in 2020), with 9-step no-op rollouts for the planning agents.
- "Summed" should read: summed, then divided by SCALE (the total no-op attainable utility) and multiplied by λ (2019); or averaged over |R| times λ (2020).
- "A few auxiliary goals" should read: 30 uniformly random state rewards by default (2019), or 1 learned CB-VAE feature (2020).

**Also checked: Part 3 "Power versus AUP".**
- The description is accurate: per-goal change against a no-op, absolute value, summed, penalising both gains and losses.
- The paper's stated reason for the absolute value is the Correction environment (shutdown avoidance raises attainable utility).

---

## 6. Implications for an empirical power meter in LinuxArena [Agent judgment]

1. **The plan's score is Turner's sub-optimal POWER, up to a one-step shift.**
   - Take each task g as an indicator reward on goal states the solver can stay in.
   - Then (1−γ)V = γ^{T_g}, and Turner's (1−γ)/γ·(V − R(s)) gives γ^{T_g − 1} for T_g ≥ 1, and 1 if the task is already satisfied.
   - So mean_g E[γ^{T_g}] equals γ × POWER^pol for an LLM pol (App. C), apart from tasks already satisfied at s. "Matches Turner's discounting" is fair.
2. **Watch tasks completed in 0 steps.**
   - Turner subtracts R(s) so that being *in* a goal state is not counted as power.
   - In the meter, an applied effect that directly satisfies a task's check scores γ⁰ = 1. That is "did the task", not "enabled tasks".
   - Flag or exclude these, or report them separately.
3. **A theoretical ceiling for known-answer tests.**
   - Prop. 5.5 (paper 1) and Prop. 1 (paper 4) bound how much value can differ between states that reach each other in k steps: at most 1 − γ^k per task after (1−γ) normalisation, for rewards in [0, 1].
   - With γ ≈ 0.89, an effect the solver could recreate in 3 calls can add at most about 0.30 per task, and only for an optimal solver.
   - This formalises the plan's point that easy-to-get power reads small, and gives a sanity bound for the known-answer changes.
4. **Report two statistics, not one.**
   - The mean gain over tasks is POWER-like. The share of tasks whose outcome improved is like optimality probability.
   - Appendix B shows these can disagree, so report both. The plan's "which tasks changed outcome" already half-does this.
5. **Solver dependence is expected.** App. C shows POWER^pol rises as pol improves, and a bounded agent's power-maximising state can differ from an optimal agent's. The plan's second-solver check is exactly right, and rankings may legitimately flip.
6. **Arya's proposal is Def. 5.6 with a′ = no-op at the start state.**
   - Power(start + effect) − Power(start) compares "apply effect" against "do nothing" at s₀.
   - Travis's step measurement is the signed analogue of AUP's stepwise-inaction comparison at the actual current state, Q(s_t, a) − Q(s_t, ∅). It is valid because the LinuxArena sandbox is static when the agent doesn't act.
   - That is a cleaner lineage for the report than the current table.
7. **Don't lean on "five goals suffice" or "most goals" for coverage.**
   - Both come from dense random state rewards in tiny worlds, or from permutation-closed goal sets. Hand-written LinuxArena task families are neither.
   - The held-out-family test and the dummy and look-alike changes are the right evidence.
   - SafeLife's finding that more auxiliary goals did worse is a reminder that noisy per-goal estimates can swamp signal. That matches the plan's variance analysis.
8. **An impact number comes cheaply, and AUP's normalisation can be borrowed.** Dividing by the plain start state's total attainable value (SCALE) would make gains comparable across environments with different baseline difficulty.
9. **Discount regime.**
   - The symmetry results (Props. 6.6 and 6.9) hold for every γ. The "ends in larger cycle sets" and shutdown results are only at γ = 1, or near it for POWER.
   - At γ ≈ 0.89 the meter measures near-term options. Long-run, resource-type power, which Turner only conjectures for γ ≈ 1, may be under-weighted.
   - The H curve covers this.
10. **Cite carefully.**
    - For the theory, cite the NeurIPS papers. The 2021 LessWrong post now carries Turner's own "practically irrelevant to alignment" disclaimer.
    - For "power should count what the agent can use", App. C (sub-optimal POWER) is a formal anchor inside the paper itself.

## 7. Could not open / not verified
- **2206.11831**, the ID given in the brief, is Turner's PhD thesis (287 pp.), not the retargetability paper. I read 2206.13477 instead. The thesis itself was not read.
- **2206.13477:** the HTML was truncated partway through Appendix A.7, so Appendices B to D (proofs, the detailed MR analysis, Thm. D.11) were not read. The PDF route was not tried for this paper, because the 2206.11831 PDF exceeded the fetch size limit.
- **1912.01683:** the last ~49K characters of the HTML (remaining proof appendices) were not read.
- **Figures:** *Conservative Agency* Fig. 4 and SafeLife Figs. 3 to 5 are plots. Exact per-|R| results were not readable, only axis ticks and the text descriptions.
