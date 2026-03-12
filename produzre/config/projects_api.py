from __future__ import annotations

"""Public project-registry API used by the CLI.

This module provides a user-facing (but still internal) API for managing the
local projects registry (`projects.yml`) and for exporting/importing projects
for collaboration.

Key concepts:
- A *project* is a named container for a stable integer seed plus metadata.
- The project seed is combined with a song's seed to produce an effective
  generation seed. Sharing the same project (including its seed) enables
  deterministic reproduction across machines.

Storage:
- The registry is stored in an OS-appropriate per-user config directory
  (see `produzre.config.paths`).

Collaboration:
- `export_project()` writes a portable YAML containing project metadata and,
  optionally, the seed.
- `import_project()` registers the project locally and appends the importing
  user to the collaborators list.

This file intentionally keeps I/O and validation close to the CLI-facing
commands so that error messages remain actionable.
"""

import pathlib
import secrets
from typing import Any, Dict, Optional

import yaml

from .errors import ConfigError
from .paths import projects_registry_path
from .registry import (
    utc_now_iso,
    load_projects_registry as _load_projects_registry,
    save_projects_registry as _save_projects_registry,
    ensure_default_project as _ensure_default_project,
)
from .user_profile import effective_user_name


def get_projects_registry_path() -> str:
    """Return the absolute path to the local projects registry YAML.

    This is a convenience wrapper around `projects_registry_path()` that returns
    a string (useful for CLI printing).

    Returns:
        str: Filesystem path to `projects.yml`.
    """
    return str(projects_registry_path())


def load_projects_registry() -> Dict[str, Any]:
    """Load the projects registry and ensure a default project exists.

    Behavior:
      - Loads the registry via the lower-level `registry.load_projects_registry()`.
      - Ensures the default project is present (creating it if missing).
      - Persists the registry back to disk if the default project was created.

    Returns:
        Dict[str, Any]: Normalized registry document containing at least:
            - schema: int
            - projects: dict

    Raises:
        ConfigError: If the registry cannot be loaded or is invalid.
    """
    reg = _load_projects_registry()
    reg2 = _ensure_default_project(reg)
    _save_projects_registry(reg2)  # persist in case default was created
    return reg2


def list_projects() -> Dict[str, Any]:
    """Return the registry's `projects` mapping.

    This helper ensures the registry is loaded and the default project exists,
    then returns the `projects` mapping.

    Returns:
        Dict[str, Any]: Mapping of project name -> project metadata dict.

    Raises:
        ConfigError: If the registry is missing a valid `projects` mapping.
    """
    reg = load_projects_registry()
    projects = reg.get("projects")
    if not isinstance(projects, dict):
        raise ConfigError("Projects registry is missing a 'projects' mapping.")
    return projects


def get_project(name: str) -> Dict[str, Any]:
    """Return a single project's metadata dict by name.

    If the project does not exist, raises a ConfigError with actionable
    next steps (list, import, or create).

    Args:
        name: Project name key in the registry.

    Returns:
        Dict[str, Any]: Project metadata mapping.

    Raises:
        ConfigError: If the project does not exist or its entry is not a mapping.
    """
    projects = list_projects()
    if name not in projects:
        raise ConfigError(
            f"Unknown project '{name}'.\n"
            f"- List projects: produzre project list\n"
            f"- Import a shared project: produzre project import <file>\n"
            f"- Or create it: produzre project create {name}"
        )
    proj = projects[name]
    if not isinstance(proj, dict):
        raise ConfigError(f"Project '{name}' entry must be a mapping.")
    return proj


def create_project(name: str, seed: Optional[int] = None, notes: str = "") -> Dict[str, Any]:
    """Create a new project entry in the local registry.

    Projects provide a stable seed namespace for deterministic generation.

    Seed rules:
      - If `seed` is provided, it is coerced to int.
      - If `seed` is None, a random positive int seed is generated.

    Metadata:
      - `created_at` is set to UTC now (ISO string).
      - `owner` is set from `effective_user_name()`.
      - `notes` is stored as a string.
      - `collaborators` starts empty.
      - `custom` starts as an empty dict.

    Args:
        name: New project name (must not already exist).
        seed: Optional explicit integer seed.
        notes: Optional notes stored with the project.

    Returns:
        Dict[str, Any]: The created project entry.

    Raises:
        ConfigError: If the registry is invalid or if the project already exists.
    """
    reg = load_projects_registry()
    projects = reg.get("projects")
    if not isinstance(projects, dict):
        raise ConfigError("Projects registry is missing a 'projects' mapping.")

    if name in projects:
        raise ConfigError(f"Project '{name}' already exists.")

    seed_val = int(seed) if seed is not None else (secrets.randbelow(2**31 - 1) + 1)

    projects[name] = {
        "seed": int(seed_val),
        "created_at": utc_now_iso(),
        "owner": effective_user_name(),
        "notes": str(notes or ""),
        "collaborators": [],
        "custom": {},
    }

    _save_projects_registry(reg)
    return projects[name]


# ----------------------------
# Project export/import (Phase 2)
# ----------------------------

