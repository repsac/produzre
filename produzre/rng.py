"""Deterministic RNG management for Produzre.

This module defines the RNG scope hierarchy and provides utilities for creating
deterministic random number generators at each level of the composition.

## RNG Scope Hierarchy

Produzre uses a hierarchical RNG system where each level derives its seed from
the parent scope plus stable contextual keys. This ensures:

1. **Reproducibility**: Same YAML + same project = same outputs
2. **Independence**: Changing one decision doesn't reshuffle unrelated decisions
3. **Controlled variation**: "Takes" allow micro-variations while staying deterministic

### Scope Levels

```
project_seed (per-user, persistent)
    ↓
song_seed (in YAML)
    ↓
take (in YAML, optional controlled variation)
    ↓
section_rng (section_id + section_type)
    ↓
instrument_rng (section + instrument_name)
        ↓
    voice_rng (section + instrument + voice_name)
            ↓
        event_rng (section + instrument + voice + bar + step)
```

### Usage Pattern

```python
# In orchestrator (build.py):
section_rng = make_section_rng(project_seed, song_seed, take, sec_id, sec_type)

# In engine (e.g., drums):
instrument_rng = make_instrument_rng(section_rng, instrument_name)

# In voice-specific logic:
voice_rng = make_voice_rng(instrument_rng, voice_name, sec_id, instrument_name)

# For individual event decisions:
event_seed = make_event_seed(voice_rng, bar_idx, step_idx)
```

## Take System

The `take` parameter (song.take in YAML) allows controlled micro-variation:
- Default: take=0
- Different takes produce different outputs (e.g., different ghost note placements)
- Same take always produces identical output (reproducible)
- Use cases: "Try another take", A/B testing, generating variations

## Implementation Notes

- Uses SHA-256 for stable cross-platform hashing (Python's built-in hash() is not stable)
- All seed functions accept arbitrary context parts and join them deterministically
- RNG streams should be split at decision boundaries to avoid coupling
"""

from __future__ import annotations

import hashlib
import random
from typing import Any


def stable_seed_int(*parts: Any) -> int:
    """Create a stable (cross-run) integer seed from arbitrary parts.

    We avoid Python's built-in `hash()` because it is randomized per-process by
    default. SHA-256 gives us a deterministic seed that is stable across runs
    and platforms.

    Args:
        *parts: Arbitrary hashable values to combine into a seed.
            Common examples: ("section", project_seed, song_seed, take, sec_id)

    Returns:
        int: A non-negative integer suitable for `random.Random(seed)`.

    Example:
        >>> seed = stable_seed_int("drums", "verse", 42, 0)
        >>> rng = random.Random(seed)

    Notes:
        Each part is hashed individually (length-prefixed) so a literal "|"
        inside a part (e.g. a section id like "a|b") cannot collide with the
        part separator: ("a|b",) and ("a", "b") produce different seeds.
    """
    hasher = hashlib.sha256()
    for p in parts:
        encoded = str(p).encode("utf-8")
        # Length-prefix each part so part boundaries are unambiguous.
        hasher.update(len(encoded).to_bytes(8, "big"))
        hasher.update(encoded)
    digest = hasher.digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def make_section_rng(
    project_seed: int,
    song_seed: int,
    take: int,
    section_id: str,
    section_type: str,
) -> random.Random:
    """Create a deterministic RNG for a section.

    This is the top-level RNG scope for section rendering. All instruments
    in the section derive their RNGs from this one.

    Args:
        project_seed: Per-user project seed (from projects registry).
        song_seed: Authored seed from song.seed in YAML.
        take: Take number for controlled variation (from song.take).
        section_id: Section identifier (e.g., "verse1", "chorus_a").
        section_type: Section type (e.g., "verse", "chorus", "bridge").

    Returns:
        random.Random: Deterministic RNG for this section.

    Notes:
        - Take is included in the seed to allow controlled micro-variation
        - Section ID + type ensure different sections get different RNG streams
        - This RNG should be used for section-level decisions only
        - Pass to make_instrument_rng() for instrument-specific decisions
    """
    seed = stable_seed_int("section", project_seed, song_seed, take, section_id, section_type)
    rng = random.Random(seed)
    # Stash the stable seed so child scopes (instrument/voice/bar) can derive
    # their seeds from stable components instead of the mutable RNG state.
    rng._produzre_seed = seed  # type: ignore[attr-defined]
    return rng


