"""Tests for the theme bank system (produzre/themes/).

Covers the design doc (docs/design/theme-bank-architecture.md) milestones:
  M1: parsing, model, transforms, realization
  M2: themed melody guide + lead quoting (integration)
  M3: rhythm-section coupling (integration via strict determinism)
  M4: auto-composition determinism and identity semantics

Unit tests build themes/chord slots directly (no filesystem).
Integration tests build examples/themes_demo.yaml via the CLI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from produzre.config.errors import ConfigError
from produzre.harmony.plan import ChordSlot
from produzre.themes.compose import compose_theme_bank
from produzre.themes.io import parse_themes_block
from produzre.themes.model import Theme, ThemeEvent, ThemeRole
from produzre.themes.realize import degree_to_pitch_class, realize_theme
from produzre.themes.transform import (
    apply_transform, displace, fragment, invert, octave_shift, sequence, thin,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slots(spec: str, rate: float = 4.0):
    """Build chord slots from 'I IV V I' at `rate` beats per chord."""
    out, beat = [], 0.0
    for i, num in enumerate(spec.split()):
        out.append(ChordSlot(index=i, numeral=num, start_beat=beat, end_beat=beat + rate))
        beat += rate
    return out


def one_note_theme(degree=1, acc=0, length=4.0):
    return Theme(
        name="t", role=ThemeRole.MELODY, length_beats=length,
        events=(ThemeEvent(0.0, 1.0, degree, acc),), base_register=(60, 72),
    )


def compose_cfg(seed=42, take=0, genre="rock"):
    return SimpleNamespace(
        song=SimpleNamespace(genre=genre, key="E", mode="ionian",
                             seed=seed, take=take, beats_per_bar=4),
    )


# ---------------------------------------------------------------------------
# M1: parsing
# ---------------------------------------------------------------------------

class TestParsing:
    def test_shorthand_events(self):
        bank = parse_themes_block({"riff": {"role": "riff", "events": "1:.5 b3:.5 .:.5 5:1"}})
        t = bank.themes["riff"]
        assert t.role is ThemeRole.RIFF
        assert t.length_beats == 2.5
        degs = [e.degree for e in t.events]
        assert degs == [1, 3, None, 5]
        assert t.events[1].accidental == -1
        assert "user" in t.tags

    def test_degrees_rhythm_lists(self):
        bank = parse_themes_block({
            "hook": {"role": "melody", "degrees": ["5", "b3", "1+"], "rhythm": [1, 1, 2]}
        })
        t = bank.themes["hook"]
        assert [e.degree for e in t.events] == [5, 3, 1]
        assert t.events[1].accidental == -1
        assert t.events[2].octave == 1

    def test_length_mismatch_rejected(self):
        with pytest.raises(ConfigError):
            parse_themes_block({"t": {"events": "1:1", "length_beats": 5}})

    def test_bad_token_rejected(self):
        with pytest.raises(ConfigError):
            parse_themes_block({"t": {"events": "1:.5 bogus:2"}})

    def test_all_rests_rejected(self):
        with pytest.raises(ConfigError):
            parse_themes_block({"t": {"events": ".:1 .:1"}})

    def test_locked_when_development_disabled(self):
        bank = parse_themes_block({"t": {"events": "1:4", "allow_development": False}})
        assert "locked" in bank.themes["t"].tags

    def test_empty_block_finalizes(self):
        assert parse_themes_block(None).themes == {}

    def test_bank_hash_stable(self):
        spec = {"riff": {"role": "riff", "events": "1:.5 b3:.5 4:1"}}
        assert parse_themes_block(spec).seed_material_hash == parse_themes_block(spec).seed_material_hash


# ---------------------------------------------------------------------------
# M1: transforms
# ---------------------------------------------------------------------------

class TestTransforms:
    base = Theme(
        name="t", role=ThemeRole.MELODY, length_beats=4.0,
        events=(
            ThemeEvent(0.0, 1.0, 1),
            ThemeEvent(1.5, 0.5, 3, -1),
            ThemeEvent(2.0, 1.0, 5),
            ThemeEvent(3.0, 1.0, 7),
        ),
    )

    def test_sequence_with_octave_carry(self):
        t = sequence(self.base, steps=3)
        assert [e.degree for e in t.events] == [4, 6, 1, 3]
        assert t.events[2].octave == 1  # 5 + 3 wraps past the octave
        assert t.events[1].accidental == -1  # accidentals preserved

    def test_invert_mirrors_around_first_degree(self):
        t = invert(self.base)
        # anchor = degree 1 (idx 0): 1->1, b3->b6 below, 5->4 below, 7->2 below
        assert [(e.degree, e.octave, e.accidental) for e in t.events] == [
            (1, 0, 0), (6, -1, -1), (4, -1, 0), (2, -1, 0),
        ]

    def test_fragment_first_and_last(self):
        first = fragment(self.base, keep="first", beats=2.0)
        assert [e.degree for e in first.events] == [1, 3]
        last = fragment(self.base, keep="last", beats=2.0)
        assert [e.degree for e in last.events] == [5, 7]
        assert last.events[0].offset_beats == 0.0  # re-based

    def test_displace_rotates_within_length(self):
        t = displace(self.base, shift_beats=1.0)
        assert [e.offset_beats for e in t.events] == [0.0, 1.0, 2.5, 3.0]
        assert [e.degree for e in t.events] == [7, 1, 3, 5]

    def test_thin_keeps_downbeats(self):
        t = thin(self.base)
        assert [e.offset_beats for e in t.events] == [0.0, 2.0, 3.0]

    def test_octave_shift(self):
        t = octave_shift(self.base, octaves=1)
        assert all(e.octave == 1 for e in t.events)

    def test_unknown_transform_raises(self):
        with pytest.raises(KeyError):
            apply_transform(self.base, "bogus")


# ---------------------------------------------------------------------------
# M1: realization
# ---------------------------------------------------------------------------

class TestRealize:
    def test_degree_mapping_c_major(self):
        assert degree_to_pitch_class(1, 0, "C", "major") == 0
        assert degree_to_pitch_class(3, -1, "C", "major") == 3   # Eb
        assert degree_to_pitch_class(7, 0, "E", "ionian") == 3   # D#

    def test_semitone_clash_snaps_to_chord_tone(self):
        # F (deg 4) over I (C E G) snaps to E.
        notes = realize_theme(one_note_theme(degree=4), slots("I"), key="C", mode="major")
        assert notes[0].pitch % 12 == 4
        assert notes[0].snapped

    def test_color_tone_survives_in_rock(self):
        # b3 over I stays put in rock (blue note), snaps in classical.
        rock = realize_theme(one_note_theme(degree=3, acc=-1), slots("I"),
                             key="C", mode="major", genre="rock")
        assert rock[0].pitch % 12 == 3 and not rock[0].snapped
        plain = realize_theme(one_note_theme(degree=3, acc=-1), slots("I"),
                              key="C", mode="major", genre="classical")
        assert plain[0].snapped

    def test_theme_tracks_chord_changes(self):
        # Degree 1 (C) over IV (F A C) is a chord tone; over G7... stays C.
        theme = one_note_theme(degree=1)
        notes = realize_theme(theme, slots("I bVII"), key="C", mode="major")
        assert notes[0].numeral == "I"
        assert notes[1].numeral == "bVII"

    def test_loops_to_cover_section(self):
        notes = realize_theme(one_note_theme(), slots("I IV V"), key="C", mode="major")
        assert len(notes) == 3
        assert [n.occurrence for n in notes] == [0, 1, 2]
        assert notes[-1].beat == 8.0

    def test_register_and_voice_leading(self):
        notes = realize_theme(one_note_theme(degree=1), slots("I"), key="C", mode="major")
        assert 60 <= notes[0].pitch <= 72

    def test_pure_function_no_rng(self):
        a = realize_theme(one_note_theme(5), slots("I IV"), key="C", mode="major")
        b = realize_theme(one_note_theme(5), slots("I IV"), key="C", mode="major")
        assert a == b


# ---------------------------------------------------------------------------
# M4: auto-composition
# ---------------------------------------------------------------------------

class TestCompose:
    def test_same_seed_same_bank(self):
        assert (compose_theme_bank(compose_cfg()).seed_material_hash
                == compose_theme_bank(compose_cfg()).seed_material_hash)

    def test_different_seed_different_bank(self):
        assert (compose_theme_bank(compose_cfg(seed=1)).seed_material_hash
                != compose_theme_bank(compose_cfg(seed=2)).seed_material_hash)

    def test_take_preserves_identity(self):
        assert (compose_theme_bank(compose_cfg(take=0)).seed_material_hash
                == compose_theme_bank(compose_cfg(take=9)).seed_material_hash)

    def test_hook_question_answer_cadence(self):
        bank = compose_theme_bank(compose_cfg())
        hook = bank.themes["auto_hook"]
        half = len(hook.events) // 2
        assert hook.events[half - 1].degree in (2, 5)   # half cadence
        assert hook.events[-1].degree == 1              # full cadence
        # consequent repeats the antecedent rhythm
        ant_rhythm = [e.duration_beats for e in hook.events[:half]]
        con_rhythm = [e.duration_beats for e in hook.events[half:]]
        assert ant_rhythm == con_rhythm

    def test_riff_closes_on_tonic(self):
        bank = compose_theme_bank(compose_cfg())
        riff = bank.themes["auto_riff"]
        assert riff.events[-1].degree == 1


# ---------------------------------------------------------------------------
# M2/M3: integration via CLI build of the themed demo song
# ---------------------------------------------------------------------------

def _build(args):
    return subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", *args],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )


@pytest.mark.integration
class TestThemedBuild:
    def test_demo_builds_with_strict_determinism(self):
        result = _build(["examples/themes_demo.yaml", "--strict-determinism"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Determinism check PASSED" in result.stderr

    def test_demo_uses_themed_guide_and_coupling(self):
        result = _build(["examples/themes_demo.yaml"])
        assert result.returncode == 0, result.stderr[-2000:]
        # Themed melody guide engaged in every section.
        assert result.stderr.count("melody guide from theme") == 6

    def test_themes_auto_false_disables_themes(self, tmp_path):
        src = (REPO_ROOT / "examples" / "themes_demo.yaml").read_text(encoding="utf-8")
        src = src.replace("seed: 7", "seed: 7\n  themes_auto: false", 1)
        # No authored themes either: strip the whole block for a pure legacy run.
        start = src.index("themes:")
        end = src.index("sections:")
        src = src[:start] + src[end:]
        cfg_path = tmp_path / "no_themes.yaml"
        cfg_path.write_text(src, encoding="utf-8")
        result = _build([str(cfg_path)])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "melody guide from theme" not in result.stderr
        assert "Auto-composed" not in result.stderr
