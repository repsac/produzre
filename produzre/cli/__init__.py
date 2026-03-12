from __future__ import annotations

"""CLI implementation for Produzre.

This module contains the main CLI entry point logic that was previously in
`cli.py`. The public-facing `cli.py` now serves as a thin compatibility shim.

Implementation structure:
- `parser.py` defines the argparse tree (subcommands + flags)
- `dispatch.py` routes parsed args to command handlers
- `commands/` package implements command families (user, project, song)

The `main()` function here is the canonical CLI entry point.
"""

from typing import Optional

from ..config import load_root_config
from ..model import RootConfig
from .parser import create_parser
from .dispatch import dispatch

from .commands.user import (
    cmd_user_path,
    cmd_user_show,
    cmd_user_set,
    cmd_user_set_custom,
    cmd_user_unset_custom,
)
from .commands.project import (
    cmd_project_list,
    cmd_project_path,
    cmd_project_create,
    cmd_project_show,
    cmd_project_export,
    cmd_project_import,
    cmd_project_set_custom,
    cmd_project_unset_custom,
    cmd_project_set_owner,
)
from .commands.song import (
    cmd_validate,
    cmd_show_config,
    cmd_build,
)


def _load_config_with_cli_overrides(config_path: str, song_name: Optional[str]) -> RootConfig:
    """Load the root config and apply lightweight CLI-only overrides.

    The YAML file is treated as the canonical source of truth for song and
    engine settings. CLI flags may optionally override a few top-level values
    that are ergonomic to specify at invocation time.

    Currently supported override:
      - `song_name`: sets `cfg.song.song_name_override` to control export naming.

    Args:
        config_path: Path to the song YAML file.
        song_name: Optional song title override.

    Returns:
        RootConfig: Parsed configuration with any CLI overrides applied.
    """
    cfg = load_root_config(config_path)
    if song_name:
        cfg.song.song_name_override = song_name
    return cfg


def main(argv: Optional[list[str]] = None) -> int:
    """Run the Produzre CLI.

    This function builds the argparse parser, parses argv, and dispatches the
    selected subcommand.

    Args:
        argv: Optional argument list. When None, argparse uses sys.argv.

    Returns:
        int: Process exit code (0 on success, non-zero on error).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    return dispatch(
        args=args,
        parser=parser,
        load_config_with_overrides=_load_config_with_cli_overrides,
        # user
        cmd_user_path=cmd_user_path,
        cmd_user_show=cmd_user_show,
        cmd_user_set=cmd_user_set,
        cmd_user_set_custom=cmd_user_set_custom,
        cmd_user_unset_custom=cmd_user_unset_custom,
        # project
        cmd_project_list=cmd_project_list,
        cmd_project_path=cmd_project_path,
        cmd_project_create=cmd_project_create,
        cmd_project_show=cmd_project_show,
        cmd_project_export=cmd_project_export,
        cmd_project_import=cmd_project_import,
        cmd_project_set_custom=cmd_project_set_custom,
        cmd_project_unset_custom=cmd_project_unset_custom,
        cmd_project_set_owner=cmd_project_set_owner,
        # song-config commands
        cmd_validate=cmd_validate,
        cmd_show_config=cmd_show_config,
        cmd_build=cmd_build,
    )


if __name__ == "__main__":
    raise SystemExit(main())
