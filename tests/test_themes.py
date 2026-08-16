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
from produzre.themes.coupling import get_theme_notes
from produzre.themes.groove import realize_groove
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


# ---------------------------------------------------------------------------
# M4b: bass_motif coupling (bass quotes the motif's pitches and rhythm)
# ---------------------------------------------------------------------------

class TestCouplingHelpers:
    def test_get_theme_notes_sorted_pairs(self):
        plan = {"themes.realized.s1": {"bass_motif": [
            {"beat": 2.0, "pitch": 45},
            {"beat": 0.5, "pitch": 40},
        ]}}
        assert get_theme_notes(plan, "s1") == [(0.5, 40), (2.0, 45)]

    def test_get_theme_notes_missing(self):
        assert get_theme_notes(None, "s1") == []
        assert get_theme_notes({}, "s1") == []
        assert get_theme_notes({"themes.realized.s1": {}}, "s1") == []


MOTIF_YAML = """\
version: 1
song:
  title: "MotifQuote"
  bpm: 100
  key: E
  mode: ionian
  meter: "4/4"
  genre: rock
  seed: 11
  exports_root: "{exports_root}"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
themes:
  bass_hook:
    role: bass_motif
    allow_development: false
    register: [36, 52]
    events: "1:.5 1:.5 b3:.5 5:.5 4:1 b3:1"
sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I I IV I"
    instruments:
      harmony: {{}}
      bass:
        intensity: 0.8
        params:
          rhythm_pattern: drive
          density: 0.9
          rest_rate: 0.0
          motif_quote_rate: {rate}
arrangement:
  - verse
"""


def _write_motif_cfg(tmp_path, rate):
    cfg_path = tmp_path / "motif.yaml"
    cfg_path.write_text(
        MOTIF_YAML.format(exports_root=(tmp_path / "exports").as_posix(), rate=rate),
        encoding="utf-8",
    )
    return cfg_path


def _read_bass_rows(exports_root: Path):
    tsvs = list(exports_root.glob("*/analysis/bass/*_bass.events.tsv"))
    assert tsvs, "no bass events export found"
    lines = tsvs[0].read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]


