"""Arrangement DNA: the per-song habits every part agrees on.

A generator gives itself away through devices that happen in every song:
stop-time before every chorus, a walk-up at every phrase end, a whammy dive
at the end of every solo. A band makes these choices per song. Arrangement
DNA draws them once per song and every composer (drums, comping, lead)
reads the same choice, so the parts stay coordinated while songs differ.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..rng import stable_seed_int
from .country import STYLES, country_style


@dataclass(frozen=True)
class ArrangementDNA:
    into_chorus: str     # stop | build | fill | push | drop
    phrase_fill: str     # walkup | slide | rake | none   (rhythm guitar phrase ends)
    intro: str           # full | riff_alone
    solo_story: str      # climb | melodic | trade | blues
    solo_ending: str     # dive | hold | trill | slide_off
    counter: str         # guide | octaves | stabs | fills   (lead under a singer's chorus)
    riff_driven: bool = False   # verses, intro and outro ride a signature riff
    bass_doubles: bool = False  # the bass doubles the riff an octave down
    chorus_form: str = "lift"   # lift (A A' B A'') | anthem (A A' A A'') | call (A B A B')
    lead_fills: str = "normal"  # sparse (every 8 bars) | normal (4) | chatty (2)
    ending: str = "ring"        # ring | cold | big
    signature: str = ""
    country_style: str = ""
    comp_activity: str = "busy"  # sparse | normal | busy (existing full figures)


def intro_entry_bar(arrangement: "ArrangementDNA", section_type: str, bars: int,
                    is_first_section: bool) -> int:
    """First bar the rhythm section plays in a riff-alone intro (0 = from the top)."""
    if is_first_section and str(section_type).lower() == "intro" and \
            getattr(arrangement, "intro", "full") == "riff_alone" and bars >= 2:
        return max(1, bars // 2)
    return 0


# Parts that can play a riff by themselves at the top of a riff-alone intro.
RIFF_PLAYERS = ("rhythm_gtr", "acoustic_gtr")

_SECTION_ALIASES = {"pre-chorus": "prechorus", "pre_chorus": "prechorus", "hook": "chorus",
                    "interlude": "bridge", "lead": "solo"}


def riff_alone_intro(arrangement: "ArrangementDNA", parts) -> "ArrangementDNA":
    """The one rule for who plays a riff-alone intro, shared by every part.

    The riff needs a guitar to play it alone (rhythm or acoustic). Without
    one the whole band plays the intro from the top. With one, the drums
    and bass wait out the first half together (``intro_entry_bar``) while
    the guitar plays; a lead guitar does not count, it plays over a band.
    """
    if getattr(arrangement, "intro", "full") != "riff_alone":
        return arrangement
    if set(parts or ()) & set(RIFF_PLAYERS):
        return arrangement
    from dataclasses import replace

    return replace(arrangement, intro="full")


def into_chorus_device(arrangement: "ArrangementDNA", section_type: str,
                       next_section_type) -> str:
    """The device the band plays in a section's last bar before a chorus, or ""."""
    def norm(t):
        t = str(t or "").strip().lower()
        return _SECTION_ALIASES.get(t, t)

    if next_section_type is None or norm(next_section_type) != "chorus" \
            or norm(section_type) == "chorus":
        return ""
    return str(getattr(arrangement, "into_chorus", "") or "")


def _pick(rng: random.Random, weights: dict) -> str:
    items = sorted(weights.items())
    total = sum(w for _, w in items)
    draw = rng.random() * total
    for name, w in items:
        draw -= w
        if draw <= 0:
            return name
    return items[-1][0]


_CHOICES = {
    "country_style": STYLES,
    "into_chorus": ("stop", "build", "fill", "push", "drop"),
    "phrase_fill": ("walkup", "slide", "rake", "none"),
    "intro": ("full", "riff_alone"),
    "solo_story": ("climb", "melodic", "trade", "blues"),
    "solo_ending": ("dive", "hold", "trill", "slide_off"),
    "counter": ("guide", "octaves", "stabs", "fills"),
    "chorus_form": ("lift", "anthem", "call"),
    "lead_fills": ("sparse", "normal", "chatty"),
    "ending": ("ring", "cold", "big"),
    "comp_activity": ("sparse", "normal", "busy"),
}


