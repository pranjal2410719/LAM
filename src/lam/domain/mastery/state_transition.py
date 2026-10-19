"""Pure domain state transition logic for Learner Concept State.

Decouples cognitive mastery computation, evidence eligibility verification,
and attempt counting from database persistence and framework concerns.
"""

from datetime import UTC, datetime

from lam.domain.events.models import LearningEvent
from lam.domain.learner_state.models import LearnerConceptState
from lam.domain.mastery.bkt import (
    BKTEngine,
    BKTTransitionResult,
    compute_operational_uncertainty,
)
from lam.domain.mastery.eligibility import (
    EvidenceEligibilityResult,
    evaluate_evidence_eligibility,
)


def apply_learning_event_transition(
    current_state: LearnerConceptState | None,
    event: LearningEvent,
    concept_id: str,
    bkt_engine: BKTEngine | None = None,
    transition_time: datetime | None = None,
) -> tuple[LearnerConceptState, EvidenceEligibilityResult, BKTTransitionResult | None]:
    """Applies a learning event to a learner concept state deterministically.

    Invariants:
    1. If current_state is None: initializes prior to P(L_0) (0.10). An initial state
       prior does not count as a student attempt or a success.
    2. If event is ASSISTED: updates assisted_performance and assisted_attempts_count,
       leaving independent_mastery and independent_attempts_count strictly unchanged.
    3. If event is PROVISIONAL, UNVERIFIED, or MISSING CORRECTNESS: recorded in ledger
       and increments total_events_count, but leaves BKT mastery and attempt counts unchanged.
    4. If event is ELIGIBLE unassisted observation: executes Corbett & Anderson (1995)
       two-step transition and updates operational uncertainty U(n).
    """
    bkt = bkt_engine or BKTEngine()
    eligibility = evaluate_evidence_eligibility(event)
    now = transition_time or datetime.now(UTC)

    bkt_result: BKTTransitionResult | None = None

    if current_state is None:
        # Initializing brand new concept state
        p_l0 = bkt.params.p_l0
        indep_mastery = p_l0
        assisted_perf = 0.0
        indep_count = 0
        assisted_count = 0
        consec_success = 0
        param_version = bkt.params.version

        if eligibility.is_assisted:
            assisted_count = 1
            if event.correctness is True:
                assisted_perf = 0.1
        elif eligibility.is_eligible_for_bkt:
            indep_count = 1
            if event.correctness is True:
                consec_success = 1
            bkt_result = bkt.update(
                prior=p_l0,
                correctness=event.correctness,
                is_assisted=False,
            )
            indep_mastery = bkt_result.posterior_mastery
            param_version = bkt_result.parameter_version

        uncertainty = compute_operational_uncertainty(indep_count)

        new_state = LearnerConceptState(
            tenant_id=event.tenant_id,
            student_id=event.student_id,
            concept_id=concept_id,
            concept_mastery=indep_mastery,
            independent_mastery=indep_mastery,
            assisted_performance=assisted_perf,
            uncertainty=uncertainty,
            total_events_count=1,
            independent_attempts_count=indep_count,
            assisted_attempts_count=assisted_count,
            consecutive_independent_successes=consec_success,
            prerequisite_readiness=None,
            retention_strength=None,
            last_practiced_at=event.timestamp,
            state_version=1,
            last_event_id=event.event_id,
            bkt_parameter_version=param_version,
            created_at=now,
            updated_at=now,
        )
        return new_state, eligibility, bkt_result

    # Updating existing concept state
    new_total_events = current_state.total_events_count + 1
    new_version = current_state.state_version + 1
    new_indep_mastery = current_state.independent_mastery
    new_assisted_perf = current_state.assisted_performance
    new_indep_count = current_state.independent_attempts_count
    new_assisted_count = current_state.assisted_attempts_count
    new_consec_successes = current_state.consecutive_independent_successes
    param_version = current_state.bkt_parameter_version or bkt.params.version

    if eligibility.is_assisted:
        new_assisted_count += 1
        if event.correctness is True:
            new_assisted_perf = min(1.0, current_state.assisted_performance + 0.1)
    elif eligibility.is_eligible_for_bkt:
        new_indep_count += 1
        if event.correctness is True:
            new_consec_successes += 1
        else:
            new_consec_successes = 0

        prior = current_state.independent_mastery
        bkt_result = bkt.update(
            prior=prior,
            correctness=event.correctness,
            is_assisted=False,
        )
        new_indep_mastery = bkt_result.posterior_mastery
        param_version = bkt_result.parameter_version

    new_uncertainty = compute_operational_uncertainty(new_indep_count)

    updated_state = LearnerConceptState(
        tenant_id=current_state.tenant_id,
        student_id=current_state.student_id,
        concept_id=concept_id,
        concept_mastery=new_indep_mastery,
        independent_mastery=new_indep_mastery,
        assisted_performance=new_assisted_perf,
        uncertainty=new_uncertainty,
        total_events_count=new_total_events,
        independent_attempts_count=new_indep_count,
        assisted_attempts_count=new_assisted_count,
        consecutive_independent_successes=new_consec_successes,
        prerequisite_readiness=current_state.prerequisite_readiness,
        retention_strength=current_state.retention_strength,
        last_practiced_at=event.timestamp,
        state_version=new_version,
        last_event_id=event.event_id,
        bkt_parameter_version=param_version,
        created_at=current_state.created_at,
        updated_at=now,
    )
    return updated_state, eligibility, bkt_result