@pytest.mark.integration
class TestBassMotifCoupling:
    def test_full_quote_rate_matches_motif_pitches(self, tmp_path):
        result = _build([str(_write_motif_cfg(tmp_path, 1.0))])
        assert result.returncode == 0, result.stderr[-2000:]
        rows = _read_bass_rows(tmp_path / "exports")
        motif_rows = [r for r in rows if r["kind"] == "motif"]
        # 24 looped motif notes over 4 bars; most should land under rate 1.0.
        assert len(motif_rows) >= 12

        # Expected pitches: realize the same theme through the same pipeline.
        theme = parse_themes_block({
            "bass_hook": {
                "role": "bass_motif",
                "register": [36, 52],
                "events": "1:.5 1:.5 b3:.5 5:.5 4:1 b3:1",
            }
        }).themes["bass_hook"]
        expected = realize_theme(
            theme, slots("I I IV I", rate=4.0), key="E", mode="ionian", genre="rock",
        )
        pc_by_beat = {round(n.beat, 3): n.pitch % 12 for n in expected}
        for r in motif_rows:
            beat = round(float(r["start_beat_abs"]), 3)
            assert int(r["pitch"]) % 12 == pc_by_beat[beat]

    def test_zero_quote_rate_no_motif_notes(self, tmp_path):
        result = _build([str(_write_motif_cfg(tmp_path, 0.0))])
        assert result.returncode == 0, result.stderr[-2000:]
        rows = _read_bass_rows(tmp_path / "exports")
        assert rows and all(r["kind"] != "motif" for r in rows)

    def test_motif_build_strictly_deterministic(self, tmp_path):
        result = _build([str(_write_motif_cfg(tmp_path, 0.7)), "--strict-determinism"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Determinism check PASSED" in result.stderr


# ---------------------------------------------------------------------------
# M4c: drum_groove themes (the kit pattern itself is thematic)
# ---------------------------------------------------------------------------

class TestGrooveRealize:
    def test_degrees_map_to_voices(self):
        theme = Theme(
            name="g", role=ThemeRole.DRUM_GROOVE, length_beats=4.0,
            events=(
                ThemeEvent(0.0, 1.0, 1),    # kick
                ThemeEvent(1.0, 1.0, 2),    # snare
                ThemeEvent(2.0, 0.5, 3),    # hat
                ThemeEvent(2.5, 0.5, 3),    # hat
                ThemeEvent(3.0, 1.0, 6),    # ride
            ),
        )
        g = realize_groove(theme, "quote", {}, 4.0)
        assert g["kick"] == [0.0]
        assert g["snare"] == [1.0]
        assert g["hat"] == [2.0, 2.5]
        assert g["ride"] == [3.0]

    def test_loops_to_cover_section(self):
        theme = Theme(
            name="g", role=ThemeRole.DRUM_GROOVE, length_beats=4.0,
            events=(ThemeEvent(0.0, 1.0, 1), ThemeEvent(2.0, 1.0, 1)),
        )
        g = realize_groove(theme, "quote", {}, 12.0)
        assert g["kick"] == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]

    def test_accent_degrees_map_and_rests_skipped(self):
        theme = Theme(
            name="g", role=ThemeRole.DRUM_GROOVE, length_beats=2.0,
            events=(
                ThemeEvent(0.0, 0.5, 4),     # open hat
                ThemeEvent(0.5, 0.5, None),  # rest
                ThemeEvent(1.0, 0.5, 5),     # crash
                ThemeEvent(1.5, 0.5, 7),     # tom
            ),
        )
        assert realize_groove(theme, "quote", {}, 2.0) == {
            "kick": [], "snare": [], "hat": [], "open_hat": [0.0],
            "crash": [1.0], "ride": [], "tom": [1.5],
        }

    def test_arc_transforms_apply(self):
        theme = Theme(
            name="g", role=ThemeRole.DRUM_GROOVE, length_beats=4.0,
            events=(
                ThemeEvent(0.0, 1.0, 1),
                ThemeEvent(0.5, 0.5, 3),
                ThemeEvent(1.0, 1.0, 2),
                ThemeEvent(1.5, 0.5, 3),
            ),
        )
        thinned = realize_groove(theme, "thin", {}, 4.0)
        assert thinned["kick"] == [0.0]
        assert thinned["snare"] == [1.0]
        assert thinned["hat"] == []          # off-beat hats removed
        displaced = realize_groove(theme, "displace", {"shift_beats": 1.0}, 4.0)
        assert displaced["kick"] == [1.0]

    def test_pure_function(self):
        theme = Theme(
            name="g", role=ThemeRole.DRUM_GROOVE, length_beats=2.0,
            events=(ThemeEvent(0.0, 1.0, 1),),
        )
        assert realize_groove(theme, "quote", {}, 8.0) == realize_groove(theme, "quote", {}, 8.0)


GROOVE_YAML = """\
version: 1
song:
  title: "GrooveTheme"
  bpm: 110
  key: E
  mode: ionian
  meter: "4/4"
  genre: rock
  seed: 5
  exports_root: "{exports_root}"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
themes:
  kit_groove:
    role: drum_groove
    allow_development: false
    events: "1:.5 3:.5 2:.5 3:.5 1:.5 3:.5 2:.5 3:.5 1:1 3:.5 2:.5 5:.5 1:.5 4:.25 7:.25 2:.5"
sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I I I I"
    instruments:
      harmony: {{}}
      drums:
        intensity: 0.7
        params:
          groove_strength: {strength}
          fill_rate: 0.0  # fills duck hats; keep the pattern assertion surgical
arrangement:
  - verse
"""


def _write_groove_cfg(tmp_path, strength):
    cfg_path = tmp_path / "groove.yaml"
    cfg_path.write_text(
        GROOVE_YAML.format(exports_root=(tmp_path / "exports").as_posix(), strength=strength),
        encoding="utf-8",
    )
    return cfg_path


def _drum_tsv_path(exports_root: Path):
    tsvs = list(exports_root.glob("*/analysis/drums/*_drums.events.tsv"))
    assert tsvs, "no drums events export found"
    return tsvs[0]


def _read_drum_rows(exports_root: Path):
    lines = _drum_tsv_path(exports_root).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]


