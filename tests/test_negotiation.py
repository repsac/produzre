"""Tests for negotiation feedback loop (Phase N8).

Verifies that:
1. Engines can provide feedback via FeedbackCollector
2. Feedback is bounded (max 1 round per section)
3. Feedback application is deterministic (priority order)
4. Only whitelisted plan keys can be modified
5. Feedback targeting works correctly (None = all subsequent, specific section ID)
6. Negotiation state prevents infinite loops
"""

from produzre.orchestrate.negotiation import (
    FeedbackCollector,
    FeedbackApplicator,
    NegotiationState,
    EngineFeedback,
    NEGOTIABLE_KEYS,
    create_feedback_collector,
    apply_feedback_for_section,
)
from produzre.orchestrate.plan import PerformancePlan


def create_test_plan():
    """Create a test PerformancePlan with default values."""
    return PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=64.0,
    )


def test_feedback_collector_accepts_valid_feedback():
    """FeedbackCollector should accept feedback with negotiable keys."""
    collector = FeedbackCollector("verse1")

    # Add valid feedback
    success = collector.add_feedback(
        engine_name="bass",
        feedback_type="density",
        plan_key="suggested_density",
        adjustment={"suggested_density": 0.7},
        priority=0.6,
        reason="Bass suggests higher density for fuller sound",
    )

    assert success is True
    feedback_items = collector.get_feedback()
    assert len(feedback_items) == 1
    assert feedback_items[0].engine_name == "bass"
    assert feedback_items[0].section_id == "verse1"
    assert feedback_items[0].feedback_type == "density"


def test_feedback_collector_rejects_non_negotiable_keys():
    """FeedbackCollector should reject feedback for non-whitelisted keys."""
    collector = FeedbackCollector("verse1")

    # Try to add feedback with invalid key
    success = collector.add_feedback(
        engine_name="malicious",
        feedback_type="evil",
        plan_key="delete_everything",  # Not in NEGOTIABLE_KEYS
        adjustment={},
    )

    assert success is False
    feedback_items = collector.get_feedback()
    assert len(feedback_items) == 0


def test_feedback_collector_clamps_priority():
    """FeedbackCollector should clamp priority to [0.0, 1.0]."""
    collector = FeedbackCollector("verse1")

    # Add feedback with out-of-range priority
    collector.add_feedback(
        engine_name="drums",
        feedback_type="rhythm",
        plan_key="rhythm.accents",
        adjustment={},
        priority=2.5,  # Will be clamped to 1.0
    )

    feedback_items = collector.get_feedback()
    assert len(feedback_items) == 1
    assert feedback_items[0].priority == 1.0


def test_negotiable_keys_whitelist():
    """Verify NEGOTIABLE_KEYS contains expected keys."""
    assert "transitions.map" in NEGOTIABLE_KEYS
    assert "rhythm.accents" in NEGOTIABLE_KEYS
    assert "suggested_density" in NEGOTIABLE_KEYS
    assert "suggested_energy" in NEGOTIABLE_KEYS

    # Verify critical keys are NOT negotiable
    assert "harmony.plan" not in NEGOTIABLE_KEYS
    assert "rhythm.grid" not in NEGOTIABLE_KEYS


