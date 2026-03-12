"""Tests for PerformancePlan (Phase N1).

Verifies that PerformancePlan is created correctly and provides the expected API.
"""

from produzre.orchestrate import (
    PerformancePlan,
    SectionMeta,
    PLAN_KEY_RHYTHM_GRID,
    PLAN_KEY_HARMONY_PLAN,
    PLAN_KEY_GROOVE_CUES,
)


def test_performance_plan_initialization():
    """Test basic PerformancePlan initialization."""
    sections = [
        SectionMeta(
            id="verse",
            type="verse",
            start_beat=0.0,
            end_beat=16.0,
            length_beats=16.0,
            beats_per_bar=4.0,
            meter="4/4",
            key="C",
            mode="ionian",
        ),
        SectionMeta(
            id="chorus",
            type="chorus",
            start_beat=16.0,
            end_beat=32.0,
            length_beats=16.0,
            beats_per_bar=4.0,
            meter="4/4",
            key="C",
            mode="ionian",
        ),
    ]

    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
        sections=sections,
    )

    assert plan.bpm == 120.0
    assert plan.meter == "4/4"
    assert plan.key == "C"
    assert plan.mode == "ionian"
    assert plan.beats_per_bar == 4.0
    assert plan.total_beats == 32.0
    assert len(plan.sections) == 2
    assert plan.sections[0].id == "verse"
    assert plan.sections[1].id == "chorus"


def test_performance_plan_data_api():
    """Test PerformancePlan data store API (has/get/set)."""
    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
    )

    # Initially empty
    assert not plan.has(PLAN_KEY_GROOVE_CUES)
    assert plan.get(PLAN_KEY_GROOVE_CUES) is None
    assert plan.get(PLAN_KEY_GROOVE_CUES, "default") == "default"

    # Set and retrieve
    groove_data = {"kick_beats": [0.0, 1.0, 2.0]}
    plan.set(PLAN_KEY_GROOVE_CUES, groove_data)

    assert plan.has(PLAN_KEY_GROOVE_CUES)
    assert plan.get(PLAN_KEY_GROOVE_CUES) == groove_data


def test_performance_plan_merge_replace():
    """Test PerformancePlan merge with replace strategy."""
    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
    )

    plan.set(PLAN_KEY_RHYTHM_GRID, {"value": 1})
    plan.merge(PLAN_KEY_RHYTHM_GRID, {"value": 2}, strategy="replace")

    assert plan.get(PLAN_KEY_RHYTHM_GRID) == {"value": 2}


def test_performance_plan_merge_extend():
    """Test PerformancePlan merge with extend strategy."""
    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
    )

    plan.set("test.list", [1, 2, 3])
    plan.merge("test.list", [4, 5], strategy="extend")

    assert plan.get("test.list") == [1, 2, 3, 4, 5]


def test_performance_plan_merge_deepmerge():
    """Test PerformancePlan merge with deepmerge strategy."""
    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
    )

    plan.set(PLAN_KEY_HARMONY_PLAN, {"verse": {"chords": ["I", "IV"]}, "chorus": {"chords": ["I", "V"]}})
    plan.merge(
        PLAN_KEY_HARMONY_PLAN,
        {"verse": {"tempo": "moderate"}, "bridge": {"chords": ["vi", "IV"]}},
        strategy="deepmerge"
    )

    result = plan.get(PLAN_KEY_HARMONY_PLAN)
    assert result["verse"]["chords"] == ["I", "IV"]
    assert result["verse"]["tempo"] == "moderate"
    assert result["chorus"]["chords"] == ["I", "V"]
    assert result["bridge"]["chords"] == ["vi", "IV"]


def test_performance_plan_get_section():
    """Test PerformancePlan.get_section() lookup."""
    sections = [
        SectionMeta(
            id="verse",
            type="verse",
            start_beat=0.0,
            end_beat=16.0,
            length_beats=16.0,
            beats_per_bar=4.0,
            meter="4/4",
            key="C",
            mode="ionian",
        ),
        SectionMeta(
            id="chorus",
            type="chorus",
            start_beat=16.0,
            end_beat=32.0,
            length_beats=16.0,
            beats_per_bar=4.0,
            meter="4/4",
            key="C",
            mode="ionian",
        ),
    ]

    plan = PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
        sections=sections,
    )

    verse = plan.get_section("verse")
    assert verse is not None
    assert verse.id == "verse"
    assert verse.type == "verse"
    assert verse.start_beat == 0.0
    assert verse.end_beat == 16.0

    chorus = plan.get_section("chorus")
    assert chorus is not None
    assert chorus.id == "chorus"

    missing = plan.get_section("bridge")
    assert missing is None
