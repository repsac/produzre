import random

from produzre.engine.acoustic_gtr import _render_fingerpicking
from produzre.engine.acoustic_gtr.params import AcousticGuitarParams
from produzre.engine.arpeggiator import render_into_timeline as render_arpeggiator
from produzre.engine.arpeggiator import _get_chord_tones_from_numeral
from produzre.harmony.plan import ChordSlot
from produzre.harmony.meter import Meter
from produzre.harmony.plan import HarmonySectionPlan
from produzre.engine.harmony import _serialize_harmony_plan
from produzre.melody import (
    build_melody_guide,
    chord_pitch_classes,
    guide_pitch_at,
)
from produzre.timeline import InstrumentTimeline


class _Harmony:
    section_id = "verse"
    chord_slots = [
        ChordSlot(0, "i", 0.0, 4.0),
        ChordSlot(1, "VI", 4.0, 8.0),
        ChordSlot(2, "III", 8.0, 12.0),
        ChordSlot(3, "V7", 12.0, 16.0),
    ]


def _guide(seed=7, section_type="verse"):
    return build_melody_guide(
        _Harmony(), key="D", mode="minor", section_type=section_type,
        genre="cinematic", rng=random.Random(seed),
    )


def test_melody_guide_is_deterministic_voice_led_and_cadential():
    first = _guide().to_dict()
    second = _guide().to_dict()
    assert first == second

    pitches = [target["pitch"] for target in first["targets"]]
    assert max(abs(b - a) for a, b in zip(pitches, pitches[1:])) <= 7

    cadence = first["targets"][-1]
    assert cadence["cadence"] is True
    assert cadence["role"] == "root"
    assert cadence["pitch"] % 12 == chord_pitch_classes("V7", "D", "minor")[0]


def test_melody_guide_changes_with_seed_and_section_shape():
    verse = _guide(seed=2, section_type="verse").to_dict()
    chorus = _guide(seed=3, section_type="chorus").to_dict()
    assert [t["pitch"] for t in verse["targets"]] != [t["pitch"] for t in chorus["targets"]]


def test_guide_pitch_fits_instrument_register_near_previous_note():
    guide = _guide().to_dict()
    pitch = guide_pitch_at(guide, 6.0, 55, 67, previous=61)
    assert pitch is not None
    assert 55 <= pitch <= 67
    assert pitch % 12 in {target["pitch"] % 12 for target in guide["targets"]}


def test_harmony_export_identifies_function_and_cadence_slots():
    harmony = HarmonySectionPlan(
        section_id="verse", meter=Meter(4, 4), total_beats=16.0, chord_rate=4.0,
        chord_slots=_Harmony.chord_slots,
    )
    slots = _serialize_harmony_plan(harmony)["chord_slots"]
    assert [slot["function"] for slot in slots] == [
        "tonic", "tonic", "tonic", "dominant",
    ]
    assert slots[-1]["is_phrase_end"] is True
    assert slots[-1]["is_section_cadence"] is True
    assert all(not slot["is_section_cadence"] for slot in slots[:-1])


class _Profile:
    num_strings = 6


class _Voicing:
    profile = _Profile()
    played_strings = (0, 1, 2, 3, 4, 5)
    pitches = [52, 59, 64, 67, 71, 76]

    def pitch_for_string(self, string):
        return self.pitches[string]


def test_fingerstyle_uses_guide_as_moving_top_voice():
    params = AcousticGuitarParams(
        technique="fingerpicking", picking_pattern="cinematic",
        strum_density=0.5, mute_ratio=0.0, body_tap_ratio=0.0,
        melody_amount=1.0, phrase_variation=0.0,
        voicing_style="open", capo=0, intensity=0.6, base_vel=70,
        vel_variation=0, timing_variation=0.0, offset_beats=0.0,
        section_type="verse", beats_per_bar=4.0,
    )
    timeline = InstrumentTimeline(instrument="acoustic_gtr")
    _render_fingerpicking(
        params, _Harmony(), {slot.numeral: _Voicing() for slot in _Harmony.chord_slots},
        0.0, 16.0, 4.0, timeline, random.Random(5), set(), _guide().to_dict(),
    )

    melody_notes = [event.pitch for event in timeline.events if event.kind == "acoustic_melody"]
    assert len(melody_notes) >= 4
    assert len(set(melody_notes)) >= 3
    assert max(abs(b - a) for a, b in zip(melody_notes, melody_notes[1:])) <= 12


def test_phrase_arpeggiator_changes_direction_and_marks_melodic_apex():
    class Song:
        key = "D"
        mode = "minor"

    class Config:
        song = Song()

    class Section:
        id = "verse"
        key = None
        mode = None

    class Plan:
        def get(self, key, default=None):
            return _guide().to_dict() if key.startswith("melody.guide") else default

    timeline = InstrumentTimeline(instrument="arpeggiator")
    render_arpeggiator(
        cfg=Config(), section=Section(), harmony_plan=_Harmony(), rhythm_grid=None,
        section_start_beat=0.0, timeline=timeline, rng=random.Random(9), plan=Plan(),
        instrument_cfg={"intensity": 0.7, "extra": {"pattern": "phrase", "note_duration": 0.5}},
    )
    first_slot = [e.pitch for e in timeline.events if 0.0 <= e.start_beat < 4.0]
    second_slot = [e.pitch for e in timeline.events if 4.0 <= e.start_beat < 8.0]
    assert first_slot != second_slot
    assert any(event.kind == "arpeggio_apex" for event in timeline.events)


def test_arpeggiator_chords_follow_mode_and_quality_suffixes():
    # VI in D natural minor is Bb, not the B produced by a major-only parser.
    vi = _get_chord_tones_from_numeral("VI", "D", "minor")
    assert vi[0] % 12 == 10
    dominant = _get_chord_tones_from_numeral("V7", "D", "minor")
    assert len(dominant) == 4
    assert (dominant[-1] - dominant[0]) % 12 == 10
