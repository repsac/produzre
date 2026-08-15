"""Deterministic theme transformations (prototype).

Every transform is a pure function Theme -> Theme. Development choices (which
transform, with what parameters) are made by the arrangement arc using seeded
RNG; the transforms themselves involve no randomness. This is what keeps a
fully developed arrangement bit-for-bit reproducible.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict, List

from .model import Theme, ThemeEvent


def _degree_index(degree: int, octave: int) -> int:
    """Flatten (degree, octave) to a single diatonic step index (0 = tonic)."""
    return (degree - 1) + octave * 7


def _unflatten(index: int) -> tuple[int, int]:
    """Inverse of _degree_index; floor division handles negatives."""
    return (index % 7) + 1, index // 7


def quote(theme: Theme, **_) -> Theme:
    """Exact restatement. Realization still tracks the local harmony."""
    return theme


def sequence(theme: Theme, *, steps: int = 2, **_) -> Theme:
    """Shift all degrees by N diatonic steps (the classic sequence)."""
    events = tuple(
        replace(
            e,
            degree=_unflatten(_degree_index(e.degree, e.octave) + steps)[0],
            octave=_unflatten(_degree_index(e.degree, e.octave) + steps)[1],
        )
        if not e.is_rest
        else e
        for e in theme.events
    )
    return replace(theme, events=events)


def invert(theme: Theme, **_) -> Theme:
    """Mirror intervals around the first sounded degree (diatonic inversion).

    Accidentals are preserved rather than flipped: a blue note (b3, b5)
    mirrors to a flattened degree below the anchor, which keeps the color
    character instead of respelling it as an augmented degree.
    """
    sounded = [e for e in theme.events if not e.is_rest]
    if not sounded:
        return theme
    anchor = _degree_index(sounded[0].degree, sounded[0].octave)
    events = tuple(
        replace(
            e,
            degree=_unflatten(2 * anchor - _degree_index(e.degree, e.octave))[0],
            octave=_unflatten(2 * anchor - _degree_index(e.degree, e.octave))[1],
        )
        if not e.is_rest
        else e
        for e in theme.events
    )
    return replace(theme, events=events)


def fragment(theme: Theme, *, keep: str = "first", beats: float = 0.0, **_) -> Theme:
    """Keep only the first or last ``beats`` of the theme (default: half)."""
    window = float(beats) if beats > 0 else theme.length_beats / 2.0
    if keep == "last":
        lo = theme.length_beats - window
        shifted = tuple(
            replace(e, offset_beats=e.offset_beats - lo)
            for e in theme.events
            if e.offset_beats >= lo
        )
        return replace(theme, events=shifted, length_beats=window)
    clipped = tuple(
        replace(e, duration_beats=min(e.duration_beats, window - e.offset_beats))
        for e in theme.events
        if e.offset_beats < window
    )
    clipped = tuple(e for e in clipped if e.duration_beats > 0)
    return replace(theme, events=clipped, length_beats=window)


def displace(theme: Theme, *, shift_beats: float = 0.5, **_) -> Theme:
    """Rotate the rhythm within the theme length (re-grooving a riff)."""
    length = theme.length_beats
    moved: List[ThemeEvent] = []
    for e in theme.events:
        off = (e.offset_beats + shift_beats) % length
        dur = min(e.duration_beats, length - off)
        if dur > 0:
            moved.append(replace(e, offset_beats=off, duration_beats=dur))
    moved.sort(key=lambda e: e.offset_beats)
    return replace(theme, events=tuple(moved))


def augment(theme: Theme, *, factor: float = 2.0, **_) -> Theme:
    """Stretch durations (climax)."""
    return replace(
        theme,
        events=tuple(
            replace(
                e,
                offset_beats=e.offset_beats * factor,
                duration_beats=e.duration_beats * factor,
            )
            for e in theme.events
        ),
        length_beats=theme.length_beats * factor,
    )


def diminish(theme: Theme, *, factor: float = 0.5, **_) -> Theme:
    """Compress durations (urgency). Same scaling mechanics as augment."""
    return augment(theme, factor=factor)


def thin(theme: Theme, **_) -> Theme:
    """Remove weak-beat events; keep downbeats, accents, and the first event."""
    kept = [
        e
        for i, e in enumerate(theme.events)
        if i == 0 or e.accent or e.is_rest or e.offset_beats % 1.0 == 0.0
    ]
    return replace(theme, events=tuple(kept))


def octave_shift(theme: Theme, *, octaves: int = 1, **_) -> Theme:
    """Transpose everything by whole octaves (final-chorus lift)."""
    return replace(
        theme,
        events=tuple(
            replace(e, octave=e.octave + octaves) if not e.is_rest else e
            for e in theme.events
        ),
    )


TRANSFORMS: Dict[str, Callable[..., Theme]] = {
    "quote": quote,
    "sequence": sequence,
    "invert": invert,
    "fragment": fragment,
    "displace": displace,
    "augment": augment,
    "diminish": diminish,
    "thin": thin,
    "octave_shift": octave_shift,
}


def apply_transform(theme: Theme, name: str, **params) -> Theme:
    """Apply a named transform; unknown names raise KeyError with options."""
    if name not in TRANSFORMS:
        raise KeyError(
            f"unknown transform {name!r}; available: {sorted(TRANSFORMS)}"
        )
    return TRANSFORMS[name](theme, **params)
