# Qrie – LAM Integration Contract (M2 Readiness Specification)

**Status:** `DRAFT FOR ENGINEERING REVIEW`  
**Date:** 2026-10-19  
**Version:** 1.0.0  
**Target Milestone:** M2 (Full Qrie End-to-End Learning Loop)  

---

## 1. System Boundaries & Division of Responsibilities

| Responsibility Area | Qrie (Product Platform) | LAM (Learning Intelligence Backend) |
|---|---|---|
| **Student UI & Interactions** | Owns lessons, chat interface, problem rendering, UI state, sound, animations. | Zero UI knowledge; headless HTTP JSON API. |
| **User Authentication & Profiles** | Authenticates students & teachers, manages accounts, issues scoped JWTs. | Enforces tenant isolation and validates JWT signatures; no student credential storage. |
| **Curriculum & Question Bank** | Authors and hosts questions, distractors, explanations, hints, and worked examples. | Consumes canonical concept identifiers; does not store question prose or multimedia. |
| **Answer Verification & Grading** | Grades student submissions via deterministic answer keys, symbolic checkers, or rubrics. | Ingests verified provenance events; refuses to treat unverified data as independent mastery. |
| **Cognitive Modeling** | Relies on LAM for state updates. | Owns append-only ledger, Bayesian Knowledge Tracing ($P(L)$), and uncertainty tracking. |
| **Misconception Diagnosis** | Maps incorrect answer distractors to misconception IDs; transmits to LAM. | Tracks competing hypotheses (`OPEN` $\rightarrow$ `CONFIRMED` $\rightarrow$ `RETIRED`) and confidence scores. |
| **Next-Action Selection** | Renders instructional activity corresponding to LAM recommendation. | Executes 7-tier deterministic recommendation ladder and outputs action codes + assistance levels. |

---

## 2. Canonical Identifiers & Curriculum DAG Contract

### 2.1 Concept Identifiers
* **Format:** Dot-separated hierarchical namespace string: `<subject>.<domain>.<topic>[.<subtopic>]`
* **Examples:**
  - `math.algebra.linear_equations`
  - `math.fractions.addition_unlike_denominators`
  - `science.physics.newton_second_law`
* **Constraints:** Minimum length 3 characters, maximum length 128 characters. Allowed characters: lowercase alphanumeric `[a-z0-9]`, dots `.`, and underscores `_`.

### 2.2 Prerequisite DAG Representation
* Qrie maintains the authoritative curriculum Directed Acyclic Graph (DAG).
* When requesting recommendations or reporting prerequisite gaps, Qrie passes the verified readiness boolean (`prerequisite_readiness: true | false`) and the immediate unfulfilled prerequisite concept ID (`prerequisite_concept_id`).
* In Milestone M2, LAM will expose optional DAG validation endpoints to guarantee acyclicity and topological prerequisite checks.

---

## 3. Evidence Ingestion Contract (`POST /v1/events`)

Every interaction that produces learning evidence must be transmitted to LAM synchronously or via reliable queue.

### 3.1 Request Payload Schema
```json
{
  "event_id": "evt_01J9...",
  "student_id": "stu_grade8_042",
  "session_id": "sess_20261019_1001",
  "concept_ids": ["math.fractions.addition_unlike_denominators"],
  "item_id": "item_frac_add_089",
  "timestamp": "2026-10-19T14:30:00Z",
  "event_type": "attempt",
  "correctness": false,
  "assistance_level": 0,
  "hints_used": 0,
  "duration_ms": 14200,
  "assessment_mode": "independent",
  "provenance": {
    "judgment_source": "answer_key",
    "status": "verified",
    "verifier_reliability": "authoritative",
    "independently_produced": true
  },
  "misconception_candidate": {
    "misconception_id": "misc_add_denominators_directly",
    "category": "conceptual"
  }
}
```

### 3.2 Ingestion Invariants
1. **Idempotency:** `event_id` is unique across the entire tenant. Repeated calls with the same `event_id` return `200 OK` with the existing record and perform **no duplicate state or hypothesis mutations**.
2. **Missing Signals:** If an event has no correctness evaluation (e.g. video watch, hint request), Qrie must send `correctness: null`. LAM will log the event and update event counts without penalizing student mastery.
3. **Assisted Attempts:** Any attempt with `hints_used > 0`, `assistance_level > 0`, or `assessment_mode: "assisted"` is logged and updates assisted metrics, but **strictly bypasses independent BKT mastery updates**.

---

## 4. Recommendation Contract (`POST /v1/recommendations`)

When a student finishes an item or requests their next activity, Qrie queries LAM's recommendation engine.

### 4.1 Request Payload
```json
{
  "student_id": "stu_grade8_042",
  "concept_id": "math.fractions.addition_unlike_denominators",
  "consecutive_failures": 0,
  "active_misconception_id": "misc_add_denominators_directly",
  "misconception_status": "open",
  "prerequisite_readiness": true,
  "context_metadata": {
    "grade_level": 8,
    "current_unit": "rational_numbers"
  }
}
```