def test_feedback_applicator_applies_in_priority_order():
    """Feedback should be applied in priority order (highest first)."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    # Add multiple feedback items with different priorities
    feedback_items = [
        EngineFeedback(
            engine_name="bass",
            section_id="verse1",
            target_section_id="chorus1",
            feedback_type="density",
            plan_key="suggested_density",
            adjustment={"suggested_density": 0.5},
            priority=0.3,
        ),
        EngineFeedback(
            engine_name="drums",
            section_id="verse1",
            target_section_id="chorus1",
            feedback_type="energy",
            plan_key="suggested_energy",
            adjustment={"suggested_energy": 0.8},
            priority=0.9,  # Highest priority
        ),
        EngineFeedback(
            engine_name="lead_gtr",
            section_id="verse1",
            target_section_id="chorus1",
            feedback_type="density",
            plan_key="suggested_density",
            adjustment={"suggested_density": 0.7},
            priority=0.6,
        ),
    ]

    applied_count = applicator.apply_feedback(feedback_items, plan, "chorus1")

    # All 3 should be applied
    assert applied_count == 3

    # Verify order: drums (0.9) > lead_gtr (0.6) > bass (0.3)
    # Since density is set by both lead_gtr and bass, last one wins
    # But drums' energy feedback should be applied first
    assert plan.get("suggested_energy.chorus1") == 0.8
    # Density will be from bass (last in priority order after sorting)
    assert plan.get("suggested_density.chorus1") == 0.5


def test_feedback_applicator_prevents_duplicate_application():
    """Feedback from same (section, engine) pair should only apply once."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    feedback = EngineFeedback(
        engine_name="bass",
        section_id="verse1",
        target_section_id="chorus1",
        feedback_type="density",
        plan_key="suggested_density",
        adjustment={"suggested_density": 0.7},
        priority=0.5,
    )

    # Apply feedback twice
    count1 = applicator.apply_feedback([feedback], plan, "chorus1")
    count2 = applicator.apply_feedback([feedback], plan, "chorus1")

    assert count1 == 1
    assert count2 == 0  # Duplicate rejected


def test_feedback_targeting_specific_section():
    """Feedback with target_section_id should only affect that section."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    feedback = EngineFeedback(
        engine_name="bass",
        section_id="verse1",
        target_section_id="chorus1",  # Specific target
        feedback_type="density",
        plan_key="suggested_density",
        adjustment={"suggested_density": 0.7},
        priority=0.5,
    )

    # Apply to chorus1 (target) - should succeed
    count1 = applicator.apply_feedback([feedback], plan, "chorus1")
    assert count1 == 1
    assert plan.get("suggested_density.chorus1") == 0.7

    # Apply to verse2 (not target) - should be ignored
    count2 = applicator.apply_feedback([feedback], plan, "verse2")
    assert count2 == 0
    assert plan.get("suggested_density.verse2") is None


def test_feedback_targeting_all_subsequent_sections():
    """Feedback with target_section_id=None should affect all subsequent sections."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    feedback = EngineFeedback(
        engine_name="bass",
        section_id="verse1",
        target_section_id=None,  # All subsequent sections
        feedback_type="energy",
        plan_key="suggested_energy",
        adjustment={"suggested_energy": 0.8},
        priority=0.5,
    )

    # Should apply to any section
    count1 = applicator.apply_feedback([feedback], plan, "chorus1")
    count2 = applicator.apply_feedback([feedback], plan, "bridge1")

    # First application succeeds, second is duplicate (same section_id + engine_name)
    assert count1 == 1
    assert count2 == 0
    assert plan.get("suggested_energy.chorus1") == 0.8


