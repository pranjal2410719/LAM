# Changelog

All notable changes to the Learning Adaptation Model (LAM) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-10-19 (M2 Closed-Loop Core: Curriculum DAG, Assistance Escalation, Spaced Retrieval & Misconception Persistence)

### Added
- **Curriculum Knowledge Graph DAG Adapter (`src/lam/domain/curriculum/`):**
  - Pure domain graph models (`ConceptNode`, `PrerequisiteEdge`, `CurriculumGraph`, `EdgeType`).
  - Graph validator (`CurriculumGraphValidator`) with DFS 3-color cycle detection (catching self-loops, 2-node cycles, and multi-hop indirect cycles).
  - Kahn's algorithm topological sorting with deterministic lexicographical tie-breaking for stable curriculum traversal.
  - Ancestor chain resolution and prerequisite mastery blocker evaluation against student mastery maps.
  - Unit test suite `tests/unit/test_curriculum_dag.py` (13/13 passed).
- **9-Level Productive-Struggle Assistance Escalation Ladder (`src/lam/domain/assistance/`):**
  - Pure domain state machine (`AssistanceEngine`) implementing Levels 0 through 8 (Independent $\rightarrow$ Metacognitive Prompt $\rightarrow$ Strategy Hint $\rightarrow$ Scaffolded Substep $\rightarrow$ Alternative Representation $\rightarrow$ Worked Example $\rightarrow$ Interactive Co-solve $\rightarrow$ Direct Direct Instruction $\rightarrow$ Teacher Intervention).
  - Tier 1 safety stop: $\ge 3$ consecutive failures unconditionally escalate to Level 8 (`teacher_intervention`) and halt automated escalation.
  - Repeated failure escalation: 2 consecutive failures escalate directly to Level 5 (`worked_example`).
  - Fading ladder: 2 consecutive assisted successes step scaffolding down toward Level 0.
  - Full reset: single independent success resets assistance level to Level 0.
  - Missing correctness signal maintenance without state alteration.
  - Immutable audit trail recording all transitions, action codes, rationale, and timestamps.
  - Decision Record `D-05` drafted (`PROPOSED`).
  - Unit test suite `tests/unit/test_assistance_escalation.py` (6/6 passed).
- **Spaced Retrieval Forgetting Curve Scheduler (`src/lam/domain/retrieval/`):**
  - Pure domain scheduler (`RetrievalScheduler`) with expanding review intervals ($1\text{d}, 3\text{d}, 7\text{d}, 14\text{d}, 30\text{d}, 60\text{d}$).
  - Assisted attempt conservative scaling: assisted attempts scale interval progression conservatively ($\times 0.5$) relative to independent successes.
  - Exponential retention decay $R(t) = \exp(-\Delta t / S)$.
  - Priority classification (`overdue` for $R(t) < 0.60$, `due_soon` for $0.60 \le R(t) < 0.75$, `maintained` for $R(t) \ge 0.75$).
  - REST endpoint `GET /v1/learners/{learner_id}/reviews` with query parameter filtering (`priority`) and multi-tenant isolation.
  - Decision Record `D-07` drafted (`PROPOSED`).
  - Unit test suite `tests/unit/test_spaced_retrieval.py` (5/5 passed).
  - Integration test suite `tests/integration/test_reviews_api.py` (3/3 passed).
- **Persistent Misconception Storage & Audit History (`src/lam/infrastructure/repositories/diagnosis_repository.py`):**
  - Relational database models `MisconceptionHypothesisModel` and `HypothesisAuditEntryModel` in `src/lam/infrastructure/database/models.py`.
  - Added `state_version` column for optimistic concurrency.
  - Alembic migration `a78f20436d91_add_misconception_persistence_tables.py` verified on PostgreSQL 16.
  - `DiagnosisRepository` with row-level locking (`with_for_update`) and transactional audit entry logging.
  - Integration test suite `tests/integration/test_diagnosis_persistence.py` (4/4 passed).
