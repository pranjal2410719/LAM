"""Application service for next-action recommendation orchestration."""

from sqlalchemy.ext.asyncio import AsyncSession

from lam.api.schemas.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
)
from lam.domain.diagnosis.models import HypothesisStatus
from lam.domain.recommendation.engine import RecommendationEngine
from lam.domain.recommendation.models import RecommendationContext
from lam.infrastructure.authentication.middleware import SecurityContext
from lam.infrastructure.repositories.diagnosis_repository import DiagnosisRepository
from lam.infrastructure.repositories.state_repository import StateRepository


class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.state_repo = StateRepository(session)
        self.engine = RecommendationEngine()

    async def get_recommendation(
        self, request: RecommendationRequest, sec: SecurityContext
    ) -> RecommendationResponse:
        """Evaluates student state and produces a deterministic learning action recommendation."""
        tenant_id = sec.tenant_id

        # Load persisted learner state for target concept
        state = await self.state_repo.get_concept_state(
            tenant_id=tenant_id,
            student_id=request.student_id,
            concept_id=request.concept_id,
        )

        context: RecommendationContext | None = None
        if state is not None:
            # Override prerequisite readiness if explicitly provided in request
            prereq_readiness = (
                request.prerequisite_readiness
                if request.prerequisite_readiness is not None
                else state.prerequisite_readiness
            )

            # Auto-detect active/confirmed misconception from repository if not supplied in request
            active_misconception_id = request.active_misconception_id
            misconception_status = request.misconception_status
            if active_misconception_id is None:
                diag_repo = DiagnosisRepository(self.session)
                active_hypos = await diag_repo.get_hypotheses(
                    tenant_id=tenant_id,
                    student_id=request.student_id,
                    concept_id=request.concept_id,
                    active_only=True,
                )
                confirmed = next(
                    (h for h in active_hypos if h.status == HypothesisStatus.CONFIRMED),
                    None,
                )
                if confirmed is not None:
                    active_misconception_id = confirmed.hypothesis_id
                    misconception_status = confirmed.status.value
                elif active_hypos:
                    active_misconception_id = active_hypos[0].hypothesis_id
                    misconception_status = active_hypos[0].status.value

            context = RecommendationContext(
                concept_id=state.concept_id,
                concept_mastery=state.concept_mastery,
                independent_mastery=state.independent_mastery,
                assisted_performance=state.assisted_performance,
                uncertainty=state.uncertainty,
                total_events_count=state.total_events_count,
                independent_attempts_count=state.independent_attempts_count,
                assisted_attempts_count=state.assisted_attempts_count,
                consecutive_independent_successes=state.consecutive_independent_successes,
                consecutive_failures=request.consecutive_failures,
                prerequisite_readiness=prereq_readiness,
                retention_strength=state.retention_strength,
                active_misconception_id=active_misconception_id,
                misconception_status=misconception_status,
                prerequisite_concept_id=request.prerequisite_concept_id,
                state_version=state.state_version,
            )

        decision = self.engine.evaluate(
            context=context,
            target_concept_id=request.concept_id,
            custom_metadata=request.context_metadata,
        )

        return RecommendationResponse(
            action_type=decision.action_type.value,
            target_concept_id=decision.target_concept_id,
            assistance_level=decision.assistance_level,
            priority_tier=decision.priority_tier.value,
            reason_code=decision.reason_code,
            suggested_strategy=decision.suggested_strategy,
            rationale=decision.rationale,
            policy_version=decision.policy_version,
            safe_fallback=decision.safe_fallback,
            uncertainty=decision.uncertainty,
            relevant_learner_state_version=decision.relevant_learner_state_version,
            metadata=decision.metadata,
        )
