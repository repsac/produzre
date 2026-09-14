"""Tests for non-4/4 meter support (drums grid, bar->beat conversion).

Conventions verified here:
- `Meter.beats_per_bar` is expressed in *quarter-note* beats per bar:
  4/4 -> 4.0, 3/4 -> 3.0, 6/8 -> 3.0, 7/8 -> 3.5.
- The drums engine grid is 4 steps per quarter-note beat (one 16th note per
  step, step duration 0.25 beats): 16 steps in 4/4, 12 in 3/4 and 6/8.
- Backbeats: bpb >= 4 -> beats 2 and 4; bpb == 6 -> beat 4; bpb < 4 -> beat 2.
- Template positions beyond the bar are dropped, not clamped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_yaml, get_export_root


# ---------------------------------------------------------------------------
# Unit-level: Meter convention and grid derivation
# ---------------------------------------------------------------------------


def test_meter_convention_quarter_note_beats():
    """Meter.beats_per_bar is quarter-note beats: 6/8 normalizes to 3.0."""
    from produzre.harmony.meter import parse_meter

    assert parse_meter("4/4").beats_per_bar == 4.0
    assert parse_meter("3/4").beats_per_bar == 3.0
    assert parse_meter("6/8").beats_per_bar == 3.0
    assert parse_meter("7/8").beats_per_bar == 3.5
    assert parse_meter("6/4").beats_per_bar == 6.0


def test_steps_per_bar_for_meter():
    """Drum grid is 4 steps per quarter beat in every meter."""
    from produzre.engine.drums.groove import steps_per_bar_for_meter

    assert steps_per_bar_for_meter(4.0) == 16
    assert steps_per_bar_for_meter(3.0) == 12  # 3/4 and 6/8
    assert steps_per_bar_for_meter(3.5) == 14  # 7/8
    assert steps_per_bar_for_meter(6.0) == 24  # 6/4


def test_groove_template_backbeats_meter_aware():
    """Backbeats/ghosts map to meter-valid steps; out-of-bar positions drop."""
    from produzre.engine.drums.groove import groove_template

    # 4/4: classic backbeat on beats 2 and 4 (steps 4 and 12 of 16).
    tpl44 = groove_template(
        "verse_groove", section_type="verse", intensity=0.5, beats_per_bar=4.0
    )
    assert tpl44.snare_backbeat_steps == (4, 12)
    assert tpl44.ghost_steps == (7, 15)

    # 3/4: only beat 2 (step 4 of 12); beat 4 is dropped, NOT clamped to 11.
    tpl34 = groove_template(
        "verse_groove", section_type="verse", intensity=0.5, beats_per_bar=3.0
    )
    assert tpl34.snare_backbeat_steps == (4,)
    assert tpl34.ghost_steps == (7,)
    for step in tpl34.kick_base + tpl34.snare_backbeat_steps + tpl34.ghost_steps:
        assert 0 <= step < 12

    # 6/4 (six quarter beats): snare on beat 4 (step 12 of 24).
    tpl64 = groove_template(
        "verse_groove", section_type="verse", intensity=0.5, beats_per_bar=6.0
    )
    assert tpl64.snare_backbeat_steps == (12,)


def test_contribute_plan_publishes_meter_grid():
    """contribute_plan publishes the same meter-derived grid the renderer uses."""
    from produzre.engine.drums import contribute_plan

    class FakePlan:
        def __init__(self):
            self.data = {}

        def set(self, key, value):
            self.data[key] = value

    for bpb, expected_spb in ((4.0, 16), (3.0, 12)):
        plan = FakePlan()
        contribute_plan(
            plan=plan,
            section_ctx={
                "rhythm_grid": {"beats_per_bar": bpb, "total_beats": bpb * 4},
                "section": None,
            },
            rng=None,
            logger=None,
        )
        grid = plan.data["rhythm.grid"]
        assert grid["steps_per_bar"] == expected_spb
        assert grid["step_duration_beats"] == pytest.approx(0.25)
        assert grid["steps_per_beat"] == pytest.approx(4.0)
        assert grid["total_steps"] == expected_spb * 4


def test_section_meter_override_bar_length():
    """A `meter: 6/8, bars: 4` section resolves to 12 quarter-beats."""
    from produzre.model import SectionConfig

    sec = SectionConfig(id="waltz", type="verse", bars=4, meter="6/8")
    assert sec.total_beats(4) == pytest.approx(12.0)

    sec34 = SectionConfig(id="w34", type="verse", bars=4, meter="3/4")
    assert sec34.total_beats(4) == pytest.approx(12.0)

    # No meter override: legacy behavior (global beats-per-bar) is unchanged.
    sec_plain = SectionConfig(id="plain", type="verse", bars=4)
    assert sec_plain.total_beats(4) == pytest.approx(16.0)


def test_resolve_total_beats_uses_section_meter():
    """harmony.utils.resolve_total_beats honors a section meter override."""
    from produzre.harmony.meter import parse_meter
    from produzre.harmony.utils import resolve_total_beats
    from produzre.model import RootConfig, SectionConfig, SongConfig

    cfg = RootConfig(
        version=1,
        song=SongConfig(beats_per_bar=4, meter="4/4"),
        sections={},
        arrangement=[],
        engines={},
    )

    sec = SectionConfig(id="waltz", type="verse", bars=4, meter="6/8")
    meter = parse_meter(sec.meter or cfg.song.meter)
    assert resolve_total_beats(cfg, sec, meter) == pytest.approx(12.0)

    # No override: legacy path uses cfg.song.beats_per_bar.
    sec_plain = SectionConfig(id="plain", type="verse", bars=4)
    meter_plain = parse_meter(sec_plain.meter or cfg.song.meter)
    assert resolve_total_beats(cfg, sec_plain, meter_plain) == pytest.approx(16.0)


# ---------------------------------------------------------------------------
# Build-level: end-to-end via the CLI
# ---------------------------------------------------------------------------


SONG_HEADER = """\
version: 1
song:
  title: "{title}"
  bpm: 120
  key: C
  mode: major
  meter: "{meter}"
  beats_per_bar: {bpb}
  seed: 42
  variation: 0.0
  humanize_velocity: 0.0
  humanize_timing: 0.0
  exports_root: "{exports_root}"

