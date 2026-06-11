"""Tests for the shared groove clock (produzre.groove).

Covers the 2026-06-10 review Theme 5 item "the band cannot swing together":

  (a) swing in the drum params shifts bass 8th-offbeats by 0.25*swing beats
      and rhythm_gtr matches the drums' shift (band coherence)
  (b) pocket offsets: bass sits ~+8 ms behind the grid once a feel resolves
  (c) swing 0 + pockets 0 -> apply_feel is a pure no-op; an all-zero config
      resolves NO groove feel (zero values count as "no indication")
  (d) determinism: two builds of the same config are event-identical
  (e) velocity_humanize produces varied-but-clamped velocities,
      deterministic across builds
  (f) macro-dynamics fallback: with instrument intensity unset, engines use
      the resolved section intensity (chorus louder than verse)
"""

from __future__ import annotations

import copy
import logging
import pathlib

import pytest

from produzre.groove import (
    DEFAULT_POCKET_MS,
    GrooveFeel,
    apply_feel,
    resolve_groove_feel,
)
from produzre.timeline import NoteEvent


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cfg(tmp_path, text: str, name: str = "song.yaml"):
    p = pathlib.Path(tmp_path) / name
    p.write_text(text, encoding="utf-8")
    from produzre.config.load import load_root_config

    return load_root_config(str(p))


def _render_timelines(cfg):
    """Build a song in-process (dry run) and capture the rendered timelines."""
    import produzre.orchestrate.build as B
    from produzre.orchestrate.build import build_song

    captured = {}
    orig = B._sort_used_timelines

    def spy(timelines, used):
        captured.update(timelines)
        orig(timelines, used)

    B._sort_used_timelines = spy
    try:
        result = build_song(
            cfg=cfg,
            dry_run=True,
            export_sections=False,
            export_patterns=False,
            sections_absolute_timing=False,
        )
    finally:
        B._sort_used_timelines = orig
    return captured, result


def _event_tuples(timelines):
    """Flatten timelines to a sorted, hashable representation."""
    rows = []
    for inst in sorted(timelines):
        for ev in timelines[inst].events:
            rows.append(
                (
                    inst,
                    round(ev.start_beat, 9),
                    round(ev.duration_beats, 9),
                    ev.pitch,
                    ev.velocity,
                    ev.channel,
                )
            )
    return rows


def _beat_fracs(timelines, inst):
    return [ev.start_beat % 1.0 for ev in timelines[inst].events]


_SWING_SONG = """
version: 1
song:
  title: "GrooveSwing"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  seed: 11
  exports_root: "exports"

instruments:
  drums:
    params:
      swing: 0.6
      timing_jitter_ms: 0.0
      velocity_humanize: 0.0
  bass:
    params:
      rhythm_pattern: "drive"
      density: 1.0
      rest_rate: 0.0
      pocket_ms: 0.0
  rhythm_gtr:
    params:
      pocket_ms: 0.0
      pattern: "offbeat"
      humanize_timing: 0.0
      humanize_velocity: 0.0
      strum_ms: 0.0
      chuck_rate: 0.0

sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: ["I", "V", "vi", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}

arrangement:
  - verse1
"""


# ---------------------------------------------------------------------------
# (a) band coherence: bass + rhythm_gtr swing with the drums
# ---------------------------------------------------------------------------

