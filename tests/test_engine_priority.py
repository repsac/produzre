"""Tests for engine priority-based execution order (Phase N2).

Verifies that:
1. Only active instruments (used in sections) are rendered
2. Engines execute in priority order (ascending)
3. Disabled engines are skipped
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_bass_only_renders_only_bass():
    """A song with only bass should render only bass, not all engines."""
    yaml_content = """
version: 1
song:
  title: "BassOnlyTest"
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
      harmony: {}
      bass:
        intensity: 0.8

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

        # Verify bass is active (harmony is auto-included as a dependency)
        assert "'bass'" in output, "Bass should be an active instrument"

        # Verify bass is rendered
        assert "rendering bass (priority=2)" in output, "Bass should be rendered"
        assert "rendering drums" not in output, "Drums should not be rendered"
        assert "rendering rhythm_gtr" not in output, "Rhythm guitar should not be rendered"
        assert "rendering lead_gtr" not in output, "Lead guitar should not be rendered"

        # Verify bass appears in event summary
        assert "bass: " in output or "bass:" in output, "Bass events should be reported"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_priority_based_execution_order():
    """Engines should execute in priority order (drums=1, bass=2, rhythm=3, lead=4)."""
    yaml_content = """
version: 1
song:
  title: "AllInstrumentsTest"
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
      harmony: {}
      lead_gtr:
        intensity: 0.6
      bass:
        intensity: 0.6
      drums:
        intensity: 0.6
      rhythm_gtr:
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

        # Verify key instruments are active
        assert "'drums'" in output, "Drums should be an active instrument"
        assert "'bass'" in output, "Bass should be an active instrument"
        assert "'rhythm_gtr'" in output, "Rhythm guitar should be an active instrument"
        assert "'lead_gtr'" in output, "Lead guitar should be an active instrument"

        # Find the positions of each rendering line (log format includes section prefix)
        lines = output.split('\n')
        drums_idx = next((i for i, line in enumerate(lines) if "rendering drums (priority=1)" in line), -1)
        bass_idx = next((i for i, line in enumerate(lines) if "rendering bass (priority=2)" in line), -1)
        rhythm_idx = next((i for i, line in enumerate(lines) if "rendering rhythm_gtr (priority=3)" in line), -1)
        lead_idx = next((i for i, line in enumerate(lines) if "rendering lead_gtr (priority=4)" in line), -1)

        # Verify all were found
        assert drums_idx != -1, f"Drums rendering should be logged. Output:\n{output}"
        assert bass_idx != -1, f"Bass rendering should be logged. Output:\n{output}"
        assert rhythm_idx != -1, f"Rhythm guitar rendering should be logged. Output:\n{output}"
        assert lead_idx != -1, f"Lead guitar rendering should be logged. Output:\n{output}"

        # Verify priority order
        assert drums_idx < bass_idx, "Drums (priority=1) should render before bass (priority=2)"
        assert bass_idx < rhythm_idx, "Bass (priority=2) should render before rhythm guitar (priority=3)"
        assert rhythm_idx < lead_idx, "Rhythm guitar (priority=3) should render before lead guitar (priority=4)"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_missing_engine_warning():
    """If a section references an instrument with no registered engine, it should be skipped with a warning."""
    yaml_content = """
version: 1
song:
  title: "MissingEngineTest"
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
      harmony: {}
      bass:
        intensity: 0.6
      nonexistent_instrument:
        intensity: 0.5

arrangement:
  - verse
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Verify warning is logged
        assert "no engine registered for instrument 'nonexistent_instrument'" in output, \
            "Warning should be logged for missing engine"

        # Verify build still succeeds
        assert result.returncode == 0, f"Build should succeed despite missing engine: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


if __name__ == "__main__":
    test_bass_only_renders_only_bass()
    print("✓ test_bass_only_renders_only_bass passed")

    test_priority_based_execution_order()
    print("✓ test_priority_based_execution_order passed")

    test_missing_engine_warning()
    print("✓ test_missing_engine_warning passed")

    print("\nAll Phase N2 tests passed!")
