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
from dataclasses import dataclass, field, replace
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
    plain_gesture: str = "strum"  # the player's undecorated chord attack
    waltz: Optional[object] = None  # country.WaltzPlayer, for 3/4 bars

    def signature(self) -> str:
        return ",".join(f"{t}:{r.name}" for t, r in sorted(self.riffs.items()))


# One-beat technique cells (four sixteenths) for synthesizing riffs. A cell
# starting with "-" ties over from the previous beat. Four cells make a bar:
# tens of thousands of figures per tier instead of a handful of templates,
# so songs of one genre start from the same technique vocabulary but do not
# share riffs.
_CELLS: Dict[str, Dict[str, List[str]]] = {
    "rock": {
        "drive": ["X-mx", "X-x-", "X-ux", "/---", "X---", "X-mX", "x-u-", "h-x-", ".xX-",
                  "X..x", "-xX-", "X-.x", "xmxm", "P-mP", "P---", "P-pp", "-.X-"],
        "low": ["p-p-", "p-pp", "r-m-", "X---", "r-f-", "d-d-", "p.p.", "pp-p", "r-mx",
                ".-d-", "p-m-", "r---", "-.d.", "P-p-", "p-.w"],
        "build": ["x-x-", "xxxx", "x-xx", "h-x-", "x-ux", "xmxm", "P-P-", "pppp", "x-xu"],
        "contrast": ["X---", "/---", "----", "X-.-", "..X-", "---.", "h---"],
        "stab": ["S---", "..S-", "S-.S", "...S", "m-S-", "S-m-", "----", "P..."],
    },
    "metal": {
        "drive": ["P-pp", "pppp", "P.pp", "/-pp", "P---", "pp.p", "P.P.", "p-pP", "Pppp",
                  "P-.p"],
        "low": ["p-pp", "pppp", "p.pp", "pp.p", "p-p-", "ppp.", "p..p"],
        "build": ["pppp", "P-P-", "p-pp", "P.P."],
        "contrast": ["P---", "/---", "----", "P-.-"],
        "stab": ["P...", "..P.", "P..P", "...P", "P.P."],
    },
    "pop": {
        "drive": ["x-u-", "X-ux", "x--u", "-uxu", "X-xu", "h-x-", "/---", "x-uu"],
        "low": ["a-a-", "r-a-", "X---", "..x-", "x-u-", "a.a.", "r---"],
        "build": ["x-x-", "xxxx", "x-ux", "h-x-"],
        "contrast": ["X---", "/---", "----"],
        "stab": ["S---", "..S-", "...S", "S-.-"],
    },
    "funk": {
        "drive": ["xmxm", "Xmxm", "xmXm", "..Xm", "xmxu", "d.dm", "mxmx", "X.mx"],
        "low": ["..X.", "mmX.", "r.rm", "w.m.", "..d.", "m.X.", "r..m"],
        "build": ["xmxm", "xxxx", "xmxx"],
        "contrast": ["X---", "----", "X-.-"],
        "stab": ["....", "X...", "..X.", "...m", "..Xm"],
    },
}
_CELLS["country"] = {
    "low": ["r---", "r-a-", "f---", "r..a"],
    "drive": ["x-u-", "d-u-", "X-u-", "x-ux"],
    "build": ["x-ux", "d-ux", "x-xu"],
    "contrast": ["r-a-", "a-a-", "X---"],
    "stab": ["d...", "..d.", "S..."],
}

_CELL_FAMILY = {"rock": "rock", "punk": "rock", "emo": "rock", "metal": "metal",
                "pop": "pop", "folk": "pop", "cinematic": "pop", "new_wave": "pop",
                "electronic": "pop", "funk": "funk", "disco": "funk", "rnb": "funk",
                "soul": "funk", "country": "country"}


