# Decision Record: D-01 — Mastery Policy & Confirmation Criteria

**Status:** `PROPOSED` (Awaiting Formal Technical Review & Sign-Off)  
**Date:** 2026-10-18  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M1 & M2 (Mastery Estimation, Verification, and Next-Action Sequencing)  

---

## 1. Context & Problem Statement

In automated learning systems, conflating temporary task success with durable, independent understanding leads to premature progression and fragile learning. 
Specific challenges:
1. A correct response obtained after receiving a hint or worked example demonstrates *scaffolded competence*, not independent mastery.
2. A single correct response in the same session can be temporary working memory recall rather than durable retention.
3. Model-graded or self-reported evaluations lack the evidentiary rigor of deterministic verification (e.g. symbolic math verification or code execution tests).

---

## 2. Considered Alternatives

* **Alternative A (Single-Score Moving Average):** Increment or decrement a single concept score upon each attempt.
  - *Rejected:* Destroys provenance, conflates assisted success with independent mastery, and hides uncertainty.
* **Alternative B (Threshold-Only Mastery):** Declare mastery whenever estimated $P(L) \ge 0.85$.
  - *Rejected:* High estimate can be artificially reached through lucky guesses or in-session clustering without retention over time.
* **Alternative C (Multi-Gate Independent Mastery Policy — Proposed):** Require independent evidence count, session separation, verifier provenance, and delayed retention verification before declaring durable mastery.

---

## 3. Decision & Proposed Rules (Candidate Policy)

### 3.1 Separate Dimensions
Learner state tracks independent performance separately from assisted performance:
* **`independent_mastery`**: Computed strictly from unassisted attempts (`assistance_level == 0`, `hints_used == 0`) and verified independent assessments.
* **`assisted_performance`**: Success rate with scaffolding (Levels 1 to 8). An assisted success never advances `independent_mastery`.

### 3.2 Durable Mastery Confirmation Criteria
A concept is transitioned to `CONFIRMED_MASTERY` status if and only if all of the following conditions are met:
1. **Model Estimate:** Calculated independent mastery point estimate $P(L_t) \ge 0.90$.
2. **Uncertainty Bound:** Explicit uncertainty criterion satisfied (see Section 3.3).
3. **Independent Evidence Count:** At least $3$ independent, verified successes.
4. **Session Separation:** Evidence spans at least $2$ distinct sessions separated by $\ge 4$ hours.
5. **Item Difficulty:** At least one independent success on an item with difficulty $\ge 0.60$.
6. **No Active Misconceptions:** Zero confirmed misconception hypotheses on the concept.
7. **Delayed Retention Check:** A scheduled spaced review (at least 1 day after learning) is passed unassisted.

### 3.3 Mathematical Clarification: Uncertainty vs. Point-Estimate BKT
> [!IMPORTANT]
> **Statistical Distinction:** Standard Bayesian Knowledge Tracing (BKT) produces a scalar point estimate $P(L_t = 1 \mid \text{Obs}_{1:t})$ representing the probability that the latent Bernoulli mastery state is 1. Standard BKT does **not** natively produce a posterior parameter distribution or a continuous Bayesian credible interval.

For Milestone M1 implementation, uncertainty must be clearly defined rather than represented as an uncalibrated credible interval. The candidate options under review are:

1. **Option 1 (Bernoulli Standard Error):**
   Treat $L_t \sim \text{Bernoulli}(p)$ where $p = P(L_t=1)$. The estimation variance is $\sigma^2 = p(1-p)$. When $p \ge 0.90$, $\sigma = \sqrt{0.90 \times 0.10} = 0.30$. Requiring $\sigma \le 0.15$ mathematically requires $p \ge 0.976$ (or $p \le 0.024$).
2. **Option 2 (Observation-Count Epistemic Uncertainty — Recommended for M1):**
   Decouple the point probability from parameter variance. Define operational uncertainty as an evidence decay function over unassisted observations:
   $$U(n) = \frac{1}{\sqrt{n_{\text{indep}} + 1}}$$
   Where $n_{\text{indep}}$ is the count of unassisted observations. Here, $U \le 0.15$ requires $n_{\text{indep}} \ge 43$ items, or using an exponential decay schedule $U(n) = \max(0.10, e^{-0.5 \cdot n_{\text{indep}}})$.
3. **Option 3 (Full Beta-BKT Parameter Posterior — Deferred to M3):**
   Maintain a full Beta distribution over BKT parameters to generate statistically valid parameter credible intervals.

**Operational Rule for M1:** The `uncertainty` field in `learner_states` is an operational epistemic confidence heuristic, **not** an empirical Bayesian parameter credible interval. The confirmation threshold in Rule 3.2(2) shall be evaluated as $U \le 0.15$ under the approved operational decay function.

---

## 4. Consequences & Migration Impact

* **Positive:** Prevents students from being pushed into advanced topics prematurely; eliminates "hint-dependency illusion."
* **Operational:** Requires host application (Qrie) to deliver independent verification items when LAM flags `verification_due`.
* **Testing:** Fixed deterministic test vectors verify that assisted successes increment `assisted_performance` while `independent_mastery` remains unchanged.
