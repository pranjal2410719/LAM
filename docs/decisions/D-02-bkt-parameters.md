# Decision Record: D-02 — Bayesian Knowledge Tracing (BKT) Baseline Parameterization

**Status:** `PROPOSED` (Awaiting Formal Pedagogical & Technical Sign-Off)  
**Date:** 2026-10-18  
**Owner:** Technical Owner & ML Lead  
**Applies to:** Milestone M1 (Domain Mastery Engine: `src/lam/domain/mastery/`)  

---

## 1. Context & Problem Statement

To replace placeholder fixed-step increments (`+0.2` on success) with a principled cognitive model, LAM requires a standard knowledge tracing foundation for Milestone M1.
Bayesian Knowledge Tracing (Corbett & Anderson, 1995) models the probability that a student knows a concept based on interaction sequences.

---

## 2. Mathematical Equations

For any concept, knowledge state is represented as a point probability $P(L_t) \in [0, 1]$.

### Step 1: Posterior Calculation upon Observation $Obs_t \in \{Correct, Incorrect\}$
* **If response is Correct ($Obs_t = 1$):**
  $$P(L_t \mid Obs=1) = \frac{P(L_{t-1}) \cdot (1 - P(S))}{P(L_{t-1}) \cdot (1 - P(S)) + (1 - P(L_{t-1})) \cdot P(G)}$$

* **If response is Incorrect ($Obs_t = 0$):**
  $$P(L_t \mid Obs=0) = \frac{P(L_{t-1}) \cdot P(S)}{P(L_{t-1}) \cdot P(S) + (1 - P(L_{t-1})) \cdot (1 - P(G))}$$

### Step 2: Learning Transition to Next Opportunity
$$P(L_{t+1}) = P(L_t \mid Obs_t) + (1 - P(L_t \mid Obs_t)) \cdot P(T)$$

### 2.1 Point-Estimate Semantics & Epistemic Uncertainty
Note that standard BKT computes a scalar point estimate $P(L_t = 1)$. It does **not** estimate parameter uncertainty or output a Bayesian credible interval. As established in Decision Record [D-01](D-01-mastery-policy.md#33-operative-uncertainty-metric-for-milestone-m1), the uncertainty metric in Milestone M1 is treated as an operational epistemic evidence bound based on unassisted observation count, pending full posterior inference in Milestone M3.

---

## 3. Candidate Baseline Parameters (Proposed Default)

| Parameter | Symbol | Meaning | Candidate Baseline Value | Allowable Range | Mathematical Constraint |
|:---|:---:|:---|:---:|:---:|:---|
| **Initial Knowledge** | $P(L_0)$ | Prior probability learner knows concept before first item | **0.10** | $[0.01, 0.40]$ | $0 < P(L_0) < 1.0$ |
| **Transit Probability** | $P(T)$ | Probability of acquiring knowledge during an attempt | **0.20** | $[0.05, 0.40]$ | $0 \le P(T) < 1.0$ |
| **Guess Probability** | $P(G)$ | Probability of answering correctly despite not knowing | **0.20** | $[0.05, 0.35]$ | $0 \le P(G) < 0.50$ |
| **Slip Probability** | $P(S)$ | Probability of making an error despite knowing | **0.10** | $[0.01, 0.20]$ | $0 \le P(S) < 0.50$ |

> [!IMPORTANT]
> **Non-Degeneracy Condition:** $P(G) + P(S) < 1.0$ is strictly required to guarantee positive item discrimination (i.e. the probability of answering correctly given mastery must exceed the probability of answering correctly without mastery).
>
> **Candidate Status:** These values are starting engineering baselines derived from standard educational data mining literature. They are **not** yet validated against Qrie student production data. They must remain marked `PROPOSED` until empirically evaluated on baseline datasets in Milestone M3.

---

## 4. Evidence Eligibility Rules

1. **Unassisted attempts only:** BKT probability updates apply exclusively to unassisted observations (`assistance_level == 0` and `hints_used == 0`).
2. **Assisted attempts excluded:** Attempts with scaffolding (Levels 1 to 8) update `assisted_performance` counters only and bypass the BKT transition.
3. **Missing signals:** If correctness is `None` (e.g. non-scored hint view), no BKT transition is computed.
4. **Parameter Versioning:** All learner state updates must record the parameter version identifier (e.g. `bkt_v1_baseline`).

---

## 5. Deterministic Test Vectors for Verification

| Step | Prior $P(L)$ | Observation | Intermediate $P(L \mid Obs)$ | Posterior $P(L_{t+1})$ |
|:---:|:---:|:---:|:---:|:---:|
| 0 | - | Initial State | - | **0.1000** |
| 1 | 0.1000 | Correct ($1$) | $\frac{0.10 \times 0.90}{(0.10 \times 0.90) + (0.90 \times 0.20)} = 0.3333$ | $0.3333 + (0.6667 \times 0.20) = \mathbf{0.4667}$ |
| 2 | 0.4667 | Incorrect ($0$) | $\frac{0.4667 \times 0.10}{(0.4667 \times 0.10) + (0.5333 \times 0.80)} = 0.0986$ | $0.0986 + (0.9014 \times 0.20) = \mathbf{0.2789}$ |
| 3 | 0.2789 | Correct ($1$) | $\frac{0.2789 \times 0.90}{(0.2789 \times 0.90) + (0.7211 \times 0.20)} = 0.6351$ | $0.6351 + (0.3649 \times 0.20) = \mathbf{0.7081}$ |
