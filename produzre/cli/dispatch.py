"""CLI dispatch routing for Produzre.

This module contains the central `dispatch()` function that maps parsed argparse
arguments to the appropriate command handler. The goal is to keep `cli.py` thin
and to isolate branching/command wiring in one place.

Commands fall into two categories:
- User/Project commands that operate on local registry/profile files only.
- Song commands that first load a `RootConfig` from YAML + CLI overrides.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from ..config import ConfigError
from ..model import RootConfig


def dispatch(
    *,
    args: Any,
    parser: Any,
    load_config_with_overrides: Callable[[str, Optional[str]], RootConfig],
    # user
    cmd_user_path: Callable[[], int],
    cmd_user_show: Callable[[], int],
    cmd_user_set: Callable[..., int],
    cmd_user_set_custom: Callable[..., int],
    cmd_user_unset_custom: Callable[..., int],
    # project
    cmd_project_list: Callable[..., int],
    cmd_project_path: Callable[[], int],
    cmd_project_create: Callable[..., int],
    cmd_project_show: Callable[..., int],
    cmd_project_export: Callable[..., int],
    cmd_project_import: Callable[..., int],
    cmd_project_set_custom: Callable[..., int],
    cmd_project_unset_custom: Callable[..., int],
    cmd_project_set_owner: Callable[..., int],
    # song-config commands
    cmd_validate: Callable[[RootConfig], int],
    cmd_show_config: Callable[[RootConfig, str], int],
    cmd_build: Callable[..., int],
) -> int:
    """Route parsed argparse args to the correct command handler.

    This function is the single branching point for the CLI. It translates the
    parsed `argparse.Namespace` into calls to the concrete `cmd_*` handlers passed
    in as callables.

    Design goals:
    - Keep the top-level CLI module thin by isolating command wiring here.
    - Make refactors safer by centralizing branching/dispatch logic.
    - Cleanly separate commands that *do not* require a song config (user/project)
      from commands that *do* require loading a `RootConfig`.

    Parameters
    ----------
    args:
        Parsed argparse arguments (typically an `argparse.Namespace`). Expected to
        include `command` and the relevant subcommand fields.
    parser:
        The argparse parser instance. Used only as a fallback to print help.
    load_config_with_overrides:
        Callable that loads and returns a `RootConfig` given a YAML path and an
        optional song name override.
    cmd_*:
        Command handlers implementing the CLI behavior. These are injected to avoid
        import cycles and to make the dispatch layer easy to unit test.

    Returns
    -------
    int
        A process-style exit code: `0` on success, non-zero on failure.

    Notes
    -----
    - User/project commands operate only on local registry/profile files and do not
      require loading a song YAML.
    - Song commands load a `RootConfig` (and may apply CLI overrides) before
      calling their handler.
    """

    # User subcommands: operate on the user profile only (no song YAML).
    if args.command == "user":
        if args.user_cmd == "path":
            return cmd_user_path()
        if args.user_cmd == "show":
            return cmd_user_show()
        if args.user_cmd == "set":
            return cmd_user_set(field=args.field, value=args.value)
        if args.user_cmd == "set-custom":
            return cmd_user_set_custom(key=args.key, value=args.value)
        if args.user_cmd == "unset-custom":
            return cmd_user_unset_custom(key=args.key)

        sys.stderr.write("Unknown user subcommand.\n")
        return 1

    # Project subcommands: operate on the projects registry only (no song YAML).
    if args.command == "project":
        if args.project_cmd == "list":
            return cmd_project_list(verbose=args.verbose)
        if args.project_cmd == "path":
            return cmd_project_path()
        if args.project_cmd == "create":
            return cmd_project_create(
                name=args.name,
                seed=args.seed,
                notes=args.notes,
                verbose=args.verbose,
            )
        if args.project_cmd == "show":
            return cmd_project_show(name=args.name, verbose=args.verbose)
        if args.project_cmd == "export":
            return cmd_project_export(
                name=args.name,
                out_path=args.out,
                include=getattr(args, "include", None),
                include_all_custom=getattr(args, "include_all_custom", False),
                no_seed=getattr(args, "no_seed", False),
                verbose=args.verbose,
            )
        if args.project_cmd == "import":
            return cmd_project_import(
                path=args.path,
                overwrite=getattr(args, "overwrite", False),
                verbose=args.verbose,
            )
        if args.project_cmd == "set-custom":
            return cmd_project_set_custom(
                name=args.name,
                key=args.key,
                value=args.value,
                verbose=args.verbose,
            )
        if args.project_cmd == "unset-custom":
            return cmd_project_unset_custom(
                name=args.name,
                key=args.key,
                verbose=args.verbose,
            )
        if args.project_cmd == "set-owner":
            return cmd_project_set_owner(
                name=args.name,
                owner=args.owner,
                verbose=args.verbose,
            )

        sys.stderr.write("Unknown project subcommand.\n")
        return 1

    # Song commands: require loading a RootConfig from YAML + CLI overrides.
    try:
        cfg = load_config_with_overrides(args.config, getattr(args, "song_name", None))
    except ConfigError as e:
        # Config errors are considered user-facing; keep the message concise.
        sys.stderr.write(f"Config error: {e}\n")
        return 1

    if args.command == "validate":
        return cmd_validate(cfg)
    if args.command == "show-config":
        return cmd_show_config(cfg, args.format)
    if args.command == "build":
        return cmd_build(
            cfg,
            dry_run=args.dry_run,
            verbose=args.verbose,
            export_sections=args.export_sections,
            export_patterns=args.export_patterns,
            sections_absolute_timing=args.sections_absolute_timing,
            strict_determinism=getattr(args, "strict_determinism", False),
        )

    # Unknown/unspecified command: show help for discoverability.
    parser.print_help()
    return 1
