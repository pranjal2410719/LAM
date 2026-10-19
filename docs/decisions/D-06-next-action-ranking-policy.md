# Decision Record: D-06 — Deterministic Next-Action Ranking Policy

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-19  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M1 & M2 (Adaptive Decision Engine, Recommendation Lifecycle)  

---

## 1. Context & Problem Statement

Section 10 of the LAM Implementation Specification requires an adaptive decision engine to select appropriate next learning actions. A naive recommendation policy (e.g. LLM-based prompting or unstructured heuristics) introduces non-deterministic behavior, unpredictability, and safety risks (e.g. repeatedly failing a frustrated student or advancing past unmet prerequisites).

---

## 2. Considered Alternatives

* **Alternative A (Generative LLM Decision Selection):** Pass learner history to an LLM to decide what to do next.
  - *Rejected:* Violates determinism, introduces latency, hallucinations, and lacks formal safety bounds.
* **Alternative B (Multi-Tier Deterministic Priority Ladder — Proposed):** Apply a strict, deterministic 7-tier decision hierarchy with clear tie-breaking rules and safe fallbacks.
  - *Accepted as Proposed Policy.*

---

## 3. Decision & Proposed Rules (Candidate Policy)

The decision engine evaluates candidate actions across 7 strictly ordered priority tiers:

| Tier | Name | Condition | Action Type | Assistance Level | Rationale |
|---|---|---|---|---|---|
| **Tier 1** | Safety & Stop | `consecutive_failures >= 3` | `teacher_intervention` | Level 8 | Prevent student frustration and cognitive overload; require human tutor escalation. |
| **Tier 2** | Blocking Prerequisite | `prerequisite_readiness is False` | `prerequisite_remediation` | Level 5 | Remediate missing prerequisite foundation before attempting target concept. |
| **Tier 3** | Confirmed Misconceptions | Confirmed active misconception (`status == "confirmed"`) | `diagnostic_probe` | Level 2 | Disconfirm or isolate specific misconception hypothesis. Open candidate hypotheses do NOT trigger Tier 3. |
| **Tier 4** | Overdue Retrieval | `retention_strength < 0.50` | `delayed_retrieval_review` | Level 0 | Spaced retrieval to reinforce fragile long-term memory. |
| **Tier 5** | Mastery Verification | `mastery >= 0.85` and (`U > 0.15` or `consec_successes < 3`) | `mastery_verification` | Level 0 | Require independent unassisted evidence to confirm mastery. |
| **Tier 6** | Curriculum Progression | `mastery >= 0.85` and `U <= 0.15` and `consec_successes >= 3` | `advance_to_next_concept` | Level 0 | Progress to subsequent learning objective in curriculum graph. |
| **Tier 7** | Difficulty Fit & Practice | Low mastery ($< 0.40$)<br>Scaffolded transition<br>Standard practice | `worked_example` (L5)<br>`scaffolded_practice` (L3)<br>`independent_practice` (L0) | Level 5<br>Level 3<br>Level 0 | Match instructional scaffolding to student's current zone of proximal development. |
| **Fallback** | Insufficient Evidence | Missing state record | `diagnostic_probe` | Level 2 | Safe baseline probe to establish initial evidence. |

### 3.1 Tie-Breaking Invariants
* Higher priority tiers strictly preempt lower tiers (e.g. Tier 1 safety stop preempts Tier 2 prerequisite gaps).
* Candidate misconception hypotheses in `OPEN` or `RETIRED` state do not trigger Tier 3; student proceeds to standard practice.
* Identical inputs deterministically generate identical recommendations, reason codes, and strategy descriptors.

---

## 4. Consequences & Verification
* **Strengths:** Fully deterministic, verifiable with fast unit tests, strictly respects safety constraints and prerequisites.
* **Test Verification:** Covered by `tests/unit/test_recommendation_engine.py` and `tests/integration/test_recommendation_api.py`.
