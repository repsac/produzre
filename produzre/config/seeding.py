from __future__ import annotations

"""Seed mixing utilities.

Produzre uses a two-layer seed model to support both individuality and
collaboration:

- `project_seed`: a stable integer stored in the per-user projects registry.
  Sharing a project (including its seed) enables collaborators to reproduce the
  same output.

- `song_seed`: an authored integer stored in a song YAML. This is the musical
  variation knob within a project.

These utilities combine the two into a single deterministic `effective_seed`
used by RNG helpers throughout the system.

Design goals:
- Deterministic across platforms and Python versions.
- Simple to reason about (integer in -> integer out).
- Stable across time for reproducibility.

Security note:
- This is not intended to be a cryptographic construction; it is a stable hash
  used for reproducible pseudo-randomness.
"""

import hashlib


def stable_u32(text: str) -> int:
    """Return a stable unsigned 32-bit integer hash of the given text.

    We avoid Python's built-in `hash()` because it is intentionally salted per
    process for security reasons, which would break determinism between runs.

    Implementation:
      - Uses MD5 and takes the first 4 bytes (little-endian) as a 32-bit value.

    Args:
        text: Input string to hash.

    Returns:
        int: Deterministic integer in the range [0, 2**32 - 1].
    """
    return int.from_bytes(hashlib.md5(text.encode("utf-8")).digest()[:4], "little")


def compute_effective_seed(project_seed: int, song_seed: int) -> int:
    """Combine a project seed and a song seed into a single effective seed.

    This function is the canonical way to compute the RNG seed used for MIDI
    generation.

    Rationale:
      - The project seed encodes collaboration context.
      - The song seed encodes musical variation within that context.
      - Mixing them yields reproducible variation that remains stable when the
        same project+song inputs are shared with collaborators.

    Args:
        project_seed: Project-level seed (typically from `projects.yml`).
        song_seed: Song-level seed (from song YAML / CLI).

    Returns:
        int: Effective deterministic seed (uint32 range).
    """
    return stable_u32(f"{int(project_seed)}:{int(song_seed)}")
