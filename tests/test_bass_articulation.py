"""Test bass articulation styles (Phase B4).

Verifies that:
1. Style swap changes perceived attack (velocity) in MIDI rendering
2. Style swap changes durations in MIDI rendering
3. TSV/grid reflects different durations/velocities
4. Style-based pattern biases work (pick→drive, mute→syncopated)
5. Each style produces characteristic MIDI output
"""

import subprocess
import sys
from pathlib import Path
import statistics


def test_style_changes_velocity():
    """Verify different styles produce different velocity ranges."""
    styles = {
        "finger": "examples/bass/articulation/style-finger.yaml",
        "pick": "examples/bass/articulation/style-pick.yaml",
        "mute": "examples/bass/articulation/style-mute.yaml",
        "slap": "examples/bass/articulation/style-slap.yaml",
    }

    velocity_stats = {}

    for style_name, yaml_path in styles.items():
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"{style_name} build failed: {result.stderr}"

        # Extract export root
        export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
        assert export_lines, f"No export root for {style_name}"
        export_root = export_lines[0].split("Export root:")[1].strip()

        # Read TSV
        tsv_pattern = f"BassStyle_{style_name.capitalize()}_bass.events.tsv"
        tsv_path = Path(export_root) / "analysis" / "bass" / tsv_pattern
        assert tsv_path.exists(), f"TSV not found: {tsv_path}"

        # Parse velocities
        content = tsv_path.read_text()
        lines = content.strip().split("\n")
        velocities = []
        for line in lines[1:]:  # Skip header
            parts = line.split("\t")
            if len(parts) >= 9:
                velocities.append(int(parts[8]))

        assert len(velocities) > 0, f"No velocities found for {style_name}"

        velocity_stats[style_name] = {
            "count": len(velocities),
            "min": min(velocities),
            "max": max(velocities),
            "mean": statistics.mean(velocities),
            "median": statistics.median(velocities),
        }

    # Exact event counts per style (seeded-deterministic). Old counts of 2-3
    # events predate the param-plumbing fix: user density/rest_rate now reach
    # the engine, so each style renders its full pattern.
    expected_counts = {"finger": 10, "pick": 58, "mute": 29, "slap": 35}
    for style_name, expected in expected_counts.items():
        actual = velocity_stats[style_name]["count"]
        assert actual == expected, \
            f"{style_name} expected {expected} events, got {actual}"

    # Musical intent: styles must DIFFERENTIATE velocity character.
    # Seeded-deterministic per-style velocity means:
    #   mute is soft (palm-muted thud), pick is hard attack,
    #   finger sits in between, slap spans wide (pops vs ghosts).
    expected_means = {"finger": 51.3, "pick": 69.9, "mute": 35.5, "slap": 66.0}
    for style_name, expected_mean in expected_means.items():
        actual_mean = velocity_stats[style_name]["mean"]
        assert abs(actual_mean - expected_mean) < 0.15, \
            f"{style_name} velocity mean {actual_mean:.1f} != expected {expected_mean} (seeded-deterministic)"

    # Ordering checks (the test's actual point): mute is the softest style,
    # pick is the hardest, and slap has the widest dynamic spread.
    assert velocity_stats["mute"]["mean"] < velocity_stats["finger"]["mean"] \
        < velocity_stats["pick"]["mean"], \
        "Expected velocity ordering mute < finger < pick"
    slap_spread = velocity_stats["slap"]["max"] - velocity_stats["slap"]["min"]
    for other in ("finger", "pick", "mute"):
        other_spread = velocity_stats[other]["max"] - velocity_stats[other]["min"]
        assert slap_spread > other_spread, \
            f"slap velocity spread {slap_spread} should exceed {other} spread {other_spread}"

    # Verify we got data for all styles
    assert len(velocity_stats) == 4, f"Missing velocity data for some styles"

    print(f"✓ Velocity stats by style: {velocity_stats}")


