# LAM Implementation Specification

**Project:** Learning Adaptation Model (LAM)  
**Document type:** Formal Implementation Specification  
**Version:** 1.0 — Draft for Engineering Review  
**Status:** Proposed; approval required before implementation of complex learning logic  
**Applies to:** Standalone LAM repository and its integrations with Qrie and other learning applications  
**Primary references:**
- `LAM – Complete Product and Engineering Requirements`
- `LAM Engineering Handbook`
- `LAM Engineering Standards & Development Lifecycle`
- `LAM: Learning Adaptation Model – Product Requirements Document` (both existing versions)

---

## 1. Purpose

This document translates LAM's existing product requirements and engineering standards into a concrete implementation contract.

It defines the system boundaries, module responsibilities, domain entities, data contracts, processing lifecycle, algorithm interfaces, failure behavior, testing requirements, and release gates required to build LAM incrementally.

The purpose is to ensure that multiple engineers can implement different parts of LAM without inventing incompatible assumptions about learner state, mastery, diagnosis, recommendation selection, event processing, or persistence.

This document does not claim that any capability described here is already implemented.

### 1.1 Implementation objectives

The implementation must:

1. Accept authenticated, validated learning evidence from Qrie and other authorized clients.
2. Preserve a durable, auditable history of learning events.
3. Maintain persistent learner state for individual concepts.
4. Distinguish independent performance from assisted performance.
5. Estimate mastery without claiming more certainty than the evidence supports.
6. Represent possible misconceptions as hypotheses rather than unquestioned facts.
7. Recommend appropriate next actions while respecting prerequisite constraints.
8. Schedule future retrieval and retention assessments.
9. Expose stable, versioned APIs and integration contracts.
10. Support deterministic testing and reproducible decisions.
11. Protect student information through tenant isolation, access control, data minimization, and defined retention policies.
12. Provide evidence that the system improves independent mastery, retention, and transfer.
13. Keep shared-model training outside the live event-processing path.
14. Permit future algorithm and model improvements without requiring changes to Qrie's internal implementation.

### 1.2 Governing principle

The implementation must follow:

**Observe → Diagnose → Teach → Test → Update Learner Model → Select Next Best Action → Revisit Later.**

LAM decides how evidence changes learner state and what learning action should happen next. The host application delivers the selected learning experience and returns the resulting evidence.

---

## 2. Authority and document precedence

The existing LAM PRDs define product intent. The engineering handbook and engineering standards define mandatory engineering behavior. This specification defines the implementation contract derived from those sources.

If requirements conflict, engineers must not silently choose whichever version is easier to implement.

The conflict must be entered in the decision register in Section 17. The responsible technical owner must approve the resolution before the affected behavior is implemented.

Security, privacy, authentication, tenant isolation, auditability, and the prohibition against treating assisted success as independent mastery cannot be bypassed for convenience.

A requirement is not complete merely because an endpoint responds successfully. Completion requires implementation, automated tests, manual verification where specified, and documented evidence.

---

## 3. Scope and system boundaries

### 3.1 LAM owns

LAM is responsible for:

- Learning-event ingestion and validation.
- Evidence provenance and the event ledger.
- Persistent learner state.
- Mastery estimation and uncertainty.
- Independent and assisted performance tracking.
- Misconception hypotheses and diagnostic evidence.
- Assistance policy and productive-struggle decisions.
- Prerequisite-aware sequencing.
- Next-best-action selection.
- Retrieval and forgetting management.
- Teaching-strategy effectiveness evidence.
- Session-level learning analysis.
- Versioned APIs and SDK contracts.
- Shared-model governance and lifecycle.
- Evaluation, observability, and decision auditability.

### 3.2 Qrie and other host applications own

The host application is responsible for:

- Student authentication at the application level and delivery of trusted identity to LAM.
- Student-facing interfaces.
- Curriculum content and lesson generation.
- Question, hint, explanation, and worked-example content.
- Assessment delivery and collection of responses.
- Answer verification and grading provenance.
- Audio, voice, animation, and interactive classroom rendering.
- School, teacher, and student administration.
- Presenting LAM recommendations to learners.
- Reporting the actual intervention delivered and its outcome.

