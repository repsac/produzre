from __future__ import annotations

"""Export path and naming helpers.

This module centralizes all logic for:

- Converting a user-provided song title into a filesystem-safe prefix.
- Resolving the exports root directory in an OS-agnostic way.
- Creating a unique per-run export folder (with collision avoidance).

Keeping this logic in one place ensures naming conventions remain consistent
across full-song exports, stems, sections, and patterns.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_song_name(name: str, *, fallback: str = "produzre") -> str:
    """Convert a user-provided song title into a filesystem-safe name.

    The returned value is intended to be used as the prefix for export folders
    and top-level exported files.

    Normalization rules:
      - Strips leading/trailing whitespace.
      - Replaces unsafe characters with underscores.
      - Collapses repeated underscores.
      - Strips leading/trailing punctuation commonly produced by replacement.
      - Ensures a non-empty result by returning `fallback`.

    Args:
        name: Raw song title from YAML/CLI.
        fallback: Value to use if `name` is empty or normalizes to empty.

    Returns:
        str: Sanitized, filesystem-safe song name.
    """
    s = (name or "").strip()
    if not s:
        return fallback

    s = _SAFE_CHARS_RE.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("._-_")
    return s or fallback


def resolve_exports_root(exports_root: str | Path) -> Path:
    """Resolve an exports root path from a string or `Path`.

    This function performs user-friendly expansion:
      - Expands `~` to the user's home directory.
      - Expands environment variables (e.g., `$HOME`, `%USERPROFILE%`).

    It intentionally does not create directories; creation is handled by the
    run-directory builder.

    Args:
        exports_root: Root export directory as a string or `Path`.

    Returns:
        Path: Resolved `Path` instance.
    """
    if isinstance(exports_root, Path):
        p = exports_root
    else:
        p = Path(os.path.expandvars(os.path.expanduser(str(exports_root))))
    return p


@dataclass(frozen=True)
class ExportPaths:
    """Paths produced by `create_run_export_dir()` for a single build.

    Attributes:
        root: The unique per-run export directory.
        instruments_dir: The `instruments/` directory under `root`.
    """

    root: Path
    instruments_dir: Path


def create_run_export_dir(
    *,
    exports_root: str | Path,
    song_name: str,
    logger,
    run_id: Optional[str] = None,
) -> ExportPaths:
    """Create a unique export directory for this run and return key subpaths.

    Directory layout:
      <exports_root>/<song_name>_<run_id>/
        instruments/

    Uniqueness:
      - `run_id` defaults to a UTC timestamp (YYYYmmdd_HHMMSS).
      - If a directory with the same name already exists (multiple runs within
        the same second), a numeric suffix is appended: `_1`, `_2`, ...

    Side effects:
      - Ensures `exports_root` exists.
      - Creates the per-run export directory.
      - Creates the `instruments/` subdirectory.
      - Logs the resolved export root when a logger is provided.

    Args:
        exports_root: Base export directory.
        song_name: Raw song title used to create a prefix (sanitized).
        logger: Optional logger for status messages.
        run_id: Optional explicit run identifier; if omitted a UTC timestamp is used.

    Returns:
        ExportPaths: Dataclass containing the run export root and `instruments/`.
    """
    root_base = resolve_exports_root(exports_root)
    safe_song = sanitize_song_name(song_name)
    rid = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    root_base.mkdir(parents=True, exist_ok=True)

    # Avoid collisions if multiple runs happen within the same second.
    export_root = root_base / f"{safe_song}_{rid}"
    if export_root.exists():
        suffix = 1
        while (root_base / f"{safe_song}_{rid}_{suffix}").exists():
            suffix += 1
        export_root = root_base / f"{safe_song}_{rid}_{suffix}"

    export_root.mkdir(parents=True, exist_ok=False)

    instruments_dir = export_root / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)

    if logger is not None:
        try:
            logger.info("Export root: %s", export_root)
        except Exception:
            pass

    return ExportPaths(root=export_root, instruments_dir=instruments_dir)
