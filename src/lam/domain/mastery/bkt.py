"""Pure Python Bayesian Knowledge Tracing (BKT) domain engine.

Implements the standard Corbett & Anderson (1995) two-step cognitive model:
1. Posterior calculation given binary observation (Correct / Incorrect).
2. Knowledge transition to the subsequent learning opportunity.

Architectural invariants:
- Zero external dependencies: no FastAPI, no SQLAlchemy, no I/O, no LLM.
- Strictly deterministic: identical inputs yield identical floating-point results.
- Parameter-versioned and auditable.
- Negative evidence gating: assisted attempts and missing signals bypass BKT transitions.
"""

import math
from dataclasses import dataclass

DEFAULT_BKT_VERSION = "bkt_v1_baseline"


@dataclass(frozen=True)
class BKTParameters:
    """Configuration parameters for Bayesian Knowledge Tracing."""

    p_l0: float = 0.10  # Initial knowledge prior
    p_transit: float = 0.20  # Probability of learning transition P(T)
    p_guess: float = 0.20  # Probability of guess P(G)
    p_slip: float = 0.10  # Probability of slip P(S)
    version: str = DEFAULT_BKT_VERSION

    def __post_init__(self) -> None:
        """Validates parameter bounds and non-degeneracy conditions."""
        if not (0.0 < self.p_l0 < 1.0):
            raise ValueError(f"p_l0 must be in open interval (0, 1), got {self.p_l0}")
        if not (0.0 <= self.p_transit < 1.0):
            raise ValueError(
                f"p_transit must be in half-open interval [0, 1), got {self.p_transit}"
            )
        if not (0.0 <= self.p_guess < 0.50):
            raise ValueError(
                f"p_guess must be in [0, 0.50) to preserve item discrimination, got {self.p_guess}"
            )
        if not (0.0 <= self.p_slip < 0.50):
            raise ValueError(
                f"p_slip must be in [0, 0.50) to preserve item discrimination, got {self.p_slip}"
            )
        if self.p_guess + self.p_slip >= 1.0:
            raise ValueError(
                f"Non-degeneracy violation: p_guess + p_slip must be < 1.0, got "
                f"{self.p_guess + self.p_slip}"
            )


@dataclass(frozen=True)
class BKTTransitionResult:
    """Structured result of a BKT knowledge estimation opportunity."""

    prior_mastery: float
    intermediate_posterior: float | None
    posterior_mastery: float
    transition_applied: bool
    reason: str
    parameter_version: str


class BKTEngine:
    """Deterministic Bayesian Knowledge Tracing engine."""

    def __init__(self, params: BKTParameters | None = None):
        self.params = params or BKTParameters()

    def compute_intermediate_posterior(
        self,
        prior: float,
        correctness: bool,
    ) -> float:
        """Step 1: Updates belief based on evidence observation.

        Correct:
            P(L_t | Obs=1) = [P(L_{t-1}) * (1 - S)] / [P(L_{t-1}) * (1 - S) + (1 - P(L_{t-1})) * G]

        Incorrect:
            P(L_t | Obs=0) = [P(L_{t-1}) * S] / [P(L_{t-1}) * S + (1 - P(L_{t-1})) * (1 - G)]
        """
        p_l = min(max(prior, 0.0), 1.0)
        p_s = self.params.p_slip
        p_g = self.params.p_guess

        if correctness:
            numerator = p_l * (1.0 - p_s)
            denominator = numerator + (1.0 - p_l) * p_g
        else:
            numerator = p_l * p_s
            denominator = numerator + (1.0 - p_l) * (1.0 - p_g)

        if denominator <= 0.0:
            return p_l

        posterior = numerator / denominator
        return min(max(posterior, 0.0), 1.0)

    def compute_learning_transition(
        self,
        intermediate_posterior: float,
    ) -> float:
        """Step 2: Accounts for learning transition to subsequent opportunity.

        P(L_{t+1}) = P(L_t | Obs_t) + (1 - P(L_t | Obs_t)) * P(T)
        """
        p_post = min(max(intermediate_posterior, 0.0), 1.0)
        p_t = self.params.p_transit
        transitioned = p_post + (1.0 - p_post) * p_t
        return min(max(transitioned, 0.0), 1.0)

    def update(
        self,
        prior: float | None,
        correctness: bool | None,
        is_assisted: bool = False,
    ) -> BKTTransitionResult:
        """Evaluates an observation and computes deterministic BKT transition if eligible.

        Eligibility Rules (Decision D-02):
        1. If is_assisted == True: Assisted attempts demonstrate scaffolded performance,
           not independent mastery. BKT transition is bypassed.
        2. If correctness is None: Missing or unscored signals bypass BKT transition.
        3. If eligible unassisted attempt: Computes Step 1 posterior then Step 2 transition.
        """
        current_prior = self.params.p_l0 if prior is None else min(max(prior, 0.0), 1.0)

        # Rule 1: Assisted attempt exclusion
        if is_assisted:
            return BKTTransitionResult(
                prior_mastery=current_prior,
                intermediate_posterior=None,
                posterior_mastery=current_prior,
                transition_applied=False,
                reason="assisted_attempt_excluded",
                parameter_version=self.params.version,
            )

        # Rule 2: Missing correctness signal
        if correctness is None:
            return BKTTransitionResult(
                prior_mastery=current_prior,
                intermediate_posterior=None,
                posterior_mastery=current_prior,
                transition_applied=False,
                reason="missing_correctness_signal",
                parameter_version=self.params.version,
            )

        # Rule 3: Eligible unassisted observation
        intermediate = self.compute_intermediate_posterior(
            prior=current_prior,
            correctness=correctness,
        )
        posterior = self.compute_learning_transition(
            intermediate_posterior=intermediate,
        )

        return BKTTransitionResult(
            prior_mastery=current_prior,
            intermediate_posterior=intermediate,
            posterior_mastery=posterior,
            transition_applied=True,
            reason="unassisted_observation_processed",
            parameter_version=self.params.version,
        )


def compute_operational_uncertainty(independent_attempts_count: int) -> float:
    """Calculates the operative evidence sufficiency heuristic for Milestone M1 (Decision D-01).

    Formula:
        U(n) = min(1.0, 1.0 / sqrt(n_indep + 1))

    Note: This is strictly an operational evidence heuristic, not a calibrated parameter
    credible interval. Exactly n_indep >= 44 observations are required to reach U <= 0.15.
    """
    n = max(0, independent_attempts_count)
    return min(1.0, 1.0 / math.sqrt(n + 1))