- **Curriculum DAG Validation REST API (`POST /v1/curriculum/validate`, `POST /v1/curriculum/check-prerequisites`):**
  - Exposed curriculum graph cycle detection, topological sort ordering, and prerequisite blocking resolution over REST API with security middleware.
  - Integration test suite `tests/integration/test_curriculum_api.py` (4/4 passed).
- **Automated Misconception Diagnosis Wiring & Auto-Detection in Ingestion & Recommendations:**
  - Automated transactional hypothesis evaluation in `EventIngestionService`: errors open candidate hypotheses, repeated errors confirm, successes weaken and retire.
  - Automated hypothesis auto-detection in `RecommendationService`: automatically queries `DiagnosisRepository` for active confirmed hypotheses if not supplied by client.
  - Added field aliases (`duration_ms`, `ms`) in `EventIngestRequest` to support Qrie's client outbox contracts cleanly.
  - Integration test suite `tests/integration/test_qrie_contract_and_boundary.py` (5/5 passed).
- **Closed-Loop Synthetic Integration Test (`tests/integration/test_qrie_end_to_end_loop.py`):**
  - Full synthetic lifecycle test proving closed-loop integration: initial error $\rightarrow$ open candidate hypothesis $\rightarrow$ repeated error $\rightarrow$ confirmed hypothesis $\rightarrow$ Tier 3 diagnostic probe recommendation $\rightarrow$ assisted attempt isolation $\rightarrow$ unassisted success $\rightarrow$ hypothesis retirement $\rightarrow$ curriculum progression $\rightarrow$ 3 failures safety stop. (1/1 passed).

### Verification
- Full test suite: **130/130 tests passed in 4.55s**.
- Static type checking: `mypy --strict src/lam tests` passed with **0 issues in 66 source files**.
- Linting and formatting: `ruff check` and `ruff format` clean across **83 files**.

---

## [0.4.0] - 2026-10-19 (Misconception Diagnosis Engine & Hypothesis Lifecycle)

### Added
- **Deterministic Misconception Diagnosis Engine (`src/lam/domain/diagnosis/`):**
  - Pure domain models (`MisconceptionCategory`, `HypothesisStatus`, `MisconceptionHypothesis`, `DiagnosisEvaluationResult`, `HypothesisAuditEntry`).
  - Pure domain diagnosis engine (`DiagnosisEngine`) implementing competing hypothesis tracking and the full lifecycle: `OPEN` candidate $\rightarrow$ `CONFIRMED` $\rightarrow$ `REVISED` / `RETIRED`.
  - Non-negotiable single-error rule: a single incorrect response opens an `OPEN` candidate hypothesis (confidence $0.35$ unassisted, $0.20$ assisted) and **never** confirms it.
  - Confirmation criteria: requires repeated independent supporting observations ($S_{\text{indep}} \ge 2$, confidence $\ge 0.75$).
  - Refutation criteria: contradictory evidence (independent verified successes) weakens confidence ($-0.35$) and transitions to `RETIRED` ($\le 0.15$ or consecutive successes $\ge 2$).
  - Scaffolding discount: assisted errors contribute lower confidence delta ($+0.15$); assisted successes do not disconfirm hypotheses.
  - Evidence gating: unverified, provisional, or non-evaluative (`correctness=None`) observations are strictly rejected.
  - Idempotency & deduplication: replayed event IDs are ignored to prevent artificial inflation.
  - Immutable audit trail recording every state transition, delta, event ID, and timestamp.
  - Decision Record `D-04` drafted (`PROPOSED`).
  - Unit test suite `tests/unit/test_misconception_diagnosis.py` (10/10 passed).
