# Decision Record: D-05 — 9-Level Productive-Struggle Assistance Escalation Policy

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-19  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M2 (Scaffolding Engine, Productive Struggle & Tutoring Integration)  

---

## 1. Context & Problem Statement

Section 7 of the LAM Implementation Specification outlines a 9-level instructional assistance ladder (Levels 0 through 8). In adaptive learning, uncalibrated scaffolding introduces two symmetrical hazards:
1. **Under-Scaffolding (Learner Frustration):** Repeated failures without timely instructional intervention lead to cognitive overload, disengagement, and unproductive struggle.
2. **Over-Scaffolding (Learner Dependence):** Excessive hints or early answers erode student retrieval effort and artificially inflate short-term performance while impairing durable learning.

---

## 2. Considered Alternatives

* **Alternative A (Static Fixed Hint Escalation):** Step up by +1 hint after every error, regardless of student performance history.
  - *Rejected:* Too slow to halt severe frustration; does not provide timely worked examples or safety stops.
* **Alternative B (Generative LLM Scaffolding):** Let an LLM tutor decide how much help to provide on every response.
  - *Rejected:* Non-deterministic, uncalibrated assistance levels, lacks auditable safety stop bounds.
* **Alternative C (Deterministic 9-Level Escalation & Fading State Machine — Proposed):** Maintain an explicit state machine tracking consecutive failures, assisted successes, and unassisted performance with deterministic escalation, fading, and safety-stop thresholds.
  - *Accepted as Proposed Policy.*

---

## 3. Decision & Proposed Rules (Candidate Policy)

### 3.1 9-Level Scaffolding Hierarchy
* **Level 0 (Independent):** Unassisted problem solving. No hints or scaffolding displayed.
* **Level 1 (Metacognitive Prompt):** Prompts student to pause, re-read question, check calculation steps, or review definitions.
* **Level 2 (Strategy Hint / Diagnostic Probe):** High-level strategic clue or conceptual probe to isolate misconception.
* **Level 3 (Scaffolded Sub-Step):** Decomposes complex problem into structured sub-steps.
* **Level 4 (Conceptual Breakdown):** Explicit review of required formulas, theorems, or grammatical rules.
* **Level 5 (Worked Example):** Step-by-step parallel solved problem demonstrating procedural execution.
* **Level 6 (Guided Walkthrough):** Interactive guided step-by-step problem execution with immediate validation per step.
* **Level 7 (Direct Instruction):** Direct conceptual exposition and remedial teaching.
* **Level 8 (Teacher Intervention):** Automated tutoring halts; student is prompted to raise hand or consult educator.

### 3.2 Escalation Rules (Struggle Response)
1. **Single Error:** Escalates assistance by +1 or +2 levels depending on baseline (e.g. Level 0 $\rightarrow$ Level 2).
2. **Two Consecutive Errors:** Escalates directly to Level 5 (Worked Example) to model the correct strategy.
3. **Three or More Consecutive Errors:** Escalates immediately to Level 8 (Teacher Intervention / Safety Stop). Automated difficulty escalation halts.

### 3.3 Fading & Reset Rules (Competence Demonstration)
1. **Independent Success (Level 0):** Resets consecutive failures to 0 and resets assistance level immediately to Level 0 (independent fluency).
2. **Assisted Success (Level > 0):**
   - Single assisted success: Maintained at current level to consolidate competence.
   - Two consecutive assisted successes: Fades assistance downward (Level 5 $\rightarrow$ Level 3 $\rightarrow$ Level 2 $\rightarrow$ Level 0) to promote independent transfer.

### 3.4 Invariants
* Non-evaluative events (`correctness is None`) strictly maintain current state without escalation or de-escalation.
* Every state transition creates an append-only [`AssistanceAuditEntry`](file:///home/dev/Desktop/projects/ai-tuitor/lam/src/lam/domain/assistance/models.py).

---

## 4. Consequences & Verification
* **Strengths:** Fully deterministic, verifiable with automated tests, prevents student frustration, enforces teacher escalation on persistent struggle, and fosters gradual fading of scaffolding.
* **Verification:** Covered by unit test suite `tests/unit/test_assistance_escalation.py`.
