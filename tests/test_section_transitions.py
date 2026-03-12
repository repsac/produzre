"""Tests for section-level transition planning (Phase N5).

Verifies that:
1. Section transitions are computed from arrangement
2. Energy/density ramps follow section type expectations
3. Turnaround/pickup hints are appropriate for transitions
4. First and last section flags are set correctly
5. Transitions are stored in PerformancePlan
"""

from dataclasses import dataclass, field
from typing import List, Optional

from produzre.orchestrate.transitions import (
    SectionTransition,
    build_section_transitions_map,
    serialize_section_transitions_map,
)


@dataclass
class MockSection:
    """Mock section for testing."""
    type: str = "verse"


@dataclass
class MockSectionTiming:
    """Mock section timing."""
    start_beat: float = 0.0
    end_beat: float = 16.0
    length_beats: float = 16.0
    beats_per_bar: float = 4.0


@dataclass
class MockPlannedSection:
    """Mock planned section."""
    sec_id: str
    sec: MockSection
    timing: MockSectionTiming = field(default_factory=MockSectionTiming)


def test_verse_to_chorus_ramps_up():
    """Verse to chorus should have positive energy and density ramps."""
    planned_sections = [
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="chorus", sec=MockSection(type="chorus")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    verse_transition = transitions["verse"]
    assert verse_transition.section_id == "verse"
    assert verse_transition.next_section_id == "chorus"
    assert verse_transition.next_section_type == "chorus"
    assert verse_transition.energy_ramp > 0.5, "Verse to chorus should ramp up energy"
    assert verse_transition.density_ramp > 0.5, "Verse to chorus should increase density"
    assert verse_transition.pickup_hint is True, "Should use pickup before chorus"
    assert verse_transition.is_first_section is True
    assert verse_transition.is_last_section is False


def test_chorus_to_verse_ramps_down():
    """Chorus to verse should have negative energy and density ramps."""
    planned_sections = [
        MockPlannedSection(sec_id="chorus", sec=MockSection(type="chorus")),
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    chorus_transition = transitions["chorus"]
    assert chorus_transition.next_section_type == "verse"
    assert chorus_transition.energy_ramp < 0, "Chorus to verse should ramp down energy"
    assert chorus_transition.density_ramp < 0, "Chorus to verse should decrease density"
    assert chorus_transition.turnaround_hint == "light", "Should have light turnaround"
    assert chorus_transition.is_first_section is True


def test_last_section_has_heavy_turnaround():
    """Last section should have heavy turnaround for ending."""
    planned_sections = [
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="outro", sec=MockSection(type="outro")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    outro_transition = transitions["outro"]
    assert outro_transition.next_section_id is None
    assert outro_transition.next_section_type is None
    assert outro_transition.energy_ramp < 0, "Outro should ramp down"
    assert outro_transition.density_ramp < 0, "Outro should thin out"
    assert outro_transition.turnaround_hint == "heavy", "Last section needs heavy turnaround"
    assert outro_transition.pickup_hint is False, "No pickup after last section"
    assert outro_transition.is_last_section is True


def test_bridge_gets_longer_lead_in():
    """Bridge sections should get longer lead-in bars."""
    planned_sections = [
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="bridge", sec=MockSection(type="bridge")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    verse_transition = transitions["verse"]
    assert verse_transition.next_section_type == "bridge"
    assert verse_transition.lead_in_bars >= 1, "Should have lead-in for bridge"
    assert verse_transition.pickup_hint is True, "Should use pickup before bridge"


def test_breakdown_ramps_down_significantly():
    """Transition to breakdown should have strong negative ramps."""
    planned_sections = [
        MockPlannedSection(sec_id="chorus", sec=MockSection(type="chorus")),
        MockPlannedSection(sec_id="breakdown", sec=MockSection(type="breakdown")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    chorus_transition = transitions["chorus"]
    assert chorus_transition.next_section_type == "breakdown"
    assert chorus_transition.density_ramp < -0.5, "Breakdown should have strong density reduction"
    assert chorus_transition.lead_in_bars >= 2, "Breakdown needs longer lead-in to signal change"


def test_intro_to_verse_has_pickup():
    """Intro to verse should use pickup for first verse entry."""
    planned_sections = [
        MockPlannedSection(sec_id="intro", sec=MockSection(type="intro")),
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    intro_transition = transitions["intro"]
    assert intro_transition.next_section_type == "verse"
    assert intro_transition.pickup_hint is True, "Should use pickup for first verse"


def test_solo_has_high_energy():
    """Transition to solo should build energy and density."""
    planned_sections = [
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="solo", sec=MockSection(type="solo")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    verse_transition = transitions["verse"]
    assert verse_transition.next_section_type == "solo"
    assert verse_transition.energy_ramp > 0, "Should ramp up for solo"
    assert verse_transition.density_ramp > 0, "Should build density for solo"
    assert verse_transition.pickup_hint is True, "Should use pickup before solo"


def test_bridge_to_chorus_has_heavy_turnaround():
    """Bridge/solo to chorus should have heavy turnaround."""
    planned_sections = [
        MockPlannedSection(sec_id="bridge", sec=MockSection(type="bridge")),
        MockPlannedSection(sec_id="chorus", sec=MockSection(type="chorus")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    bridge_transition = transitions["bridge"]
    assert bridge_transition.next_section_type == "chorus"
    assert bridge_transition.turnaround_hint == "heavy", "Bridge to chorus needs heavy turnaround"


def test_serialization_roundtrip():
    """Serialized transitions should preserve all data."""
    planned_sections = [
        MockPlannedSection(sec_id="verse", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="chorus", sec=MockSection(type="chorus")),
    ]

    transitions = build_section_transitions_map(planned_sections)
    serialized = serialize_section_transitions_map(transitions)

    # Verify serialization preserves all fields
    assert "verse" in serialized
    verse_dict = serialized["verse"]

    assert verse_dict["section_id"] == "verse"
    assert verse_dict["next_section_id"] == "chorus"
    assert verse_dict["next_section_type"] == "chorus"
    assert isinstance(verse_dict["energy_ramp"], float)
    assert isinstance(verse_dict["density_ramp"], float)
    assert isinstance(verse_dict["lead_in_bars"], int)
    assert isinstance(verse_dict["turnaround_hint"], str)
    assert isinstance(verse_dict["pickup_hint"], bool)
    assert isinstance(verse_dict["is_first_section"], bool)
    assert isinstance(verse_dict["is_last_section"], bool)


def test_complex_arrangement():
    """Test a more complex arrangement with multiple section types."""
    planned_sections = [
        MockPlannedSection(sec_id="intro", sec=MockSection(type="intro")),
        MockPlannedSection(sec_id="verse1", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="chorus1", sec=MockSection(type="chorus")),
        MockPlannedSection(sec_id="verse2", sec=MockSection(type="verse")),
        MockPlannedSection(sec_id="chorus2", sec=MockSection(type="chorus")),
        MockPlannedSection(sec_id="bridge", sec=MockSection(type="bridge")),
        MockPlannedSection(sec_id="chorus3", sec=MockSection(type="chorus")),
        MockPlannedSection(sec_id="outro", sec=MockSection(type="outro")),
    ]

    transitions = build_section_transitions_map(planned_sections)

    # Verify all sections have transitions
    assert len(transitions) == 8

    # Check first section
    assert transitions["intro"].is_first_section is True
    assert transitions["intro"].is_last_section is False

    # Check middle sections
    assert transitions["verse1"].is_first_section is False
    assert transitions["verse1"].is_last_section is False

    # Check last section
    assert transitions["outro"].is_first_section is False
    assert transitions["outro"].is_last_section is True
    assert transitions["outro"].turnaround_hint == "heavy"

    # Verify transitions have sensible directives
    # Bridge to final chorus should have heavy turnaround
    assert transitions["bridge"].turnaround_hint == "heavy"
    assert transitions["bridge"].next_section_type == "chorus"

    # Chorus to verse should pull back
    assert transitions["chorus1"].energy_ramp < 0
    assert transitions["chorus1"].next_section_type == "verse"


if __name__ == "__main__":
    # Run all tests
    test_verse_to_chorus_ramps_up()
    print("✓ test_verse_to_chorus_ramps_up passed")

    test_chorus_to_verse_ramps_down()
    print("✓ test_chorus_to_verse_ramps_down passed")

    test_last_section_has_heavy_turnaround()
    print("✓ test_last_section_has_heavy_turnaround passed")

    test_bridge_gets_longer_lead_in()
    print("✓ test_bridge_gets_longer_lead_in passed")

    test_breakdown_ramps_down_significantly()
    print("✓ test_breakdown_ramps_down_significantly passed")

    test_intro_to_verse_has_pickup()
    print("✓ test_intro_to_verse_has_pickup passed")

    test_solo_has_high_energy()
    print("✓ test_solo_has_high_energy passed")

    test_bridge_to_chorus_has_heavy_turnaround()
    print("✓ test_bridge_to_chorus_has_heavy_turnaround passed")

    test_serialization_roundtrip()
    print("✓ test_serialization_roundtrip passed")

    test_complex_arrangement()
    print("✓ test_complex_arrangement passed")

    print("\nAll Phase N5 section transition tests passed!")
