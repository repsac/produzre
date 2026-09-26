"""Shared country direction, with independent player streams inside each style."""
import random
from dataclasses import dataclass
from typing import Dict, Tuple

from ..rng import stable_seed_int

STYLES = ("honky_tonk", "bakersfield", "outlaw", "two_step", "ballad", "country_rock")


def country_style(seed, genre, pinned=None):
    if "country" not in str(genre).lower():
        return ""
    if pinned in STYLES:
        return pinned
    hinted = style_hint(genre)
    if hinted:
        return hinted
    return random.Random(stable_seed_int("composer.country.style", seed)).choice(STYLES)


COMP_FAMILIES = {
    "honky_tonk": ("carter", "chucks", "carter", "hybrid"),
    "bakersfield": ("low_strings", "carter", "hybrid", "low_strings"),
    "outlaw": ("train", "low_strings", "chucks", "train"),
    "two_step": ("offbeats", "chucks", "offbeats", "hybrid"),
    "ballad": ("arp", "arp", "carter", "hybrid"),
    "country_rock": ("strum", "low_strings", "strum", "train"),
}

LICK_FAMILIES = {
    "honky_tonk": ("chicken", "thirds", "chromatic", "travis"),
    "bakersfield": ("chicken", "hybrid", "sixths", "chromatic"),
    "outlaw": ("travis", "banjo", "chicken", "hybrid"),
    "two_step": ("thirds", "sixths", "chicken", "banjo"),
    "ballad": ("steel", "steel", "sixths", "hybrid"),
    "country_rock": ("chicken", "banjo", "hybrid", "steel"),
}


# Genre names that already say which country the song is. A pinned
# ``country_style`` still wins; a plain "country" draws a style.
_HINTS = (("honky", "honky_tonk"), ("bakersfield", "bakersfield"), ("outlaw", "outlaw"),
          ("two_step", "two_step"), ("texas", "two_step"), ("dance_hall", "two_step"),
          ("ballad", "ballad"), ("country_rock", "country_rock"), ("rock", "country_rock"),
          ("modern", "country_rock"), ("southern", "country_rock"))


def style_hint(genre):
    g = str(genre or "").lower().replace("-", "_").replace(" ", "_")
    return next((style for word, style in _HINTS if word in g), None)


def is_waltz(bpb, groups=None):
    """Three quarter-note beats to the bar (not 6/8 or another grouping)."""
    try:
        return float(bpb) == 3.0 and tuple(float(g) for g in (groups or (1, 1, 1))) == (1.0, 1.0, 1.0)
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class WaltzPlayer:
    """How one band plays a country waltz: bass on 1, the band on 2 and 3,
    and each part's own way of doing it. Keyed by section type."""

    bass_alternation: str          # bar (root/fifth by bar) | change (fifth on a held chord) | root
    walk_every: int                # walk into 1 of 1, 2 or 4 (phrase end) chord changes
    walk_style: str                # diatonic | chromatic
    bass: Dict[str, Tuple[float, bool]]   # section -> (bass note length, walks)
    comp: Dict[str, str]           # section -> guitar figure (see WALTZ_FIGURES)
    kick: Dict[str, str]           # section -> 12-step kick
    snare: Dict[str, Tuple[int, ...]]     # section -> snare steps
    hands: Dict[str, str]          # section -> 12-step timekeeper
    snare_voice: Dict[str, str]    # section -> snare | cross_stick
    foot: Dict[str, bool]          # section -> foot hi-hat on 2 and 3

    def part(self, table, section_type):
        st = str(section_type or "verse").lower()
        if st in table:
            return table[st]
        return table["chorus" if st in ("solo", "outro", "hook") else "verse"]