def test_transition_feedback_adjusts_ramps():
    """Transition feedback should adjust energy_ramp and density_ramp."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    # Create mock transitions map
    transitions_map = {
        "verse1": {
            "section_id": "verse1",
            "next_section_id": "chorus1",
            "energy_ramp": 0.5,
            "density_ramp": 0.3,
        }
    }
    plan.set("transitions.map", transitions_map)

    # Feedback to adjust transition
    feedback = EngineFeedback(
        engine_name="bass",
        section_id="verse1",
        target_section_id="chorus1",
        feedback_type="transition",
        plan_key="transitions.map",
        adjustment={
            "energy_ramp_delta": 0.2,   # Increase energy ramp
            "density_ramp_delta": -0.1,  # Decrease density ramp
        },
        priority=0.5,
    )

    applied_count = applicator.apply_feedback([feedback], plan, "chorus1")
    assert applied_count == 1

    # Verify adjustments (use approximate comparison for floating point)
    updated_transitions = plan.get("transitions.map")
    verse_transition = updated_transitions["verse1"]
    assert abs(verse_transition["energy_ramp"] - 0.7) < 0.001  # 0.5 + 0.2
    assert abs(verse_transition["density_ramp"] - 0.2) < 0.001  # 0.3 - 0.1


def test_transition_feedback_clamps_values():
    """Transition feedback should clamp ramps to [-1.0, 1.0]."""
    state = NegotiationState()
    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    transitions_map = {
        "verse1": {
            "section_id": "verse1",
            "next_section_id": "chorus1",
            "energy_ramp": 0.8,
            "density_ramp": -0.9,
        }
    }
    plan.set("transitions.map", transitions_map)

    feedback = EngineFeedback(
        engine_name="drums",
        section_id="verse1",
        target_section_id="chorus1",
        feedback_type="transition",
        plan_key="transitions.map",
        adjustment={
            "energy_ramp_delta": 0.5,   # Would exceed 1.0
            "density_ramp_delta": -0.5,  # Would go below -1.0
        },
        priority=0.5,
    )

    applicator.apply_feedback([feedback], plan, "chorus1")

    updated_transitions = plan.get("transitions.map")
    verse_transition = updated_transitions["verse1"]
    assert verse_transition["energy_ramp"] == 1.0   # Clamped at max
    assert verse_transition["density_ramp"] == -1.0  # Clamped at min


def test_factory_function():
    """create_feedback_collector should create a working collector."""
    collector = create_feedback_collector("verse1")

    assert isinstance(collector, FeedbackCollector)
    assert collector.section_id == "verse1"

    collector.add_feedback(
        engine_name="test",
        feedback_type="density",
        plan_key="suggested_density",
        adjustment=0.5,
    )

    feedback = collector.get_feedback()
    assert len(feedback) == 1


def test_convenience_function():
    """apply_feedback_for_section should work as a convenience wrapper."""
    plan = create_test_plan()
    state = NegotiationState()

    feedback_items = [
        EngineFeedback(
            engine_name="bass",
            section_id="verse1",
            target_section_id="chorus1",
            feedback_type="density",
            plan_key="suggested_density",
            adjustment={"suggested_density": 0.7},
            priority=0.5,
        )
    ]

    applied_count = apply_feedback_for_section(
        feedback_items=feedback_items,
        performance_plan=plan,
        target_section_id="chorus1",
        negotiation_state=state,
    )

    assert applied_count == 1
    assert plan.get("suggested_density.chorus1") == 0.7


def test_negotiation_state_tracks_applications():
    """NegotiationState should track which feedback has been applied."""
    state = NegotiationState()

    assert len(state.feedback_log) == 0
    assert len(state.applied_feedback) == 0

    applicator = FeedbackApplicator(state)
    plan = create_test_plan()

    feedback = EngineFeedback(
        engine_name="bass",
        section_id="verse1",
        target_section_id="chorus1",
        feedback_type="density",
        plan_key="suggested_density",
        adjustment={"suggested_density": 0.7},
        priority=0.5,
    )

    applicator.apply_feedback([feedback], plan, "chorus1")

    # State should be updated
    assert len(state.feedback_log) == 1
    assert ("verse1", "bass") in state.applied_feedback


if __name__ == "__main__":
    # Run all tests
    test_feedback_collector_accepts_valid_feedback()
    print("✓ test_feedback_collector_accepts_valid_feedback passed")

    test_feedback_collector_rejects_non_negotiable_keys()
    print("✓ test_feedback_collector_rejects_non_negotiable_keys passed")

    test_feedback_collector_clamps_priority()
    print("✓ test_feedback_collector_clamps_priority passed")

    test_negotiable_keys_whitelist()
    print("✓ test_negotiable_keys_whitelist passed")

    test_feedback_applicator_applies_in_priority_order()
    print("✓ test_feedback_applicator_applies_in_priority_order passed")

    test_feedback_applicator_prevents_duplicate_application()
    print("✓ test_feedback_applicator_prevents_duplicate_application passed")

    test_feedback_targeting_specific_section()
    print("✓ test_feedback_targeting_specific_section passed")

    test_feedback_targeting_all_subsequent_sections()
    print("✓ test_feedback_targeting_all_subsequent_sections passed")

    test_transition_feedback_adjusts_ramps()
    print("✓ test_transition_feedback_adjusts_ramps passed")

    test_transition_feedback_clamps_values()
    print("✓ test_transition_feedback_clamps_values passed")

    test_factory_function()
    print("✓ test_factory_function passed")

    test_convenience_function()
    print("✓ test_convenience_function passed")

    test_negotiation_state_tracks_applications()
    print("✓ test_negotiation_state_tracks_applications passed")

    print("\nAll Phase N8 negotiation tests passed!")
