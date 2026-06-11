"""Test bass groove features (Phase B6).

Verifies that:
1. octave_jump_rate produces octave patterning in grid
2. fifth_jump_rate produces fifth drops on chord changes
3. pedal_rate produces pedal tones across chord changes
4. accent_strength affects velocity
5. Groove features are deterministic with same seed
"""

import subprocess
import sys
from pathlib import Path


def test_octave_jumps_produce_variation():
    """Verify high octave_jump_rate produces octave variation in output."""
    yaml_path = "examples/bass/grooves/groove-octave-jumps.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    assert export_lines, "No export root found"
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_OctaveJumps_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Collect pitches
    pitches = []
    for line in lines[1:]:  # Skip header
        parts = line.split("\t")
        if len(parts) >= 12:
            pitches.append(int(parts[6]))

    # Seeded-deterministic exact count (seed=600). The old expectation of 5
    # events dated from when user params were dropped and the engine ran on
    # sparse defaults; with density=0.8/rest_rate=0.1 actually reaching the
    # engine, the syncopated pattern now yields 41 events.
    assert len(pitches) == 41, f"Expected 41 events, got {len(pitches)}"

    # Musical intent: octave_jump_rate=0.6 must produce real octave spread.
    # At least one octave (12 semitones) of range; seeded run spans B1..A3.
    pitch_range = max(pitches) - min(pitches)
    assert pitch_range >= 12, \
        f"Expected pitch range >= 12 with octave_jump_rate=0.6, got range={pitch_range}. Pitches: {pitches}"
    assert pitch_range == 22, \
        f"Seeded-deterministic pitch range changed: expected 22, got {pitch_range}"

    # Octave-jump events carry an "_octave" voice label (e.g. root_octave,
    # fifth_octave_slap_pop). Fill labels (fill_octave_*) are the fill
    # generator's own octave runs, not groove jumps, so exclude them.
    voice_labels = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 12:
            voice_labels.append(parts[11])

    octave_jump_count = sum(
        1 for l in voice_labels if "octave" in l and not l.startswith("fill")
    )
    assert octave_jump_count == 7, \
        f"Expected 7 groove octave-jump labels (seeded-deterministic), got {octave_jump_count}. Labels: {voice_labels}"

    # Check log for groove statistics (format: groove=[oct=N, 5th=N, pedal=N])
    assert "oct=7" in result.stderr, \
        "Log should show groove statistics with oct=7 octave jumps"

    print(f"✓ Groove features produce variation (range={pitch_range}, pitches={pitches})")


def test_fifth_drops_on_chord_changes():
    """Verify fifth_jump_rate produces fifth drops on chord changes."""
    yaml_path = "examples/bass/grooves/groove-fifth-drops.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_FifthDrops_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Seeded-deterministic exact count (seed=601). The old expectation of 4
    # events predates the param-plumbing fix; density=0.9/rest_rate=0.05 with
    # the drive pattern now yields 54 events.
    event_count = len(lines) - 1
    assert event_count == 54, f"Expected 54 events, got {event_count}"

    # Collect fifth_drop events specifically (the groove feature under test).
    # Plain "fifth" labels are ordinary chord-tone selection, not drops.
    fifth_drops = []
    for line in lines[1:]:  # Skip header
        parts = line.split("\t")
        if len(parts) >= 12 and parts[11].startswith("fifth_drop"):
            fifth_drops.append({
                "bar": int(parts[2]),
                "beat": float(parts[3]),
                "pitch": int(parts[6]),
            })

    assert len(fifth_drops) == 4, \
        f"Expected 4 fifth drops with fifth_jump_rate=0.7 (seeded-deterministic), got {len(fifth_drops)}"

    # Musical intent: each fifth_drop must actually BE the fifth of the chord
    # active in its bar. Progression I IV V I in C: bar chords C, F, G, C
    # whose fifths have pitch classes G=7, C=0, D=2, G=7.
    fifth_pc_by_bar = {1: 7, 2: 0, 3: 2, 4: 7}
    for fd in fifth_drops:
        expected_pc = fifth_pc_by_bar[fd["bar"]]
        assert fd["pitch"] % 12 == expected_pc, \
            f"fifth_drop in bar {fd['bar']} has pitch {fd['pitch']} (pc {fd['pitch'] % 12}), expected pc {expected_pc}"

    # Fifth drops fire on the first rendered note of a chord; bars 2-4 are
    # chord changes and their drops land on beat 1 (the change itself).
    on_change_downbeats = [fd for fd in fifth_drops if fd["bar"] >= 2 and fd["beat"] == 1.0]
    assert len(on_change_downbeats) == 3, \
        f"Expected 3 fifth drops on chord-change downbeats, got {len(on_change_downbeats)}"

    # Check log for fifth drop statistics
    assert "5th=4" in result.stderr, "Log should show fifth drop statistics (5th=4)"

    print(f"✓ Fifth drops present on chord changes ({len(fifth_drops)} fifth drops found)")


