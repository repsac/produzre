"""Tests for core/export/config fixes (2026-06-10 review, Themes 1.5/2/4/6).

These tests intentionally assert STRUCTURE (meta events, filenames, keys,
relative pitch classes), not content, so they stay stable across engine and
RNG evolution.
"""

from __future__ import annotations

import logging
import random

import mido
import pytest

from produzre.timeline import InstrumentTimeline, SectionTiming


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_yaml(tmp_path, text: str):
    p = tmp_path / "song.yaml"
    p.write_text(text, encoding="utf-8")
    from produzre.config.load import load_root_config
    return load_root_config(str(p))


MINIMAL_68_SONG = """
version: 1
song:
  title: "SixEight"
  bpm: 120
  key: C
  mode: ionian
  meter: "6/8"
  beats_per_bar: 3
  seed: 1
  exports_root: "{exports_root}"
sections:
  verse1:
    type: verse
    bars: 2
    instruments:
      drums: {{}}
arrangement:
  - verse1
"""


# ---------------------------------------------------------------------------
# 1. time_signature meta event
# ---------------------------------------------------------------------------

def test_time_signature_meta_present_for_6_8_song(tmp_path):
    cfg = _build_yaml(tmp_path, MINIMAL_68_SONG.format(exports_root=tmp_path / "exports"))
    from produzre.orchestrate.build import build_song

    res = build_song(
        cfg=cfg,
        dry_run=False,
        export_sections=False,
        export_patterns=False,
        sections_absolute_timing=False,
    )
    assert res.export_root is not None

    import pathlib
    mids = list(pathlib.Path(res.export_root).glob("*.mid"))
    assert mids, "full song MIDI should be written"

    mid = mido.MidiFile(str(mids[0]))
    ts = [
        msg
        for track in mid.tracks
        for msg in track
        if msg.type == "time_signature"
    ]
    assert ts, "no time_signature meta event found in full song MIDI"
    assert ts[0].numerator == 6
    assert ts[0].denominator == 8

    # Tempo should live on exactly one (conductor) track.
    tempo_tracks = [
        i
        for i, track in enumerate(mid.tracks)
        if any(msg.type == "set_tempo" for msg in track)
    ]
    assert tempo_tracks == [0], (
        f"set_tempo should only be on the conductor track, found on {tempo_tracks}"
    )


def test_parse_meter_defaults_to_4_4():
    from produzre.export.midi import parse_meter

    assert parse_meter("6/8") == (6, 8)
    assert parse_meter("7/8") == (7, 8)
    assert parse_meter("4/4") == (4, 4)
    assert parse_meter(None) == (4, 4)
    assert parse_meter("garbage") == (4, 4)
    assert parse_meter("0/4") == (4, 4)


# ---------------------------------------------------------------------------
# 2. No stuck notes for sub-tick durations; same-pitch de-overlap
# ---------------------------------------------------------------------------

def _track_note_balance(track):
    """Return per-(channel, pitch) running note-on/off balance violations."""
    open_notes: dict[tuple[int, int], int] = {}
    violations = []
    for msg in track:
        if msg.type == "note_on" and msg.velocity > 0:
            key = (msg.channel, msg.note)
            open_notes[key] = open_notes.get(key, 0) + 1
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            count = open_notes.get(key, 0)
            if count <= 0:
                violations.append(("orphan_off", key))
            else:
                open_notes[key] = count - 1
    stuck = [k for k, v in open_notes.items() if v > 0]
    return stuck, violations