### 4.2 Response Payload
```json
{
  "recommendation_id": "rec_3a9f12b84e01",
  "action_type": "independent_practice",
  "target_concept_id": "math.fractions.addition_unlike_denominators",
  "assistance_level": 0,
  "priority_tier": "tier_7_difficulty_fit_practice",
  "reason_code": "standard_independent_practice",
  "suggested_strategy": "Present standard problem without scaffolding to build fluency.",
  "rationale": "Learner has intermediate mastery (0.55). Independent practice recommended.",
  "policy_version": "d06_ladder_v1",
  "safe_fallback": false,
  "uncertainty": 0.45,
  "relevant_learner_state_version": 4,
  "metadata": {}
}
```

### 4.3 Action Code Definitions & Qrie Execution Mapping

| Action Code (`action_type`) | Assistance Level | Priority Tier | Qrie Execution Action |
|---|---|---|---|
| `teacher_intervention` | 8 | Tier 1 (Safety) | Pause automated tutoring. Prompt student to consult teacher or raise hand. Notify school dashboard. |
| `prerequisite_remediation` | 5 | Tier 2 (Prereq Gap) | Route student to `target_concept_id` (the prerequisite). Present worked example and foundational review. |
| `diagnostic_probe` | 2 | Tier 3 (Confirmed Misc) | Present a targeted conceptual diagnostic question designed to isolate or refute the confirmed misconception. |
| `delayed_retrieval_review` | 0 | Tier 4 (Retention) | Present a spaced retrieval challenge from an earlier mastered topic before continuing new material. |
| `mastery_verification` | 0 | Tier 5 (Verification) | Present an unassisted, high-validity problem to reduce epistemic uncertainty and verify durable mastery. |
| `advance_to_next_concept` | 0 | Tier 6 (Progression) | Celebrate concept mastery. Advance curriculum path to next concept in sequence. |
| `worked_example` | 5 | Tier 7 (Scaffolding) | Present step-by-step worked problem with explanation before asking student to attempt a problem. |
| `scaffolded_practice` | 3 | Tier 7 (Scaffolding) | Present problem with sub-steps, hints, and active scaffolding enabled. |
| `independent_practice` | 0 | Tier 7 (Standard) | Present standard problem with hints collapsed/unprompted to encourage independent retrieval. |

---

## 5. Spaced Retrieval Review Schedule Contract (`GET /v1/learners/{learner_id}/reviews`)

Qrie queries this endpoint periodically (e.g. at session start or daily study plan load) to determine which previously practiced concepts require spaced review.

### 5.1 Request Parameters
* Path: `/v1/learners/{learner_id}/reviews`
* Query Parameters (optional):
  - `priority`: filter by priority (`overdue`, `due_soon`, `maintained`)
  - `limit`: integer max items (default 50)

### 5.2 Response Payload Schema
```json
{
  "student_id": "stu_grade8_042",
  "evaluated_at": "2026-10-19T14:30:00Z",
  "policy_version": "retrieval_v1_expanding",
  "total_concepts_evaluated": 12,
  "reviews_due_count": 2,
  "reviews_due": [
    {
      "concept_id": "math.fractions.addition_unlike_denominators",
      "concept_mastery": 0.88,
      "last_reviewed_at": "2026-10-12T10:00:00Z",
      "scheduled_for": "2026-10-19T10:00:00Z",
      "interval_days": 7.0,
      "retention_estimate": 0.58,
      "is_due": true,
      "priority": "overdue",
      "reason_code": "retention_decay_below_threshold",
      "consecutive_successes": 3,
      "half_life_days": 8.5
    }
  ],
  "upcoming_reviews": []
}
```

---

## 6. Curriculum Graph DAG Validation Contract (`POST /v1/curriculum/...`)

### 6.1 Validate Graph (`POST /v1/curriculum/validate`)
Allows Qrie to upload a syllabus unit graph to verify acyclicity and obtain the canonical topological sort order.

* **Response:**
```json
{
  "valid": true,
  "is_dag": true,
  "topological_order": ["math.concept.a", "math.concept.b", "math.concept.c"],
  "total_nodes": 3,
  "total_edges": 2,
  "message": "Curriculum graph is a valid Directed Acyclic Graph (DAG)."
}
```
* **Cycle Rejection:** If a cycle exists, returns `422 Unprocessable Content` with the cycle path in `detail`.

### 6.2 Check Prerequisites (`POST /v1/curriculum/check-prerequisites`)
Evaluates student readiness for a target concept given their concept mastery map.

---

## 7. Tenant Isolation & Security Requirements

1. **Authentication:** All requests must include an `Authorization: Bearer <JWT>` header signed with the shared HMAC-SHA256 secret.
2. **Tenant Claim:** JWT must contain a valid `tenant_id` claim matching the `X-Tenant-ID` header.
3. **Cross-Tenant Access:** Any attempt to request or manipulate data belonging to a different tenant returns `403 Forbidden`.
4. **Student Privacy:** No student PII (real names, emails, phone numbers) is ever transmitted to LAM. All student references must be opaque, pseudonymized tokens (e.g. `stu_e89a...`).

---

## 8. Client Failure Modes, Retries & Fallback Behavior

1. **Timeouts:** Qrie client should use a 2.0s connect timeout and 5.0s read timeout.
2. **Retries:** Retry up to 3 times on 502/503/504 errors using exponential backoff with jitter.
3. **Graceful Fallback:** When LAM is unavailable, Qrie must NEVER fabricate a mastery estimate or simulate BKT probability transitions. Qrie queues the event in the device/server outbox and falls back to standard practice mode using the last known recommendation or safe diagnostic probe.