LAM may request a diagnostic question, a hint, independent practice, prerequisite remediation, or a review. It does not generate the corresponding lesson or classroom content.

### 3.3 Architectural boundary

LAM must be independently deployable and consumable through a stable REST API and SDKs.

Qrie must not import LAM's internal Python modules or depend on its database schema. Integration must occur through documented external contracts.

LAM must not depend on Qrie's internal application packages.

### 3.4 Initial deployment topology

**Proposed Default:** Start with a modular monolith.

Use one independently deployable LAM service with well-separated modules. Keep shared-model training and evaluation in a separate offline execution path. Do not introduce a separate network service for every subsystem unless operational evidence justifies it.

---

## 4. Required technology and repository structure

The implementation should use the technology choices established by the engineering documents:

- Python for domain and application logic.
- FastAPI for HTTP endpoints.
- Pydantic v2 for boundary validation.
- SQLAlchemy 2.0 with asynchronous database access.
- asyncpg for PostgreSQL connectivity.
- Alembic for database migrations.
- PostgreSQL for durable event and learner-state storage.
- pytest for automated tests.
- Ruff for linting and formatting.
- mypy in strict mode for static type checking.
- OpenAPI for the HTTP contract.
- A documented Python SDK and TypeScript client or adapter for external consumers.

Exact dependency versions must be pinned in the project configuration and updated through reviewed changes.

### 4.1 Suggested repository structure

```text
lam/
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── .env.example
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── docs/
│   ├── LAM_IMPLEMENTATION_SPECIFICATION.md
│   ├── architecture.md
│   ├── api-contracts.md
│   ├── domain-model.md
│   ├── algorithm-specifications.md
│   ├── security-and-privacy.md
│   ├── testing-and-verification.md
│   ├── deployment-and-operations.md
│   └── decisions/
├── src/
│   └── lam/
│       ├── api/
│       │   ├── routes/
│       │   ├── dependencies.py
│       │   ├── error_handlers.py
│       │   └── schemas/
│       ├── application/
│       │   ├── services/
│       │   ├── commands/
│       │   └── queries/
│       ├── domain/
│       │   ├── events/
│       │   ├── learner_state/
│       │   ├── mastery/
│       │   ├── diagnosis/
│       │   ├── decisions/
│       │   ├── retrieval/
│       │   ├── curriculum/
│       │   └── shared/
│       ├── infrastructure/
│       │   ├── database/
│       │   ├── repositories/
│       │   ├── authentication/
│       │   ├── observability/
│       │   └── integrations/
│       └── main.py
├── sdk/
│   ├── python/
│   └── typescript/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   ├── end_to_end/
│   └── fixtures/
└── evaluation/
    ├── scenarios/
    ├── datasets/
    ├── baselines/
    └── reports/
```

### 4.2 Dependency direction

The permitted dependency direction is:

**API → Application services → Domain logic**

Infrastructure implements persistence and external-service interfaces consumed by application services.

Domain code must not directly depend on FastAPI, HTTP request objects, ORM sessions, external model providers, or database implementation details.

Business logic must not be hidden inside route handlers, ORM hooks, SDK wrappers, or background-job callbacks.

---

## 5. Core domain model

The domain model must distinguish recorded observations from derived conclusions.

### 5.1 Learning event

A learning event represents an observable learning interaction, such as an attempt, hint, explanation, assessment, or retrieval review.

Required or conditionally required fields must be validated against a versioned schema.