def synthesize_riff(rng: random.Random, family: str, tier: str, heavy: bool = False,
                    tries: int = 48) -> Optional[CompRiff]:
    """Build a one-bar riff from technique cells, chosen for character.

    Candidates must open on an attack and not go silent for most of a
    driving bar; they are ranked by character (distinct techniques and
    off-beat accents) plus internal repetition (a figure that restates a
    cell grooves), and the seed picks among the best few.
    """
    table = _CELLS.get(_CELL_FAMILY.get(family, ""), {})
    if heavy and family in ("rock", "punk") and tier in ("drive", "low", "stab"):
        table = {tier: table.get(tier, []) + _CELLS["metal"][tier]}
    cells = table.get(tier)
    if not cells:
        return None
    scored = []
    for k in range(tries):
        bar = [rng.choice(cells) for _ in range(4)]
        if bar[0][0] not in _EVENT_CHARS:
            continue
        steps = "".join(bar)
        if tier in ("drive", "low", "build") and steps.count("-") + steps.count(".") > 11:
            continue
        riff = CompRiff(f"gen_{tier}", (family,), tier, steps,
                        {"contrast": 2.0, "stab": 0.3, "low": 0.6, "build": 0.4}.get(tier, 0.75))
        # Signature riffs mix a few techniques and restate themselves: more
        # than four techniques in one bar reads as a sampler, not a riff.
        classes = {_TECHNIQUE_CLASS[c] for c in steps if c in _TECHNIQUE_CLASS}
        variety = min(len(classes), 4) - 0.9 * max(0, len(classes) - 4)
        offbeat = sum(1 for i, c in enumerate(steps) if c in "XPS/h" and i % 4 != 0)
        if bar[0] == bar[2] or bar[1] == bar[3]:
            repeat = 1.0        # an AB/AB shape grooves
        elif len(set(bar)) < len(bar):
            repeat = 0.5
        else:
            repeat = 0.0
        scored.append((variety + 0.5 * min(offbeat, 3) + repeat, k, riff))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1]))
    pick = rng.choice(scored[:5])[2]
    return CompRiff(f"gen_{tier}:{pick.steps}", pick.families, tier, pick.steps, pick.ring)


def compose_comp_dna(*, seed: int, genre: str, key: str, mode: str, shuffle: bool, country_style=None) -> CompDNA:
    """Choose one riff per tier: characterful, and different from each other."""
    if comp_family(genre) == "country":
        from .country import country_style as resolve_style

        style = resolve_style(seed, genre, country_style)
        player = random.Random(stable_seed_int("composer.country.comp.player", seed, key, mode))
        dna = CompDNA("country")
        used = set()
        for tier in ("low", "drive", "build", "contrast", "stab"):
            riff = country_riff(player, style, tier)
            for _ in range(8):
                if riff.steps not in used:
                    break
                riff = country_riff(player, style, tier)
            used.add(riff.steps)
            dna.riffs[tier] = riff
            dna.alternates[tier] = country_riff(player, style, tier)
        from .country import waltz_player

        dna.waltz = waltz_player(seed, style)
        return dna
    fam = comp_family(genre)
    rng = random.Random(stable_seed_int("composer.comp", seed, genre, key, mode))
    # A separate stream, so vocabulary picks stay as they were.
    synth_rng = random.Random(stable_seed_int("composer.comp.synth", seed, genre, key, mode))
    heavy = any(t in str(genre).lower() for t in ("hard", "metal", "punk", "grunge"))
    wanted_len = 12 if shuffle else 16
    dna = CompDNA(fam)
    touch_rng = random.Random(stable_seed_int("composer.touch", seed, genre))
    dna.plain_gesture = touch_rng.choice(("power", "chug", "dyad", "stab") if heavy else
                                         ("strum", "up", "dyad"))
    used: set = set()
    for tier in ("drive", "low", "build", "contrast", "stab"):
        pool = [r for r in RIFFS if fam in r.families and r.tier == tier
                and len(r.steps) == wanted_len]
        if not pool and fam in ("country", "reggae", "jazz", "latin", "ska"):
            pool = [r for r in RIFFS if fam in r.families and len(r.steps) == wanted_len]
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
        # Most songs play a riff of their own, synthesized from technique
        # cells; the rest keep a personalized vocabulary riff.
        if not shuffle and synth_rng.random() < 0.7:
            own = synthesize_riff(synth_rng, fam, tier, heavy)
            if own is not None:
                dna.riffs[tier] = own
            alt = synthesize_riff(synth_rng, fam, tier, heavy)
            if alt is not None and tier == "drive":
                dna.alternates[tier] = alt
    return dna


