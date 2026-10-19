# LAM Implementation Plan & Task Backlog

**Version:** 2.0  
**Status:** Active  
**Last Updated:** 2026-10-19  

---

## Milestone M0 — Service Foundation

| Task ID | Task Description | Dependencies | Acceptance Criteria | Tests & Evidence | Status |
|:---|:---|:---:|:---|:---|:---:|
| `M0-01` | **Repository Scaffold & Tooling** | None | Directory structure created, `pyproject.toml` configured with `ruff`, `mypy --strict`, `pytest`. | `ruff check`, `mypy`, `pytest` pass. | `VERIFIED` |
| `M0-02` | **Typed Event & State Domain Contracts** | `M0-01` | Pydantic v2 domain models for `LearningEvent` and `LearnerConceptState` strictly preventing coercion of nulls. | `tests/unit/test_events_validation.py` | `VERIFIED` |
| `M0-03` | **SQLAlchemy Database & Alembic Migrations** | `M0-02` | Tables for `learning_events` and `learner_states` with unique constraints. Migrations upgrade and downgrade cleanly. | `alembic upgrade head && alembic downgrade base` | `VERIFIED` |
| `M0-04` | **Ledger Ingestion & Idempotency Service** | `M0-03` | Atomic event ingestion. Replay returns duplicate status without duplicate state mutation. Conflicting reuse raises HTTP 409. | `tests/integration/test_event_ingestion.py` | `VERIFIED` |
| `M0-05` | **Authentication & Multi-Tenant Middleware** | `M0-01` | Cryptographic JWT verification (signature, issuer, audience, expiration). Token-tenant binding, cross-tenant rejection (403), role claims. | `tests/security/test_tenant_isolation.py` (7/7 passed) | `VERIFIED` |
| `M0-06` | **REST API Routes & Stable Error Formatting** | `M0-04`, `M0-05` | `POST /v1/events`, `GET /v1/learners/{id}/state`, `GET /health/live`, `GET /health/ready` with stable machine-readable error format. | Smoke test & integration tests. | `VERIFIED` |
| `M0-HARDENING` | **PostgreSQL Verification & Hygiene** | `M0-06` | Startup verifies connection without `create_all()`; live PostgreSQL 16 integration tests pass; `.gitignore` established; generated artifacts untracked; CI workflow created. | `tests/integration/test_postgres_integration.py` (4/4 passed), `.github/workflows/ci.yml`. | `VERIFIED` |
| `M0-CONCURRENCY` | **PostgreSQL High-Concurrency & Race Safety** | `M0-HARDENING` | Concurrent duplicate submissions handled cleanly without 500s; concurrent updates serialized with PostgreSQL row-level locks (`with_for_update`); transaction rollback verified. | `tests/integration/test_postgres_concurrency.py` (4/4 passed). | `VERIFIED` |

---

## Milestone M1 — Deterministic Learner Model

| Task ID | Task Description | Dependencies | Acceptance Criteria | Tests & Evidence | Status |
|:---|:---|:---:|:---|:---|:---:|
| `M1-01` | **Formalize Decisions D-01 & D-02** | None | Decision records for Mastery Policy (`D-01`, with $n \ge 44$ uncertainty arithmetic fix) and BKT parameters (`D-02`) written with exact equations and deterministic test vectors. | `docs/decisions/D-01-mastery-policy.md`, `D-02-bkt-parameters.md` | `COMPLETED` (Drafted as `PROPOSED`, awaiting sign-off) |
| `M1-02` | **BKT Knowledge Tracing Engine** | `M1-01` | Pure Python implementation of Corbett & Anderson BKT equations (`src/lam/domain/mastery/bkt.py`). Deterministic reproduction of all D-02 test vectors. Zero database/web framework dependencies. | `tests/unit/test_bkt.py` (7/7 passed) | `VERIFIED` |
| `M1-03` | **Assisted vs. Unassisted Segregation in Ingestion** | `M1-02` | Unassisted attempts update BKT independent mastery; assisted attempts update assisted performance only. Placeholder increments removed from state transitions. | `tests/integration/test_event_ingestion.py` passed | `VERIFIED` |
| `M1-EVIDENCE` | **Evidence Provenance & Eligibility Policy** | `M1-02` | Enforce verifier eligibility (`answer_key`, `symbolic_math_check`, `code_tests`, `curriculum_fact_check`, `teacher`); provisional, model-graded, and missing provenance strictly bypass BKT transitions. | `tests/unit/test_evidence_eligibility.py` (15/15 passed), `tests/integration/test_event_ingestion.py` | `VERIFIED` |
| `M1-STATE-SEMANTICS` | **Initial State & Parameter Auditability** | `M1-02` | Initial concept state semantics fixed to BKT prior $P(L_0)=0.10$, $n=0, U=1.0$; Alembic migration `435e371938d3` adds `bkt_parameter_version` column to `learner_states`. | `tests/unit/test_learner_state_transition.py` (7/7 passed), Alembic upgrade/downgrade verified | `VERIFIED` |
| `M1-REFACTOR` | **Decouple Cognitive Logic to Domain Layer** | `M1-EVIDENCE` | Cognitive calculations moved from `StateRepository` into pure domain function `apply_learning_event_transition()`. Repository handles DB persistence and concurrency. | Unit & integration concurrency tests | `VERIFIED` |
| `M1-05` | **Rule-Based Decision Engine (Next Action)** | `D-06` | Deterministic 7-tier priority ranking (Safety -> Prerequisite -> Confirmed Misconception -> Retrieval -> Verification -> Progression -> Practice) with safe fallback. Distinguishes confirmed misconceptions from candidate hypotheses. Endpoint `POST /v1/recommendations`. | `tests/unit/test_recommendation_engine.py` (16/16 passed), `tests/integration/test_recommendation_api.py` (6/6 passed) | `VERIFIED` |
| `M1-04` | **Misconception Diagnosis Engine** | `D-04` | Competing hypothesis lifecycle (`OPEN` candidate -> `CONFIRMED` -> `REVISED` / `RETIRED`) driven by independent evidence accumulation, contradiction tracking, scaffolding discounts, deduplication, and immutable audit trail. | `tests/unit/test_misconception_diagnosis.py` (10/10 passed) | `VERIFIED` |
| `M1-06` | **M1 Reproducibility & End-to-End Test Gate** | `M1-02`–`M1-05` | Event ingestion, evidence eligibility, initial state semantics, BKT transition, hypothesis diagnosis, and recommendation integration pass 100% deterministically across unit, concurrency, security, and PostgreSQL 16 suites. | 89/89 tests passed in 9.88s | `VERIFIED` |

