"""Shared test fixtures and helpers for Produzre tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_yaml(yaml_path: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
    """Build a YAML song file and return the completed process.

    Args:
        yaml_path: Path to the YAML file (relative to repo root).
        timeout: Build timeout in seconds.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    return subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", yaml_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_export_root(result: subprocess.CompletedProcess) -> str:
    """Extract the export root directory from build output."""
    for line in result.stderr.splitlines():
        if "Export root:" in line:
            return line.split("Export root:")[1].strip()
    raise AssertionError(f"No export root found in build output:\n{result.stderr}")


@pytest.fixture
def example_path():
    """Return a helper that resolves example paths relative to repo root."""
    def _resolve(relative: str) -> Path:
        p = REPO_ROOT / relative
        assert p.exists(), f"Example file not found: {p}"
        return p
    return _resolve