_COUNTRY_CELLS = {
    "carter": (("r---", "r-a-", "r..a"), ("x-u-", "m-u-", "d---"),
               ("f---", "r-w-", "f-a-"), ("x-u-", "m-u-", "x-w-")),
    "chucks": (("r---", "r-m-"), ("m...", "m-u-", "x..."),
               ("f---", "f-m-"), ("m-u-", "x...", "m...")),
    "train": (("x-m-", "r-m-", "x.mm"), ("m-x-", "x-m-", "m.mu"),
              ("f-m-", "x-m-", "x.mm"), ("x-m-", "m-x-", "m.mu")),
    "low_strings": (("r-r-", "r---", "q---"), ("f-r-", "m-d-", "d---"),
                    ("r-a-", "f---", "q-q-"), ("d-u-", "m-d-", "w-r-")),
    "offbeats": (("r-u-", "r-d-", "r..."), ("..x.", "..d.", "..u."),
                 ("f-u-", "f-d-", "r..."), ("..x.", "..d.", "..u.")),
    "arp": (("r---", "r-a-"), ("a---", "..a.", "a-a-"),
            ("f---", "a---", "r-a-"), ("a---", "..a.", "a-a-")),
    "hybrid": (("r-d-", "d---", "r---"), ("..d.", "d-u-", "a-d-"),
               ("f-d-", "d---", "f---"), ("..d.", "d-u-", "a-d-")),
    "strum": (("x---", "r-x-", "x-m-"), ("x-u-", "x-ux", "m-u-"),
              ("X---", "f-x-", "x-m-"), ("x-u-", "d-u-", "m-u-")),
}


def country_riff(rng, style, tier):
    from .country import COMP_FAMILIES

    pool = COMP_FAMILIES[style]
    if tier == "contrast":
        pool = pool + ("arp", "hybrid")
    family = rng.choice(pool)
    steps = "".join(rng.choice(cell) for cell in _COUNTRY_CELLS[family])
    return CompRiff(f"country_{family}:{steps}", ("country",), tier, steps,
                    1.5 if family == "arp" else .5)


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
            # A bass-string pickup in the gap before a later beat, or before
            # the next bar line, where chords usually change. The walk only
            # sounds where it lands on a new chord (see riff_events).
            gaps = [i for i in range(sub, n) if steps[i] in ".-" and (i + 1) % sub == 0
                    and steps[(i + 1) % n] in _EVENT_CHARS]
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
    interval: int = 0                 # riff gestures: semitones above the chord root


_KIND = {"X": "strum", "x": "strum", "u": "up", "m": "chuck", "p": "chug", "P": "power",
         "S": "stab", "r": "root", "f": "fifth", "w": "walk", "d": "dyad", "q": "dyad5",
         "Q": "dyad6", "y": "dyad7", "h": "sus", "a": "arp", "/": "slide"}


def _fit_steps(steps: str, bpb: float, groups: Optional[Sequence[float]] = None) -> str:
    """Fit a 4/4 riff to another bar, phrased by the meter's beat groups.

    Each group is a slice of the riff that opens with an attack, so 7/8 is
    heard as 2+2+3 rather than a figure cut short. A group that would run
    past the riff's bar restarts the riff head (5/4 = 3 + a 2-beat restart);
    compound meters give each dotted-quarter pulse one half of the riff.
    Plain 4/4, and grids a group does not divide evenly, keep the riff as
    written (trimmed or repeated to length).
    """
    sub = len(steps) // 4
    n = max(1, int(round(bpb * sub)))
    plain = not groups or (abs(bpb - 4.0) < 1e-6 and tuple(groups) == (2.0, 2.0))
    if not plain and all(abs(g * sub - round(g * sub)) < 1e-6 for g in groups):
        compound = all(abs(g - 1.5) < 1e-6 for g in groups)
        out: List[str] = []
        pos = 0.0
        for k, g in enumerate(groups):
            length = int(round(g * sub))
            start = float((2 * k) % 4) if compound else (pos if pos + g <= 4.0 + 1e-6 else 0.0)
            first = int(round(start * sub))
            chunk = [steps[(first + i) % len(steps)] for i in range(length)]
            if chunk[0] in "-.":
                chunk[0] = "X" if k == 0 else "x"
            elif chunk[0] == "x":
                chunk[0] = "X"  # the group's downbeat carries the accent
            out.extend(chunk)
            pos = start + g
        return "".join(out)[:n]
    if n <= len(steps):
        return steps[:n]
    out = steps
    while len(out) < n:
        out += steps[: n - len(out)]
    return out


