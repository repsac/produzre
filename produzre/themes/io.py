"""Parse the top-level ``themes:`` YAML block into a ThemeBank (prototype).

Two input forms are supported per theme:

1. Shorthand string (rhythm-first, one line per theme)::

      events: "1:.5 .:.25 b3:.5 4:1"
      # token = degree:dur; "." or "r" = rest; b/# prefixes = accidentals;
      # trailing + / - = octave displacement ("5+" = degree 5 up an octave)

2. Explicit lists::

      degrees: [5, 5, 6, 5, 3]
      rhythm:  [0.5, 0.5, 0.5, 0.5, 2.0]

Common keys: ``role`` (riff|melody|bass_motif), ``register: [lo, hi]``,
``length_beats`` (default: sum of durations), ``allow_development``.

MIDI-clip import (``source: {midi: ...}``) is part of the design but is
deliberately out of scope for this prototype milestone.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..config.errors import ConfigError
from .model import DEFAULT_REGISTERS, Theme, ThemeBank, ThemeEvent, ThemeRole


_TOKEN_RE = re.compile(r"^([b#]*)([1-7]|[.r])([+-]*):([0-9]*\.?[0-9]+)$")


def _parse_shorthand(spec: str) -> List[ThemeEvent]:
    events: List[ThemeEvent] = []
    offset = 0.0
    for raw_tok in spec.split():
        m = _TOKEN_RE.match(raw_tok)
        if not m:
            raise ConfigError(
                f"themes: bad event token {raw_tok!r} "
                "(expected e.g. '1:.5', 'b3:.25', '.:.5', '5+:1')"
            )
        accs, deg_tok, octs, dur_s = m.groups()
        dur = float(dur_s)
        if dur <= 0:
            raise ConfigError(f"themes: event {raw_tok!r} has non-positive duration")
        if deg_tok in (".", "r"):
            events.append(ThemeEvent(offset, dur, None))
        else:
            events.append(
                ThemeEvent(
                    offset,
                    dur,
                    degree=int(deg_tok),
                    accidental=accs.count("#") - accs.count("b"),
                    octave=octs.count("+") - octs.count("-"),
                )
            )
        offset += dur
    return events


def _parse_lists(degrees: List[Any], rhythm: List[Any]) -> List[ThemeEvent]:
    if len(degrees) != len(rhythm):
        raise ConfigError(
            f"themes: degrees/rhythm length mismatch ({len(degrees)} vs {len(rhythm)})"
        )
    events: List[ThemeEvent] = []
    offset = 0.0
    for d, dur in zip(degrees, rhythm):
        dur = float(dur)
        if dur <= 0:
            raise ConfigError(f"themes: non-positive rhythm value {dur!r}")
        if d is None or str(d) in (".", "r"):
            events.append(ThemeEvent(offset, dur, None))
        else:
            m = re.match(r"^([b#]*)([1-7])([+-]*)$", str(d))
            if not m:
                raise ConfigError(f"themes: bad degree {d!r} (use 1-7, b/#, +/-)")
            accs, deg, octs = m.groups()
            events.append(
                ThemeEvent(
                    offset,
                    dur,
                    degree=int(deg),
                    accidental=accs.count("#") - accs.count("b"),
                    octave=octs.count("+") - octs.count("-"),
                )
            )
        offset += dur
    return events


def _parse_theme(name: str, spec: Dict[str, Any]) -> Theme:
    if not isinstance(spec, dict):
        raise ConfigError(f"themes.{name}: expected a mapping, got {type(spec).__name__}")

    role_raw = str(spec.get("role", "melody")).strip().lower()
    try:
        role = ThemeRole(role_raw)
    except ValueError:
        raise ConfigError(
            f"themes.{name}: unknown role {role_raw!r}; "
            f"expected one of: {', '.join(r.value for r in ThemeRole)}"
        )

    if "events" in spec:
        events = _parse_shorthand(str(spec["events"]))
    elif "degrees" in spec and "rhythm" in spec:
        events = _parse_lists(list(spec["degrees"]), list(spec["rhythm"]))
    else:
        raise ConfigError(
            f"themes.{name}: provide 'events' shorthand or 'degrees' + 'rhythm' lists"
        )
    if not any(not e.is_rest for e in events):
        raise ConfigError(f"themes.{name}: theme contains only rests")

    length = float(spec.get("length_beats") or sum(e.duration_beats for e in events))
    total = sum(e.duration_beats for e in events)
    if abs(total - length) > 1e-6:
        raise ConfigError(
            f"themes.{name}: event durations sum to {total:g} but length_beats={length:g}"
        )

    reg = spec.get("register")
    if reg is not None:
        if not (isinstance(reg, (list, tuple)) and len(reg) == 2):
            raise ConfigError(f"themes.{name}.register: expected [low, high]")
        register = (int(reg[0]), int(reg[1]))
    else:
        register = DEFAULT_REGISTERS[role]

    tags = {"user"}
    if spec.get("allow_development") is False:
        tags.add("locked")

    return Theme(
        name=name,
        role=role,
        length_beats=length,
        events=tuple(events),
        base_register=register,
        tags=frozenset(tags),
    )


def parse_themes_block(
    raw: Optional[Dict[str, Any]],
    logger: Optional[logging.Logger] = None,
) -> ThemeBank:
    """Parse the top-level ``themes:`` mapping into a finalized ThemeBank.

    Args:
        raw: Value of ``cfg.raw.get("themes")`` (None/absent -> empty bank).
        logger: Optional logger for diagnostics.

    Returns:
        ThemeBank (empty but finalized when no themes are defined).

    Raises:
        ConfigError: On any malformed theme specification.
    """
    log = logger or logging.getLogger("produzre")
    bank = ThemeBank()
    if not raw:
        return bank.finalize()
    if not isinstance(raw, dict):
        raise ConfigError("themes: expected a mapping of theme name -> spec")
    for name, spec in raw.items():
        theme = _parse_theme(str(name), spec)
        bank.themes[theme.name] = theme
        log.info(
            "Theme '%s' loaded (role=%s, %.1f beats, %d events, register=%s)",
            theme.name, theme.role.value, theme.length_beats,
            len(theme.events), theme.base_register,
        )
    return bank.finalize()