- **Candidate vs Confirmed Misconceptions Gating in Recommendation Engine:**
  - Updated `RecommendationEngine` so Tier 3 (`DIAGNOSTIC_PROBE`) triggers **only** for `CONFIRMED` misconceptions.
  - Candidate hypotheses in `OPEN` or `RETIRED` status do not trigger Tier 3, allowing students to continue regular practice uninterrupted.
  - Updated `RecommendationService` and API schemas (`RecommendationRequest`) to handle `misconception_status`.
  - Added unit and HTTP integration tests verifying that `OPEN` candidate hypotheses yield `independent_practice` while `CONFIRMED` misconceptions yield `diagnostic_probe`.
- **Qrie – LAM Integration Contract Specification (`docs/QRIE_INTEGRATION_CONTRACT.md`):**
  - Formal division of responsibilities between Qrie and LAM.
  - Specification of canonical concept IDs format (`<subject>.<domain>.<topic>[.<subtopic>]`).
  - Complete request/response schemas for `/v1/events` and `/v1/recommendations`.
  - Action code definitions and Qrie execution mappings for all 7 priority tiers and assistance levels.
  - Tenant isolation, JWT security, and pseudonymization requirements.

---

## [0.3.0] - 2026-10-19 (Evidence Eligibility, State Auditability & Recommendation Engine)

### Added
- **Domain Evidence Eligibility Policy (`src/lam/domain/mastery/eligibility.py`):**
  - Authoritatively restricts independent BKT mastery updates to approved, verified sources (`answer_key`, `symbolic_math_check`, `code_tests`, `curriculum_fact_check`, `teacher`).
  - Gating against assisted attempts (Level > 0, hints used > 0, assisted mode, non-independent flag).
  - Explicit exclusion of unverified, provisional, or AI model-graded evidence from independent mastery.
  - Decision Record `D-03` drafted (`PROPOSED`).
- **Domain State Transition Engine (`src/lam/domain/mastery/state_transition.py`):**
  - Decoupled cognitive mastery calculation from database repository into a pure domain function.
  - Initialized concept state prior to $P(L_0)=0.10$ without registering student attempts or false successes ($n_{\text{indep}}=0, U=1.0$).
  - Unit test suite `tests/unit/test_learner_state_transition.py` (7/7 passed).
  - Unit test suite `tests/unit/test_evidence_eligibility.py` (15/15 passed).
- **BKT Parameter Versioning & Auditability:**
  - Added `bkt_parameter_version` column to `learner_states` table via Alembic migration `435e371938d3`.
  - Persisted parameter version (`bkt_v1_baseline`) with learner concept state.
  - Exposed `bkt_parameter_version` on API DTOs.
- **Deterministic Next-Action Recommendation Engine (`src/lam/domain/recommendation/`):**
  - Implemented 7-tier deterministic priority ladder matching Section 10 of Implementation Specification:
    1. Safety & Stop Conditions (`teacher_intervention`)
    2. Blocking Prerequisite Gaps (`prerequisite_remediation`)
    3. Confirmed Misconceptions (`diagnostic_probe`)
    4. Overdue Retrieval (`delayed_retrieval_review`)
    5. Mastery Verification (`mastery_verification`)
    6. Curriculum Progression (`advance_to_next_concept`)
    7. Difficulty Fit / Practice (`worked_example`, `scaffolded_practice`, `independent_practice`)
    Fallback: Safe baseline probe (`diagnostic_probe`, Level 2) on missing state.
  - Application service `src/lam/application/services/recommendation_service.py`.
  - API endpoint `POST /v1/recommendations` with full tenant isolation.
  - Decision Record `D-06` drafted (`PROPOSED`).
  - Unit test suite `tests/unit/test_recommendation_engine.py` (14/14 passed).
  - Integration test suite `tests/integration/test_recommendation_api.py` (5/5 passed).

### Fixed
- **Unverified Evidence Ingestion Vulnerability (Finding A):**
  - Fixed issue where unverified or provisional results could advance independent BKT mastery.
- **Cognitive Logic in Repository (Finding B):**
  - Refactored `StateRepository` to handle strictly database persistence, row-locking, and transactions.
- **Initial Mastery Inconsistency (Finding C):**
  - Fixed initial concept state defaulting to 0.0; now correctly initialized to model prior $0.10$.