def _performance_grid(riff: CompRiff, bpb: float, groups):
    """Keep shuffle gestures on the actual pulse in compound meters."""
    if riff.subdivision == 3 and groups and all(abs(g - 1.5) < 1e-6 for g in groups):
        # A triplet quarter in 4/4 becomes one dotted-quarter pulse: three
        # eighths. Retain successive beats of the riff, including its rests.
        chunks = []
        for i in range(len(groups)):
            chunk = list(riff.steps[(i % 4) * 3:(i % 4 + 1) * 3])
            if chunk[0] in "-.":
                chunk[0] = "X" if i == 0 else "x"
            chunks.extend(chunk)
        return "".join(chunks), 2
    if riff.subdivision == 3 and groups and any(abs(g * 3 - round(g * 3)) > 1e-6 for g in groups):
        # Mixed eighth-note groups need a common grid for triplets and halves.
        steps = "".join(c + ("." if c == "." else "-") for c in riff.steps)
        return _fit_steps(steps, bpb, groups), 6
    return _fit_steps(riff.steps, bpb, groups), riff.subdivision


def _walk_landing(steps: str, i: int, bar_start: float, bpb: float, step: float,
                  chords: ChordMap):
    """The chord a walk at step ``i`` lands on, if it lands on a change.

    A walk lands on the next attack in the bar that is not itself a walk,
    or on the next bar line when nothing follows it. Returns None when the
    chord there is the one the walk is played over (or the section ends
    first).
    """
    k = next((j for j in range(i + 1, len(steps))
              if steps[j] in _EVENT_CHARS and steps[j] != "w"), None)
    landing = bar_start + (k * step if k is not None else bpb)
    current = chords.at(bar_start + i * step)
    if current is None or landing >= chords.total - 1e-6:
        return None
    nxt = chords.at(landing)
    if nxt is None or (nxt.pcs == current.pcs and nxt.root_pc == current.root_pc):
        return None
    return nxt


def _land_walks(steps: str, bar_start: float, bpb: float, step: float, chords: ChordMap) -> str:
    """Keep only the walks that lead into a chord change.

    A walking note is an approach: over a held chord it is a stray chromatic
    note every bar. Where the chord does not change, the step holds the
    previous gesture instead (or stays silent after a rest).
    """
    if "w" not in steps:
        return steps
    out = list(steps)
    for i, c in enumerate(steps):
        if c == "w" and _walk_landing(steps, i, bar_start, bpb, step, chords) is None:
            out[i] = "-"
    return "".join(out)


def riff_events(riff: CompRiff, bar_start: float, bpb: float, chords: ChordMap,
                *, tag: str = "comp", groups: Optional[Sequence[float]] = None) -> List[CompEvent]:
    """Expand one bar of a riff into events."""
    steps, sub = _performance_grid(riff, bpb, groups)
    step = 1.0 / sub
    steps = _land_walks(steps, bar_start, bpb, step, chords)
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
        dur = min((j - i) * step, bar_start + bpb - beat)
        if dur <= 1e-6:
            break
        kind = _KIND[c]
        on_beat = i % sub == 0
        direction = "up" if (kind == "up" or (kind == "strum" and not on_beat and sub != 3)) \
            else "down"
        target = None
        if kind == "walk":
            target = _walk_landing(steps, i, bar_start, bpb, step, chords).root_pc
        events.append(CompEvent(round(beat, 4), dur, kind, accent=c in "XPS/", direction=direction,
                                arp_index=arp_i if kind == "arp" else 0, target_pc=target, tag=tag))
        if kind == "arp":
            arp_i += 1
        i = j
    return events


