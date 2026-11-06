# What makes discounted POWER larger

*Written 2026-11-05 at about 04:50 CST by the main session. The algebra is mine, and I checked it numerically on the Nov 3 curves. Numbers: `analysis/data/curves.json`, `no_rollback_rows` (every-5-turn scoring), `last-scored` rule. Arya asked whether the discounted measure is simply larger when an arm starts higher.*

## The answer

**Almost: it's larger when test cases pass earlier. A test case that first passes at step t is worth γ^(t−1); one that never passes is worth 0.** Discounted POWER is the average of that over all counted test cases. The level at the very start only matters through this, and it adds little unless test cases pass at step 0.

So the discount factor γ picks a window. It says how much a step is worth, not how high a curve goes:
- **γ close to 1** asks "did it pass at all?", which is the end share.
- **Smaller γ** asks "how soon?". With γ = 0.95, half the weight falls in the first 13.5 steps.

## The identity

The code's definition (`harness/power_horizons.py`, "geometric") for a curve F_H, H = 0..80:

$$D_\gamma = \sum_{H=1}^{80} (1-\gamma)\,\gamma^{H-1} F_H + \gamma^{80} F_{80}$$

The weights from step H onward add up to exactly γ^(H−1). Summing by parts gives:

$$D_\gamma = F_0 + \sum_{H=1}^{80} \gamma^{H-1}\,(F_H - F_{H-1})$$

**Read it as:** each share of test cases gained at step H earns γ^(H−1), and each share lost at step H gives back γ^(H−1). When curves only rise, this is the mean of γ^(t−1) over test cases, with t the step of first passing and 0 for those that never pass. Under the `last-scored` rule a test case that breaks gives its value back at the step it breaks. On all 5 arms the two forms agree to about 1e-16 at every γ tried.

**It's also a random budget.** D_γ is the expected F_H when the budget H is drawn from a geometric distribution with mean about 1/(1−γ), cut off at 80.

**The undiscounted mean is steps saved.** For rising curves, the mean over H = 1..80 of the difference between two arms is the mean steps saved per test case, divided by 80 (a test case that never passes counts as passing at step 81). So 80 × ΔPOWER reads directly in steps per test case.

**The link to Turner (my reading):** for a goal paid once on arrival, an optimal agent's discounted value is about γ^d, with d its distance to the goal. So POWER is roughly the average of γ^(distance) over goals: how close you are to everything. We measure the same form, but the "distance" is how long our fixed solver takes, not the shortest possible path. So the solver's habits are part of what we measure. This is one reason the measure can miss access the solver doesn't happen to use.

## What the Nov 3 curves say

| γ | Half the weight within | Mean budget | Before | A1 | B1 | A2 | B2 | B1 − A1 | B2 − A2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.80 | 3.1 steps | 5.0 | 0.037 | 0.168 | 0.138 | 0.075 | 0.077 | −0.030 | +0.002 |
| 0.90 | 6.6 | 10.0 | 0.142 | 0.360 | 0.320 | 0.231 | 0.227 | −0.039 | −0.004 |
| 0.95 | 13.5 | 19.7 | 0.330 | 0.550 | 0.513 | 0.432 | 0.426 | −0.038 | −0.005 |
| 0.98 | 34.3 | 40.1 | 0.578 | 0.724 | 0.694 | 0.645 | 0.647 | −0.030 | +0.002 |
| 0.99 | 69.0 | 55.2 | 0.703 | 0.796 | 0.771 | 0.742 | 0.748 | −0.026 | +0.007 |
| 1.00 | end share | 80 | 0.858 | 0.878 | 0.858 | 0.855 | 0.869 | −0.020 | +0.014 |

**In steps, using 80 × the mean over H = 1..80:**

| | Steps saved per test case over the initial state |
| --- | --- |
| A1 | +10.3 |
| B1 | +8.0 |
| A2 | +4.8 |
| B2 | +5.0 |

B1 − A1 is −2.24 steps per test case, and B2 − A2 is +0.27. **The arms' shared gain is much bigger than the gap between them.**

**Where the gap comes from, in steps per test case:**

| Budget range | B1 − A1 | B2 − A2 |
| --- | --- | --- |
| H = 1–5 | −0.09 | +0.02 |
| H = 6–10 | −0.34 | +0.13 |
| H = 11–15 | −0.33 | −0.31 |
| H = 16–20 | −0.33 | −0.22 |
| H = 21–30 | −0.14 | −0.08 |
| H = 31–50 | −0.40 | +0.31 |
| H = 51–80 | −0.60 | +0.42 |

**Saturation shows clearly, which supports Arya's first point:**
- All five arms level off between H = 25 and 40, at shares of 0.855–0.878.
- The initial state catches up at about H = 30–40.
- So every arm's advantage over the initial state lives in the first 30 or so steps.

**But "only at low H" isn't quite the whole gap:**
- About half of pair 1's −2.24 (−1.09 steps) comes from H ≤ 20, where B1 lags.
- About −1.0 comes from H > 30, where B1 has simply levelled off lower than A1 (0.858 against 0.878). A difference in where an arm saturates counts for 50 steps, so a small end-share difference adds up. That difference is about half a task's worth of test cases out of 27, which may well be one run's luck.
- In pair 2 the tail runs the other way, and cancels the low-H lag.

**The size of a low-H gap depends on the slope.** Curves climb about 0.04–0.06 per step around H = 10. So a lag of 1.5 to 2 steps reads as the 0.086 gap between A1 and B1 at H = 10. A large-looking gap at one H can be a short lag.

## What this means for reporting (my judgment)

- **Report the lag in steps next to POWER_H.** It's easier to compare with noise and with the cost of a turn.
- **Report end share and speed separately** (Taylor and Stone's advice for budget curves, in [nov5-literature.md](nov5-literature.md)). The summed measure mixes "how far it levels off" with "how soon", and a small end-share difference dominates it because it counts over many steps. Discounting with γ around 0.9–0.95 mostly measures speed.
- **Choosing γ should be fixed in advance.** Pair 2's sign changes between γ = 0.95 (−0.005) and 0.98 (+0.002). Both are tiny, which is itself the finding.
- **Every-5-turn scoring is coarse for this.** At γ = 0.9, half the weight lies within the first 6.6 steps, about one grid interval. Every-turn scoring matters most for the discounted measure.
