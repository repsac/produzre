"""End-to-end integration regression net for the 2026-06 fix session.

Each test pins one of the session's core fixes so it cannot silently regress:

1. Param plumbing — user params (pattern/density/rest_rate/intensity) actually
   reach the bass engine instead of being dropped in favor of defaults.
2. Harmony spelling — V7 renders a dominant seventh (b7), not a major seventh.
3. Section bounds — no engine (drums/rhythm_gtr/bass) spills events past its
   section window (turnaround/fill material must stay inside the section).
4. Persona precedence — explicit user params override persona presets.
5. Groove clock no-op — without groove indications, no groove resolution runs
   and all bass onsets stay on the straight 16th (0.25-beat) grid.

All configs use fixed seeds and zero humanization so outputs are
seeded-deterministic.
"""

import logging
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT


def _build_cli(yaml_path: Path) -> subprocess.CompletedProcess:
    """Build a YAML file via the CLI and return the completed process."""
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    return result


def _export_root(result: subprocess.CompletedProcess) -> Path:
    for line in result.stderr.splitlines():
        if "Export root:" in line:
            return REPO_ROOT / line.split("Export root:")[1].strip()
    raise AssertionError(f"No export root in output:\n{result.stderr}")


def _read_events(tsv_path: Path) -> list[dict]:
    """Parse an analysis events TSV into a list of dicts."""
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"
    lines = tsv_path.read_text().strip().split("\n")
    events = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        events.append({
            "section_id": parts[1],
            "bar": int(parts[2]),
            "beat": float(parts[3]),
            "start": float(parts[4]),
            "duration": float(parts[5]),
            "pitch": int(parts[6]),
            "note": parts[7],
            "velocity": int(parts[8]),
            "kind": parts[11],
        })
    return events


# ---------------------------------------------------------------------------
# 1. Param plumbing: user params reach the engine (dry-run via build_song API)
# ---------------------------------------------------------------------------

def test_param_plumbing_user_params_reach_engine(caplog):
    """rhythm-drive.yaml sets pattern=drive, density=0.70, rest_rate=0.15,
    intensity=0.70 — the engine log must echo the USER values, not engine
    defaults (density=0.57/rest_rate=0.24) or the metal persona/recipe values.
    """
    from produzre.config.load import load_root_config
    from produzre.orchestrate.build import build_song

    cfg = load_root_config(str(REPO_ROOT / "examples/bass/rhythm/rhythm-drive.yaml"))

    with caplog.at_level(logging.INFO):
        result = build_song(
            cfg=cfg,
            dry_run=True,
            export_sections=False,
            export_patterns=False,
            sections_absolute_timing=False,
        )

    # Dry run: planning + rendering happen, nothing written.
    assert result.dry_run is True
    assert result.export_root is None

    messages = [r.getMessage() for r in caplog.records]

    section_lines = [m for m in messages if "[BASS] Section" in m]
    assert section_lines, f"No [BASS] Section log line found in: {messages}"
    assert "intensity=0.70" in section_lines[0], \
        f"Expected user intensity=0.70 in: {section_lines[0]}"

    generated_lines = [m for m in messages if "[BASS]" in m and "Generated" in m]
    assert generated_lines, f"No [BASS] Generated log line found in: {messages}"
    gen = generated_lines[0]
    assert "pattern=drive" in gen, f"Expected user pattern=drive in: {gen}"
    assert "density=0.70" in gen, f"Expected user density=0.70 in: {gen}"
    assert "rest_rate=0.15" in gen, f"Expected user rest_rate=0.15 in: {gen}"

    # Seeded-deterministic (seed=301): the drive pattern at these settings
    # renders 41 bass events.
    assert result.events_per_instrument.get("bass") == 41, \
        f"Expected 41 bass events, got {result.events_per_instrument}"


# ---------------------------------------------------------------------------
# 2. V7 correctness: dominant seventh spelling (b7, never major 7)
# ---------------------------------------------------------------------------

