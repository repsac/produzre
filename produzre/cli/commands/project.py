from __future__ import annotations

"""CLI command handlers for managing Produzre projects.

Projects provide a named, shareable seed namespace plus metadata used for
collaboration and reproducible MIDI generation.

This module implements the `produzre project ...` command family by delegating
high-level operations to `produzre.config` while keeping CLI-friendly output and
error messages close to the command handlers.
"""

from typing import Optional
import yaml

from ...config import (
    ConfigError,
    list_projects,
    create_project,
    get_project,
    get_projects_registry_path,
    export_project,
    import_project,
)
from ...logging_setup import configure_logging


def _load_projects_registry_yaml() -> dict:
    """Load and normalize the local projects registry YAML (`projects.yml`).

    This command module historically contained its own registry I/O helpers.
    Even though higher-level APIs exist in `produzre.config`, these helpers are
    still used by a few CLI commands that perform targeted edits (e.g., setting
    custom keys and owner).

    Expected YAML structure:

        schema: 1
        projects:
          <project_name>:
            seed: 123
            owner: "..."
            created_at: "..."
            notes: "..."
            custom: {}

    Behavior:
      - If the file does not exist, returns a minimal default structure.
      - If YAML parses to a non-dict, returns the minimal default structure.
      - Ensures top-level `schema` exists (defaults to 1).
      - Ensures `projects` exists and is a dict.

    Returns:
        dict: Normalized registry document.
    """
    import pathlib

    path = pathlib.Path(get_projects_registry_path())
    if not path.exists():
        return {"schema": 1, "projects": {}}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return {"schema": 1, "projects": {}}

    if "schema" not in data:
        data["schema"] = 1
    if "projects" not in data or not isinstance(data.get("projects"), dict):
        data["projects"] = {}

    return data


def _save_projects_registry_yaml(data: dict) -> None:
    """Persist the provided projects registry document to `projects.yml`.

    The target path is determined by `get_projects_registry_path()`.

    Serialization:
      - Uses `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)` to preserve
        a human-friendly ordering and support non-ASCII values.

    Args:
        data: Full registry document to write (typically produced by
            `_load_projects_registry_yaml()` and then modified).

    Returns:
        None
    """
    import pathlib

    path = pathlib.Path(get_projects_registry_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def cmd_project_list(verbose: bool) -> int:
    """CLI handler: list known projects in the local registry.

    Output:
      - Prints a one-line summary per project (name, owner, created_at, notes).
      - In verbose mode also prints the project seed.

    Logging:
      - Initializes console logging.
      - Logs the registry path for traceability.

    Args:
        verbose: If True, include seed and print more detail.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    projects = list_projects()
    names = sorted(projects.keys())

    print(f"Projects ({len(names)}):")
    for name in names:
        p = projects.get(name) or {}
        created_at = p.get("created_at", "")
        owner = p.get("owner", "")
        notes = p.get("notes", "")
        if verbose:
            seed = p.get("seed", None)
            print(f"- {name}  seed={seed}  owner={owner}  created_at={created_at}  notes={notes}")
        else:
            print(f"- {name}  owner={owner}  created_at={created_at}  notes={notes}")

    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_path() -> int:
    """CLI handler: print the resolved path to the projects registry (`projects.yml`).

    This is primarily for debugging and for shell scripts that need to locate the
    registry file on disk.

    Side effects:
      - Prints the registry path to stdout.

    Returns:
        int: Process-style exit code (0 for success).
    """
    print(get_projects_registry_path())
    return 0


def cmd_project_create(name: str, seed: Optional[int], notes: str, verbose: bool) -> int:
    """CLI handler: create a new project in the local projects registry.

    Projects provide a stable, shareable seed namespace. A project's seed is
    combined with song-level seeding to ensure collaborators can reproduce the
    same MIDI output when using the same project and song YAML.

    Behavior:
      - Delegates to `create_project(...)` for registry updates and defaults.
      - Prints a brief confirmation in non-verbose mode.
      - In verbose mode, prints the created project entry as YAML.

    Args:
        name: Project name (unique key in registry).
        seed: Optional explicit seed. If omitted, the registry layer chooses a
            seed (or derives one).
        notes: Optional free-form notes stored with the project.
        verbose: If True, enable debug logging and print full project YAML.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    proj = create_project(name=name, seed=seed, notes=notes)
    logger.info("Created project '%s'.", name)

    if verbose:
        print(yaml.safe_dump({"project": {name: proj}}, sort_keys=False, allow_unicode=True))
    else:
        print(f"Created project: {name}")

    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_show(name: str, verbose: bool) -> int:
    """CLI handler: show a single project's metadata as YAML.

    Behavior:
      - Loads the project via `get_project(name)`.
      - By default, hides the project seed (prints `seed: null`) to avoid
        accidentally leaking it in screenshots/logs.
      - In verbose mode, prints the actual seed.

    Args:
        name: Project name.
        verbose: If True, include the real seed.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    proj = dict(get_project(name))

    if not verbose and "seed" in proj:
        # Hide seed unless verbose
        proj["seed"] = None

    print(yaml.safe_dump({"project": {name: proj}}, sort_keys=False, allow_unicode=True))
    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_export(
    name: str,
    out_path: str,
    include: Optional[str],
    include_all_custom: bool,
    no_seed: bool,
    verbose: bool,
) -> int:
    """CLI handler: export a project to a portable YAML file for collaboration.

    Exported files intentionally contain *metadata* needed to recreate a project
    on another machine. Depending on flags, this may include the project seed.

    Behavior:
      - Optional inclusion of specific custom keys, or all custom keys.
      - Optional exclusion of the seed (for sharing without reproducibility).
      - In non-verbose mode, prints the output path.

    Args:
        name: Project name to export.
        out_path: Destination path for the exported YAML.
        include: Optional comma-separated list of custom keys to include.
        include_all_custom: If True, include all custom keys.
        no_seed: If True, omit the seed from export.
        verbose: If True, log export details.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=verbose, log_file=None)

    include_keys = None
    if include:
        include_keys = [k.strip() for k in include.split(",") if k.strip()]

    p = export_project(
        name=name,
        out_path=out_path,
        include_custom_keys=include_keys,
        include_all_custom=include_all_custom,
        include_seed=not no_seed,
    )

    if verbose:
        logger.info("Exported project '%s' -> %s", name, p)
    else:
        print(str(p))

    return 0


