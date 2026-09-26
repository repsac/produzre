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
"""

from __future__ import annotations

import random
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
    rim_pickups: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    crash_policy: str = "regular"
    accent_voice: str = "crash"
    idiom: str = ""
    signature: str = ""


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


def _make_fill(rng: random.Random, beats: float, name: str) -> Fill:
    rhythm = rng.choice(list(_FILL_RHYTHMS))
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
            vel = 0.7 + 0.35 * (k / max(1, total - 1))   # crescendo into the downbeat
            if voice == "unison":
                hits.append((offset, "snare", vel))
                hits.append((offset, "kick", vel))
            else:
                hits.append((offset, voice, vel))
                if rhythm == "flam8" and voice == "snare":
                    hits.append((max(0.0, offset - 0.06), "snare", vel * 0.5))
            k += 1
    return Fill(f"{name}:{rhythm}/{path_name}", float(n_beats), tuple(hits))


def compose_drum_dna(*, seed: int, genre: str, beats_per_bar: float = 4.0) -> DrumDNA:
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
        dna.kick_verse = "x..." * beats
        dna.kick_chorus = dna.kick_verse
        dna.grooves = {sec: (rng.choice(("ride8", "ride_bell", "hat4", "hat8_open")),
                            "jazz:" + "".join(rng.choice(("....", "..x.", "x...", "...x"))
                                             for _ in range(beats))) for sec in _POOLS}
        dna.kick_verse = "".join(rng.choice(("x...", "....", "....")) for _ in range(beats))
        dna.kick_chorus = "".join(rng.choice(("x...", "....")) for _ in range(beats))
        dna.feel = "shuffle"
    if dna.idiom:
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
    tk, backbeat = dna.grooves.get(st, dna.grooves.get("verse", ("hat8", "backbeat")))
    kick = dna.kick_chorus if st in ("chorus", "solo", "outro") else dna.kick_verse
    bpb = float(beats_per_bar)
    beats = max(1, int(round(bpb)))
    steps = max(1, int(round(bpb * 4)))
    kick = (kick * 4)[:steps]
    if st in dna.kick_styles:
        kick = _idiom_kick(dna.kick_styles[st], bpb, groups)
    train = dna.train_patterns.get(st, dna.snare_pattern)
    prev = _ALIASES.get(str(prev_section_type or "").lower(), str(prev_section_type or "").lower())
    pushed_in = st == "chorus" and prev not in ("", "chorus") and arrangement.into_chorus == "push"
    nxt = _ALIASES.get(str(next_section_type or "").lower(), str(next_section_type or "").lower())
    into_chorus = nxt == "chorus" and st != "chorus"
    device = arrangement.into_chorus if into_chorus else "fill"
    hits: List[DrumHit] = []
    voice, offsets = TIMEKEEPERS.get(tk, TIMEKEEPERS["hat8"])
    snare_steps = _snare_steps(backbeat, beats, steps, groups)
    enter = intro_entry_bar(arrangement, st, bars, is_first_section)
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
        fill: Optional[Fill] = None
        if last and next_section_type is not None:
            fill = None if device in ("stop", "drop", "push") else (
                dna.fills["big"] if device in ("fill", "build") else dna.fills["medium"])
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
        for s in range(steps):
            t = start + s * 0.25
            if t >= fill_from - 1e-6:
                break
            beat_i, sub = divmod(s, 4)
            # Right hand.
            hand = dna.hand_patterns.get(st)
            hand_hit = hand[s % len(hand)] == "x" if hand else sub in offsets
            if hand_hit and not (voice == "crash" and b == 0 and s == 0):
                v = 1.0 if sub == 0 else (0.72 if sub == 2 else 0.58)
                name = voice
                if tk == "hat8_open" and s in dna.open_hat_steps:
                    name = "hat_open"
                hits.append(DrumHit(t, name, v, "hat" if "hat" in name else name))
            if tk == "ride_bell" and sub == 2:
                hits.append(DrumHit(t, "ride_bell", 0.8, "ride"))
            # Kick.
            if backbeat == "one_drop" and s in snare_steps:
                hits.append(DrumHit(t, "kick", 1.0, "kick"))
            if kick[s] == "x" and (s not in snare_steps or dna.idiom in ("country", "reggae")):
                hits.append(DrumHit(t, "kick", .45 if backbeat.startswith("jazz") else 1.0 if sub == 0 else 0.9, "kick"))
            elif backbeat == "stomp" and sub == 0:
                hits.append(DrumHit(t, "kick", 1.0, "kick"))
            # Snare and ghosts.
            if s in snare_steps:
                hits.append(DrumHit(t, "snare", 1.05, "snare"))
            elif backbeat == "train" and train and train[s % len(train)] == "x":
                hits.append(DrumHit(t, "snare", .4 if sub == 0 else .3, "snare_train"))
            elif (s in dna.rim_pickups.get(st, ()) and b % 2 == 1) or _ghost(dna.ghosts, s, b, snare_steps):
                hits.append(DrumHit(t, "snare", 0.32, "snare_ghost"))
            # Two-bar groove: the second bar's last beat answers.
            if dna.two_bar and b % 2 == 1 and beat_i == beats - 1 and sub == 2 and not fill:
                hits.append(DrumHit(t, "kick", 0.9, "kick_extra"))
        if fill:
            for off, v, vel in fill.hits:
                hits.append(DrumHit(fill_from + off, v, vel, "fill"))
        if last and device == "build" and next_section_type is not None and fills_enabled:
            # Build: snare eighths through the bar under the fill's crescendo.
            for k in range(int(bpb * 2)):
                t = start + k * 0.5
                if t < fill_from:
                    hits.append(DrumHit(t, "snare", 0.55 + 0.5 * k / (bpb * 2), "snare_build"))
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
    if dna.idiom:
        hits = [replace(h, voice=dna.accent_voice, vel=h.vel*.8) if h.voice == "crash" else h
                for h in hits if h.voice != "crash" or dna.crash_policy != "none"]
    if solo:
        hits = solo_development(hits, dna, bars, bpb, next_section_type is None)
    return sorted(hits, key=lambda h: (h.beat, h.voice))


def _ghost(style: str, step: int, bar: int, snare_steps: set) -> bool:
    """Light: a grace "a" before the backbeat on alternate bars. Busy: that
    grace every bar plus an "e" after the backbeat."""
    before = (step + 1) in snare_steps
    after = (step - 1) in snare_steps
    if style == "light":
        return before and bar % 2 == 1
    if style == "busy":
        return before or after
    return False


def _snare_steps(backbeat: str, beats: int, steps: int,
                 groups: Optional[Sequence[float]] = None) -> set:
    """Backbeat positions (sixteenth steps). Simple meters: beats 2 and 4
    (or the middle of the bar for half-time). Grouped meters: the start of
    every group after the first (6/8 on the "4", 7/8 on its 2+2+3 starts)."""
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


def solo_development(hits, dna, bars, bpb, closing):
    """Keep the foot pulse while a recurring hand motif moves around the kit."""
    out = []
    voices = [v for _, v, _ in dna.fills["big"].hits if v.startswith("tom")]
    answer = tuple(dict.fromkeys(voices)) or ("tom_high", "tom_low")
    for h in hits:
        bar = int(h.beat // bpb)
        phase = bar % 4
        if closing and bar == bars - 1:
            out.append(h)
            continue
        # Statement, answer, stronger statement, response. The motif's
        # rhythm survives the orchestration change and foot time continues.
        voice, kind = h.voice, h.kind
        if phase in (1, 3) and h.kind == "snare":
            voice = answer[(int(h.beat % bpb) + bar // 4) % len(answer)]
            kind = "solo_answer"
        gain = (0.82, 0.9, 1.04, 0.94)[phase]
        out.append(replace(h, voice=voice, kind=kind, vel=h.vel * gain))
    return out
