# Requirement Traceability Matrix

**Milestone:** M0 (Service Foundation & Hardening)  
**Last Updated:** 2026-10-18  

---

| Requirement ID | Requirement Summary | Implementation Source | Test File / Function | Evidence / Status |
|:---|:---|:---|:---|:---:|
| **FR-01** | Capture structured learning events in an append-only ledger | `src/lam/infrastructure/database/models.py:LearningEventModel`, `src/lam/infrastructure/repositories/ledger_repository.py` | `tests/integration/test_event_ingestion.py::test_successful_event_ingestion`, `tests/integration/test_postgres_integration.py` | `VERIFIED` |
| **FR-01.1** | Idempotent event ingestion (replays must not double-apply state updates) | `src/lam/infrastructure/repositories/ledger_repository.py::ingest_event`, `src/lam/application/services/ingestion_service.py` | `tests/integration/test_event_ingestion.py::test_idempotent_event_deduplication`, `tests/integration/test_postgres_concurrency.py::test_concurrent_duplicate_event_submissions_race` | `VERIFIED` |
| **FR-01.2** | Non-coercion rule: missing/unknown signals must not be coerced to 0/false | `src/lam/domain/events/models.py::LearningEvent` | `tests/unit/test_events_validation.py::test_non_coercion_of_missing_signals` | `VERIFIED` |
| **FR-02** | Persistent per-concept learner state with optimistic concurrency & row locking | `src/lam/domain/learner_state/models.py`, `src/lam/infrastructure/repositories/state_repository.py` | `tests/integration/test_postgres_concurrency.py::test_concurrent_distinct_events_for_same_concept`, `test_state_version_conflict_optimistic_concurrency` | `VERIFIED` |
| **FR-02.1** | Strict separation of independent mastery from assisted performance | `src/lam/application/services/ingestion_service.py` | `tests/integration/test_event_ingestion.py::test_assisted_success_does_not_advance_independent_mastery` | `VERIFIED` |
| **FR-07** | Strict cryptographic JWT authentication, tenant binding, and multi-tenant isolation | `src/lam/infrastructure/authentication/jwt.py`, `src/lam/infrastructure/authentication/middleware.py::get_security_context` | `tests/security/test_tenant_isolation.py` (7 tests covering forged, expired, cross-tenant mismatch, admin prefix rejection, verified admin) | `VERIFIED` |
| **NFR-01** | Schema-validated API endpoints with stable error formats | `src/lam/api/routes/events.py`, `src/lam/main.py::validation_exception_handler` | `tests/unit/test_events_validation.py`, `tests/integration/` | `VERIFIED` |
| **NFR-02** | Clean architecture: pure domain logic decoupled from web framework/ORM | `src/lam/domain/` has zero dependencies on FastAPI or SQLAlchemy | `src/lam/domain/events/models.py`, `src/lam/domain/learner_state/models.py` | `VERIFIED` |
| **NFR-03** | High-concurrency race safety & transactional atomicity | `src/lam/infrastructure/repositories/ledger_repository.py` (savepoints), `state_repository.py` (`with_for_update`) | `tests/integration/test_postgres_concurrency.py` (4 tests) | `VERIFIED` |
| **FR-03** | Bayesian Knowledge Tracing (BKT) mastery estimation | `docs/decisions/D-02-bkt-parameters.md` | Pure Python BKT engine in `src/lam/domain/mastery/bkt.py` | `BLOCKED` (Awaiting D-01/D-02 sign-off) |
| **FR-04** | Misconception hypothesis testing & diagnosis | Not yet implemented | None | `NOT_STARTED` (M1) |
| **FR-05** | Deterministic adaptive next-action decision policy | Not yet implemented | None | `NOT_STARTED` (M1) |
| **FR-06** | 9-level productive-struggle assistance ladder | Not yet implemented | None | `NOT_STARTED` (M2) |
| **FR-08** | Spaced retrieval forgetting curve scheduler | Not yet implemented | None | `NOT_STARTED` (M2) |
