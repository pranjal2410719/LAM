# Known Issues and Risks

**Last Updated:** 2026-10-18  

---

## 1. Unresolved Decisions (Pre-Implementation Blockers)

| Decision ID | Area | Severity | Impact | Resolution Criteria | Status |
|:---|:---|:---:|:---|:---|:---:|
| **D-01** | Mastery Policy & Uncertainty Definition | **P1 (High)** | Governs formal graduation to `CONFIRMED_MASTERY` in M1/M2. | Approved numeric threshold ($\ge 0.90$), evidence counts ($\ge 3$ independent successes across $\ge 2$ sessions), and operative uncertainty bound $U \le 0.15$ ($n_{\text{indep}} \ge 44$). Drafted in `docs/decisions/D-01-mastery-policy.md`. | `PROPOSED` (Awaiting Formal Sign-off) |
| **D-02** | BKT Parameters & Versioning | **P1 (High)** | Governs baseline cognitive model parameterization. | Formal approval of baseline parameters $P(L_0)=0.10, P(T)=0.20, P(G)=0.20, P(S)=0.10$ and version `bkt_v1_baseline`. Domain engine implemented. Drafted in `docs/decisions/D-02-bkt-parameters.md`. | `PROPOSED` (Awaiting Formal Sign-off) |
| **D-04** | Diagnosis Confirmation | **P2 (Medium)** | Blocks automated confirmation of misconception hypotheses in M1. | Approved confidence threshold ($\ge 0.80$) and independent observation requirement. | `PROPOSED` |
| **D-05** | Assistance Ladder Transitions | **P2 (Medium)** | Blocks assistance policy escalation logic in M2. | Approved escalation and reset criteria for Levels 0 through 8. | `PROPOSED` |
| **D-06** | Decision Ranking Priority | **P2 (Medium)** | Blocks deterministic next-action recommendation policy in M1. | Approved priority ordering and tie-breaking algorithms. | `PROPOSED` |

---

## 2. Technical Debt & Operational Risks

| Issue ID | Description | Severity | Impact | Mitigation / Status |
|:---|:---|:---:|:---|:---|
| **TECH-01** | High-concurrency race condition safety on PostgreSQL. | **P2 (Medium)** | Potential for duplicate event insertion races or lost state updates under simultaneous requests. | **RESOLVED:** Added database savepoints in `LedgerRepository` for concurrent duplicate insertion handling, and row-level locking (`with_for_update`) in `StateRepository`. Verified by 4/4 passing tests in `tests/integration/test_postgres_concurrency.py`. |
| **TECH-02** | Authentication boundary previously trusted caller-controlled identity/prefixes. | **P1 (High)** | Callers could supply arbitrary Bearer strings, spoof `X-Tenant-ID`, or prefix with `admin_`. | **RESOLVED:** Implemented cryptographic JWT authentication (`PyJWT`) with strict signature, expiration, issuer, audience, and tenant claim verification. Verified by 7/7 security tests in `tests/security/test_tenant_isolation.py`. |
| **TECH-03** | Placeholder fixed-step increments in `ingestion_service.py`. | **P2 (Medium)** | Prior state increments (`+0.2` on unassisted success) were fixed placeholders, not BKT probability transitions. | **RESOLVED:** Implemented pure Python Corbett & Anderson BKT engine (`src/lam/domain/mastery/bkt.py`) and integrated into state repository. Verified by 7 BKT unit tests and end-to-end multi-step trajectory integration test. |
| **TECH-04** | Silent adoption of insecure default JWT secret in production. | **P1 (High)** | Misconfigured production deployments could default to predictable development secrets. | **RESOLVED:** Implemented fail-closed `Settings.validate_production_security()` rejecting missing, default, or weak (< 32 chars) secrets in production. Verified by 5 unit tests in `tests/unit/test_config_security.py`. |
| **TECH-05** | Baseline BKT parameters are derived from EDM literature, not student dataset evaluation. | **P2 (Medium)** | True student performance distributions in Qrie may exhibit different guess/slip rates. | Parameters explicitly tagged as candidate baselines (`bkt_v1_baseline`). Empirical parameter fitting and validation scheduled for Milestone M3. |
