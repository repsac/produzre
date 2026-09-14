#!/usr/bin/env python3
"""Golden TSV tests for drums engine.

This test suite prevents "it sounded good yesterday" regressions by comparing
generated drum patterns against known-good golden TSV files.

The golden files are committed to the repository and represent the expected
output for specific example YAML configurations. Any changes to the drums
engine that alter the output will cause these tests to fail, requiring explicit
review and regeneration of the golden files.

Test cases:
- hats-demo.yaml: Hi-hat patterns with open/closed/pedal variations
- kick-demo.yaml: Kick drum patterns with syncopation and double-kick
- fills-demo.yaml: Fill patterns with various lengths and personas

Usage:
    # Run tests
    python tests/test_golden_drums.py

    # Regenerate golden files (after verifying changes are intentional)
    python tests/test_golden_drums.py --regenerate
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Test configuration: (yaml_file, instrument)
GOLDEN_TESTS = [
    ("examples/drums/hats-demo.yaml", "drums"),
    ("examples/drums/kick-demo.yaml", "drums"),
    ("examples/drums/fills-demo.yaml", "drums"),
]


def get_repo_root() -> Path:
    """Return the repository root directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def get_golden_path(yaml_file: str, instrument: str) -> Path:
    """Return the path to the golden TSV file for a test case."""
    repo_root = get_repo_root()
    yaml_stem = Path(yaml_file).stem
    return repo_root / "tests" / "golden" / f"{yaml_stem}_{instrument}.events.tsv"


def build_and_extract_tsv(yaml_file: str, instrument: str) -> Optional[str]:
    """Build a YAML file and extract the TSV output.

    Args:
        yaml_file: Path to YAML file (relative to repo root)
        instrument: Instrument name (e.g., "drums")

    Returns:
        TSV file contents as a string, or None if build failed.
    """
    repo_root = get_repo_root()
    yaml_path = repo_root / yaml_file

    if not yaml_path.exists():
        print(f"ERROR: YAML file not found: {yaml_path}")
        return None

    cmd = [sys.executable, "-m", "produzre.cli", "build", str(yaml_path)]
    try:
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True,
                                text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"ERROR: Build timed out for {yaml_file}")
        return None
    if result.returncode != 0:
        print(f"ERROR: Build failed for {yaml_file}\n{result.stdout}\n{result.stderr}")
        return None

    # Use this build's output path, even if another build finishes concurrently.
    roots = [line.split("Export root:", 1)[1].strip()
             for line in result.stderr.splitlines() if "Export root:" in line]
    if len(roots) != 1:
        print(f"ERROR: Expected one export root for {yaml_file}, got {roots}")
        return None
    export_root = Path(roots[0])
    if not export_root.is_absolute():
        export_root = repo_root / export_root
    tsv_files = sorted((export_root / "analysis" / instrument).glob(f"*_{instrument}.events.tsv"))
    if len(tsv_files) != 1:
        print(f"ERROR: Expected one TSV for {instrument} in {export_root}")
        return None
    return tsv_files[0].read_text(encoding="utf-8")


def compare_tsv(expected: str, actual: str, test_name: str) -> bool:
    """Compare two TSV strings and return True if they match.

    Args:
        expected: Expected TSV content
        actual: Actual TSV content
        test_name: Name of the test (for error reporting)

    Returns:
        True if the TSVs match exactly, False otherwise.
    """
    if expected == actual:
        return True

    # Generate unified diff for debugging
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)

    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile=f"{test_name} (golden)",
        tofile=f"{test_name} (actual)",
        lineterm="",
    )

    print(f"\n{'=' * 70}")
    print(f"MISMATCH: {test_name}")
    print(f"{'=' * 70}")
    print("".join(diff))
    print(f"{'=' * 70}\n")

    return False


def regenerate_golden(yaml_file: str, instrument: str) -> bool:
    """Regenerate a golden TSV file.

    Args:
        yaml_file: Path to YAML file (relative to repo root)
        instrument: Instrument name

    Returns:
        True if regeneration succeeded, False otherwise.
    """
    print(f"Regenerating golden file for {yaml_file} ({instrument})...")

    tsv_content = build_and_extract_tsv(yaml_file, instrument)
    if tsv_content is None:
        print(f"  FAILED: Could not generate TSV")
        return False

    golden_path = get_golden_path(yaml_file, instrument)
    golden_path.parent.mkdir(parents=True, exist_ok=True)
    golden_path.write_text(tsv_content, encoding="utf-8")

    print(f"  SUCCESS: Written to {golden_path}")
    return True


def run_test(yaml_file: str, instrument: str) -> bool:
    """Run a single golden TSV test.

    Args:
        yaml_file: Path to YAML file (relative to repo root)
        instrument: Instrument name

    Returns:
        True if test passed, False otherwise.
    """
    test_name = f"{Path(yaml_file).stem} ({instrument})"
    print(f"Testing {test_name}...", end=" ")

    golden_path = get_golden_path(yaml_file, instrument)
    if not golden_path.exists():
        print(f"FAIL (no golden file at {golden_path})")
        return False

    expected = golden_path.read_text(encoding="utf-8")
    actual = build_and_extract_tsv(yaml_file, instrument)

    if actual is None:
        print("FAIL (build failed)")
        return False

    if compare_tsv(expected, actual, test_name):
        print("PASS")
        return True
    else:
        print("FAIL")
        return False


def main() -> int:
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Run golden TSV tests for drums engine")
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate golden TSV files instead of testing",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    print(f"Repository root: {repo_root}")
    print(f"Test mode: {'REGENERATE' if args.regenerate else 'TEST'}\n")

    if args.regenerate:
        # Regenerate mode
        success_count = 0
        fail_count = 0

        for yaml_file, instrument in GOLDEN_TESTS:
            if regenerate_golden(yaml_file, instrument):
                success_count += 1
            else:
                fail_count += 1

        print(f"\nRegeneration complete: {success_count} succeeded, {fail_count} failed")
        return 0 if fail_count == 0 else 1

    else:
        # Test mode
        passed = 0
        failed = 0

        for yaml_file, instrument in GOLDEN_TESTS:
            if run_test(yaml_file, instrument):
                passed += 1
            else:
                failed += 1

        print(f"\nTests complete: {passed} passed, {failed} failed")

        if failed > 0:
            print("\nTo regenerate golden files after verifying changes:")
            print(f"  python {Path(__file__).name} --regenerate")

        return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