# The guitar's bar: (beat, dur, kind, arp_index). "B" is the bass note on 1.
WALTZ_FIGURES = {
    "pah_pah": ((0, .65, "B", 0), (1, .65, "strum", 0), (2, .65, "strum", 0)),
    "choked": ((0, .8, "B", 0), (1, .3, "strum", 0), (2, .3, "strum", 0)),
    "pah_up": ((0, .65, "B", 0), (1, .45, "strum", 0), (1.5, .3, "up", 0),
               (2, .45, "strum", 0), (2.5, .3, "up", 0)),
    "sixths": ((0, .8, "B", 0), (1, .6, "dyad6", 0), (2, .6, "dyad6", 0)),
    "arp": ((0, .9, "B", 0), (1, .45, "arp", 1), (1.5, .45, "arp", 2), (2, .45, "arp", 3),
            (2.5, .45, "arp", 2)),
    "ring": ((0, 2.9, "strum", 0), (2, .9, "arp", 3)),
}

_WALTZ_COMP_ODDS = {
    "honky_tonk": {"pah_pah": 4, "choked": 3, "pah_up": 3, "sixths": 2},
    "bakersfield": {"choked": 4, "pah_pah": 3, "sixths": 3, "pah_up": 1},
    "outlaw": {"pah_pah": 3, "choked": 3, "arp": 2, "ring": 1},
    "two_step": {"pah_up": 4, "choked": 3, "sixths": 3, "pah_pah": 1},
    "ballad": {"arp": 4, "ring": 3, "sixths": 2, "pah_pah": 1},
    "country_rock": {"pah_pah": 3, "pah_up": 3, "ring": 2, "choked": 2},
}

_SECTIONS = ("verse", "chorus", "bridge", "prechorus")


def _pick(rng, weights):
    items = sorted(weights.items())
    draw = rng.random() * sum(w for _, w in items)
    for name, w in items:
        draw -= w
        if draw <= 0:
            return name
    return items[-1][0]


def waltz_player(seed, style):
    """Seeded on its own stream, so 4/4 country and other meters are unchanged."""
    rng = random.Random(stable_seed_int("composer.country.waltz", seed, style))
    lengths = (2.9, 1.9, 1.9) if style == "ballad" else (.9, 1.9, 2.9)
    bass, comp, kick, snare, hands, voice, foot = {}, {}, {}, {}, {}, {}, {}
    odds = _WALTZ_COMP_ODDS.get(style, _WALTZ_COMP_ODDS["honky_tonk"])
    for sec in _SECTIONS:
        pick = (rng.choice(lengths), rng.random() < .6)
        fig = _pick(rng, odds)
        if sec == "chorus":
            while pick == bass["verse"]:
                pick = (rng.choice(lengths + (.9, 2.9)), rng.random() < .6)
            fig = _pick(rng, {k: v for k, v in odds.items() if k != comp["verse"]})
        bass[sec], comp[sec] = pick, fig
        # Kick on 1, sometimes a pickup on the "and" of 3; snare "pah-pah"
        # on 2 and 3, or a lighter touch on one of them.
        kick[sec] = rng.choice(("x...........",) * 3 + ("x.........x.",))
        snare[sec] = rng.choice(((4, 8), (4, 8), (8,), (4,)) if style != "ballad" else ((8,), (4, 8)))
        hands[sec] = rng.choice(("x...x...x...", "x.x.x.x.x.x.", "x...x.x.x.x.", "x.x.x...x...",
                                 "x...x...x.x.", "x.x.x.x.x..."))
        voice[sec] = rng.choice(("snare", "snare", "cross_stick") if style != "ballad" else
                                ("cross_stick", "cross_stick", "snare"))
        foot[sec] = rng.random() < .35
    if hands["chorus"] == hands["verse"]:
        hands["chorus"] = "x.x.x.x.x.x." if hands["verse"] != "x.x.x.x.x.x." else "x...x...x..."
    return WaltzPlayer(
        bass_alternation=rng.choice(("bar", "change", "change", "root")),
        walk_every=rng.choice((1, 2, 4)),
        walk_style=rng.choice(("diatonic", "diatonic", "chromatic")),
        bass=bass, comp=comp, kick=kick, snare=snare, hands=hands, snare_voice=voice, foot=foot)
