"""Song DNA: the small set of ideas a song is built from.

Human songs are economical. A handful of ideas (a hook, a verse idea, a
contrasting bridge idea, a few signature licks) are stated, repeated, and
developed. Everything the composer writes later is derived from this DNA,
which is why the result sounds like *one song* instead of a stream of
unrelated bars.

Ideas are chosen by generate-and-score: many candidates are built from an
idiomatic rhythm vocabulary and a constrained contour walk, then ranked by a
memorability score drawn from music-cognition findings on catchy melodies
(Jakubowski et al. 2017; Huron 2006; Meyer's gap-fill): a distinctive
rhythm with internal repetition, one signature leap filled in by contrary
steps, an arch-like contour with a single peak, few distinct pitches, and a
moderate (not generic, not bizarre) surprise level under the human prior.
The seed only chooses among the best-scoring candidates.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from .cells import Cell, CellNote, cell_from, fit_length, invert, augment
from .licks import Lick, choose_lick_bank
from .listener import prior_information

# Rhythm vocabulary for one 4/4 bar, as 16-step patterns: ``x`` attacks a
# note, ``.`` holds it, ``-`` is silence. Each figure is an idiomatic
# melodic rhythm: anticipations (an attack on an off-sixteenth held across
# the beat), dotted figures, repeated-note pickups, and breaths at the end.
_PATTERNS: Dict[str, List[str]] = {
    "anthem": [
        "x...x.x.x.......",   # quarter, eighths, long
        "x.x.x...x.......",
        "x..x..x.x.......",   # dotted-eighth push
        "x...x...x.x.x...",
        "x.x.x.x.x...----",   # run and breathe
        "x.....x.x.......",   # long pickup to the arrival
        "x..x..x...x.----",
        "--x.x.x.x.......",   # pickup into beat 3
    ],
    "driving": [
        "x.x.x.x.x.x.x...",
        "x.x.x.x.x...x...",
        "xx.x.x.xx.x.x...",
        "x.xxx.x.x.x.----",
        "x.x.x.x.x.x.----",
        "xxx.x.x.x.......",
    ],
    "syncopated": [
        "x..x..x...x.....",   # 3+3+2 clave feel
        "--x..x..x.......",
        "x.x..x..x..x....",
        "x..x.x...x......",
        "-x.x..x.x.......",
        "x..x..x.x.x.----",
        "--xx..x.x..x....",
        "x.-x.x..x.......",
    ],
    "conversational": [
        "--x.x.x.x.x.....",
        "x.xxx.x.x.......",
        "---x.x.x.x.x....",
        "x.x.x.xxx.......",
        "--x.x.xxx.x.----",
        "x.x.x.x...x.x...",
    ],
    "sparse": [
        "x.......x.......",
        "x.....x.x.......",
        "x...........x...",
        "x.......x...x...",
        "--x.......x.....",
    ],
}


def _parse_pattern(pattern: str) -> Tuple[float, ...]:
    """16-step pattern -> signed durations in beats (negative = rest)."""
    out: List[float] = []
    step = 0.25
    for ch in pattern:
        if ch == "x":
            out.append(step)
        elif ch == ".":
            if out:
                out[-1] += step if out[-1] > 0 else -step
            else:
                out.append(-step)
        else:  # rest
            if out and out[-1] < 0:
                out[-1] -= step
            else:
                out.append(-step)
    return tuple(round(d, 4) for d in out)


_RHYTHMS: Dict[str, List[Tuple[float, ...]]] = {
    fam: [_parse_pattern(p) for p in pats] for fam, pats in _PATTERNS.items()
}

_GENRE_WEIGHTS: List[Tuple[Tuple[str, ...], Dict[str, float]]] = [
    (("metal", "punk", "thrash", "hard_rock", "grunge"),
     {"driving": 0.45, "syncopated": 0.3, "anthem": 0.25}),
    (("funk", "soul", "rnb", "hip_hop", "disco", "reggae", "ska"),
     {"syncopated": 0.6, "conversational": 0.25, "driving": 0.15}),
    (("jazz", "swing", "bebop", "bossa", "latin"),
     {"conversational": 0.45, "syncopated": 0.4, "sparse": 0.15}),
    (("ambient", "cinematic", "ballad", "post-rock", "folk", "classical"),
     {"sparse": 0.4, "anthem": 0.4, "conversational": 0.2}),
    (("blues", "country", "rock", "pop", "gospel", "emo", "new_wave"),
     {"anthem": 0.4, "syncopated": 0.25, "conversational": 0.2, "driving": 0.15}),
]
_DEFAULT_WEIGHTS = {"anthem": 0.35, "syncopated": 0.25, "conversational": 0.25,
                    "driving": 0.1, "sparse": 0.05}


def genre_weights(genre: str) -> Dict[str, float]:
    g = str(genre or "").lower().replace(" ", "_")
    for tokens, weights in _GENRE_WEIGHTS:
        if any(t in g for t in tokens):
            return weights
    return _DEFAULT_WEIGHTS


def fit_rhythm(figure: Sequence[float], beats_per_bar: float) -> Tuple[float, ...]:
    """Adapt a 4/4 figure to another bar length without leaving its grid."""
    remaining = float(beats_per_bar)
    out: List[float] = []
    for d in figure:
        if remaining <= 1e-9:
            break
        mag = min(abs(d), remaining)
        out.append(mag if d > 0 else -mag)
        remaining -= mag
    if remaining > 1e-9:
        if out and out[-1] > 0:
            out[-1] += remaining
        else:
            out.append(remaining)
    return tuple(out)


# Rhythm cells per beat group (quarter-note beats; negative = rest). Odd
# meters are phrased by their groups: 7/8 as 2+2+3 eighths, 5/4 as 3+2
# quarters, 6/8 as two dotted quarters, so an idea is assembled group by
# group instead of truncating a 4/4 figure.
_GROUP_CELLS: Dict[float, Dict[str, List[Tuple[float, ...]]]] = {
    1.0: {"driving": [(0.5, 0.5), (0.25, 0.25, 0.5), (0.5, 0.25, 0.25)],
          "anthem": [(1.0,), (0.5, 0.5)],
          "syncopated": [(0.75, 0.25), (-0.5, 0.5), (0.25, 0.75)],
          "conversational": [(0.5, 0.5), (-0.5, 0.5)],
          "sparse": [(1.0,)]},
    1.5: {"driving": [(0.5, 0.5, 0.5), (0.5, 0.25, 0.25, 0.5)],
          "anthem": [(1.0, 0.5), (1.5,)],
          "syncopated": [(0.5, 1.0), (-0.5, 0.5, 0.5), (0.75, 0.75)],
          "conversational": [(0.5, 0.5, 0.5), (-0.5, 1.0)],
          "sparse": [(1.5,)]},
    2.0: {"driving": [(0.5, 0.5, 0.5, 0.5), (1.0, 0.5, 0.5)],
          "anthem": [(1.0, 1.0), (1.5, 0.5), (2.0,)],
          "syncopated": [(0.75, 0.75, 0.5), (-0.5, 1.0, 0.5)],
          "conversational": [(0.5, 0.5, 1.0), (-1.0, 0.5, 0.5)],
          "sparse": [(2.0,)]},
    3.0: {"driving": [(0.5,) * 6, (1.0, 0.5, 0.5, 1.0)],
          "anthem": [(1.0, 1.0, 1.0), (2.0, 1.0), (1.5, 1.5)],
          "syncopated": [(0.75, 0.75, 0.5, 1.0), (-0.5, 1.0, 1.5)],
          "conversational": [(0.5, 0.5, 1.0, 1.0), (-1.0, 1.0, 1.0)],
          "sparse": [(3.0,), (2.0, 1.0)]},
}


def uses_group_rhythm(beats_per_bar: float, groups: Optional[Sequence[float]]) -> bool:
    """Everything but plain 4/4 builds its ideas from the meter's groups."""
    if not groups:
        return False
    return not (abs(beats_per_bar - 4.0) < 1e-6 and tuple(groups) == (2.0, 2.0))