| Field | Meaning |
|---|---|
| `event_id` | Unique event identifier used for idempotent ingestion |
| `tenant_id` | Organization boundary, derived or verified server-side |
| `student_id` | Learner identity resolved and authorized by the server |
| `session_id` | Learning session reference |
| `concept_ids` | Concepts addressed by the activity |
| `item_id` | Question or assessment reference |
| `timestamp` | Event time, timezone-aware and normalized for persistence |
| `event_type` | Attempt, hint, explanation, assessment, review, or another defined type |
| `correctness` | Outcome with verification provenance, or unknown |
| `attempt_number` | Position in the attempt sequence, when applicable |
| `assistance_level` | Amount of assistance received, when applicable |
| `hints_used` | Hint metadata, when available |
| `response_time_ms` | Response duration, when available and meaningful |
| `self_reported_confidence` | Learner-stated confidence, when available |
| `strategy_id` | Teaching strategy identifier, when applicable |
| `intervention_id` | Intervention identifier, when applicable |
| `difficulty` | Difficulty value or explicitly unknown |
| `assessment_mode` | Independent, assisted, delayed, transfer, or another defined mode |
| `provenance` | Origin and verification status of the evidence |
| `schema_version` | Version of the event contract |

Additional operational fields may include a server-generated ingestion timestamp, request identifier, policy version, and audit metadata.

A client-supplied `student_id` or `tenant_id` must never independently authorize access to that student's records.

Missing optional values must remain unknown. They must not silently become `0`, `false`, or an arbitrary default.

### 5.2 Learner state

Learner state represents the current evidence-supported estimate of what a student understands about a concept.

The state must be keyed by the authorized learner and concept, with tenant, subject, curriculum, and prerequisite context where required.

It should support:

- Overall mastery estimate and uncertainty.
- Independent mastery estimate and uncertainty.
- Assisted performance.
- Evidence counts and evidence references.
- Misconception hypotheses.
- Retention and retrieval history.
- Strategy and intervention outcomes.
- Last practice time and next review time.
- State version.
- Algorithm, policy, graph, and schema versions used to produce it.
- A reason explaining why the state changed.

Historical state snapshots or equivalent reconstructable history must be available for audit and debugging.

### 5.3 Misconception hypothesis

A misconception hypothesis is a possible explanation for a student's observed difficulty.

It must contain:

- Hypothesis identifier.
- Student and concept references.
- Hypothesis category.
- Supporting evidence references.
- Contradictory evidence references, when available.
- Confidence estimate and its meaning.
- Lifecycle status.
- Creation and update timestamps.
- Diagnosis-policy version.
- Reason for confirmation, revision, or retirement.

Possible categories include conceptual misunderstanding, missing prerequisite, procedural error, arithmetic error, misreading, guessing, retrieval failure, carelessness, and flawed reasoning.

These are candidate explanations, not permanent student labels.

### 5.4 Recommendation

A recommendation represents a learning action that the host application should deliver.

It should include:

- Recommendation identifier.
- Action type.
- Target concept.
- Suggested strategy.
- Assistance level.
- Relevant evidence references.
- Reason codes.
- Brief user-safe rationale.
- Uncertainty or insufficient-evidence indicator.
- Required prerequisite conditions.
- Relevant learner-state version.
- Policy version.
- Curriculum-graph version.
- Model version, when a model is involved.
- Safe fallback or explicit inability to recommend.

A recommendation must not contain internal chain-of-thought or unsupported claims about a student's ability.

### 5.5 Retrieval plan

A retrieval plan represents when and how a concept should be revisited.

It should include:

- Learner and concept identifiers.
- Last qualifying practice event.
- Last independent success.
- Last retrieval outcome.
- Current review interval.
- Next scheduled review.
- Scheduling-policy version.
- Reason for scheduling or rescheduling.
- Whether the review is overdue.
- Whether the review is intended to verify durable mastery.

---

## 6. API contracts and request lifecycle

All external APIs must be versioned and documented in OpenAPI.

### 6.1 Required initial API surface

| Endpoint | Purpose |
|---|---|
| `POST /v1/events` | Validate and ingest learning evidence |
| `GET /v1/learners/{learner_id}/state` | Retrieve authorized learner state |
| `GET /v1/learners/{learner_id}/concepts/{concept_id}/state` | Retrieve state for one concept |
| `POST /v1/recommendations` | Request a next-best-action recommendation |
| `GET /v1/learners/{learner_id}/reviews` | Retrieve scheduled or overdue reviews |
| `GET /health/live` | Check process liveness |
| `GET /health/ready` | Check whether required dependencies are available |