def cmd_project_import(path: str, overwrite: bool, verbose: bool) -> int:
    """CLI handler: import a project export YAML into the local registry.

    This command registers the project locally, updating collaborator metadata
    (handled by the config layer) and optionally overwriting an existing project.

    Args:
        path: Path to a project export YAML.
        overwrite: If True, allow overwriting an existing project with the same name.
        verbose: If True, log details of the import operation.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    name = import_project(path, allow_overwrite=overwrite)

    if verbose:
        logger.info("Imported project '%s' from %s", name, path)
    else:
        print(name)

    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_set_custom(name: str, key: str, value: str, verbose: bool) -> int:
    """CLI handler: set a custom key/value on a project in the registry.

    Custom keys live under `projects.<name>.custom` and are intended for
    user-defined metadata (band name, URLs, tags, etc.) without colliding with
    reserved keys like `seed` or `created_at`.

    Behavior:
      - Loads the registry YAML.
      - Hard-errors with a helpful message if the project does not exist.
      - Ensures `custom` is a dict before writing.
      - Saves the registry back to disk.

    Args:
        name: Project name.
        key: Custom metadata key.
        value: Custom metadata value.
        verbose: If True, print the updated project YAML.

    Returns:
        int: Process-style exit code (0 for success).

    Raises:
        ConfigError: If the project does not exist in the registry.
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    reg = _load_projects_registry_yaml()
    projects = reg.get("projects")
    if not isinstance(projects, dict) or name not in projects or not isinstance(projects.get(name), dict):
        raise ConfigError(
            f"Unknown project '{name}'.\n"
            f"- List projects: produzre project list\n"
            f"- Or create it: produzre project create {name}"
        )

    proj = projects[name]
    if "custom" not in proj or not isinstance(proj.get("custom"), dict):
        proj["custom"] = {}

    proj["custom"][str(key)] = value
    _save_projects_registry_yaml(reg)

    logger.info("Set project.%s.custom.%s", name, key)
    if verbose:
        print(yaml.safe_dump({"project": {name: proj}}, sort_keys=False, allow_unicode=True))
    else:
        print("OK")

    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_unset_custom(name: str, key: str, verbose: bool) -> int:
    """CLI handler: remove a custom key from a project in the registry.

    If the key is not present, the operation is a no-op.

    Args:
        name: Project name.
        key: Custom metadata key to remove.
        verbose: If True, print the updated project YAML.

    Returns:
        int: Process-style exit code (0 for success).

    Raises:
        ConfigError: If the project does not exist in the registry.
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    reg = _load_projects_registry_yaml()
    projects = reg.get("projects")
    if not isinstance(projects, dict) or name not in projects or not isinstance(projects.get(name), dict):
        raise ConfigError(
            f"Unknown project '{name}'.\n"
            f"- List projects: produzre project list\n"
            f"- Or create it: produzre project create {name}"
        )

    proj = projects[name]
    if "custom" in proj and isinstance(proj.get("custom"), dict):
        proj["custom"].pop(str(key), None)

    _save_projects_registry_yaml(reg)

    logger.info("Removed project.%s.custom.%s", name, key)
    if verbose:
        print(yaml.safe_dump({"project": {name: proj}}, sort_keys=False, allow_unicode=True))
    else:
        print("OK")

    logger.info("Registry: %s", get_projects_registry_path())
    return 0


def cmd_project_set_owner(name: str, owner: str, verbose: bool) -> int:
    """CLI handler: set the `owner` field for a project.

    This is useful when projects are shared across machines and the OS username
    is not the preferred artist/producer name.

    Behavior:
      - Loads the registry YAML.
      - Hard-errors with a helpful message if the project does not exist.
      - Updates `projects.<name>.owner`.
      - Saves the registry back to disk.

    Args:
        name: Project name.
        owner: New owner display name.
        verbose: If True, print the updated project YAML.

    Returns:
        int: Process-style exit code (0 for success).

    Raises:
        ConfigError: If the project does not exist in the registry.
    """
    logger = configure_logging(verbose=verbose, log_file=None)
    reg = _load_projects_registry_yaml()
    projects = reg.get("projects")
    if not isinstance(projects, dict) or name not in projects or not isinstance(projects.get(name), dict):
        raise ConfigError(
            f"Unknown project '{name}'.\n"
            f"- List projects: produzre project list\n"
            f"- Or create it: produzre project create {name}"
        )

    proj = projects[name]
    proj["owner"] = str(owner)
    _save_projects_registry_yaml(reg)

    logger.info("Set project.%s.owner", name)
    if verbose:
        print(yaml.safe_dump({"project": {name: proj}}, sort_keys=False, allow_unicode=True))
    else:
        print("OK")

    logger.info("Registry: %s", get_projects_registry_path())
    return 0
