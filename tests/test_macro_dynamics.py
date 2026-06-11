"""Tests for default macro-dynamics (2026-06-10 review, Theme 5).

When a section does not set `intensity:`, the planner derives it from the
section type and arrangement position (with per-repeat escalation), so an
un-tweaked config has a dynamic shape instead of a flat song. User-set
intensities are never touched.

Covered here:
  (a) un-tweaked configs resolve the documented arc, including escalation
  (b) user-set intensity is never overridden
  (c) engines actually receive the resolved value (drums output for a derived
      chorus matches an explicit `intensity: 0.9` chorus, and differs from an
      explicit `intensity: 0.5` chorus; default verse vs chorus velocities
      differ within one build)
  (d) explicit `intensity: 0.5` everywhere produces a flat plan (no escalation)

Note: drums read section-level intensity directly; the groove-clock task
wired bass and the guitar engines to fall back to the resolved section
intensity when instrument-level intensity is unset (see
tests/test_groove_clock.py::test_section_intensity_fallback_chorus_louder_than_verse).
The engine-output assertions here are made on drums.
"""

from __future__ import annotations

import logging
import pathlib

import mido
import pytest

from produzre.orchestrate.plan import plan_song, resolve_section_intensity


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cfg(tmp_path, text: str):
    p = pathlib.Path(tmp_path) / "song.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    from produzre.config.load import load_root_config

    return load_root_config(str(p))


def _build(cfg):
    from produzre.orchestrate.build import build_song

    return build_song(
        cfg=cfg,
        dry_run=False,
        export_sections=False,
        export_patterns=False,
        sections_absolute_timing=False,
    )


def _note_events(export_root: str):
    """Extract (track_index, abs_tick, type, note, velocity) tuples from the
    full-song MIDI under an export root."""
    mids = sorted(pathlib.Path(export_root).glob("*.mid"))
    assert mids, f"no full-song MIDI found under {export_root}"
    mid = mido.MidiFile(str(mids[0]))
    events = []
    for ti, track in enumerate(mid.tracks):
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type in ("note_on", "note_off"):
                events.append((ti, tick, msg.type, msg.note, msg.velocity))
    return events, mid.ticks_per_beat


# ---------------------------------------------------------------------------
# Unit: resolve_section_intensity
# ---------------------------------------------------------------------------

def test_resolver_type_defaults():
    assert resolve_section_intensity("intro") == pytest.approx(0.55)
    assert resolve_section_intensity("verse") == pytest.approx(0.65)
    assert resolve_section_intensity("prechorus") == pytest.approx(0.75)
    assert resolve_section_intensity("chorus") == pytest.approx(0.9)
    assert resolve_section_intensity("bridge") == pytest.approx(0.7)
    assert resolve_section_intensity("solo") == pytest.approx(0.85)
    assert resolve_section_intensity("breakdown") == pytest.approx(0.45)
    assert resolve_section_intensity("outro") == pytest.approx(0.5)
    # Unknown type falls back to the generic default.
    assert resolve_section_intensity("interlude") == pytest.approx(0.65)
    # Case-insensitive.
    assert resolve_section_intensity("Chorus") == pytest.approx(0.9)


def test_resolver_repeat_escalation_capped():
    # chorus 1 = 0.90, chorus 2 = 0.95, chorus 3+ = 1.00 (cap +0.10)
    assert resolve_section_intensity("chorus", 0) == pytest.approx(0.90)
    assert resolve_section_intensity("chorus", 1) == pytest.approx(0.95)
    assert resolve_section_intensity("chorus", 2) == pytest.approx(1.00)
    assert resolve_section_intensity("chorus", 5) == pytest.approx(1.00)
    # Non-chorus types escalate too, capped at +0.10.
    assert resolve_section_intensity("verse", 1) == pytest.approx(0.70)
    assert resolve_section_intensity("verse", 4) == pytest.approx(0.75)


def test_resolver_user_value_passthrough():
    # User values pass through untouched — no escalation, no clamping.
    assert resolve_section_intensity("chorus", 3, 0.42) == pytest.approx(0.42)
    assert resolve_section_intensity("verse", 0, 1.5) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# (a) Un-tweaked config resolves the documented arc
# ---------------------------------------------------------------------------