def test_sub_tick_duration_produces_no_stuck_notes():
    from produzre.export.midi import write_timeline_to_track

    tl = InstrumentTimeline(instrument="bass")
    # Duration far below one tick (PPQ=480 → 1 tick ≈ 0.00208 beats).
    tl.add_note(start_beat=0.0, duration_beats=0.0001, pitch=40, velocity=90, channel=1)
    tl.add_note(start_beat=1.0, duration_beats=0.0005, pitch=42, velocity=90, channel=1)

    track = mido.MidiTrack()
    write_timeline_to_track(track, tl)

    stuck, violations = _track_note_balance(track)
    assert not stuck, f"stuck notes: {stuck}"
    assert not violations, f"crossed note_offs: {violations}"

    # Each note must have positive audible length (note_off strictly after note_on).
    abs_time = 0
    on_at = {}
    for msg in track:
        abs_time += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            on_at[(msg.channel, msg.note)] = abs_time
        elif msg.type == "note_off":
            start = on_at.pop((msg.channel, msg.note), None)
            assert start is not None
            assert abs_time > start, "note_off must come strictly after note_on"


def test_same_pitch_overlap_is_truncated():
    from produzre.export.midi import write_timeline_to_track

    tl = InstrumentTimeline(instrument="bass")
    # First note overlaps the second (same pitch, same channel).
    tl.add_note(start_beat=0.0, duration_beats=2.0, pitch=40, velocity=90, channel=1)
    tl.add_note(start_beat=1.0, duration_beats=1.0, pitch=40, velocity=80, channel=1)

    track = mido.MidiTrack()
    write_timeline_to_track(track, tl)

    stuck, violations = _track_note_balance(track)
    assert not stuck
    assert not violations

    # The first note must be truncated: its note_off lands at the second
    # note's start tick (480), not at tick 960.
    abs_time = 0
    events = []
    for msg in track:
        abs_time += msg.time
        if msg.type in ("note_on", "note_off"):
            events.append((abs_time, msg.type))
    assert events == [
        (0, "note_on"),
        (480, "note_off"),
        (480, "note_on"),
        (960, "note_off"),
    ]


# ---------------------------------------------------------------------------
# 3. Repeated arrangement sections export distinct files
# ---------------------------------------------------------------------------

REPEATED_SECTIONS_SONG = """
version: 1
song:
  title: "Repeats"
  bpm: 120
  key: C
  mode: aeolian
  meter: "4/4"
  beats_per_bar: 4
  seed: 1
  exports_root: "{exports_root}"
sections:
  verse1:
    type: verse
    bars: 1
    instruments:
      drums: {{}}
  chorus1:
    type: chorus
    bars: 1
    instruments:
      drums: {{}}
arrangement:
  - verse1
  - chorus1
  - verse1
"""


def test_repeated_sections_export_distinct_files(tmp_path):
    cfg = _build_yaml(
        tmp_path, REPEATED_SECTIONS_SONG.format(exports_root=tmp_path / "exports")
    )
    from produzre.orchestrate.build import build_song

    res = build_song(
        cfg=cfg,
        dry_run=False,
        export_sections=True,
        export_patterns=False,
        sections_absolute_timing=False,
    )
    assert res.export_root is not None

    import pathlib
    sections_dir = pathlib.Path(res.export_root) / "instruments" / "drums" / "sections"
    files = sorted(p.name for p in sections_dir.glob("*.mid"))
    # 3 arrangement entries -> 3 distinct files (verse1 appears twice).
    assert len(files) == 3, f"expected 3 section files, got {files}"
    verse_files = [f for f in files if "verse1" in f]
    assert len(verse_files) == 2, f"both verse1 occurrences must export: {files}"
    assert len(set(files)) == 3


# ---------------------------------------------------------------------------
# 4. Section energy override is parsed and resolved
# ---------------------------------------------------------------------------

def test_section_energy_override_parsed(tmp_path):
    song = """
version: 1
song:
  title: "Energy"
  bpm: 120
  seed: 1
sections:
  chorus1:
    type: chorus
    energy: "low"
    bars: 1
    instruments:
      drums: {}
arrangement:
  - chorus1
"""
    cfg = _build_yaml(tmp_path, song)
    from produzre.orchestrate.energy import resolve_section_energy

    sec = cfg.sections["chorus1"]
    assert sec.energy == "low"
    forced = resolve_section_energy(sec.energy, sec.type)
    auto = resolve_section_energy(None, "chorus")
    assert forced == pytest.approx(0.3)
    assert auto == pytest.approx(0.9)
    assert forced != auto


