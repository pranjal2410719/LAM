"""Deterministic 9-Level Assistance Escalation State Machine (Milestone M2-02).

Implements the scaffolding progression and fading ladder:
Level 0 (Independent) -> Level 1 (Metacognitive) -> Level 2 (Hint) ->
Level 3 (Sub-step) -> Level 4 (Breakdown) -> Level 5 (Worked Example) ->
Level 6 (Guided Walkthrough) -> Level 7 (Direct Instruction) -> Level 8 (Teacher Escalation).
"""

from lam.domain.assistance.models import (
    AssistanceAuditEntry,
    AssistanceLevel,
    AssistanceState,
    AssistanceTransitionResult,
    TransitionAction,
)
from lam.domain.events.models import AssessmentMode, LearningEvent


class AssistanceEngine:
    """Evaluates student performance to adapt instructional assistance levels."""

    def __init__(self, policy_version: str = "assistance_ladder_v1") -> None:
        self.policy_version = policy_version

    def evaluate(
        self,
        state: AssistanceState,
        event: LearningEvent,
    ) -> AssistanceTransitionResult:
        """Evaluates an observation and deterministically transitions the assistance level."""
        prev_level = state.current_level
        event_id = event.event_id

        # 1. Missing or non-evaluative signal -> strictly MAINTAIN state
        if event.correctness is None:
            audit = AssistanceAuditEntry(
                event_id=event_id,
                from_level=prev_level,
                to_level=prev_level,
                action=TransitionAction.MAINTAIN,
                reason_code="non_evaluative_event_maintained",
                rationale=(
                    "Observation does not carry correctness evaluation. "
                    "Assistance level maintained."
                ),
            )
            state.audit_trail.append(audit)
            return AssistanceTransitionResult(
                previous_level=prev_level,
                new_level=prev_level,
                action=TransitionAction.MAINTAIN,
                consecutive_failures=state.consecutive_failures,
                reason_code=audit.reason_code,
                rationale=audit.rationale,
                policy_version=self.policy_version,
                audit_entry=audit,
            )

        # Determine whether attempt was assisted
        is_assisted = (
            (event.assistance_level is not None and event.assistance_level > 0)
            or (event.hints_used is not None and event.hints_used > 0)
            or (event.assessment_mode == AssessmentMode.ASSISTED)
            or (event.provenance is not None and event.provenance.independently_produced is False)
        )

        if is_assisted:
            state.total_assisted_attempts += 1
        else:
            state.total_independent_attempts += 1

        # 2. Student failure -> Deterministic Escalation Ladder
        if event.correctness is False:
            state.consecutive_failures += 1
            state.consecutive_assisted_successes = 0
            state.consecutive_independent_successes = 0

            # Tier 1 Safety Stop Priority: 3 or more consecutive failures
            if state.consecutive_failures >= 3:
                new_level = AssistanceLevel.LEVEL_8_TEACHER_INTERVENTION
                action = TransitionAction.SAFETY_STOP
                reason = "persistent_failure_safety_stop"
                rationale = (
                    f"Student has failed {state.consecutive_failures} consecutive attempts. "
                    "Halting automated difficulty escalation; requiring human teacher intervention."
                )
            elif state.consecutive_failures == 2:
                # Two consecutive failures: escalate directly to Worked Example
                new_level = AssistanceLevel.LEVEL_5_WORKED_EXAMPLE
                action = TransitionAction.ESCALATE
                reason = "two_failures_escalate_to_worked_example"
                rationale = (
                    "Repeated failure detected. Escalating to Level 5 worked example "
                    "for conceptual modeling."
                )
            else:
                # First failure: step up scaffolding based on current level
                if prev_level == AssistanceLevel.LEVEL_0_INDEPENDENT:
                    new_level = AssistanceLevel.LEVEL_2_STRATEGY_HINT
                elif prev_level == AssistanceLevel.LEVEL_1_METACOGNITIVE_PROMPT:
                    new_level = AssistanceLevel.LEVEL_2_STRATEGY_HINT
                elif prev_level == AssistanceLevel.LEVEL_2_STRATEGY_HINT:
                    new_level = AssistanceLevel.LEVEL_3_SCAFFOLDED_SUBSTEP
                else:
                    new_level = AssistanceLevel(min(7, int(prev_level) + 1))
                action = TransitionAction.ESCALATE
                reason = "initial_failure_scaffolding_escalation"
                rationale = (
                    f"Initial struggle observed. Escalating assistance from Level "
                    f"{int(prev_level)} to Level {int(new_level)}."
                )

        # 3. Student success -> Scaffolding Fading or Independent Reset
        else:
            state.consecutive_failures = 0

            if not is_assisted:
                # Independent verified success
                state.consecutive_independent_successes += 1
                state.consecutive_assisted_successes = 0

                if prev_level == AssistanceLevel.LEVEL_0_INDEPENDENT:
                    new_level = AssistanceLevel.LEVEL_0_INDEPENDENT
                    action = TransitionAction.MAINTAIN
                    reason = "independent_fluency_maintained"
                    rationale = "Student demonstrated unassisted fluency. Maintaining Level 0."
                else:
                    # Reset to independent practice
                    new_level = AssistanceLevel.LEVEL_0_INDEPENDENT
                    action = TransitionAction.RESET
                    reason = "independent_success_full_reset"
                    rationale = "Student succeeded independently. Resetting assistance to Level 0."
            else:
                # Assisted success: demonstrate mastery with help, fade gradually
                state.consecutive_assisted_successes += 1
                state.consecutive_independent_successes = 0

                if state.consecutive_assisted_successes >= 2:
                    # Two consecutive assisted successes: fade scaffolding downward
                    action = TransitionAction.DE_ESCALATE
                    reason = "fading_scaffolding_after_consecutive_successes"
                    if prev_level >= AssistanceLevel.LEVEL_6_GUIDED_WALKTHROUGH:
                        new_level = AssistanceLevel.LEVEL_5_WORKED_EXAMPLE
                    elif prev_level == AssistanceLevel.LEVEL_5_WORKED_EXAMPLE:
                        new_level = AssistanceLevel.LEVEL_3_SCAFFOLDED_SUBSTEP
                    elif prev_level in (
                        AssistanceLevel.LEVEL_4_CONCEPTUAL_BREAKDOWN,
                        AssistanceLevel.LEVEL_3_SCAFFOLDED_SUBSTEP,
                    ):
                        new_level = AssistanceLevel.LEVEL_2_STRATEGY_HINT
                    elif prev_level == AssistanceLevel.LEVEL_2_STRATEGY_HINT:
                        new_level = AssistanceLevel.LEVEL_1_METACOGNITIVE_PROMPT
                    else:
                        new_level = AssistanceLevel.LEVEL_0_INDEPENDENT
                    rationale = (
                        f"Student achieved {state.consecutive_assisted_successes} consecutive "
                        f"assisted successes. Fading scaffolding from Level {int(prev_level)} "
                        f"down to Level {int(new_level)}."
                    )
                else:
                    # Single assisted success: maintain current level to consolidate
                    new_level = prev_level
                    action = TransitionAction.MAINTAIN
                    reason = "consolidate_assisted_performance"
                    rationale = (
                        f"Student succeeded with assistance. Consolidating Level "
                        f"{int(prev_level)} before fading."
                    )

        state.current_level = new_level
        state.state_version += 1

        audit = AssistanceAuditEntry(
            event_id=event_id,
            from_level=prev_level,
            to_level=new_level,
            action=action,
            reason_code=reason,
            rationale=rationale,
        )
        state.audit_trail.append(audit)

        return AssistanceTransitionResult(
            previous_level=prev_level,
            new_level=new_level,
            action=action,
            consecutive_failures=state.consecutive_failures,
            reason_code=reason,
            rationale=rationale,
            policy_version=self.policy_version,
            audit_entry=audit,
        )
