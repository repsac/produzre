from __future__ import annotations

"""Deterministic seed composition utilities.

Produzre uses deterministic seeding to make generated MIDI reproducible.

Conceptually, a final seed is derived from multiple layers of identity:
- Project identity (project_id): makes two users/projects diverge by default.
- Song seed (song_seed): user-controlled integer for exploring variations.
- Optional section id: enables section-scoped randomness while staying stable.
- Optional instrument name: enables instrument-scoped randomness.

This module provides a small, stable way to combine those identifiers into a
32-bit integer seed and then construct a `random.Random` instance.

Notes:
- Seeds are intentionally reduced to 32 bits to remain compatible with common
  RNG implementations and to keep serialized seeds compact.
- SHA-256 is used only for stable mixing (not for security).
"""

import hashlib
import random
from typing import Optional


def _hash_to_int(s: str) -> int:
    """Hash a string into a stable 32-bit unsigned integer.

    This is a deterministic mixing function used to combine multiple identity
    components (project id, song seed, section id, instrument name) into a
    single integer suitable for initializing an RNG.

    Implementation:
      - Computes SHA-256 of the UTF-8 encoded string.
      - Takes the first 4 bytes and interprets them as big-endian.

    Args:
        s: Input string to hash.

    Returns:
        int: Unsigned 32-bit integer in the range [0, 2**32 - 1].
    """
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def make_seed(
    project_id: str,
    song_seed: int,
    section_id: Optional[str] = None,
    instrument_name: Optional[str] = None,
) -> int:
    """Compose a deterministic RNG seed from project/song identity.

    The returned integer is stable across runs and machines as long as the same
    inputs are provided.

    Composition:
      - Always includes `project_id` and `song_seed`.
      - Optionally includes `section_id` and/or `instrument_name`.

    This enables multiple reproducibility scopes:
      - Song-global: (project_id, song_seed)
      - Per-section: + section_id
      - Per-instrument: + instrument_name
      - Per-section + per-instrument: + both

    Args:
        project_id: Identifier for the active project (not the secret seed).
        song_seed: User-controlled integer seed for the song.
        section_id: Optional section identifier (e.g., "verse1").
        instrument_name: Optional instrument key (e.g., "drums").

    Returns:
        int: Deterministic 32-bit integer seed.
    """
    base = f"proj={project_id}|song={song_seed}"
    if section_id is not None:
        base += f"|section={section_id}"
    if instrument_name is not None:
        base += f"|inst={instrument_name}"
    return _hash_to_int(base)


def rng_from_seed(seed: int) -> random.Random:
    """Create a Python `random.Random` instance from an integer seed.

    Args:
        seed: Integer seed value.

    Returns:
        random.Random: RNG instance seeded with `seed`.
    """
    return random.Random(seed)
