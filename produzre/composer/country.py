"""Shared country direction, with independent player streams inside each style."""
import random

from ..rng import stable_seed_int

STYLES = ("honky_tonk", "bakersfield", "outlaw", "two_step", "ballad", "country_rock")


def country_style(seed, genre, pinned=None):
    if "country" not in str(genre).lower():
        return ""
    if pinned in STYLES:
        return pinned
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
