"""Test MIDI output determinism with byte-for-byte comparison.

Verifies that:
1. Same YAML + seed produces byte-identical MIDI files
2. Different seeds produce different MIDI outputs
3. Determinism holds across all demo files
4. Full song MIDI, stems, sections, and patterns are all deterministic
"""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Tuple, List


def get_midi_hash(midi_path: Path) -> str:
    """Compute SHA256 hash of a MIDI file for comparison."""
    with open(midi_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def extract_export_root(stderr: str) -> Path:
    """Extract export root directory from build output."""
    export_lines = [l for l in stderr.splitlines() if "Export root:" in l]
    assert export_lines, f"No export root line found in stderr:\n{stderr}"
    export_root_str = export_lines[0].split("Export root:")[1].strip()
    return Path(export_root_str)


def build_song(yaml_path: Path, timeout: int = 60) -> Tuple[Path, str]:
    """Build a song and return the export root and stderr output.

    Returns:
        Tuple of (export_root_path, stderr_output)
    """
    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"Build failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    export_root = extract_export_root(result.stderr)
    return export_root, result.stderr


def collect_all_midi_files(export_root: Path) -> List[Path]:
    """Collect all MIDI files from an export directory."""
    return sorted(export_root.rglob("*.mid"))


def test_full_song_determinism():
    """Two builds with same YAML/seed should produce byte-identical full song MIDI."""
    yaml_path = Path("examples/rhythm_gtr/sustained-chords-demo.yaml")
    assert yaml_path.exists(), f"Demo not found: {yaml_path}"

    # Build 1
    export_root_1, _ = build_song(yaml_path)
    full_song_1 = export_root_1 / "Sustained_Chords_Demo.mid"
    assert full_song_1.exists(), f"Full song MIDI not found: {full_song_1}"
    hash_1 = get_midi_hash(full_song_1)

    # Build 2
    export_root_2, _ = build_song(yaml_path)
    full_song_2 = export_root_2 / "Sustained_Chords_Demo.mid"
    assert full_song_2.exists(), f"Full song MIDI not found: {full_song_2}"
    hash_2 = get_midi_hash(full_song_2)

    assert hash_1 == hash_2, (
        f"Full song MIDI files differ between builds:\n"
        f"Build 1: {full_song_1} ({hash_1})\n"
        f"Build 2: {full_song_2} ({hash_2})"
    )


def test_stems_determinism():
    """Per-instrument stem MIDI files should be byte-identical across builds."""
    yaml_path = Path("examples/bass/advanced/motion-style-demo.yaml")
    assert yaml_path.exists(), f"Demo not found: {yaml_path}"

    # Build 1
    export_root_1, _ = build_song(yaml_path)
    stems_dir_1 = export_root_1 / "instruments"
    stem_files_1 = sorted(stems_dir_1.glob("*/BassMotionStyleDemo_*.mid"))
    assert len(stem_files_1) == 3, f"Expected 3 stem files (harmony excluded) in build 1, got {len(stem_files_1)}"

    # Build 2
    export_root_2, _ = build_song(yaml_path)
    stems_dir_2 = export_root_2 / "instruments"
    stem_files_2 = sorted(stems_dir_2.glob("*/BassMotionStyleDemo_*.mid"))
    assert len(stem_files_2) == 3, f"Expected 3 stem files (harmony excluded) in build 2, got {len(stem_files_2)}"

    # Compare file counts
    assert len(stem_files_1) == len(stem_files_2), (
        f"Different number of stems: {len(stem_files_1)} vs {len(stem_files_2)}"
    )

    # Compare each stem file
    for stem_1, stem_2 in zip(stem_files_1, stem_files_2):
        hash_1 = get_midi_hash(stem_1)
        hash_2 = get_midi_hash(stem_2)
        assert hash_1 == hash_2, (
            f"Stem file differs:\n"
            f"  {stem_1.name}: {hash_1}\n"
            f"  {stem_2.name}: {hash_2}"
        )


def test_all_midi_files_determinism():
    """All MIDI files (full song, stems, sections, patterns) should be deterministic."""
    yaml_path = Path("examples/rhythm_gtr/sustained-chords-demo.yaml")
    assert yaml_path.exists(), f"Demo not found: {yaml_path}"

    # Build 1
    export_root_1, _ = build_song(yaml_path)
    midi_files_1 = collect_all_midi_files(export_root_1)
    # Pattern-file count is content-dependent; updated after the RNG
    # derivation fix (rng.py) changed generated output (2026-06-10 review).
    assert len(midi_files_1) == 157, f"Expected 157 MIDI files in build 1, got {len(midi_files_1)}"

    # Build 2
    export_root_2, _ = build_song(yaml_path)
    midi_files_2 = collect_all_midi_files(export_root_2)
    assert len(midi_files_2) == 157, f"Expected 157 MIDI files in build 2, got {len(midi_files_2)}"

    # Compare file counts
    assert len(midi_files_1) == len(midi_files_2), (
        f"Different number of MIDI files: {len(midi_files_1)} vs {len(midi_files_2)}"
    )

    # Build hash maps by relative path (ignoring timestamp in export directory name)
    def get_hash_map(export_root: Path, midi_files: List[Path]) -> dict:
        hash_map = {}
        for midi_file in midi_files:
            # Get relative path from export root for comparison
            rel_path = midi_file.relative_to(export_root)
            hash_map[str(rel_path)] = get_midi_hash(midi_file)
        return hash_map

    hash_map_1 = get_hash_map(export_root_1, midi_files_1)
    hash_map_2 = get_hash_map(export_root_2, midi_files_2)

    # Compare all files
    differences = []
    for rel_path, hash_1 in hash_map_1.items():
        if rel_path not in hash_map_2:
            differences.append(f"Missing in build 2: {rel_path}")
            continue

        hash_2 = hash_map_2[rel_path]
        if hash_1 != hash_2:
            differences.append(
                f"Hash mismatch for {rel_path}:\n"
                f"  Build 1: {hash_1}\n"
                f"  Build 2: {hash_2}"
            )

    for rel_path in hash_map_2:
        if rel_path not in hash_map_1:
            differences.append(f"Missing in build 1: {rel_path}")

    assert not differences, (
        f"MIDI file differences found:\n" + "\n".join(differences)
    )


def test_different_seeds_produce_different_outputs():
    """Changing the seed should produce different MIDI outputs.

    This is a sanity check to ensure the seed is actually being used.
    """
    # We'll create two temporary YAML files with different seeds
    import tempfile
    import yaml

    base_yaml = Path("examples/rhythm_gtr/sustained-chords-demo.yaml")
    assert base_yaml.exists()

    # Read base config
    with open(base_yaml, "r") as f:
        config = yaml.safe_load(f)

    # Build with seed 800 (original)
    export_root_1, _ = build_song(base_yaml)
    full_song_1 = export_root_1 / "Sustained_Chords_Demo.mid"
    hash_1 = get_midi_hash(full_song_1)

    # Create temporary YAML with different seed
    config["song"]["seed"] = 999
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        temp_yaml = Path(f.name)

    try:
        # Build with seed 999
        export_root_2, _ = build_song(temp_yaml)
        full_song_2 = export_root_2 / "Sustained_Chords_Demo.mid"
        hash_2 = get_midi_hash(full_song_2)

        # Hashes should be DIFFERENT
        assert hash_1 != hash_2, (
            "Different seeds produced identical MIDI outputs - "
            "seed may not be affecting generation"
        )
    finally:
        # Clean up temp file
        temp_yaml.unlink()


def test_multiple_demo_determinism():
    """Test determinism across multiple demo files."""
    demo_files = [
        "examples/rhythm_gtr/sustained-chords-demo.yaml",
        "examples/bass/advanced/motion-style-demo.yaml",
    ]

    for yaml_path_str in demo_files:
        yaml_path = Path(yaml_path_str)
        if not yaml_path.exists():
            print(f"Skipping {yaml_path_str} (not found)")
            continue

        # Build twice
        export_root_1, _ = build_song(yaml_path)
        export_root_2, _ = build_song(yaml_path)

        # Collect all MIDI files
        midi_files_1 = collect_all_midi_files(export_root_1)
        midi_files_2 = collect_all_midi_files(export_root_2)

        # Compare counts
        assert len(midi_files_1) == len(midi_files_2), (
            f"Different MIDI file counts for {yaml_path.name}: "
            f"{len(midi_files_1)} vs {len(midi_files_2)}"
        )

        # Build hash maps
        def get_hash_map(export_root: Path, midi_files: List[Path]) -> dict:
            hash_map = {}
            for midi_file in midi_files:
                rel_path = midi_file.relative_to(export_root)
                hash_map[str(rel_path)] = get_midi_hash(midi_file)
            return hash_map

        hash_map_1 = get_hash_map(export_root_1, midi_files_1)
        hash_map_2 = get_hash_map(export_root_2, midi_files_2)

        # Compare all files
        for rel_path, hash_1 in hash_map_1.items():
            hash_2 = hash_map_2.get(rel_path)
            assert hash_2 is not None, f"Missing in build 2: {rel_path}"
            assert hash_1 == hash_2, (
                f"Hash mismatch in {yaml_path.name} for {rel_path}"
            )


if __name__ == "__main__":
    print("Running MIDI determinism tests...")

    print("\n1. Testing full song determinism...")
    test_full_song_determinism()
    print("✓ Full song MIDI is deterministic")

    print("\n2. Testing stems determinism...")
    test_stems_determinism()
    print("✓ Stem MIDI files are deterministic")

    print("\n3. Testing all MIDI files determinism...")
    test_all_midi_files_determinism()
    print("✓ All MIDI files are deterministic")

    print("\n4. Testing different seeds produce different outputs...")
    test_different_seeds_produce_different_outputs()
    print("✓ Different seeds produce different outputs")

    print("\n5. Testing multiple demos...")
    test_multiple_demo_determinism()
    print("✓ Multiple demos are deterministic")

    print("\n✅ All MIDI determinism tests passed!")
