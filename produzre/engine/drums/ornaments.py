"""Performance ornaments for drums: chokes, flams, drags.

This module adds drummer realism beyond note placement:
- Cymbal chokes: Shortened sustain when drummer grabs cymbal
- Flams: Single grace note before main stroke (two-note ornament)
- Drags: Double grace note before main stroke (three-note ornament)

Design goals:
- Conservative by default (no ornaments unless explicitly enabled)
- Deterministic: same seed = same ornament placements
- Context-aware: flams on accents, chokes in tight grooves
- MIDI-realistic: grace notes with proper timing and velocity

Usage:
    from .ornaments import add_ornaments
    events = add_ornaments(
        events=events,
        rng=rng,
        choke_rate=0.3,
        flam_rate=0.2,
        drag_rate=0.1,
        ...
    )
"""

from __future__ import annotations

import random
from typing import Dict, List

from .patterns import DrumEvent


def add_ornaments(
    *,
    events: List[DrumEvent],
    rng: random.Random,
    pitches: Dict[str, int],
    choke_rate: float = 0.0,
    flam_rate: float = 0.0,
    drag_rate: float = 0.0,
    persona: str = "tight",
    beats_per_bar: float = 4.0,
) -> List[DrumEvent]:
    """Add performance ornaments (chokes, flams, drags) to drum events.

    Args:
        events: Existing drum events (from patterns + fills).
        rng: Deterministic RNG for ornament placement.
        pitches: Pitch mapping for drum voices.
        choke_rate: 0..1 probability of choking open cymbals (hats, crashes).
        flam_rate: 0..1 probability of adding flam to accented snares.
        drag_rate: 0..1 probability of adding drag to accented snares.
        persona: "tight" (conservative) or "loose" (more ornaments).
        beats_per_bar: Meter beats per bar, used for backbeat detection.

    Returns:
        New list with ornament events added (sorted).

    Notes:
        Ornaments are mutually exclusive per event:
        - A snare hit can have flam OR drag (not both)
        - Cymbal chokes replace original event (shortened duration)

        Flam timing:
        - Grace note: 0.04 beats before main note
        - Grace velocity: 50-60% of main note

        Drag timing:
        - First grace: 0.06 beats before main
        - Second grace: 0.03 beats before main
        - Grace velocity: 45-55% of main note

        Choke rules:
        - Open hats: choke if next event is close (tight grooves)
        - Crashes: choke probabilistically based on choke_rate
        - Shortened to 0.05-0.1 beats duration
    """
    cr = max(0.0, min(1.0, float(choke_rate)))
    fr = max(0.0, min(1.0, float(flam_rate)))
    dr = max(0.0, min(1.0, float(drag_rate)))

    if cr <= 0.0 and fr <= 0.0 and dr <= 0.0:
        return list(events)

    # Identify cymbal pitches for choke detection
    crash = int(pitches.get("crash", 49))
    splash = int(pitches.get("splash", 55))
    china = int(pitches.get("china", 52))
    open_hat = int(pitches.get("hat_open", 46))
    ride = int(pitches.get("ride", 51))

    # Snare pitch for flam/drag detection
    snare = int(pitches.get("snare", 38))

    chokeable_cymbals = {crash, splash, china, open_hat, ride}

    out: List[DrumEvent] = []
    persona_str = (persona or "tight").strip().lower()

    # Track last snare hit time to avoid ornamenting rapid sequences
    last_snare_beat: float = -999.0

    for i, ev in enumerate(events):
        pitch = int(ev.pitch)
        vel = int(ev.velocity)
        kind = str(getattr(ev, "kind", ""))

        # Cymbal chokes: shorten sustain for open cymbals
        if cr > 0.0 and pitch in chokeable_cymbals:
            # Decide whether to choke this cymbal hit
            should_choke = False

            if pitch == open_hat:
                # Choke open hats in tight grooves if next event is close
                if i + 1 < len(events):
                    next_ev = events[i + 1]
                    time_to_next = float(next_ev.beat) - float(ev.beat)
                    if time_to_next < 0.5:  # Less than half beat
                        should_choke = rng.random() < cr

            elif pitch in {crash, splash, china}:
                # Probabilistically choke crashes/splashes/chinas
                # More likely in tight persona
                choke_prob = cr * (0.8 if persona_str == "tight" else 0.5)
                should_choke = rng.random() < choke_prob

            elif pitch == ride:
                # Rarely choke ride (unless very high choke_rate)
                should_choke = rng.random() < (cr * 0.2)

            if should_choke:
                # Shorten duration to simulate choke
                choke_duration = rng.uniform(0.05, 0.1)
                out.append(
                    DrumEvent(
                        beat=ev.beat,
                        duration_beats=choke_duration,
                        pitch=pitch,
                        velocity=vel,
                        kind=f"{kind}_choke" if kind else "choke",
                    )
                )
                continue

        # Flams and drags: add grace notes before accented snares
        if (fr > 0.0 or dr > 0.0) and pitch == snare:
            # Skip ornaments on rapid note sequences (e.g., fast fill rolls)
            # Ornaments need breathing room to sound natural
            current_beat = float(ev.beat)
            time_since_last_snare = current_beat - last_snare_beat

            # Minimum spacing: 0.25 beats (16th note at moderate tempo)
            # This prevents ornamenting every hit in a roll
            if time_since_last_snare < 0.25:
                # Too close to previous snare, skip ornament
                last_snare_beat = current_beat
                out.append(ev)
                continue

            last_snare_beat = current_beat

            # Flams and drags are more common on:
            # - Accented snares (higher velocity)
            # - Snares at phrase boundaries
            # - Backbeats (beat 2 and 4 in 4/4, beat 2 in 3/4)
            is_accent = vel >= 80
            bpb = float(beats_per_bar) if beats_per_bar and beats_per_bar > 0 else 4.0
            beat_in_bar = float(ev.beat) % bpb
            # Backbeat offsets (0-indexed): beat 2 always; beat 4 only when
            # the meter has at least 4 beats. Use a tolerance instead of
            # exact float equality (humanized/jittered beats never match).
            backbeat_offsets = [1.0]
            if bpb >= 3.5:
                backbeat_offsets.append(3.0)
            is_backbeat = any(abs(beat_in_bar - b) < 0.05 for b in backbeat_offsets)

            # Calculate ornament probability boost based on context.
            # The boost scales the ornament RATES up (accents are MORE likely
            # to be ornamented), with the effective probability clamped to 1.
            ornament_boost = 1.0
            if is_accent:
                ornament_boost *= 1.5
            if is_backbeat:
                ornament_boost *= 1.2

            # Decide between flam, drag, or no ornament
            r = rng.random()
            ornament_type = None

            if dr > 0.0 and r < min(1.0, dr * ornament_boost):
                ornament_type = "drag"
            elif fr > 0.0 and r < min(1.0, (dr + fr) * ornament_boost):
                ornament_type = "flam"

            if ornament_type == "flam":
                # Add single grace note ~0.04 beats before main note
                grace_offset = rng.uniform(0.035, 0.045)
                grace_vel = int(vel * rng.uniform(0.50, 0.60))
                grace_beat = float(ev.beat) - grace_offset

                if grace_beat >= 0.0:  # Don't place grace notes before section start
                    out.append(
                        DrumEvent(
                            beat=grace_beat,
                            duration_beats=0.05,
                            pitch=pitch,
                            velocity=grace_vel,
                            kind="flam_grace",
                        )
                    )

            elif ornament_type == "drag":
                # Add two grace notes before main note
                first_grace_offset = rng.uniform(0.055, 0.065)
                second_grace_offset = rng.uniform(0.025, 0.035)
                grace_vel_1 = int(vel * rng.uniform(0.45, 0.50))
                grace_vel_2 = int(vel * rng.uniform(0.50, 0.55))

                first_grace_beat = float(ev.beat) - first_grace_offset
                second_grace_beat = float(ev.beat) - second_grace_offset

                if first_grace_beat >= 0.0:
                    out.append(
                        DrumEvent(
                            beat=first_grace_beat,
                            duration_beats=0.05,
                            pitch=pitch,
                            velocity=grace_vel_1,
                            kind="drag_grace",
                        )
                    )

                if second_grace_beat >= 0.0:
                    out.append(
                        DrumEvent(
                            beat=second_grace_beat,
                            duration_beats=0.05,
                            pitch=pitch,
                            velocity=grace_vel_2,
                            kind="drag_grace",
                        )
                    )

            # Add main note with ornament marker if ornamented
            main_kind = kind
            if ornament_type:
                main_kind = f"{kind}_{ornament_type}" if kind else ornament_type

            out.append(
                DrumEvent(
                    beat=ev.beat,
                    duration_beats=ev.duration_beats,
                    pitch=pitch,
                    velocity=vel,
                    kind=main_kind,
                )
            )
            continue

        # No ornament: pass through unchanged
        out.append(ev)

    out.sort(key=lambda e: (e.beat, e.pitch, e.kind))
    return out
