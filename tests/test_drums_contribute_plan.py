"""Tests for drums contribute_plan hook (Phase N6).

Verifies that:
1. Drums exports rhythm.grid to PerformancePlan
2. Drums exports rhythm.accents to PerformancePlan
3. Data structures contain expected fields
4. Other engines can read these plan keys
"""

import sys
import subprocess
import tempfile
from pathlib import Path


def test_drums_exports_rhythm_grid():
    """Drums should export rhythm.grid with step information."""
    yaml_content = """
version: 1
song:
  title: "RhythmGridTest"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 2
    harmony:
      progression: "I IV"
    instruments:
      drums:
        intensity: 0.6

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run", "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Verify rhythm.grid was exported
        assert "[DRUMS_PLAN] Exported rhythm.grid:" in output, "Drums should export rhythm.grid"
        assert "steps/bar" in output, "Should log steps per bar"
        assert "total steps" in output, "Should log total steps"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_drums_exports_rhythm_accents():
    """Drums should export rhythm.accents with accent beat positions."""
    yaml_content = """
version: 1
song:
  title: "RhythmAccentsTest"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
    instruments:
      drums:
        intensity: 0.6

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run", "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Verify rhythm.accents was exported
        assert "[DRUMS_PLAN] Exported rhythm.accents:" in output, "Drums should export rhythm.accents"
        assert "accent beats" in output, "Should log accent beats count"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_drums_contribute_plan_called_before_render():
    """Drums contribute_plan should be called before render."""
    yaml_content = """
version: 1
song:
  title: "ContributePlanOrderTest"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 2
    harmony:
      progression: "I IV"
    instruments:
      harmony:
        intensity: 0.6
      drums:
        intensity: 0.6
      bass:
        intensity: 0.6

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run", "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Find positions of drums plan export and rendering
        lines = output.split('\n')

        plan_export_idx = -1
        drums_render_idx = -1
        bass_render_idx = -1

        for i, line in enumerate(lines):
            if "[DRUMS_PLAN] Exported rhythm.grid:" in line:
                plan_export_idx = i
            if "rendering drums (priority=1)" in line:
                drums_render_idx = i
            if "rendering bass (priority=2)" in line:
                bass_render_idx = i

        # Verify drums plan export happens before rendering
        assert plan_export_idx != -1, "Drums should export plan data"
        assert drums_render_idx != -1, "Drums should be rendered"
        assert bass_render_idx != -1, "Bass should be rendered"

        # Plan export should happen before bass renders (bass can use the data)
        assert plan_export_idx < bass_render_idx, \
            "Drums plan export should happen before bass renders"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_drums_with_bass_integration():
    """Test that drums exports plan data and bass can potentially use it."""
    yaml_content = """
version: 1
song:
  title: "DrumsBassPlanTest"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I IV V I"
    instruments:
      harmony:
        intensity: 0.7
      drums:
        intensity: 0.7
      bass:
        intensity: 0.7

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run", "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Verify drums exports plan data
        assert "[DRUMS_PLAN] Exported rhythm.grid:" in output
        assert "[DRUMS_PLAN] Exported rhythm.accents:" in output

        # Verify both instruments render successfully
        assert "rendering drums (priority=1)" in output
        assert "rendering bass (priority=2)" in output

        # Verify both produce events
        assert "drums:" in output, "Drums should produce events"
        assert "bass:" in output, "Bass should produce events"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_rhythm_grid_data_structure():
    """Verify rhythm.grid has expected fields and values."""
    yaml_content = """
version: 1
song:
  title: "RhythmGridStructureTest"
  bpm: 120
  key: C
  mode: ionian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 2
    harmony:
      progression: "I IV"
    instruments:
      drums:
        intensity: 0.6

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run", "-v"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # For 2 bars of 4/4 time:
        # - beats_per_bar = 4.0
        # - total_beats = 8.0
        # - steps_per_beat = 4 (16th notes)
        # - steps_per_bar = 16
        # - total_steps = 32

        assert "16 steps/bar" in output, "Should have 16 steps per bar (4 beats * 4 subdivisions)"
        assert "32 total steps" in output, "Should have 32 total steps (2 bars * 16 steps)"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


if __name__ == "__main__":
    # Run all tests
    test_drums_exports_rhythm_grid()
    print("✓ test_drums_exports_rhythm_grid passed")

    test_drums_exports_rhythm_accents()
    print("✓ test_drums_exports_rhythm_accents passed")

    test_drums_contribute_plan_called_before_render()
    print("✓ test_drums_contribute_plan_called_before_render passed")

    test_drums_with_bass_integration()
    print("✓ test_drums_with_bass_integration passed")

    test_rhythm_grid_data_structure()
    print("✓ test_rhythm_grid_data_structure passed")

    print("\nAll Phase N6 drums contribute_plan tests passed!")