@pytest.mark.integration
class TestDrumGrooveCoupling:
    # The 2-bar groove theme quantizes to (section-relative, per bar):
    #   theme bar 1 (bars 1,3): kick {0, 2}    snare {1, 3}     hats {0.5, 1.5, 2.5, 3.5}
    #   theme bar 2 (bars 2,4): kick {0, 2.5}  snare {1.5, 3.5} hat line {1.0, 3.0}
    #                           crash @2.0  open hat @3.0  tom @3.25
    @staticmethod
    def _expected(bar_index: int):
        if bar_index % 2 == 0:
            return {"kick": [0.0, 2.0], "snare": [1.0, 3.0],
                    "hat": [0.5, 1.5, 2.5, 3.5]}
        return {"kick": [0.0, 2.5], "snare": [1.5, 3.5], "hat": [1.0, 3.0]}

    @staticmethod
    def _has_hit(rows, pitches, abs_beat):
        return any(
            int(r["pitch"]) in pitches
            and abs(float(r["start_beat_abs"]) - abs_beat) < 0.13
            for r in rows
        )

    def test_theme_owns_the_kit_pattern(self, tmp_path):
        result = _build([str(_write_groove_cfg(tmp_path, 1.0))])
        assert result.returncode == 0, result.stderr[-2000:]
        rows = _read_drum_rows(tmp_path / "exports")
        assert rows
        for bar in range(4):
            expected = self._expected(bar)
            base = bar * 4.0
            for b in expected["kick"]:
                assert self._has_hit(rows, {36}, base + b), \
                    f"kick missing at bar {bar + 1} beat {b}"
            for b in expected["snare"]:
                assert self._has_hit(rows, {37, 38, 40}, base + b), \
                    f"snare missing at bar {bar + 1} beat {b}"
            for b in expected["hat"]:
                assert self._has_hit(rows, {42, 46, 51}, base + b), \
                    f"hat missing at bar {bar + 1} beat {b}"
            if bar % 2 == 1:
                # Theme bar 2 accent voices (injected alongside the pattern).
                assert self._has_hit(rows, {49}, base + 2.0), \
                    f"crash missing at bar {bar + 1} beat 2.0"
                assert self._has_hit(rows, {46}, base + 3.0), \
                    f"open hat missing at bar {bar + 1} beat 3.0"
                assert self._has_hit(rows, {45, 47, 50}, base + 3.25), \
                    f"tom missing at bar {bar + 1} beat 3.25"

    def test_groove_strength_zero_keeps_genre_pattern(self, tmp_path):
        on_dir = tmp_path / "on"
        off_dir = tmp_path / "off"
        on_dir.mkdir()
        off_dir.mkdir()
        r_on = _build([str(_write_groove_cfg(on_dir, 1.0))])
        r_off = _build([str(_write_groove_cfg(off_dir, 0.0))])
        assert r_on.returncode == 0, r_on.stderr[-2000:]
        assert r_off.returncode == 0, r_off.stderr[-2000:]
        text_on = _drum_tsv_path(on_dir / "exports").read_text(encoding="utf-8")
        text_off = _drum_tsv_path(off_dir / "exports").read_text(encoding="utf-8")
        assert text_on != text_off

    def test_groove_build_strictly_deterministic(self, tmp_path):
        result = _build([str(_write_groove_cfg(tmp_path, 1.0)), "--strict-determinism"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Determinism check PASSED" in result.stderr


GROOVE_DRUMS_ONLY_YAML = """\
version: 1
song:
  title: "GrooveDrumsOnly"
  bpm: 110
  key: E
  mode: ionian
  meter: "4/4"
  genre: rock
  seed: 5
  exports_root: "{exports_root}"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
themes:
  kit_groove:
    role: drum_groove
    allow_development: false
    events: "1:.5 3:.5 2:.5 3:.5 1:.5 3:.5 2:.5 3:.5 1:1 3:.5 2:.5 5:.5 1:.5 4:.25 7:.25 2:.5"
sections:
  break:
    type: verse
    bars: 2
    instruments:
      drums:
        intensity: 0.7
        params:
          fill_rate: 0.0
arrangement:
  - break
"""


@pytest.mark.integration
class TestDrumGrooveDrumsOnly:
    """A drum_groove theme is rhythm + voice: it must apply even in sections
    with no harmony plan (drums-only breaks), taking the section length from
    bars x meter instead of the harmony plan."""

    def test_groove_applies_without_harmony_plan(self, tmp_path):
        cfg_path = tmp_path / "drums_only.yaml"
        cfg_path.write_text(
            GROOVE_DRUMS_ONLY_YAML.format(
                exports_root=(tmp_path / "exports").as_posix()
            ),
            encoding="utf-8",
        )
        result = _build([str(cfg_path)])
        assert result.returncode == 0, result.stderr[-2000:]
        rows = _read_drum_rows(tmp_path / "exports")
        assert rows

        def has(pitches, abs_beat):
            return TestDrumGrooveCoupling._has_hit(rows, pitches, abs_beat)

        # The 2-bar theme's kit steps squash into the per-bar template
        # (union semantics, same as harmony-backed sections): a bar-2-only
        # onset like the kick at 2.5 or the snare at 1.5 proves the theme
        # reached the engine.
        assert has({36}, 0.0), "theme kick missing at beat 0"
        assert has({36}, 2.5), "theme kick missing at beat 2.5"
        assert has({37, 38, 40}, 1.5), "theme snare missing at beat 1.5"
        # Accent voices: open hat forced on theme bar 2's step-12 onset
        # (lands in both bars via the union), crash and tom injected.
        assert has({46}, 3.0), "open hat missing at beat 3.0"
        assert has({46}, 7.0), "open hat missing at beat 7.0"
        assert has({49}, 6.0), "crash missing at beat 6.0"
        assert has({45, 47, 50}, 7.25), "tom missing at beat 7.25"

    def test_drums_only_groove_strictly_deterministic(self, tmp_path):
        cfg_path = tmp_path / "drums_only.yaml"
        cfg_path.write_text(
            GROOVE_DRUMS_ONLY_YAML.format(
                exports_root=(tmp_path / "exports").as_posix()
            ),
            encoding="utf-8",
        )
        result = _build([str(cfg_path), "--strict-determinism"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Determinism check PASSED" in result.stderr


# ---------------------------------------------------------------------------
# Lead presence: quoted hooks sustain and sit above the band
# ---------------------------------------------------------------------------

LEAD_YAML = """\
version: 1
song:
  title: "LeadPresence"
  bpm: 120
  key: E
  mode: ionian
  meter: "4/4"
  genre: rock
  seed: 7
  exports_root: "{exports_root}"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
themes:
  chorus_hook:
    role: melody
    allow_development: false
    register: [64, 79]
    events: "5:.5 5:.5 6:.5 5:.5 4:1 b3:.5 2:.5 1:4"
sections:
  chorus:
    type: chorus
    bars: 8
    harmony:
      progression: "bVI bVII I I"
    instruments:
      harmony: {{}}
      lead_gtr:
        intensity: 0.9
        extra:
          theme_quote_rate: 1.0
arrangement:
  - chorus
"""


@pytest.mark.integration
class TestLeadPresence:
    def _build_lead(self, tmp_path):
        cfg_path = tmp_path / "lead.yaml"
        cfg_path.write_text(
            LEAD_YAML.format(exports_root=(tmp_path / "exports").as_posix()),
            encoding="utf-8",
        )
        result = _build([str(cfg_path)])
        assert result.returncode == 0, result.stderr[-2000:]
        tsvs = list((tmp_path / "exports").glob("*/analysis/lead_gtr/*_lead_gtr.events.tsv"))
        assert tsvs, "no lead events export found"
        lines = tsvs[0].read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        return [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]

    def test_quoted_hook_sustains_long_notes(self, tmp_path):
        rows = self._build_lead(tmp_path)
        assert rows
        durs = [float(r["duration_beats"]) for r in rows]
        # The hook ends on a 4-beat tonic; quoting adopts theme durations, so
        # the money note must survive articulation instead of being chopped.
        assert max(durs) >= 3.0, f"longest lead note is {max(durs):.2f} beats"

    def test_lead_sits_above_the_band(self, tmp_path):
        rows = self._build_lead(tmp_path)
        vels = sorted(int(r["velocity"]) for r in rows)
        median = vels[len(vels) // 2]
        assert median >= 85, f"lead median velocity {median} (was ~72 pre-fix)"
        assert vels[-1] >= 100