UNTWEAKED_SONG = """
version: 1
song:
  title: "MacroDefault"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 7
  exports_root: "{exports_root}"
sections:
  intro:
    type: intro
    bars: 2
    instruments:
      drums: {{}}
  verse1:
    type: verse
    bars: 4
    instruments:
      drums: {{}}
  verse2:
    type: verse
    bars: 4
    instruments:
      drums: {{}}
  chorus1:
    type: chorus
    bars: 4
    instruments:
      drums: {{}}
  outro:
    type: outro
    bars: 2
    instruments:
      drums: {{}}
arrangement:
  - intro
  - verse1
  - chorus1
  - verse2
  - chorus1
  - outro
"""


def test_untweaked_config_resolves_documented_arc(tmp_path, caplog):
    cfg = _load_cfg(tmp_path, UNTWEAKED_SONG.format(exports_root=tmp_path / "exports"))

    with caplog.at_level(logging.INFO):
        plan = plan_song(cfg=cfg, logger=logging.getLogger("test"))

    resolved = [ps.sec.intensity for ps in plan.planned_sections]
    assert resolved == pytest.approx([0.55, 0.65, 0.90, 0.70, 0.95, 0.50])

    # Repeated chorus escalates even though both occurrences reference the
    # same section id (chorus1).
    assert plan.planned_sections[2].sec_id == plan.planned_sections[4].sec_id == "chorus1"

    # Original config objects stay untouched (derived values live on
    # per-occurrence planned copies only).
    assert all(sec.intensity is None for sec in cfg.sections.values())

    # One INFO line summarizing the arc.
    arc_lines = [r.getMessage() for r in caplog.records if "intensity arc:" in r.getMessage()]
    assert len(arc_lines) == 1
    assert (
        arc_lines[0]
        == "intensity arc: intro 0.55 → verse 0.65 → chorus 0.90 → verse 0.70 → chorus 0.95 → outro 0.50"
    )


# ---------------------------------------------------------------------------
# (b) User-set intensity is never overridden
# ---------------------------------------------------------------------------

USER_SET_SONG = """
version: 1
song:
  title: "MacroUserSet"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 7
  exports_root: "{exports_root}"
sections:
  verse1:
    type: verse
    bars: 4
    intensity: 0.42
    instruments:
      drums: {{}}
  chorus1:
    type: chorus
    bars: 4
    intensity: 0.33
    instruments:
      drums: {{}}
arrangement:
  - verse1
  - chorus1
  - chorus1
  - chorus1
"""


def test_user_set_intensity_never_overridden(tmp_path):
    cfg = _load_cfg(tmp_path, USER_SET_SONG.format(exports_root=tmp_path / "exports"))

    # Parsed into the typed field, not dropped into extras.
    assert cfg.sections["verse1"].intensity == pytest.approx(0.42)
    assert "intensity" not in cfg.sections["verse1"].extras

    plan = plan_song(cfg=cfg, logger=logging.getLogger("test"))
    resolved = [ps.sec.intensity for ps in plan.planned_sections]
    # No escalation on repeats of a user-set section.
    assert resolved == pytest.approx([0.42, 0.33, 0.33, 0.33])


# ---------------------------------------------------------------------------
# (d) Explicit flat intensity stays flat (no escalation)
# ---------------------------------------------------------------------------

FLAT_SONG = """
version: 1
song:
  title: "MacroFlat"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 7
  exports_root: "{exports_root}"
sections:
  intro:
    type: intro
    bars: 2
    intensity: 0.5
    instruments:
      drums: {{}}
  verse1:
    type: verse
    bars: 4
    intensity: 0.5
    instruments:
      drums: {{}}
  chorus1:
    type: chorus
    bars: 4
    intensity: 0.5
    instruments:
      drums: {{}}
arrangement:
  - intro
  - verse1
  - chorus1
  - verse1
  - chorus1
"""


def test_explicit_flat_intensity_produces_flat_plan(tmp_path):
    cfg = _load_cfg(tmp_path, FLAT_SONG.format(exports_root=tmp_path / "exports"))
    plan = plan_song(cfg=cfg, logger=logging.getLogger("test"))
    resolved = [ps.sec.intensity for ps in plan.planned_sections]
    assert resolved == pytest.approx([0.5, 0.5, 0.5, 0.5, 0.5])


