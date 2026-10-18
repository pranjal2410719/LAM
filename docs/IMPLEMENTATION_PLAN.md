# LAM Implementation Plan & Task Backlog

**Version:** 1.2  
**Status:** Active  
**Last Updated:** 2026-10-18  

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

| Task ID | Task Description | Dependencies | Acceptance Criteria | Status |
|:---|:---|:---:|:---|:---:|
| `M1-01` | **Formalize Decisions D-01 & D-02** | None | Decision records for Mastery Policy (`D-01`) and BKT parameters (`D-02`) written with exact equations, point-estimate vs epistemic uncertainty clarification, and deterministic test vectors. | `COMPLETED` (Drafted as `PROPOSED`, awaiting sign-off) |
| `M1-02` | **BKT Knowledge Tracing Engine** | `M1-01` (Sign-off) | Pure Python implementation of Standard BKT equations with candidate parameters $P(L_0), P(T), P(G), P(S)$. Deterministic state updates. Zero database/web framework dependencies. | `BLOCKED` (Awaiting D-01/D-02 Approval) |
| `M1-03` | **Assisted vs. Unassisted Segregation** | `M1-02` | Unassisted attempts update BKT independent mastery; assisted attempts update assisted performance only. Replace placeholder increments in `ingestion_service.py`. | `NOT_STARTED` |
| `M1-04` | **Misconception Diagnosis Engine** | `D-04` | Competing hypothesis tracking across standard taxonomy (`conceptual`, `procedural`, `guessing`, etc.) with confidence. | `NOT_STARTED` |
| `M1-05` | **Rule-Based Decision Engine (Next Action)** | `D-05`, `D-06` | Deterministic priority ranking: Safety $\rightarrow$ Prerequisite $\rightarrow$ Misconception $\rightarrow$ Practice. Endpoint `POST /v1/recommendations`. | `NOT_STARTED` |
| `M1-06` | **M1 Reproducibility & End-to-End Test Gate** | `M1-02`–`M1-05` | Fixed replay scenarios produce identical results; manual test records logged. | `NOT_STARTED` |

---

## Milestone M2 — Closed Loop with Qrie

| Task ID | Task Description | Dependencies | Acceptance Criteria | Status |
|:---|:---|:---:|:---|:---:|
| `M2-01` | **Curriculum Knowledge Graph DAG Adapter** | `D-10` | Ingestion of versioned concept graph; cycle detection; prerequisite blocking. | `NOT_STARTED` |
| `M2-02` | **9-Level Assistance Ladder Escalation** | `D-05`, `M1-05` | Policy escalates through Levels 0 to 8 on repeated struggle; resets on unassisted success. | `NOT_STARTED` |
| `M2-03` | **Spaced Retrieval Scheduler** | `D-07` | Baseline expanding-interval ladder (1d, $2.0\times - 2.5\times$); reset on failure; overdue prioritization. Endpoint `GET /v1/learners/{id}/reviews`. | `NOT_STARTED` |
| `M2-04` | **Evidence Provenance & Verification Trust Policy** | `D-12` | Ingestion of `judgment_source`; provisional vs. verified evidence handling. | `NOT_STARTED` |
| `M2-05` | **Asynchronous Learning Scientist Agent** | `D-11` | Post-session async batch synthesis; low-impact updates committed idempotently. | `NOT_STARTED` |

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
| `M4-01` | **Offline Training Dataset Extractor & Anonymizer** | Verified consent check; PII sanitization; tenant isolation verification. | `NOT_STARTED` |
| `M4-02` | **Offline Model Training & Versioning Pipeline** | Isolated offline execution; zero online weight training from live API requests. | `NOT_STARTED` |
| `M4-03` | **Candidate Model Evaluation & Staged Rollout** | Promotion gate: candidate must beat deterministic baseline; rollback tested. | `NOT_STARTED` |