def group_figure(rng: random.Random, groups: Sequence[float], family: str) -> Tuple[float, ...]:
    """One bar's rhythm, a cell per group; the last group may hold."""
    out: List[float] = []
    for i, g in enumerate(groups):
        table = _GROUP_CELLS.get(round(g * 2) / 2)
        if i == len(groups) - 1 and rng.random() < 0.5:
            out.append(g)  # a held arrival at the end of the bar
            continue
        if table is None:
            n = int(round(g / 0.5))
            out.extend([0.5] * n)
            continue
        cells = table.get(family) or table["anthem"]
        out.extend(rng.choice(cells))
    return tuple(out)


def _rhythm_to_cell_parts(figure: Sequence[float]):
    durs = [abs(d) for d in figure]
    rests = [d < 0 for d in figure]
    return durs, rests


# ---------------------------------------------------------------------------
# Memorability score
# ---------------------------------------------------------------------------

def rhythm_score(cell: Cell) -> float:
    """Catchiness of a cell's rhythm alone."""
    notes = cell.notes
    n = len(notes)
    if n < 3 or n > 8:
        return -10.0
    score = 0.0
    durs = [x.dur for x in notes]
    # Syncopation: an off-beat attack that sustains through the next beat.
    if any(abs(x.onset - round(x.onset)) > 1e-6 and x.onset + x.dur > int(x.onset) + 1 + 1e-6
           for x in notes):
        score += 1.0
    # Internal rhythmic repetition (two identical duration pairs).
    pairs = [tuple(durs[i:i + 2]) for i in range(n - 1)]
    if len(pairs) != len(set(pairs)):
        score += 0.7
    # A long final note (or a breath) gives the idea an end.
    if durs[-1] >= 1.0:
        score += 0.6
    elif notes[-1].onset + durs[-1] < cell.length - 0.4:
        score += 0.2
    if notes[0].onset > 0:
        score += 0.25  # a pickup entry is characterful
    # Enough notes to carry a melodic idea, few enough to sing back.
    score += {3: -0.6, 4: 0.1, 5: 0.5, 6: 0.5, 7: 0.3}.get(n, -0.2)
    # Silence at the head of a bar: a short pickup breathes; a full beat or
    # more of rest leaves the downbeat empty and the idea feels late.
    if notes[0].onset >= 1.0:
        score -= 0.5
    return score


