"""Unit tests for event domain models and non-coercion validation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lam.domain.events.models import EventType, LearningEvent


def test_valid_learning_event() -> None:
    event = LearningEvent(
        event_id="evt_001",
        tenant_id="tenant_alpha",
        student_id="student_123",
        session_id="sess_abc",
        concept_ids=["fractions.addition"],
        item_id="q_101",
        timestamp=datetime.now(UTC),
        event_type=EventType.ATTEMPT,
        correctness=True,
        attempt_number=1,
        assistance_level=0,
    )
    assert event.event_id == "evt_001"
    assert event.correctness is True
    assert event.assistance_level == 0


def test_non_coercion_of_missing_signals() -> None:
    """Non-negotiable rule: Missing or unknown values MUST remain None and never

    coerced to False or 0.
    """
    event = LearningEvent(
        event_id="evt_002",
        tenant_id="tenant_alpha",
        student_id="student_123",
        session_id="sess_abc",
        concept_ids=["fractions.addition"],
        item_id="q_102",
        timestamp=datetime.now(UTC),
        event_type=EventType.HINT,
        correctness=None,  # No score for a hint event
        difficulty=None,
    )
    assert event.correctness is None
    assert event.difficulty is None
    assert event.assistance_level is None


def test_rejection_of_invalid_assistance_level() -> None:
    """Assistance level must be bounded between 0 and 8."""
    with pytest.raises(ValidationError):
        LearningEvent(
            event_id="evt_003",
            tenant_id="tenant_alpha",
            student_id="student_123",
            session_id="sess_abc",
            concept_ids=["fractions.addition"],
            item_id="q_103",
            timestamp=datetime.now(UTC),
            event_type=EventType.ATTEMPT,
            assistance_level=9,  # Invalid: max is 8
        )
