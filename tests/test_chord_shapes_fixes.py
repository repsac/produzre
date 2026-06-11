"""Regression tests for verified guitar bugs (2026-06-10 full review).

Covers:
  Theme 2.4 — chord shape / voicing bugs in produzre/instruments/chord_shapes.py:
    - D-form movable shapes had wrong intervals (maj7 + minor 10th!)
    - Voice-leading octave shift corrupted barre chords (negative frets)
    - Capo discarded by the open-shape path (capo=2 played a whole step flat)
    - Fallback voicing span check was one-sided (unplayable spans)
    - Quality fallback degraded min7 → minor before trying the exact min7 barre

  Theme 3 — rhythm guitar placement bugs:
    - Turnaround/pickup overlays smeared up to 5 beats past the barline
      (double offset + wrong subdivision in merge_patterns)
    - merge_patterns density was len(hits)/len(hits) == always 1.0
    - play_pattern "syncopated"/"offbeat" produced ZERO notes on the
      quarter-note orchestrator grid
"""

import logging
import random
from types import SimpleNamespace

import pytest

from produzre.instruments.chord_shapes import (
    _MOVABLE_FORMS,
    _fallback_voicing,
    select_voicing,
)
from produzre.instruments.profile import GUITAR_STANDARD


# ---------------------------------------------------------------------------
# Theme 2.4 — chord shape data and voicing
# ---------------------------------------------------------------------------

class TestDFormIntervals:
    """D-form movable shapes must spell plain major/minor triads."""

    def _interval_classes(self, form_name: str) -> set:
        form = next(f for f in _MOVABLE_FORMS if f.name == form_name)
        root_fret = 5
        root = GUITAR_STANDARD.open_tuning[form.root_string] + root_fret
        pitches = [
            GUITAR_STANDARD.open_tuning[i] + root_fret + rel
            for i, rel in enumerate(form.rel_frets)
            if rel >= 0
        ]
        return {(p - root) % 12 for p in pitches}

    def test_d_form_major_is_major_triad(self):
        # Was [0, 7, 11, 15] → maj7 plus a minor 10th
        assert self._interval_classes("D-form_major") == {0, 4, 7}

    def test_d_form_minor_is_minor_triad(self):
        # Was [0, 7, 11, 14] → no minor 3rd at all
        assert self._interval_classes("D-form_minor") == {0, 3, 7}


class TestVoiceLeadingBarre:
    """Octave shifts must never push fretted strings below fret 1."""

    def test_e_form_barre_fret_11_does_not_collapse(self):
        # Previous hand position low on the neck...
        prev = select_voicing(41, "major", prefer_open=False)  # F major @ fret 1
        assert prev.shape_name.startswith("E-form")

        # ...then an Eb major whose E-form sits at fret 11. The old -12 shift
        # guard was dead (0 < f+delta < 1 is impossible for ints), so frets
        # went negative, got treated as muted, and the chord collapsed to an
        # unrelated 3-note cluster.
        v = select_voicing(51, "major", prev_voicing=prev, prefer_open=False)
        assert {p % 12 for p in v.pitches} == {3, 7, 10}  # Eb major triad
        assert len(v.played_strings) >= 5  # full barre, not a collapsed cluster
        assert all(f >= 0 for f in v.frets if f != -1)

    def test_voice_led_voicing_always_valid(self):
        prev = None
        for root in (41, 43, 46, 48, 51, 53, 56, 58):
            v = select_voicing(root, "major", prev_voicing=prev, prefer_open=False)
            played = [f for f in v.frets if f > 0]
            if played:
                assert max(played) - min(played) <= GUITAR_STANDARD.max_fret_span
            assert all(p >= 0 for p in v.pitches)
            prev = v


class TestCapo:
    """select_voicing(..., capo=N) must transpose sounding pitches up by N."""

    def test_d_major_with_capo_2_sounds_as_d(self):
        # Player fingers a C shape behind a capo at fret 2 → sounds as D major.
        # The old code returned capo=0, so the chord sounded a whole step flat.
        v = select_voicing(50, "major", capo=2)
        assert v.capo == 2
        assert {p % 12 for p in v.pitches} == {2, 6, 9}  # D F# A

    def test_capo_zero_unchanged(self):
        v = select_voicing(50, "major", capo=0)
        assert v.capo == 0
        assert {p % 12 for p in v.pitches} == {2, 6, 9}

    def test_capo_with_movable_shape(self):
        v = select_voicing(51, "major", capo=3, prefer_open=False)
        assert {p % 12 for p in v.pitches} == {3, 7, 10}  # Eb major


