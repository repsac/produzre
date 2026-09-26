"""Rhythm-guitar composition: signature comp riffs with real technique.

A rhythm part with character is not a strum grid. The parts people ask
"how did he play that?" about mix several techniques inside one figure:
dead-note chucks between chords, single-note bass-string fills that walk
into the next chord, sus4 hammer-ons inside a held chord, chords that slide
in from a fret below, boogie dyads, partial-chord stabs, palm-muted
gallops. And they are arranged: the verse figure differs from the chorus
figure, the bar before a chorus stops dead, phrase ends walk up into the
next phrase.

Riffs are written as step strings over one 4/4 bar (16 steps, or 12 for
shuffle and swing families). Each character starts an event, ``-`` holds
it, ``.`` is silence:

====  ==========================================================
X x   accented / plain full strum (direction follows the grid)
u     light upstrum on the top strings
m     dead-note chuck (muted strings, percussive)
p P   palm-muted chug / open accented power chord
S     short partial-chord stab (top strings)
r f   single bass-string note: root / fifth
w     walking approach note into the next chord's root
d     double-stop on the top two strings
q Q y boogie dyads: root+5th, root+6th, root+b7
h     sus4 chord that hammers down to the third
a     arpeggio: the next string of the chord shape, let ring
/     full chord sliding in from a fret below
====  ==========================================================

A song draws its comp DNA once (a riff per energy tier, chosen for
character and contrast); every section is arranged from it. The engine
performs the events with its own playable chord shapes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from .theory import ChordMap

_EVENT_CHARS = set("XxumpPSrfwdqQyha/")
# Technique classes used to score how much character a riff carries.
_TECHNIQUE_CLASS = {
    "m": "chuck", "r": "single", "f": "single", "w": "walk", "d": "dyad", "h": "sus",
    "/": "slide", "a": "arp", "q": "boogie", "Q": "boogie", "y": "boogie", "S": "stab",
    "p": "chug", "u": "up",
}


@dataclass(frozen=True)
class CompRiff:
    name: str
    families: Tuple[str, ...]
    tier: str          # "low" (verse), "build", "drive" (chorus), "contrast", "stab"
    steps: str         # 16 (straight) or 12 (triplet) characters
    ring: float = 1.0  # longest a strum may ring, in beats

    @property
    def subdivision(self) -> int:
        return len(self.steps) // 4

    def character(self) -> float:
        """How much a riff stands out: distinct techniques plus syncopation."""
        classes = {_TECHNIQUE_CLASS[c] for c in self.steps if c in _TECHNIQUE_CLASS}
        sub = self.subdivision
        offbeat_accents = sum(1 for i, c in enumerate(self.steps)
                              if c in "XPS/h" and i % sub != 0)
        return len(classes) + 0.5 * min(offbeat_accents, 3)


def _R(name, families, tier, steps, ring=1.0):
    assert len(steps) in (12, 16), (name, len(steps))
    return CompRiff(name, tuple(families.split()), tier, steps, ring)


RIFFS: Tuple[CompRiff, ...] = (
    # --- rock -------------------------------------------------------------
    _R("chuck_drive", "rock pop punk", "drive", "X-mxX-mxX-mxX-mx", 0.5),
    _R("keef_sus", "rock blues soul", "drive", "X-h-x-u-X-h-x-u-", 0.75),
    _R("hits_and_walk", "rock blues", "drive", "X---..X-r.w.X---", 1.5),
    _R("slide_push", "rock pop", "drive", "/---x-u-.uX-u-mx", 1.0),
    _R("anthem_eighths", "rock pop emo", "drive", "X-x-x-x-X-x-xux-", 0.5),
    _R("palm_verse", "rock punk metal", "low", "p-p-p-p-p-p-p-p-", 0.4),
    _R("palm_push", "rock pop emo", "low", "p-p-p-.xp-p-p-.x", 0.4),
    _R("bass_and_chuck", "rock blues country", "low", "r-m-X---f-m-X---", 1.0),
    _R("dyad_answer", "rock soul", "low", "X-----d-d-.dX---", 1.5),
    _R("eighth_build", "rock pop punk emo", "build", "x-x-x-x-x-x-xxxx", 0.4),
    _R("stop_and_ring", "rock pop metal emo cinematic", "contrast", "X---------------", 4.0),
    _R("half_notes_slide", "rock pop", "contrast", "/-------X-------", 2.0),
    _R("dotted_stabs", "rock pop metal", "stab", "S-----S-----S---", 0.3),
    # --- metal ------------------------------------------------------------
    _R("gallop", "metal", "low", "p-ppp-ppp-ppp-pp", 0.3),
    _R("chug_sixteenths", "metal", "build", "pppppppppppppppp", 0.2),
    _R("stab_chug", "metal", "drive", "P--pppP--pppP-pp", 0.75),
    _R("slide_chug", "metal", "drive", "/--pp.ppP--pp.pp", 0.75),
    _R("breakdown_hits", "metal", "stab", "P..P..P...P..P..", 0.3),
    _R("pedal_riff", "metal punk", "low", "pp.pp.P-pp.pp.P-", 0.5),
    # --- pop / acoustic strum ---------------------------------------------
    _R("ddu_udu", "pop folk country rock", "drive", "x---x-u---u-x-u-", 0.75),
    _R("offbeat_pop", "pop soul emo", "low", "X---..x-..x-..x-", 0.5),
    _R("arp_eighths", "pop emo cinematic folk", "low", "a-a-a-a-a-a-a-a-", 2.0),
    _R("root_arp", "pop cinematic folk country", "low", "r-a-a-a-r-a-a-a-", 2.0),
    _R("pop_sus_lift", "pop rock soul", "build", "x-h-x-u-x-h-xuxu", 0.5),
    _R("three_three_two", "pop latin rock", "drive", "X--x--X-x-X--x--", 0.75),
    # --- funk / disco / r&b ------------------------------------------------
    _R("nile_sixteenths", "funk disco rnb", "drive", "xmxmXmxmxmxmXmxu", 0.2),
    _R("chank_space", "funk rnb soul", "low", "..X.mmX..mX.mmx.", 0.2),
    _R("single_note_line", "funk rnb", "low", "r.rmw.m.r.rmX.m.", 0.3),
    _R("dyad_funk", "funk soul rnb", "drive", "d.dmd.m.d.dmX.m.", 0.25),
    _R("funk_build", "funk disco rnb", "build", "xmxmxmxmxmxmxxxx", 0.2),
    _R("funk_stabs", "funk disco soul", "stab", "....X.......X..m", 0.2),
    # --- reggae / ska ------------------------------------------------------
    _R("one_drop_skank", "reggae", "low", "....S-..mm..S-..", 0.3),
    _R("offbeat_skank", "reggae ska", "drive", "..S-..S-..S-..S-", 0.3),
    _R("double_skank", "reggae ska", "build", "..SS..SS..SS..SS", 0.2),
    _R("ska_upstroke", "ska", "low", "..u...u...u...u.", 0.3),
    # --- soul / gospel ------------------------------------------------------
    _R("soul_answers", "soul gospel rnb", "drive", "..X.h...X-..d.d.", 0.75),
    _R("gospel_push", "gospel soul", "build", "X--x--x-X-x-xxx-", 0.5),
    # --- country / folk ------------------------------------------------------
    _R("boom_chuck", "country folk", "low", "r---x-u-f---x-u-", 0.5),
    _R("train_beat", "country folk", "build", "x.xxx.xxx.xxx.xx", 0.25),
    _R("walk_up_chuck", "country folk", "drive", "r---X-u-f-w-X-u-", 0.5),
    # --- latin -------------------------------------------------------------
    _R("clave_hits", "latin", "drive", "X--X--X---X-X---", 0.5),
    _R("montuno_arp", "latin", "low", "a.a.aa.a.aa.a.a.", 0.4),
    # --- electronic / new wave ----------------------------------------------
    _R("pulse_mutes", "electronic new_wave", "low", "p.p.p.p.p.p.p.p.", 0.2),
    _R("octave_pulse", "electronic new_wave", "drive", "X.xxX.xxX.xxX.xx", 0.25),
    _R("offbeat_pulse", "electronic new_wave pop", "build", "..x-..x-..x-..x-", 0.3),
    # --- shuffle families (12 steps: triplet eighths) -------------------------
    _R("boogie", "blues rock country", "low", "q-Qq-Qq-yq-Q", 0.4),
    _R("chuck_berry", "blues rock country", "drive", "q-qQ-Qy-yQ-Q", 0.4),
    _R("boogie_stop", "blues rock", "drive", "X-mX-m...q-Q", 0.6),
    _R("chuck_shuffle", "blues soul", "low", "r-mX-mf-mX-m", 0.4),
    _R("slow_blues_triplets", "blues soul gospel", "build", "x-xx-xx-x/--", 0.6),
    _R("palm_shuffle", "blues jazz", "low", "p-pp-pp-pp-p", 0.4),
    _R("shuffle_strum", "blues rock", "build", "x-xx-xx-xx-x", 0.5),
    _R("shuffle_hits", "blues", "stab", "X.....X..X..", 0.3),
    _R("blues_ring", "blues jazz soul", "contrast", "X-----/-----", 2.0),
    _R("freddie_green", "jazz", "low", "S..S..S..S..", 0.5),
    _R("charleston", "jazz latin", "drive", "X....S......", 0.8),
    _R("swing_comp", "jazz", "build", "S..S.xS..S.x", 0.5),
)

_FAMILY_OF = (
    ("metal", "metal"), ("thrash", "metal"), ("punk", "punk"), ("grunge", "rock"),
    ("emo", "emo"), ("funk", "funk"), ("disco", "disco"), ("rnb", "rnb"), ("r&b", "rnb"),
    ("hip_hop", "funk"), ("soul", "soul"), ("gospel", "gospel"), ("reggae", "reggae"),
    ("ska", "ska"), ("blues", "blues"), ("jazz", "jazz"), ("swing", "jazz"),
    ("bossa", "latin"), ("latin", "latin"), ("country", "country"), ("folk", "folk"),
    ("classical", "cinematic"), ("cinematic", "cinematic"), ("ambient", "cinematic"),
    ("post-rock", "cinematic"), ("new_wave", "new_wave"), ("electronic", "electronic"),
    ("techno", "electronic"), ("dance", "electronic"), ("pop", "pop"), ("rock", "rock"),
)

# Section type -> (tier, fallback tiers)
_SECTION_TIERS = {
    "intro": ("drive", "contrast"),
    "verse": ("low", "stab"),
    "prechorus": ("build", "low"),
    "chorus": ("drive", "build"),
    "bridge": ("contrast", "stab"),
    "solo": ("build", "low"),
    "breakdown": ("stab", "contrast"),
    "outro": ("drive", "contrast"),
}
_ALIASES = {"pre-chorus": "prechorus", "pre_chorus": "prechorus", "hook": "chorus",
            "interlude": "bridge", "lead": "solo"}


def comp_family(genre: str) -> str:
    g = str(genre or "").lower().replace(" ", "_").replace("-", "_")
    for token, fam in _FAMILY_OF:
        if token.replace("-", "_") in g:
            return fam
    return "rock"


@dataclass
class CompDNA:
    family: str
    riffs: Dict[str, CompRiff] = field(default_factory=dict)  # tier -> riff
    alternates: Dict[str, CompRiff] = field(default_factory=dict)

    def signature(self) -> str:
        return ",".join(f"{t}:{r.name}" for t, r in sorted(self.riffs.items()))


def compose_comp_dna(*, seed: int, genre: str, key: str, mode: str, shuffle: bool) -> CompDNA:
    """Choose one riff per tier: characterful, and different from each other."""
    fam = comp_family(genre)
    rng = random.Random(stable_seed_int("composer.comp", seed, genre, key, mode))
    wanted_len = 12 if shuffle else 16
    dna = CompDNA(fam)
    used: set = set()
    for tier in ("drive", "low", "build", "contrast", "stab"):
        pool = [r for r in RIFFS if fam in r.families and r.tier == tier
                and len(r.steps) == wanted_len]
        if not pool:
            pool = [r for r in RIFFS if "rock" in r.families and r.tier == tier
                    and len(r.steps) == wanted_len]
        if not pool:
            pool = [r for r in RIFFS if r.tier == tier and len(r.steps) == wanted_len]
        if not pool:
            continue
        # Character-weighted choice over the whole pool, then a personal
        # variation: two songs in one genre start from shared vocabulary
        # but never play the same figure.
        pool = sorted(pool, key=lambda r: (-r.character(), r.name))
        fresh = [r for r in pool if r.name not in used] or pool
        weights = [1.0 + r.character() for r in fresh]
        pick = rng.choices(fresh, weights=weights, k=1)[0]
        used.add(pick.name)
        dna.riffs[tier] = mutate_riff(pick, rng, fam)
        rest = [r for r in fresh if r is not pick]
        if rest:
            dna.alternates[tier] = mutate_riff(rng.choice(rest), rng, fam)
    return dna


# Families where a sus hammer or a slid chord belongs in the vocabulary.
_SUS_FAMILIES = ("rock", "pop", "blues", "soul", "gospel", "folk", "country", "emo")
_SLIDE_FAMILIES = ("rock", "pop", "blues", "metal", "punk", "soul", "emo", "country")


def mutate_riff(riff: CompRiff, rng: random.Random, family: str, count: int = 2) -> CompRiff:
    """Give a vocabulary riff a personal variation (idiom-preserving).

    The downbeat never changes, so the figure keeps its identity. Each
    mutation is something a player does to make a pattern theirs: ghost a
    strum into a dead-note chuck, lighten it into an upstroke, push a hit
    an eighth early, hammer a sus into a held chord, slide into a chord, or
    answer the end of a beat with a bass-string walk.
    """
    steps = list(riff.steps)
    sub = riff.subdivision
    n = len(steps)
    ops = ["chuck", "up", "push", "walk"]
    if "p" in riff.steps:
        # Chug riffs are personalized by accent placement and by gaps.
        ops += ["accent", "gap", "accent"]
    if family in _SUS_FAMILIES:
        ops.append("sus")
    if family in _SLIDE_FAMILIES:
        ops.append("slide")
    applied = []
    for _ in range(count * 3):
        if len(applied) >= count:
            break
        op = rng.choice(ops)
        idx = [i for i in range(1, n) if steps[i] in "xX"]
        if op == "chuck" and idx:
            i = rng.choice(idx)
            if i % sub:
                steps[i] = "m"
                applied.append(op)
        elif op == "up":
            off = [i for i in idx if i % sub]
            if off:
                steps[rng.choice(off)] = "u"
                applied.append(op)
        elif op == "push":
            beats = [i for i in idx if i % sub == 0 and i - sub // 2 > 0
                     and steps[i - sub // 2] in ".-"]
            if beats and sub % 2 == 0:
                i = rng.choice(beats)
                j = i - sub // 2
                steps[j], steps[i] = "X", "-"
                applied.append(op)
        elif op == "sus":
            held = [i for i in idx if steps[i] in "xX" and i + 1 < n and steps[i + 1] == "-"]
            if held:
                steps[rng.choice(held)] = "h"
                applied.append(op)
        elif op == "slide":
            beats = [i for i in idx if i % sub == 0]
            if beats:
                steps[rng.choice(beats)] = "/"
                applied.append(op)
        elif op == "accent":
            chugs = [i for i in range(1, n) if steps[i] == "p" and i % sub]
            if chugs:
                steps[rng.choice(chugs)] = "P"
                applied.append(op)
        elif op == "gap":
            chugs = [i for i in range(1, n) if steps[i] == "p"]
            if len(chugs) > 4:
                steps[rng.choice(chugs)] = "."
                applied.append(op)
        elif op == "walk":
            # A bass-string pickup in the gap before a later beat.
            gaps = [i for i in range(sub, n) if steps[i] in ".-" and (i + 1) % sub == 0
                    and i + 1 < n and steps[i + 1] in _EVENT_CHARS]
            if gaps:
                steps[rng.choice(gaps)] = "w"
                applied.append(op)
    if not applied:
        return riff
    return CompRiff(f"{riff.name}~{'+'.join(applied)}", riff.families, riff.tier,
                    "".join(steps), riff.ring)


@dataclass(frozen=True)
class CompEvent:
    """One performed gesture, section-relative."""

    beat: float
    dur: float
    kind: str            # strum, up, chuck, chug, power, stab, root, fifth, walk,
                         # dyad, dyad5, dyad6, dyad7, sus, arp, slide
    accent: bool = False
    direction: str = "down"
    arp_index: int = 0
    target_pc: Optional[int] = None   # walk notes: the pitch class to land on
    tag: str = "comp"                 # "comp" or "comp_fill" / "comp_stop"


_KIND = {"X": "strum", "x": "strum", "u": "up", "m": "chuck", "p": "chug", "P": "power",
         "S": "stab", "r": "root", "f": "fifth", "w": "walk", "d": "dyad", "q": "dyad5",
         "Q": "dyad6", "y": "dyad7", "h": "sus", "a": "arp", "/": "slide"}


def _fit_steps(steps: str, bpb: float) -> str:
    """Stretch a 4/4 riff to another bar length on its own grid."""
    sub = len(steps) // 4
    n = max(1, int(round(bpb * sub)))
    if n <= len(steps):
        return steps[:n]
    out = steps
    while len(out) < n:
        out += steps[: n - len(out)]
    return out


def riff_events(riff: CompRiff, bar_start: float, bpb: float, chords: ChordMap,
                *, tag: str = "comp") -> List[CompEvent]:
    """Expand one bar of a riff into events."""
    steps = _fit_steps(riff.steps, bpb)
    sub = riff.subdivision
    step = 1.0 / sub
    events: List[CompEvent] = []
    arp_i = 0
    i = 0
    while i < len(steps):
        c = steps[i]
        if c not in _EVENT_CHARS:
            i += 1
            continue
        j = i + 1
        while j < len(steps) and steps[j] == "-":
            j += 1
        beat = bar_start + i * step
        dur = (j - i) * step
        kind = _KIND[c]
        on_beat = i % sub == 0
        direction = "up" if (kind == "up" or (kind == "strum" and not on_beat and sub != 3)) \
            else "down"
        target = None
        if kind == "walk":
            nxt = chords.at(min(bar_start + bpb + 1e-3, chords.total - 1e-3)) \
                if bar_start + bpb < chords.total else chords.at(beat)
            # Walk toward the next chord change inside this bar, if any.
            for k in range(j, len(steps)):
                if steps[k] in _EVENT_CHARS:
                    nxt = chords.at(bar_start + k * step)
                    break
            target = nxt.root_pc if nxt is not None else None
        events.append(CompEvent(round(beat, 4), dur, kind, accent=c in "XPS/", direction=direction,
                                arp_index=arp_i, target_pc=target, tag=tag))
        if kind == "arp":
            arp_i += 1
        i = j
    return events


def _walk_up(bar_start: float, bpb: float, sub: int, chords: ChordMap) -> List[CompEvent]:
    """The last beat of a phrase: root, then a stepwise walk into the next chord."""
    last = bar_start + bpb - 1.0
    nxt_beat = bar_start + bpb
    nxt = chords.at(min(nxt_beat + 1e-3, chords.total - 1e-3))
    target = nxt.root_pc if nxt is not None else None
    if sub == 3:
        offs = (0.0, 2.0 / 3.0)
    else:
        offs = (0.0, 0.5, 0.75)
    out = [CompEvent(round(last, 4), 0.45, "root", accent=True, tag="comp_fill")]
    for k, o in enumerate(offs[1:]):
        out.append(CompEvent(round(last + o, 4), 0.24, "walk", target_pc=target,
                             arp_index=len(offs) - 2 - k, tag="comp_fill"))
    return out


def _stop_bar(bar_start: float, bpb: float) -> List[CompEvent]:
    """Stop-time before a big arrival: one hit, silence, a pickup strum."""
    return [CompEvent(round(bar_start, 4), bpb - 0.75, "strum", accent=True, tag="comp_stop"),
            CompEvent(round(bar_start + bpb - 0.5, 4), 0.2, "chuck", tag="comp_stop"),
            CompEvent(round(bar_start + bpb - 0.25, 4), 0.25, "strum", accent=True,
                      direction="up", tag="comp_stop")]


def plan_comp_section(
    dna: CompDNA,
    *,
    section_type: str,
    occurrence: int,
    is_final_of_type: bool,
    bars: int,
    beats_per_bar: float,
    chord_slots: Sequence,
    key: str,
    mode: str,
    next_section_type: Optional[str] = None,
    hook_onsets: Sequence[float] = (),
) -> Tuple[List[CompEvent], str, float]:
    """Arrange a section. Returns (events, riff name, ring beats)."""
    st = str(section_type or "verse").strip().lower()
    st = _ALIASES.get(st, st)
    chords = ChordMap(chord_slots, key, mode)
    if bars <= 0 or chords.total <= 0:
        return [], "", 1.0
    tiers = _SECTION_TIERS.get(st, ("low", "drive"))
    riff = next((dna.riffs[t] for t in tiers if t in dna.riffs), None)
    if riff is None:
        return [], "", 1.0
    # The last chorus kicks up a gear: the alternate driving figure.
    if st == "chorus" and is_final_of_type and occurrence > 0 and "drive" in dna.alternates:
        riff = dna.alternates["drive"]
    nxt = _ALIASES.get(str(next_section_type or "").lower(), str(next_section_type or "").lower())
    bpb = float(beats_per_bar)
    sub = riff.subdivision
    events: List[CompEvent] = []
    phrase = 4 if bars >= 4 else bars
    for b in range(bars):
        start = b * bpb
        last_bar = b == bars - 1
        phrase_end = (b % phrase == phrase - 1) and not last_bar
        if last_bar and nxt == "chorus" and st in ("prechorus", "verse", "bridge") and bars >= 2:
            events += _stop_bar(start, bpb)
            continue
        if last_bar and next_section_type is None and st != "breakdown":
            events.append(CompEvent(round(start, 4), bpb, "slide" if sub == 4 else "strum",
                                    accent=True, tag="comp_stop"))
            continue
        bar = riff_events(riff, start, bpb, chords)
        if phrase_end and st in ("verse", "chorus", "outro", "solo", "intro") and bpb >= 3:
            # Keep the head of the bar, answer the phrase with a walk-up.
            bar = [e for e in bar if e.beat < start + bpb - 1.0 - 1e-6]
            bar += _walk_up(start, bpb, sub, chords)
        events += bar
    if hook_onsets and st == "chorus":
        # Band hits: strums that coincide with the hook's attacks get the accent.
        hook = {round(h % (bpb * 2), 2) for h in hook_onsets}
        events = [CompEvent(e.beat, e.dur, e.kind, True, e.direction, e.arp_index, e.target_pc, e.tag)
                  if e.kind in ("strum", "power", "slide", "stab") and round(e.beat % (bpb * 2), 2) in hook
                  else e for e in events]
    return events, riff.name, riff.ring
