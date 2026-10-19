# Testing and Verification Log

**Last Execution Date:** 2026-10-19  
**Environment:** Linux (x86_64), Python 3.11.16, PostgreSQL 16 (podman container `lam-postgres-test`) & SQLite (aiosqlite in-memory)  
**Milestone:** M0 (Foundation Hardened), M1 (Deterministic Learner Model), & M2 (Closed-Loop Engines & Storage)  

---

## 1. Test Execution Summary

| Test Category | Command | Target | Total | Passed | Failed | Status | Evidence / Notes |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Code Style & Lint** | `ruff check .` | Whole project | - | - | 0 | `PASSED` | 0 errors across all Python files. |
| **Formatting** | `ruff format --check .` | Whole project | 88 files | 88 | 0 | `PASSED` | All source, test, and migration files cleanly formatted. |
| **Static Type Check** | `mypy --strict src/lam tests` | Source & tests | 70 files | 70 | 0 | `PASSED` | Zero type errors in strict mode across 70 source files. |
| **BKT Domain Tests** | `pytest tests/unit/test_bkt.py -v` | Pure Python BKT engine | 7 | 7 | 0 | `PASSED` | Parameters, bounds, 4-step D-02 vectors, assisted bypass, missing signal bypass, boundary stability, $n \ge 44$ uncertainty threshold. |
| **Curriculum DAG Tests** | `pytest tests/unit/test_curriculum_dag.py -v` | Pure Python DAG validator | 13 | 13 | 0 | `PASSED` | Empty graph, single node, linear chain, multi-prereq convergence, disconnected components, duplicate edge rejection, unknown node reference rejection, direct self-loops, 2-node cycles, multi-hop indirect cycles, malformed IDs, ancestor chain resolution, and blocking prerequisite identification. |
| **Assistance Escalation Tests** | `pytest tests/unit/test_assistance_escalation.py -v` | Pure Python state machine | 6 | 6 | 0 | `PASSED` | Tier 1 safety stop on $\ge 3$ consecutive failures, 2 failures escalation to Worked Example, single failure scaffolding step-up, fading ladder after 2 consecutive assisted successes, full reset to Level 0 on independent success, audit trail recording. |
| **Spaced Retrieval Tests** | `pytest tests/unit/test_spaced_retrieval.py -v` | Pure Python scheduler | 5 | 5 | 0 | `PASSED` | Interval progression (1d, 3d, 7d, 14d, 30d, 60d), assisted attempt conservative scaling, exponential retention decay $R(t)=\exp(-\Delta t / S)$, priority classification (overdue, due_soon, maintained), zero-attempt concept exclusion. |
| **Evidence Eligibility Tests** | `pytest tests/unit/test_evidence_eligibility.py -v` | Evidence rules (D-03) | 15 | 15 | 0 | `PASSED` | Verifier sources, provisional status, model-graded provenance, low reliability, assistance flags, missing correctness. |
| **Learner State Transition Tests** | `pytest tests/unit/test_learner_state_transition.py -v` | Initial state & BKT transitions | 7 | 7 | 0 | `PASSED` | Initial prior 0.10 semantics, unassisted updates, assisted isolation, provisional/unverified isolation, parameter versioning. |
| **Misconception Diagnosis Tests** | `pytest tests/unit/test_misconception_diagnosis.py -v` | Competing hypothesis engine (D-04) | 10 | 10 | 0 | `PASSED` | Missing correctness bypass, unverified/provisional rejection, single error candidate opening, repeated independent error confirmation, contradictory evidence retirement, scaffolding discounts, deduplication, competing hypotheses, determinism. |
| **Recommendation Engine Tests** | `pytest tests/unit/test_recommendation_engine.py -v` | Deterministic decision engine (D-06) | 16 | 16 | 0 | `PASSED` | Fallback, 7 priority tiers, confirmed vs open candidate misconception distinction, retired hypothesis bypass, conflicting priorities, tie-breaking, determinism. |
| **Config Security Tests**| `pytest tests/unit/test_config_security.py -v` | Fail-closed production config | 5 | 5 | 0 | `PASSED` | Dev default allowed; production rejects missing, default, or weak secrets (< 32 chars); production accepts valid strong keys. |
| **Unit Event Validation**| `pytest tests/unit/test_events_validation.py -v` | Domain event schema | 3 | 3 | 0 | `PASSED` | Valid event, non-coercion, bounds checking. |
| **Event Ingestion Integration** | `pytest tests/integration/test_event_ingestion.py -v` | Ingestion, BKT & provenance | 5 | 5 | 0 | `PASSED` | Ingestion, idempotency, assisted vs unassisted, end-to-end BKT trajectory matching D-02, unverified/provisional provenance handling. |
| **Recommendation API Integration** | `pytest tests/integration/test_recommendation_api.py -v` | `POST /v1/recommendations` | 6 | 6 | 0 | `PASSED` | Auth rejection, unknown student fallback, end-to-end event-to-recommendation flow, prerequisite blocking, safety stop, confirmed vs open misconception gating. |
| **Reviews API Integration** | `pytest tests/integration/test_reviews_api.py -v` | `GET /v1/learners/{id}/reviews` | 3 | 3 | 0 | `PASSED` | Auth rejection, multi-tenant isolation, priority filter (`overdue`, `due_soon`). |
| **Curriculum API Integration** | `pytest tests/integration/test_curriculum_api.py -v` | Curriculum DAG endpoints | 4 | 4 | 0 | `PASSED` | DAG validation, cycle detection (422), prerequisite blocking calculation, auth rejection. |
| **Qrie Contract & Boundary** | `pytest tests/integration/test_qrie_contract_and_boundary.py -v` | Application boundary contract | 5 | 5 | 0 | `PASSED` | Unauthorized/cross-tenant rejection, payload aliases (duration_ms), auto misconception confirmation & recommendation, assisted isolation, safety stops, reviews. |
| **Qrie Resilience & Recovery** | `pytest tests/integration/test_qrie_resilience_and_recovery.py -v` | Production LamRelayClient resilience | 8 | 8 | 0 | `PASSED` | 503 retry recovery, fast-fail 409/422/401, timeout limits, persistent 503 exhaustion, safe fallback without mastery guessing, outbox replay zero drift, conflict 409 rejection, cross-tenant 403 auth error. |
| **Diagnosis Persistence Integration** | `pytest tests/integration/test_diagnosis_persistence.py -v` | PostgreSQL 16 persistence | 4 | 4 | 0 | `PASSED` | Upsert, audit accumulation, status transitions and retirement, row locking and concurrency. |
| **Qrie Closed-Loop Integration** | `pytest tests/integration/test_qrie_end_to_end_loop.py -v` | Synthetic end-to-end lifecycle | 1 | 1 | 0 | `PASSED` | Complete closed-loop lifecycle covering event $\rightarrow$ candidate hypothesis $\rightarrow$ repeated error $\rightarrow$ confirmed hypothesis $\rightarrow$ Tier 3 diagnostic probe $\rightarrow$ assisted isolation $\rightarrow$ unassisted success $\rightarrow$ hypothesis retirement $\rightarrow$ curriculum progression $\rightarrow$ 3 failures safety stop. |
| **PostgreSQL Integration**| `pytest tests/integration/test_postgres_integration.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Connection, ingestion, idempotency deduplication, and tenant isolation on live PostgreSQL. |
| **PostgreSQL Concurrency**| `pytest tests/integration/test_postgres_concurrency.py -v` | Live PostgreSQL 16 | 4 | 4 | 0 | `PASSED` | Race condition duplicate submission, concurrent distinct state serialization, optimistic concurrency, and transaction rollback. |
| **Security & Auth Tests** | `pytest tests/security/ -v` | Cryptographic Auth & Isolation| 7 | 7 | 0 | `PASSED` | Forged token, expired token, cross-tenant header mismatch (403), admin string prefix rejection, verified admin role access, tenant data isolation. |
| **Database Migrations**| `DATABASE_URL=... alembic upgrade head` | PostgreSQL 16 | 3 revs | 3 | 0 | `PASSED` | Transactional DDL upgrade and downgrade verified on PostgreSQL 16 (`6ed18e85f377`, `435e371938d3`, and `a78f20436d91`). |

**Total passing test cases: 138 / 138 passed in 5.02s.**

---

## 2. Key Verification Invariants

1. **Non-Negotiable Misconception Invariant:** A single wrong answer opens a candidate hypothesis in `OPEN` status ($confidence=0.35$). It never confirms it. Confirmation strictly requires $\ge 2$ independent supporting observations and high confidence ($\ge 0.75$).
2. **Provenance Protection Invariant:** Clients cannot forge evidence eligibility by simply sending `status: "verified"`. The verification source must belong to trusted verifiers (`answer_key`, `symbolic_math_check`, `code_tests`, `curriculum_fact_check`, `teacher`), with non-low reliability, independence confirmed, and zero scaffolding (`assistance_level=0, hints_used=0`).
3. **Escalation Safety Stop Invariant:** 3 consecutive failures unconditionally trigger Tier 1 Safety Stop (Level 8, `teacher_intervention`), immediately halting automated escalation.
4. **Clean Domain Invariant:** All domain engines (`curriculum`, `assistance`, `retrieval`, `mastery`, `diagnosis`, `recommendation`) remain pure Python with zero database, ORM, or web framework imports.