def _walk_up(bar_start: float, bpb: float, sub: int, chords: ChordMap) -> List[CompEvent]:
    """The last beat of a phrase: root, then a stepwise walk into the next chord.

    When the next phrase starts on the same chord there is nothing to walk
    into, so the phrase is answered with root and fifth instead.
    """
    last = bar_start + bpb - 1.0
    nxt_beat = bar_start + bpb
    here = chords.at(last)
    nxt = chords.at(nxt_beat) if nxt_beat < chords.total - 1e-6 else None
    if nxt is None or here is None or (nxt.pcs == here.pcs and nxt.root_pc == here.root_pc):
        # No change to walk into: answer the phrase on the bass strings.
        second = 2.0 / 3.0 if sub == 3 else 0.5
        return [CompEvent(round(last, 4), round(second - 0.05, 4), "root", accent=True,
                          tag="comp_fill"),
                CompEvent(round(last + second, 4), round(1.0 - second - 0.05, 4), "fifth",
                          tag="comp_fill")]
    target = nxt.root_pc
    if sub == 3:
        offs = (0.0, 2.0 / 3.0)
    else:
        offs = (0.0, 0.5, 0.75)
    out = [CompEvent(round(last, 4), 0.45, "root", accent=True, tag="comp_fill")]
    for k, o in enumerate(offs[1:]):
        out.append(CompEvent(round(last + o, 4), 0.24, "walk", target_pc=target,
                             arp_index=len(offs) - 2 - k, tag="comp_fill"))
    return out


def _into_chorus(device: str, riff: CompRiff, start: float, bpb: float, chords: ChordMap,
                 groups: Optional[Sequence[float]]) -> List[CompEvent]:
    """The bar before a chorus, played the song's way."""
    if device == "build":
        n = int(round(bpb * 2))
        return [CompEvent(round(start + k * 0.5, 4), 0.45, "strum", accent=k >= n - 2,
                          direction="down", tag="comp_stop") for k in range(n)]
    if device == "push":
        bar = [e for e in riff_events(riff, start, bpb, chords, groups=groups)
               if e.beat < start + bpb - 0.5 - 1e-6]
        return bar + [CompEvent(round(start + bpb - 0.5, 4), 1.5, "strum", accent=True,
                                tag="comp_stop")]
    if device == "drop":
        return [CompEvent(round(start, 4), bpb, "strum", accent=True, tag="comp_stop")]
    if device == "fill":
        bar = [e for e in riff_events(riff, start, bpb, chords, groups=groups)
               if e.beat < start + bpb - 1.0 - 1e-6]
        return bar + [CompEvent(round(start + bpb - 1.0 + k * 0.25, 4), 0.06, "chuck",
                                tag="comp_fill") for k in range(3)] + [
            CompEvent(round(start + bpb - 0.25, 4), 0.25, "strum", accent=True,
                      direction="up", tag="comp_fill")]
    return _stop_bar(start, bpb)


def _stop_bar(bar_start: float, bpb: float) -> List[CompEvent]:
    """Stop-time before a big arrival: one hit, silence, a pickup strum."""
    return [CompEvent(round(bar_start, 4), bpb - 0.75, "strum", accent=True, tag="comp_stop"),
            CompEvent(round(bar_start + bpb - 0.5, 4), 0.2, "chuck", tag="comp_stop"),
            CompEvent(round(bar_start + bpb - 0.25, 4), 0.25, "strum", accent=True,
                      direction="up", tag="comp_stop")]


_CLASH = (1, 6, 11)   # minor second, tritone, major seventh