# ---------------------------------------------------------------------------
# 6. Empty-genre recipe must not outscore a genre-tagged one
# ---------------------------------------------------------------------------

def test_empty_genre_recipe_does_not_match():
    from produzre.config.recipes import _auto_select_recipe

    recipes = {
        "zz_empty": {  # lexicographically late on purpose
            "id": "zz_empty",
            "instrument": "bass",
            "tags": {"genre": "", "section_types": ["verse"], "bpm_range": [60, 200]},
            "params": {},
        },
        "rock_basic": {
            "id": "rock_basic",
            "instrument": "bass",
            "tags": {"genre": "rock"},
            "params": {},
        },
    }
    picked = _auto_select_recipe(
        genre="rock",
        section_type="verse",
        intensity=0.5,
        bpm=120.0,
        time_signature="4/4",
        recipes=recipes,
    )
    assert picked == "rock_basic"

    # An empty-genre recipe alone must yield no match at all.
    picked_none = _auto_select_recipe(
        genre="rock",
        section_type="verse",
        intensity=0.5,
        bpm=120.0,
        time_signature="4/4",
        recipes={"zz_empty": recipes["zz_empty"]},
    )
    assert picked_none is None


# ---------------------------------------------------------------------------
# 8. Major-mode presets return a major progression
# ---------------------------------------------------------------------------

def test_major_mode_preset_returns_major_progression():
    from produzre.harmony.presets import choose_progression_for_section

    for mode in ("ionian", "Ionian", "major", "MAJOR "):
        prog = choose_progression_for_section(
            song_mode=mode,
            section_type="verse",
            section_id="verse1",
            explicit=None,
            logger=logger,
        )
        # Major progression: tonic is uppercase "I", no minor "i" tonic loop.
        assert prog[0] == "I", f"mode={mode!r} produced {prog}"
        assert "bVII" not in prog, f"mode={mode!r} fell back to minor loop {prog}"


def test_minor_alias_and_unknown_mode_fallback():
    from produzre.harmony.presets import choose_progression_for_section

    minor_prog = choose_progression_for_section(
        song_mode="minor",
        section_type="verse",
        section_id="v",
        explicit=None,
        logger=logger,
    )
    assert minor_prog[0] == "i"

    # Major-ish unknown coverage: lydian has no own presets -> ionian fallback.
    lydian_prog = choose_progression_for_section(
        song_mode="lydian",
        section_type="verse",
        section_id="v",
        explicit=None,
        logger=logger,
    )
    assert lydian_prog[0] == "I"

    # Unknown mode -> minor-ish fallback (legacy behavior).
    unknown_prog = choose_progression_for_section(
        song_mode="klingon",
        section_type="verse",
        section_id="v",
        explicit=None,
        logger=logger,
    )
    assert unknown_prog[0] == "i"


# ---------------------------------------------------------------------------
# 9. Legacy section-level `progression:` synthesizes harmony
# ---------------------------------------------------------------------------

def test_legacy_progression_synthesizes_harmony(tmp_path):
    song = """
version: 1
song:
  title: "Legacy"
  bpm: 120
  key: C
  mode: aeolian
  seed: 1
sections:
  verse1:
    type: verse
    bars: 4
    progression: "i bVII VI i"
    instruments:
      drums: {}
arrangement:
  - verse1
"""
    cfg = _build_yaml(tmp_path, song)
    sec = cfg.sections["verse1"]
    assert sec.harmony is not None, "progression: should synthesize a HarmonyConfig"

    from produzre.harmony.plan import build_harmony_plan

    hplan = build_harmony_plan(cfg, sec, logger)
    assert hplan is not None
    numerals = [s.numeral for s in hplan.chord_slots]
    assert numerals[:4] == ["i", "bVII", "VI", "i"]


# ---------------------------------------------------------------------------
# 11. Arpeggiator: flat keys and flat degrees
# ---------------------------------------------------------------------------

