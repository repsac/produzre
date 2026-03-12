from __future__ import annotations

r"""OS-agnostic path utilities for Produzre configuration files.

Produzre maintains per-user state on disk (projects registry, user profile, etc.).
This module centralizes the resolution of those paths so:

- CLI commands, config loading, and orchestration all agree on where state lives.
- The rest of the codebase can remain platform-agnostic.
- Future changes to directory layout are localized to a single place.

Directory conventions:
- macOS: ~/Library/Application Support/produzre
- Windows: %APPDATA%\produzre (fallback to ~/AppData/Roaming/produzre)
- Linux/Unix: $XDG_CONFIG_HOME/produzre (fallback to ~/.config/produzre)

Testing / overrides:
- `PRODUZRE_PLATFORM` may be set to force platform resolution branches
  (e.g., "darwin", "win32") during tests.
"""

import os
import pathlib


def default_produzre_config_dir() -> pathlib.Path:
    r"""Return the per-user configuration directory for Produzre.

    This function chooses a directory appropriate for the current operating
    system and user. It does not create the directory; callers that write files
    should create parent directories as needed.

    Platform resolution:
      - If `PRODUZRE_PLATFORM` is set, its value is used as the platform string.
      - Otherwise uses `os.sys.platform`.

    Resolution rules:
      - macOS (darwin*): ~/Library/Application Support/produzre
      - Windows (win*): %APPDATA%\produzre if APPDATA is set, otherwise
        ~/AppData/Roaming/produzre
      - Linux/Unix: $XDG_CONFIG_HOME/produzre if XDG_CONFIG_HOME is set,
        otherwise ~/.config/produzre

    Returns:
        pathlib.Path: The chosen configuration directory.
    """
    home = pathlib.Path.home()
    plat = (os.environ.get("PRODUZRE_PLATFORM") or os.sys.platform or "").lower()

    # macOS
    if plat.startswith("darwin"):
        return home / "Library" / "Application Support" / "produzre"

    # Windows
    if plat.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return pathlib.Path(appdata) / "produzre"
        # Fallback
        return home / "AppData" / "Roaming" / "produzre"

    # Linux/Unix (XDG)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return pathlib.Path(xdg) / "produzre"
    return home / ".config" / "produzre"


def projects_registry_path() -> pathlib.Path:
    """Return the full path to the per-user projects registry file.

    The projects registry is stored as `projects.yml` inside the directory
    returned by `default_produzre_config_dir()`.

    Returns:
        pathlib.Path: Path to `projects.yml`.
    """
    return default_produzre_config_dir() / "projects.yml"


def user_profile_path() -> pathlib.Path:
    """Return the full path to the per-user user profile file.

    The user profile is stored as `user.yml` in the same directory as the
    projects registry, ensuring all per-user Produzre state is co-located.

    Returns:
        pathlib.Path: Path to `user.yml`.
    """
    return projects_registry_path().parent / "user.yml"