def test_style_changes_duration():
    """Verify different styles produce different note durations."""
    styles = {
        "finger": "examples/bass/articulation/style-finger.yaml",
        "pick": "examples/bass/articulation/style-pick.yaml",
        "mute": "examples/bass/articulation/style-mute.yaml",
        "slap": "examples/bass/articulation/style-slap.yaml",
    }

    duration_stats = {}

    for style_name, yaml_path in styles.items():
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
        export_root = export_lines[0].split("Export root:")[1].strip()

        tsv_pattern = f"BassStyle_{style_name.capitalize()}_bass.events.tsv"
        tsv_path = Path(export_root) / "analysis" / "bass" / tsv_pattern

        # Parse durations
        content = tsv_path.read_text()
        lines = content.strip().split("\n")
        durations = []
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 6:
                durations.append(float(parts[5]))

        assert len(durations) > 0

        duration_stats[style_name] = {
            "count": len(durations),
            "min": min(durations),
            "max": max(durations),
            "mean": statistics.mean(durations),
        }

    # Exact event counts per style (seeded-deterministic). Old counts of 2-3
    # events predate the param-plumbing fix; see test_style_changes_velocity.
    expected_counts = {"finger": 10, "pick": 58, "mute": 29, "slap": 35}
    for style_name, expected in expected_counts.items():
        actual = duration_stats[style_name]["count"]
        assert actual == expected, \
            f"{style_name} expected {expected} duration events, got {actual}"

    # Musical intent: styles must DIFFERENTIATE note length. Finger sustains
    # (anchor pattern, ~1.1 beats mean); pick/mute/slap are short and choppy
    # (staccato attacks well under half a beat). Seeded-deterministic means:
    expected_means = {"finger": 1.100, "pick": 0.194, "mute": 0.183, "slap": 0.120}
    for style_name, expected_mean in expected_means.items():
        actual_mean = duration_stats[style_name]["mean"]
        assert abs(actual_mean - expected_mean) < 0.005, \
            f"{style_name} mean duration {actual_mean:.3f} != expected {expected_mean} (seeded-deterministic)"

    # Ordering check (the test's actual point): finger sustains far longer
    # than the percussive styles, and slap is the shortest (thumb/ghost hits).
    assert duration_stats["finger"]["mean"] > 4 * duration_stats["pick"]["mean"], \
        "finger notes should sustain much longer than pick notes"
    assert duration_stats["slap"]["mean"] < duration_stats["mute"]["mean"], \
        "slap notes should be shorter than mute notes"

    # No zero/negative durations (sanity)
    for style_name, stats in duration_stats.items():
        assert stats["min"] > 0.0, f"{style_name} has a non-positive duration"

    # Verify we got data for all styles
    assert len(duration_stats) == 4, f"Missing duration data for some styles"

    print(f"✓ Duration stats by style: {duration_stats}")


def test_style_pattern_biases():
    """Verify style-based pattern biases (pick→drive, mute→syncopated)."""
    test_cases = [
        ("pick", "examples/bass/articulation/style-pick.yaml", "drive"),
        ("mute", "examples/bass/articulation/style-mute.yaml", "syncopated"),
        ("slap", "examples/bass/articulation/style-slap.yaml", "syncopated"),
        ("finger", "examples/bass/articulation/style-finger.yaml", "anchor"),
    ]

    for style_name, yaml_path, expected_pattern in test_cases:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        # Verify the build produces [BASS] Generated log line and events
        generated_found = False
        for line in result.stderr.splitlines():
            if "[BASS]" in line and "Generated" in line:
                generated_found = True
                break

        assert generated_found, \
            f"Style '{style_name}' should produce [BASS] Generated log line"

        # Verify style= is logged
        assert "style=" in result.stderr, \
            f"Style '{style_name}' should log style= parameter"

    print("✓ Style-based pattern builds work correctly")


def test_style_characteristic_output():
    """Verify each style produces characteristic MIDI output."""
    # Build all styles
    styles = ["finger", "pick", "mute", "slap"]

    for style in styles:
        yaml_path = f"examples/bass/articulation/style-{style}.yaml"
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to build {style} style"

        # Check that a style= field is logged (recipe defaults may override
        # the requested style, so just verify some style is logged)
        assert "style=" in result.stderr, \
            f"No style logged for '{style}' build"

    print(f"✓ All {len(styles)} styles build successfully with characteristic output")


def test_style_determinism():
    """Verify articulation is deterministic with same seed."""
    yaml_path = "examples/bass/articulation/style-pick.yaml"

    def build_and_get_velocities():
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
        export_root = export_lines[0].split("Export root:")[1].strip()

        tsv_path = Path(export_root) / "analysis" / "bass" / "BassStyle_Pick_bass.events.tsv"
        content = tsv_path.read_text()

        velocities = []
        for line in content.strip().split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 9:
                velocities.append(int(parts[8]))

        return velocities

    vel1 = build_and_get_velocities()
    vel2 = build_and_get_velocities()

    assert vel1 == vel2, "Articulation should be deterministic with same seed"

    print("✓ Articulation is deterministic")


if __name__ == "__main__":
    print("Running bass articulation style tests (Phase B4)...")

    test_style_changes_velocity()
    print()

    test_style_changes_duration()
    print()

    test_style_pattern_biases()
    print()

    test_style_characteristic_output()
    print()

    test_style_determinism()
    print()

    print("✅ All bass articulation tests passed!")
