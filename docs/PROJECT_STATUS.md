# LAM Project Status

**Current Date:** 2026-10-18  
**Current Milestone:** Milestone M0 — Service Foundation  
**Overall Status:** `VERIFIED` (M0 Core Foundation on SQLite; PostgreSQL daemon test environment pending)  

---

## 1. Milestone Tracking

| Milestone | Focus | Status | Target Completion | Evidence / Notes |
|:---|:---|:---:|:---:|:---|
| **M0** | **Service Foundation** | `VERIFIED` | 2026-10-18 | Repo scaffold, Pydantic contracts, event ledger, state persistence, Alembic migrations, tenant auth, 8/8 tests passing, ruff & mypy clean. |
| **M1** | **Deterministic Learner Model** | `BLOCKED` | TBD | Blocked on approval of decisions `D-01` (Mastery Policy) and `D-02` (BKT Configuration). |
| **M2** | **Closed Loop with Qrie** | `NOT_STARTED` | TBD | Requires M1 completion and Qrie curriculum DAG adapter. |
| **M3** | **Personalization & Strategy** | `NOT_STARTED` | TBD | Requires M2 closed-loop evidence collection. |
| **M4** | **Governed Shared Intelligence** | `NOT_STARTED` | TBD | Offline pipeline; depends on M1–M3 baseline. |

---

## 2. Component Health Matrix

| Component | Layer | Status | Implemented Behavior | Remaining Gaps / Limitations |
|:---|:---|:---:|:---|:---|
| **Event Ledger** | Infrastructure | `VERIFIED` | Append-only ledger with database-level uniqueness constraint `(tenant_id, event_id)` for idempotency. | Needs validation against a live PostgreSQL server (currently tested on async SQLite). |
| **Event Validation** | Domain | `VERIFIED` | Pydantic v2 domain models; strictly enforces non-coercion rule (`None` remains `None`). | None for M0 scope. |
| **Learner State** | Domain / Infra | `VERIFIED` | Multi-dimensional tracking; assisted success updates assisted performance only; optimistic concurrency via `state_version`. | Full BKT knowledge-tracing calculation is deferred to M1. |
| **Auth & Isolation** | Infrastructure | `VERIFIED` | Server-side Bearer token validation and `X-Tenant-ID` scoping. Cross-tenant access blocked. | JWT signature verification and role-based access control (RBAC). |
| **API Gateway** | API | `VERIFIED` | `POST /v1/events`, `GET /v1/learners/{id}/state`, `GET /v1/learners/{id}/concepts/{c_id}/state`, `/health/live`, `/health/ready`. | `POST /v1/recommendations`, `GET /v1/reviews` (M1/M2). |
| **Database Migrations**| Infrastructure | `VERIFIED` | Alembic async migrations; upgrade to head and downgrade to base verified. | Live PostgreSQL test run. |
| **Decision Engine** | Domain | `NOT_STARTED`| None. | M1 rule-based next-action policy (`D-05`, `D-06`). |
| **Diagnosis Engine**| Domain | `NOT_STARTED`| None. | M1 competing hypothesis generation (`D-04`). |
| **Retrieval Engine**| Domain | `NOT_STARTED`| None. | M2 spaced forgetting curve scheduler (`D-07`). |

---

## 3. Latest Verification Evidence

- **Linting & Code Quality:** `ruff check .` $\rightarrow$ **0 errors** (PASSED)
- **Formatting:** `ruff format --check .` $\rightarrow$ **22 files clean** (PASSED)
- **Static Type Checking:** `mypy --strict src/lam tests` $\rightarrow$ **0 issues in 20 files** (PASSED)
- **Automated Test Suite:** `pytest -v` $\rightarrow$ **8 passed in 0.89s** (PASSED)
  - `tests/unit/test_events_validation.py`: 3/3 passed (valid event, zero-coercion, bounds check)
  - `tests/integration/test_event_ingestion.py`: 3/3 passed (ingestion, idempotency replay, assisted vs unassisted isolation)
  - `tests/security/test_tenant_isolation.py`: 2/2 passed (tenant data isolation, 401 unauthenticated check)
- **Database Migrations:** `alembic upgrade head && alembic downgrade base && alembic upgrade head` $\rightarrow$ **PASSED**

---

## 4. Current Blockers & Decisions Required

Before implementing Milestone M1 domain logic, the following formal decisions in `docs/decisions/` require sign-off:

1. **`D-01` (Mastery Policy):** Define the exact threshold (e.g. $\ge 0.9$) and evidence criteria ($\ge 3$ independent attempts across $\ge 2$ sessions) for durable mastery.
2. **`D-02` (BKT Configuration):** Define baseline BKT parameters ($P(L_0), P(T), P(G), P(S)$) and parameter versioning.
3. **`D-05` (Assistance Ladder):** Define exact transition rules between Levels 0 through 8.
4. **`D-06` (Decision Priority):** Define deterministic priority order and tie-breaking for next-action recommendations.

---

## 5. Next Concrete Task

- **Task ID:** `TASK-M1-01` (Record and Review Initial Decisions D-01 and D-02).
- **Objective:** Draft formal decision records `docs/decisions/D-01-mastery-policy.md` and `docs/decisions/D-02-bkt-parameters.md` with explicit mathematical formulas and test vectors to unlock M1 implementation.
