"""Drum DNA: every song gets its own drummer.

The drum engine draws from genre templates, so across an album every song
played nearly the same verse beat (measured cross-song similarity 0.91) and
put a fill in bar 4 of every phrase. A drummer's identity lives in a few
choices made per song: the kick pattern, what the right hand plays in each
section, how the backbeat sits, how busy the ghost notes are, the fills they
reach for, and how often they fill and crash.

``compose_drum_dna`` makes those choices once per song from a large,
idiomatic space (kick cells per beat, about ten timekeeper archetypes,
backbeat styles, a synthesized fill vocabulary, fill and crash policies).
``plan_drum_section`` arranges a section from it: contrasting grooves per
section type, the song's own fills at its own phrase points, and the song's
chosen transition into the chorus (shared with the other parts through
``ArrangementDNA``). The drum engine performs the events with its kit,
humanization, and groove clock, and still publishes the kick features the
bass locks to.

Jazz and dance songs get their own players (``JazzKit``, ``DanceKit``): a
swing ride with the hi-hat foot and feathered kick, or four on the floor
with offbeat hats, claps, builds and drops. Compound meters (6/8, 12/8)
lay every figure out on the dotted-quarter pulse and its eighths
(``for_meter``).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from .arrangement import ArrangementDNA, intro_entry_bar

# Kick cells for one beat (4 sixteenths). Downbeat-beat cells start on the
# beat; backbeat cells leave the snare's step alone.
_KICK_ON = ["x...", "x...", "x.x.", "x..x", "xx..", "x.xx", "x...", "x..."]
_KICK_BACK = ["....", "....", "..x.", "...x", "..xx", "....", ".x.."]
_KICK_FREE = ["x...", "....", "..x.", "x.x.", "xx..", "...x", "x..x", "..xx"]

# Right-hand archetypes: (voice, step offsets within a beat, accent rule).
TIMEKEEPERS = {
    "hat8": ("hat_closed", (0, 2)),
    "hat16": ("hat_closed", (0, 1, 2, 3)),
    "hat4": ("hat_closed", (0,)),
    "hat8_open": ("hat_closed", (0, 2)),      # plus the song's open-hat accents
    "wash": ("hat_open", (0, 2)),             # half-open, washy chorus hats
    "ride8": ("ride", (0, 2)),
    "ride_bell": ("ride", (0,)),              # quarters with bell on the "and"
    "crash_ride": ("crash", (0,)),            # crash on every beat
    "floor8": ("tom_low", (0, 2)),            # tribal floor-tom pulse
    "pedal4": ("hat_pedal", (0,)),
}
_POOLS = {
    "verse": ["hat8", "hat8", "hat8_open", "hat16", "hat4", "ride8", "floor8", "pedal4"],
    "prechorus": ["hat16", "hat8", "ride8", "hat8_open", "floor8"],
    "chorus": ["wash", "ride8", "crash_ride", "hat8_open", "ride_bell", "hat8", "hat16"],
    "bridge": ["floor8", "ride_bell", "hat4", "ride8", "pedal4", "wash"],
    "solo": ["ride8", "wash", "hat8_open", "crash_ride", "ride_bell"],
    "intro": ["hat8", "ride8", "floor8", "pedal4", "wash"],
    "outro": ["wash", "ride8", "crash_ride", "hat8_open"],
    "breakdown": ["pedal4", "hat4", "floor8", "ride_bell"],
}
_BACKBEAT_POOLS = {
    "verse": ["backbeat"] * 5 + ["halftime"],
    "chorus": ["backbeat"] * 5 + ["stomp"],
    "bridge": ["halftime", "halftime", "backbeat"],
    "breakdown": ["halftime"],
}

# Fill grammar: per-beat rhythms and voice paths around the kit.
_FILL_RHYTHMS = {"16": (0, 1, 2, 3), "8": (0, 2), "trip": (0, 1.333, 2.667),
                 "flam8": (0, 2), "ga": (0, 2, 3)}
_FILL_PATHS = {
    "down_toms": ["snare", "tom_high", "tom_mid", "tom_low"],
    "snare_only": ["snare"],
    "high_low": ["tom_high", "tom_low"],
    "around": ["snare", "tom_high", "snare", "tom_mid", "tom_low"],
    "floor_snare": ["tom_low", "snare"],
    "unison": ["unison"],
}


@dataclass(frozen=True)
class DrumHit:
    beat: float          # section-relative
    voice: str           # kit voice name (drums engine pitch map)
    vel: float           # velocity scale (1.0 = base)
    kind: str
    dur: float = 0.25


@dataclass(frozen=True)
class Fill:
    name: str
    beats: float
    hits: Tuple[Tuple[float, str, float], ...]   # (offset, voice, vel)


@dataclass
class DrumDNA:
    kick_verse: str
    kick_chorus: str
    grooves: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # section -> (timekeeper, backbeat)
    ghosts: str = "light"          # none | light | busy
    open_hat_steps: Tuple[int, ...] = (14,)
    fills: Dict[str, Fill] = field(default_factory=dict)  # small | medium | big
    fill_every: int = 4            # bars between phrase fills
    small_fill_every: int = 0      # 0 = none
    crash_every: int = 8           # bars between phrase crashes (sections always crash)
    two_bar: bool = False          # bar 2 of each pair varies its last beat
    feel: str = "straight"         # straight | laid_back | push | shuffle
    hand_patterns: Dict[str, str] = field(default_factory=dict)
    snare_pattern: str = ""
    train_patterns: Dict[str, str] = field(default_factory=dict)
    kick_styles: Dict[str, str] = field(default_factory=dict)
    country_style: str = ""
    snare_gain: float = 1.0
    waltz: Optional[object] = None  # country.WaltzPlayer, for 3/4 bars
    rim_pickups: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    crash_policy: str = "regular"
    accent_voice: str = "crash"
    idiom: str = ""
    signature: str = ""
    seed_key: Tuple = ()           # (seed, genre): later draws (meter layouts) use their own streams
    meter: Tuple = ()              # (beats_per_bar, groups) the patterns are laid out for
    build_bars: int = 1            # how long an into-chorus build lasts (1 or 2 bars)
    kick_feel: str = ""            # dense | sparse: the kick_density knob, every section
    hand_feel: str = ""            # dense | sparse: the hat_density knob on idiom hand patterns
    jazz: Optional["JazzKit"] = None
    dance: Optional["DanceKit"] = None


@dataclass(frozen=True)
class JazzKit:
    """A swing drummer: ride and hi-hat foot keep time, the kick feathers,
    the left hand comps. Keyed by section type."""

    ride: Dict[str, str]           # section -> ride figure (see _RIDE_SKIPS)
    hand: Dict[str, str]           # section -> ride | hat_closed (sticks on a closed hat)
    foot: str                      # hi-hat foot: odd (2 and 4, or 2 in 3/4) | all | last | odd_last
    comp: Dict[str, float]         # section -> comping chance per beat
    comp_spots: Tuple[int, ...]    # where a comp lands in a beat (0 on it, 2 the swung "and")
    feather: float                 # feathered kick touch on every beat
    bombs: float                   # chance per bar of a dropped bomb


@dataclass(frozen=True)
class DanceKit:
    """A four-on-the-floor drummer (dance, house, techno, disco)."""

    backbeat: str                  # clap | snare | both, on 2 and 4
    hats: Dict[str, str]           # section -> hat figure (see _DANCE_HATS)
    perc: Dict[str, str]           # section -> percussion layer (see _DANCE_PERC)
    fill: str                      # phrase ends: clap_roll | snare_roll | kick_drop
    intro: str                     # kick_first | hats_first | full
    breakdown: str                 # no_kick | half_kick (bridges and breakdowns)
    prechorus: str                 # build (the whole prechorus rises) | groove
    pickup_kick: bool              # a kick on the last sixteenth of chorus bars
    feel: str = "straight"         # straight | swing16 (house-style swung sixteenths)


def _kick_pattern(rng: random.Random, beats: int, snare_beats: Sequence[int],
                  busy: float) -> str:
    cells = []
    for b in range(beats):
        if b == 0:
            pool = _KICK_ON
        elif b in snare_beats:
            pool = _KICK_BACK
        else:
            pool = _KICK_FREE
        cell = rng.choice(pool)
        if busy > 0.6 and cell.count("x") < 2 and rng.random() < busy - 0.5:
            cell = rng.choice(pool)  # a second chance for a busier chorus kick
        cells.append(cell)
    return "".join(cells)


def _make_fill(rng: random.Random, beats: float, name: str,
               rhythms: Optional[Sequence[str]] = None, touch: float = 1.0) -> Fill:
    rhythm = rng.choice(list(rhythms or _FILL_RHYTHMS))
    path_name = rng.choice(list(_FILL_PATHS))
    path = _FILL_PATHS[path_name]
    hits = []
    n_beats = max(1, int(round(beats)))
    total = sum(len(_FILL_RHYTHMS[rhythm]) for _ in range(n_beats))
    k = 0
    for b in range(n_beats):
        for o in _FILL_RHYTHMS[rhythm]:
            offset = b + o / 4.0
            voice = path[min(len(path) - 1, int(k * len(path) / max(1, total)))]
            vel = (0.7 + 0.35 * (k / max(1, total - 1))) * touch   # crescendo into the downbeat
            if voice == "unison":
                hits.append((offset, "snare", vel))
                hits.append((offset, "kick", vel))
            else:
                hits.append((offset, voice, vel))
                if rhythm == "flam8" and voice == "snare":
                    hits.append((max(0.0, offset - 0.06), "snare", vel * 0.5))
            k += 1
    return Fill(f"{name}:{rhythm}/{path_name}", float(n_beats), tuple(hits))


def compose_drum_dna(*, seed: int, genre: str, beats_per_bar: float = 4.0, country_style=None) -> DrumDNA:
    rng = random.Random(stable_seed_int("composer.drums", seed, genre))
    beats = max(1, int(round(beats_per_bar)))
    snare_beats = [b for b in range(beats) if b % 2 == 1] or [beats - 1]
    heavy = any(t in str(genre).lower() for t in ("metal", "hard", "punk", "grunge"))
    dna = DrumDNA(
        kick_verse=_kick_pattern(rng, beats, snare_beats, 0.4),
        kick_chorus=_kick_pattern(rng, beats, snare_beats, 0.8 if heavy else 0.6),
    )
    # Section grooves: contrast between verse and chorus is enforced.
    for sec, pool in _POOLS.items():
        tk = rng.choice(pool)
        if sec == "chorus" and tk == dna.grooves.get("verse", ("",))[0]:
            tk = rng.choice([p for p in pool if p != tk])
        bb = rng.choice(_BACKBEAT_POOLS.get(sec, ["backbeat"]))
        dna.grooves[sec] = (tk, bb)
    dna.ghosts = rng.choice(["none", "none", "light", "light", "busy"])
    dna.open_hat_steps = tuple(sorted(rng.sample([2, 6, 10, 14], rng.choice([1, 1, 2]))))
    dna.fills = {"small": _make_fill(rng, 1, "small"), "medium": _make_fill(rng, 2, "medium"),
                 "big": _make_fill(rng, beats, "big")}
    dna.fill_every = rng.choice([4, 4, 8, 8])
    dna.small_fill_every = rng.choice([0, 0, 2, 4])
    dna.crash_every = rng.choice([4, 8, 8, 16])
    dna.two_bar = rng.random() < 0.4
    # The band's feel: where the drummer sits against the grid.
    bluesy = any(t in str(genre).lower() for t in ("blues", "boogie", "southern", "country"))
    feel_weights = [("straight", 45), ("laid_back", 25), ("push", 15),
                    ("shuffle", 35 if bluesy else 15)]
    draw = rng.random() * sum(w for _, w in feel_weights)
    for name, w in feel_weights:
        draw -= w
        if draw <= 0:
            dna.feel = name
            break
    g = str(genre).lower()
    dna.idiom = next((t for t in ("country", "reggae", "jazz", "swing") if t in g), "")
    if dna.idiom == "country":
        dna.kick_verse = "x......." * max(1, (beats+1)//2)
        dna.kick_chorus = dna.kick_verse
        dna.grooves = {sec: (rng.choice(("hat8", "hat4", "ride8", "hat8_open")),
                            rng.choice(("train", "train", "backbeat"))) for sec in _POOLS}
        dna.snare_pattern = "".join(rng.choice(("x.x.", "..x.", "....", "x...")) for _ in range(beats))
        if rng.random() < .5:
            dna.kick_chorus = dna.kick_chorus[:beats*4-2] + "x."
        dna.feel = rng.choice(("straight", "shuffle"))
        dna.fills = {name: replace(fill, hits=tuple((t, "snare", v*.8) for t, _, v in fill.hits))
                     for name, fill in dna.fills.items()}
    elif dna.idiom == "reggae":
        dna.kick_verse = "." * (beats*4)
        dna.kick_chorus = dna.kick_verse
        dna.grooves = {sec: (rng.choice(("hat8", "hat8_open", "hat16", "hat4", "ride8")), "one_drop") for sec in _POOLS}
        dna.feel, dna.ghosts, dna.two_bar = "laid_back", "none", False
    elif dna.idiom in ("jazz", "swing"):
        # The swing drummer is its own player (JazzKit below): the kick
        # feathers every beat, so that is the pocket the band locks to.
        dna.kick_verse = "x..." * beats
        dna.kick_chorus = dna.kick_verse
        dna.feel = "shuffle"
    if dna.idiom and dna.idiom not in ("jazz", "swing"):
        cells = (("..x.", "x.x.", "x...", "...x") if dna.idiom == "reggae" else
                 ("x...", "x.x.", "x.xx", "..x.") if dna.idiom == "country" else
                 ("x...", "x.x.", "....", "..x."))
        dna.hand_patterns = {sec: "".join(rng.choice(cells) for _ in range(beats)) for sec in _POOLS}
    if dna.idiom:
        player = random.Random(stable_seed_int("composer.drums.idiom", seed, genre))
        dna.crash_policy = player.choice(("chorus", "chorus", "section", "none"))
        dna.accent_voice = player.choice(("crash", "crash", "ride", "china"))
        if dna.idiom in ("country", "reggae"):
            styles = (("two_beat", "two_beat", "pickup", "four_floor") if dna.idiom == "country"
                      else ("one_drop", "one_drop", "one_drop", "rockers", "steppers"))
            verse = player.choice(styles)
            chorus = player.choice([v for v in styles if v != verse])
            for sec in _POOLS:
                style = chorus if sec in ("chorus", "solo", "outro") else verse
                dna.kick_styles[sec] = style
                tk, bb = dna.grooves[sec]
                if sec == "chorus" and tk == dna.grooves["verse"][0]:
                    tk = player.choice([v for v in ("hat8", "hat8_open", "ride8", "hat4") if v != tk])
                if dna.idiom == "reggae":
                    bb = style
                dna.grooves[sec] = (tk, bb)
                dna.train_patterns[sec] = "".join(player.choice(("x.x.", "..x.", "x...", "...."))
                                                 for _ in range(beats))
            if dna.train_patterns["chorus"] == dna.train_patterns["verse"]:
                head = "..x." if dna.train_patterns["verse"][:4] != "..x." else "x..."
                dna.train_patterns["chorus"] = head + dna.train_patterns["chorus"][4:]
            if dna.idiom == "reggae":
                rim_rng = random.Random(stable_seed_int("composer.drums.reggae.rim", seed, genre))
                dna.rim_pickups = {sec: rim_rng.choice(((), (), (6,), (14,), (6, 14))) for sec in _POOLS}
            dna.kick_verse = _idiom_kick(verse, beats_per_bar)
            dna.kick_chorus = _idiom_kick(chorus, beats_per_bar)
            dna.two_bar = False
            if dna.idiom == "reggae":
                dna.ghosts = player.choice(("none", "light", "light", "busy"))
                dna.small_fill_every = player.choice((0, 0, 4))
                dna.fills = {name: replace(fill, beats=min(fill.beats, 2),
                    hits=tuple((t, v, vel*.8) for t, v, vel in fill.hits if t < 2))
                    for name, fill in dna.fills.items()}
    if dna.idiom == "country":
        from .country import country_style as resolve_style

        dna.country_style = resolve_style(seed, genre, country_style)
        from .country import waltz_player

        dna.waltz = waltz_player(seed, dna.country_style)
        player = random.Random(stable_seed_int("composer.country.drums.player", seed))
        style = dna.country_style
        dna.feel = "shuffle" if style == "honky_tonk" else "straight"
        dna.snare_gain = player.choice((.55, .65, .8)) if style in ("outlaw", "ballad") else player.choice((.85, 1., 1.))
        dna.kick_styles = {}  # Preserve these personal patterns through planning.
        def feet(chorus):
            hits = {0, 8} if beats >= 4 else {0}
            if style == "country_rock" and chorus or style == "two_step" and player.random() < .5:
                hits.update(range(0, beats*4, 4))
            choices = (2, 6, 10, 14) if style != "ballad" else (6, 14)
            hits.update(player.sample(choices, player.choice((0, 1, 1, 2))))
            return "".join("x" if i in hits else "." for i in range(beats*4))
        dna.kick_verse, dna.kick_chorus = feet(False), feet(True)
        if dna.kick_chorus == dna.kick_verse:
            i = min(beats*4-2, 14)
            dna.kick_chorus = dna.kick_chorus[:i] + ("." if dna.kick_chorus[i] == "x" else "x") + dna.kick_chorus[i+1:]
        for sec in dna.grooves:
            chorus = sec in ("chorus", "solo", "outro")
            bb = player.choice(("train", "train", "backbeat") if style == "outlaw" else
                               ("backbeat", "backbeat", "train"))
            tk = player.choice(("hat4", "hat8", "ride8") if not chorus else
                               ("ride8", "hat8_open", "hat8", "ride_bell"))
            if sec == "chorus" and tk == dna.grooves["verse"][0]:
                tk = "ride8" if tk != "ride8" else "hat8_open"
            dna.grooves[sec] = (tk, bb)
            cells = ("x...", "x.x.", "..x.") if style != "ballad" else ("x...", "....", "..x.")
            dna.hand_patterns[sec] = "".join(player.choice(cells) for _ in range(beats))
    dna.seed_key = (seed, str(genre))
    # How long a build into the chorus lasts: its own stream, so every
    # other habit above stays put.
    dna.build_bars = random.Random(stable_seed_int("composer.drums.build", seed, genre)).choice((1, 2, 2))
    if dna.idiom in ("jazz", "swing"):
        dna.jazz = _compose_jazz(seed, genre, beats)
        dna.grooves = {sec: (f"{dna.jazz.hand[sec]}:{dna.jazz.ride[sec]}", "comp") for sec in _POOLS}
        dna.hand_patterns = {}
        jrng = random.Random(stable_seed_int("composer.drums.jazz.fills", seed, genre))
        dna.fills = {name: _make_fill(jrng, n, name, rhythms=("trip", "8"), touch=.75)
                     for name, n in (("small", 1), ("medium", 2), ("big", 2))}
        dna.fill_every, dna.small_fill_every = jrng.choice((4, 8, 8)), 0
        dna.ghosts, dna.two_bar = "none", False
    elif not dna.idiom and is_dance_genre(genre):
        dna.idiom = "dance"
        dna.dance = _compose_dance(seed, genre)
        drng = random.Random(stable_seed_int("composer.drums.dance.form", seed, genre))
        dna.kick_verse = dna.kick_chorus = "x..." * beats
        dna.grooves = {sec: (dna.dance.hats[sec], dna.dance.backbeat) for sec in _POOLS}
        dna.hand_patterns, dna.kick_styles = {}, {}
        dna.fills = _dance_fills(dna.dance.fill)
        dna.fill_every, dna.small_fill_every = drng.choice((8, 8, 4)), 0
        dna.crash_every, dna.crash_policy, dna.accent_voice = drng.choice((8, 8, 16)), "regular", "crash"
        dna.ghosts, dna.two_bar, dna.feel = "none", False, dna.dance.feel
    dna.signature = (f"kick {dna.kick_verse}/{dna.kick_chorus}, "
                     + ", ".join(f"{s}={t}/{b}" for s, (t, b) in sorted(dna.grooves.items()))
                     + f", ghosts={dna.ghosts}, fills every {dna.fill_every}"
                     + f" ({dna.fills['big'].name}), crash every {dna.crash_every}, feel {dna.feel}")
    return dna


def _idiom_kick(style, bpb, groups=None):
    steps = max(1, int(round(bpb*4)))
    if groups and (bpb != 4 or tuple(groups) != (2.0, 2.0)):
        positions = ([0] if bpb == 3 and tuple(groups) == (1.0, 1.0, 1.0) else
                     [int(round(sum(groups[:i])*4)) for i in range(len(groups))])
    elif style == "one_drop":
        positions = []  # The kick shares the cross-stick's drop below.
    elif style in ("four_floor", "steppers"):
        positions = list(range(0, steps, 4))
    elif style == "rockers":
        positions = [0, steps//2]
    else:
        positions = list(range(0, steps, 8))
        if style == "pickup" and steps > 6:
            positions += [6]
    return "".join("x" if i in positions else "." for i in range(steps))


# --- jazz --------------------------------------------------------------------

# Ride figures: the ride plays every beat; these are the beats whose swung
# "and" adds the skip note. "spang" is spang-a-lang (1, 2&, 3, 4& in 4/4;
# the jazz waltz's 1, 2&, 3 in 3/4); "spang_alt" adds the "and" of 3 every
# other bar; "quarters" (no skips) is only the sparse hat_density setting.
_RIDE_FIGURES = ("spang", "spang", "spang", "spang_every", "spang_late", "spang_alt")
_JAZZ_COMP = {"intro": (.08, .18), "verse": (.15, .3), "prechorus": (.2, .35),
              "chorus": (.2, .35), "bridge": (.2, .4), "solo": (.3, .5),
              "outro": (.12, .25), "breakdown": (.1, .2)}


def _ride_skips(figure: str, beats: int, bar: int = 0) -> set:
    if figure == "spang_every":
        return set(range(beats))
    if figure == "quarters":
        return set()
    if figure == "spang_late":
        return {beats - 1}
    odd = {b for b in range(beats) if b % 2 == 1} or {beats - 1}
    if figure == "spang_alt" and bar % 2 == 1:
        return odd | {beats - 1 if beats % 2 else beats - 2}
    return odd


def _foot_beats(foot: str, beats: int) -> set:
    odd = {b for b in range(beats) if b % 2 == 1} or {beats - 1}
    return {"all": set(range(beats)), "last": {beats - 1},
            "odd_last": odd | {beats - 1}}.get(foot, odd)


def _compose_jazz(seed: int, genre: str, beats: int) -> JazzKit:
    rng = random.Random(stable_seed_int("composer.drums.jazz", seed, genre))
    ride = {sec: rng.choice(_RIDE_FIGURES) for sec in _POOLS}
    if ride["solo"] == ride["verse"]:
        ride["solo"] = "spang_every" if ride["verse"] != "spang_every" else "spang"
    hand = {sec: "hat_closed" if sec in ("intro", "bridge", "breakdown") and rng.random() < .3
            else "ride" for sec in _POOLS}
    # The foot: 2 and 4 in 4/4 (some players every beat); in a jazz waltz
    # on 2, on 3, or on 2 and 3.
    foot = rng.choice(("odd", "odd", "odd", "odd", "all")) if beats % 2 == 0 else \
        rng.choice(("odd", "last", "odd_last", "odd_last"))
    comp = {sec: round(rng.uniform(*_JAZZ_COMP[sec]), 2) for sec in _POOLS}
    return JazzKit(ride=ride, hand=hand, foot=foot, comp=comp,
                   comp_spots=rng.choice(((2,), (2, 2, 0), (0, 2))),
                   feather=rng.choice((.28, .32, .36)), bombs=rng.choice((.08, .15, .25)))


def _jazz_bar(dna: DrumDNA, st: str, start: float, bpb: float, groups, rng: random.Random,
              until: float) -> List[DrumHit]:
    """One bar of swing time: the ride on every beat (with the song's skip
    notes), the hi-hat foot, the feathered kick, a comping left hand and the
    odd bomb. Compound bars ride every eighth of the dotted-quarter pulse."""
    kit = dna.jazz
    hand = kit.hand.get(st, "ride")
    kind = "hat" if "hat" in hand else "ride"
    hits: List[DrumHit] = []
    if is_compound(groups):
        pulses = len(groups)
        feet = _foot_beats(kit.foot, pulses)
        for p in range(pulses):
            t0 = start + 1.5 * p
            for e in range(3):
                hits.append(DrumHit(t0 + .5 * e, hand, .85 if e == 0 else .58, kind))
            if p in feet:
                hits.append(DrumHit(t0, "hat_pedal", .62, "hat"))
            if kit.feather > 0:
                hits.append(DrumHit(t0, "kick", kit.feather, "kick_feather"))
        slots = [start + .5 * i for i in range(pulses * 3) if i % 3]
        chance = kit.comp.get(st, .25) * .6
    else:
        beats = max(1, int(round(bpb)))
        skips = _ride_skips(kit.ride.get(st, "spang"), beats, int(round(start / max(1e-6, bpb))))
        feet = _foot_beats(kit.foot, beats)
        for i in range(beats):
            t = start + i
            # 2 and 4 speak a little on the ride, as they do with the foot.
            hits.append(DrumHit(t, hand, .9 if i in feet else .82, kind))
            if i in skips:
                hits.append(DrumHit(t + .5, hand, .58, kind))
            if i in feet:
                hits.append(DrumHit(t, "hat_pedal", .62, "hat"))
            if kit.feather > 0:
                hits.append(DrumHit(t, "kick", kit.feather, "kick_feather"))
        slots = [start + i + s / 4.0 for i in range(beats) for s in kit.comp_spots]
        chance = kit.comp.get(st, .25) / max(1, len(kit.comp_spots))
    comps = 0
    for t in slots:
        if rng.random() < chance and comps < 3:
            hits.append(DrumHit(t, "snare", round(rng.uniform(.34, .5), 2), "snare_comp"))
            comps += 1
    if rng.random() < kit.bombs:
        # A bomb: the kick drops an accent, usually on an offbeat.
        t = start + rng.randrange(max(1, int(round(bpb)))) + rng.choice((.5, .5, 0.0))
        if t < start + bpb - 1e-6:
            hits = [h for h in hits if not (h.voice == "kick" and abs(h.beat - t) < 1e-6)]
            hits.append(DrumHit(t, "kick", .95, "kick_bomb"))
    return [h for h in hits if h.beat < until - 1e-6]


# --- dance -------------------------------------------------------------------

_DANCE_WORDS = {"dance", "electronic", "electro", "techno", "house", "disco", "edm",
                "trance", "electropop", "synthpop", "eurodance"}
# Hat figures per beat: (sixteenth, voice, touch).
_DANCE_HATS = {
    "open_off": ((2, "hat_open", .8),),
    "off_closed": ((2, "hat_closed", .75),),
    "closed8_open": ((0, "hat_closed", .58), (2, "hat_open", .8)),
    "closed16_open": ((0, "hat_closed", .6), (1, "hat_closed", .42), (2, "hat_open", .8),
                      (3, "hat_closed", .42)),
    "closed16": ((0, "hat_closed", .6), (1, "hat_closed", .42), (2, "hat_closed", .75),
                 (3, "hat_closed", .42)),
}
_DANCE_HAT_POOLS = {
    "verse": ("closed16", "off_closed", "closed8_open", "open_off"),
    "prechorus": ("closed16", "closed8_open", "closed16_open"),
    "chorus": ("open_off", "closed16_open", "closed8_open"),
    "bridge": ("off_closed", "closed16", "open_off"),
    "solo": ("open_off", "closed16_open"),
    "intro": ("off_closed", "closed16", "closed8_open"),
    "outro": ("open_off", "closed8_open", "closed16_open"),
    "breakdown": ("off_closed", "closed16"),
}
_DANCE_PERC = ("none", "none", "shaker16", "tamb_backbeat", "tamb_off", "cowbell_off", "ride_quarters")


def is_dance_genre(genre: str) -> bool:
    """Four-on-the-floor genres, matched on whole words (not "dancehall")."""
    return any(w in _DANCE_WORDS for w in re.split(r"[^a-z]+", str(genre or "").lower()))


def _compose_dance(seed: int, genre: str) -> DanceKit:
    rng = random.Random(stable_seed_int("composer.drums.dance", seed, genre))
    hats = {sec: rng.choice(pool) for sec, pool in _DANCE_HAT_POOLS.items()}
    if hats["chorus"] == hats["verse"]:
        hats["chorus"] = rng.choice([h for h in _DANCE_HAT_POOLS["chorus"] if h != hats["verse"]])
    verse_perc, chorus_perc = rng.choice(_DANCE_PERC), rng.choice(_DANCE_PERC)
    perc = {sec: chorus_perc if sec in ("chorus", "solo", "outro") else verse_perc for sec in _POOLS}
    swung = any(w in str(genre).lower() for w in ("house", "disco"))
    return DanceKit(
        backbeat=rng.choice(("clap", "clap", "snare", "both")),
        hats=hats, perc=perc,
        fill=rng.choice(("clap_roll", "snare_roll", "kick_drop")),
        intro=rng.choice(("kick_first", "hats_first", "full")),
        breakdown=rng.choice(("no_kick", "no_kick", "half_kick")),
        prechorus=rng.choice(("build", "build", "groove")),
        pickup_kick=rng.random() < .3,
        feel="swing16" if rng.random() < (.4 if swung else .15) else "straight",
    )


def _dance_fills(style: str) -> Dict[str, Fill]:
    """Dance phrase ends: a sixteenth roll over the kick, or the kick drops
    out under two claps."""
    def roll(voice, beats):
        n = int(beats * 4)
        hits = [(k * .25, voice, .55 + .5 * k / max(1, n - 1)) for k in range(n)]
        return tuple(hits + [(float(b), "kick", 1.0) for b in range(int(beats))])
    if style == "kick_drop":
        small = ((.5, "clap", .85), (.75, "clap", 1.0))
        big = ((0.0, "kick", 1.0), (1.5, "clap", .85), (1.75, "clap", 1.0))
    else:
        voice = "clap" if style == "clap_roll" else "snare"
        small, big = roll(voice, 1), roll(voice, 2)
    return {"small": Fill("dance_small:" + style, 1.0, small),
            "medium": Fill("dance_medium:" + style, 1.0, small),
            "big": Fill("dance_big:" + style, 2.0, big)}


def _dance_bar(dna: DrumDNA, st: str, b: int, bars: int, start: float, bpb: float,
               groups, snare_steps: set, until: float) -> List[DrumHit]:
    """One bar of four on the floor: kick on every beat, the song's hats on
    the offbeats, clap or snare on 2 and 4, a percussion layer. Intros bring
    the kit in by halves; bridges and breakdowns take the kick out (or to
    half time); a building prechorus rolls up from quarters to sixteenths."""
    kit = dna.dance
    compound = is_compound(groups)
    unit = 1.5 if compound else 1.0
    beats = len(groups) if compound else max(1, int(round(bpb)))
    hat = _DANCE_HATS.get(kit.hats.get(st, kit.hats["verse"]), _DANCE_HATS["open_off"])
    perc = kit.perc.get(st, "none")
    kick_beats = set(range(beats))
    hats_on = claps_on = True
    if st in ("bridge", "breakdown"):
        kick_beats = set() if kit.breakdown == "no_kick" else {0, beats // 2}
    if st == "intro" and b < bars // 2:
        if kit.intro == "kick_first":
            hats_on = claps_on = False
        elif kit.intro == "hats_first":
            kick_beats = set()
    hits: List[DrumHit] = []
    for i in range(beats):
        t = start + i * unit
        if i in kick_beats:
            hits.append(DrumHit(t, "kick", 1.05, "kick"))
        if hats_on:
            for s, voice, touch in hat:
                off = (s / 4.0) if not compound else {0: 0.0, 1: .5, 2: 1.0, 3: 1.25}[s]
                hits.append(DrumHit(t + off, voice, touch, "hat"))
        if perc == "shaker16":
            for s in range(int(unit * 4)):
                hits.append(DrumHit(t + s * .25, "shaker", .5 if s == 2 else .34, "perc"))
        elif perc in ("tamb_off", "cowbell_off"):
            hits.append(DrumHit(t + (1.0 if compound else .5), perc.split("_")[0].replace("tamb", "tambourine"),
                                .5, "perc"))
        elif perc == "ride_quarters" and st in ("chorus", "solo", "outro"):
            hits.append(DrumHit(t, "ride", .55, "perc"))
    if claps_on:
        for s in sorted(snare_steps):
            t = start + s * .25
            if kit.backbeat in ("clap", "both"):
                hits.append(DrumHit(t, "clap", 1.0, "snare"))
            if kit.backbeat in ("snare", "both"):
                hits.append(DrumHit(t, "snare", .95 if kit.backbeat == "snare" else .8, "snare"))
            if perc == "tamb_backbeat":
                hits.append(DrumHit(t, "tambourine", .6, "perc"))
    if kit.pickup_kick and st in ("chorus", "solo", "outro") and kick_beats:
        hits.append(DrumHit(start + bpb - .25, "kick", .85, "kick"))
    if st == "prechorus" and kit.prechorus == "build" and bars >= 2:
        # The whole prechorus rises: quarters, then eighths, then sixteenths.
        step = 1.0 if b < bars // 2 else (.5 if b < bars - 1 else .25)
        span = bars * bpb
        for k in range(int(round(bpb / step))):
            t = start + k * step
            pos = (b * bpb + k * step) / span
            hits.append(DrumHit(t, "snare", .35 + .75 * pos, "snare_build"))
    return [h for h in hits if h.beat < until - 1e-6]


# --- meters ------------------------------------------------------------------

def is_compound(groups) -> bool:
    """Dotted-quarter pulses (6/8, 9/8, 12/8): eighths are the subdivision."""
    try:
        return bool(groups) and len(groups) >= 2 and all(abs(float(g) - 1.5) < 1e-6 for g in groups)
    except (TypeError, ValueError):
        return False


# Timekeepers on the compound pulse: offsets in sixteenths within a
# dotted quarter (0, 2 and 4 are its eighths).
COMPOUND_TIMEKEEPERS = {
    "hat8": ("hat_closed", (0, 2, 4)),
    "hat16": ("hat_closed", (0, 1, 2, 3, 4, 5)),
    "hat4": ("hat_closed", (0,)),
    "hat8_open": ("hat_closed", (0, 2, 4)),
    "wash": ("hat_open", (0, 2, 4)),
    "ride8": ("ride", (0, 2, 4)),
    "ride_bell": ("ride", (0, 2, 4)),          # the bell on the pulse
    "crash_ride": ("crash", (0,)),
    "floor8": ("tom_low", (0, 2, 4)),
    "pedal4": ("hat_pedal", (0,)),
}
_COMPOUND_KICK_ON = ["x.....", "x.....", "x...x.", "x.x...", "x....."]
_COMPOUND_KICK_BACK = ["......", "......", "....x.", "..x..."]
_COMPOUND_KICK_FREE = ["x.....", "......", "x...x.", "....x.", "......"]


def _compound_kick(rng: random.Random, pulses: int, snare_pulses: Sequence[int], busy: float) -> str:
    """A kick on the eighth-note grid of the dotted-quarter pulse."""
    cells = []
    for p in range(pulses):
        pool = _COMPOUND_KICK_ON if p == 0 else (
            _COMPOUND_KICK_BACK if p in snare_pulses else _COMPOUND_KICK_FREE)
        cell = rng.choice(pool)
        if busy > 0.6 and cell.count("x") < 2 and rng.random() < busy - 0.5:
            cell = rng.choice(pool)
        cells.append(cell)
    return "".join(cells)


def _compound_cells(rng: random.Random, pulses: int, cells: Sequence[str]) -> str:
    return "".join(rng.choice(cells) for _ in range(pulses))


def _compound_fill(fill: Fill, pulses_long: int) -> Fill:
    """The song's fill (same rhythm family and path) on the compound grid:
    eighths or sixteenths of the dotted quarter."""
    head, _, spec = fill.name.partition(":")
    rhythm, _, path_name = spec.partition("/")
    path = _FILL_PATHS.get(path_name)
    if path is None:
        return fill
    per = {"16": (0, 1, 2, 3, 4, 5), "ga": (0, 2, 3, 4)}.get(rhythm, (0, 2, 4))
    offsets = [p * 1.5 + s * .25 for p in range(pulses_long) for s in per]
    hits = []
    for k, off in enumerate(offsets):
        voice = path[min(len(path) - 1, int(k * len(path) / max(1, len(offsets))))]
        vel = 0.7 + 0.35 * (k / max(1, len(offsets) - 1))
        if voice == "unison":
            hits += [(off, "snare", vel), (off, "kick", vel)]
        else:
            hits.append((off, voice, vel))
    return Fill(f"{head}:{rhythm}/{path_name}", 1.5 * pulses_long, tuple(hits))


def for_meter(dna: DrumDNA, beats_per_bar: float, groups=None) -> DrumDNA:
    """The song's drummer laid out for one meter. Simple meters play the DNA
    as drawn; compound meters (6/8, 12/8) get the same habits on the
    dotted-quarter pulse and its eighths, drawn on their own stream: kicks
    on the eighth grid, idiom hands and trains in pulse cells, open-hat
    accents on the pulse's last eighth, and fills of whole pulses."""
    key = (float(beats_per_bar), tuple(float(g) for g in (groups or ())))
    if dna.meter == key:
        return dna
    if not is_compound(groups) or dna.jazz is not None or dna.dance is not None:
        return replace(dna, meter=key)
    pulses = len(groups)
    rng = random.Random(stable_seed_int("composer.drums.compound", *dna.seed_key, pulses))
    snare_pulses = [p for p in range(pulses) if p % 2 == 1] or [pulses - 1]
    genre = str(dna.seed_key[1]).lower() if len(dna.seed_key) > 1 else ""
    heavy = any(t in genre for t in ("metal", "hard", "punk", "grunge"))
    kick_verse = _compound_kick(rng, pulses, snare_pulses, 0.4)
    kick_chorus = _compound_kick(rng, pulses, snare_pulses, 0.8 if heavy else 0.6)
    if kick_chorus == kick_verse:
        kick_chorus = kick_chorus[:-2] + ("x." if kick_chorus[-2] == "." else "..")
    cells = (("..x.x.", "x.x.x.", "x...x.") if dna.idiom == "reggae" else
             ("x.x.x.", "x...x.", "x.....") if dna.idiom == "country" else
             ("x.x.x.", "x.....", "x...x."))
    hands = {sec: _compound_cells(rng, pulses, cells) for sec in dna.hand_patterns}
    trains = {sec: _compound_cells(rng, pulses, ("x.x.x.", "....x.", "x.....", "......"))
              for sec in dna.train_patterns}
    snare_pattern = _compound_cells(rng, pulses, ("x.x.x.", "....x.", "x.....", "......")) \
        if dna.snare_pattern else ""
    opens = [p * 6 + 4 for p in range(pulses)]
    open_steps = tuple(sorted(rng.sample(opens, min(len(opens), len(dna.open_hat_steps)))))
    fills = {"small": _compound_fill(dna.fills["small"], 1),
             "medium": _compound_fill(dna.fills["medium"], 1 if pulses <= 2 else 2),
             "big": _compound_fill(dna.fills["big"], pulses)}
    if dna.idiom == "country":
        # Country fills stay on the snare, a touch lighter (as in 4/4).
        fills = {n: replace(f, hits=tuple((t, "snare", v * .8) for t, _, v in f.hits))
                 for n, f in fills.items()}
    elif dna.idiom == "reggae":
        fills = {n: replace(f, beats=min(f.beats, 1.5),
                            hits=tuple((t, v, vel * .8) for t, v, vel in f.hits if t < 1.5))
                 for n, f in fills.items()}
    return replace(dna, meter=key, kick_verse=kick_verse, kick_chorus=kick_chorus,
                   hand_patterns=hands, train_patterns=trains, snare_pattern=snare_pattern,
                   open_hat_steps=open_steps, rim_pickups={}, fills=fills)


