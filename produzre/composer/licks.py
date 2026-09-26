"""Idiomatic lead-guitar licks.

Licks are written on a *ladder* instead of absolute pitches: the pentatonic
ladder (minor pentatonic in minor-family modes, major pentatonic otherwise)
or the diatonic ladder. Index 0 is the tonic; the realizer places the lick
in a register "box" and follows the harmony only where a sustained note
would clash. One lick therefore works in any key, and the same figure turns
bluesy in minor and country-flavored in major, the way players reuse
vocabulary.

A song draws a bank of three licks and keeps reusing them for fills, which
gives its lead guitar a recognizable voice instead of a new random figure
every phrase.

Technique codes: ``bend2``/``bend1`` bend up into the written pitch,
``rel`` a release after a bend, ``slide`` slide in from below, ``hammer`` a
quick hammer-on grace, ``vib`` wide vibrato, ``stac`` staccato.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .realize import Note
from .theory import ChordMap, pentatonic_pcs, pitches_in, scale_pcs, tonic_pc


@dataclass(frozen=True)
class Lick:
    name: str
    families: Tuple[str, ...]
    notes: Tuple[Tuple[float, float, int, Optional[str]], ...]
    length: float
    ladder: str = "penta"
    energy: float = 0.5  # 0 = laid back, 1 = shred


def _L(name, families, notes, ladder="penta", energy=0.5):
    length = max(o + d for o, d, _, _ in notes)
    return Lick(name, tuple(families), tuple(notes), float(length), ladder, energy)


LICKS: Tuple[Lick, ...] = (
    # --- blues / rock pentatonic vocabulary --------------------------------
    _L("bend_release_home", ("rock", "blues", "pop"),
       [(0, .5, 3, "bend2"), (.5, .5, 2, "rel"), (1, .5, 1, None), (1.5, 1.5, 0, "vib")]),
    _L("climb_and_cry", ("rock", "blues", "metal"),
       [(0, .25, 0, None), (.25, .25, 1, None), (.5, .5, 2, None), (1, 2, 4, "bend2")], energy=.6),
    _L("root_b7_answer", ("rock", "blues", "funk"),
       [(0, .5, 5, None), (.5, .5, 4, None), (1, .5, 3, None), (1.5, .5, 4, "bend1"), (2, 1, 3, "vib")]),
    _L("double_pickup", ("rock", "pop", "country"),
       [(0, .5, 2, None), (.5, .5, 2, None), (1, .5, 3, "slide"), (1.5, .5, 4, None), (2, 2, 3, "vib")]),
    _L("descending_triplets", ("rock", "blues", "metal"),
       [(0, 1 / 3, 5, None), (1 / 3, 1 / 3, 4, None), (2 / 3, 1 / 3, 3, None),
        (1, 1 / 3, 4, None), (4 / 3, 1 / 3, 3, None), (5 / 3, 1 / 3, 2, None),
        (2, 1, 1, None), (3, 1, 0, "vib")], energy=.75),
    _L("slow_hand_bend", ("blues", "rock", "soul", "gospel"),
       [(0, 1.5, 4, "bend2"), (1.5, .5, 3, "rel"), (2, 2, 2, "vib")], energy=.3),
    _L("call_repeat", ("rock", "pop", "funk"),
       [(0, .5, 3, None), (.5, .25, 3, "stac"), (.75, .75, 4, "bend1"), (1.5, .5, 3, None),
        (2, 1, 2, "vib")]),
    # --- metal ------------------------------------------------------------
    _L("pedal_run", ("metal",),
       [(0, .25, 0, "stac"), (.25, .25, 2, None), (.5, .25, 0, "stac"), (.75, .25, 3, None),
        (1, .25, 0, "stac"), (1.25, .25, 4, None), (1.5, .5, 5, "vib")], energy=.9),
    _L("tremolo_scream", ("metal", "rock"),
       [(0, .25, 5, None), (.25, .25, 5, None), (.5, .25, 5, None), (.75, .25, 5, None),
        (1, .25, 6, None), (1.25, .25, 5, None), (1.5, 1.5, 4, "bend2")], energy=1.0),
    _L("harmonic_minor_dive", ("metal",),
       [(0, .25, 7, None), (.25, .25, 6, None), (.5, .25, 5, None), (.75, .25, 4, None),
        (1, .5, 3, None), (1.5, 1.5, 4, "vib")], ladder="diatonic", energy=.85),
    # --- country / major pentatonic ----------------------------------------
    _L("chicken_pick", ("country", "pop", "folk"),
       [(0, .25, 2, "stac"), (.25, .25, 3, None), (.5, .5, 4, "bend2"), (1, .5, 3, None),
        (1.5, .5, 2, None), (2, 1, 0, "vib")], energy=.6),
    _L("pedal_steel_sigh", ("country", "folk", "gospel", "soul"),
       [(0, 1, 1, "bend2"), (1, .5, 0, None), (1.5, 1.5, -1, "vib")], energy=.25),
    # --- funk / soul ------------------------------------------------------
    _L("funk_stab_run", ("funk", "rnb", "soul", "disco"),
       [(0, .25, 3, "stac"), (.5, .25, 3, "stac"), (.75, .25, 4, "stac"), (1, .25, 5, "stac"),
        (1.5, .5, 4, None)], energy=.55),
    _L("soul_turn", ("soul", "rnb", "gospel", "pop"),
       [(0, .25, 2, None), (.25, .25, 3, None), (.5, .25, 2, None), (.75, .25, 1, None),
        (1, 2, 0, "vib")], ladder="diatonic", energy=.35),
    # --- jazz / fusion ----------------------------------------------------
    _L("bebop_enclosure", ("jazz", "latin", "bossa"),
       [(0, .5, 3, None), (.5, .5, 1, None), (1, .5, 2, None), (1.5, .5, 4, None),
        (2, 1, 2, None)], ladder="diatonic", energy=.5),
    # --- pop / anthemic ---------------------------------------------------
    _L("slide_to_hook_note", ("pop", "rock", "emo", "new_wave"),
       [(0, .5, 1, None), (.5, .5, 2, None), (1, 2, 3, "slide")], energy=.4),
    _L("octave_lift", ("pop", "rock", "cinematic", "post-rock"),
       [(0, 1, 0, None), (1, 1, 5, "slide"), (2, 2, 4, "vib")], energy=.45),
)

_FAMILY_ALIASES = (
    ("hard_rock", "rock"), ("grunge", "rock"), ("punk", "rock"), ("alt", "rock"),
    ("prog", "rock"), ("arena", "rock"), ("thrash", "metal"), ("heavy", "metal"),
    ("r&b", "rnb"), ("hip_hop", "funk"), ("ska", "funk"), ("reggae", "funk"),
    ("swing", "jazz"), ("bebop", "jazz"), ("electronic", "pop"), ("techno", "pop"),
    ("dance", "pop"), ("classical", "cinematic"), ("ambient", "cinematic"),
)


def genre_family(genre: str) -> str:
    g = str(genre or "").lower().replace(" ", "_").replace("-", "_")
    for fam in ("metal", "blues", "country", "funk", "soul", "gospel", "jazz", "latin",
                "folk", "rnb", "emo", "new_wave", "cinematic", "post_rock", "pop", "rock"):
        if fam in g:
            return fam
    for token, fam in _FAMILY_ALIASES:
        if token in g:
            return fam
    return "rock"


def choose_lick_bank(rng: random.Random, *, genre: str, count: int = 3,
                     max_energy: float = 0.7) -> List[Lick]:
    """The song's signature fills: idiomatic for the genre and laid back
    enough to answer a phrase (shred licks are saved for the solo)."""
    fam = genre_family(genre)
    pool = [l for l in LICKS if fam in l.families and l.energy <= max_energy]
    others = [l for l in LICKS if fam not in l.families and "rock" in l.families
              and l.energy <= max_energy]
    bank: List[Lick] = []
    while pool and len(bank) < count:
        pick = pool.pop(rng.randrange(len(pool)))
        bank.append(pick)
    while others and len(bank) < count:
        bank.append(others.pop(rng.randrange(len(others))))
    return bank


def _ladder(lick: Lick, key: str, mode: str, lo: int, hi: int) -> List[int]:
    pcs = pentatonic_pcs(key, mode) if lick.ladder == "penta" else scale_pcs(key, mode)
    return pitches_in(pcs, lo - 12, hi + 12)


def realize_lick(
    lick: Lick,
    start: float,
    chords: ChordMap,
    *,
    key: str,
    mode: str,
    lo: int,
    hi: int,
    anchor: int,
    beats_per_bar: float = 4.0,
    time_scale: float = 1.0,
) -> List[Note]:
    """Place a lick with its ladder index 0 on the tonic nearest ``anchor``.

    Sustained notes that clash with the chord slide to the nearest ladder or
    chord tone; quick notes pass freely, as they do under a player's hands.
    """
    ladder = _ladder(lick, key, mode, lo, hi)
    t = tonic_pc(key)
    tonics = [i for i, p in enumerate(ladder) if p % 12 == t]
    if not tonics:
        return []
    per_octave = 5 if lick.ladder == "penta" else 7

    def span(b: int) -> Tuple[int, int]:
        ps = [ladder[max(0, min(len(ladder) - 1, b + idx))] for _, _, idx, _ in lick.notes]
        return min(ps), max(ps)

    def centre(b: int) -> float:
        ps = [ladder[max(0, min(len(ladder) - 1, b + idx))] for _, _, idx, _ in lick.notes]
        return sum(ps) / len(ps)

    # Place the lick so its centre of pitch (not its tonic) sits at the
    # anchor: a climax lick belongs at the top of the register plan.
    fitting = [b for b in tonics if span(b)[1] <= hi + 2 and span(b)[0] >= lo - 2]
    base = min(fitting or tonics, key=lambda b: (abs(centre(b) - anchor), b))

    # Move the whole lick by octaves until it fits: folding single notes
    # would break its shape (a tremolo peak dropping below its own run).
    for _ in range(3):
        low, high = span(base)
        if high > hi + 2 and base - per_octave >= 0:
            base -= per_octave
        elif low < lo - 2 and base + per_octave < len(ladder):
            base += per_octave
        else:
            break
    out: List[Note] = []
    for onset, dur, idx, tech in lick.notes:
        j = max(0, min(len(ladder) - 1, base + idx))
        pitch = ladder[j]
        beat = start + onset * time_scale
        d = dur * time_scale
        span = chords.at(beat)
        if span is not None and d >= 0.75 and (pitch % 12) not in span.pcs:
            near = [p for p in range(pitch - 2, pitch + 3) if p % 12 in span.pcs]
            if near:
                pitch = min(near, key=lambda p: (abs(p - pitch), p))
        while pitch > hi + 2:
            pitch -= 12
        while pitch < lo - 2:
            pitch += 12
        out.append(Note(round(beat, 4), d, pitch, accent=onset == 0, tech=tech, role="lick"))
    return out
