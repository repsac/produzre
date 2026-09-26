"""Bass DNA: the bass player's role in each section of a song.

The bass engine locks to the kick and the chords, which is one bassist. Rock
bass lines differ most in *role*: driving root eighths under a chorus (the
pedal that pushes a hard rock chorus forward), pumping octaves, a gallop,
sustained roots that leave a verse room to breathe, or the kick-locked line
the engine already plays. ``compose_bass_dna`` picks a role per section type
for each song (verse and chorus contrast), and ``bass_bar`` writes one bar
of a role over the harmony, approaching chord changes with neighbor tones.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..rng import stable_seed_int
from .theory import ChordMap, default_groups, nearest_in, scale_pcs

ROLES = ("engine", "kick", "pedal8", "octaves", "gallop", "whole")

_WEIGHTS = {
    "heavy": {
        "verse": {"engine": 25, "kick": 30, "pedal8": 20, "gallop": 10, "whole": 10, "octaves": 5},
        "chorus": {"pedal8": 30, "kick": 25, "engine": 20, "octaves": 10, "gallop": 15},
        "bridge": {"whole": 15, "engine": 35, "kick": 30, "octaves": 10, "pedal8": 10},
        "prechorus": {"pedal8": 30, "kick": 30, "engine": 30, "whole": 10},
    },
    "default": {
        "verse": {"engine": 45, "kick": 25, "whole": 15, "pedal8": 10, "octaves": 5},
        "chorus": {"engine": 35, "kick": 25, "pedal8": 20, "octaves": 15, "gallop": 5},
        "bridge": {"whole": 15, "engine": 55, "kick": 20, "octaves": 10},
        "prechorus": {"engine": 45, "kick": 25, "pedal8": 20, "whole": 10},
    },
}


@dataclass
class BassDNA:
    roles: Dict[str, str] = field(default_factory=dict)
    approach: str = "below"       # below (chromatic) | scale (neighbor toward root) | none
    # Per-song variation inside the roles, so a role is a player's habit and
    # not a template every song shares.
    drop_eighths: Tuple[int, ...] = ()     # pedal/octave eighths left silent
    pop_eighth: Optional[int] = None       # an octave pop in the pedal line
    octave_mask: Tuple[bool, ...] = (False, True) * 4
    gallop_beats: Tuple[int, ...] = (0, 1, 2, 3)
    anticipate: bool = False               # whole notes push the next chord an eighth early
    hold_figure: str = "whole"             # whole | dotted (dotted half + quarter) | halves
    country_fifths: Dict[str, int] = field(default_factory=dict)
    country_figures: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    train_pickups: Dict[str, float] = field(default_factory=dict)
    walk_style: str = "diatonic"
    walk_every: int = 1
    signature: str = ""


def _pick(rng: random.Random, weights: Dict[str, int]) -> str:
    items = sorted(weights.items())
    draw = rng.random() * sum(w for _, w in items)
    for name, w in items:
        draw -= w
        if draw <= 0:
            return name
    return items[-1][0]


def compose_bass_dna(*, seed: int, genre: str) -> BassDNA:
    g = str(genre or "").lower()
    heavy = any(t in g for t in ("hard", "metal", "punk", "grunge"))
    table = _WEIGHTS["heavy" if heavy else "default"]
    rng = random.Random(stable_seed_int("composer.bass", seed, genre))
    dna = BassDNA()
    for sec in ("verse", "chorus", "bridge", "prechorus"):
        role = _pick(rng, table[sec])
        if sec == "chorus" and role == dna.roles.get("verse") and role != "engine":
            role = _pick(rng, {k: v for k, v in table[sec].items() if k != role})
        dna.roles[sec] = role
    if "country" in g:
        dna.roles = {sec: "boom_chick" for sec in dna.roles}
    elif any(t in g for t in ("reggae", "jazz", "swing", "bossa")):
        dna.roles = {sec: "engine" for sec in dna.roles}
    dna.approach = _pick(rng, {"below": 5, "scale": 3, "none": 2})
    dna.drop_eighths = tuple(sorted(rng.sample(range(1, 8), rng.choice([0, 1, 1, 2]))))
    dna.pop_eighth = rng.choice([None, None, 3, 5, 6, 7])
    dna.octave_mask = rng.choice([(False, True) * 4, (False, False, True, False) * 2,
                                  (False, True, False, False) * 2,
                                  (False, False, False, True, False, True, False, True)])
    dna.gallop_beats = rng.choice([(0, 1, 2, 3), (0, 2), (1, 3), (0, 1, 2)])
    dna.anticipate = rng.random() < 0.5
    dna.hold_figure = rng.choice(["whole", "dotted", "halves"])
    if "country" in g:
        player = random.Random(stable_seed_int("composer.bass.country", seed, genre))
        weights = {"boom_chick": 6, "country_walk": 2, "country_octave": 1, "country_train": 1}
        for sec in dna.roles:
            choices = weights if sec != "chorus" else {k: v for k, v in weights.items()
                                                       if k != dna.roles["verse"]}
            dna.roles[sec] = _pick(player, choices)
            dna.country_fifths[sec] = player.choice((-5, 7))
        figures = random.Random(stable_seed_int("composer.bass.country.figures", seed, genre))
        for sec in dna.roles:
            dna.country_figures[sec] = tuple(figures.choice((0, 0, 2, 4)) for _ in range(4))
            dna.train_pickups[sec] = figures.choice((1.5, 2.5, 3.5))
        dna.walk_style = player.choice(("diatonic", "diatonic", "chromatic", "none"))
        dna.walk_every = player.choice((1, 2, 4, 4))
    dna.signature = ", ".join(f"{s}={r}" for s, r in sorted(dna.roles.items())) + \
        f", approach={dna.approach}"
    return dna


def _root_pitch(pc: int, near: int, lo: int = 28, hi: int = 47) -> int:
    return min((p for p in range(lo, hi + 1) if p % 12 == pc),
               key=lambda p: (abs(p - near), p))


def bass_bar(role: str, bar_start: float, bpb: float, chords: ChordMap, *,
             approach: str = "below", near: int = 36,
             last_bar: bool = False, dna: Optional[BassDNA] = None,
             kick: str = "", groups=None, section_type: str = "verse") -> List[Tuple[float, float, int, bool]]:
    """One bar of a bass role: (beat, dur, pitch, accent) tuples.

    ``dna`` carries the song's variations inside the role; ``kick`` is the
    song's kick pattern (sixteenth string) for the "kick" role.
    """
    dna = dna or BassDNA()
    out: List[Tuple[float, float, int, bool]] = []
    span = chords.at(bar_start)
    if span is None:
        return out
    if role == "boom_chick" or role.startswith("country_"):
        gs = tuple(groups) if groups else default_groups(bpb)
        waltz = bpb == 3 and gs == (1.0, 1.0, 1.0)
        ordinary = bpb == 4 and gs == (2.0, 2.0)
        pulses = [0.0] if waltz else [sum(gs[:i]) for i in range(len(gs))]
        if ordinary and role == "country_walk":
            pulses = [0.0, 1.0, 2.0, 3.0]
        bar = int(round(bar_start / bpb))
        fifth = dna.country_fifths.get(section_type, 7)
        figure = dna.country_figures.get(section_type, (0, 0, 0, 0))
        root = _root_pitch(span.root_pc, near)
        for i, off in enumerate(pulses):
            t = bar_start + off
            span = chords.at(t)
            root = _root_pitch(span.root_pc, near)
            phase = bar % 2 if waltz else i % 2
            interval = fifth if phase else 0
            if role == "country_octave" and not waltz and i % 2 and (bar+figure[0]) % 3:
                interval = 12
            if ordinary and role == "country_walk":
                third = 4 if (span.root_pc+4)%12 in span.pcs else 3
                paths = ((0, third, fifth, 12), (0, fifth, third, fifth), (0, 12, fifth, third),
                         (0, third, 12, fifth), (0, fifth, 12, third))
                interval = paths[figure[bar % 4]][i]
            pitch = nearest_in(((span.root_pc+interval)%12,), root+interval, 28, 52)
            end = min(span.end, bar_start + (pulses[i+1] if i+1 < len(pulses) else bpb))
            out.append((t, min(1.4, end-t-.05), pitch, True))
        nxt = chords.at(bar_start + bpb) if bar_start + bpb < chords.total else None
        walk = (ordinary and nxt and not last_bar and dna.walk_style != "none"
                and nxt.root_pc != span.root_pc and (bar+1) % dna.walk_every == 0)
        if walk:
            target = _root_pitch(nxt.root_pc, near)
            scale = scale_pcs(chords.key, chords.mode)
            lead = target - 1
            if dna.walk_style == "diatonic":
                while lead % 12 not in scale:
                    lead -= 1
            t = bar_start + bpb - .5
            out = [(a, min(d, t-a-.03), p, acc) for a, d, p, acc in out if a < t]
            out.append((t, .22 if dna.walk_style == "chromatic" else .4, lead, False))
        elif ordinary and role == "country_train" and not last_bar:
            t = bar_start + dna.train_pickups.get(section_type, 1.5)
            out = [(a, min(d, t-a-.03) if a < t else d, p, acc) for a, d, p, acc in out]
            sp = chords.at(t)
            out.append((t, .35, _root_pitch(sp.root_pc, near), False))
        return sorted(out)
    if role == "whole":
        t = bar_start
        while t < bar_start + bpb - 1e-6:
            s = chords.at(t)
            end = min(s.end, bar_start + bpb)
            push = dna.anticipate and end < chords.total - 1e-6 and not last_bar and \
                end - t >= 1.5
            hold_end = end - 0.5 if push else end
            root = _root_pitch(s.root_pc, near)
            span_len = hold_end - t
            if dna.hold_figure == "dotted" and span_len >= 3.0:
                out.append((t, span_len * 0.75 - 0.05, root, True))
                out.append((t + span_len * 0.75, span_len * 0.25 - 0.05, root + 12, False))
            elif dna.hold_figure == "halves" and span_len >= 2.0:
                half = span_len / 2.0
                out.append((t, half - 0.05, root, True))
                out.append((t + half, half - 0.05, root, False))
            else:
                out.append((t, span_len - 0.05, root, True))
            if push:
                nxt = chords.at(end + 1e-3)
                out.append((hold_end, 0.45, _root_pitch(nxt.root_pc, near), True))
            t = end
        return out
    eighths = int(bpb * 2)
    if role == "kick":
        steps = [(i * 0.25, False) for i, c in enumerate(kick[: int(round(bpb * 4))]) if c == "x"]
        if not steps:
            steps = [(0.0, False)]
    elif role == "pedal8":
        steps = [(k * 0.5, k == dna.pop_eighth) for k in range(eighths)
                 if k not in dna.drop_eighths]
    elif role == "octaves":
        mask = (dna.octave_mask * 2)[:eighths]
        steps = [(k * 0.5, mask[k]) for k in range(eighths) if k not in dna.drop_eighths[:1]]
    elif role == "gallop":
        steps = [(b + o, False) for b in range(int(bpb))
                 for o in ((0.0, 0.5, 0.75) if b in dna.gallop_beats else (0.0,))]
    else:
        steps = None
    if steps is None:
        return out
    for off, up in steps:
        t = bar_start + off
        s = chords.at(t)
        root = _root_pitch(s.root_pc, near)
        pitch = root + 12 if up else root
        nxt_off = next((o for o, _ in steps if o > off + 1e-6), bpb)
        dur = max(0.12, min(0.95, nxt_off - off) - 0.05)
        out.append((t, dur, pitch, abs(off % 2) < 1e-6))
    # Approach the next chord with a neighbor on the last eighth.
    nxt = chords.at(bar_start + bpb + 1e-3) if bar_start + bpb < chords.total else None
    if approach != "none" and nxt is not None and nxt.root_pc != chords.at(bar_start + bpb - 0.25).root_pc \
            and out and not last_bar:
        target = _root_pitch(nxt.root_pc, near)
        lead_in = target - 1
        if approach == "scale":
            scale = scale_pcs(chords.key, chords.mode)
            current = _root_pitch(chords.at(bar_start + bpb - 0.25).root_pc, near)
            direction = 1 if current > target else -1
            lead_in = target + direction
            while lead_in % 12 not in scale:
                lead_in += direction
        t, d, _, a = out[-1]
        if t >= bar_start + bpb - 0.5 - 1e-6:
            out[-1] = (t, min(d, 0.45), lead_in, False)
    return out
