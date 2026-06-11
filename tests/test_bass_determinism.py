"""Test bass engine determinism and golden outputs.

Verifies that:
1. Same YAML + seed produces identical TSV/grid outputs
2. Voice labels (root, octave, fifth, approach) appear in analysis
3. Structured logging shows effective parameters
"""

import subprocess
import sys
from pathlib import Path


def test_bass_determinism():
    """Two builds with same YAML/seed should produce identical TSV outputs."""
    yaml_path = Path("examples/bass/baseline/baseline-demo.yaml")
    assert yaml_path.exists(), f"Baseline demo not found: {yaml_path}"

    # Build 1
    result1 = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result1.returncode == 0, f"Build 1 failed:\nSTDOUT:\n{result1.stdout}\nSTDERR:\n{result1.stderr}"

    # Extract export root from output
    export_lines = [l for l in result1.stderr.splitlines() if "Export root:" in l]
    assert export_lines, f"No export root line found in stderr:\n{result1.stderr}"
    export_root_1 = export_lines[0].split("Export root:")[1].strip()
    tsv_1 = Path(export_root_1) / "analysis" / "bass" / "BassBaseline_bass.events.tsv"
    grid_1 = Path(export_root_1) / "analysis" / "bass" / "BassBaseline_bass.grid.txt"

    assert tsv_1.exists(), f"TSV not found: {tsv_1}"
    assert grid_1.exists(), f"Grid not found: {grid_1}"

    # Build 2
    result2 = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result2.returncode == 0, f"Build 2 failed:\nSTDOUT:\n{result2.stdout}\nSTDERR:\n{result2.stderr}"

    export_lines = [l for l in result2.stderr.splitlines() if "Export root:" in l]
    assert export_lines, f"No export root line found in stderr:\n{result2.stderr}"
    export_root_2 = export_lines[0].split("Export root:")[1].strip()
    tsv_2 = Path(export_root_2) / "analysis" / "bass" / "BassBaseline_bass.events.tsv"
    grid_2 = Path(export_root_2) / "analysis" / "bass" / "BassBaseline_bass.grid.txt"

    # Compare TSV files
    tsv_content_1 = tsv_1.read_text()
    tsv_content_2 = tsv_2.read_text()
    assert tsv_content_1 == tsv_content_2, "TSV files differ between builds"

    # Compare grid files
    grid_content_1 = grid_1.read_text()
    grid_content_2 = grid_2.read_text()
    assert grid_content_1 == grid_content_2, "Grid files differ between builds"


def test_bass_voice_labels():
    """Voice labels should appear in TSV output."""
    yaml_path = Path("examples/bass/baseline/baseline-demo.yaml")
    assert yaml_path.exists()

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassBaseline_bass.events.tsv"

    tsv_content = tsv_path.read_text()

    # Check that expected voice label families appear (deterministic with seed)
    assert "root" in tsv_content, "Missing 'root' voice label"
    assert "fifth" in tsv_content, "Missing 'fifth' voice label"
    assert "root_cadence" in tsv_content, "Missing 'root_cadence' voice label"

    # Verify exact event count and voice label distribution
    # (seeded-deterministic, seed=42). Old expectation of 6 events predates
    # the param-plumbing/cadence fixes; both sections now render and each
    # section closes with a root_cadence resolution.
    lines = tsv_content.strip().split("\n")
    event_count = len(lines) - 1  # minus header
    assert event_count == 11, f"Expected 11 events, got {event_count}"

    voice_labels = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 12:
            voice_labels.append(parts[11])
    assert voice_labels == [
        # verse1 (i bVII VI V in E dorian) — opens on root: the engine never
        # substitutes the fifth on a section's first downbeat.
        "root", "third", "third", "root", "root_cadence",
        # chorus1 (i iv V i)
        "root", "third", "root", "third", "fifth", "root_cadence",
    ], f"Unexpected voice labels: {voice_labels}"


def test_bass_structured_logging():
    """Structured logging should show effective parameters."""
    yaml_path = Path("examples/bass/baseline/baseline-demo.yaml")
    assert yaml_path.exists()

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    # Logging goes to stderr in Python logging
    output = result.stderr

    # Check for structured bass logging
    assert "[BASS]" in output, "Missing [BASS] log prefix"
    assert "intensity=" in output, "Missing intensity parameter"
    assert "Harmony:" in output, "Missing harmony info"


def test_bass_golden_comparison():
    """Compare against golden reference files."""
    yaml_path = Path("examples/bass/baseline/baseline-demo.yaml")
    golden_tsv = Path("tests/golden/bass/baseline.events.tsv")
    golden_grid = Path("tests/golden/bass/baseline.grid.txt")

    assert yaml_path.exists()
    assert golden_tsv.exists(), "Golden TSV not found - run script to generate"
    assert golden_grid.exists(), "Golden grid not found - run script to generate"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()
    tsv_path = Path(export_root) / "analysis" / "bass" / "BassBaseline_bass.events.tsv"
    grid_path = Path(export_root) / "analysis" / "bass" / "BassBaseline_bass.grid.txt"

    # Compare with golden files
    current_tsv = tsv_path.read_text()
    reference_tsv = golden_tsv.read_text()
    assert current_tsv == reference_tsv, "TSV differs from golden reference"

    current_grid = grid_path.read_text()
    reference_grid = golden_grid.read_text()
    assert current_grid == reference_grid, "Grid differs from golden reference"


if __name__ == "__main__":
    print("Running bass determinism tests...")
    test_bass_determinism()
    print("✓ Determinism test passed")

    test_bass_voice_labels()
    print("✓ Voice labels test passed")

    test_bass_structured_logging()
    print("✓ Structured logging test passed")

    test_bass_golden_comparison()
    print("✓ Golden comparison test passed")

    print("\n✅ All bass engine tests passed!")