class TestFallbackVoicingSpan:
    """Greedy fallback must respect max_fret_span on BOTH sides."""

    @pytest.mark.parametrize("root_midi", range(40, 52))
    @pytest.mark.parametrize("quality", ["major", "minor", "dominant7", "sus4"])
    def test_span_bounded(self, root_midi, quality):
        v = _fallback_voicing(root_midi, quality, GUITAR_STANDARD, capo=0)
        played = [f for f in v.frets if f > 0]
        if len(played) >= 2:
            assert max(played) - min(played) <= GUITAR_STANDARD.max_fret_span, (
                f"root={root_midi} quality={quality} frets={v.frets}"
            )


class TestQualityFallbackOrder:
    """Exact-quality movable forms must beat quality-degraded open shapes."""

    def test_c_min7_keeps_its_seventh(self):
        # Old order: open Cm barre (plain minor — 7th lost) was chosen before
        # the exact min7 movable form was even tried.
        v = select_voicing(48, "minor7")
        pcs = {p % 12 for p in v.pitches}
        assert 10 in pcs, f"Cm7 lost its b7: {sorted(pcs)} ({v.shape_name})"
        assert pcs == {0, 3, 7, 10}

    def test_open_exact_still_preferred(self):
        # Am7 has an exact open shape; it must still win over a barre.
        v = select_voicing(45, "minor7")
        assert v.shape_name == "Am7"


# ---------------------------------------------------------------------------
# Theme 3 — rhythm guitar turnaround merging (B6)
# ---------------------------------------------------------------------------

class TestTurnaroundMerge:
    def _base_pattern(self, seed=1):
        from produzre.engine.rhythm_gtr.rhythm import build_bar_pattern
        return build_bar_pattern(
            "verse", style="straight_8s", density=0.6,
            beats_per_bar=4.0, rng=random.Random(seed),
        )

    def test_merged_turnaround_hits_all_within_bar(self):
        from produzre.engine.rhythm_gtr.transitions import adjust_pattern_for_transition
        for intensity in ("light", "heavy"):
            pattern = self._base_pattern()
            transition = {"turnaround_hint": intensity, "pickup_hint": True}
            merged = adjust_pattern_for_transition(
                pattern=pattern, bar_idx=3, total_bars=4,
                transition=transition, beats_per_bar=4.0,
                rng=random.Random(7),
            )
            total_slots = int(4.0 * merged.subdivision)
            assert merged.hits, "turnaround merge produced no hits"
            assert all(0 <= h < total_slots for h in merged.hits), (
                f"hits escaped the bar: {merged.hits} (subdivision={merged.subdivision})"
            )
            # Heavy turnaround hits land on beats 3..4.5 of the bar
            beats = {h / merged.subdivision for h in merged.hits}
            assert all(0.0 <= b < 4.0 for b in beats)

    def test_merged_pattern_directions_match_hits(self):
        from produzre.engine.rhythm_gtr.transitions import adjust_pattern_for_transition
        pattern = self._base_pattern()
        merged = adjust_pattern_for_transition(
            pattern=pattern, bar_idx=3, total_bars=4,
            transition={"turnaround_hint": "heavy", "pickup_hint": True},
            beats_per_bar=4.0, rng=random.Random(7),
        )
        assert len(merged.strum_directions) == len(merged.hits)

    def test_merge_density_not_always_one(self):
        from produzre.engine.rhythm_gtr.transitions import (
            create_turnaround_pattern,
            merge_patterns,
        )
        base = self._base_pattern()
        turnaround = create_turnaround_pattern(
            style="straight_8s", turnaround_intensity="light",
            beats_per_bar=4.0, base_pattern=base,
        )
        merged = merge_patterns(base, turnaround, beats_per_bar=4.0)
        total_slots = int(4.0 * merged.subdivision)
        assert merged.density == pytest.approx(len(merged.hits) / total_slots)
        assert merged.density < 1.0


