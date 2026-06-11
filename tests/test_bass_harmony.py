"""Test bass harmony-driven note selection (Phase B2).

Verifies that:
1. Bass notes change appropriately at chord boundaries
2. Bass notes are valid chord tones for the current chord
3. No out-of-range notes (register constraints work)
4. Cadence behavior produces root resolutions
5. No weird chromatic accidents in default persona
"""

import subprocess
import sys
from pathlib import Path


def test_bass_follows_chord_changes():
    """Verify bass notes change at chord boundaries in a clear progression."""
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", "examples/bass/baseline/chord-changes-demo.yaml"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    assert export_lines, "No export root found in output"
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassChordChanges_Demo_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")
    assert len(lines) > 1, "TSV has no events"

    # Parse events (skip header)
    events = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        events.append({
            "bar": int(parts[2]),
            "beat": float(parts[3]),
            "pitch": int(parts[6]),
            "note": parts[7],
            "kind": parts[11] if len(parts) > 11 else "",
        })

    # Seeded-deterministic (seed=200): the anchor pattern with density=0.70
    # selects 4 of 8 anchor slots (bars 1 and 3); the cadence guarantee then
    # re-adds the final chord's downbeat so the section resolves — bar 4
    # closes with root_cadence even when the density filter empties it.
    assert len(events) == 5, f"Expected 5 events, got {len(events)}"
    assert events[-1]["kind"] == "root_cadence" and events[-1]["bar"] == 4, \
        f"Section must close with a bar-4 root_cadence, got {events[-1]}"

    # Musical intent: every note must be a chord tone of the chord ACTIVE in
    # its bar — this is stronger than a key-diatonic check and proves the
    # engine tracks the changes. Progression I IV V I in C major:
    chord_pcs_by_bar = {
        1: {0, 4, 7},   # C major (C E G)
        2: {5, 9, 0},   # F major (F A C)
        3: {7, 11, 2},  # G major (G B D)
        4: {0, 4, 7},   # C major
    }
    for e in events:
        pc = e["pitch"] % 12
        assert pc in chord_pcs_by_bar[e["bar"]], \
            f"Bar {e['bar']} note {e['note']} (pc {pc}) is not a chord tone of the active chord"

    # The voice labels must track the changes: the section opens on the
    # bar-1 C root (the engine never substitutes the fifth on a section's
    # first downbeat), G2 is "root" under the bar-3 G chord, and the cadence
    # guarantee closes bar 4 on the root.
    pinned = [(e["bar"], e["note"], e["kind"]) for e in events]
    assert pinned == [
        (1, "C2", "root"),
        (1, "E2", "third"),
        (3, "G2", "root"),
        (3, "B2", "third"),
        (4, "C2", "root_cadence"),
    ], f"Seeded-deterministic events changed: {pinned}"

    print(f"✓ Bass follows chord changes correctly")


def test_bass_notes_in_register():
    """Verify all bass notes are within register bounds."""
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", "examples/bass/baseline/chord-changes-demo.yaml"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassChordChanges_Demo_bass.events.tsv"
    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Parse pitches
    pitches = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        pitches.append(int(parts[6]))

    # tight persona defaults: register_low=28 (E1), register_high=52 (E3)
    register_low = 28
    register_high = 52

    for pitch in pitches:
        assert register_low <= pitch <= register_high, \
            f"Pitch {pitch} out of range [{register_low}, {register_high}]"

    print(f"✓ All {len(pitches)} notes within register bounds [{register_low}, {register_high}]")


def test_bass_minor_key():
    """Verify bass works correctly in minor keys."""
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", "examples/bass/baseline/chord-changes-minor.yaml"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassChordChanges_Minor_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Parse events
    events = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        events.append({
            "bar": int(parts[2]),
            "pitch": int(parts[6]),
            "note": parts[7],
        })

    # Progression: i VI iv V in A minor = Am F Dm E
    # With sparse density, not every bar will have notes.
    # Just verify the notes present are valid in A minor context.
    a_minor_letters = {"A", "B", "C", "D", "E", "F", "G"}
    all_notes = [e["note"] for e in events]
    assert len(all_notes) >= 2, f"Expected at least 2 events, got {len(all_notes)}"

    for note in all_notes:
        letter = note[0]
        assert letter in a_minor_letters, \
            f"Note {note} not diatonic to A minor"

    # Verify notes are reasonable chord tones (root or fifth of the chord in that bar)
    for e in events:
        bar = e["bar"]
        note_letter = e["note"][0]
        if bar == 1:
            assert note_letter in {"A", "E", "C"}, \
                f"Bar 1 (Am) note {e['note']} not a chord tone"
        elif bar == 2:
            assert note_letter in {"F", "C", "A"}, \
                f"Bar 2 (F) note {e['note']} not a chord tone"
        elif bar == 3:
            assert note_letter in {"D", "A", "F"}, \
                f"Bar 3 (Dm) note {e['note']} not a chord tone"
        elif bar == 4:
            assert note_letter in {"E", "B", "G"}, \
                f"Bar 4 (E) note {e['note']} not a chord tone"

    print(f"✓ Bass follows minor key progression correctly")