- **Parameter Version Traceability (Finding D):**
  - Added schema support and persistence for BKT parameter version.

---

## [0.2.0] - 2026-10-18 (BKT Domain Engine & Production Fail-Closed Configuration)

### Added
- **Pure Python BKT Engine (`src/lam/domain/mastery/bkt.py`):**
  - Implemented Corbett & Anderson (1995) two-step Bayesian Knowledge Tracing engine.
  - Zero framework/database dependencies; fully typed dataclasses for `BKTParameters` and `BKTTransitionResult`.
  - Non-degeneracy validation enforcing positive item discrimination ($P(G) < 0.50$, $P(S) < 0.50$, $P(G) + P(S) < 1.0$).
  - Negative evidence gating: assisted attempts and missing correctness signals bypass BKT updates.
  - Unit tests (`tests/unit/test_bkt.py`) verifying all four D-02 published deterministic test vectors.
- **Operative Epistemic Uncertainty Calculator (`bkt.py::compute_operational_uncertainty`):**
  - Formally implemented $U(n) = \min(1.0, \frac{1}{\sqrt{n_{\text{indep}} + 1}})$.
  - Corrected arithmetic: exactly $n_{\text{indep}} \ge 44$ observations are required for $U \le 0.15$.
- **Fail-Closed Production JWT Configuration (`src/lam/infrastructure/config.py`):**
  - Enforced that production environments reject startup with missing, empty, default, or weak (< 32 chars) JWT secrets.
  - Added unit test suite `tests/unit/test_config_security.py` (5/5 passed).
- **End-to-End Trajectory Ingestion Test (`tests/integration/test_event_ingestion.py`):**
  - Multi-step integration test verifying unassisted correct/incorrect attempts produce exact BKT trajectory.

### Changed
- **Learner State Transition (`src/lam/infrastructure/repositories/state_repository.py`):**
  - Replaced interim fixed-step `+0.2` increments with the pure domain `BKTEngine`.
  - Persisted BKT independent mastery and operational uncertainty on unassisted attempts.

---

## [0.1.2] - 2026-10-18 (Authentication Security Hardening & Concurrency Safety)

### Added
- **Cryptographic JWT Authentication (`src/lam/infrastructure/authentication/jwt.py`):**
  - Cryptographically signed JWT token creation and verification (`PyJWT`).
  - Strict verification of signature, expiration (`exp`), issuer (`iss`), and audience (`aud`).
  - Explicit claims for tenant (`tid`), client subject (`sub`), and roles (`roles`).
  - Configuration settings via `pydantic-settings` in `src/lam/infrastructure/config.py`.
- **PostgreSQL High-Concurrency & Race Verification (`tests/integration/test_postgres_concurrency.py`):**
  - Simultaneous duplicate event submissions race test with 10 concurrent requests (1 ingested, 9 duplicate, 0 internal errors).
  - Concurrent distinct event submissions for same student safely serialized via PostgreSQL row locks (`with_for_update`).
  - Optimistic concurrency control test (`StateVersionConflictError` on stale `state_version`).
  - Atomic transaction rollback test (no partial writes on failed requests).
- **Expanded Security Test Suite (`tests/security/test_tenant_isolation.py`):**
  - Rejection of forged/tampered tokens (401).
  - Rejection of expired tokens (401).
  - Rejection of cross-tenant token mismatch with `X-Tenant-ID` header (403).
  - Rejection of caller-controlled `admin_` prefix escalation attempts.
  - Verification of authorized multi-tenant access for tokens with verified `admin` role claim.

### Fixed
- **Authentication Bypass / Spoofing Vulnerability (P1 Security Fix):**
  - Eliminated caller-controlled token string prefix checking (`admin_`) and unverified client ID derivation.
  - Enforced server-side cryptographic token validation and tenant claim binding.