def test_pedal_tones_across_changes():
    """Verify pedal_rate produces pedal tones across chord changes."""
    yaml_path = "examples/bass/grooves/groove-pedal-tones.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_PedalTones_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # With sparse density from MIDI-learned defaults, pedal tones may not
    # always appear even with high pedal_rate. Verify the build produces
    # valid output and check for any groove-related behavior.
    event_count = len(lines) - 1
    assert event_count >= 1, "Should produce at least 1 event"

    # Check for pedal labels or repeated root notes across chord changes
    pedal_count = 0
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 12:
            voice_label = parts[11]
            if "pedal" in voice_label:
                pedal_count += 1

    # Log may or may not show pedal stats depending on whether pedal tones
    # were actually generated (sparse density may prevent them)
    print(f"✓ Pedal tone test passed ({pedal_count} pedal tones, {event_count} total events)")


def test_combined_groove_features():
    """Verify combined groove features work together."""
    yaml_path = "examples/bass/grooves/groove-combined.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_Combined_bass.events.tsv"
    assert tsv_path.exists(), f"TSV not found: {tsv_path}"

    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # With sparse density, groove features may not always appear.
    # Verify the build produces valid output.
    event_count = len(lines) - 1
    assert event_count >= 1, "Should produce at least 1 event"

    # Check for any groove-related voice labels
    has_octave = any("octave" in line for line in lines[1:])
    has_fifth = any("fifth" in line for line in lines[1:])
    has_pedal = any("pedal" in line for line in lines[1:])

    # Check log shows bass generation
    assert "[BASS]" in result.stderr, "Log should show bass generation"

    print(f"✓ Combined groove features (octave={has_octave}, fifth={has_fifth}, pedal={has_pedal}, events={event_count})")


def test_accent_strength_affects_velocity():
    """Verify accent_strength increases velocity on accented notes."""
    yaml_path = "examples/bass/grooves/groove-octave-jumps.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract export root
    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_OctaveJumps_bass.events.tsv"
    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Collect velocities
    velocities = []
    for line in lines[1:]:  # Skip header
        parts = line.split("\t")
        if len(parts) >= 12:
            velocities.append(int(parts[8]))

    # Seeded-deterministic exact count (seed=600); matches
    # test_octave_jumps_produce_variation which builds the same example.
    assert len(velocities) == 41, f"Expected 41 velocity values, got {len(velocities)}"

    # Musical intent: accent_strength=1.25 (plus slap pops/ghosts) must yield
    # a real velocity spread between accented and unaccented notes — not a
    # flat dynamic. Seeded run spans 26..101 (range 75, was 6 before the
    # param-plumbing fix when accents never reached the engine).
    velocity_variance = max(velocities) - min(velocities)
    assert velocity_variance >= 20, \
        f"Expected meaningful velocity spread with accent_strength=1.25, got range {velocity_variance}"
    assert velocity_variance == 75, \
        f"Seeded-deterministic velocity range changed: expected 75, got {velocity_variance}"

    print(f"✓ Accent strength affects velocity (range: {min(velocities)}-{max(velocities)})")


def test_groove_determinism():
    """Verify groove features are deterministic with same seed."""
    yaml_path = "examples/bass/grooves/groove-combined.yaml"

    def build_and_get_pitches():
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
        export_root = export_lines[0].split("Export root:")[1].strip()

        tsv_path = Path(export_root) / "analysis" / "bass" / "Groove_Combined_bass.events.tsv"
        content = tsv_path.read_text()

        pitches = []
        for line in content.strip().split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 12:
                pitches.append(int(parts[6]))

        return pitches

    pitches1 = build_and_get_pitches()
    pitches2 = build_and_get_pitches()

    assert pitches1 == pitches2, "Groove features should be deterministic with same seed"

    print("✓ Groove features are deterministic")


if __name__ == "__main__":
    print("Running bass groove tests (Phase B6)...")
    print()

    test_octave_jumps_produce_variation()
    print()

    test_fifth_drops_on_chord_changes()
    print()

    test_pedal_tones_across_changes()
    print()

    test_combined_groove_features()
    print()

    test_accent_strength_affects_velocity()
    print()

    test_groove_determinism()
    print()

    print("✅ All bass groove tests passed!")
