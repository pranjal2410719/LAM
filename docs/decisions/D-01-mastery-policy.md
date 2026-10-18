# Decision Record: D-01 — Mastery Policy & Confirmation Criteria

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
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
* **`independent_mastery`**: Computed strictly from unassisted attempts (`assistance_level == 0`, `hints_used == 0`) and verified independent assessments via the BKT domain engine.
* **`assisted_performance`**: Success rate with scaffolding (Levels 1 to 8). An assisted success never advances `independent_mastery`.

### 3.2 Durable Mastery Confirmation Criteria
A concept is transitioned to `CONFIRMED_MASTERY` status if and only if all of the following conditions are met:
1. **Model Estimate:** Calculated independent mastery point estimate $P(L_t) \ge 0.90$.
2. **Operational Uncertainty Bound:** Operative evidence sufficiency heuristic $U(n_{\text{indep}}) \le 0.15$ (requiring $n_{\text{indep}} \ge 44$, see Section 3.3).
3. **Independent Evidence Count:** At least $3$ independent, verified successes.
4. **Session Separation:** Evidence spans at least $2$ distinct sessions separated by $\ge 4$ hours.
5. **Item Difficulty:** At least one independent success on an item with difficulty $\ge 0.60$.
6. **No Active Misconceptions:** Zero confirmed misconception hypotheses on the concept.
7. **Delayed Retention Check:** A scheduled spaced review (at least 1 day after learning) is passed unassisted.

### 3.3 Operative Uncertainty Metric for Milestone M1
> [!IMPORTANT]
> **Statistical Distinction:** Standard Bayesian Knowledge Tracing (BKT) produces a scalar point estimate $P(L_t = 1 \mid \text{Obs}_{1:t})$ representing the probability that the latent Bernoulli mastery state is 1. Standard BKT does **not** natively produce a posterior parameter distribution or a continuous Bayesian credible interval.

For Milestone M1, the single operative formula for uncertainty is defined as an evidence-sufficiency heuristic:

$$U(n_{\text{indep}}) = \min\left(1.0, \frac{1}{\sqrt{n_{\text{indep}} + 1}}\right)$$

Where $n_{\text{indep}}$ is the total count of unassisted observations for the concept.

#### Threshold Derivation:
To satisfy the confirmation threshold $U(n_{\text{indep}}) \le 0.15$:
$$\frac{1}{\sqrt{n_{\text{indep}} + 1}} \le 0.15 \iff n_{\text{indep}} + 1 \ge \frac{1}{0.15^2} = \frac{1}{0.0225} \approx 44.44$$

Because $n_{\text{indep}}$ is an integer count of observations:
- At $n_{\text{indep}} = 43$: $U(43) = \frac{1}{\sqrt{44}} \approx 0.15076 > 0.15$ (FAILS).
- At $n_{\text{indep}} = 44$: $U(44) = \frac{1}{\sqrt{45}} \approx 0.14907 \le 0.15$ (PASSES).

Therefore, exactly **44 independent observations** are required to satisfy the $0.15$ uncertainty bound.

**Important Note on Terminology:** This metric is strictly an operational evidence-sufficiency heuristic. It must not be presented to educators or downstream systems as an empirically calibrated Bayesian credible interval. True parameter posterior credible intervals are deferred to Milestone M3 (Beta-BKT).

---

## 4. Consequences & Migration Impact

* **Positive:** Prevents students from being pushed into advanced topics prematurely; eliminates "hint-dependency illusion."
* **Operational:** Requires host application (Qrie) to deliver independent verification items when LAM flags `verification_due`.
* **Testing:** Fixed deterministic test vectors verify that assisted successes increment `assisted_performance` while `independent_mastery` remains unchanged.