# ---------------------------------------------------------------------------
# Theme 3 — legacy play_pattern presets must produce notes (B9)
# ---------------------------------------------------------------------------

class TestLegacyPlayPatterns:
    """syncopated/offbeat/gallop must produce notes on a quarter-note grid."""

    @pytest.fixture(scope="class")
    def render_ctx(self):
        from produzre.config.load import load_root_config
        from produzre.harmony import build_harmony_plan, parse_meter
        from produzre.rhythm import create_basic_rhythm_grid

        cfg = load_root_config("examples/rhythm_gtr/sustained-chords-demo.yaml")
        section = cfg.sections["intro_normal"]
        logger = logging.getLogger("test_chord_shapes_fixes")
        harmony_plan = build_harmony_plan(cfg=cfg, section=section, logger=logger)
        meter = parse_meter(section.meter or cfg.song.meter)
        total_beats = section.total_beats(cfg.song.beats_per_bar)
        # Quarter-note grid: this is what the orchestrator delivers, and what
        # used to silence the sub-beat play_patterns entirely.
        grid = create_basic_rhythm_grid(
            meter=meter, total_beats=total_beats, subdivision=1.0
        )
        return cfg, section, harmony_plan, grid, logger

    def _render(self, render_ctx, extra):
        from produzre.engine.rhythm_gtr import _render_legacy_rhythm_guitar
        from produzre.timeline import InstrumentTimeline

        cfg, section, harmony_plan, grid, logger = render_ctx
        timeline = InstrumentTimeline(instrument="rhythm_gtr")
        instrument_cfg = SimpleNamespace(
            enabled=True,
            intensity=0.8,
            style_bias=0.0,
            voicing=None,
            playstyle=None,
            offset_beats=0.0,
            extra=dict(extra),
        )
        _render_legacy_rhythm_guitar(
            cfg=cfg,
            section=section,
            instrument_name="rhythm_gtr",
            instrument_cfg=instrument_cfg,
            harmony_plan=harmony_plan,
            rhythm_grid=grid,
            section_start_beat=0.0,
            timeline=timeline,
            rng=random.Random(99),
            logger=logger,
        )
        return timeline

    def test_syncopated_produces_notes(self, render_ctx):
        timeline = self._render(render_ctx, {"pattern": "syncopated"})
        assert len(timeline.events) > 0, "syncopated pattern produced zero notes"
        # Hits must land on offbeats (x.5 within the bar)
        offsets = {round(ev.start_beat % 1.0, 2) for ev in timeline.events}
        assert 0.5 in offsets

    def test_offbeat_produces_notes(self, render_ctx):
        timeline = self._render(render_ctx, {"pattern": "offbeat"})
        assert len(timeline.events) > 0, "offbeat pattern produced zero notes"
        offsets = {round(ev.start_beat % 1.0, 2) for ev in timeline.events}
        assert offsets == {0.5}

    def test_gallop_produces_notes(self, render_ctx):
        timeline = self._render(render_ctx, {"pattern": "gallop"})
        assert len(timeline.events) > 0, "gallop pattern produced zero notes"
        offsets = {round(ev.start_beat % 1.0, 2) for ev in timeline.events}
        assert offsets <= {0.0, 0.5, 0.75}
        assert {0.5, 0.75} & offsets

    def test_chug_hit_strategy_produces_notes(self, render_ctx):
        # "chug" implies pmute + gallop; it used to be silenced as well.
        timeline = self._render(render_ctx, {"hit_strategy": "chug"})
        assert len(timeline.events) > 0, "chug preset produced zero notes"

    def test_chug_style_produces_notes(self, render_ctx):
        timeline = self._render(render_ctx, {"style": "chug"})
        assert len(timeline.events) > 0, "style=chug preset produced zero notes"

    def test_backbeat_produces_notes(self, render_ctx):
        timeline = self._render(render_ctx, {"pattern": "backbeat"})
        assert len(timeline.events) > 0
        offsets = {round(ev.start_beat % 4.0, 2) for ev in timeline.events}
        assert offsets <= {1.0, 3.0}
