from __future__ import annotations

"""YAML I/O helpers.

This module centralizes YAML loading behavior so that parsing is consistent
across the codebase.

Design goals:
- Keep the helper small and reusable.
- Avoid imposing schema rules at this layer; callers decide whether the parsed
  object must be a mapping, list, etc.
- Use safe loading only (`yaml.safe_load`).

All file paths are handled with `pathlib` for OS portability.
"""

import pathlib
from typing import Any

import yaml


def read_yaml_file(path: pathlib.Path) -> Any:
    """Read YAML from disk and return the raw parsed object.

    This function intentionally does **not** enforce a top-level schema type.
    Different callers may expect different shapes:
      - Root song config loader expects a dict (mapping)
      - Export/import helpers may expect dicts with specific keys
      - Future features may use lists for simple collections

    Empty-file handling:
      - If the file is empty or parses to `None`, this function returns `{}`.

    Args:
        path: Filesystem path to the YAML file.

    Returns:
        Any: Parsed YAML object (typically a dict), or `{}` for empty input.

    Raises:
        OSError: If the file cannot be read.
        yaml.YAMLError: If YAML parsing fails.
    """
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