The API may use a server-resolved learner context rather than exposing every identifier in the path. The final contract must not rely on client-provided IDs as proof of authorization.

### 6.2 Event-ingestion lifecycle

The event-ingestion operation must perform the following logical steps:

1. Assign or validate a request identifier.
2. Authenticate the caller.
3. Resolve tenant and learner permissions.
4. Validate the event against its schema version.
5. Validate identifiers, value ranges, event types, timestamps, and provenance.
6. Check event identity and idempotency.
7. Persist valid evidence durably.
8. Apply eligible deterministic state changes according to the selected milestone's policy.
9. Record the state version and processing outcome.
10. Return a stable response describing the result.

If processing fails, the system must not silently lose the event or partially apply a state update.

Where event ingestion and state update are required to be atomic, they must share a transaction or use a documented recoverable processing design with equivalent guarantees.

### 6.3 Recommendation lifecycle

A recommendation request must:

1. Authenticate and authorize the caller.
2. Resolve the correct learner and tenant.
3. Load the relevant learner state.
4. Load or validate the curriculum-graph version and prerequisite information.
5. Determine whether evidence is sufficient for a specific recommendation.
6. Apply mandatory safety, prerequisite, and progression constraints.
7. Evaluate eligible next actions under the versioned decision policy.
8. Produce the recommendation with reason codes, relevant versions, and uncertainty.
9. Persist a decision audit record when required by the selected policy.
10. Return the recommendation to the host application.

If the learner state or curriculum information is unavailable, the service must return a documented safe fallback or explicit error. It must not invent confident mastery estimates or recommend actions that violate known prerequisites.

### 6.4 Error contract

Errors must have a stable machine-readable format:

```json
{
  "error": {
    "code": "INVALID_EVENT_SCHEMA",
    "message": "The submitted event does not satisfy the required schema.",
    "request_id": "server-generated-request-id",
    "details": []
  }
}
```

The final implementation must define stable error codes for at least:
- Invalid request or schema.
- Missing or invalid credentials.
- Unauthorized tenant or learner access.
- Unknown resource.
- Duplicate event.
- State-version conflict.
- Invalid curriculum or concept reference.
- Rate limiting.
- Dependency unavailable.
- Internal processing failure.

---

## 7. Authentication, tenant isolation, and event integrity

### 7.1 Authorization requirements

Every learner-data operation must verify permissions server-side:
- Tenant-scoped access.
- Learner-level access.
- Appropriate service-to-service permissions.
- Explicit authorization for administrative or cross-learner operations.
- Authorization for background jobs and asynchronous workers.
- Separation between development, test, staging, and production credentials.

A student ID in a URL or request body is not authorization.

### 7.2 Idempotency

Repeated delivery of the same valid event must not apply the same logical learner-state update twice.

The database must enforce uniqueness constraints. Application-level memory checks are insufficient.

The system must distinguish between:
- A new event.
- A repeated event with equivalent content.
- An attempted reuse of the same event identifier with conflicting content (rejected/quarantined).

**Acceptance criterion:** submitting an identical event repeatedly produces one logical state transition, with a documented response for duplicate submissions.

### 7.3 Concurrent updates

Concurrent events must not silently overwrite each other.

Use transactions and optimistic locking or an equivalent concurrency-safe mechanism. State updates must verify the expected state version before committing.

### 7.4 Corrections

Historical evidence must not be silently rewritten or deleted. A correction workflow must record original event reference, superseding event, reason, actor, state recalculation, and affected state versions.

---

## 8. Learner-state engine and mastery estimation

### 8.1 State-update contract

Each state update receives prior state, validated event, curriculum context, algorithm/version, and policy configuration. It returns updated state, state version, evidence references, reason code, and uncertainty. Domain logic must be deterministic.

### 8.2 Independent and assisted performance

Independent and assisted evidence must be represented separately. A correct answer after a hint, worked example, partial solution, or direct explanation cannot automatically establish independent mastery.

### 8.3 Bayesian Knowledge Tracing

