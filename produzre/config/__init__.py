"""Config subsystem public API.

This module loads and validates Produzre song configuration from YAML files.

Implementation modules:
- config.load: Main config loading and validation
- config.engines: Engine registry and defaults
- config.projects_api: Project management (registry, import/export)
"""

from .errors import ConfigError
from .load import load_root_config
from .projects_api import (
    get_projects_registry_path,
    load_projects_registry,
    list_projects,
    get_project,
    create_project,
    export_project,
    import_project,
)

__all__ = [
    "ConfigError",
    "load_root_config",
    "get_projects_registry_path",
    "load_projects_registry",
    "list_projects",
    "get_project",
    "create_project",
    "export_project",
    "import_project",
]
