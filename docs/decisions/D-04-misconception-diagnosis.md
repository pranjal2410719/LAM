# Decision Record: D-04 — Misconception Diagnosis Engine & Hypothesis Lifecycle

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-19  
**Owner:** Technical Owner & Pedagogy Lead  
**Applies to:** Milestone M1 & M2 (Cognitive Modeling, Diagnostic Engine, Remediation Gating)  

---

## 1. Context & Problem Statement

Section 9 of the LAM Implementation Specification outlines the need for a Misconception Diagnosis Engine. In adaptive learning, distinguishing careless slips from deep-seated conceptual misconceptions is essential.
A naive diagnostic policy suffers from severe failure modes:
1. **Premature Diagnostic Disruption:** Treating any single incorrect response as a confirmed misconception sends the student into disruptive remedial loops when they may simply have made a typographical error or slip.
2. **Scaffolding Bias:** An error occurring while a student is receiving heavy hints or viewing worked examples does not provide the same diagnostic signal as an error made during independent problem solving.
3. **Ghost Misconceptions:** Without a formal retirement and refutation mechanism, students remain permanently flagged with historical misconceptions even after demonstrating mastery.
4. **Noisy Evidence Ingestion:** Accepting unverified or provisional model grades creates bogus diagnostic hypotheses.

---

## 2. Considered Alternatives

* **Alternative A (Generative LLM Classification):** Prompt an LLM with student chat and answer text to diagnose misconceptions dynamically.
  - *Rejected:* Non-deterministic, uncalibrated confidence scores, vulnerable to hallucinations, and lacks an immutable mathematical audit trail.
* **Alternative B (Single-Error Static Rule Flags):** Map incorrect distractors directly to misconception tags and immediately trigger remediation.
  - *Rejected:* Treats every slip as a deep misconception, interrupting student flow and inflating false positives.
* **Alternative C (Multi-Stage Bayesian-Inspired Hypothesis Lifecycle — Proposed):** Maintain an explicit hypothesis lifecycle (`OPEN` candidate $\rightarrow$ `CONFIRMED` $\rightarrow$ `REVISED` / `RETIRED`) driven by independent evidence accumulation, contradiction tracking, and strict eligibility gating.
  - *Accepted as Proposed Policy.*

---

## 3. Decision & Proposed Rules (Candidate Policy)

### 3.1 Misconception Taxonomy
Every diagnosed misconception is categorized into one of four domain categories:
* `CONCEPTUAL`: Flawed mental model or foundational misunderstanding (e.g., adding numerators and denominators directly in fractions).
* `PROCEDURAL`: Flawed application of an algorithm or operational step.
* `NOTATION`: Inability to parse or properly represent symbolic syntax.
* `FACTUAL`: Incorrect retrieval of basic facts or definitions.

### 3.2 Hypothesis Lifecycle States
A misconception hypothesis transitions deterministically through the following states:
* `OPEN`: Candidate hypothesis opened upon initial detection. **Never treated as confirmed.**
* `CONFIRMED`: High-confidence misconception supported by repeated independent evidence. Triggers Tier 3 diagnostic probes.
* `REVISED`: Active hypothesis modified or weakened due to contradictory evidence.
* `RETIRED`: Hypothesis refuted or cleared by consecutive independent successes.

```
       [ Initial Error ]
              │
              ▼
           ┌──────┐   Contradiction / Success
           │ OPEN │ ──────────────────────────► [ RETIRED ]
           └──────┘
              │
              │ Repeated Independent Errors
              ▼
         ┌───────────┐   Independent Success
         │ CONFIRMED │ ───────────────────────► ┌─────────┐
         └───────────┘                          │ REVISED │
              │                                 └─────────┘
              │ Consecutive Independent Success      │
              └──────────────────────────────────────┴──► [ RETIRED ]
```

### 3.3 Strict Single-Error Rule
* **Non-Negotiable Policy:** A single incorrect attempt opens an `OPEN` candidate hypothesis with baseline confidence ($0.35$ unassisted, $0.20$ assisted).
* **Zero Disruption Invariant:** An `OPEN` hypothesis **never** triggers Tier 3 (`DIAGNOSTIC_PROBE`) in the recommendation engine. The student continues normal practice uninterrupted.

### 3.4 Confirmation & Refutation Criteria
* **Confirmation Thresholds:**
  - Independent errors count: $S_{\text{indep}} \ge 2$
  - Cumulative confidence: $\ge 0.75$
* **Refutation / Retirement Criteria:**
  - An independent verified success decreases confidence by $-0.35$ and increments the contradiction counter $C$.
  - When cumulative confidence falls $\le 0.15$ or consecutive independent successes reach $C \ge 2$, the hypothesis transitions to `RETIRED`.
* **Scaffolding Discount:**
  - Assisted errors contribute a discounted confidence delta ($+0.15$) and increment $S_{\text{assist}}$, not $S_{\text{indep}}$.
  - Assisted successes do **not** disconfirm an active hypothesis (contradiction counter unchanged).

### 3.5 Evidence Quality & Deduplication Gating
* Diagnostic updates reject unverified, provisional, or low-reliability evidence (`is_eligible_for_diagnosis == False`).
* Non-evaluative events (`correctness is None`) are rejected.
* Replayed or duplicate `event_id`s are detected and ignored, preventing artificial inflation of hypothesis confidence.
* Every hypothesis maintains an immutable, append-only `audit_history` tracking the triggering event ID, previous state, new state, confidence delta, and timestamp.

---

## 4. Consequences & Verification

* **Strengths:** Eliminates false alarms from careless slips, preserves student flow during open hypotheses, ensures deterministic auditability, and integrates safely with the Tier 3 recommendation ladder.
* **Verification:** Covered by pure domain unit tests in `tests/unit/test_misconception_diagnosis.py` and recommendation integration tests in `tests/unit/test_recommendation_engine.py`.