def yield_to_lead(events: Sequence[CompEvent], lead: Sequence[dict],
                  chord_slots, key: str, mode: str, country: bool = False) -> List[CompEvent]:
    """Choke riff power moves that would ring against a held lead note.

    A power chord moved to the b7 or 4 is riff language, but held under a
    lead note a semitone or tritone away it is a sustained clash, not a
    color. The move keeps its attack (the riff's rhythm and shape stay)
    and is cut to a stab, so the clash passes like a blue note.
    """
    if not lead:
        return list(events)
    chords = ChordMap(chord_slots, key, mode)
    held = [(float(n["beat"]), float(n["beat"]) + float(n["duration_beats"]), int(n["pitch"]) % 12)
            for n in lead if float(n.get("duration_beats") or 0) >= 0.5]
    out = []
    for e in events:
        if country and e.kind not in ("chuck", "root", "fifth", "walk") and e.dur > .35:
            span = chords.at(e.beat)
            if span and any(min(e.beat+e.dur, end)-max(e.beat, start) >= .25 and
                            pc_l not in span.pcs and any((pc-pc_l)%12 in _CLASH for pc in span.pcs)
                            for start, end, pc_l in held):
                e = replace(e, dur=.35)
        if e.kind == "rpower" and e.interval != 0 and e.dur > 0.3:
            span = chords.at(e.beat)
            pcs = set() if span is None else {(span.root_pc + e.interval) % 12,
                                               (span.root_pc + e.interval + 7) % 12}
            if any(min(e.beat + e.dur, end) - max(e.beat, start) >= 0.25 and
                   any((pc - pc_l) % 12 in _CLASH for pc in pcs)
                   for start, end, pc_l in held):
                e = replace(e, dur=0.24)
        out.append(e)
    return out


def _waltz(bpb, groups) -> bool:
    from .country import is_waltz

    return is_waltz(bpb, groups)