def test_arpeggiator_flat_key_and_flat_degree_pitches():
    from produzre.engine.arpeggiator import _get_chord_tones_from_numeral

    # Eb major: tonic must be Eb (MIDI 51), not C (48).
    tones_i = _get_chord_tones_from_numeral("I", "Eb", "ionian")
    assert tones_i[0] == 51, f"Eb tonic should be MIDI 51, got {tones_i[0]}"

    # bVII in Eb: 10 semitones above the tonic (Db = 61).
    tones_bvii = _get_chord_tones_from_numeral("bVII", "Eb", "ionian")
    assert (tones_bvii[0] - 51) % 12 == 10, (
        f"bVII root should be 10 semitones above tonic, got {tones_bvii[0]}"
    )

    # Plain VII (no accidental) stays at 11 semitones.
    tones_vii = _get_chord_tones_from_numeral("VII", "Eb", "ionian")
    assert (tones_vii[0] - 51) % 12 == 11

    # Quality suffixes don't collapse to the tonic: V7 has the V root.
    tones_v7 = _get_chord_tones_from_numeral("V7", "C", "ionian")
    assert (tones_v7[0] - 48) % 12 == 7

    # Lowercase numerals are minor (minor third).
    tones_min = _get_chord_tones_from_numeral("vi", "C", "ionian")
    assert tones_min[1] - tones_min[0] == 3


def test_arpeggiator_requires_rng():
    from produzre.engine.arpeggiator import render_into_timeline

    class FakeSlot:
        numeral = "I"
        start_beat = 0.0
        end_beat = 4.0

    class FakePlan:
        chord_slots = [FakeSlot()]

    with pytest.raises(TypeError):
        render_into_timeline(
            cfg=None,
            section=None,
            harmony_plan=FakePlan(),
            rhythm_grid=None,
            section_start_beat=0.0,
            timeline=InstrumentTimeline(instrument="arpeggiator"),
            instrument_cfg={},
            rng=None,
            logger=logger,
        )


def test_arpeggiator_accepts_dict_instrument_cfg():
    from produzre.engine.arpeggiator import render_into_timeline

    class FakeSlot:
        numeral = "I"
        start_beat = 0.0
        end_beat = 1.0

    class FakePlan:
        chord_slots = [FakeSlot()]

    class FakeSong:
        key = "C"
        mode = "ionian"

    class FakeCfg:
        song = FakeSong()

    tl = InstrumentTimeline(instrument="arpeggiator")
    render_into_timeline(
        cfg=FakeCfg(),
        section=None,
        harmony_plan=FakePlan(),
        rhythm_grid=None,
        section_start_beat=0.0,
        timeline=tl,
        instrument_cfg={"intensity": 1.0, "extra": {"pattern": "down"}},
        rng=random.Random(1),
        logger=logger,
    )
    assert tl.events, "dict-shaped instrument_cfg must not be silently ignored"
    # "down" pattern: first note is the highest chord tone.
    pitches = [ev.pitch for ev in tl.events[:3]]
    assert pitches[0] == max(pitches)


# ---------------------------------------------------------------------------
# 12. Channel handling: arpeggiator no longer lands on channel 0
# ---------------------------------------------------------------------------

def test_arpeggiator_default_channel_not_zero():
    tl = InstrumentTimeline(instrument="arpeggiator")
    tl.add_note(start_beat=0.0, duration_beats=1.0, pitch=60, velocity=80)
    assert tl.events[0].channel == 6


def test_engine_spec_channel_preferred():
    tl = InstrumentTimeline(instrument="bass", default_channel=14)
    tl.add_note(start_beat=0.0, duration_beats=1.0, pitch=40, velocity=80)
    assert tl.events[0].channel == 14
    # Explicit channel still wins.
    tl.add_note(start_beat=1.0, duration_beats=1.0, pitch=40, velocity=80, channel=2)
    assert tl.events[1].channel == 2


