# Known Issues and Risks

**Last Updated:** 2026-10-18  

---

## 1. Unresolved Decisions (Pre-Implementation Blockers)

| Decision ID | Area | Severity | Impact | Resolution Criteria | Status |
|:---|:---|:---:|:---|:---|:---:|
| **D-01** | Mastery Policy | **P1 (High)** | Blocks implementation of deterministic mastery transitions in M1. | Approved numeric threshold (e.g., $\ge 0.90$) and evidence counts ($\ge 3$ independent successes across $\ge 2$ sessions). Drafted in `docs/decisions/D-01-mastery-policy.md`. | `PROPOSED` (Awaiting Sign-off) |
| **D-02** | BKT Parameters | **P1 (High)** | Blocks implementation of the BKT engine in M1. | Approved baseline parameter values for $P(L_0), P(T), P(G), P(S)$ and parameter versioning scheme. Drafted in `docs/decisions/D-02-bkt-parameters.md`. | `PROPOSED` (Awaiting Sign-off) |
| **D-04** | Diagnosis Confirmation | **P2 (Medium)** | Blocks automated confirmation of misconception hypotheses in M1. | Approved confidence threshold ($\ge 0.80$) and independent observation requirement. | `PROPOSED` |
| **D-05** | Assistance Ladder Transitions | **P2 (Medium)** | Blocks assistance policy escalation logic in M2. | Approved escalation and reset criteria for Levels 0 through 8. | `PROPOSED` |
| **D-06** | Decision Ranking Priority | **P2 (Medium)** | Blocks deterministic next-action recommendation policy in M1. | Approved priority ordering and tie-breaking algorithms. | `PROPOSED` |

---

## 2. Technical Debt & Operational Risks

| Issue ID | Description | Severity | Impact | Mitigation / Status |
|:---|:---|:---:|:---|:---|
| **TECH-01** | Concurrency verification on PostgreSQL under heavy load. | **P2 (Medium)** | Basic duplicate rejection and isolation are verified on PostgreSQL 16; high-concurrency race condition testing is planned for M1. | Run load test script in M1. Status: `MITIGATED` (PostgreSQL 16 integration tests passing). |
| **TECH-02** | Bearer authentication in M0 uses token prefix matching rather than signed cryptographic JWTs. | **P3 (Low)** | Adequate for M0 test environment; production will require asymmetric JWT verification and key rotation. | Upgrade auth middleware when host service key server integration is implemented. |
| **TECH-03** | Placeholder fixed-step increments in `ingestion_service.py`. | **P2 (Medium)** | Current state increments (`+0.2` on unassisted success) are fixed placeholders, not BKT probability transitions. | BKT engine will replace this placeholder in task `M1-02` once `D-02` is approved. |
