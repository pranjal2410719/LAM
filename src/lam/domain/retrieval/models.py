"""Domain models for Spaced Retrieval Review Scheduling (Milestone M2-03)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewDuePriority(StrEnum):
    """Urgency tier for scheduled spaced retrieval reviews."""

    CRITICAL_OVERDUE = "critical_overdue"  # Retention < 0.50, high forgetting risk
    DUE_FOR_REVIEW = "due_for_review"  # Scheduled date elapsed or retention < 0.80
    UPCOMING = "upcoming"  # Scheduled within next 48 hours
    STABLE = "stable"  # High retention, review distant


@dataclass(frozen=True)
class ScheduledReview:
    """A single concept scheduled for spaced retrieval review."""

    concept_id: str
    concept_mastery: float
    last_reviewed_at: datetime
    scheduled_for: datetime
    interval_days: float
    retention_estimate: float
    is_due: bool
    priority: ReviewDuePriority
    reason_code: str
    consecutive_successes: int
    half_life_days: float


@dataclass(frozen=True)
class RetrievalScheduleResult:
    """Output of evaluating spaced retrieval schedules across a student's concepts."""

    student_id: str
    evaluated_at: datetime
    policy_version: str
    total_concepts_evaluated: int
    reviews_due_count: int
    reviews_due: list[ScheduledReview]
    upcoming_reviews: list[ScheduledReview]