def contour_score(pitches: Sequence[int]) -> float:
    """Catchiness of a pitch line (semitones), after harmony fitting."""
    n = len(pitches)
    if n < 3:
        return -5.0
    ivs = [b - a for a, b in zip(pitches, pitches[1:])]
    score = 0.0
    leaps = [i for i, iv in enumerate(ivs) if abs(iv) >= 5]
    if len(leaps) == 1:
        score += 1.0
        i = leaps[0]
        if i + 1 < len(ivs) and ivs[i + 1] != 0 and (ivs[i + 1] > 0) != (ivs[i] > 0) \
                and abs(ivs[i + 1]) <= 3:
            score += 0.6  # gap-fill
    elif len(leaps) == 2:
        score += 0.2
    elif not leaps:
        score -= 0.4
    else:
        score -= 1.0
    repeats = sum(1 for iv in ivs if iv == 0)
    score += {0: 0.0, 1: 0.5, 2: 0.2}.get(repeats, -0.9)
    span = max(pitches) - min(pitches)
    score += 0.5 if 5 <= span <= 10 else (-1.0 if span > 12 else -0.3)
    peak = pitches.index(max(pitches))
    if 0 < peak < n - 1:
        score += 0.4
    distinct = len(set(pitches))
    score += 0.4 if 3 <= distinct <= 5 else (-0.4 if distinct < 3 else 0.0)
    ic = prior_information(pitches)
    score -= 0.6 * abs(ic - 3.4)
    return score