V7_YAML = """\
version: 1
song:
  title: "E2E_V7"
  bpm: 100
  key: C
  mode: major
  meter: "4/4"
  beats_per_bar: 4
  seed: 77
  variation: 0.0
  humanize_velocity: 0.0
  humanize_timing: 0.0
  exports_root: "exports"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
instruments:
  bass:
    enabled: true
    intensity: 0.7
    params:
      rhythm_pattern: drive
      density: 1.0
      rest_rate: 0.0
sections:
  verse1:
    type: verse
    bars: 3
    harmony:
      progression: "I V7 I"
    instruments:
      harmony: {}
      bass: {}
arrangement:
  - verse1
"""


def test_v7_dominant_seventh_spelling(tmp_path):
    """Bar 2 carries the V7 (G7) chord: its root must be G (pc 7) and any
    chord-seventh events must be F (pc 5) — a dominant b7. F# (pc 6) sounding
    as the seventh would mean V7 was spelled as a major seventh (the pre-fix
    bug).
    """
    yaml_file = tmp_path / "e2e-v7.yaml"
    yaml_file.write_text(V7_YAML)
    result = _build_cli(yaml_file)

    events = _read_events(
        _export_root(result) / "analysis" / "bass" / "E2E_V7_bass.events.tsv"
    )
    bar2 = [e for e in events if e["bar"] == 2]
    assert bar2, "V7 bar (bar 2) has no bass events"

    # The chord change downbeat states the root G.
    downbeats = [e for e in bar2 if e["beat"] == 1.0]
    assert downbeats, "No event on the V7 downbeat"
    assert downbeats[0]["pitch"] % 12 == 7, \
        f"V7 downbeat should be root G (pc 7), got {downbeats[0]['note']}"

    # No F# (pc 6) anywhere under the V7 slot.
    pc6 = [e for e in bar2 if e["pitch"] % 12 == 6]
    assert not pc6, f"F# (pc 6) sounded under V7 — major-seventh spelling bug: {pc6}"

    # Any event labeled as the chord seventh must be F (pc 5).
    sevenths = [e for e in bar2 if e["kind"].startswith("seventh")]
    for e in sevenths:
        assert e["pitch"] % 12 == 5, \
            f"V7 chord seventh must be F (pc 5), got {e['note']} ({e['kind']})"
    # The dense drive pattern does walk onto the seventh for this seed.
    assert sevenths, "Expected the bass to voice the b7 under V7 (seeded-deterministic)"


# ---------------------------------------------------------------------------
# 3. Section bounds: turnaround/fill material stays inside its section
# ---------------------------------------------------------------------------

BOUNDS_YAML = """\
version: 1
song:
  title: "E2E_SectionBounds"
  bpm: 120
  key: G
  mode: major
  meter: "4/4"
  beats_per_bar: 4
  seed: 99
  variation: 0.0
  humanize_velocity: 0.0
  humanize_timing: 0.0
  exports_root: "exports"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
instruments:
  drums:
    enabled: true
    intensity: 0.7
  rhythm_gtr:
    enabled: true
    intensity: 0.8
  bass:
    enabled: true
    intensity: 0.7
sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
    instruments:
      harmony: {}
      drums: {}
      rhythm_gtr: {}
      bass: {}
  chorus1:
    type: chorus
    bars: 4
    harmony:
      progression: "I V vi IV"
    instruments:
      harmony: {}
      drums: {}
      rhythm_gtr: {}
      bass: {}
arrangement:
  - verse1
  - chorus1
"""

# Section windows in song-global beats: 4 bars x 4 beats each.
SECTION_WINDOWS = {"verse1": (0.0, 16.0), "chorus1": (16.0, 32.0)}


