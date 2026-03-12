from __future__ import annotations

"""Argument parser definition for the Produzre CLI.

This module defines the full `argparse` command tree (subcommands and flags)
without embedding business logic.

Why keep this separate?
- **Stability:** the CLI surface area is easy to review and version.
- **Refactors:** command implementations can move between modules without
  rewriting argument wiring.
- **Testability:** parser behavior can be unit-tested independently from
  configuration loading and orchestration.

All handlers are dispatched elsewhere (see `cli_impl/dispatch.py`).
"""

import argparse


def create_parser() -> argparse.ArgumentParser:
    """Create and return the Produzre CLI argument parser.

    The parser is intentionally kept free of business logic. This function should:
    - Declare commands/subcommands and their flags.
    - Provide stable defaults for options.
    - Avoid importing orchestration/config modules to prevent import cycles.

    Command groups
    --------------
    Song commands (require a YAML song config):
    - `build`        Build/export MIDI and analysis artifacts.
    - `validate`     Validate a YAML song config.
    - `show-config`  Print the effective configuration (after defaults/overrides).

    Registry/profile commands (do not require a song config):
    - `project ...`  Manage local project seeds + metadata registry.
    - `user ...`     Manage local user profile metadata.

    Returns
    -------
    argparse.ArgumentParser
        The configured top-level parser.
    """
    from produzre import __version__

    parser = argparse.ArgumentParser(
        prog="produzre",
        description="Produzre - procedural section-based MIDI engine.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )

    # Top-level subcommands are required so the CLI always has an explicit mode.
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Options shared by song commands that consume a YAML song config.
    def add_common(args_parser: argparse.ArgumentParser) -> None:
        # Path to the song YAML is positional to keep commands concise.
        args_parser.add_argument(
            "config",
            help="Path to the YAML song configuration.",
        )
        args_parser.add_argument(
            "--song-name",
            help="Override song name used for exports (falls back to song.title).",
        )
        args_parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Enable verbose logging.",
        )

    # build
    build_p = subparsers.add_parser("build", help="Build the song (MIDI export).")
    add_common(build_p)
    build_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate config, but do not write MIDI.",
    )
    build_p.add_argument(
        "--sections-absolute-timing",
        action="store_true",
        help="Keep song-global timing in section MIDIs instead of rebasing to 0.",
    )
    # Export sections/patterns by default (MIDI files are small; this is a key feature).
    build_p.set_defaults(export_sections=True, export_patterns=True)

    # Invert-logic flags: allow users to disable exports explicitly.
    build_p.add_argument(
        "--no-export-sections",
        dest="export_sections",
        action="store_false",
        help="Disable per-section MIDIs per instrument.",
    )
    build_p.add_argument(
        "--no-export-patterns",
        dest="export_patterns",
        action="store_false",
        help="Disable per-pattern MIDIs and per-instrument sequence YAML.",
    )

    # Determinism validation
    build_p.add_argument(
        "--strict-determinism",
        action="store_true",
        help="Verify byte-identical MIDI output by building twice and comparing hashes.",
    )

    # validate
    validate_p = subparsers.add_parser("validate", help="Validate the YAML config.")
    add_common(validate_p)

    # show-config
    show_p = subparsers.add_parser(
        "show-config", help="Load and print the effective configuration."
    )
    add_common(show_p)
    show_p.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format for effective config.",
    )

    # project
    project_p = subparsers.add_parser(
        "project",
        help="Manage local projects (seed registry + metadata).",
    )
    # Note: `project` also accepts -v for convenience; it does not share song options.
    project_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show more details (including seed).",
    )
    project_sp = project_p.add_subparsers(dest="project_cmd", required=True)

    list_p = project_sp.add_parser("list", help="List local projects.")
    # `project list` duplicates -v so it can be used with or without the parent `project -v`.
    list_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show more details (including seed).",
    )

    path_p = project_sp.add_parser("path", help="Print the projects registry path.")
    # `project path` accepts -v only for consistency with other subcommands.
    path_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="(Accepted for consistency; no additional output.)",
    )

    create_p = project_sp.add_parser("create", help="Create a new local project.")
    create_p.add_argument("name", help="Project name.")
    create_p.add_argument("--seed", type=int, default=None, help="Optional explicit seed.")
    create_p.add_argument("--notes", default="", help="Notes for this project.")
    create_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print created project YAML.",
    )

    show_proj_p = project_sp.add_parser("show", help="Show metadata for a project.")
    show_proj_p.add_argument("name", help="Project name.")
    show_proj_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show more details (including seed).",
    )

    export_p = project_sp.add_parser("export", help="Export a project to a shareable YAML file.")
    export_p.add_argument("name", help="Project name.")
    export_p.add_argument("--out", required=True, help="Output path for exported project YAML.")
    export_p.add_argument(
        "--include",
        default=None,
        help="Comma-separated list of custom keys to include from project.custom (e.g. band,email,url).",
    )
    export_p.add_argument(
        "--include-all-custom",
        action="store_true",
        help="Include all keys from project.custom.",
    )
    export_p.add_argument(
        "--no-seed",
        action="store_true",
        help="Omit seed from export (NOT recommended for reproducibility).",
    )
    export_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print export summary.",
    )

    import_p = project_sp.add_parser("import", help="Import a project YAML into the local registry.")
    import_p.add_argument("path", help="Path to a project export YAML file.")
    import_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing local project with the same name.",
    )
    import_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print import summary.",
    )

    setpc_p = project_sp.add_parser(
        "set-custom",
        help="Set a project custom metadata key/value (stored in the local registry).",
    )
    setpc_p.add_argument("name", help="Project name.")
    setpc_p.add_argument("key", help="Custom metadata key.")
    setpc_p.add_argument("value", help="Custom metadata value.")
    setpc_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print updated project YAML.",
    )

    unsetpc_p = project_sp.add_parser(
        "unset-custom",
        help="Remove a project custom metadata key (stored in the local registry).",
    )
    unsetpc_p.add_argument("name", help="Project name.")
    unsetpc_p.add_argument("key", help="Custom metadata key to remove.")
    unsetpc_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print updated project YAML.",
    )

    setowner_p = project_sp.add_parser(
        "set-owner",
        help="Set/override the project owner display name in the local registry.",
    )
    setowner_p.add_argument("name", help="Project name.")
    setowner_p.add_argument("owner", help="Owner display name to set.")
    setowner_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print updated project YAML.",
    )

    # user
    user_p = subparsers.add_parser(
        "user",
        help="Manage local user profile metadata (stored in the Produzre config directory).",
    )
    user_sp = user_p.add_subparsers(dest="user_cmd", required=True)

    user_sp.add_parser("show", help="Show the local user profile YAML.")
    user_sp.add_parser("path", help="Print the user profile YAML path.")

    set_p = user_sp.add_parser("set", help="Set a standard profile field.")
    set_p.add_argument(
        "field",
        choices=["name", "email", "url", "company", "band"],
        help="Profile field to set.",
    )
    set_p.add_argument("value", help="Value to set.")

    setc_p = user_sp.add_parser("set-custom", help="Set a custom profile key/value.")
    setc_p.add_argument("key", help="Custom key.")
    setc_p.add_argument("value", help="Custom value.")

    unsetc_p = user_sp.add_parser("unset-custom", help="Remove a custom profile key.")
    unsetc_p.add_argument("key", help="Custom key to remove.")

    return parser
