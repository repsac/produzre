from __future__ import annotations

"""Per-user profile storage and lookup.

Produzre maintains a small per-user profile file (`user.yml`) alongside the
projects registry in the OS-appropriate configuration directory.

The profile serves two related purposes:

1) Friendly identity metadata
   - A stable, human-friendly display name for logs, exports, and collaboration
     metadata (e.g., project exports/imports).

2) User-defined arbitrary metadata
   - An open-ended `profile.custom` mapping for any extra information users want
     to associate with themselves (band name, URL, email, etc.).

The file is intentionally lightweight and best-effort:
- If it is missing or malformed, Produzre falls back to OS-derived usernames.
- Errors here should never prevent core MIDI generation.

Schema (v1) minimal structure:

    schema: 1
    profile:
      name: "Optional Friendly Name"
      custom: {}
"""

from typing import Any, Dict

import pathlib
import os

import yaml

from .paths import user_profile_path


def os_username() -> str:
    """Return a best-effort OS username for metadata (cross-platform).

    This is used as a fallback identity when the user profile does not define
    a preferred display name.

    Resolution order:
      1) Environment variables: USER, LOGNAME, USERNAME
      2) Home directory name (Path.home().name)
      3) Fallback literal "unknown"

    Returns:
        str: Best-effort username string.
    """
    for key in ("USER", "LOGNAME", "USERNAME"):
        v = os.environ.get(key)
        if v:
            return str(v)
    try:
        return pathlib.Path.home().name
    except Exception:
        return "unknown"


def load_user_profile() -> Dict[str, Any]:
    """Load `user.yml` as a dict and normalize to a minimal structure.

    Behavior:
      - If the file does not exist, returns the minimal default structure.
      - If YAML parses to a non-dict value, returns the minimal default.
      - Ensures top-level `schema` exists (defaults to 1).
      - Ensures `profile` exists and is a dict.
      - Ensures `profile.custom` exists and is a dict.

    The normalization guarantees callers can safely assume the presence of
    `profile.custom` when mutating or reading user-defined metadata.

    Returns:
        Dict[str, Any]: Normalized user profile document.
    """
    path = user_profile_path()
    if not path.exists():
        return {"schema": 1, "profile": {"custom": {}}}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return {"schema": 1, "profile": {"custom": {}}}

    if "schema" not in data:
        data["schema"] = 1

    prof = data.get("profile")
    if not isinstance(prof, dict):
        prof = {}
        data["profile"] = prof

    if "custom" not in prof or not isinstance(prof.get("custom"), dict):
        prof["custom"] = {}

    return data


def effective_user_name() -> str:
    """Return the effective display name for the current user.

    Preference order:
      1) `user.yml` -> `profile.name` (trimmed non-empty string)
      2) `user.yml` -> `profile.custom.name` (power-user fallback)
      3) OS-derived username from `os_username()`

    This function is intentionally best-effort and must not raise.

    Returns:
        str: A friendly display name.
    """
    try:
        data = load_user_profile()
        prof = data.get("profile") if isinstance(data, dict) else None
        if isinstance(prof, dict):
            name = prof.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

            # Allow power-users to store a display name under profile.custom.name as well.
            custom = prof.get("custom")
            if isinstance(custom, dict):
                cname = custom.get("name")
                if isinstance(cname, str) and cname.strip():
                    return cname.strip()
    except Exception:
        # Best-effort; never block core functionality.
        pass

    return os_username()
