#!/usr/bin/env python3
"""Compare drums analysis outputs from the last two exports.

Validates that drums engine changes produce stable, deterministic output
by comparing both the TSV event data and visual grid output from the two
most recent builds.

Usage:
    python scripts/diff_last_two.py              # Default exports/ dir
    python scripts/diff_last_two.py path/to/exports

Exit codes:
    0 - Files are identical (success)
    1 - Files differ or error occurred

Example workflow:
    python -m produzre.cli build examples/drums/hats-demo.yaml -v
    python -m produzre.cli build examples/drums/hats-demo.yaml -v
    python scripts/diff_last_two.py
"""

import difflib
import sys
from pathlib import Path

# ANSI color codes (disabled when not a TTY)
USE_COLOR = sys.stdout.isatty()
RED = "\033[0;31m" if USE_COLOR else ""
GREEN = "\033[0;32m" if USE_COLOR else ""
YELLOW = "\033[1;33m" if USE_COLOR else ""
NC = "\033[0m" if USE_COLOR else ""

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_latest_exports(exports_dir: Path) -> tuple[Path, Path]:
    """Find the two most recent export directories."""
    subdirs = sorted(
        [d for d in exports_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if len(subdirs) < 2:
        print(f"{YELLOW}Only {len(subdirs)} export(s) found. Need at least two for comparison.{NC}", file=sys.stderr)
        print("Run your build twice, then re-run this script.", file=sys.stderr)
        sys.exit(1)
    return subdirs[0], subdirs[1]


def find_file(drums_dir: Path, pattern: str) -> Path | None:
    """Find a single file matching a glob pattern."""
    matches = list(drums_dir.glob(pattern))
    return matches[0] if matches else None


def compare_files(older: Path, newer: Path, label: str) -> bool:
    """Compare two files and print unified diff if they differ. Returns True if identical."""
    print("=" * 60)
    print(f"Comparing {label}...")
    print("=" * 60)

    older_lines = older.read_text().splitlines(keepends=True)
    newer_lines = newer.read_text().splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        older_lines, newer_lines,
        fromfile=str(older.name),
        tofile=str(newer.name),
    ))

    if not diff:
        print(f"{GREEN}Identical{NC}")
        return True
    else:
        for line in diff:
            print(line, end="")
        print(f"\n{RED}Files differ{NC}")
        return False


def main() -> int:
    exports_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "exports"

    if not exports_dir.is_dir():
        print(f"{RED}Error: Exports directory not found: {exports_dir}{NC}", file=sys.stderr)
        return 1

    print(f"Finding last two exports in {exports_dir}...")
    newer, older = find_latest_exports(exports_dir)

    print("Comparing:")
    print(f"  Newer: {newer.name}")
    print(f"  Older: {older.name}")
    print()

    # Find drums analysis directories
    newer_drums = newer / "analysis" / "drums"
    older_drums = older / "analysis" / "drums"

    for label, path in [("newer", newer_drums), ("older", older_drums)]:
        if not path.is_dir():
            print(f"{RED}Error: Drums analysis not found in {label} export: {path}{NC}", file=sys.stderr)
            return 1

    # Find TSV and grid files
    newer_tsv = find_file(newer_drums, "*_drums.events.tsv")
    older_tsv = find_file(older_drums, "*_drums.events.tsv")
    newer_grid = find_file(newer_drums, "*_drums.grid.txt")
    older_grid = find_file(older_drums, "*_drums.grid.txt")

    if not newer_tsv or not older_tsv:
        print(f"{RED}Error: Could not find TSV files in both exports{NC}", file=sys.stderr)
        return 1

    if not newer_grid or not older_grid:
        print(f"{RED}Error: Could not find grid files in both exports{NC}", file=sys.stderr)
        return 1

    # Compare files
    tsv_ok = compare_files(older_tsv, newer_tsv, "TSV event files")
    print()
    grid_ok = compare_files(older_grid, newer_grid, "grid visualization files")
    print()

    if tsv_ok and grid_ok:
        print(f"{GREEN}SUCCESS: Outputs are identical!{NC}")
        print("Your changes produce stable, deterministic output.")
        return 0
    else:
        print(f"{RED}FAILURE: Outputs differ!{NC}")
        print()
        print("This indicates non-deterministic behavior or a real change in output.")
        print("Review the diffs above to determine if this is expected.")
        print()
        print("Common causes:")
        print("  - RNG state not properly threaded through voice modules")
        print("  - Humanization enabled (should be 0.0 in test YAMLs)")
        print("  - Variation enabled (should be 0.0 in test YAMLs)")
        print("  - Missing 'seed' parameter in YAML")
        print("  - Intentional change to drums logic (verify expected)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
