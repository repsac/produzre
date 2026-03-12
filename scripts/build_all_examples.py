#!/usr/bin/env python3
"""Build all example YAML files and report results.

Usage:
    python scripts/build_all_examples.py              # Build all examples
    python scripts/build_all_examples.py --validate   # Validate before building
    python scripts/build_all_examples.py --clean      # Clean exports first
    python scripts/build_all_examples.py --dir genres  # Build only examples/genres/
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ANSI color codes (disabled when not a TTY)
USE_COLOR = sys.stdout.isatty()
RED = "\033[0;31m" if USE_COLOR else ""
GREEN = "\033[0;32m" if USE_COLOR else ""
YELLOW = "\033[1;33m" if USE_COLOR else ""
NC = "\033[0m" if USE_COLOR else ""

# Resolve project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_examples(search_dir: Path) -> list[Path]:
    """Find all .yaml files under search_dir, sorted by path."""
    return sorted(search_dir.rglob("*.yaml"))


def run_cli(command: str, yaml_path: Path, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a produzre CLI command using the current Python interpreter."""
    return subprocess.run(
        [sys.executable, "-m", "produzre.cli", command, str(yaml_path)],
        capture_output=capture,
        text=True,
        cwd=PROJECT_ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build all Produzre example YAML files.")
    parser.add_argument("--validate", action="store_true", help="Validate YAML before building")
    parser.add_argument("--clean", action="store_true", help="Clean exports directory first")
    parser.add_argument("--dir", dest="subdir", default="", help="Only build examples in examples/<subdir>/")
    args = parser.parse_args()

    print("=== Produzre Example Build Script ===")
    print()

    # Clean exports if requested
    exports_dir = PROJECT_ROOT / "exports"
    if args.clean and exports_dir.exists():
        print("Cleaning exports directory...")
        shutil.rmtree(exports_dir)
        exports_dir.mkdir()
        print("Cleaned")
        print()

    # Determine search directory
    search_dir = PROJECT_ROOT / "examples"
    if args.subdir:
        search_dir = search_dir / args.subdir
        if not search_dir.is_dir():
            print(f"{RED}Directory not found: {search_dir}{NC}")
            return 1

    # Find example files
    print(f"Finding example files in {search_dir.relative_to(PROJECT_ROOT)}/ ...")
    examples = find_examples(search_dir)

    if not examples:
        print(f"{RED}No example files found in {search_dir.relative_to(PROJECT_ROOT)}/{NC}")
        return 1

    total = len(examples)
    print(f"Found {total} example files")
    print()

    # Build each example
    success = 0
    failed = 0
    failed_files: list[Path] = []

    for i, example in enumerate(examples, 1):
        rel_path = example.relative_to(PROJECT_ROOT)
        print(f"[{i}/{total}] Building {rel_path} ...")

        # Validate first if requested
        if args.validate:
            result = run_cli("validate", example)
            if result.returncode == 0:
                print("  Validation passed")
            else:
                print(f"  {YELLOW}Validation warnings{NC}")

        # Build the example
        result = run_cli("build", example)
        if result.returncode == 0:
            print(f"  {GREEN}Build successful{NC}")
            success += 1
        else:
            print(f"  {RED}Build failed{NC}")
            failed += 1
            failed_files.append(rel_path)

            # Show last 5 lines of error output
            error_text = (result.stderr or result.stdout or "").strip()
            if error_text:
                print("  Error details:")
                for line in error_text.splitlines()[-5:]:
                    print(f"    {line}")

        print()

    # Summary
    print("=== Build Summary ===")
    print(f"Total:   {total}")
    print(f"{GREEN}Success: {success}{NC}")
    if failed > 0:
        print(f"{RED}Failed:  {failed}{NC}")
        print(f"{RED}Failed files:{NC}")
        for f in failed_files:
            print(f"  {RED}{f}{NC}")

    print()
    if failed == 0:
        print(f"{GREEN}All {total} examples built successfully!{NC}")
        return 0
    else:
        print(f"{RED}{failed} of {total} examples failed to build{NC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