- **Concurrent Ingestion & State Race Conditions (P2 Concurrency Fix):**
  - Added savepoint retries to `LedgerRepository` to handle race conditions during concurrent duplicate event submissions without raising 500s.
  - Added row-level locking (`with_for_update`) to `StateRepository.record_event_state_transition` ensuring serializable, race-safe learner state updates.

### Changed
- **Mastery Decision Records (`docs/decisions/`):**
  - Clarified statistical distinction in `D-01` and `D-02`: standard BKT yields a point estimate $P(L_t)$, not a parameter credible interval. Defined M1 operational epistemic uncertainty bound based on unassisted observation counts.
  - Explicitly marked candidate parameter status ($P(L_0)=0.10, P(T)=0.20, P(G)=0.20, P(S)=0.10$).

---

## [0.1.1] - 2026-10-18 (M0 Hardening & PostgreSQL Verification)

### Added
- **PostgreSQL Integration Suite (`tests/integration/test_postgres_integration.py`):**
  - Live PostgreSQL 16 container test coverage: schema verification, event ingestion, idempotency deduplication, and multi-tenant isolation.
- **GitHub Actions CI (`.github/workflows/ci.yml`):**
  - Workflow executing `ruff check`, `ruff format`, `mypy --strict`, Alembic migrations on a live PostgreSQL service container, and `pytest`.
- **Decision Records (`docs/decisions/`):**
  - Drafted `docs/decisions/D-01-mastery-policy.md` (Mastery confirmation rules, evidence count, and session separation).
  - Drafted `docs/decisions/D-02-bkt-parameters.md` (Mathematical BKT equations, candidate parameters $P(L_0), P(T), P(G), P(S)$, and deterministic test vectors).
- **Repository Hygiene:**
  - Added `.gitignore` covering bytecode, test caches, local databases (`lam_dev.db`), and environment files.

### Changed
- **Schema Lifecycle Decoupling (`src/lam/main.py`, `src/lam/infrastructure/database/session.py`):**
  - Removed `Base.metadata.create_all()` table creation on service startup.
  - Added non-mutating connection check `verify_db_connection()` executing `SELECT 1`.
  - Enforced Alembic migrations as the exclusive schema lifecycle authority.

### Fixed
- **Git Tracking Cleanup:**
  - Safely untracked committed bytecode caches (`__pycache__`, `*.pyc`) and local SQLite database (`lam_dev.db`) from git index.

---

## [0.1.0] - 2026-10-18 (Initial Foundation Release)

### Added
- **Repository Scaffold & Configuration:**
  - Setup Python 3.11+ project using `pyproject.toml`.
  - Configured `ruff`, `mypy --strict`, and `pytest`.
- **Domain Layer (`src/lam/domain/`):**
  - `LearningEvent` model enforcing the non-coercion rule (missing signals remain `None`).
  - `LearnerConceptState` model separating independent mastery from assisted performance.
- **Persistence Layer (`src/lam/infrastructure/database/`):**
  - SQLAlchemy 2.0 async models for `learning_events` (append-only ledger) and `learner_states`.
  - Database-enforced idempotency via `UniqueConstraint("tenant_id", "event_id")`.
  - Optimistic concurrency control via `state_version` column.
  - Initial Alembic migration `6ed18e85f377`.
  - `LedgerRepository` and `StateRepository` for database access.
- **Application Services (`src/lam/application/`):**
  - `EventIngestionService` coordinating atomic ledger insertion and state updates.
- **API Layer (`src/lam/api/`):**
  - `POST /v1/events` endpoint with server-side tenant authorization.
  - `GET /v1/learners/{learner_id}/state` and `GET /v1/learners/{learner_id}/concepts/{concept_id}/state`.
  - Liveness and readiness probes (`/health/live`, `/health/ready`).
  - Standardized error response contract `ErrorResponse`.
- **Security & Authorization (`src/lam/infrastructure/authentication/`):**
  - Server-side token and `X-Tenant-ID` verification dependency.
  - Cross-tenant data isolation preventing unauthorized access.
