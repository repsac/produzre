from __future__ import annotations

"""Engine registry construction and dynamic engine-module loading.

This module is responsible for producing a runtime registry of `Engine` objects
from two sources:

1) Package defaults: `produzre/config/engines.yml`
2) Project overrides: the top-level `instruments:` mapping in a song YAML

Each engine entry ultimately resolves to a Python module that provides a
callable `render_into_timeline(...)` function plus optional module constants
used as defaults:

- ENGINE_NAME
- ENGINE_DEFAULT_PRIORITY
- ENGINE_DEFAULT_CHANNEL
- ENGINE_DEFAULT_PROGRAM

The YAML (defaults and/or project overrides) may override priority/channel/program.

Notes:
- Relative engine module paths like `.engine.bass` are resolved against the
  package root (`produzre`), not `produzre.config`.
- All filesystem paths are handled with `pathlib` to remain OS-agnostic.
"""

import importlib
import pathlib
import sys
from typing import Any, Dict

import yaml

from .errors import ConfigError
from .yaml_io import read_yaml_file
from ..model import Engine


def _load_yaml_dict(path: pathlib.Path) -> Dict[str, Any]:
    """Read a YAML file from disk and require a top-level mapping.

    This helper is used for configuration files that must be dictionaries
    (YAML "mapping" / JSON object). It provides consistent error handling
    and clearer user-facing failures.

    Args:
        path: Path to the YAML file.

    Raises:
        ConfigError:
            - If the file does not exist.
            - If the file cannot be read.
            - If YAML parsing fails.
            - If the parsed YAML is not a dict.

    Returns:
        Dict[str, Any]: Parsed YAML mapping.
    """
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        data = read_yaml_file(path)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read YAML file: {path}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("Top-level YAML must be a mapping/object.")
    return data


def load_default_engines_yaml() -> Dict[str, Any]:
    """Load the default engine configuration from `produzre/config/engines.yml`.

    The returned structure is a raw YAML mapping. The keys are instrument names
    (e.g., `drums`, `bass`, `rhythm_gtr`) and the values are per-instrument
    mappings containing at minimum an `engine` module path.

    Example:
        drums:
          engine: ".engine.drums"
          priority: 10
          channel: 9
          program: null

    Returns:
        Dict[str, Any]: Raw YAML mapping (not yet converted to `Engine` objects).

    Raises:
        ConfigError: If the default config file is missing or invalid.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base_dir = pathlib.Path(meipass) / "produzre"
    else:
        base_dir = pathlib.Path(__file__).resolve().parent.parent
    engines_path = base_dir / "resources" / "engines.yml"
    return _load_yaml_dict(engines_path)


def build_engine_registry(raw_root: Dict[str, Any]) -> Dict[str, Engine]:
    """Build the runtime engine registry from defaults + project-level overrides.

    Sources:
      - Defaults are loaded from `produzre/config/engines.yml`.
      - Project overrides are read from the top-level `instruments:` mapping in
        the song YAML (provided here as `raw_root`).

    Merge behavior:
      - For each instrument name in the union of (defaults ∪ project overrides),
        we merge mappings with project values overriding defaults.
      - `engine` is required after merging; if missing, a ConfigError is raised.

    Module loading:
      - Imports the engine module using `importlib.import_module`.
      - Relative module paths (e.g., `.engine.bass`) are resolved against the
        package root (`produzre`).
      - The module must define `render_into_timeline(...)`.

    Default resolution order for Engine attributes:
      1) YAML override values (priority/channel/program)
      2) Module constants (ENGINE_DEFAULT_*)
      3) Hardcoded fallbacks (priority=50, channel=0, program=None)

    Args:
        raw_root: Parsed song YAML root mapping.

    Raises:
        ConfigError:
            - If `instruments` is present but not a mapping.
            - If any default or override entry is not a mapping.
            - If the engine module cannot be imported.
            - If the module does not provide a callable `render_into_timeline`.
            - If required configuration values are missing.

    Returns:
        Dict[str, Engine]: Mapping of instrument name -> Engine instance.
    """
    default_engines = load_default_engines_yaml()

    project_instruments = raw_root.get("instruments") or {}
    if not isinstance(project_instruments, dict):
        raise ConfigError("Top-level 'instruments' must be a mapping if present.")

    instrument_names = set(default_engines.keys()) | set(project_instruments.keys())
    registry: Dict[str, Engine] = {}

    # IMPORTANT: relative engine paths like `.engine.bass` must be resolved
    # against the *package root* (`produzre`), not `produzre.config`.
    package_root = __name__.split(".")[0]  # "produzre"

    for name in sorted(instrument_names):
        default_cfg = default_engines.get(name, {}) or {}
        override_cfg = project_instruments.get(name, {}) or {}

        if not isinstance(default_cfg, dict):
            raise ConfigError(f"Default engine config for '{name}' must be a mapping.")
        if not isinstance(override_cfg, dict):
            raise ConfigError(f"Project instrument config for '{name}' must be a mapping.")

        merged = {**default_cfg, **override_cfg}

        engine_path = merged.get("engine")
        if not engine_path:
            raise ConfigError(f"Engine path is required for instrument '{name}'.")

        # Import engine module (supports relative paths like `.engine.bass`)
        try:
            module = importlib.import_module(str(engine_path), package=package_root)
        except ImportError as e:
            raise ConfigError(f"Failed to import engine module '{engine_path}' for '{name}': {e}") from e

        # Module-level defaults
        mod_name = getattr(module, "ENGINE_NAME", name)
        mod_priority = getattr(module, "ENGINE_DEFAULT_PRIORITY", 50)
        mod_channel = getattr(module, "ENGINE_DEFAULT_CHANNEL", 0)
        mod_program = getattr(module, "ENGINE_DEFAULT_PROGRAM", None)

        # YAML can override module defaults
        priority = int(merged.get("priority", mod_priority))
        channel = int(merged.get("channel", mod_channel))
        program = merged.get("program", mod_program)
        if program is not None:
            program = int(program)

        # Parse orchestration fields (Phase N0)
        enabled = bool(merged.get("enabled", True))
        requires = merged.get("requires", []) or []
        provides = merged.get("provides", []) or []
        roles = merged.get("roles", []) or []

        # Validate orchestration fields
        if not isinstance(requires, list):
            raise ConfigError(f"Engine '{name}': 'requires' must be a list of strings.")
        if not isinstance(provides, list):
            raise ConfigError(f"Engine '{name}': 'provides' must be a list of strings.")
        if not isinstance(roles, list):
            raise ConfigError(f"Engine '{name}': 'roles' must be a list of strings.")

        render = getattr(module, "render_into_timeline", None)
        if not callable(render):
            raise ConfigError(
                f"Engine module '{engine_path}' for instrument '{name}' must "
                f"define a callable 'render_into_timeline(...)'."
            )

        # Phase N4: Detect optional contribute_plan hook
        contribute_plan = getattr(module, "contribute_plan", None)
        if contribute_plan is not None and not callable(contribute_plan):
            raise ConfigError(
                f"Engine module '{engine_path}' for instrument '{name}' has "
                f"'contribute_plan' but it is not callable."
            )

        registry[name] = Engine(
            name=str(mod_name),
            module_path=str(engine_path),
            priority=priority,
            channel=channel,
            program=program,
            render=render,
            contribute_plan=contribute_plan,
            enabled=enabled,
            requires=[str(r) for r in requires],
            provides=[str(p) for p in provides],
            roles=[str(role) for role in roles],
        )

    return registry
