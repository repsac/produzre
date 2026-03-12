from __future__ import annotations

"""Low-level persistence for the projects registry.

This module owns the on-disk format and I/O for the per-user projects registry
YAML (`projects.yml`). It is intentionally "low-level":

- Reads/writes raw YAML mappings.
- Provides small helpers for ensuring required structure.
- Resolves a project name to a numeric project seed.

Higher-level behaviors (export/import, CLI formatting, selective field hiding,
etc.) live in `projects_api.py` and CLI command handlers.

The registry format (current schema=1) looks like:

    schema: 1
    default_project: default
    projects:
      default:
        seed: 123
        created_at: "...Z"
        owner: "..."
        notes: ""
        collaborators: []
        custom: {}

All filesystem paths are resolved via `config.paths` for OS portability.
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import yaml

from .errors import ConfigError
from .paths import projects_registry_path
from .user_profile import effective_user_name


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a trailing 'Z'.

    Produzre stores timestamps in a human-readable, timezone-unambiguous form.
    Microseconds are stripped for stable diffs and cleaner exports.

    Returns:
        str: Timestamp like "2025-12-24T21:05:00Z".
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_projects_registry() -> Dict[str, Any]:
    """Load the per-user projects registry YAML from disk.

    Behavior:
      - If the registry file does not exist, returns an empty dict.
      - Parses YAML with `yaml.safe_load`.
      - Requires a top-level mapping; otherwise raises ConfigError.

    Returns:
        Dict[str, Any]: Raw registry mapping (may be empty).

    Raises:
        ConfigError: If YAML parsing fails or the document is not a mapping.
    """
    path = projects_registry_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse projects registry YAML: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError("Projects registry YAML must be a mapping/object.")
    return data


def save_projects_registry(data: Dict[str, Any]) -> None:
    """Write the per-user projects registry YAML to disk.

    The registry path is resolved using `projects_registry_path()`. Parent
    directories are created if missing.

    Serialization:
      - Uses `yaml.safe_dump(..., sort_keys=False)` to preserve key order.

    Args:
        data: Registry mapping to write.

    Raises:
        ConfigError: If the file cannot be written.
    """
    path = projects_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)
    except OSError as e:
        raise ConfigError(f"Failed to write projects registry: {path}: {e}") from e


def ensure_default_project(reg: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the registry has required top-level structure and a default project.

    This function normalizes the registry mapping in-place:
      - Ensures `schema` is set (defaults to 1).
      - Ensures `projects` exists and is a dict.
      - Ensures `default_project` exists (defaults to "default").

    If the default project entry does not exist, it is created with a randomly
    generated per-user seed and basic metadata.

    Seed generation:
      - Uses `secrets.randbelow(2**31 - 1) + 1` to create a positive int seed.

    Args:
        reg: Raw registry mapping.

    Returns:
        Dict[str, Any]: The same mapping instance, normalized.
    """
    schema = reg.get("schema")
    if schema is None:
        reg["schema"] = 1

    if "projects" not in reg or not isinstance(reg.get("projects"), dict):
        reg["projects"] = {}

    if "default_project" not in reg:
        reg["default_project"] = "default"

    default_name = str(reg.get("default_project") or "default")
    projects = reg["projects"]

    if default_name not in projects:
        # Per-user seed, created once.
        seed = secrets.randbelow(2**31 - 1) + 1
        projects[default_name] = {
            "seed": int(seed),
            "created_at": utc_now_iso(),
            "owner": effective_user_name(),
            "notes": "",
            "collaborators": [],
            "custom": {},
        }

    return reg


def resolve_project_seed(reg: Dict[str, Any], requested: Optional[str]) -> Tuple[str, int]:
    """Resolve a project name to a numeric seed.

    Rules:
      - If `requested` is None or empty/whitespace, uses the registry's
        `default_project`.
      - If `requested` is provided but not present in the registry, raises a
        ConfigError with actionable remediation steps.

    This function always calls `ensure_default_project()` first to guarantee the
    registry has the expected shape.

    Args:
        reg: Raw registry mapping.
        requested: Optional project name requested by the song YAML.

    Returns:
        Tuple[str, int]: (resolved_project_name, project_seed)

    Raises:
        ConfigError: If a non-empty project name is requested but not present.
    """
    reg = ensure_default_project(reg)
    projects = reg["projects"]

    if requested is None or str(requested).strip() == "":
        pname = str(reg.get("default_project") or "default")
        seed = int(projects[pname]["seed"])
        return pname, seed

    pname = str(requested)
    if pname not in projects:
        raise ConfigError(
            f"Unknown project '{pname}'.\n"
            f"- Check the project name in song.project\n"
            f"- Import the project registry entry\n"
            f"- Or create it as a new project"
        )

    seed = int(projects[pname]["seed"])
    return pname, seed
