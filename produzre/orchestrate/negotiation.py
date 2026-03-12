"""Negotiation feedback loop for engine-to-engine communication (Phase N8).

This module provides a bounded negotiation mechanism where engines can suggest
adjustments to the PerformancePlan for subsequent sections. This enables later
engines to provide hints that might improve coordination without causing
nondeterministic chaos.

Key constraints:
- Feedback can only affect FUTURE sections (not the current section)
- Maximum 1 feedback round per section boundary (no infinite loops)
- Only whitelisted plan keys can be modified via feedback
- Feedback application is deterministic (fixed order, same inputs = same outputs)

Design:
- Engines optionally return feedback during render
- Feedback is collected after section render completes
- Feedback is applied before next section renders
- Feedback is stored in PerformancePlan for transparency
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set
import logging


# Whitelisted plan keys that can be modified via negotiation feedback
NEGOTIABLE_KEYS = {
    "transitions.map",       # Section-level transition adjustments
    "rhythm.accents",        # Rhythm accent tweaks (rare)
    "suggested_density",     # Density hints for subsequent sections
    "suggested_energy",      # Energy hints for subsequent sections
}


@dataclass
class EngineFeedback:
    """Feedback from an engine about plan adjustments for subsequent sections.

    Engines can provide feedback to suggest adjustments that might improve
    coordination or musical flow. Feedback is advisory and may be ignored
    if it conflicts with other constraints.

    Attributes:
        engine_name: Name of the engine providing feedback.
        section_id: Section where feedback was generated.
        target_section_id: Section to apply feedback to (None = all subsequent).
        feedback_type: Type of feedback ("transition", "rhythm", "density", "energy").
        plan_key: Plan key to modify (must be in NEGOTIABLE_KEYS).
        adjustment: Adjustment data (structure depends on feedback_type).
        priority: Priority hint (higher = more important, default 0.5).
        reason: Optional human-readable explanation for debugging.
    """
    engine_name: str
    section_id: str
    target_section_id: Optional[str]
    feedback_type: str
    plan_key: str
    adjustment: Any
    priority: float = 0.5
    reason: Optional[str] = None


@dataclass
class NegotiationState:
    """State tracker for negotiation feedback across sections.

    Tracks feedback collected from engines and ensures bounded negotiation
    (max 1 round per section boundary).

    Attributes:
        feedback_log: List of all feedback received (for debugging/transparency).
        applied_feedback: Set of (section_id, engine_name) tuples that have
            already applied feedback (prevents infinite loops).
        max_feedback_rounds: Maximum feedback rounds per section (default 1).
    """
    feedback_log: List[EngineFeedback] = field(default_factory=list)
    applied_feedback: Set[tuple[str, str]] = field(default_factory=set)
    max_feedback_rounds: int = 1


class FeedbackCollector:
    """Collects feedback from engines during section rendering.

    Engines can call add_feedback() during their render to suggest plan
    adjustments for subsequent sections.
    """

    def __init__(self, section_id: str, logger: Optional[logging.Logger] = None):
        """Initialize feedback collector for a section.

        Args:
            section_id: ID of the section being rendered.
            logger: Optional logger for debug output.
        """
        self.section_id = section_id
        self.feedback_items: List[EngineFeedback] = []
        self.logger = logger or logging.getLogger(__name__)

    def add_feedback(
        self,
        engine_name: str,
        feedback_type: str,
        plan_key: str,
        adjustment: Any,
        target_section_id: Optional[str] = None,
        priority: float = 0.5,
        reason: Optional[str] = None,
    ) -> bool:
        """Add feedback from an engine.

        Args:
            engine_name: Name of the engine providing feedback.
            feedback_type: Type of feedback ("transition", "rhythm", "density", "energy").
            plan_key: Plan key to modify (must be in NEGOTIABLE_KEYS).
            adjustment: Adjustment data (structure depends on feedback_type).
            target_section_id: Section to apply feedback to (None = all subsequent).
            priority: Priority hint (0.0 to 1.0, default 0.5).
            reason: Optional explanation for debugging.

        Returns:
            bool: True if feedback was accepted, False if rejected.
        """
        # Validate plan_key is negotiable
        if plan_key not in NEGOTIABLE_KEYS:
            self.logger.warning(
                f"[NEGOTIATION] Rejected feedback from {engine_name}: "
                f"plan_key '{plan_key}' is not negotiable (allowed: {NEGOTIABLE_KEYS})"
            )
            return False

        # Validate priority range
        priority = max(0.0, min(1.0, priority))

        feedback = EngineFeedback(
            engine_name=engine_name,
            section_id=self.section_id,
            target_section_id=target_section_id,
            feedback_type=feedback_type,
            plan_key=plan_key,
            adjustment=adjustment,
            priority=priority,
            reason=reason,
        )

        self.feedback_items.append(feedback)

        if self.logger:
            self.logger.debug(
                f"[NEGOTIATION] Collected feedback from {engine_name} in section '{self.section_id}': "
                f"type={feedback_type}, key={plan_key}, target={target_section_id}, priority={priority:.2f}"
            )

        return True

    def get_feedback(self) -> List[EngineFeedback]:
        """Get all collected feedback items.

        Returns:
            List[EngineFeedback]: All feedback collected for this section.
        """
        return self.feedback_items.copy()


class FeedbackApplicator:
    """Applies collected feedback to the PerformancePlan.

    Applies feedback in priority order (highest first) and ensures determinism
    by using stable sorting and bounded application.
    """

    def __init__(
        self,
        negotiation_state: NegotiationState,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize feedback applicator.

        Args:
            negotiation_state: Negotiation state tracker.
            logger: Optional logger for debug output.
        """
        self.state = negotiation_state
        self.logger = logger or logging.getLogger(__name__)

    def apply_feedback(
        self,
        feedback_items: List[EngineFeedback],
        performance_plan,
        target_section_id: str,
    ) -> int:
        """Apply feedback to the PerformancePlan for a target section.

        Filters feedback relevant to target_section_id, sorts by priority,
        and applies adjustments in order. Ensures each (section_id, engine_name)
        pair only applies feedback once (bounded negotiation).

        Args:
            feedback_items: List of feedback to potentially apply.
            performance_plan: PerformancePlan object to modify.
            target_section_id: ID of section to apply feedback for.

        Returns:
            int: Number of feedback items actually applied.
        """
        # Filter feedback relevant to target section
        relevant_feedback = [
            fb for fb in feedback_items
            if fb.target_section_id is None or fb.target_section_id == target_section_id
        ]

        if not relevant_feedback:
            return 0

        # Sort by priority (highest first), then by engine_name for determinism
        sorted_feedback = sorted(
            relevant_feedback,
            key=lambda fb: (-fb.priority, fb.engine_name),
        )

        applied_count = 0

        for fb in sorted_feedback:
            # Check if this (section, engine) pair already applied feedback
            feedback_key = (fb.section_id, fb.engine_name)

            if feedback_key in self.state.applied_feedback:
                self.logger.debug(
                    f"[NEGOTIATION] Skipping duplicate feedback from {fb.engine_name} "
                    f"in section '{fb.section_id}' (already applied)"
                )
                continue

            # Apply the feedback
            success = self._apply_single_feedback(fb, performance_plan, target_section_id)

            if success:
                applied_count += 1
                self.state.applied_feedback.add(feedback_key)
                self.state.feedback_log.append(fb)

                if self.logger:
                    self.logger.info(
                        f"[NEGOTIATION] Applied feedback from {fb.engine_name}: "
                        f"type={fb.feedback_type}, key={fb.plan_key}, "
                        f"target={target_section_id}, priority={fb.priority:.2f}"
                    )
                    if fb.reason:
                        self.logger.debug(f"[NEGOTIATION]   Reason: {fb.reason}")

        return applied_count

    def _apply_single_feedback(
        self,
        feedback: EngineFeedback,
        performance_plan,
        target_section_id: str,
    ) -> bool:
        """Apply a single feedback item to the plan.

        Args:
            feedback: Feedback item to apply.
            performance_plan: PerformancePlan object to modify.
            target_section_id: Section to apply feedback for.

        Returns:
            bool: True if feedback was successfully applied.
        """
        try:
            if feedback.feedback_type == "transition":
                return self._apply_transition_feedback(feedback, performance_plan, target_section_id)
            elif feedback.feedback_type == "rhythm":
                return self._apply_rhythm_feedback(feedback, performance_plan, target_section_id)
            elif feedback.feedback_type == "density":
                return self._apply_density_feedback(feedback, performance_plan, target_section_id)
            elif feedback.feedback_type == "energy":
                return self._apply_energy_feedback(feedback, performance_plan, target_section_id)
            else:
                self.logger.warning(
                    f"[NEGOTIATION] Unknown feedback type: {feedback.feedback_type}"
                )
                return False
        except Exception as e:
            self.logger.error(
                f"[NEGOTIATION] Error applying feedback from {feedback.engine_name}: {e}"
            )
            return False

    def _apply_transition_feedback(
        self,
        feedback: EngineFeedback,
        performance_plan,
        target_section_id: str,
    ) -> bool:
        """Apply transition-related feedback.

        Example adjustment format:
        {
            "energy_ramp_delta": +0.2,  # Adjust energy ramp by this amount
            "density_ramp_delta": -0.1,  # Adjust density ramp by this amount
        }
        """
        transitions_map = performance_plan.get("transitions.map")
        if not transitions_map:
            return False

        # Find the transition TO the target section (from previous section)
        transition_data = None
        prev_section_id = None

        # Search for transition that has target_section_id as next_section_id
        for sec_id, trans in transitions_map.items():
            if trans.get("next_section_id") == target_section_id:
                transition_data = trans
                prev_section_id = sec_id
                break

        if not transition_data:
            return False

        adjustment = feedback.adjustment
        if not isinstance(adjustment, dict):
            return False

        # Apply adjustments with bounds
        if "energy_ramp_delta" in adjustment:
            current_ramp = transition_data.get("energy_ramp", 0.0)
            delta = float(adjustment["energy_ramp_delta"])
            new_ramp = max(-1.0, min(1.0, current_ramp + delta))
            transition_data["energy_ramp"] = new_ramp

        if "density_ramp_delta" in adjustment:
            current_ramp = transition_data.get("density_ramp", 0.0)
            delta = float(adjustment["density_ramp_delta"])
            new_ramp = max(-1.0, min(1.0, current_ramp + delta))
            transition_data["density_ramp"] = new_ramp

        return True

    def _apply_rhythm_feedback(
        self,
        feedback: EngineFeedback,
        performance_plan,
        target_section_id: str,
    ) -> bool:
        """Apply rhythm-related feedback.

        Example adjustment format:
        {
            "add_accents": [4.0, 8.0, 12.0],  # Add accent beats
            "remove_accents": [2.0, 6.0],     # Remove accent beats
        }
        """
        # Rhythm feedback is stored as suggestions, not directly applied
        # (rhythm.accents are per-section and set by drums)
        # Store as hints for next time drums runs

        suggestions_key = f"rhythm.accents.suggestions.{target_section_id}"
        performance_plan.set(suggestions_key, feedback.adjustment)

        return True

    def _apply_density_feedback(
        self,
        feedback: EngineFeedback,
        performance_plan,
        target_section_id: str,
    ) -> bool:
        """Apply density-related feedback.

        Example adjustment format:
        {
            "suggested_density": 0.7,  # 0.0 to 1.0
            "reason": "bass suggests higher density for fuller sound"
        }
        """
        density_key = f"suggested_density.{target_section_id}"
        if isinstance(feedback.adjustment, dict):
            density_value = feedback.adjustment.get("suggested_density")
        else:
            density_value = feedback.adjustment

        if density_value is not None:
            performance_plan.set(density_key, float(density_value))
            return True

        return False

    def _apply_energy_feedback(
        self,
        feedback: EngineFeedback,
        performance_plan,
        target_section_id: str,
    ) -> bool:
        """Apply energy-related feedback.

        Example adjustment format:
        {
            "suggested_energy": 0.8,  # 0.0 to 1.0
            "reason": "lead guitar suggests higher energy for solo"
        }
        """
        energy_key = f"suggested_energy.{target_section_id}"
        if isinstance(feedback.adjustment, dict):
            energy_value = feedback.adjustment.get("suggested_energy")
        else:
            energy_value = feedback.adjustment

        if energy_value is not None:
            performance_plan.set(energy_key, float(energy_value))
            return True

        return False


def create_feedback_collector(
    section_id: str,
    logger: Optional[logging.Logger] = None,
) -> FeedbackCollector:
    """Factory function to create a feedback collector for a section.

    Args:
        section_id: ID of the section being rendered.
        logger: Optional logger for debug output.

    Returns:
        FeedbackCollector: New collector instance.
    """
    return FeedbackCollector(section_id, logger)


def apply_feedback_for_section(
    feedback_items: List[EngineFeedback],
    performance_plan,
    target_section_id: str,
    negotiation_state: NegotiationState,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Apply collected feedback for a target section.

    Convenience function that creates an applicator and applies feedback.

    Args:
        feedback_items: List of feedback to apply.
        performance_plan: PerformancePlan object to modify.
        target_section_id: Section to apply feedback for.
        negotiation_state: Negotiation state tracker.
        logger: Optional logger for debug output.

    Returns:
        int: Number of feedback items actually applied.
    """
    applicator = FeedbackApplicator(negotiation_state, logger)
    return applicator.apply_feedback(feedback_items, performance_plan, target_section_id)