BKT is the baseline mastery-estimation approach for M1. The implementation specification must define:
- Exact BKT variant ($P(L_0), P(T), P(G), P(S)$).
- Parameter provenance and configuration.
- Classification of independent vs. assisted evidence.
- Handling of ambiguous/unverified outcomes.
- State initialization in insufficient-evidence state.
- Replay consistency and parameter evaluation.

### 8.4 State initialization

A new learner-concept pair begins in a documented insufficient-evidence state, distinguished from a concept with repeated failures.

### 8.5 Mastery verification

Mastery confirmation must rely on independent assessment evidence. A single correct answer, lesson completion, high engagement, or assisted success must not independently confirm durable mastery.

---

## 9. Misconception diagnosis

### 9.1 Diagnostic objective

The diagnosis engine evaluates plausible explanations for a learner's difficulty. It does not automatically label every incorrect answer as a misconception.

### 9.2 Required behavior

1. Examine validated evidence.
2. Identify plausible candidate explanations.
3. Preserve uncertainty where evidence is ambiguous.
4. Distinguish prerequisite gaps from conceptual misunderstandings.
5. Consider procedural errors, arithmetic errors, misreading, retrieval failure, guessing, and slips.
6. Request additional diagnostic evidence when necessary.
7. Record supporting and contradictory evidence.
8. Update hypothesis lifecycle status (`open → confirmed → revised or retired`).
9. Retain an audit trail.

---

## 10. Adaptive decision engine and assistance policy

### 10.1 Responsibility

The decision engine selects the next appropriate learning action from eligible candidates. It does not generate lesson content.

### 10.2 Candidate actions

Independent practice, metacognitive/rethink prompt, conceptual question, hint, stronger hint, analogy/alternative explanation, similar worked example, partial solution, direct explanation, prerequisite remediation, diagnostic question, delayed retrieval review, independent mastery verification.

### 10.3 Assistance ladder (Levels 0 to 8)

| Level | Meaning |
|---|---|
| 0 | Independent attempt |
| 1 | Rethink prompt |
| 2 | Conceptual question |
| 3 | Small hint |
| 4 | Stronger hint |
| 5 | Similar worked example |
| 6 | Partial solution |
| 7 | Full explanation |
| 8 | Direct answer |

### 10.4 Decision priority

1. Safety and stop conditions.
2. Blocking prerequisite gaps.
3. Confirmed misconceptions.
4. Overdue retrieval.
5. Mastery verification.
6. Curriculum and learning goals.
7. Difficulty fit.

---

## 11. Curriculum graph integration

LAM consumes a versioned curriculum/concept DAG through a stable adapter. It does not maintain an independently drifting copy. Cycles must be detected and rejected. Decision engine must never progress past an unmet hard prerequisite.

---

## 12. Retrieval and forgetting management

- Baseline review interval: 1 day.
- Interval expanded after independent success ($2.0 \times - 2.5 \times$).
- Interval retained/reduced after assisted success.
- Reset to 1 day and concept marked `fragile` after review failure.
- Overdue reviews prioritized.
- Durable mastery requires passed delayed retention check.

---

## 13. Event ledger, persistence, and transaction requirements

PostgreSQL stores learning events, learner-concept state, state snapshots, hypotheses, retrieval schedules, and decision audit logs. Enforce event idempotency, tenant isolation, foreign keys, optimistic concurrency (`state_version`), and atomic commit/rollback.

---

## 14. Learning Scientist and asynchronous session analysis

Asynchronous, non-blocking post-session batch processor. Idempotently summarizes session evidence, identifies macro patterns, and proposes provisional updates. High-impact updates require validation before mutating authoritative learner state.

---

## 15. Answer verification and evidence provenance

Supported provenance:
- `symbolic_math_check`
- `code_tests`
- `answer_key`
- `curriculum_fact_check`
- `teacher`
- `model_graded` (provisional only; cannot confirm mastery alone)

---

## 16. Shared Learning Adaptation Model

Separately governed offline training pipeline. No live online training on incoming events. Data governance, anonymization, consent checks, and offline evaluation against baseline before any model promotion.

---