exports:
  midi_text:
    enabled: true
    views: ["events"]
"""


def _build(tmp_path: Path, name: str, yaml_text: str) -> Path:
    yaml_file = tmp_path / f"{name}.yaml"
    yaml_file.write_text(yaml_text)
    result = build_yaml(str(yaml_file), timeout=60)
    assert result.returncode == 0, (
        f"Build failed for {name}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "Traceback" not in result.stderr, f"Build raised:\n{result.stderr}"
    return Path(get_export_root(result))


def _drum_events(export_root: Path, title: str) -> list[dict]:
    tsv = export_root / "analysis" / "drums" / f"{title}_drums.events.tsv"
    assert tsv.exists(), f"Drums events TSV not found: {tsv}"
    lines = tsv.read_text().splitlines()
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        row = dict(zip(header, line.split("\t")))
        row["start_beat_abs"] = float(row["start_beat_abs"])
        row["pitch"] = int(row["pitch"])
        rows.append(row)
    return rows


def test_three_four_drums_on_valid_steps(tmp_path):
    """A 3/4 build places drum hits only on valid 3/4 grid positions."""
    title = "MeterDrums34"
    yaml_text = SONG_HEADER.format(
        title=title, meter="3/4", bpb=3, exports_root=tmp_path / "exports"
    ) + """
sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
      chord_rate: 3.0
    instruments:
      harmony: {}
      drums:
        params:
          fill_rate: 0.0
          fill_chatter: 0.0

arrangement:
  - verse
"""
    export_root = _build(tmp_path, "meter34", yaml_text)
    events = _drum_events(export_root, title)
    assert events, "No drum events rendered in 3/4"

    total_beats = 4 * 3.0
    snare_full_positions = set()
    for e in events:
        start = e["start_beat_abs"]
        # 1) Every event is within the section's bar bounds.
        assert 0.0 <= start < total_beats - 1e-9, f"Event out of bounds: {e}"
        # 2) Every event sits on the 16th-note grid (multiples of 0.25 beats).
        #    The legacy fixed 16-step grid placed 3/4 steps at multiples of
        #    0.1875, which would fail this.
        frac = start % 0.25
        assert min(frac, 0.25 - frac) < 1e-6, f"Event off the 0.25 grid: {e}"
        beat_in_bar = start % 3.0
        # 3) Nothing beyond beat 3 should be clamped onto the bar's last 16th.
        if e["kind"] == "snare":
            snare_full_positions.add(round(beat_in_bar, 6))

    # 4) Backbeat lands on beat 2 (beat offset 1.0) and only there.
    assert snare_full_positions == {1.0}, (
        f"3/4 snare backbeats not on beat 2: {sorted(snare_full_positions)}"
    )


def test_six_eight_drums_in_bounds(tmp_path):
    """A 6/8 build (3.0 quarter-beats per bar) produces in-bounds drum events."""
    title = "MeterDrums68"
    yaml_text = SONG_HEADER.format(
        title=title, meter="6/8", bpb=3, exports_root=tmp_path / "exports"
    ) + """
