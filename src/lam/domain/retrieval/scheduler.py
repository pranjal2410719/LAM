"""Deterministic Spaced Retrieval Scheduler (Milestone M2-03).

Implements candidate baseline expanding-interval retrieval scheduling and
exponential retention decay estimation: R(t) = exp(-delta_t / S).
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from lam.domain.learner_state.models import LearnerConceptState
from lam.domain.retrieval.models import (
    RetrievalScheduleResult,
    ReviewDuePriority,
    ScheduledReview,
)

# Baseline expanding intervals in days for unassisted successes:
# Index represents consecutive unassisted successes (0->1d, 1->3d, 2->7d, 3->14d, 4->30d, 5+->60d)
INTERVAL_LADDER_DAYS: tuple[float, ...] = (1.0, 3.0, 7.0, 14.0, 30.0, 60.0)


class SpacedRetrievalScheduler:
    """Calculates review schedules and memory retention decay for learner concepts."""

    def __init__(self, policy_version: str = "retrieval_ladder_v1") -> None:
        self.policy_version = policy_version

    def compute_interval_days(
        self,
        consecutive_independent_successes: int,
        assisted_attempts_count: int,
        independent_attempts_count: int,
    ) -> float:
        """Determines scheduled interval in days based on performance history."""
        # If learner has no independent successes, schedule conservative 1-day interval
        if consecutive_independent_successes <= 0:
            return 1.0

        idx = min(consecutive_independent_successes - 1, len(INTERVAL_LADDER_DAYS) - 1)
        base_interval = INTERVAL_LADDER_DAYS[idx]

        # If assisted attempts dominate, scale interval conservatively
        if assisted_attempts_count > independent_attempts_count and base_interval > 1.0:
            return max(1.0, base_interval * 0.70)

        return base_interval

    def estimate_retention(self, elapsed_days: float, interval_days: float) -> float:
        """Estimates retention probability using exponential forgetting model.

        R(t) = exp(-delta_t / S), where S = interval_days / ln(1 / 0.85).
        At delta_t == interval_days, retention is calibrated to 0.85 (target review threshold).
        """
        if elapsed_days <= 0.0:
            return 1.0

        # Half-life / stability parameter calibrated so R(interval) = 0.85
        # 0.85 = exp(-interval / S) => S = -interval / ln(0.85) ≈ interval * 6.16
        stability = interval_days * 6.159
        retention = math.exp(-elapsed_days / max(0.1, stability))
        return max(0.0, min(1.0, retention))

    def evaluate_schedules(
        self,
        student_id: str,
        concept_states: Sequence[LearnerConceptState],
        reference_time: datetime | None = None,
    ) -> RetrievalScheduleResult:
        """Evaluates spaced retrieval needs across all concepts for a student."""
        now = reference_time or datetime.now(UTC)

        reviews_due: list[ScheduledReview] = []
        upcoming_reviews: list[ScheduledReview] = []

        for state in concept_states:
            # Concepts with 0 attempts are in learning phase, not retrieval review
            if state.total_events_count == 0:
                continue

            last_reviewed = state.last_practiced_at or state.created_at
            # Make sure timezone matches
            if last_reviewed.tzinfo is None:
                last_reviewed = last_reviewed.replace(tzinfo=UTC)

            elapsed = max(0.0, (now - last_reviewed).total_seconds() / 86400.0)

            interval_days = self.compute_interval_days(
                consecutive_independent_successes=state.consecutive_independent_successes,
                assisted_attempts_count=state.assisted_attempts_count,
                independent_attempts_count=state.independent_attempts_count,
            )

            scheduled_for = last_reviewed + timedelta(days=interval_days)
            retention = self.estimate_retention(elapsed, interval_days)
            half_life = interval_days * 6.159

            is_due = (now >= scheduled_for) or (retention < 0.80)

            if retention < 0.50 or elapsed >= (2.0 * interval_days):
                priority = ReviewDuePriority.CRITICAL_OVERDUE
                reason = "memory_retention_critical_decay"
                is_due = True
            elif is_due:
                priority = ReviewDuePriority.DUE_FOR_REVIEW
                reason = "scheduled_retrieval_window_open"
            elif (scheduled_for - now).total_seconds() <= 172800.0:  # 48 hours
                priority = ReviewDuePriority.UPCOMING
                reason = "review_due_soon"
            else:
                priority = ReviewDuePriority.STABLE
                reason = "memory_trace_stable"

            item = ScheduledReview(
                concept_id=state.concept_id,
                concept_mastery=state.concept_mastery,
                last_reviewed_at=last_reviewed,
                scheduled_for=scheduled_for,
                interval_days=interval_days,
                retention_estimate=round(retention, 4),
                is_due=is_due,
                priority=priority,
                reason_code=reason,
                consecutive_successes=state.consecutive_independent_successes,
                half_life_days=round(half_life, 2),
            )

            if is_due:
                reviews_due.append(item)
            else:
                upcoming_reviews.append(item)

        # Sort reviews due by priority (CRITICAL first) then ascending retention
        reviews_due.sort(
            key=lambda r: (
                0 if r.priority == ReviewDuePriority.CRITICAL_OVERDUE else 1,
                r.retention_estimate,
            )
        )

        upcoming_reviews.sort(key=lambda r: r.scheduled_for)

        return RetrievalScheduleResult(
            student_id=student_id,
            evaluated_at=now,
            policy_version=self.policy_version,
            total_concepts_evaluated=len(concept_states),
            reviews_due_count=len(reviews_due),
            reviews_due=reviews_due,
            upcoming_reviews=upcoming_reviews,
        )