## 17. Decision register — mandatory before affected implementation

| ID | Decision | Required resolution |
|---|---|---|
| D-01 | Mastery policy | Approve estimate threshold, evidence-count requirements, session separation, difficulty requirements, and delayed-retention requirements |
| D-02 | BKT configuration | Approve model variant, parameters, initialization, and parameter-versioning strategy |
| D-03 | Uncertainty semantics | Define what uncertainty represents, how it is calculated, and how it affects progression |
| D-04 | Diagnosis confirmation | Approve confidence semantics, evidence-independence rules, and hypothesis lifecycle thresholds |
| D-05 | Assistance ladder | Approve level mappings, escalation transitions, reset rules, and independence requirements |
| D-06 | Decision priority | Approve hard constraints, priority ordering, tie-breaking, and fallback behavior |
| D-07 | Retrieval scheduler | Approve baseline interval, multipliers, caps, overdue handling, and failure resets |
| D-08 | Event idempotency | Approve duplicate-event responses and conflicting reuse of event identifiers |
| D-09 | Identity and tenancy | Approve trusted identity propagation, service authentication, and tenant authorization |
| D-10 | Curriculum adapter | Approve graph schema, version compatibility, and behavior when the graph is unavailable |
| D-11 | Learning Scientist | Approve asynchronous processing, retry, commit, and state-recalculation semantics |
| D-12 | Verification provenance | Approve supported provenance types and which can contribute to mastery confirmation |
| D-13 | Privacy lifecycle | Approve consent, retention, deletion, correction, and training eligibility |
| D-14 | Operational targets | Approve latency, throughput, availability, recovery, and observability targets |
| D-15 | API and SDK compatibility | Approve versioning, deprecation, error contracts, and supported client compatibility |
| D-16 | Evaluation thresholds | Approve baseline datasets, outcome metrics, minimum evidence, and model/policy promotion gates |

---

## 18. Testing and acceptance requirements

- **Unit tests:** Domain rules, BKT, assistance ladder, DAG validation, decision priority.
- **Integration tests:** Real isolated PostgreSQL database, migrations, idempotency replay, concurrency version checks.
- **Contract tests:** Pydantic schema validation, SDK compatibility, error codes.
- **Security tests:** Tenant isolation, token validation, non-leakage of PII in logs.
- **End-to-end tests:** 12-step learning cycle from attempt to delayed retrieval.
- **Manual scenarios:** 12 defined test scenarios before M2 gate.

---

## 19. CI/CD and engineering workflow

Mandatory quality gates in CI:
```bash
ruff check .
ruff format --check .
mypy --strict src/lam
pytest
```
No engineer may bypass a required gate to merge a change.

---

## 20. Observability, performance, and recovery

Structured, privacy-safe metrics and logs. No raw student PII/transcripts logged. Explicit error codes, retry policies, and safe fallbacks.

---

## 21. Milestones and release gates

- **M0 — Service foundation:** Repo scaffold, typed contracts, auth/tenant middleware, PostgreSQL migrations, event ledger, CI.
- **M1 — Deterministic learner model:** Per-concept state, BKT baseline, assisted vs. independent separation, diagnosis hypotheses, rule-based decisions.
- **M2 — Closed-loop Qrie integration:** Qrie adapter, curriculum DAG, assistance ladder, spaced retrieval, independent assessments.
- **M3 — Validated personalization:** Strategy effectiveness, uncertainty calibration, proactive struggle triggers, baseline benchmarking.
- **M4 — Governed shared intelligence:** Offline pipeline, anonymized datasets, versioned models, staged rollout/rollback.

---

## 22. Definition of Done

Done requires: issue link, design documentation, clean architecture compliance, test coverage (unit/integration/contract), manual test record for visible behavior, zero P0/P1 defects, schema versioning, passing CI quality gates, and verified milestone acceptance criteria.

---

## 23. Final implementation directive

Build LAM incrementally starting with M0. Establish durable evidence, tenant authorization, deterministic state transitions, reproducible policies, and tested integration contracts before introducing complex machine learning or distributed orchestration.