# ---------------------------------------------------------------------------
# 13. Rhythm features: syncopation and fill windows
# ---------------------------------------------------------------------------

class _Ev:
    def __init__(self, beat, pitch, velocity=90, kind="", duration_beats=0.25):
        self.beat = beat
        self.pitch = pitch
        self.velocity = velocity
        self.kind = kind
        self.duration_beats = duration_beats


def test_syncopation_excludes_on_beat_kicks():
    from produzre.rhythm_features import extract_rhythm_features

    pitches = {"kick": 36, "snare": 38}
    events = [
        _Ev(0.0, 36),   # downbeat kick: not syncopated
        _Ev(1.0, 36),   # on-beat kick: not syncopated
        _Ev(2.0, 36),   # backbeat-position kick: not syncopated
        _Ev(2.5, 36),   # off-beat kick: syncopated
        _Ev(3.75, 36),  # off-beat kick: syncopated
    ]
    features = extract_rhythm_features(events, 4.0, 4.0, pitches)
    assert features.syncopation_beats == {2.5, 3.75}


def test_fill_window_not_fragmented_by_other_voices():
    from produzre.rhythm_features import extract_rhythm_features

    pitches = {"kick": 36, "snare": 38, "hat_closed": 42}
    events = [
        _Ev(12.0, 45, kind="fill"),
        _Ev(12.25, 42),               # interleaved hat (other voice): must NOT end the fill
        _Ev(12.5, 47, kind="fill"),
        _Ev(12.75, 42),               # another hat
        _Ev(13.0, 48, kind="fill"),
    ]
    features = extract_rhythm_features(events, 16.0, 4.0, pitches)
    assert len(features.fill_windows) == 1, (
        f"interleaved hats fragmented the fill: {features.fill_windows}"
    )
    start, end = features.fill_windows[0]
    assert start == 12.0
    assert end >= 13.0


def test_fill_window_ends_on_gap():
    from produzre.rhythm_features import extract_rhythm_features

    pitches = {"kick": 36}
    events = [
        _Ev(4.0, 45, kind="fill"),
        _Ev(4.25, 47, kind="fill"),
        # > 1 beat gap -> second window
        _Ev(8.0, 45, kind="fill"),
    ]
    features = extract_rhythm_features(events, 12.0, 4.0, pitches)
    assert len(features.fill_windows) == 2


# ---------------------------------------------------------------------------
# 14. Rhythm grid: no float drift, downbeats from below
# ---------------------------------------------------------------------------

def test_rhythm_grid_downbeats_stable_over_long_sections():
    from produzre.harmony import Meter
    from produzre.rhythm import create_basic_rhythm_grid

    meter = Meter(numerator=4, denominator=4)
    grid = create_basic_rhythm_grid(meter, total_beats=256.0, subdivision=0.25)

    downbeats = [c.beat for c in grid.cells if c.is_downbeat]
    expected = [float(b) for b in range(0, 256, 4)]
    assert downbeats == expected
    # Cells computed as idx * subdivision: exact values, no accumulation error.
    assert grid.cells[1023].beat == 255.75


# ---------------------------------------------------------------------------
# 15. RNG: stable derivation + "|" safety
# ---------------------------------------------------------------------------

def test_instrument_rng_independent_of_section_draws():
    from produzre.rng import make_section_rng, make_instrument_rng

    s1 = make_section_rng(1, 2, 0, "verse1", "verse")
    s2 = make_section_rng(1, 2, 0, "verse1", "verse")
    # Draw from one section RNG before deriving: must not reshuffle children.
    s2.random()
    r1 = make_instrument_rng(s1, "bass")
    r2 = make_instrument_rng(s2, "bass")
    assert [r1.random() for _ in range(4)] == [r2.random() for _ in range(4)]


def test_instrument_rng_streams_differ_per_instrument():
    from produzre.rng import make_section_rng, make_instrument_rng

    s = make_section_rng(1, 2, 0, "verse1", "verse")
    r_bass = make_instrument_rng(s, "bass")
    r_drums = make_instrument_rng(s, "drums")
    assert r_bass.random() != r_drums.random()