def test_swing_shifts_bass_offbeats_and_matches_drums(tmp_path):
    cfg = _load_cfg(tmp_path, _SWING_SONG)
    timelines, _ = _render_timelines(cfg)

    expected_shift = 0.25 * 0.6  # 0.15 beats on the 8th "&"
    shifted_offbeat = 0.5 + expected_shift

    bass_fracs = _beat_fracs(timelines, "bass")
    assert bass_fracs, "bass rendered no events"

    # No bass event may remain on the unswung "&".
    assert not any(abs(f - 0.5) < 1e-6 for f in bass_fracs), (
        "bass 8th offbeats were not swung"
    )
    swung = [f for f in bass_fracs if abs(f - shifted_offbeat) < 1e-6]
    assert swung, (
        f"expected bass events at offbeat +{expected_shift} beats; fracs={sorted(set(round(f, 4) for f in bass_fracs))}"
    )

    # Drums swing internally with the same semantics: their swung "&" position
    # must match the bass shift exactly (band coherence).
    drum_fracs = _beat_fracs(timelines, "drums")
    drum_swung = [f for f in drum_fracs if abs(f - shifted_offbeat) < 1e-6]
    assert drum_swung, "drums did not swing their 8th offbeats"

    # rhythm_gtr (strum/humanize disabled) lands on the identical swung grid.
    gtr_fracs = _beat_fracs(timelines, "rhythm_gtr")
    assert gtr_fracs, "rhythm_gtr rendered no events"
    assert not any(abs(f - 0.5) < 1e-6 for f in gtr_fracs), (
        "rhythm_gtr 8th offbeats were not swung"
    )
    gtr_swung = [f for f in gtr_fracs if abs(f - shifted_offbeat) < 1e-6]
    assert gtr_swung, (
        f"rhythm_gtr does not match the drums' swing shift; fracs={sorted(set(round(f, 4) for f in gtr_fracs))}"
    )


# ---------------------------------------------------------------------------
# (b) pocket: bass sits ~+8ms behind the grid
# ---------------------------------------------------------------------------

def test_bass_default_pocket_behind_the_beat(tmp_path):
    bpm = 120.0
    cfg = _load_cfg(
        tmp_path,
        """
version: 1
song:
  title: "GroovePocket"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  seed: 11
  exports_root: "exports"

instruments:
  drums:
    params:
      swing: 0.6
      timing_jitter_ms: 0.0
  bass:
    params:
      rhythm_pattern: "anchor"
      density: 1.0
      rest_rate: 0.0

sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: ["I", "V", "vi", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}

arrangement:
  - verse1
""",
    )
    timelines, _ = _render_timelines(cfg)

    pocket_beats = DEFAULT_POCKET_MS["bass"] * bpm / 60000.0  # 8ms -> 0.016
    assert pocket_beats == pytest.approx(8.0 / (60000.0 / bpm))

    on_beat = [
        f for f in _beat_fracs(timelines, "bass")
        if f < 0.2  # events classified to the downbeat grid positions
    ]
    assert on_beat, "bass rendered no on-beat events"
    for f in on_beat:
        assert f == pytest.approx(pocket_beats, abs=1e-9), (
            f"bass on-beat event not +8ms behind the grid: frac={f}"
        )


# ---------------------------------------------------------------------------
# (c) no-op proofs
# ---------------------------------------------------------------------------

def _synthetic_events():
    return [
        NoteEvent(start_beat=0.0, duration_beats=0.5, pitch=40, velocity=90),
        NoteEvent(start_beat=0.5, duration_beats=0.5, pitch=40, velocity=80),
        NoteEvent(start_beat=1.25, duration_beats=0.25, pitch=43, velocity=85),
        NoteEvent(start_beat=1.75, duration_beats=0.25, pitch=45, velocity=70),
    ]


def test_apply_feel_zero_everything_is_pure_noop():
    events = _synthetic_events()
    reference = copy.deepcopy(events)
    feel = GrooveFeel(swing=0.0, swing_16th=0.0, pocket_offsets_ms={"bass": 0.0})
    apply_feel(
        events, feel, "bass", 120.0, 4.0, rng_seed=123,
        section_start_beat=0.0, timing_jitter_ms=0.0, velocity_humanize=0.0,
    )
    assert [
        (e.start_beat, e.duration_beats, e.pitch, e.velocity) for e in events
    ] == [
        (e.start_beat, e.duration_beats, e.pitch, e.velocity) for e in reference
    ]