def _ensure_list(value: Any) -> list:
    """Normalize a value to a list.

    Used primarily for collaborator fields which may be absent, already a list,
    or a scalar in older/hand-written YAML.

    Args:
        value: Any input.

    Returns:
        list: Normalized list value.
            - None -> []
            - list -> unchanged
            - scalar -> [scalar]
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def export_project(
    name: str,
    out_path: str,
    include_custom_keys: Optional[list[str]] = None,
    include_all_custom: bool = False,
    include_seed: bool = True,
) -> pathlib.Path:
    """Export a project to a shareable YAML file.

    The export payload is designed for collaboration and reproducibility.

    Output format:
        schema: 1
        project:
          <name>:
            created_at: ...
            owner: ...
            notes: ...
            collaborators: [...]
            custom: {...}
            seed: <int>   # only if include_seed=True
            exported_at: ...
            exported_by: ...

    Custom key selection:
      - If `include_all_custom` is True, all custom keys are exported.
      - Else if `include_custom_keys` is provided, only those keys (if present)
        are exported.
      - Otherwise, an empty custom mapping is exported.

    Args:
        name: Project name to export.
        out_path: Destination file path for the exported YAML.
        include_custom_keys: Optional list of custom keys to include.
        include_all_custom: If True, include all custom keys.
        include_seed: If True, include the project seed (required for
            deterministic reproduction by collaborators).

    Returns:
        pathlib.Path: Path to the written export file.

    Raises:
        ConfigError: If the project cannot be loaded or the file cannot be written.
    """
    proj = dict(get_project(name))

    exported_at = utc_now_iso()
    exported_by = effective_user_name()

    out: Dict[str, Any] = {}
    out["created_at"] = proj.get("created_at")
    out["owner"] = proj.get("owner")
    out["notes"] = proj.get("notes", "")
    out["collaborators"] = _ensure_list(proj.get("collaborators"))

    custom = proj.get("custom") if isinstance(proj.get("custom"), dict) else {}
    if include_all_custom:
        out["custom"] = dict(custom)
    elif include_custom_keys:
        keys = [str(k) for k in include_custom_keys]
        out["custom"] = {k: custom.get(k) for k in keys if k in custom}
    else:
        out["custom"] = {}

    if include_seed:
        out["seed"] = int(proj.get("seed")) if proj.get("seed") is not None else None

    out["exported_at"] = exported_at
    out["exported_by"] = exported_by

    payload = {
        "schema": 1,
        "project": {str(name): out},
    }

    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
    except OSError as e:
        raise ConfigError(f"Failed to write project export: {p}: {e}") from e

    return p


def import_project(
    in_path: str,
    *,
    allow_overwrite: bool = False,
) -> str:
    """Import a project YAML export into the local registry.

    Behavior:
      - Validates the import file exists and parses as a YAML mapping.
      - Requires the `project` mapping to contain exactly one project.
      - Requires `seed` to be present and coercible to int.
      - Appends the importing user (via `effective_user_name()`) to the
        collaborators list if not already present.
      - Adds `imported_at` timestamp and preserves optional `exported_at` and
        `exported_by` fields.
      - Writes the project into the local registry.

    Args:
        in_path: Path to a project export YAML.
        allow_overwrite: If True, overwrite an existing local project with the
            same name.

    Returns:
        str: Imported project name.

    Raises:
        ConfigError: If the file is missing/invalid, required fields are missing,
        or an existing project would be overwritten without permission.
    """
    p = pathlib.Path(in_path)
    if not p.exists():
        raise ConfigError(f"Project import file not found: {p}")

    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse project import YAML: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("Project import YAML must be a mapping/object.")

    proj_block = data.get("project")
    if not isinstance(proj_block, dict) or not proj_block:
        raise ConfigError("Project import YAML must contain a non-empty 'project' mapping.")
    if len(proj_block) != 1:
        raise ConfigError("Project import YAML 'project' mapping must contain exactly one project.")

    name = next(iter(proj_block.keys()))
    proj = proj_block.get(name)
    if not isinstance(proj, dict):
        raise ConfigError(f"Project '{name}' entry must be a mapping.")

    seed = proj.get("seed")
    if seed is None:
        raise ConfigError(
            f"Imported project '{name}' is missing required 'seed'. "
            f"(Export should include it for reproducibility.)"
        )
    try:
        seed_int = int(seed)
    except Exception as e:
        raise ConfigError(f"Imported project '{name}' seed must be an integer.") from e

    created_at = proj.get("created_at")
    owner = proj.get("owner")
    notes = proj.get("notes", "")

    collaborators = _ensure_list(proj.get("collaborators"))
    importer = effective_user_name()
    if importer not in collaborators:
        collaborators.append(importer)

    custom = proj.get("custom") or {}
    if not isinstance(custom, dict):
        raise ConfigError(f"Imported project '{name}' custom must be a mapping.")

    imported_at = utc_now_iso()
    exported_at = proj.get("exported_at")
    exported_by = proj.get("exported_by")

    new_entry: Dict[str, Any] = {
        "seed": int(seed_int),
        "created_at": created_at if created_at is not None else utc_now_iso(),
        "owner": owner if owner is not None else importer,
        "notes": str(notes or ""),
        "collaborators": collaborators,
        "custom": dict(custom),
        "imported_at": imported_at,
    }
    if exported_at is not None:
        new_entry["exported_at"] = exported_at
    if exported_by is not None:
        new_entry["exported_by"] = exported_by

    reg = load_projects_registry()
    projects = reg.get("projects")
    if not isinstance(projects, dict):
        raise ConfigError("Projects registry is missing a 'projects' mapping.")

    if name in projects and not allow_overwrite:
        raise ConfigError(f"Project '{name}' already exists locally. Use --overwrite to overwrite.")

    projects[name] = new_entry
    _save_projects_registry(reg)

    return str(name)