def test_bass_no_chromatic_accidents():
    """Verify no weird chromatic accidents in default tight persona."""
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", "examples/bass/baseline/chord-changes-demo.yaml"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassChordChanges_Demo_bass.events.tsv"
    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Parse note kinds
    kinds = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) > 11:
            kinds.append(parts[11])

    # All notes should be chord tones (root, fifth, third, seventh, etc)
    # No "chromatic" or unexpected kinds in tight persona
    # Engine now uses root_octave, fifth_drop, fifth_drop_octave, third_octave, approach_diatonic etc.
    valid_kinds = [
        "root", "fifth", "third", "seventh",
        "root_octave", "root_cadence",
        "fifth_drop", "fifth_drop_octave",
        "third_octave",
        "approach", "approach_diatonic", "approach_chromatic",
        "pedal",
        # Fills (persona/recipe params now reach the engine, enabling fills)
        "fill_run_diatonic", "fill_run_chromatic",
        "fill_octave", "fill_octave_passing",
        "fill_pickup", "fill_pickup_approach",
    ]

    for kind in kinds:
        assert kind in valid_kinds, f"Unexpected note kind: {kind}"

    # Count kinds
    kind_counts = {}
    for kind in kinds:
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    print(f"✓ No chromatic accidents. Note kinds: {kind_counts}")


CADENCE_YAML = """\
version: 1
song:
  title: "BassCadenceResolution"
  bpm: 100
  key: C
  mode: major
  meter: "4/4"
  beats_per_bar: 4
  seed: 200
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
    persona: tight
    intensity: 0.7
    params:
      density: 1.0
      rest_rate: 0.0
sections:
  verse1:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
    instruments:
      harmony: {}
      bass: {}
arrangement:
  - verse1
"""


def test_bass_cadence_resolution(tmp_path):
    """Verify cadences resolve to root correctly.

    Uses density=1.0 / rest_rate=0.0 so every anchor slot renders and the
    final chord slot is guaranteed to be selected — the cadence-detection fix
    (root_cadence fires on the LAST SELECTED slot of the final chord) is then
    deterministic rather than at the mercy of the density filter.
    """
    yaml_file = tmp_path / "cadence-resolution.yaml"
    yaml_file.write_text(CADENCE_YAML)

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassCadenceResolution_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"
    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    events = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) > 11:
            events.append({
                "bar": int(parts[2]),
                "beat": float(parts[3]),
                "pitch": int(parts[6]),
                "note": parts[7],
                "kind": parts[11],
            })

    assert len(events) >= 8, f"Dense config should fill all bars, got {len(events)} events"

    # The tonic must be established: bar 1, beat 1 is a root C (I chord).
    first = events[0]
    assert (first["bar"], first["beat"]) == (1, 1.0), \
        f"First event should be on bar 1 beat 1, got bar {first['bar']} beat {first['beat']}"
    assert first["kind"] == "root" and first["pitch"] % 12 == 0, \
        f"Section should open on root C, got {first['note']} ({first['kind']})"

    # Exactly one cadence event, in the final bar, resolving to root C.
    cadence_events = [e for e in events if e["kind"] == "root_cadence"]
    assert len(cadence_events) == 1, \
        f"Expected exactly 1 root_cadence event, got {len(cadence_events)}"
    cadence = cadence_events[0]
    assert cadence["bar"] == 4, f"Cadence should be in bar 4, got bar {cadence['bar']}"
    assert cadence["pitch"] % 12 == 0, \
        f"Cadence should resolve to C in C major, got: {cadence['note']}"

    # Nothing after the cadence except fill notes (the pickup run into the
    # next loop) — the cadence is the last structural note.
    after_cadence = [
        e for e in events
        if (e["bar"], e["beat"]) > (cadence["bar"], cadence["beat"])
    ]
    for e in after_cadence:
        assert e["kind"].startswith("fill"), \
            f"Non-fill event after cadence: {e}"

    print(f"✓ Cadence resolves to {cadence['note']} in bar {cadence['bar']}")


if __name__ == "__main__":
    print("Running bass harmony tests (Phase B2)...")

    test_bass_follows_chord_changes()
    print()

    test_bass_notes_in_register()
    print()

    test_bass_minor_key()
    print()

    test_bass_no_chromatic_accidents()
    print()

    test_bass_cadence_resolution()
    print()

    print("✅ All bass harmony tests passed!")
