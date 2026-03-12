"""Rhythm-aware note placement for lead guitar (Phase LG3).

Selects note start positions that breathe with the groove:
  - Biases placement toward strong beats or offbeats depending on section style
  - Avoids stacking directly on accent hits from drums / rhythm guitar
  - Provides rest_rate so silence is normal between phrases

The returned positions are used to remap a motif's pitch sequence onto the
grid, keeping melodic contour while respecting the rhythmic landscape.
"""

from __future__ import annotations

import random
from typing import List, Optional, Set

from ...rhythm import RhythmGrid


def choose_note_starts(
    grid: RhythmGrid,
    accent_beats: List[float],
    density: float,
    rng: random.Random,
    phrase_start: float = 0.0,
    phrase_end: Optional[float] = None,
    prefer_offbeat: bool = False,
    rest_rate: float = 0.2,
) -> List[float]:
    """Select beat positions for lead notes within a phrase window.

    Strategy:
      1. Gather grid cells within [phrase_start, phrase_end) as candidates.
      2. Score each candidate:
         - Strong beats (downbeats, beat-3) get higher base weight by default.
         - If prefer_offbeat is True, offbeats are weighted higher (chorus contrast).
         - Positions coinciding with drum/rhythm accent beats receive an avoidance
           penalty so the lead doesn't double-hit the band's emphasis points.
      3. Weighted random selection picks *density* fraction of candidates.
      4. rest_rate randomly silences additional positions for breathing space
         (at least one position is always kept).

    Args:
        grid: RhythmGrid providing cell positions and downbeat flags.
        accent_beats: Section-local beat positions accented by drums/rhythm gtr.
        density: 0.0–1.0 — fraction of candidate positions to select.
        rng: Seeded RNG for determinism.
        phrase_start: Start beat of the phrase window (section-local).
        phrase_end: End beat of the phrase window (defaults to grid.total_beats).
        prefer_offbeat: Bias toward off-grid positions for energetic contrast.
        rest_rate: 0.0–1.0 — probability of silencing each selected position
                   after density filtering (minimum one position always kept).

    Returns:
        Sorted list of selected beat positions (section-local).
    """
    if phrase_end is None:
        phrase_end = grid.total_beats

    bpb = grid.beats_per_bar

    # Build 8th-note candidate positions within the phrase window.
    # Using 0.5-beat steps gives 8 positions/bar in 4/4, which is fine for a lead
    # melody. This is intentionally finer than the shared rhythm grid (which is
    # typically at quarter-note resolution) so the lead can play 8th-note lines.
    step = 0.5
    n_steps = max(1, int((phrase_end - phrase_start) / step + 1e-9))
    candidate_beats: List[float] = [
        phrase_start + i * step for i in range(n_steps)
        if phrase_start + i * step < phrase_end - 1e-9
    ]

    if not candidate_beats:
        return [phrase_start]

    # Build quantised accent set for fast lookup (avoids float precision issues).
    accent_set: Set[float] = {round(ab, 2) for ab in accent_beats}

    # Score each candidate position.
    scored: List[tuple[float, float]] = []  # (score, beat)

    for beat in candidate_beats:
        beat_q = round(beat, 2)

        # Classify beat strength within bar using arithmetic (no cell objects needed).
        pos_in_bar = beat % bpb if bpb > 0 else 0.0
        is_downbeat = abs(pos_in_bar) < 0.01
        is_beat3 = abs(pos_in_bar - (bpb * 0.5)) < 0.01
        is_integer_beat = abs(pos_in_bar - round(pos_in_bar)) < 0.01
        is_strong = is_downbeat or is_beat3
        # Off-grid (8th-note "and" positions): those that fall between integer beats
        is_offgrid = not is_integer_beat

        # Base weight: strong vs weak beat preference.
        if prefer_offbeat:
            base_w = 1.3 if is_offgrid else (0.55 if is_strong else 0.8)
        else:
            base_w = 1.2 if is_strong else (0.8 if is_integer_beat else 0.6)

        # Accent avoidance: penalise stacking on drum/rhythm accent hits.
        accent_pen = 0.25 if beat_q in accent_set else 1.0

        scored.append((base_w * accent_pen, beat))

    if not scored:
        return [phrase_start]

    # Density selection: weighted random sampling without replacement.
    target_count = max(1, int(len(scored) * max(0.05, min(density, 1.0))))
    target_count = min(target_count, len(scored))

    selected: List[float] = []
    remaining = list(scored)

    for _ in range(target_count):
        if not remaining:
            break
        total = sum(s for s, _ in remaining)
        if total <= 0:
            # All scores zeroed; take first available.
            selected.append(remaining[0][1])
            remaining.pop(0)
            continue
        roll = rng.random() * total
        cum = 0.0
        chosen_idx = 0
        for i, (score, _beat) in enumerate(remaining):
            cum += score
            if roll <= cum:
                chosen_idx = i
                break
        selected.append(remaining[chosen_idx][1])
        remaining.pop(chosen_idx)

    # Rest-rate pass: randomly silence positions, keeping at least one.
    if rest_rate > 0.0 and len(selected) > 1:
        kept: List[float] = []
        for beat in selected:
            if rng.random() >= rest_rate or not kept:
                kept.append(beat)
        if not kept:
            kept = [selected[0]]
        selected = kept

    return sorted(selected)
