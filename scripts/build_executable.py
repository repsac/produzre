#!/usr/bin/env python3
"""Build a standalone Produzre executable using PyInstaller.

The output is a single-file binary at dist/produzre (or dist/produzre.exe on
Windows) that bundles Python, all dependencies (mido, pyyaml), and resource
files (recipes, personas, engines.yml). Users can run it without installing
Python or any packages.

Prerequisites:
    pip install pyinstaller

Usage:
    python scripts/build_executable.py            # Build executable
    python scripts/build_executable.py --clean     # Clean previous build first

Output:
    dist/produzre       (macOS / Linux)
    dist/produzre.exe   (Windows)

The executable supports all produzre CLI commands:
    ./dist/produzre build examples/minimal.yaml
    ./dist/produzre validate my_song.yaml
    ./dist/produzre show-config my_song.yaml
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Build a standalone Produzre executable.",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove build/ and dist/ before building",
    )
    args = parser.parse_args()

    # Ensure we're in the project root
    spec_file = Path("produzre.spec")
    if not spec_file.exists():
        print("Error: Run this script from the project root (where produzre.spec is)")
        sys.exit(1)

    # Check for pyinstaller (try module import, then PATH)
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        if shutil.which("pyinstaller") is None:
            print("Error: pyinstaller not found. Install it with:")
            print("  pip install pyinstaller")
            sys.exit(1)

    # Clean previous build artifacts if requested
    if args.clean:
        print("Cleaning previous build...")
        for d in ("build", "dist"):
            if Path(d).exists():
                shutil.rmtree(d)

    print("Building standalone executable...")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "produzre.spec", "--noconfirm"],
    )

    if result.returncode != 0:
        print()
        print("Build failed!")
        sys.exit(result.returncode)

    print()
    print("Build complete!")
    print()

    # Determine expected output path
    exe_name = "produzre.exe" if platform.system() == "Windows" else "produzre"
    exe_path = Path("dist") / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Executable: {exe_path} ({size_mb:.1f} MB)")
        print()
        if platform.system() == "Windows":
            print("Test it with:")
            print(f"  .\\dist\\{exe_name} build examples\\minimal.yaml")
        else:
            print("Test it with:")
            print(f"  ./dist/{exe_name} build examples/minimal.yaml")
    else:
        print(f"Error: Expected output not found at {exe_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
