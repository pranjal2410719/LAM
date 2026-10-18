# Known Issues and Risks

**Last Updated:** 2026-10-18  

---

## 1. Unresolved Decisions (Pre-Implementation Blockers)

| Decision ID | Area | Severity | Impact | Resolution Criteria | Status |
|:---|:---|:---:|:---|:---|:---:|
| **D-01** | Mastery Policy & Uncertainty Definition | **P1 (High)** | Blocks implementation of deterministic mastery transitions in M1. | Approved numeric threshold (e.g., $\ge 0.90$) and evidence counts ($\ge 3$ independent successes across $\ge 2$ sessions). Updated with Section 3.3 defining operational epistemic uncertainty vs point-estimate BKT. Drafted in `docs/decisions/D-01-mastery-policy.md`. | `PROPOSED` (Awaiting Sign-off) |
| **D-02** | BKT Parameters & Versioning | **P1 (High)** | Blocks implementation of the BKT engine in M1. | Approved baseline candidate parameter values for $P(L_0), P(T), P(G), P(S)$ and parameter versioning scheme (`bkt_v1_baseline`). Drafted in `docs/decisions/D-02-bkt-parameters.md`. | `PROPOSED` (Awaiting Sign-off) |
| **D-04** | Diagnosis Confirmation | **P2 (Medium)** | Blocks automated confirmation of misconception hypotheses in M1. | Approved confidence threshold ($\ge 0.80$) and independent observation requirement. | `PROPOSED` |
| **D-05** | Assistance Ladder Transitions | **P2 (Medium)** | Blocks assistance policy escalation logic in M2. | Approved escalation and reset criteria for Levels 0 through 8. | `PROPOSED` |
| **D-06** | Decision Ranking Priority | **P2 (Medium)** | Blocks deterministic next-action recommendation policy in M1. | Approved priority ordering and tie-breaking algorithms. | `PROPOSED` |

---

## 2. Technical Debt & Operational Risks

| Issue ID | Description | Severity | Impact | Mitigation / Status |
|:---|:---|:---:|:---|:---|
| **TECH-01** | High-concurrency race condition safety on PostgreSQL. | **P2 (Medium)** | Potential for duplicate event insertion races or lost state updates under simultaneous requests. | **RESOLVED:** Added database savepoints in `LedgerRepository` for concurrent duplicate insertion handling, and row-level locking (`with_for_update`) in `StateRepository`. Verified by 4/4 passing tests in `tests/integration/test_postgres_concurrency.py`. |
| **TECH-02** | Authentication boundary previously trusted caller-controlled identity/prefixes. | **P1 (High)** | Callers could supply arbitrary Bearer strings, spoof `X-Tenant-ID`, or prefix with `admin_`. | **RESOLVED:** Implemented cryptographic JWT authentication (`PyJWT`) with strict signature, expiration, issuer, audience, and tenant claim verification. Verified by 7/7 security tests in `tests/security/test_tenant_isolation.py`. |
| **TECH-03** | Placeholder fixed-step increments in `ingestion_service.py`. | **P2 (Medium)** | Current state increments (`+0.2` on unassisted success) are fixed placeholders, not BKT probability transitions. | BKT engine will replace this placeholder in task `M1-02` once `D-01` and `D-02` are formally signed off. |