# --- feel knobs ----------------------------------------------------------------

def _hand_density(pattern: str, feel: str, unit: int = 4) -> str:
    """An idiom hand pattern thinned to its beats (pulses) or filled out to
    eighths."""
    if feel == "dense":
        return "".join("x" if (c == "x" or i % 2 == 0) else "." for i, c in enumerate(pattern))
    if feel == "sparse":
        return "".join("x" if i % unit == 0 else "." for i in range(len(pattern)))
    return pattern


def _kick_feel(kick: str, feel: str, unit: int, snare_steps: set) -> str:
    """The kick_density knob on one bar's kick. Dense adds the last eighth
    of every beat (pulse) that carries no backbeat; sparse keeps the
    downbeat and the bar's middle beat."""
    if feel not in ("dense", "sparse"):
        return kick
    beats = max(1, len(kick) // unit)
    backbeat = {s // unit for s in snare_steps}
    out = list(kick)
    if feel == "dense":
        for b in range(beats):
            if b not in backbeat:
                out[b * unit + unit - 2] = "x"
        return "".join(out)
    keep = {0} | ({(beats // 2) * unit} if (beats // 2) not in backbeat else set())
    return "".join("x" if i in keep else "." for i in range(len(kick)))


def apply_feel_knobs(dna: DrumDNA, ghost_rate=None, fill_rate=None, kick_density=None,
                     hat_density=None) -> DrumDNA:
    """The drum feel knobs on the composed drummer, in every section.
    ``hat_density`` puts every section's hands on quarter-note hi-hats
    (pulses in 6/8 and 12/8) below 0.3 and on sixteenths above 0.8 (the
    jazz ride on quarters or skip notes every beat; dance hats on the
    offbeat or sixteenths). ``kick_density`` thins every section's kick to
    1 and 3 below 0.3 and adds offbeat kicks above 0.7. Values between leave
    the drummer as drawn."""
    if ghost_rate is not None:
        g = float(ghost_rate)
        dna = replace(dna, ghosts="none" if g <= 0.05 else ("light" if g < 0.3 else "busy"))
    if fill_rate is not None:
        f = float(fill_rate)
        dna = replace(dna, fill_every=4 if f >= 0.5 else 8,
                      small_fill_every=2 if f >= 0.75 else (0 if f < 0.25 else dna.small_fill_every))
    if kick_density is not None:
        k = float(kick_density)
        if k >= 0.7 or k <= 0.3:
            dense = k >= 0.7
            styles = {sec: (("four_floor" if dna.idiom == "country" else "steppers") if dense
                            else ("two_beat" if dna.idiom == "country" else "one_drop"))
                      for sec in dna.kick_styles}
            dna = replace(dna, kick_feel="dense" if dense else "sparse", kick_styles=styles)
            if dna.jazz is not None:
                dna = replace(dna, jazz=replace(dna.jazz, feather=.45 if dense else 0.0,
                                                bombs=.35 if dense else 0.0))
            if dna.dance is not None:
                # Four on the floor stays; the knob sets the pickup kick and
                # whether breakdowns keep a half-time pulse.
                dna = replace(dna, dance=replace(dna.dance, pickup_kick=dense,
                                                 breakdown="half_kick" if dense else "no_kick"))
            if dna.waltz is not None:
                kick = {sec: "x.......x..." if dense else "x..........." for sec in dna.waltz.kick}
                dna = replace(dna, waltz=replace(dna.waltz, kick=kick))
    if hat_density is not None:
        h = float(hat_density)
        if h >= 0.8 or h <= 0.3:
            dense = h >= 0.8
            grooves = {sec: ("hat16" if dense else "hat4", bb) for sec, (tk, bb) in dna.grooves.items()}
            # Country hands give way to the timekeeper itself (as before);
            # other idioms keep their figure, thinned or filled out.
            dna = replace(dna, grooves=grooves, hand_feel="dense" if dense else "sparse",
                          hand_patterns={} if dna.idiom == "country" else dna.hand_patterns)
            if dna.jazz is not None:
                dna = replace(dna, jazz=replace(dna.jazz, ride={
                    sec: "spang_every" if dense else "quarters" for sec in dna.jazz.ride}))
            if dna.dance is not None:
                dna = replace(dna, dance=replace(dna.dance, hats={
                    sec: "closed16_open" if dense else "open_off" for sec in dna.dance.hats}))
            if dna.waltz is not None:
                hands_w = dict(dna.waltz.hands)
                timekeeper = dict(dna.waltz.timekeeper)
                for sec in set(hands_w) | set(timekeeper):
                    hands_w[sec] = "xxxxxxxxxxxx" if dense else "x...x...x..."
                    timekeeper[sec] = "hat16" if dense else "hat4"
                dna = replace(dna, waltz=replace(dna.waltz, hands=hands_w, timekeeper=timekeeper))
    return dna


def feel_values(dna: DrumDNA, groups=None) -> Dict[str, float]:
    """The drummer's feel as groove-clock values. A straight, laid-back or
    pushing drummer plays even eighths, so the band does too: recipe and
    persona swing do not outrank the drummer (explicit swing still does).
    Compound meters are already in triplets and are never swung."""
    even = {"swing": 0.0, "swing_16th": 0.0}
    values = dict({"straight": even, "laid_back": dict(even, push_pull=-0.08),
                   "push": dict(even, push_pull=0.06), "shuffle": {"swing": 0.62, "swing_16th": 0.31},
                   "swing16": {"swing": 0.0, "swing_16th": 0.18}}.get(dna.feel, even))
    if is_compound(groups):
        values.update(swing=0.0, swing_16th=0.0)
    return values


def section_level(intensity: Optional[float], energy: Optional[float]) -> float:
    """Velocity scale for a section's dynamics: a verse at the default
    intensity (0.65) and energy (0.3) plays at 1.0, a default chorus (0.9,
    0.9) about a quarter louder, and escalating repeats climb with the
    planner's +0.05 per repeat."""
    i = 0.65 if intensity is None else float(intensity)
    e = 0.3 if energy is None else float(energy)
    return max(0.55, min(1.35, 1.0 + 0.6 * (i - 0.65) + 0.15 * (e - 0.3)))


_ALIASES = {"pre-chorus": "prechorus", "pre_chorus": "prechorus", "hook": "chorus",
            "interlude": "bridge", "lead": "solo"}


def plan_drum_section(dna: DrumDNA, arrangement: ArrangementDNA, *, section_type: str,
                      bars: int, beats_per_bar: float, occurrence: int = 0,
                      next_section_type: Optional[str] = None,
                      prev_section_type: Optional[str] = None,
                      is_first_section: bool = False,
                      groups: Optional[Sequence[float]] = None, solo: bool = False, fills_enabled: bool = True) -> List[DrumHit]:
    """Arrange one section of drums from the song's DNA."""
    st = _ALIASES.get(str(section_type or "verse").lower(), str(section_type or "verse").lower())
    bpb = float(beats_per_bar)
    dna = for_meter(dna, bpb, groups)
    compound = is_compound(groups)
    unit = 6 if compound else 4          # sixteenths per beat (per dotted quarter in 6/8, 12/8)
    tk, backbeat = dna.grooves.get(st, dna.grooves.get("verse", ("hat8", "backbeat")))
    kick = dna.kick_chorus if st in ("chorus", "solo", "outro") else dna.kick_verse
    beats = max(1, int(round(bpb)))
    steps = max(1, int(round(bpb * 4)))
    kick = (kick * 4)[:steps]
    if dna.idiom == "country" and groups and bpb != 4:
        kick = _idiom_kick("two_beat", bpb, groups)
    if st in dna.kick_styles:
        kick = _idiom_kick(dna.kick_styles[st], bpb, groups)
    train = dna.train_patterns.get(st, dna.snare_pattern)
    prev = _ALIASES.get(str(prev_section_type or "").lower(), str(prev_section_type or "").lower())
    pushed_in = st == "chorus" and prev not in ("", "chorus") and arrangement.into_chorus == "push"
    nxt = _ALIASES.get(str(next_section_type or "").lower(), str(next_section_type or "").lower())
    into_chorus = nxt == "chorus" and st != "chorus"
    device = arrangement.into_chorus if into_chorus else "fill"
    hits: List[DrumHit] = []
    voice, offsets = (COMPOUND_TIMEKEEPERS if compound else TIMEKEEPERS).get(
        tk, (COMPOUND_TIMEKEEPERS if compound else TIMEKEEPERS)["hat8"])
    snare_steps = _snare_steps(backbeat, beats, steps, groups)
    if st not in dna.kick_styles:
        kick = _kick_feel(kick, dna.kick_feel, unit, snare_steps)
    from .country import is_waltz

    snare_voice, foot, hand_touch = "snare", False, 1.0
    waltz = dna.waltz is not None and is_waltz(bpb, groups)
    if waltz:
        # The drummer's own waltz: kick on 1 (maybe a pickup on the "and"
        # of 3), snare "pah-pah" on 2 and 3 or a lighter touch, and a
        # timekeeper figure of their own. No ghost notes: the space between
        # the "pah"s is the waltz.
        kick = dna.waltz.part(dna.waltz.kick, st)
        snare_steps = set(dna.waltz.part(dna.waltz.snare, st))
        tk = dna.waltz.part(dna.waltz.timekeeper, st)
        voice, offsets = TIMEKEEPERS[tk]
        hand_touch = dna.waltz.part(dna.waltz.touch, st)
        path = {"snare": ("snare", "snare", "snare", "snare"),
                "toms": ("tom_high", "tom_mid", "tom_low", "tom_low"),
                "mixed": ("snare", "tom_high", "snare", "tom_low")}[dna.waltz.fill]
        fills = {name: Fill("waltz_" + name, beats,
                 tuple((i*.5, path[i], .65 + .08*i) for i in range(int(beats*2))))
                 for name, beats in (("small", 1), ("medium", 1), ("big", 2))}
        dna = replace(dna, ghosts="none", two_bar=False, rim_pickups={}, fills=fills,
                      open_hat_steps=(8,),
                      hand_patterns=dict(dna.hand_patterns, **{st: dna.waltz.part(dna.waltz.hands, st)}))
        train = ""
        snare_voice = dna.waltz.part(dna.waltz.snare_voice, st)
        foot = dna.waltz.part(dna.waltz.foot, st)
    hand = dna.hand_patterns.get(st)
    if hand and not waltz:
        hand = _hand_density(hand, dna.hand_feel, unit)
    enter = intro_entry_bar(arrangement, st, bars, is_first_section)
    # A dance prechorus that builds by itself needs no separate build bar.
    self_building = (dna.dance is not None and st == "prechorus"
                     and dna.dance.prechorus == "build" and bars >= 2)
    build_n = 0
    if device == "build" and next_section_type is not None and fills_enabled and not self_building:
        build_n = max(1, min(dna.build_bars, bars - enter - 1)) if bars - enter >= 2 else 1
    build_from = (bars - build_n) * bpb
    for b in range(bars):
        start = b * bpb
        last = b == bars - 1
        if b < enter:
            # Riff-alone intro: the guitar plays by itself; the drums come in
            # with a fill at the end of the bar before they enter.
            if b == enter - 1 and fills_enabled:
                fill = dna.fills["medium"]
                hits += [DrumHit(start + bpb - fill.beats + off, v, vel, "fill")
                         for off, v, vel in fill.hits]
            continue
        if b == enter and enter > 0:
            hits.append(DrumHit(start, "crash", 1.15, "crash", 1.0))
            hits.append(DrumHit(start, "kick", 1.1, "kick"))
        phrase_end = (b + 1) % dna.fill_every == 0 and not last
        small = dna.small_fill_every and (b + 1) % dna.small_fill_every == 0 and not phrase_end \
            and not last
        building = build_n > 0 and b >= bars - build_n
        fill: Optional[Fill] = None
        if last and next_section_type is not None:
            # A build is its own device (below), not a fill.
            fill = None if device in ("stop", "drop", "push", "build") else (
                dna.fills["big"] if device == "fill" else dna.fills["medium"])
        elif building:
            fill = None
        elif phrase_end:
            fill = dna.fills["medium"] if dna.fill_every <= 4 else dna.fills["big"]
        elif small:
            fill = dna.fills["small"]
        if not fills_enabled:
            fill = None
        fill_from = start + bpb - fill.beats if fill else start + bpb
        # Crash: every section start, and the song's phrase crash.
        crash = ((b == 0 or b % dna.crash_every == 0) if dna.crash_policy == "regular" else
                 b == 0 and (dna.crash_policy == "section" or
                             dna.crash_policy == "chorus" and st in ("chorus", "solo")))
        if crash:
            # A pushed chorus already crashed on the "and" before its downbeat.
            if not (b == 0 and pushed_in) and not (
                    is_first_section and b == 0 and st == "intro" and arrangement.intro == "riff_alone"):
                hits.append(DrumHit(start, "crash", 1.1, "crash", 1.0))
        if last and device == "stop" and next_section_type is not None:
            # Stop-time: hit with the band on 1, silence, a snare pickup.
            hits += [DrumHit(start, "kick", 1.1, "kick"), DrumHit(start, "crash", 1.1, "crash", 1.0),
                     DrumHit(start + bpb - 0.5, "snare", 0.8, "snare_pickup"),
                     DrumHit(start + bpb - 0.25, "snare", 1.0, "snare_pickup")]
            continue
        if last and device == "drop" and next_section_type is not None:
            hits.append(DrumHit(start + bpb - 1.0, "snare", 0.9, "snare_pickup"))
            hits.append(DrumHit(start + bpb - 0.5, "tom_low", 1.0, "tom_pickup"))
            continue
        if dna.jazz is not None:
            bar_rng = random.Random(stable_seed_int("composer.drums.jazz.bar", *dna.seed_key,
                                                    st, occurrence, b))
            bar_hits = _jazz_bar(dna, st, start, bpb, groups, bar_rng, fill_from)
        elif dna.dance is not None:
            bar_hits = _dance_bar(dna, st, b, bars, start, bpb, groups, snare_steps, fill_from)
        else:
            bar_hits = _groove_bar(dna, st, b, start, steps, beats, unit, compound, fill_from, fill,
                                   tk, voice, offsets, hand, hand_touch, kick, backbeat, snare_steps,
                                   snare_voice, train, foot, waltz)
        if building:
            bar_hits = _build_bar(bar_hits, start, bpb, build_from, bars * bpb, groups)
        hits += bar_hits
        if fill:
            for off, v, vel in fill.hits:
                hits.append(DrumHit(fill_from + off, v, vel, "fill"))
        if last and next_section_type is not None and into_chorus and dna.dance is not None \
                and device in ("build", "fill"):
            # The dance drop: the kick sits out the beat before the chorus.
            gap = start + bpb - (1.5 if compound else 1.0)
            hits = [h for h in hits if not (h.voice == "kick" and h.beat >= gap - 1e-6)]
        if last and device == "push" and next_section_type is not None:
            # Push: the band anticipates the chorus downbeat by an eighth and
            # lets it ring into the chorus.
            push = start + bpb - 0.5
            hits = [h for h in hits if h.beat < push - 1e-6]
            hits.append(DrumHit(push, "crash", 1.15, "crash", 1.5))
            hits.append(DrumHit(push, "kick", 1.1, "kick"))
    if next_section_type is None and bars > 0:
        end = bars * bpb
        last = end - bpb
        hits = [h for h in hits if h.beat < last + 1e-6]
        ending = arrangement.ending
        if ending == "cold":
            # Everyone stops on the downbeat; the crash is choked.
            hits += [DrumHit(last, "crash", 1.15, "crash", 0.25), DrumHit(last, "kick", 1.1, "kick")]
        elif ending == "big" and fills_enabled:
            # The big rock finish: a hit, a roll that swells, a last crash.
            hits += [DrumHit(last, "crash", 1.15, "crash", 1.0), DrumHit(last, "kick", 1.1, "kick")]
            n = int(round((bpb - 1.0) * 4))
            path = ("snare", "snare", "tom_high", "tom_mid", "tom_low")
            for k in range(n):
                hits.append(DrumHit(last + 0.5 + k * 0.25, path[min(len(path) - 1, k * len(path) // max(1, n))],
                                    0.55 + 0.6 * k / max(1, n), "fill"))
            hits += [DrumHit(end - 0.5, "crash", 1.2, "crash", 0.5),
                     DrumHit(end - 0.5, "kick", 1.15, "kick")]
        else:
            hits += [DrumHit(last, "crash", 1.15, "crash", bpb), DrumHit(last, "kick", 1.1, "kick")]
    if dna.idiom == "country":
        hits = [replace(h, vel=h.vel*dna.snare_gain) if h.voice in ("snare", "cross_stick") else h for h in hits]
    if dna.idiom and dna.idiom != "dance":
        hits = [replace(h, voice=dna.accent_voice, vel=h.vel*.8) if h.voice == "crash" else h
                for h in hits if h.voice != "crash" or dna.crash_policy != "none"]
    if solo:
        hits = solo_development(hits, dna, bars, bpb, next_section_type is None)
    return sorted(hits, key=lambda h: (h.beat, h.voice))


def _groove_bar(dna: DrumDNA, st: str, b: int, start: float, steps: int, beats: int, unit: int,
                compound: bool, fill_from: float, fill: Optional[Fill], tk: str, voice: str,
                offsets, hand: Optional[str], hand_touch: float, kick: str, backbeat: str,
                snare_steps: set, snare_voice: str, train: str, foot: bool,
                waltz: bool) -> List[DrumHit]:
    """One bar of the song's groove: right hand, kick, backbeat, ghosts."""
    hits: List[DrumHit] = []
    for s in range(steps):
        t = start + s * 0.25
        if t >= fill_from - 1e-6:
            break
        beat_i, sub = divmod(s, unit)
        # Right hand.
        hand_hit = hand[s % len(hand)] == "x" if hand else sub in offsets
        if hand_hit and not (voice == "crash" and b == 0 and s == 0):
            if compound:
                v = 1.0 if sub == 0 else (0.72 if sub % 2 == 0 else 0.58)
            else:
                v = 1.0 if sub == 0 else (0.72 if sub == 2 else 0.58)
            name = voice
            if tk == "hat8_open" and s in dna.open_hat_steps:
                name = "hat_open"
            if waltz and tk == "ride_bell" and s == 0 or compound and tk == "ride_bell" and sub == 0:
                name = "ride_bell"
            hits.append(DrumHit(t, name, v*hand_touch, "hat" if "hat" in name else name))
        if tk == "ride_bell" and sub == 2 and not waltz and not compound:
            hits.append(DrumHit(t, "ride_bell", 0.8, "ride"))
        if foot and s in snare_steps:
            hits.append(DrumHit(t, "hat_pedal", 0.6, "hat"))
        # Kick.
        if backbeat == "one_drop" and s in snare_steps:
            hits.append(DrumHit(t, "kick", 1.0, "kick"))
        if kick[s] == "x" and (s not in snare_steps or dna.idiom in ("country", "reggae")):
            hits.append(DrumHit(t, "kick", 1.0 if sub == 0 else 0.9, "kick"))
        elif backbeat == "stomp" and sub == 0:
            hits.append(DrumHit(t, "kick", 1.0, "kick"))
        # Snare and ghosts.
        if s in snare_steps:
            hits.append(DrumHit(t, snare_voice, 1.05, "snare"))
        elif backbeat == "train" and train and train[s % len(train)] == "x":
            hits.append(DrumHit(t, "snare", .4 if sub == 0 else .3, "snare_train"))
        elif (s in dna.rim_pickups.get(st, ()) and b % 2 == 1) or _ghost(
                dna.ghosts, s, b, snare_steps, 2 if compound else 1):
            hits.append(DrumHit(t, "snare", 0.32, "snare_ghost"))
        # Two-bar groove: the second bar's last beat answers.
        last_beat = (steps // unit - 1) if compound else beats - 1
        if dna.two_bar and b % 2 == 1 and beat_i == last_beat and sub == unit - 2 and not fill:
            hits.append(DrumHit(t, "kick", 0.9, "kick_extra"))
    return hits


def _build_bar(bar_hits: List[DrumHit], start: float, bpb: float, roll_from: float,
               roll_to: float, groups) -> List[DrumHit]:
    """A build into the chorus: a snare roll that crescendos from eighths to
    sixteenths over the last bar or two. The groove's backbeat and ghosts
    give way to the roll; in the sixteenth half the roll takes both hands
    and the kick marks every beat (every pulse in compound meters)."""
    half = (roll_from + roll_to) / 2
    span = max(1e-6, roll_to - roll_from)
    kept = [h for h in bar_hits
            if h.beat < half - 1e-6 and h.voice not in ("snare", "cross_stick", "clap")
            and not h.kind.startswith("snare")]
    t = start
    while t < start + bpb - 1e-6:
        kept.append(DrumHit(t, "snare", round(.45 + .7 * (t - roll_from) / span, 3), "snare_build"))
        t += .5 if t < half - 1e-6 else .25
    pulse = 1.5 if is_compound(groups) else 1.0
    k = start
    while k < start + bpb - 1e-6:
        if k >= half - 1e-6:
            kept.append(DrumHit(k, "kick", 1.0, "kick"))
        k += pulse
    return kept


def _ghost(style: str, step: int, bar: int, snare_steps: set, span: int = 1) -> bool:
    """Light: a grace "a" before the backbeat on alternate bars. Busy: that
    grace every bar plus an "e" after the backbeat. Compound meters place
    them an eighth (``span`` 2) either side."""
    before = (step + span) in snare_steps
    after = (step - span) in snare_steps
    if style == "light":
        return before and bar % 2 == 1
    if style == "busy":
        return before or after
    return False


def _snare_steps(backbeat: str, beats: int, steps: int,
                 groups: Optional[Sequence[float]] = None) -> set:
    """Backbeat positions (sixteenth steps). Simple meters: beats 2 and 4
    (or the middle of the bar for half-time). Compound meters: the even
    dotted-quarter pulses (12/8 on pulses 2 and 4, 6/8 on its "4");
    half-time 12/8 on pulse 3. Other grouped meters: the start of every
    group after the first (7/8 on its 2+2+3 starts)."""
    if is_compound(groups):
        pulses = len(groups)
        if backbeat == "halftime" and pulses >= 4:
            return {int(round(pulses // 2 * 6))}
        return {p * 6 for p in range(pulses) if p % 2 == 1} or {(pulses - 1) * 6}
    if groups and tuple(groups) not in ((2.0, 2.0),) and not all(g == 1.0 for g in groups):
        starts, t = [], 0.0
        for g in groups[:-1]:
            t += g
            starts.append(int(round(t * 4)))
        if backbeat == "halftime":
            return {starts[len(starts) // 2]} if starts else {steps // 2}
        return set(starts) or {steps // 2}
    if backbeat in ("one_drop", "rockers", "steppers"):
        return {steps // 2}
    if backbeat.startswith("jazz:"):
        return {i for i, c in enumerate(backbeat[5:]) if c == "x" and i < steps}
    if backbeat == "halftime":
        return {((beats // 2) * 4) if beats >= 3 else 4}
    return {b * 4 for b in range(beats) if b % 2 == 1} or {(beats - 1) * 4}


_HAND_KINDS = ("hat", "ride", "tom_low", "snare_ghost")


def solo_development(hits, dna, bars, bpb, closing):
    """Solo drums develop a four-bar phrase: statement, answer, a stronger
    statement, and a response. The groove keeps time in every bar (kick,
    backbeat, the hands). The answer bar and the phrase's last bar answer
    on their last beat: the hands there move around the toms
    (a tom pair where the hands rest), unless a fill already answers."""
    voices = [v for _, v, _ in dna.fills["big"].hits if v.startswith("tom")]
    answer = tuple(dict.fromkeys(voices)) or ("tom_high", "tom_low")
    window = 1.0
    out = []
    for h in hits:
        bar = int(h.beat // bpb)
        phase = bar % 4
        if closing and bar == bars - 1:
            out.append(h)
            continue
        voice, kind = h.voice, h.kind
        pos = h.beat - bar * bpb
        if phase in (1, 3) and pos >= bpb - window - 1e-6 and h.kind in _HAND_KINDS \
                and h.voice != "hat_pedal":
            voice = answer[(int((pos - (bpb - window)) * 4) + bar // 4) % len(answer)]
            kind = "solo_answer"
        gain = (0.82, 0.9, 1.04, 0.94)[phase]
        out.append(replace(h, voice=voice, kind=kind, vel=h.vel * gain))
    # An answer bar whose last beat had no hands (quarter-note or pedal
    # timekeepers) still answers: two sixteenths down the toms.
    for bar in (b for b in range(bars) if b % 4 in (1, 3)):
        if closing and bar == bars - 1:
            continue
        end = (bar + 1) * bpb
        if any(end - window - 1e-6 <= h.beat < end and h.kind in ("solo_answer", "fill")
               for h in out):
            continue
        out += [DrumHit(end - .5, answer[0], .8, "solo_answer"),
                DrumHit(end - .25, answer[-1], .9, "solo_answer")]
    return out
