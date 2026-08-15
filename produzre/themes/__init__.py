"""Song-level thematic material for Produzre (prototype, design M1).

This package implements the Theme Bank proposal in
``docs/design/theme-bank-architecture.md``: themes are stored as
**rhythm + scale degrees** (not absolute pitches), generated once per song or
authored by the user, then *realized* over the harmony plan and *developed*
via pure deterministic transforms.

Public API:
    - model:     ThemeEvent, Theme, ThemeBank, ThemeRole
    - transform: pure Theme -> Theme development functions
    - realize:   Theme + chord slots -> concrete pitches
    - io:        parse the top-level ``themes:`` YAML block
"""

from .model import Theme, ThemeBank, ThemeEvent, ThemeRole
from .realize import RealizedNote, realize_theme
from .io import parse_themes_block

__all__ = [
    "Theme",
    "ThemeBank",
    "ThemeEvent",
    "ThemeRole",
    "RealizedNote",
    "realize_theme",
    "parse_themes_block",
]