def hook_score(cell: Cell, beats_per_bar: float = 4.0) -> float:
    """Abstract catchiness (rhythm + contour on a major-scale ladder)."""
    ladder = (0, 2, 4, 5, 7, 9, 11)
    pitches = [60 + 12 * (h // 7) + ladder[h % 7] for h in cell.contour()]
    return rhythm_score(cell) + contour_score(pitches)


def _walk(rng: random.Random, n: int) -> List[int]:
    """Constrained contour walk: mostly steps, occasional leaps with recovery."""
    steps = [0]
    leap_dir = 0
    for _ in range(n - 1):
        if leap_dir:
            s = -leap_dir * rng.choice((1, 1, 2))
            leap_dir = 0
        else:
            r = rng.random()
            if r < 0.55:
                s = rng.choice((-1, 1, -2, 2, -1, 1))
            elif r < 0.75:
                s = 0
            else:
                s = rng.choice((3, 4, -3, -4, 3))
                leap_dir = 1 if s > 0 else -1
        steps.append(s)
    return steps


def compose_idea(
    rng: random.Random,
    *,
    genre: str,
    beats_per_bar: float,
    families: Optional[Dict[str, float]] = None,
    pool: int = 160,
    top: int = 6,
    min_notes: int = 3,
    name: str = "idea",
    fit=None,
    groups: Optional[Sequence[float]] = None,
) -> Cell:
    """Generate ``pool`` candidates and pick among the ``top`` best.

    ``fit`` is an optional callable ``cell -> (pitches, cost)`` that realizes
    a candidate over real harmony. When given, the best abstract candidates
    are re-ranked by how they actually sound over those chords: an idea
    whose signature leap the harmony would flatten loses to one that
    survives.
    """
    weights = families or genre_weights(genre)
    fams = sorted(weights)
    candidates: List[Tuple[float, int, Cell]] = []
    for k in range(pool):
        draw = rng.random() * sum(weights.values())
        fam = fams[-1]
        for f in fams:
            draw -= weights[f]
            if draw <= 0:
                fam = f
                break
        if uses_group_rhythm(beats_per_bar, groups):
            figure = group_figure(rng, groups, fam)
        else:
            figure = fit_rhythm(rng.choice(_RHYTHMS[fam]), beats_per_bar)
        durs, rests = _rhythm_to_cell_parts(figure)
        sounded = sum(1 for r in rests if not r)
        if sounded < min_notes:
            continue
        steps = _walk(rng, len(durs))
        cell = cell_from(durs, steps, rests=rests, length=beats_per_bar, name=name)
        # Rests shift which steps belong to sounded notes; re-derive so the
        # first sounded note enters on step 0.
        if cell.notes and cell.notes[0].step != 0:
            cell = Cell((CellNote(cell.notes[0].onset, cell.notes[0].dur, 0),) + cell.notes[1:],
                        cell.length, name)
        candidates.append((hook_score(cell, beats_per_bar), k, cell))
    candidates.sort(key=lambda t: (-t[0], t[1]))
    if fit is not None and candidates:
        rescored = []
        for abstract, k, cell in candidates[:max(top * 4, 24)]:
            pitches, cost = fit(cell)
            if len(pitches) < min_notes:
                continue
            rescored.append((rhythm_score(cell) + contour_score(pitches) - 0.8 * cost, k, cell))
        if rescored:
            candidates = sorted(rescored, key=lambda t: (-t[0], t[1]))
    best = candidates[:max(1, top if fit is None else max(2, top // 2))]
    return rng.choice(best)[2]


@dataclass
class SongDNA:
    """The ideas one song is built from (all deterministic from the seed)."""

    hook: Cell
    hook_answer: Cell
    verse: Cell
    bridge: Cell
    licks: List[Lick] = field(default_factory=list)
    signature: str = ""
    authored: bool = False  # hook comes from a user melody theme: never reshape it


def _answer(hook: Cell, rng: random.Random, fit=None) -> Cell:
    """The second bar of the hook line: it answers the call.

    Candidates keep the hook's opening (so the line is one thought) and
    change what follows: the same rhythm with a new ending, or the head
    followed by a held note (the classic call-and-sustain). A held answer
    gives the line the rhythmic contrast a bar-long loop lacks, so it wins
    ties.
    """
    from .cells import concat, fragment, vary_tail

    half = hook.length / 2.0
    head = fragment(hook, half)
    options = [vary_tail(hook, rng, keep=0.5, end_long=True)]
    if len(head.notes) >= 2:
        hold = Cell((CellNote(0.0, half, rng.choice((-2, -1, 1, 2))),), half)
        options.insert(0, concat(head, hold))
    if len(options) == 1 or fit is None:
        return options[0].with_name("hook_answer")
    best = max(
        enumerate(options),
        key=lambda kc: (contour_score(fit(kc[1])[0] or [0, 0, 0]) - 0.8 * fit(kc[1])[1]
                        + (0.8 if kc[0] == 0 else 0.0), -kc[0]),
    )
    return best[1].with_name("hook_answer")


def compose_dna(
    *,
    seed: int,
    genre: str,
    key: str,
    mode: str,
    beats_per_bar: float,
    melody_theme=None,
    hook_fit=None,
    verse_fit=None,
    groups: Optional[Sequence[float]] = None,
) -> SongDNA:
    """Compose the song's ideas from one dedicated RNG stream.

    ``melody_theme`` (an authored or auto-composed ``Theme`` with role
    melody) seeds the hook, so user material stays the song's identity.
    """
    rng = random.Random(stable_seed_int("composer.dna", seed, genre, key, mode, beats_per_bar))
    hook: Optional[Cell] = None
    answer: Optional[Cell] = None
    if melody_theme is not None:
        hook, answer = _cells_from_theme(melody_theme, beats_per_bar)
    if hook is None:
        hook_weights = dict(genre_weights(genre))
        for fam, boost in (("anthem", 0.25), ("syncopated", 0.15)):
            hook_weights[fam] = hook_weights.get(fam, 0.0) + boost
        hook = compose_idea(rng, genre=genre, beats_per_bar=beats_per_bar, groups=groups, name="hook",
                            families=hook_weights, fit=hook_fit)
    if answer is None:
        answer = _answer(hook, rng, hook_fit)
    verse_weights = dict(genre_weights(genre))
    verse_weights["conversational"] = verse_weights.get("conversational", 0.0) + 0.4
    verse = compose_idea(rng, genre=genre, beats_per_bar=beats_per_bar, groups=groups,
                         families=verse_weights, min_notes=4, name="verse", fit=verse_fit)
    for _ in range(6):
        # Verse and chorus must not share a rhythm: contrast is what makes
        # the chorus arrive.
        if verse.durations != hook.durations:
            break
        verse = compose_idea(rng, genre=genre, beats_per_bar=beats_per_bar, groups=groups,
                             families=verse_weights, min_notes=4, name="verse", fit=verse_fit)
    # Bridge: contrast by inversion and a slower surface rhythm.
    bridge_seed = compose_idea(rng, genre=genre, beats_per_bar=beats_per_bar / 2.0,
                               families={"anthem": 0.5, "sparse": 0.5}, min_notes=2,
                               name="bridge")
    bridge = fit_length(augment(invert(bridge_seed), 2.0), beats_per_bar).with_name("bridge")
    if len(bridge.notes) < 2:
        bridge = fit_length(invert(hook), beats_per_bar).with_name("bridge")
    licks = choose_lick_bank(rng, genre=genre, count=3)
    sig = "|".join(
        f"{c.name}:" + ",".join(f"{n.onset:g}/{n.dur:g}/{n.step}" for n in c.notes)
        for c in (hook, answer, verse, bridge)
    ) + "|licks:" + ",".join(l.name for l in licks)
    return SongDNA(hook, answer, verse, bridge, licks, sig, authored=melody_theme is not None
                   and any(n.degree is not None for n in hook.notes))


def _cells_from_theme(theme, beats_per_bar: float):
    """Split a melody theme into hook and answer cells (degrees pinned)."""
    events = [e for e in theme.events if not e.is_rest]
    if len(events) < 2:
        return None, None
    notes = []
    prev = None
    for e in events:
        idx = (e.degree - 1) + 7 * e.octave
        step = 0 if prev is None else idx - prev
        notes.append(CellNote(float(e.offset_beats), float(e.duration_beats), step,
                              accent=bool(e.accent), degree=idx, alter=int(e.accidental or 0)))
        prev = idx
    length = float(theme.length_beats)
    if length > beats_per_bar * 1.5:
        half = beats_per_bar * max(1, round(length / beats_per_bar) // 2)
        head = [n for n in notes if n.onset < half - 1e-6]
        tail = [CellNote(round(n.onset - half, 4), n.dur, n.step, n.accent, n.tech, n.degree,
                         n.alter) for n in notes if n.onset >= half - 1e-6]
        if len(head) >= 2 and len(tail) >= 1:
            return (Cell(tuple(head), half, "hook"),
                    Cell(tuple(tail), max(length - half, beats_per_bar), "hook_answer"))
    return Cell(tuple(notes), max(length, beats_per_bar), "hook"), None