def _waltz_comp_bar(dna: CompDNA, section_type: str, start: float, bar: int, chords=None) -> List[CompEvent]:
    """The guitar's waltz bar: a bass note on 1 (alternating with the bass
    player's habit) and the song's own answer on 2 and 3."""
    from .country import WALTZ_FIGURES

    w = dna.waltz
    figure = WALTZ_FIGURES[w.part(w.comp, section_type) if w is not None else "pah_pah"]
    held = (chords is not None and start > 0 and
            chords.at(start - 1e-3).root_pc == chords.at(start).root_pc)
    alternate = w is None or w.bass_alternation == "bar" or (w.bass_alternation == "change" and held)
    out = []
    for off, dur, kind, arp in figure:
        if kind == "B":
            kind = "fifth" if alternate and bar % 2 else "root"
        out.append(CompEvent(round(start + off, 4), dur, kind, accent=off == 0,
                             direction="up" if kind == "up" else "down", arp_index=arp))
    return out


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
    groups: Optional[Sequence[float]] = None,
    arrangement=None,
    prev_section_type: Optional[str] = None,
    signature_riff=None,
) -> Tuple[List[CompEvent], str, float]:
    """Arrange a section. Returns (events, riff name, ring beats).

    ``arrangement`` (composer/arrangement.py) chooses the song's devices:
    how the band goes into a chorus (stop, build, fill, push, drop) and how
    phrases end (walk-up, chord slide, dead-note rake, or nothing). Without
    one, every chorus is approached with stop-time and every phrase ends
    with a walk-up.
    """
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
    riff_section = signature_riff is not None and getattr(arrangement, "riff_driven", False) \
        and st in ("verse", "intro", "outro") and bpb >= 3
    into = getattr(arrangement, "into_chorus", "stop")
    phrase_fill = getattr(arrangement, "phrase_fill", "walkup")
    prev = _ALIASES.get(str(prev_section_type or "").lower(), str(prev_section_type or "").lower())
    pushed_in = arrangement is not None and st == "chorus" and prev not in ("", "chorus") \
        and into == "push"
    activity = getattr(arrangement, "comp_activity", "normal")
    tail_every = 1 if activity == "busy" else (4 if activity == "sparse" else 2)
    fill_every = 8 if activity == "sparse" else 4
    # The same rule the drums and bass use (composer/arrangement.py), so the
    # whole band plays the device into any chorus.
    from .arrangement import into_chorus_device

    device = (into_chorus_device(arrangement, st, next_section_type) if arrangement is not None
              else ("stop" if nxt == "chorus" and st != "chorus" else ""))
    slide_next = False
    for b in range(bars):
        start = b * bpb
        last_bar = b == bars - 1
        phrase_end = (b % phrase == phrase - 1) and not last_bar
        if last_bar and device:
            events += _into_chorus(device, riff, start, bpb, chords, groups)
            continue
        if last_bar and next_section_type is None and st != "breakdown":
            ending = getattr(arrangement, "ending", "ring")
            if ending == "cold":
                events.append(CompEvent(round(start, 4), 0.25, "strum", accent=True,
                                        tag="comp_stop"))
            elif ending == "big":
                # Tremolo-strummed chord under the drum roll, a last hit.
                n = int(round((bpb - 0.5) * 4))
                events += [CompEvent(round(start + k * 0.25, 4), 0.24, "strum",
                                     accent=k == 0, direction="down" if k % 2 == 0 else "up",
                                     tag="comp_stop") for k in range(n)]
                events.append(CompEvent(round(start + bpb - 0.5, 4), 0.5, "strum", accent=True,
                                        tag="comp_stop"))
            else:
                events.append(CompEvent(round(start, 4), bpb, "slide" if sub == 4 else "strum",
                                        accent=True, tag="comp_stop"))
            continue
        if riff_section:
            # Normal players state the full figure, then leave an answer
            # bar open. Sparse players save the tail for the phrase end.
            events += [CompEvent(round(start + n.onset, 4), n.dur, n.kind, n.accent,
                                 tag="comp_riff", interval=n.interval)
                       for n in signature_riff.notes_for_bar(b)
                       if n.kind != "rsingle" or
                       (b if activity != "sparse" else b + 1) % tail_every == 0]
            continue
        if dna.family == "country" and _waltz(bpb, groups):
            bar = _waltz_comp_bar(dna, st, start, b, chords)
        else:
            bar = riff_events(riff, start, bpb, chords, groups=groups)
        if activity == "sparse" and st != "bridge":
            # A slid chord is a phrase gesture, not a new slide every bar.
            allow_slide = (b + 1) % fill_every == 0 and phrase_fill != "slide"
            used_slide = False
            restrained = []
            for e in bar:
                if e.kind == "slide":
                    if not allow_slide or used_slide:
                        e = replace(e, kind=dna.plain_gesture)
                    else:
                        used_slide = True
                restrained.append(e)
            bar = restrained
        if slide_next and bar:
            # The previous phrase ended by sliding into this chord.
            first = next((i for i, e in enumerate(bar) if e.kind in ("strum", "power")), None)
            if first is not None:
                e = bar[first]
                bar[first] = CompEvent(e.beat, e.dur, "slide", True, e.direction, e.arp_index,
                                       e.target_pc, "comp_fill")
            slide_next = False
        if b == 0 and pushed_in:
            # The chord already arrived on the push; the downbeat rests.
            bar = [e for e in bar if e.beat > start + 1e-6 or e.kind not in ("strum", "power",
                                                                             "slide", "stab")]
        if phrase_end and (b + 1) % fill_every == 0 and st in ("verse", "chorus", "outro", "solo", "intro") and bpb >= 3:
            if phrase_fill == "walkup":
                # Keep the head of the bar, answer the phrase with a walk-up.
                bar = [e for e in bar if e.beat < start + bpb - 1.0 - 1e-6]
                bar += _walk_up(start, bpb, sub, chords)
            elif phrase_fill == "rake":
                bar = [e for e in bar if e.beat < start + bpb - 1.0 - 1e-6]
                bar += [CompEvent(round(start + bpb - 1.0 + k * 0.25, 4), 0.06, "chuck",
                                  tag="comp_fill") for k in range(4)]
            elif phrase_fill == "slide":
                slide_next = True
        events += bar
    if hook_onsets and st == "chorus":
        # Band hits: strums that coincide with the hook's attacks get the accent.
        hook = {round(h % (bpb * 2), 2) for h in hook_onsets}
        events = [CompEvent(e.beat, e.dur, e.kind, True, e.direction, e.arp_index, e.target_pc, e.tag)
                  if e.kind in ("strum", "power", "slide", "stab") and round(e.beat % (bpb * 2), 2) in hook
                  else e for e in events]
    return events, (signature_riff.name if riff_section else riff.name), riff.ring
