"""Fill generation for the Produzre drums engine.

This module adds optional fill events (toms/snare rolls/crashes) on top of a
core groove pattern.

Design goals:
- Pure logic: operates on DrumEvent lists; does not touch Timeline or MIDI.
- Deterministic: all randomness is driven by an explicit `random.Random`.
- Conservative by default: fills only at phrase/section end unless the user
  enables more experimental "chatter" fills.

The engine entrypoint (package `__init__.py`) is responsible for:
- Reading user params (fill_rate / fill_chatter)
- Calling `add_fills(...)` before humanization
"""

from __future__ import annotations

import math
import random
from typing import Dict, List

from .patterns import DrumEvent


def _bars_total(total_beats: float, beats_per_bar: float) -> int:
    """Return number of bars needed to cover total_beats."""

    bpb = float(beats_per_bar)
    if bpb <= 0.0:
        return 0
    return int(math.ceil(float(total_beats) / bpb))


def add_fills(
    *,
    events: List[DrumEvent],
    total_beats: float,
    beats_per_bar: float,
    rng: random.Random,
    pitches: Dict[str, int],
    base_velocity: int,
    fill_rate: float,
    fill_chatter: float,
    fill_length: str = "medium",
    persona: str = "tight",
    steps_per_bar: int = 16,
    rng_fill: random.Random | None = None,
    rng_chatter: random.Random | None = None,
    phrase_len_bars: int = 4,
    phrase_end_emphasis: float = 1.5,
) -> List[DrumEvent]:
    """Return events with optional fills added.

    Args:
        events: Existing core groove events.
        total_beats: Section duration in beats.
        beats_per_bar: Meter beats per bar.
        rng: Deterministic RNG (fallback if rng_fill/rng_chatter not provided).
        pitches: Mapping for drum pitches. Uses keys: snare, crash, tom_low,
            tom_mid, tom_high, kick. Missing tom keys fall back to snare.
        base_velocity: Baseline velocity.
        fill_rate: 0..1 probability of placing a phrase-end fill.
        fill_chatter: 0..1 probability of placing an extra in-section fill.
            This is "experimental" and should default to 0.
        fill_length: "short" (1 beat), "medium" (2 beats), "long" (1 bar).
        persona: "tight" or "loose" - affects fill type selection.
        steps_per_bar: Step grid resolution (default 16).
        rng_fill: Optional RNG stream for phrase-end fills. If None, uses `rng`.
        rng_chatter: Optional RNG stream for chatter fills. If None, uses `rng`.
        phrase_len_bars: Number of bars per musical phrase (default 4).
            Fills are placed at phrase boundaries (bars 4, 8, 12, etc.).
        phrase_end_emphasis: Multiplier for final phrase fill intensity (default 1.5).
            Values > 1.0 make the section-ending fill bigger/longer.

    Returns:
        New list including fill events (sorted).

    Notes:
        Fill types:
        - snare_roll: Classic snare roll
        - tom_run: Descending tom pattern (high → mid → low)
        - alternating: Snare and tom alternating pattern
        - kick_burst: Fast kick pattern with snare accents
        - cymbal_swell: Building cymbal crashes with rolls

        Meter awareness:
        - 6/8 time uses triplet-based patterns
        - 4/4 time uses standard 16th patterns

        Phrase awareness:
        - Fills are placed at phrase boundaries (every phrase_len_bars bars)
        - Final phrase (section end) gets emphasis via phrase_end_emphasis
    """

    tb = float(total_beats)
    bpb = float(beats_per_bar)
    if tb <= 0.0 or bpb <= 0.0:
        return list(events)

    fr = 0.0 if fill_rate < 0.0 else 1.0 if fill_rate > 1.0 else float(fill_rate)
    cr = 0.0 if fill_chatter < 0.0 else 1.0 if fill_chatter > 1.0 else float(fill_chatter)

    # Split RNG streams so enabling chatter doesn't reshuffle phrase-end fills.
    rng_fill = rng if rng_fill is None else rng_fill
    rng_chatter = rng if rng_chatter is None else rng_chatter

    if fr <= 0.0 and cr <= 0.0:
        return list(events)

    spb = int(steps_per_bar)
    spb = 16 if spb <= 0 else spb
    step_beats = bpb / float(spb)
    step_beats = float(step_beats)

    kick = int(pitches.get("kick", 36))
    snare = int(pitches.get("snare", 38))
    crash = int(pitches.get("crash", 49))
    tom_l = int(pitches.get("tom_low", snare))
    tom_m = int(pitches.get("tom_mid", snare))
    tom_h = int(pitches.get("tom_high", snare))

    out: List[DrumEvent] = list(events)

    bars = _bars_total(tb, bpb)

    # Meter awareness: detect compound 6-beat bars (e.g., 6/4, or 6/8 expressed
    # as 6 quarter beats). Note: Meter.beats_per_bar normalizes 6/8 to 3.0
    # quarter beats per bar, in which case it is indistinguishable from 3/4
    # here and uses the straight-16th path. (The old `spb == 6` clause was a
    # leftover from the legacy fixed 16-step grid and never fired.)
    is_6_8 = abs(bpb - 6.0) < 0.1

    # Map fill_length to beat durations
    fill_length_str = (fill_length or "medium").strip().lower()
    if fill_length_str == "short":
        fill_beats = 1.0
    elif fill_length_str == "long":
        fill_beats = bpb  # Full bar
    else:  # medium
        fill_beats = min(2.0, bpb / 2.0)

    # Calculate phrase boundaries (bars at which phrases end)
    # For phrase_len_bars=4 in an 8-bar section, phrase boundaries are at bars 3 and 7 (0-indexed)
    phrase_len = max(1, int(phrase_len_bars))
    phrase_boundaries = []
    for bar_idx in range(bars):
        # Phrase boundary occurs at the END of phrase_len bars
        if (bar_idx + 1) % phrase_len == 0:
            phrase_boundaries.append(bar_idx)

    # If the section doesn't end on a phrase boundary, add the last bar as a phrase boundary
    if bars > 0 and (bars % phrase_len != 0):
        phrase_boundaries.append(bars - 1)

    # Ensure we always have at least the last bar as a phrase boundary
    if not phrase_boundaries and bars > 0:
        phrase_boundaries.append(bars - 1)

    # Place fills at phrase boundaries
    if fr > 0.0:
        for phrase_bar in phrase_boundaries:
            # Decide whether to place a fill at this phrase boundary
            if rng_fill.random() >= fr:
                continue

            # Check if this is the final phrase (section end)
            is_final_phrase = phrase_bar == (bars - 1)

            # Apply emphasis to final phrase
            phrase_fill_beats = fill_beats
            if is_final_phrase and phrase_end_emphasis > 1.0:
                # Make final phrase fill longer by emphasis factor
                phrase_fill_beats = min(bpb, fill_beats * phrase_end_emphasis)

            phrase_bar_start = float(phrase_bar) * bpb

            # Calculate fill start based on fill_length
            fill_start = max(0.0, phrase_bar_start + bpb - phrase_fill_beats)
            fill_end = min(tb, phrase_bar_start + bpb)

            # Choose fill type based on persona and available voices
            have_toms = (tom_l != snare) or (tom_m != snare) or (tom_h != snare)
            persona_str = (persona or "tight").strip().lower()

            # Fill types: 0=snare_roll, 1=alternating, 2=tom_run, 3=kick_burst, 4=cymbal_swell
            fill_type_weights = {
                "tight": [0.40, 0.30, 0.20, 0.05, 0.05],   # Conservative, classic fills
                "loose": [0.20, 0.25, 0.25, 0.15, 0.15],   # More experimental
            }
            weights = fill_type_weights.get(persona_str, fill_type_weights["tight"])

            # If no toms, reduce tom-based fills
            if not have_toms:
                weights = [0.70, 0.15, 0.0, 0.10, 0.05]

            # Cumulative weights for selection
            r = rng_fill.random()
            cumulative = 0.0
            fill_type = 0
            for i, w in enumerate(weights):
                cumulative += w
                if r < cumulative:
                    fill_type = i
                    break

            # Meter-aware step sizing
            if is_6_8:
                # 6/8: use triplet feel (3 subdivisions per beat)
                roll_step = step_beats if rng_fill.random() < 0.70 else (1.5 * step_beats)
            else:
                # 4/4: standard 16ths or 8ths
                roll_step = step_beats if rng_fill.random() < 0.75 else (2.0 * step_beats)

            # Define note sequences per fill type
            if fill_type == 0:
                # Snare roll
                choices = [snare]
            elif fill_type == 1:
                # Alternating snare/tom
                choices = [snare, tom_m if tom_m != snare else snare, snare, tom_h if tom_h != snare else snare]
            elif fill_type == 2:
                # Tom run (descending)
                choices = [tom_h if tom_h != snare else snare, tom_m if tom_m != snare else snare, tom_l if tom_l != snare else snare, snare]
            elif fill_type == 3:
                # Kick burst with snare accents
                choices = [kick, kick, snare, kick]
            else:
                # Cymbal swell (crash repeated with crescendo)
                choices = [crash]

            # Generate fill events with appropriate velocity shaping
            fill_len_beats = max(1e-6, float(fill_end - fill_start))

            idx = 0
            t = float(fill_start)
            while t < fill_end - 1e-9:
                pitch = choices[idx % len(choices)]
                idx += 1

                # Progress through the fill (0..1)
                prog = max(0.0, min(1.0, (t - float(fill_start)) / fill_len_beats))

                # Velocity shaping depends on fill type
                if fill_type == 0:
                    # Snare roll: exponential crescendo — slow build then explosive end
                    # Real rolls accelerate dynamically into the downbeat
                    ramp = int((prog ** 1.8) * 22.0)
                    # Alternate L/R hands: odd hits slightly softer (weaker hand)
                    if idx % 2 == 0:
                        ramp = max(0, ramp - 3)
                elif fill_type == 1:
                    # Alternating: moderate exponential crescendo
                    ramp = int(6 + (prog ** 1.5) * 14.0)
                elif fill_type == 2:
                    # Tom run: strong crescendo into final snare
                    ramp = int(8 + (prog ** 1.3) * 16.0)
                elif fill_type == 3:
                    # Kick burst: consistent power with accented snares
                    ramp = int(12) if pitch == snare else int(8)
                else:
                    # Cymbal swell: dramatic crescendo
                    ramp = int(4 + (prog * 18.0))

                vel = max(1, min(127, int(base_velocity + ramp + rng_fill.randint(-4, 4))))

                # Cymbal swell uses longer durations for overlap/sustain
                duration = 0.5 if fill_type == 4 else min(0.25, roll_step)

                # Per-hit jitter: snare/alternating fills get micro-timing variation
                # simulating natural hand acceleration (human roll feel)
                if fill_type in (0, 1):
                    # Accelerate slightly into the phrase boundary (compress step at end)
                    # step_multiplier: 1.15 at start → 0.85 at end
                    step_mult = 1.15 - (prog * 0.30)
                    jitter_beats = rng_fill.uniform(-0.006, 0.006)
                    effective_step = roll_step * step_mult + jitter_beats
                else:
                    effective_step = roll_step

                out.append(
                    DrumEvent(
                        beat=t,
                        duration_beats=duration,
                        pitch=int(pitch),
                        velocity=vel,
                        kind="fill",
                    )
                )
                t += effective_step

            # The fill resolves on the NEXT bar's downbeat (the downbeat the
            # fill is leading into), not the downbeat of the bar containing
            # the fill. At the section end that downbeat belongs to the next
            # section, so we leave it to the section-transition logic.
            resolution_beat = phrase_bar_start + bpb

            # Draw the rolls unconditionally to keep the RNG stream stable
            # regardless of whether the resolution falls inside the section.
            place_kick = rng_fill.random() < 0.40
            place_crash = rng_fill.random() < 0.70

            if resolution_beat < tb - 1e-9:
                # Optional kick reinforcement on the resolution downbeat
                # (avoid duplicates). This stays conservative.
                vel_k = max(1, min(127, int(base_velocity + 10)))
                if place_kick and not any(
                    (abs(e.beat - resolution_beat) < 1e-9 and int(e.pitch) == kick) for e in out
                ):
                    out.append(DrumEvent(beat=resolution_beat, duration_beats=0.5, pitch=kick, velocity=vel_k, kind="kick"))

                # Optional crash on the resolution downbeat (avoid duplicates).
                vel_c = max(1, min(127, int(base_velocity + 22)))
                if place_crash and not any(
                    (abs(e.beat - resolution_beat) < 1e-9 and int(e.pitch) == crash) for e in out
                ):
                    out.append(
                        DrumEvent(
                            beat=resolution_beat,
                            duration_beats=0.5,
                            pitch=crash,
                            velocity=vel_c,
                            kind="crash",
                        )
                    )

    # Experimental chatter: short mini-fills inside the section (excluding last bar).
    if cr > 0.0 and bars >= 2 and rng_chatter.random() < cr:
        bar_i = rng_chatter.randint(0, max(0, bars - 2))
        bar_start = float(bar_i) * bpb

        # Place at a grid-aligned position (meter-aware)
        if is_6_8:
            # In 6/8, prefer beat 4 or 5 (second half)
            candidate_steps = [int(spb * 0.5), int(spb * 0.67)]
        else:
            # In 4/4, prefer beat 2 or 3
            candidate_steps = []
            if spb >= 4:
                candidate_steps.append(spb // 2)
            if spb >= 8:
                candidate_steps.append((3 * spb) // 4)

        start_step = int(rng_chatter.choice(candidate_steps or [max(0, spb // 2)]))
        place = bar_start + (float(start_step) * step_beats)

        # Chatter fills are always short (1 beat max)
        end = min(tb, place + 1.0)

        # Simple patterns for chatter
        have_toms = (tom_m != snare) or (tom_h != snare)
        chatter_type = rng_chatter.random()

        if chatter_type < 0.5:
            # Snare-centric
            choices = [snare]
        elif chatter_type < 0.8:
            # Alternating
            choices = [snare, (tom_m if have_toms else snare)]
        else:
            # Quick kick-snare
            choices = [kick, snare]

        # Meter-aware step sizing
        if is_6_8:
            chatter_step = step_beats if rng_chatter.random() < 0.80 else (1.5 * step_beats)
        else:
            chatter_step = step_beats if rng_chatter.random() < 0.70 else (2.0 * step_beats)

        t = float(place)
        idx = 0
        while t < end - 1e-9:
            pitch = choices[idx % len(choices)]
            idx += 1
            vel = max(1, min(127, int(base_velocity + 2 + rng_chatter.randint(-4, 4))))
            out.append(DrumEvent(beat=t, duration_beats=min(0.25, chatter_step), pitch=int(pitch), velocity=vel, kind="chatter"))
            t += chatter_step

    out.sort(key=lambda e: (e.beat, e.pitch, e.kind))
    return out