def test_all_zero_config_resolves_no_feel(tmp_path):
    """Personas full of swing: 0.0 / push_pull: 0.0 count as NO indication."""
    cfg = _load_cfg(
        tmp_path,
        """
version: 1
song:
  title: "NoGroove"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  seed: 11
  exports_root: "exports"

sections:
  verse1:
    type: verse
    bars: 2
    harmony:
      progression: ["I", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}

arrangement:
  - verse1
""",
    )
    # The default 'tight' personas define swing: 0.0 and push_pull: 0.0
    # explicitly — those zeros must not resolve a feel.
    drum_params = (
        cfg.raw["_effective"]["instruments"]["drums"].get("params", {})
    )
    sec = cfg.sections["verse1"]
    inst_params = {
        "drums": drum_params,
        "bass": cfg.raw["_effective"]["instruments"]["bass"].get("params", {}),
    }
    assert resolve_groove_feel(cfg, sec, drum_params, inst_params) is None

    # And the rendered output carries no pocket: bass on-beats stay on-grid.
    timelines, _ = _render_timelines(cfg)
    on_grid = [
        f for f in _beat_fracs(timelines, "bass") if f < 0.2
    ]
    assert on_grid, "bass rendered no on-beat events"
    for f in on_grid:
        assert f == pytest.approx(0.0, abs=1e-9), (
            f"no-groove config produced an off-grid bass event: frac={f}"
        )


# ---------------------------------------------------------------------------
# (d) + (e) determinism and velocity humanization
# ---------------------------------------------------------------------------

_HUMANIZE_SONG = """
version: 1
song:
  title: "GrooveHumanize"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  seed: 23
  exports_root: "exports"

instruments:
  drums:
    params:
      swing: 0.5
  bass:
    params:
      rhythm_pattern: "drive"
      density: 1.0
      rest_rate: 0.0
      timing_jitter_ms: 6.0
      velocity_humanize: 0.2

sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: ["I", "V", "vi", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}

arrangement:
  - verse1
"""


def test_two_builds_are_identical(tmp_path):
    cfg1 = _load_cfg(tmp_path, _HUMANIZE_SONG, name="a.yaml")
    cfg2 = _load_cfg(tmp_path, _HUMANIZE_SONG, name="b.yaml")
    t1, _ = _render_timelines(cfg1)
    t2, _ = _render_timelines(cfg2)
    rows1 = _event_tuples(t1)
    rows2 = _event_tuples(t2)
    assert rows1, "no events rendered"
    assert rows1 == rows2, "two builds of the same config differ"


def test_velocity_humanize_varies_and_clamps(tmp_path):
    cfg = _load_cfg(tmp_path, _HUMANIZE_SONG)
    timelines, _ = _render_timelines(cfg)
    velocities = [ev.velocity for ev in timelines["bass"].events]
    assert len(velocities) > 4
    assert all(1 <= v <= 127 for v in velocities)
    # +/-20% noise on the bass velocity must produce more than a couple of
    # distinct values across a 4-bar drive pattern.
    assert len(set(velocities)) > 3, (
        f"velocity_humanize produced no variation: {sorted(set(velocities))}"
    )


def test_timing_jitter_moves_events_deterministically(tmp_path):
    """Bass timing_jitter_ms must act (was dead) and stay deterministic."""
    cfg = _load_cfg(tmp_path, _HUMANIZE_SONG)
    timelines, _ = _render_timelines(cfg)
    fracs = _beat_fracs(timelines, "bass")
    # 6ms jitter at 120bpm = +/-0.012 beats around the pocketed grid; events
    # must not all sit on exact grid+pocket positions.
    pocket = DEFAULT_POCKET_MS["bass"] * 120.0 / 60000.0
    on_beat = [f for f in fracs if f < 0.2]
    assert on_beat
    assert any(abs(f - pocket) > 1e-6 for f in on_beat), (
        "timing_jitter_ms had no effect on bass events"
    )


# ---------------------------------------------------------------------------
# (f) section intensity fallback (macro-dynamics follow-up)
# ---------------------------------------------------------------------------