def _signature(dna: "ArrangementDNA") -> str:
    return (f"into chorus={dna.into_chorus}, phrase ends={dna.phrase_fill}, intro={dna.intro}, "
            f"solo={dna.solo_story}/{dna.solo_ending}, counter={dna.counter}, "
            f"riff-driven={dna.riff_driven}, bass doubles={dna.bass_doubles}, "
            f"chorus={dna.chorus_form}, lead fills={dna.lead_fills}, ending={dna.ending}, "
            f"comp activity={dna.comp_activity}")


def apply_overrides(dna: ArrangementDNA, overrides) -> ArrangementDNA:
    """``song.arrangement_style`` pins any habit; unknown values are ignored."""
    if not isinstance(overrides, dict):
        return dna
    from dataclasses import replace

    fields = {}
    for name, allowed in _CHOICES.items():
        value = overrides.get(name)
        if isinstance(value, str) and value.strip().lower() in allowed:
            fields[name] = value.strip().lower()
    for name in ("riff_driven", "bass_doubles"):
        if isinstance(overrides.get(name), bool):
            fields[name] = overrides[name]
    if not fields:
        return dna
    dna = replace(dna, **fields)
    return replace(dna, signature=_signature(dna))


def compose_arrangement_dna(*, seed: int, genre: str, country_style_override=None) -> ArrangementDNA:
    g = str(genre or "").lower()
    heavy = any(t in g for t in ("metal", "hard", "punk", "grunge"))
    bluesy = any(t in g for t in ("blues", "soul", "country"))
    rng = random.Random(stable_seed_int("composer.arrangement", seed, genre))
    dna = ArrangementDNA(
        into_chorus=_pick(rng, {"stop": 2, "build": 3 if heavy else 2, "fill": 3, "push": 2,
                                "drop": 1}),
        phrase_fill=_pick(rng, {"walkup": 3, "slide": 2, "rake": 2 if heavy else 1, "none": 2}),
        intro=_pick(rng, {"full": 3, "riff_alone": 2 if heavy else 1}),
        solo_story=_pick(rng, {"climb": 3, "melodic": 2, "trade": 2, "blues": 3 if bluesy else 1}),
        solo_ending=_pick(rng, {"dive": 3 if heavy else 1, "hold": 3, "trill": 1,
                                "slide_off": 2}),
        counter=_pick(rng, {"guide": 3, "octaves": 2, "stabs": 2, "fills": 2}),
    )
    rock = heavy or "rock" in g or "blues" in g
    from dataclasses import replace

    riff_driven = rng.random() < (0.75 if heavy else 0.45 if rock else 0.15 if "funk" in g else 0.0)
    dna = replace(
        dna,
        riff_driven=riff_driven,
        bass_doubles=riff_driven and rng.random() < 0.6,
        chorus_form=_pick(rng, {"lift": 45, "anthem": 30, "call": 25}),
        lead_fills=_pick(rng, {"sparse": 3, "normal": 5, "chatty": 2}),
        ending=_pick(rng, {"ring": 4, "cold": 3, "big": 3 if heavy else 2}),
    )
    # How busy the rhythm guitarist is: most players state the figure and
    # leave room, some decorate every bar. Its own stream, so the habits
    # above stay as they were.
    busy_rng = random.Random(stable_seed_int("composer.comp_activity", seed, genre))
    funky = any(t in g for t in ("funk", "disco"))
    dna = replace(dna, comp_activity=_pick(busy_rng, {"busy": 5 if funky else 3, "normal": 5,
                                                      "sparse": 1 if funky else 2}))
    family = next((t for t in ("country", "reggae", "jazz", "swing", "bossa") if t in g), "")
    if family:
        fills = ({"walkup": 6, "slide": 2, "none": 2} if family == "country" else
                 {"none": 8, "slide": 2} if family == "reggae" else {"none": 7, "walkup": 3})
        tables = {"phrase_fill": fills, "intro": {"full": 7, "riff_alone": 3},
                  "solo_ending": {"hold": 6, "trill": 1, "slide_off": 3},
                  "ending": {"ring": 6, "cold": 3, "big": 1}}
        choices = {name: _pick(random.Random(stable_seed_int("composer.idiom.arrangement", seed, genre, name)), table)
                   for name, table in tables.items()}
        dna = replace(dna, **choices)
    style = country_style(seed, genre, country_style_override)
    dna = replace(dna, country_style=style)
    if style:
        player = random.Random(stable_seed_int("composer.country.arrangement", seed))
        dna = replace(dna, counter=_pick(player, {"guide": 5 if style == "ballad" else 2,
                                                "fills": 5, "stabs": 2}),
                      solo_story=_pick(player, {"melodic": 5, "trade": 3, "climb": 2}))
    return replace(dna, signature=_signature(dna))