def test_stable_seed_int_pipe_safety():
    from produzre.rng import stable_seed_int

    assert stable_seed_int("a|b") != stable_seed_int("a", "b")
    assert stable_seed_int("a", "b|c") != stable_seed_int("a|b", "c")
    # Determinism is preserved.
    assert stable_seed_int("x", 1, "y") == stable_seed_int("x", 1, "y")


# ---------------------------------------------------------------------------
# 7. Transitions map keyed per arrangement occurrence
# ---------------------------------------------------------------------------

def test_transitions_map_per_occurrence_keys():
    from produzre.orchestrate.transitions import (
        build_section_transitions_map,
        get_section_transition,
        serialize_section_transitions_map,
        transition_occurrence_key,
    )

    class FakeSec:
        def __init__(self, sec_type):
            self.type = sec_type

    class FakePS:
        def __init__(self, sec_id, sec_type):
            self.sec_id = sec_id
            self.sec = FakeSec(sec_type)

    planned = [
        FakePS("verse1", "verse"),
        FakePS("chorus1", "chorus"),
        FakePS("verse1", "verse"),  # repeated
    ]
    tmap = build_section_transitions_map(planned)

    first = get_section_transition(tmap, "verse1", arrangement_index=0)
    last = get_section_transition(tmap, "verse1", arrangement_index=2)
    assert first is not None and last is not None
    # First verse leads into the chorus; last verse ends the song.
    assert first.next_section_id == "chorus1"
    assert last.next_section_id is None
    assert last.is_last_section

    # Legacy bare-id lookup still works (last occurrence).
    legacy = get_section_transition(tmap, "verse1")
    assert legacy is last

    serialized = serialize_section_transitions_map(tmap)
    assert transition_occurrence_key(0, "verse1") in serialized
    assert "verse1" in serialized
    # Aliased keys share one dict so feedback mutations stay consistent.
    assert serialized["verse1"] is serialized[transition_occurrence_key(2, "verse1")]


# ---------------------------------------------------------------------------
# 5. Section meter/key/mode fall back to song values in SectionMeta
# ---------------------------------------------------------------------------

def test_section_meta_falls_back_to_song_meter(tmp_path):
    cfg = _build_yaml(tmp_path, MINIMAL_68_SONG.format(exports_root=tmp_path / "exports"))
    from produzre.orchestrate.build import build_song

    res = build_song(
        cfg=cfg,
        dry_run=True,
        export_sections=False,
        export_patterns=False,
        sections_absolute_timing=False,
    )
    meta = res.performance_plan.sections[0]
    assert meta.meter == "6/8"  # not None
    assert meta.key == "C"
    assert meta.mode == "ionian"


# ---------------------------------------------------------------------------
# 18. Stale harmony.plan must not satisfy dependency validation
# ---------------------------------------------------------------------------

def test_harmony_plan_cleared_between_sections(tmp_path):
    # Section 2 declares bass (requires harmony.plan) but no harmony.
    # With the stale-plan bug, the previous section's harmony.plan would
    # satisfy validation; now it must raise a ConfigError.
    song = """
version: 1
song:
  title: "StalePlan"
  bpm: 120
  key: C
  mode: aeolian
  seed: 1
sections:
  verse1:
    type: verse
    bars: 1
    harmony: {}
    instruments:
      drums: {}
      harmony: {}
      bass: {}
  nakedbass:
    type: chorus
    bars: 1
    instruments:
      bass: {}
arrangement:
  - verse1
  - nakedbass
"""
    cfg = _build_yaml(tmp_path, song)
    from produzre.config.errors import ConfigError
    from produzre.orchestrate.build import build_song

    with pytest.raises(ConfigError, match="harmony.plan"):
        build_song(
            cfg=cfg,
            dry_run=True,
            export_sections=False,
            export_patterns=False,
            sections_absolute_timing=False,
        )
