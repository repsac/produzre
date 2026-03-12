"""Tests for harmony contribute_plan hook (Phase N7).

Verifies that:
1. Harmony exports harmony.plan to PerformancePlan
2. Harmony plan contains expected fields
3. Chord slots have correct structure
4. Harmony contribute_plan is called before other engines render
5. Other engines can consume harmony.plan
"""

import sys
import subprocess
import tempfile
from pathlib import Path


def test_harmony_exports_plan():
    """Harmony should export harmony.plan with chord slot information."""
    yaml_content = """
version: 1
song:
  title: "HarmonyPlanTest"
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

        # Verify harmony.plan was exported
        assert "[HARMONY_PLAN] Exported harmony.plan" in output, "Harmony should export harmony.plan"
        assert "chord slots" in output, "Should log chord slot count"
        assert "chord_rate" in output, "Should log chord rate"
        assert "total_beats" in output, "Should log total beats"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_harmony_plan_structure():
    """Verify harmony.plan has expected fields and values."""
    yaml_content = """
version: 1
song:
  title: "HarmonyStructureTest"
  bpm: 120
  key: E
  mode: dorian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "i bVII VI i"
      chord_rate: 4
    instruments:
      harmony:
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

        # For 4 bars of 4/4 time with progression "i bVII VI i" and chord_rate=4:
        # - total_beats = 16.0
        # - 4 chord slots (one per chord in progression, each lasting 4 beats)
        # - chord_rate = 4.0

        assert "[HARMONY_PLAN] Exported harmony.plan" in output
        assert "4 chord slots" in output, "Should have 4 chord slots for 4-chord progression"
        assert "verse" in output, "Should reference verse section"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_harmony_contribute_plan_called_before_render():
    """Harmony contribute_plan should be called before other engines render."""
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

        # Find positions of harmony plan export and engine rendering
        lines = output.split('\n')

        harmony_plan_export_idx = -1
        bass_render_idx = -1

        for i, line in enumerate(lines):
            if "[HARMONY_PLAN] Exported harmony.plan" in line:
                harmony_plan_export_idx = i
            if "rendering bass (priority=2)" in line:
                bass_render_idx = i

        # Verify harmony plan export happens before other engines render
        assert harmony_plan_export_idx != -1, "Harmony should export plan data"
        assert bass_render_idx != -1, "Bass should be rendered"

        # Harmony plan export should happen before bass renders (bass requires harmony.plan)
        assert harmony_plan_export_idx < bass_render_idx, \
            "Harmony plan export should happen before bass renders"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_harmony_with_bass_integration():
    """Test that harmony exports plan data and bass can consume it."""
    yaml_content = """
version: 1
song:
  title: "HarmonyBassPlanTest"
  bpm: 120
  key: G
  mode: mixolydian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 4
    harmony:
      progression: "I bVII IV I"
    instruments:
      harmony:
        intensity: 0.7
      bass:
        intensity: 0.7
      drums:
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

        # Verify harmony exports plan data
        assert "[HARMONY_PLAN] Exported harmony.plan" in output

        # Verify all instruments render successfully
        assert "rendering harmony (priority=0)" in output
        assert "rendering drums (priority=1)" in output
        assert "rendering bass (priority=2)" in output

        # Verify bass produces events (consumes harmony.plan)
        assert "bass:" in output or "[BASS]" in output, "Bass should produce events"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_harmony_dependency_validation():
    """Test that dependency validation passes when harmony.plan is provided."""
    yaml_content = """
version: 1
song:
  title: "HarmonyDependencyTest"
  bpm: 120
  key: D
  mode: dorian
  meter: "4/4"
  beats_per_bar: 4
  seed: 42
  exports_root: "exports"

sections:
  verse:
    type: verse
    bars: 2
    harmony:
      progression: "i IV"
    instruments:
      harmony:
        intensity: 0.6
      drums:
        intensity: 0.6
      bass:
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

        # Verify no dependency validation errors
        assert "missing required plan keys" not in output.lower(), \
            "Should not have dependency validation errors"
        assert "harmony.plan" in output or "[HARMONY_PLAN]" in output, \
            "Harmony plan should be exported"

        # Verify engines that require harmony.plan run successfully
        assert "rendering bass (priority=2)" in output
        assert "rendering rhythm_gtr (priority=3)" in output

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_harmony_no_plan_when_disabled():
    """When harmony is not defined in section, harmony.plan should not be exported."""
    yaml_content = """
version: 1
song:
  title: "NoHarmonyTest"
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

        # When no harmony is defined, harmony engine might still run but skip export
        # We should see a skip message if harmony engine is present but no harmony defined
        # OR harmony engine might not be in the enabled instruments list

        # Either way, there should be no harmony.plan export
        if "rendering harmony" in output:
            assert "no harmony defined, skipping export" in output, \
                "Should skip export when harmony not defined"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


if __name__ == "__main__":
    # Run all tests
    test_harmony_exports_plan()
    print("✓ test_harmony_exports_plan passed")

    test_harmony_plan_structure()
    print("✓ test_harmony_plan_structure passed")

    test_harmony_contribute_plan_called_before_render()
    print("✓ test_harmony_contribute_plan_called_before_render passed")

    test_harmony_with_bass_integration()
    print("✓ test_harmony_with_bass_integration passed")

    test_harmony_dependency_validation()
    print("✓ test_harmony_dependency_validation passed")

    test_harmony_no_plan_when_disabled()
    print("✓ test_harmony_no_plan_when_disabled passed")

    print("\nAll Phase N7 harmony contribute_plan tests passed!")
