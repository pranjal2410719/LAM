# LAM Project Status

**Current Date:** 2026-10-18  
**Current Milestone:** Milestone M0 — Service Foundation (Hardened)  
**Overall Status:** `VERIFIED` for Milestone M0  

---

## 1. Milestone Tracking

| Milestone | Focus | Status | Target Completion | Evidence / Notes |
|:---|:---|:---:|:---:|:---|
| **M0** | **Service Foundation** | `VERIFIED` | 2026-10-18 | Repo scaffold, Pydantic contracts, append-only event ledger, tenant isolation, Alembic migrations verified against PostgreSQL 16, 12/12 tests passing, ruff & mypy clean, CI workflow configured. |
| **M1** | **Deterministic Learner Model** | `BLOCKED` | TBD | Blocked awaiting formal review and sign-off on decision records `D-01` (Mastery Policy) and `D-02` (BKT Parameters). |
| **M2** | **Closed Loop with Qrie** | `NOT_STARTED` | TBD | Requires M1 completion and Qrie curriculum DAG contract. |
| **M3** | **Personalization & Strategy** | `NOT_STARTED` | TBD | Requires M2 closed-loop evidence collection. |
| **M4** | **Governed Shared Intelligence** | `NOT_STARTED` | TBD | Offline pipeline; depends on M1–M3 baseline. |

---

## 2. Component Health Matrix

| Component | Layer | Status | Implemented Behavior | Remaining Gaps / Limitations |
|:---|:---|:---:|:---|:---|
| **Event Ledger** | Infrastructure | `VERIFIED` | Append-only ledger with database-level uniqueness constraint `(tenant_id, event_id)` for idempotency. Verified against live PostgreSQL 16. | None for M0 scope. |
| **Event Validation** | Domain | `VERIFIED` | Pydantic v2 domain models; strictly enforces non-coercion rule (`None` remains `None`). | None for M0 scope. |
| **Learner State** | Domain / Infra | `VERIFIED` (Foundation) | Multi-dimensional tracking; assisted success updates assisted performance only; optimistic concurrency via `state_version`. | Current numeric increments in `ingestion_service.py` are fixed-step placeholders, not BKT. Real BKT math is specified in `D-02` and awaits implementation in M1. |
| **Auth & Isolation** | Infrastructure | `VERIFIED` (M0 Baseline) | Server-side Bearer token validation and `X-Tenant-ID` scoping. Cross-tenant access blocked. | Token validation uses prefix matching in M0; production requires cryptographic asymmetric JWT verification. |
| **API Gateway** | API | `VERIFIED` | `POST /v1/events`, `GET /v1/learners/{id}/state`, `GET /v1/learners/{id}/concepts/{c_id}/state`, `/health/live`, `/health/ready`. | `POST /v1/recommendations`, `GET /v1/reviews` (M1/M2). |
| **Database Migrations**| Infrastructure | `VERIFIED` | Alembic async migrations; transactional DDL upgrade and rollback verified on PostgreSQL 16. Application startup verifies connection without running `create_all()`. | None. |
| **Decision Engine** | Domain | `NOT_STARTED`| None. | M1 rule-based next-action policy (`D-05`, `D-06`). |
| **Diagnosis Engine**| Domain | `NOT_STARTED`| None. | M1 competing hypothesis generation (`D-04`). |
| **Retrieval Engine**| Domain | `NOT_STARTED`| None. | M2 spaced forgetting curve scheduler (`D-07`). |

---

## 3. Latest Verification Evidence

- **Linting & Code Quality:** `ruff check .` $\rightarrow$ **0 errors** (PASSED)
- **Formatting:** `ruff format --check .` $\rightarrow$ **30 files clean** (PASSED)
- **Static Type Checking:** `mypy --strict src/lam tests` $\rightarrow$ **0 issues in 21 files** (PASSED)
- **Automated Test Suite:** `pytest -v` $\rightarrow$ **12 passed in 3.57s** (PASSED)
  - `tests/unit/test_events_validation.py`: 3/3 passed (valid event, zero-coercion, bounds check)
  - `tests/integration/test_event_ingestion.py`: 3/3 passed (ingestion, idempotency replay, assisted vs unassisted isolation on SQLite)
  - `tests/integration/test_postgres_integration.py`: 4/4 passed against live PostgreSQL 16 container:
    - `test_postgres_connection_and_table_presence` (PASSED)
    - `test_postgres_event_ingestion_and_state_update` (PASSED)
    - `test_postgres_idempotency_deduplication` (PASSED)
    - `test_postgres_tenant_isolation` (PASSED)
  - `tests/security/test_tenant_isolation.py`: 2/2 passed (tenant data isolation, 401 unauthenticated check)
- **Database Migrations on PostgreSQL:** `alembic upgrade head && alembic downgrade base && alembic upgrade head` against PostgreSQL 16 $\rightarrow$ **PASSED**
- **Repository Hygiene:** Bytecode caches (`__pycache__`, `*.pyc`) and local SQLite database (`lam_dev.db`) untracked from Git; `.gitignore` established.

---

## 4. Current Blockers & Decisions Required

Before implementing Milestone M1 domain logic, formal sign-off is required on:
1. **`D-01` (Mastery Policy):** Drafted in [`docs/decisions/D-01-mastery-policy.md`](./decisions/D-01-mastery-policy.md). Status: `PROPOSED`.
2. **`D-02` (BKT Configuration):** Drafted in [`docs/decisions/D-02-bkt-parameters.md`](./decisions/D-02-bkt-parameters.md) with candidate values ($P(L_0)=0.10, P(T)=0.20, P(G)=0.20, P(S)=0.10$) and deterministic test vectors. Status: `PROPOSED`.

---

## 5. Next Concrete Task

- **Task ID:** `M1-APPROVAL-AND-ENGINE`
- **Objective:** Obtain formal technical review and sign-off on `D-01` and `D-02`, then implement the pure Python BKT domain engine in `src/lam/domain/mastery/`.
