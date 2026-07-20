from __future__ import annotations

import random
from dataclasses import dataclass, field

from produzre.engine.bass.patterns.generators import (
    get_rhythm_pattern_funk_16ths,
    get_rhythm_pattern_rock_riff,
)
from produzre.engine.drums.fills import add_fills
from produzre.engine.drums.humanize import humanize_events
from produzre.engine.drums.patterns import DrumEvent
from produzre.engine.lead_gtr.phrasing import make_motif
from produzre.engine.rhythm_gtr.rhythm import build_bar_pattern
from produzre.orchestrate.coordinator import EngineCoordinator
from produzre.orchestrate.ensemble import build_ensemble_section_plan
from produzre.orchestrate.plan import PerformancePlan


@dataclass
class _Song:
    genre: str = "rock"


@dataclass
class _Config:
    song: _Song = field(default_factory=_Song)


@dataclass
class _Section:
    id: str = "verse1"
    type: str = "verse"
    instruments: dict = field(default_factory=lambda: {
        "drums": {}, "bass": {}, "rhythm_gtr": {}, "lead_gtr": {}
    })


@dataclass
class _Grid:
    beats_per_bar: float = 4.0
    total_beats: float = 16.0


def _plan() -> PerformancePlan:
    return PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="E",
        mode="minor",
        beats_per_bar=4.0,
        total_beats=16.0,
    )


def test_ensemble_plan_assigns_complementary_roles_and_windows():
    section_plan = build_ensemble_section_plan(_Config(), _Section(), _Grid())

    assert section_plan["roles"]["bass"]["role"] == "anchor"
    assert section_plan["roles"]["rhythm_gtr"]["role"] == "comp"
    assert section_plan["roles"]["lead_gtr"]["role"] == "answer"
    assert section_plan["fill_owner"] == "drums"
    assert section_plan["lead_activity_windows"] == [(4.0, 12.0)]
    assert section_plan["lead_rest_ratio"] == 0.5


def test_coordinator_exposes_role_density_and_activity_contract():
    plan = _plan()
    section_plan = build_ensemble_section_plan(_Config(), _Section(), _Grid())
    plan.set("ensemble.verse1", section_plan)
    coordinator = EngineCoordinator(plan)

    assert coordinator.get_instrument_role("verse1", "rhythm_gtr") == "comp"
    assert coordinator.get_density_multiplier("verse1", "bass") == 0.82
    assert coordinator.get_lead_activity_windows("verse1") == [(4.0, 12.0)]
    assert coordinator.get_fill_owner("verse1") == "drums"


def test_bass_genre_cells_are_structurally_distinct():
    slots = [index / 4.0 for index in range(32)]
    rock = get_rhythm_pattern_rock_riff(slots, 4.0)
    funk = get_rhythm_pattern_funk_16ths(slots, 4.0)

    assert rock != funk
    assert 0.75 in funk and 0.75 not in rock
    assert 1.5 in rock and 1.5 in funk


def test_rhythm_guitar_idiom_cells_have_distinct_signatures():
    rock = build_bar_pattern("verse", "rock_riff", 1.0, rng=random.Random(3))
    funk = build_bar_pattern("verse", "funk_chanks", 1.0, rng=random.Random(3))
    jazz = build_bar_pattern("verse", "jazz_comp", 1.0, rng=random.Random(3))

    signatures = {(pattern.subdivision, tuple(pattern.hits)) for pattern in (rock, funk, jazz)}
    assert len(signatures) == 3
    assert 0 not in funk.hits
    assert jazz.subdivision == 3


def test_lead_genres_select_different_phrase_vocabularies():
    rock = make_motif(random.Random(11), 0.7, genre="rock")
    funk = make_motif(random.Random(11), 0.7, genre="funk")
    jazz = make_motif(random.Random(11), 0.7, genre="jazz")

    assert len({rock.intervals, funk.intervals, jazz.intervals}) == 3
    rock_variants = {make_motif(random.Random(seed), 0.7, genre="rock") for seed in range(12)}
    assert len(rock_variants) >= 4


def test_drum_phrase_fills_never_compress_below_sixteenth_grid():
    pitches = {
        "kick": 36,
        "snare": 38,
        "crash": 49,
        "tom_low": 45,
        "tom_mid": 47,
        "tom_high": 50,
    }
    for seed in range(30):
        events = add_fills(
            events=[],
            total_beats=16.0,
            beats_per_bar=4.0,
            rng=random.Random(seed),
            rng_fill=random.Random(seed),
            pitches=pitches,
            base_velocity=75,
            fill_rate=1.0,
            fill_chatter=0.0,
            phrase_len_bars=4,
            genre="rock",
        )
        fill_beats = sorted(event.beat for event in events if event.kind == "fill")
        intervals = [b - a for a, b in zip(fill_beats, fill_beats[1:]) if b > a]
        assert all(interval >= 0.25 - 1e-9 for interval in intervals)


def test_drum_fill_vocabulary_is_not_snare_roll_dominated():
    pitches = {
        "kick": 36,
        "snare": 38,
        "crash": 49,
        "tom_low": 45,
        "tom_mid": 47,
        "tom_high": 50,
    }
    all_fill_pitches = []
    for seed in range(40):
        events = add_fills(
            events=[],
            total_beats=16.0,
            beats_per_bar=4.0,
            rng=random.Random(seed),
            rng_fill=random.Random(seed),
            pitches=pitches,
            base_velocity=75,
            fill_rate=1.0,
            fill_chatter=0.0,
            phrase_len_bars=4,
            genre="rock",
        )
        all_fill_pitches.extend(event.pitch for event in events if event.kind == "fill")

    snare_ratio = all_fill_pitches.count(38) / len(all_fill_pitches)
    assert snare_ratio < 0.72
    assert {45, 47, 50} & set(all_fill_pitches)


def test_swing_does_not_compress_structural_fill_cells():
    events = [
        DrumEvent(beat=1.5, duration_beats=0.25, pitch=38, velocity=80, kind="fill"),
        DrumEvent(beat=1.75, duration_beats=0.25, pitch=47, velocity=86, kind="fill"),
    ]
    notes = humanize_events(
        events=events,
        section_start_beat=0.0,
        beats_per_bar=4.0,
        bpm=120.0,
        timing_jitter_ms=0.0,
        swing=0.8,
        push_pull=0.0,
        velocity_humanize=0.0,
        rng=random.Random(4),
    )
    assert notes[1][0] - notes[0][0] == 0.25
