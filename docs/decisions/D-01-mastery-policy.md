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
1. **Model Estimate:** Calculated independent mastery probability $\ge 0.90$.
2. **Uncertainty Bound:** Credible interval width $\le 0.15$.
3. **Independent Evidence Count:** At least $3$ independent, verified successes.
4. **Session Separation:** Evidence spans at least $2$ distinct sessions separated by $\ge 4$ hours.
5. **Item Difficulty:** At least one independent success on an item with difficulty $\ge 0.60$.
6. **No Active Misconceptions:** Zero confirmed misconception hypotheses on the concept.
7. **Delayed Retention Check:** A scheduled spaced review (at least 1 day after learning) is passed unassisted.

---

## 4. Consequences & Migration Impact

* **Positive:** Prevents students from being pushed into advanced topics prematurely; eliminates "hint-dependency illusion."
* **Operational:** Requires host application (Qrie) to deliver independent verification items when LAM flags `verification_due`.
* **Testing:** Fixed deterministic test vectors will verify that assisted successes increment `assisted_performance` while `independent_mastery` remains unchanged.