def test_events_stay_within_section_bounds(tmp_path):
    """The verse->chorus boundary is turnaround/pickup-prone (energy ramp,
    pickup hint). No instrument may start an event at/after its section's end:
    the timing fixes anchor turnarounds INSIDE the closing bar.
    """
    yaml_file = tmp_path / "e2e-bounds.yaml"
    yaml_file.write_text(BOUNDS_YAML)
    result = _build_cli(yaml_file)
    root = _export_root(result)

    tolerance = 0.01
    for inst in ("drums", "rhythm_gtr", "bass"):
        events = _read_events(
            root / "analysis" / inst / f"E2E_SectionBounds_{inst}.events.tsv"
        )
        assert events, f"No events for {inst}"

        sections_seen = set()
        for e in events:
            sections_seen.add(e["section_id"])
            start_b, end_b = SECTION_WINDOWS[e["section_id"]]
            assert e["start"] >= start_b - 1e-6, \
                f"{inst} event at {e['start']} starts before its section " \
                f"'{e['section_id']}' [{start_b}, {end_b})"
            assert e["start"] < end_b + tolerance, \
                f"{inst} event at {e['start']} starts at/after its section " \
                f"'{e['section_id']}' end {end_b}"

        # Non-vacuous: both sections must actually contain events.
        assert sections_seen == {"verse1", "chorus1"}, \
            f"{inst} missing events in some section: {sections_seen}"


# ---------------------------------------------------------------------------
# 4. Persona precedence: explicit user params beat persona presets
# ---------------------------------------------------------------------------

PERSONA_YAML = """\
version: 1
song:
  title: "E2E_Persona"
  bpm: 120
  key: C
  mode: major
  meter: "4/4"
  beats_per_bar: 4
  seed: 88
  variation: 0.0
  humanize_velocity: 0.0
  humanize_timing: 0.0
  exports_root: "exports"
exports:
  midi_text:
    enabled: true
    views: [events]
    subdiv: 16
instruments:
  bass:
    enabled: true
    persona: metal
    intensity: 0.7
    params:
{params}
sections:
  verse1:
    type: verse
    bars: 2
    harmony:
      progression: "I V"
    instruments:
      harmony: {{}}
      bass: {{}}
arrangement:
  - verse1
"""


def test_user_articulation_overrides_persona(tmp_path):
    """bass persona=metal presets articulation pick; an explicit user
    articulation_style: finger must win (merge chain persona < user params).
    """
    # Control: metal persona alone resolves to pick.
    control = tmp_path / "e2e-persona-control.yaml"
    control.write_text(PERSONA_YAML.format(params="      density: 0.9"))
    result = _build_cli(control)
    assert "style=pick" in result.stderr, \
        f"Control build: metal persona should resolve style=pick:\n{result.stderr}"

    # Override: user articulation_style=finger beats the persona's pick.
    override = tmp_path / "e2e-persona-override.yaml"
    override.write_text(PERSONA_YAML.format(params="      articulation_style: finger"))
    result = _build_cli(override)
    assert "style=finger" in result.stderr, \
        f"User articulation_style=finger should override persona:\n{result.stderr}"
    assert "style=pick" not in result.stderr, \
        "Persona's pick style leaked through despite user override"


# ---------------------------------------------------------------------------
# 5. Groove no-op: no groove indications -> no resolution, straight grid
# ---------------------------------------------------------------------------

def test_groove_noop_without_indications(tmp_path):
    """A config with no groove indications (no persona push/pull, no swing,
    no groove params) must not trigger the shared groove clock, and every
    bass onset must sit exactly on the straight 16th (0.25-beat) grid.
    """
    yaml_file = tmp_path / "e2e-groove-noop.yaml"
    yaml_file.write_text(V7_YAML)  # plain config: no persona, no groove params
    result = _build_cli(yaml_file)

    assert "groove feel resolved" not in result.stderr, \
        "Groove clock resolved a feel despite no groove indications:\n" + \
        "\n".join(l for l in result.stderr.splitlines() if "groove" in l.lower())

    events = _read_events(
        _export_root(result) / "analysis" / "bass" / "E2E_V7_bass.events.tsv"
    )
    assert events, "No bass events rendered"
    off_grid = [
        e["start"] for e in events
        if abs(e["start"] / 0.25 - round(e["start"] / 0.25)) > 1e-6
    ]
    assert not off_grid, f"Bass onsets off the 0.25 grid: {off_grid}"