# ---------------------------------------------------------------------------
# (c) Engines actually receive the resolved value
# ---------------------------------------------------------------------------

CHORUS_ONLY_SONG = """
version: 1
song:
  title: "MacroChorus"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 7
  exports_root: "{exports_root}"
sections:
  chorus1:
    type: chorus
    bars: 4
{intensity_line}
    instruments:
      drums: {{}}
arrangement:
  - chorus1
"""


def test_derived_intensity_reaches_drums_engine(tmp_path):
    """Derived chorus intensity (0.90) must produce the exact same drums
    output as an explicit `intensity: 0.9`, and different output from an
    explicit `intensity: 0.5` (the old flat default)."""
    cfg_derived = _load_cfg(
        tmp_path / "derived",
        CHORUS_ONLY_SONG.format(exports_root=tmp_path / "derived" / "exports", intensity_line=""),
    )
    cfg_explicit = _load_cfg(
        tmp_path / "explicit",
        CHORUS_ONLY_SONG.format(
            exports_root=tmp_path / "explicit" / "exports",
            intensity_line="    intensity: 0.9",
        ),
    )
    cfg_flat = _load_cfg(
        tmp_path / "flat",
        CHORUS_ONLY_SONG.format(
            exports_root=tmp_path / "flat" / "exports",
            intensity_line="    intensity: 0.5",
        ),
    )

    res_derived = _build(cfg_derived)
    res_explicit = _build(cfg_explicit)
    res_flat = _build(cfg_flat)

    ev_derived, _ = _note_events(res_derived.export_root)
    ev_explicit, _ = _note_events(res_explicit.export_root)
    ev_flat, _ = _note_events(res_flat.export_root)

    assert ev_derived == ev_explicit, (
        "drums output for a derived chorus intensity (0.90) should be identical "
        "to an explicit intensity: 0.9"
    )
    assert ev_derived != ev_flat, (
        "drums output should change when section intensity changes "
        "(derived 0.90 vs explicit 0.5)"
    )


VERSE_CHORUS_SONG = """
version: 1
song:
  title: "MacroShape"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 7
  exports_root: "{exports_root}"
sections:
  verse1:
    type: verse
    bars: 4
    instruments:
      drums: {{}}
  chorus1:
    type: chorus
    bars: 4
    instruments:
      drums: {{}}
arrangement:
  - verse1
  - chorus1
"""


def test_default_verse_and_chorus_differ_in_drums_velocity(tmp_path):
    """With no user intensities, the resolved arc (verse 0.65 -> chorus 0.90)
    must produce audibly different drums dynamics between the two sections."""
    cfg = _load_cfg(tmp_path, VERSE_CHORUS_SONG.format(exports_root=tmp_path / "exports"))
    res = _build(cfg)

    events, ticks_per_beat = _note_events(res.export_root)
    boundary_tick = 16 * ticks_per_beat  # verse is 4 bars of 4/4 = 16 beats

    verse_vels = [v for (_, tick, typ, _, v) in events if typ == "note_on" and v > 0 and tick < boundary_tick]
    chorus_vels = [v for (_, tick, typ, _, v) in events if typ == "note_on" and v > 0 and tick >= boundary_tick]

    assert verse_vels, "expected drums notes in the verse"
    assert chorus_vels, "expected drums notes in the chorus"

    verse_mean = sum(verse_vels) / len(verse_vels)
    chorus_mean = sum(chorus_vels) / len(chorus_vels)

    # The default chorus (0.90) should hit noticeably harder and/or busier
    # than the default verse (0.65).
    assert (chorus_mean, len(chorus_vels)) != (verse_mean, len(verse_vels)), (
        f"default verse and chorus produced identical drums dynamics "
        f"(mean velocity {verse_mean:.2f}, {len(verse_vels)} notes)"
    )
    assert chorus_mean > verse_mean or len(chorus_vels) > len(verse_vels), (
        f"default chorus should be louder or busier than default verse "
        f"(verse mean {verse_mean:.2f}/{len(verse_vels)} notes, "
        f"chorus mean {chorus_mean:.2f}/{len(chorus_vels)} notes)"
    )