def _parent_seed_material(parent_rng: random.Random) -> Any:
    """Return stable seed material for deriving a child RNG.

    Prefers the stable seed stashed by the factory functions in this module
    (project/song/take/section components), so deriving a child RNG does NOT
    depend on how many draws were made from the parent. Falls back to the
    parent's current state for RNGs created outside this module (keeps
    backward compatibility for tests/mocks passing raw `random.Random`).
    """
    stable = getattr(parent_rng, "_produzre_seed", None)
    if stable is not None:
        return stable
    return str(parent_rng.getstate())


def make_instrument_rng(
    section_rng: random.Random,
    instrument_name: str,
) -> random.Random:
    """Create a deterministic RNG for an instrument within a section.

    Derives seed from the section RNG's *stable seed components* (project,
    song, take, section — stashed by make_section_rng) plus the instrument
    name, ensuring each instrument in the section gets an independent RNG
    stream that does not reshuffle if the section RNG is drawn from first.

    Args:
        section_rng: The parent section RNG (from make_section_rng).
        instrument_name: Instrument identifier (e.g., "drums", "bass").

    Returns:
        random.Random: Deterministic RNG for this section-instrument pair.

    Notes:
        - Different instruments in the same section get different streams
        - This RNG should be used for instrument-level orchestration decisions
        - Pass to make_voice_rng() for voice-specific decisions
        - RNGs not created by this module fall back to getstate()-based
          derivation (backward compatible for tests/mocks)
    """
    seed = stable_seed_int("instrument", _parent_seed_material(section_rng), instrument_name)
    rng = random.Random(seed)
    rng._produzre_seed = seed  # type: ignore[attr-defined]
    return rng


def make_voice_rng(
    instrument_rng: random.Random,
    voice_name: str,
    section_id: str,
    instrument_name: str,
) -> random.Random:
    """Create a deterministic RNG for a specific voice within an instrument.

    Derives seed from instrument RNG plus voice/section/instrument context.
    This ensures different voices (kick, snare, hats) get independent streams.

    Args:
        instrument_rng: The parent instrument RNG (from make_instrument_rng).
        voice_name: Voice identifier (e.g., "kick", "snare", "hats", "crash").
        section_id: Section identifier for stable keying.
        instrument_name: Instrument identifier for stable keying.

    Returns:
        random.Random: Deterministic RNG for this voice.

    Notes:
        - Voice-level RNG isolates decisions (e.g., kick pattern doesn't affect hats)
        - Use for voice-specific decisions like note placement, accents
        - For bar/step-level decisions, use make_event_seed()
    """
    seed = stable_seed_int(
        "voice", _parent_seed_material(instrument_rng), section_id, instrument_name, voice_name
    )
    rng = random.Random(seed)
    rng._produzre_seed = seed  # type: ignore[attr-defined]
    return rng


def make_event_seed(
    voice_rng: random.Random,
    bar_idx: int,
    step_idx: int,
) -> int:
    """Create a deterministic seed for an individual event decision.

    Derives seed from voice RNG state plus bar/step indices. Use this for
    fine-grained event decisions like velocity humanization, ghost note placement,
    or micro-timing adjustments.

    Args:
        voice_rng: The parent voice RNG (from make_voice_rng).
        bar_idx: Bar index within the section (0-based).
        step_idx: Step index within the bar (0-based).

    Returns:
        int: Deterministic seed for this specific event.

    Usage:
        >>> event_seed = make_event_seed(voice_rng, bar=2, step=8)
        >>> event_rng = random.Random(event_seed)
        >>> velocity_offset = event_rng.randint(-5, 5)

    Notes:
        - Bar + step indices provide spatial context for event decisions
        - Different events at different times get different seeds
        - Use when you need reproducible per-event variation
    """
    state_bytes = str(voice_rng.getstate()).encode("utf-8")
    return stable_seed_int("event", state_bytes, bar_idx, step_idx)


def make_bar_rng(
    voice_rng: random.Random,
    bar_idx: int,
) -> random.Random:
    """Create a deterministic RNG for all events in a bar.

    Convenience function for bar-level decisions that affect multiple events.
    Use this when you need consistent randomization across a full bar.

    Args:
        voice_rng: The parent voice RNG (from make_voice_rng).
        bar_idx: Bar index within the section (0-based).

    Returns:
        random.Random: Deterministic RNG for this bar.

    Usage:
        >>> bar_rng = make_bar_rng(voice_rng, bar=2)
        >>> bar_accent_boost = bar_rng.uniform(0.0, 0.2)

    Notes:
        - Use for decisions that apply to a whole bar
        - For per-event decisions, use make_event_seed() instead
    """
    state_bytes = str(voice_rng.getstate()).encode("utf-8")
    seed = stable_seed_int("bar", state_bytes, bar_idx)
    return random.Random(seed)