---

## Milestone M2 — Closed Loop with Qrie

| Task ID | Task Description | Dependencies | Acceptance Criteria | Tests & Evidence | Status |
|:---|:---|:---:|:---|:---|:---:|
| `M2-01` | **Curriculum Knowledge Graph DAG Adapter** | None | Pure Python graph validator with DFS 3-color cycle detection, Kahn's topological sort with deterministic lexicographical tie-breaking, ancestor chain resolution, and blocking prerequisite identification (`src/lam/domain/curriculum/`). | `tests/unit/test_curriculum_dag.py` (13/13 passed) | `VERIFIED` |
| `M2-02` | **9-Level Assistance Ladder Escalation** | `D-05` | Pure Python state machine implementing Levels 0–8. Tier 1 safety stop on $\ge 3$ consecutive failures; step-down fading ladder on 2 consecutive assisted successes; reset on independent success (`src/lam/domain/assistance/`). | `tests/unit/test_assistance_escalation.py` (6/6 passed) | `VERIFIED` |
| `M2-03` | **Spaced Retrieval Scheduler** | `D-07` | Baseline expanding-interval ladder (1d, 3d, 7d, 14d, 30d, 60d), exponential retention decay $R(t)=\exp(-\Delta t / S)$, priority classification (overdue, due_soon, maintained), and REST endpoint `GET /v1/learners/{id}/reviews`. | `tests/unit/test_spaced_retrieval.py` (5/5 passed), `tests/integration/test_reviews_api.py` (3/3 passed) | `VERIFIED` |
| `M2-PERSISTENCE` | **Misconception Storage & Audit History** | `M1-04` | Transactional persistence models `MisconceptionHypothesisModel` and `HypothesisAuditEntryModel` with row locking (`with_for_update`), Alembic migration `a78f20436d91`. | `tests/integration/test_diagnosis_persistence.py` (4/4 passed) | `VERIFIED` |
| `M2-04` | **Closed-Loop Synthetic Integration** | `M2-01`–`M2-03` | Synthetic end-to-end integration test validating the complete closed-loop lifecycle from event ingestion through hypothesis lifecycle, recommendation gating, assisted isolation, progression, and safety stops. | `tests/integration/test_qrie_end_to_end_loop.py` (1/1 passed) | `VERIFIED` |
| `M2-05` | **Asynchronous Learning Scientist Agent** | `M2-04` | Post-session async batch synthesis; low-impact updates committed idempotently. | Backlog | `NOT_STARTED` |

---

## Milestone M3 — Validated Personalization

| Task ID | Task Description | Dependencies | Acceptance Criteria | Status |
|:---|:---|:---:|:---|:---|
| `M3-01` | **Teaching-Strategy Effectiveness Tracking** | Matched prior states; minimum sample size $\ge 30$; separate immediate vs delayed vs transfer outcomes. | `NOT_STARTED` |
| `M3-02` | **Confidence Calibration (Metacognition)** | Rolling window calibration gap; overconfidence and underconfidence triggers. | `NOT_STARTED` |
| `M3-03` | **Proactive Struggle Triggers** | Automated triggers for repeated failure, abnormal pause times, guessing. | `NOT_STARTED` |
| `M3-04` | **Controlled Policy Evaluation vs. Baseline** | Empirical verification that adaptive sequencing outperforms fixed sequencing on mastery gain. | `NOT_STARTED` |

---

## Milestone M4 — Governed Shared Intelligence

| Task ID | Task Description | Dependencies | Acceptance Criteria | Status |
|:---|:---|:---:|:---|:---|
| `M4-01` | **Cross-School Federation Schema** | Privacy-preserving federated aggregation without raw PII transfer. | `NOT_STARTED` |
| `M4-02` | **Empirical BKT Fitting Pipeline** | Fit $P(L_0), P(T), P(G), P(S)$ across historical cohorts using grid search / expectation maximization. | `NOT_STARTED` |
| `M4-03` | **Differential Privacy Exporter** | Export parameter updates with noise injection preserving differential privacy bounds. | `NOT_STARTED` |