def test_section_intensity_fallback_chorus_louder_than_verse(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        """
version: 1
song:
  title: "MacroGroove"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  seed: 5
  exports_root: "exports"

sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: ["I", "V", "vi", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}
  chorus1:
    type: chorus
    bars: 4
    harmony:
      progression: ["I", "V", "vi", "IV"]
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}

arrangement:
  - verse1
  - chorus1
""",
    )
    timelines, result = _render_timelines(cfg)

    timings = {t.id: t for t in result.section_timings}
    verse = timings["verse1"]
    chorus = timings["chorus1"]

    for inst in ("bass", "rhythm_gtr"):
        evs = timelines[inst].events
        verse_v = [
            e.velocity for e in evs
            if verse.start_beat <= e.start_beat < verse.end_beat
        ]
        chorus_v = [
            e.velocity for e in evs
            if chorus.start_beat <= e.start_beat < chorus.end_beat
        ]
        assert verse_v and chorus_v, f"{inst}: missing events in a section"
        mean_verse = sum(verse_v) / len(verse_v)
        mean_chorus = sum(chorus_v) / len(chorus_v)
        assert mean_chorus > mean_verse, (
            f"{inst}: chorus (intensity 0.9) not louder than verse (0.65): "
            f"{mean_chorus:.1f} vs {mean_verse:.1f}"
        )


# ---------------------------------------------------------------------------
# Resolution units: precedence + push_pull mapping
# ---------------------------------------------------------------------------

class _CfgStub:
    def __init__(self, raw):
        self.raw = raw


def test_section_drum_swing_beats_groove_block():
    cfg = _CfgStub({"groove": {"swing": 0.3}})
    feel = resolve_groove_feel(cfg, None, {"swing": 0.7}, {"bass": {}})
    assert feel is not None
    assert feel.swing == pytest.approx(0.7)
    assert feel.swing_16th == pytest.approx(0.35)  # default = swing * 0.5


def test_groove_block_used_when_drums_silent():
    cfg = _CfgStub({"groove": {"swing": 0.3, "swing_16th": 0.1}})
    feel = resolve_groove_feel(cfg, None, {"swing": 0.0}, {"bass": {}})
    assert feel is not None
    assert feel.swing == pytest.approx(0.3)
    assert feel.swing_16th == pytest.approx(0.1)
    assert feel.source == "groove_block"
    # Default pockets engage once a feel resolves.
    assert feel.pocket_offsets_ms["bass"] == pytest.approx(8.0)


def test_push_pull_maps_to_pocket_ms():
    cfg = _CfgStub({})
    # bass persona 'pocket': push_pull -0.05 -> +5ms behind the beat
    feel = resolve_groove_feel(cfg, None, {}, {"bass": {"push_pull": -0.05}})
    assert feel is not None
    assert feel.pocket_offsets_ms["bass"] == pytest.approx(5.0)
    # 'dub': -0.15 -> +15ms behind
    feel = resolve_groove_feel(cfg, None, {}, {"bass": {"push_pull": -0.15}})
    assert feel.pocket_offsets_ms["bass"] == pytest.approx(15.0)
    # pushing ahead: +0.10 -> -10ms
    feel = resolve_groove_feel(cfg, None, {}, {"bass": {"push_pull": 0.10}})
    assert feel.pocket_offsets_ms["bass"] == pytest.approx(-10.0)


def test_rhythm_gtr_push_pull_not_double_applied():
    """rhythm_gtr consumes push_pull internally (apply_microtiming); the
    groove clock must not also derive a pocket from it."""
    cfg = _CfgStub({})
    feel = resolve_groove_feel(
        cfg, None, {"swing": 0.5}, {"rhythm_gtr": {"push_pull": 0.1}}
    )
    assert feel is not None
    assert feel.pocket_offsets_ms["rhythm_gtr"] == pytest.approx(
        DEFAULT_POCKET_MS["rhythm_gtr"]
    )


def test_explicit_pocket_ms_wins():
    cfg = _CfgStub({})
    feel = resolve_groove_feel(
        cfg, None, {"swing": 0.5},
        {"bass": {"pocket_ms": -4.0, "push_pull": -0.15}},
    )
    assert feel is not None
    assert feel.pocket_offsets_ms["bass"] == pytest.approx(-4.0)
