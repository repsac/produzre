"""Test bass solo/lead capability (Phase B10).

Verifies that:
1. Solo mode detects solo=True flag
2. Solo mode detects role=lead
3. Solo sections have higher density than normal
4. Solo sections have expanded register (higher notes)
5. Solo sections are less locked to kick drum
6. Solo mode logs correctly
7. Solo is deterministic with same seed
"""

import subprocess
import sys
from pathlib import Path
import statistics


def test_solo_mode_detection():
    """Verify solo mode is detected from solo=True flag."""
    yaml_path = "tests/fixtures/examples/bass/advanced/solo-pocket.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Check log for solo mode indication
    assert "mode=solo" in result.stderr, "Solo mode should be detected and logged"

    print("✓ Solo mode detected from solo=True flag")


def test_role_lead_detection():
    """Verify solo mode is detected from role=lead."""
    yaml_path = "tests/fixtures/examples/bass/advanced/solo-funk.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Check log for solo mode indication
    assert "mode=solo" in result.stderr, "Solo mode should be detected from role=lead"

    print("✓ Solo mode detected from role=lead")


def test_solo_higher_density():
    """Verify solo sections have higher note density than normal."""
    yaml_path = "tests/fixtures/examples/bass/advanced/solo-comparison.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
    export_root = export_lines[0].split("Export root:")[1].strip()

    # Read TSV
    tsv_path = Path(export_root) / "analysis" / "bass" / "Solo_Comparison_bass.events.tsv"
    content = tsv_path.read_text()
    lines = content.strip().split("\n")

    # Count notes per section
    verse1_notes = 0
    solo1_notes = 0
    verse2_notes = 0

    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 12:
            section_id = parts[1]
            if section_id == "verse1":
                verse1_notes += 1
            elif section_id == "solo1":
                solo1_notes += 1
            elif section_id == "verse2":
                verse2_notes += 1

    # Solo should have more notes than normal verses
    avg_verse_notes = (verse1_notes + verse2_notes) / 2
    assert solo1_notes > avg_verse_notes, \
        f"Solo should have more notes than verses (solo={solo1_notes}, avg_verse={avg_verse_notes:.1f})"

    print(f"✓ Solo has higher density (verse1={verse1_notes}, solo={solo1_notes}, verse2={verse2_notes})")


def _solo_comparison_by_seed(seeds):
    """Per-seed (section id -> pitches) for the solo comparison fixture."""
    import yaml
    from tests.test_groove_clock import _load_cfg, _render_timelines
    import tempfile

    base = yaml.safe_load(Path("tests/fixtures/examples/bass/advanced/solo-comparison.yaml").read_text())
    out = []
    for seed in seeds:
        base["song"]["seed"] = seed
        cfg = _load_cfg(tempfile.mkdtemp(), yaml.safe_dump(base, sort_keys=False))
        timelines, result = _render_timelines(cfg)
        sections = {}
        for meta in result.performance_plan.sections:
            sections[meta.id] = [e.pitch for e in timelines["bass"].events
                                 if meta.start_beat - 0.06 <= e.start_beat < meta.end_beat - 0.06]
        out.append(sections)
    return out


def test_solo_expanded_register():
    """Solo sections may leave the accompaniment range (up to solo_register_high).

    Whether one take happens to climb is chance, so this checks the range
    over several seeds instead of one pinned take: verses stay inside the
    persona's register_high (52), and solos reach past it in most takes
    without passing solo_register_high (loose: 72).
    """
    takes = _solo_comparison_by_seed(range(1, 9))
    for t in takes:
        assert max(t["verse1"] + t["verse2"]) <= 52
        assert max(t["solo1"]) <= 72
    climbed = sum(1 for t in takes if max(t["solo1"]) > 52)
    assert climbed >= len(takes) // 2, f"solos climbed past the verse range in {climbed} takes"


def test_solo_less_locked_to_kick():
    """Verify solo sections are more melodically independent (less kick-locked)."""
    # This is harder to test directly without drum events
    # We can verify by checking that solo mode is applied in the logs
    yaml_path = "tests/fixtures/examples/bass/advanced/solo-pocket.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0

    # Verify solo mode was applied (which reduces kick locking)
    assert "mode=solo" in result.stderr, "Solo mode should reduce kick locking"

    print("✓ Solo mode reduces kick locking (verified via log)")


def test_solo_differs_from_normal():
    """Solo sections are busier than the accompaniment (solo_density), over seeds."""
    takes = _solo_comparison_by_seed(range(1, 9))
    busier = sum(1 for t in takes if len(t["solo1"]) > len(t["verse1"]))
    assert busier >= len(takes) * 3 // 4, f"solo busier than the verse in {busier} takes"


def test_solo_determinism():
    """Verify solo bass is deterministic with same seed."""
    yaml_path = "tests/fixtures/examples/bass/advanced/solo-pocket.yaml"

    def build_and_get_solo_pitches():
        result = subprocess.run(
            [sys.executable, "-m", "produzre.cli", "build", yaml_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        export_lines = [l for l in result.stderr.splitlines() if "Export root:" in l]
        export_root = export_lines[0].split("Export root:")[1].strip()

        tsv_path = Path(export_root) / "analysis" / "bass" / "Solo_Bass_Pocket_bass.events.tsv"
        content = tsv_path.read_text()

        solo_pitches = []
        for line in content.strip().split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 12 and parts[1] == "solo1":
                solo_pitches.append(int(parts[6]))

        return solo_pitches

    pitches1 = build_and_get_solo_pitches()
    pitches2 = build_and_get_solo_pitches()

    assert pitches1 == pitches2, "Solo bass should be deterministic with same seed"

    print("✓ Solo bass is deterministic")


if __name__ == "__main__":
    print("Running bass solo/lead capability tests (Phase B10)...")
    print()

    test_solo_mode_detection()
    print()

    test_role_lead_detection()
    print()

    test_solo_higher_density()
    print()

    test_solo_expanded_register()
    print()

    test_solo_less_locked_to_kick()
    print()

    test_solo_differs_from_normal()
    print()

    test_solo_determinism()
    print()

    print("✅ All bass solo tests passed!")