sections:
  verse:
    type: verse
    bars: 4
    meter: "6/8"
    harmony:
      progression: "I IV V I"
      chord_rate: 3.0
    instruments:
      harmony: {}
      drums:
        params:
          fill_rate: 0.0
          fill_chatter: 0.0

arrangement:
  - verse
"""
    export_root = _build(tmp_path, "meter68", yaml_text)
    events = _drum_events(export_root, title)
    assert events, "No drum events rendered in 6/8"

    # 6/8 with section meter override: 4 bars * 3.0 quarter-beats = 12 beats.
    total_beats = 12.0
    for e in events:
        start = e["start_beat_abs"]
        assert 0.0 <= start < total_beats - 1e-9, f"Event out of bounds: {e}"
        frac = start % 0.25
        assert min(frac, 0.25 - frac) < 1e-6, f"Event off the 0.25 grid: {e}"


def test_six_eight_section_in_four_four_song_length(tmp_path):
    """`meter: 6/8, bars: 4` inside a 4/4 song spans 12 quarter-beats."""
    title = "MeterMixed"
    yaml_text = SONG_HEADER.format(
        title=title, meter="4/4", bpb=4, exports_root=tmp_path / "exports"
    ) + """
sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
    instruments:
      harmony: {}
      drums:
        params:
          fill_rate: 0.0
          fill_chatter: 0.0
  waltz:
    type: bridge
    bars: 4
    meter: "6/8"
    harmony:
      progression: "I IV V I"
      chord_rate: 3.0
    instruments:
      harmony: {}
      drums:
        params:
          fill_rate: 0.0
          fill_chatter: 0.0

arrangement:
  - verse
  - waltz
"""
    export_root = _build(tmp_path, "metermixed", yaml_text)
    events = _drum_events(export_root, title)

    verse_events = [e for e in events if e["section_id"] == "verse"]
    waltz_events = [e for e in events if e["section_id"] == "waltz"]
    assert verse_events and waltz_events

    # Verse: 4 bars of 4/4 = 16 beats; waltz starts at 16 and spans 12 beats
    # (4 bars of 6/8 == 4 * 3.0 quarter-beats, per Meter.beats_per_bar).
    assert max(e["start_beat_abs"] for e in verse_events) < 16.0
    for e in waltz_events:
        assert 16.0 <= e["start_beat_abs"] < 28.0 - 1e-9, f"Waltz event out of bounds: {e}"


def test_three_four_bass_and_drums_build(tmp_path):
    """A 3/4 bass+drums build completes without crashing."""
    title = "MeterBand34"
    yaml_text = SONG_HEADER.format(
        title=title, meter="3/4", bpb=3, exports_root=tmp_path / "exports"
    ) + """
sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
      chord_rate: 3.0
    instruments:
      harmony: {}
      drums: {}
      bass: {}

arrangement:
  - verse
"""
    export_root = _build(tmp_path, "meterband34", yaml_text)
    events = _drum_events(export_root, title)
    assert events, "No drum events in 3/4 bass+drums build"
    for e in events:
        assert 0.0 <= e["start_beat_abs"] < 12.0 - 1e-9


def test_swing_offbeat_detection_meter_proof():
    """Swing delays 8th-note offbeats in 3/4 (was a silent no-op pre-fix).

    With the legacy fixed 16-step grid, 3/4 events landed on multiples of
    0.1875 beats so no event ever had a beat fraction of exactly 0.5 and the
    swing branch never fired. The meter-derived grid (0.25-beat steps) places
    offbeats exactly on x.5 in every meter.

    Note: this is a unit test on humanize_events because the section-level
    `params.swing` plumbing into the drums engine is a separate, pre-existing
    gap (it does not flow in 4/4 either).
    """
    import random

    from produzre.engine.drums.humanize import humanize_events
    from produzre.engine.drums.patterns import DrumEvent

    for bpb in (3.0, 4.0):
        events = [
            DrumEvent(beat=b * 0.5, duration_beats=0.25, pitch=42, velocity=80, kind="hat")
            for b in range(int(bpb * 2) * 2)  # two bars of straight 8ths
        ]
        notes = humanize_events(
            events=events,
            section_start_beat=0.0,
            beats_per_bar=bpb,
            bpm=120.0,
            timing_jitter_ms=0.0,
            swing=0.5,
            push_pull=0.0,
            velocity_humanize=0.0,
            rng=random.Random(1),
        )
        fractions = sorted({round(n[0] % 1.0, 6) for n in notes})
        # Offbeats (x.5) delayed by 0.25 * 0.5 = 0.125 beats -> x.625.
        assert fractions == [0.0, 0.625], (
            f"swing not applied to 8th offbeats at bpb={bpb}: {fractions}"
        )
