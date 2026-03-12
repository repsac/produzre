"""Integration tests for Phases N0-N3.

Verifies the complete orchestration infrastructure:
- Phase N0: Engine specs with priority/requires/provides/roles
- Phase N1: PerformancePlan creation
- Phase N2: Priority-based engine ordering
- Phase N3: Dependency validation

These tests use real build commands to verify end-to-end functionality.
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_phase_n0_engines_have_orchestration_fields():
    """Phase N0: Engines should have priority, requires, provides, and roles fields."""
    yaml_content = """
version: 1
song:
  title: "EngineFieldsTest"
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
        # Use show-config to verify engine fields
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "show-config", yaml_path, "--format", "yaml"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Verify engines section exists
        assert "engines:" in output, "Engines section should be in config output"

        # Verify orchestration fields are present
        assert "priority:" in output, "Priority field should be present"
        assert "requires:" in output, "Requires field should be present"
        assert "provides:" in output, "Provides field should be present"
        assert "roles:" in output, "Roles field should be present"

        # Verify drums engine has expected values
        assert "drums:" in output
        assert "groove.cues" in output or "kick_pattern" in output, "Drums should provide groove data"

        assert result.returncode == 0, f"show-config failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_phase_n1_performance_plan_created():
    """Phase N1: PerformancePlan should be created during build."""
    yaml_content = """
version: 1
song:
  title: "PerfPlanTest"
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

        # Verify PerformancePlan creation is logged
        assert "PERFORMANCE_PLAN" in output, "PerformancePlan creation should be logged"
        assert "Created plan with" in output, "PerformancePlan details should be logged"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_phase_n2_priority_based_ordering():
    """Phase N2: Engines should execute in priority order."""
    yaml_content = """
version: 1
song:
  title: "PriorityTest"
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
      rhythm_gtr:
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

        # Find rendering order (log format includes section prefix)
        lines = output.split('\n')
        drums_idx = next((i for i, line in enumerate(lines) if "rendering drums (priority=1)" in line), -1)
        bass_idx = next((i for i, line in enumerate(lines) if "rendering bass (priority=2)" in line), -1)
        rhythm_idx = next((i for i, line in enumerate(lines) if "rendering rhythm_gtr (priority=3)" in line), -1)

        # Verify priority order is respected
        assert drums_idx != -1, f"Drums should be rendered. Output:\n{output}"
        assert bass_idx != -1, f"Bass should be rendered. Output:\n{output}"
        assert rhythm_idx != -1, f"Rhythm guitar should be rendered. Output:\n{output}"
        assert drums_idx < bass_idx, "Drums (priority=1) should render before bass (priority=2)"
        assert bass_idx < rhythm_idx, "Bass (priority=2) should render before rhythm guitar (priority=3)"

        assert result.returncode == 0, f"Build failed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


def test_phase_n3_dependency_validation_success():
    """Phase N3: Engines with no requirements should pass validation."""
    yaml_content = """
version: 1
song:
  title: "NoDepsTest"
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
        # This should succeed since no engines have requirements (Phase N3 default state)
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path, "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Should complete successfully
        assert "Dry run requested" in output, "Build should complete"
        assert result.returncode == 0, f"Build should succeed: {result.stderr}"

    finally:
        Path(yaml_path).unlink()


if __name__ == "__main__":
    test_phase_n0_engines_have_orchestration_fields()
    print("✓ test_phase_n0_engines_have_orchestration_fields passed")

    test_phase_n1_performance_plan_created()
    print("✓ test_phase_n1_performance_plan_created passed")

    test_phase_n2_priority_based_ordering()
    print("✓ test_phase_n2_priority_based_ordering passed")

    test_phase_n3_dependency_validation_success()
    print("✓ test_phase_n3_dependency_validation_success passed")

    print("\nAll Phases N0-N3 integration tests passed!")
