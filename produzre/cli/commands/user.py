
from __future__ import annotations

"""CLI command handlers for user-level configuration.

This module implements the `produzre user ...` command family and manages the
per-user profile file (`user.yml`). The profile stores a preferred display name
and an open-ended `profile.custom` mapping for arbitrary user metadata.

The file is intentionally lightweight and best-effort: commands will create the
file on demand and normalize its structure so future edits are safe.
"""

import pathlib
import yaml

from ...config import get_projects_registry_path
from ...logging_setup import configure_logging


def _user_profile_path() -> str:
    """Return the filesystem path to the Produzre user profile YAML.

    This CLI module stores user-specific metadata (e.g., preferred display name and
    arbitrary custom key/value pairs) in a YAML file named `user.yml` that lives
    alongside the projects registry file.

    Path resolution:
      - Uses `get_projects_registry_path()` to locate the registry.
      - Returns `<registry_dir>/user.yml`.
      - If anything goes wrong while resolving the directory (unexpected types,
        path errors), falls back to the relative path `user.yml`.

    Returns:
        str: Absolute (or best-effort) path to `user.yml`.
    """
    reg_path = get_projects_registry_path()
    try:
        p = pathlib.Path(reg_path).parent / "user.yml"
        return str(p)
    except Exception:
        return "user.yml"


def _load_user_profile() -> dict:
    """Load and normalize the user profile file (`user.yml`).

    The file is expected to be a YAML mapping with this minimal structure:

        schema: 1
        profile:
          custom: {}

    Behavior:
      - If `user.yml` does not exist, returns the minimal default structure.
      - If the YAML parses to a non-dict value, returns the minimal default.
      - Ensures the top-level keys `schema` and `profile` exist.
      - Ensures `profile.custom` exists and is a dict.

    This normalization allows future CLI commands to safely set fields without
    defensive checks scattered across call sites.

    Returns:
        dict: A normalized profile document ready for read/modify/write.
    """
    path = pathlib.Path(_user_profile_path())
    if not path.exists():
        return {"schema": 1, "profile": {"custom": {}}}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return {"schema": 1, "profile": {"custom": {}}}

    if "schema" not in data:
        data["schema"] = 1
    if "profile" not in data or not isinstance(data.get("profile"), dict):
        data["profile"] = {"custom": {}}

    prof = data["profile"]
    if "custom" not in prof or not isinstance(prof.get("custom"), dict):
        prof["custom"] = {}

    return data


def _save_user_profile(data: dict) -> None:
    """Persist the provided user profile document to `user.yml`.

    The target path is determined by `_user_profile_path()`. Parent directories are
    created if missing.

    Serialization:
      - Uses `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)` to preserve
        human-friendly ordering and allow non-ASCII values.

    Args:
        data (dict): The full user profile document to write (already normalized
            by `_load_user_profile()` or constructed by the caller).

    Returns:
        None
    """
    path = pathlib.Path(_user_profile_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def cmd_user_path() -> int:
    """CLI handler: print the resolved path to `user.yml`.

    This command is useful for debugging and for scripts that want to locate the
    user profile file on disk.

    Side effects:
      - Prints the path to stdout.

    Returns:
        int: Process-style exit code (0 for success).
    """
    print(_user_profile_path())
    return 0


def cmd_user_show() -> int:
    """CLI handler: display the current user profile YAML.

    Loads `user.yml` (creating an in-memory default profile if missing) and prints
    the full YAML to stdout.

    Logging:
      - Configures verbose console logging for this command.
      - Logs the location of the user profile file.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=True, log_file=None)
    data = _load_user_profile()
    print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    logger.info("User profile: %s", _user_profile_path())
    return 0


def cmd_user_set(field: str, value: str) -> int:
    """CLI handler: set a top-level field under `profile` in `user.yml`.

    Example:
        produzre user set owner "Some Name"

    This writes:
        profile:
          owner: "Some Name"

    Notes:
      - `profile.custom` is always preserved as a dict.
      - This command intentionally does not validate field names; callers may set
        any key under `profile`.

    Args:
        field (str): The key name to set under `profile`.
        value (str): The value to store (string).

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=True, log_file=None)
    data = _load_user_profile()
    data.setdefault("profile", {})
    data["profile"][field] = value
    data["profile"].setdefault("custom", {})
    _save_user_profile(data)
    logger.info("Set profile.%s", field)
    logger.info("User profile: %s", _user_profile_path())
    return 0


def cmd_user_set_custom(key: str, value: str) -> int:
    """CLI handler: set a key/value under `profile.custom` in `user.yml`.

    This is the preferred way to store arbitrary user-defined metadata without
    colliding with reserved/standard profile fields.

    Example:
        produzre user set-custom band "Shredding Evidence"

    Args:
        key (str): Custom metadata key.
        value (str): Custom metadata value.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=True, log_file=None)
    data = _load_user_profile()
    data.setdefault("profile", {})
    data["profile"].setdefault("custom", {})
    data["profile"]["custom"][key] = value
    _save_user_profile(data)
    logger.info("Set profile.custom.%s", key)
    logger.info("User profile: %s", _user_profile_path())
    return 0


def cmd_user_unset_custom(key: str) -> int:
    """CLI handler: remove a key from `profile.custom` in `user.yml`.

    If the key does not exist, this operation is a no-op.

    Args:
        key (str): Custom metadata key to remove.

    Returns:
        int: Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=True, log_file=None)
    data = _load_user_profile()
    data.setdefault("profile", {})
    data["profile"].setdefault("custom", {})
    data["profile"]["custom"].pop(key, None)
    _save_user_profile(data)
    logger.info("Removed profile.custom.%s", key)
    logger.info("User profile: %s", _user_profile_path())
    return 0
