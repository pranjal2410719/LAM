# Decision Record: D-03 — Evidence Eligibility & Answer-Verification Provenance Policy

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-19  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M1 & M2 (Evidence Ingestion, Mastery Estimation, and Auditability)  

---

## 1. Context & Problem Statement

In automated cognitive modeling, not all observations have equal evidentiary weight. Conflating provisional, model-graded, assisted, or unverified student responses with authoritative, independent evidence degrades the integrity of knowledge tracing:
1. An unverified or provisional assessment (e.g. ungraded submission or provisional grader) cannot reliably establish student mastery.
2. An AI model-graded evaluation may have hallucinations or scoring noise, and must not silently be treated as a deterministic ground truth.
3. Scaffolded attempts (hints used, worked examples, non-zero assistance level) reflect assisted competence, not independent mastery.
4. Missing correctness signals (non-evaluative events such as reviewing explanations or requesting hints) must not be coerced to incorrect or zero.

---

## 2. Considered Alternatives

* **Alternative A (Permissive Ingestion):** Treat any event carrying `correctness == True` as valid BKT evidence.
  - *Rejected:* Allows untrusted or provisional graders and assisted attempts to falsely inflate student mastery.
* **Alternative B (Strict Deterministic Eligibility — Proposed):** Authoritatively restrict BKT mastery updates to unassisted, verified, non-provisional observations from approved deterministic and teacher sources.
  - *Accepted as Proposed Policy.*

---

## 3. Decision & Proposed Rules (Candidate Policy)

### 3.1 Eligibility Requirements for Independent BKT Updates
An observation is eligible to update independent Bayesian Knowledge Tracing mastery if and only if ALL of the following criteria are satisfied:
1. **Unassisted Attempt:**
   - `assistance_level == 0` (or `None` when explicitly unassisted)
   - `hints_used == 0` (or `None`)
   - `assessment_mode != AssessmentMode.ASSISTED`
   - `provenance.independently_produced == True`
2. **Evaluative Event with Definite Correctness:**
   - `event.correctness is not None` (Boolean `True` or `False`)
   - `event_type` is evaluative (`attempt`, `assessment`, or `review`)
3. **Approved Verification Source:**
   - `provenance` is present
   - `provenance.status == "verified"` (rejects `"provisional"`, `"unverified"`, etc.)
   - `provenance.verifier_reliability != "low"`
   - `provenance.judgment_source` is in the approved trusted sources:
     - `answer_key`
     - `symbolic_math_check`
     - `code_tests`
     - `curriculum_fact_check`
     - `teacher`

### 3.2 Handling Ineligible Events
* **Assisted Events:** Recorded in the durable append-only ledger and update `assisted_performance` and `assisted_attempts_count`. `independent_mastery` and `independent_attempts_count` remain strictly unchanged.
* **Missing Correctness:** Recorded in the ledger and increment `total_events_count`. No mastery update occurs.
* **Provisional or Model-Graded Provenance:** Recorded in the ledger for full auditability, but bypass BKT transitions (`is_eligible_for_bkt = False`). They do not establish independent mastery.

---

## 4. Consequences & Verification
* **Strengths:** Prevents false mastery inflation from noisy graders and scaffolding. Every transition is auditable and mathematically justified.
* **Test Verification:** Covered by unit suite `tests/unit/test_evidence_eligibility.py` and integration suite `tests/integration/test_event_ingestion.py`.
