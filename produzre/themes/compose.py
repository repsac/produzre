"""Rule-based theme composition (M4, design doc §6).

When a song has no ``themes:`` block, this module composes a small bank —
a riff and a hook — from the song seed. The rules matter more than the
randomness:

1. **Rhythm first.** A distinctive rhythm with plain pitches is a hook; the
   reverse is noodling. Cells come from a curated library, weighted by genre.
2. **Pitch skeleton.** Consonant degrees on strong beats, passing/neighbor
   degrees on weak beats; leaps larger than a third are answered by contrary
   stepwise motion.
3. **Question/answer.** The hook's two bars form an antecedent (ends on a
   half cadence: degree 5 or 2) and a consequent (same rhythm, full cadence
   on the tonic).
4. **Color tones.** Blues-family genres may flatten 3/5/7 for blue notes.
5. **Register by role.** Riff low, hook mid — from DEFAULT_REGISTERS.

The RNG only *selects* among valid options; generation is one dedicated
song-level stream, so take/variation change the performance, never the
song's identity.
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from .model import DEFAULT_REGISTERS, Theme, ThemeBank, ThemeEvent, ThemeRole

# ---------------------------------------------------------------------------
# Rhythm cell library (durations in beats, one bar each, 4/4 grid).
# Families are genre-weighted; cells are scaled for other meters.
# ---------------------------------------------------------------------------

_RHYTHM_FAMILIES: Dict[str, List[Tuple[float, ...]]] = {
    "driving": [
        (0.5,) * 8,
        (0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0),
        (1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0),
    ],
    "syncopated": [
        (0.75, 0.25, 0.5, 0.5, 1.0, 1.0),
        (0.5, 0.75, 0.25, 0.5, 1.0, 1.0),
        (1.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    ],
    "anthem": [
        (1.5, 0.5, 1.0, 1.0),
        (1.0, 1.0, 1.5, 0.5),
        (2.0, 0.5, 0.5, 1.0),
    ],
    "sparse": [
        (2.0, 1.0, 1.0),
        (3.0, 1.0),
        (2.0, 2.0),
    ],
    "conversational": [
        (0.5, 0.5, 0.75, 0.25, 2.0),
        (0.75, 0.25, 0.5, 0.5, 2.0),
        (0.5, 0.5, 1.0, 0.5, 0.5, 1.0),
    ],
}

_GENRE_FAMILY_WEIGHTS: List[Tuple[Tuple[str, ...], Dict[str, float]]] = [
    (("metal", "punk", "thrash", "hard_rock", "grunge"),
     {"driving": 0.6, "syncopated": 0.3, "anthem": 0.1}),
    (("funk", "soul", "rnb", "hip_hop", "disco"),
     {"syncopated": 0.6, "driving": 0.2, "conversational": 0.2}),
    (("jazz", "swing", "bebop", "bossa", "latin"),
     {"conversational": 0.5, "syncopated": 0.3, "sparse": 0.2}),
    (("ambient", "cinematic", "ballad", "post-rock", "folk"),
     {"sparse": 0.5, "anthem": 0.3, "conversational": 0.2}),
    (("blues", "country", "rock", "pop", "reggae", "ska"),
     {"anthem": 0.35, "driving": 0.25, "conversational": 0.25, "syncopated": 0.15}),
]
_DEFAULT_WEIGHTS = {"anthem": 0.3, "driving": 0.25, "conversational": 0.25,
                    "syncopated": 0.1, "sparse": 0.1}

# Genres where blue notes (b3 / b5 / b7) are idiomatic.
_COLOR_GENRES = ("blues", "rock", "metal", "punk", "grunge", "funk", "soul",
                 "rnb", "jazz", "country")

# Strong-beat-safe degrees (flattened index = degree - 1 + octave * 7).
_STRONG_DEGREES = (0, 2, 4)  # 1, 3, 5
_WEAK_DEGREES = (1, 3, 5, 6)  # 2, 4, 6, 7


def _pick_weighted(rng: random.Random, weights: Dict[str, float]) -> str:
    items = sorted(weights.items())
    total = sum(w for _, w in items)
    draw = rng.random() * total
    for name, w in items:
        draw -= w
        if draw <= 0:
            return name
    return items[-1][0]


def _genre_weights(genre: str) -> Dict[str, float]:
    g = str(genre or "").lower()
    for tokens, weights in _GENRE_FAMILY_WEIGHTS:
        if any(t in g for t in tokens):
            return weights
    return _DEFAULT_WEIGHTS


def _scale_cell(cell: Sequence[float], beats_per_bar: float) -> Tuple[float, ...]:
    """Adapt a 4/4 rhythm cell to another bar length (uniform scaling)."""
    if abs(beats_per_bar - 4.0) < 1e-9:
        return tuple(cell)
    factor = beats_per_bar / 4.0
    return tuple(d * factor for d in cell)


def _is_strong_beat(beat: float) -> bool:
    return abs(beat - round(beat)) < 1e-6


def _compose_pitches(
    rng: random.Random,
    rhythm: Sequence[float],
    *,
    lo_idx: int,
    hi_idx: int,
    start_idx: int,
    half_cadence_idx: Optional[int],
    full_cadence_idx: int,
    color_rate: float,
) -> List[Tuple[int, int, int]]:
    """Walk a pitch skeleton over a rhythm cell.

    Returns (degree, accidental, octave) per event. ``*_idx`` are flattened
    diatonic indices (degree - 1 + octave * 7).
    """
    events: List[Tuple[int, int, int]] = []
    idx = start_idx
    prev_leap_dir = 0  # +1 up, -1 down, 0 = none/step
    beat = 0.0
    last = len(rhythm) - 1

    for i, dur in enumerate(rhythm):
        is_final = i == last
        is_penult = i == last - 1
        strong = _is_strong_beat(beat)

        if is_final and full_cadence_idx is not None:
            idx = full_cadence_idx
        elif is_penult and half_cadence_idx is not None:
            idx = half_cadence_idx
        else:
            if prev_leap_dir != 0:
                # Leap recovery: contrary stepwise motion.
                step = -prev_leap_dir * rng.choice((1, 1, 2))
                idx += step
                prev_leap_dir = 0
            else:
                move = rng.random()
                if move < 0.70:
                    delta = rng.choice((-2, -1, 1, 2))
                    prev_leap_dir = 0
                elif move < 0.95:
                    delta = rng.choice((-4, -3, 3, 4))
                    prev_leap_dir = 1 if delta > 0 else -1
                else:
                    delta = 0
                    prev_leap_dir = 0
                idx += delta

            idx = max(lo_idx, min(hi_idx, idx))

            if strong:
                # Snap to the nearest consonant degree (1/3/5 area).
                idx = min(
                    range(lo_idx, hi_idx + 1),
                    key=lambda c: (
                        0 if (c % 7) in _STRONG_DEGREES else 1,
                        abs(c - idx),
                    ),
                )

        degree = (idx % 7) + 1
        octave = idx // 7
        accidental = 0
        # Blue notes: occasionally flatten 3 / 7 (rarely 5) on color genres.
        if color_rate > 0 and degree in (3, 7) and rng.random() < color_rate:
            accidental = -1
        elif color_rate > 0 and degree == 5 and rng.random() < color_rate * 0.3:
            accidental = -1

        events.append((degree, accidental, octave))
        beat += dur

    return events


def _make_theme(
    name: str,
    role: ThemeRole,
    rhythm: Sequence[float],
    pitches: Sequence[Tuple[int, int, int]],
) -> Theme:
    events = []
    beat = 0.0
    for dur, (degree, acc, oct_) in zip(rhythm, pitches):
        events.append(ThemeEvent(beat, dur, degree, acc, oct_))
        beat += dur
    return Theme(
        name=name,
        role=role,
        length_beats=beat,
        events=tuple(events),
        base_register=DEFAULT_REGISTERS[role],
        tags=frozenset({"generated"}),
    )


def compose_theme_bank(
    cfg,
    logger: Optional[logging.Logger] = None,
) -> ThemeBank:
    """Compose an automatic riff + hook from the song seed.

    Deterministic: one dedicated stream derived from the (effective) song
    seed, genre, key, and mode. Take and variation never participate, so a
    new take is a new performance of the same song.
    """
    log = logger or logging.getLogger("produzre")
    song = getattr(cfg, "song", None)
    genre = str(getattr(song, "genre", "") or "")
    key = str(getattr(song, "key", "C") or "C")
    mode = str(getattr(song, "mode", "major") or "major")
    seed = int(getattr(song, "seed", 0) or 0)
    bpb = float(getattr(song, "beats_per_bar", 4) or 4)

    rng = random.Random(stable_seed_int("themes.compose", seed, genre, key, mode))
    weights = _genre_weights(genre)
    color_rate = 0.18 if any(t in genre.lower() for t in _COLOR_GENRES) else 0.0

    bank = ThemeBank()

    # --- Riff: one bar, low register, root-anchored, repetitive ----------
    riff_family = _pick_weighted(rng, weights)
    riff_cell = _scale_cell(rng.choice(_RHYTHM_FAMILIES[riff_family]), bpb)
    riff_pitches = _compose_pitches(
        rng, riff_cell,
        lo_idx=0, hi_idx=7,            # degree 1 .. degree 1+8va
        start_idx=0,
        half_cadence_idx=None,
        full_cadence_idx=0,            # riffs always close on the tonic
        color_rate=color_rate,
    )
    bank.themes["auto_riff"] = _make_theme(
        "auto_riff", ThemeRole.RIFF, riff_cell, riff_pitches
    )

    # --- Hook: two bars, question/answer --------------------------------
    hook_family = _pick_weighted(rng, weights)
    antecedent = _scale_cell(rng.choice(_RHYTHM_FAMILIES[hook_family]), bpb)
    half_idx = rng.choice((4, 1))      # half cadence: 5 or 2
    ant_pitches = _compose_pitches(
        rng, antecedent,
        lo_idx=4, hi_idx=12,           # degree 5 low .. degree 5 high
        start_idx=7,                   # start on the tonic, up an octave
        half_cadence_idx=half_idx,
        full_cadence_idx=half_idx,
        color_rate=color_rate,
    )
    # Consequent: same rhythm, mostly the same pitches, full cadence on 1.
    con_pitches = []
    for j, (degree, acc, oct_) in enumerate(ant_pitches):
        if j == len(ant_pitches) - 1:
            con_pitches.append((1, 0, oct_ if degree >= 5 else 1))
        elif j == len(ant_pitches) - 2:
            con_pitches.append((2 if rng.random() < 0.5 else 7, 0, oct_))
        elif rng.random() < 0.75:      # mostly repeat: identity lives here
            con_pitches.append((degree, acc, oct_))
        else:
            step = rng.choice((-1, 1))
            new_idx = (degree - 1) + oct_ * 7 + step
            new_idx = max(4, min(12, new_idx))
            con_pitches.append(((new_idx % 7) + 1, acc, new_idx // 7))

    hook_rhythm = tuple(antecedent) + tuple(antecedent)
    hook_pitches = list(ant_pitches) + con_pitches
    bank.themes["auto_hook"] = _make_theme(
        "auto_hook", ThemeRole.MELODY, hook_rhythm, hook_pitches
    )

    bank.finalize()
    log.info(
        "Auto-composed themes (genre=%s, riff=%s, hook=%s), hash %s",
        genre or "default", riff_family, hook_family, bank.seed_material_hash,
    )
    return bank
