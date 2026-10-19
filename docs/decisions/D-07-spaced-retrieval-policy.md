# Decision Record: D-07 — Spaced Retrieval & Forgetting Curve Review Scheduling

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-19  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M2 (Spaced Retrieval Scheduler, Long-Term Retention Review)  

---

## 1. Context & Problem Statement

Section 6 of the LAM Implementation Specification requires spaced retrieval review scheduling to consolidate long-term memory. Without scheduled retrieval, student mastery decays over time according to Ebbinghaus forgetting curves.
However:
1. An uncalibrated scheduler risks overwhelming students with excessive reviews, starving them of new curriculum progress.
2. Conversely, omitting reviews causes fragile knowledge to fade unnoticed until subsequent curriculum units fail.
3. Crucially, the mathematical parameters of student forgetting curves cannot be claimed as empirically calibrated prior to fitting against actual student cohorts.

---

## 2. Considered Alternatives

* **Alternative A (Fixed Periodic Review):** Review every concept every 7 days.
  - *Rejected:* Ignores demonstrated memory strength; over-tests stable concepts while neglecting fragile ones.
* **Alternative B (Candidate Baseline Expanding-Interval Ladder with Exponential Decay — Proposed):** Apply a classical expanding interval ladder ($1\text{d} \rightarrow 3\text{d} \rightarrow 7\text{d} \rightarrow 14\text{d} \rightarrow 30\text{d} \rightarrow 60\text{d}$) combined with an exponential retention decay model $R(t) = \exp(-\Delta t / S)$.
  - *Accepted as Candidate Baseline Policy.*

---

## 3. Decision & Proposed Rules (Candidate Policy)

### 3.1 Interval Progression
* **Unassisted Successes ($k$ consecutive):**
  $$I(k) = [1.0, 3.0, 7.0, 14.0, 30.0, 60.0][\min(k, 5)] \text{ days}$$
* **Failure ($C = \text{False}$):** Resets scheduled interval to $1.0$ day.
* **Assisted Success ($C = \text{True}, L > 0$):** Advance is discounted ($0.70\times$ base interval) to prevent overestimating independent memory stability.

### 3.2 Retention Decay & Urgency Tiers
* Memory stability $S = I \times 6.159$ (calibrated so that at $\Delta t = I$, estimated retention $R(t) = 0.85$).
* **Urgency Classification:**
  - `CRITICAL_OVERDUE`: $R(t) < 0.50$ or $\Delta t \ge 2 \times I$. Review is urgently due.
  - `DUE_FOR_REVIEW`: $\Delta t \ge I$ or $R(t) < 0.80$. Review window is open.
  - `UPCOMING`: Scheduled within next 48 hours.
  - `STABLE`: $R(t) \ge 0.80$, review distant.

### 3.3 Limitations & Calibration Requirements
> [!IMPORTANT]
> This schedule is a **candidate baseline policy** derived from educational psychology literature. It is **not empirically calibrated** on Qrie student population data. Empirical curve fitting is scheduled for Milestone M3.

---

## 4. Consequences & Verification
* **Strengths:** Fully deterministic, safe fallback on missing timestamps, strict tenant isolation, priority-ordered review lists.
* **Verification:** Covered by unit tests in `tests/unit/test_spaced_retrieval.py` and integration tests in `tests/integration/test_reviews_api.py`.
