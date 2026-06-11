"""Drum limb constraints for realistic playability.

This module enforces physical limitations of a drummer (2 hands + 2 feet)
by resolving collisions where too many simultaneous hits occur.

Treats the drum kit as:
- Hands (2): snare, toms, hi-hat (stick), ride, crash, other cymbals
- Feet (2): kick, hi-hat pedal

Hard constraints:
- At most 2 simultaneous hand hits per step
- At most 2 simultaneous foot hits per step
- Avoid hi-hat stick + pedal on same step (unless intentional)
- Reduce impossible combos like snare roll + tom + cymbal at same time

Soft constraints:
- Allow kick + snare + crash (2 hands + 1 foot = classic accent)
- Prefer swap/convert over deletion when possible
- Duck hats/ride during fills
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import logging


# General MIDI drum note mappings
KICK_PITCHES = {35, 36}
SNARE_PITCHES = {37, 38, 40}  # Cross-stick, acoustic snare, electric snare
TOM_PITCHES = {41, 43, 45, 47, 48, 50}  # Low floor, low, mid, mid-high, high, high floor
HAT_CLOSED_PITCH = 42
HAT_OPEN_PITCH = 46
HAT_PEDAL_PITCH = 44  # Hi-hat pedal chick/splash
RIDE_PITCHES = {51, 53, 59}  # Ride cymbal 1, ride bell, ride cymbal 2
CRASH_PITCHES = {49, 57, 52, 55}  # Crash 1, Crash 2, Chinese, Splash


@dataclass
class DrumHit:
    """Represents a single drum hit with metadata for constraint resolution.

    Attributes:
        pitch: MIDI note number (GM drum mapping).
        start_beat: Beat position (absolute).
        duration_beats: Note duration in beats.
        velocity: MIDI velocity (1-127).
        kind: Hit type for priority ('main', 'ghost', 'fill', 'roll', 'timekeep', 'accent', 'pedal').
        voice: Drum voice name ('kick', 'snare', 'hat_c', 'hat_o', 'tom_l', 'crash', etc.).
        limb: Which limb plays this hit ('hand', 'foot').
    """
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int
    kind: str
    voice: str
    limb: str
    channel: int = 9  # Source MIDI channel (preserved through reconstruction)


def classify_drum_event(pitch: int, velocity: int, start_beat: float, beats_per_bar: float = 4.0) -> tuple[str, str, str]:
    """Classify a drum event by voice, kind, and limb.

    Args:
        pitch: MIDI note number.
        velocity: MIDI velocity.
        start_beat: Beat position.
        beats_per_bar: Beats per bar for downbeat detection.

    Returns:
        (voice, kind, limb): Classification tuple.
    """
    # Determine voice
    if pitch in KICK_PITCHES:
        voice = "kick"
        limb = "foot"
        kind = "kick"
    elif pitch in SNARE_PITCHES:
        voice = "snare"
        limb = "hand"
        # Classify snare kind based on velocity and position
        beat_in_bar = start_beat % beats_per_bar
        is_backbeat = abs(beat_in_bar - 1.0) < 0.1 or abs(beat_in_bar - 3.0) < 0.1
        if is_backbeat and velocity >= 80:
            kind = "main"
        elif velocity < 60:
            kind = "ghost"
        else:
            kind = "roll"
    elif pitch in TOM_PITCHES:
        voice = f"tom_{pitch}"
        limb = "hand"
        kind = "fill" if velocity >= 70 else "ghost"
    elif pitch == HAT_CLOSED_PITCH:
        voice = "hat_c"
        limb = "hand"
        kind = "timekeep"
    elif pitch == HAT_OPEN_PITCH:
        voice = "hat_o"
        limb = "hand"
        kind = "timekeep"
    elif pitch == HAT_PEDAL_PITCH:
        voice = "hat_pedal"
        limb = "foot"
        kind = "pedal"
    elif pitch in RIDE_PITCHES:
        voice = "ride"
        limb = "hand"
        beat_in_bar = start_beat % beats_per_bar
        is_downbeat = beat_in_bar < 0.1
        kind = "accent" if is_downbeat and velocity >= 90 else "timekeep"
    elif pitch in CRASH_PITCHES:
        voice = "crash"
        limb = "hand"
        beat_in_bar = start_beat % beats_per_bar
        is_downbeat = beat_in_bar < 0.1
        kind = "accent" if is_downbeat else "fill"
    else:
        voice = f"other_{pitch}"
        limb = "hand"
        kind = "other"

    return voice, kind, limb


def compute_hit_priority(hit: DrumHit, beats_per_bar: float = 4.0) -> tuple[int, int]:
    """Compute priority for a drum hit (higher = more important).

    Priority order (hand hits):
    1. Crash/Ride accent on downbeat
    2. Snare backbeat (main)
    3. Tom fill hits
    4. Snare roll strokes
    5. Hat timekeeping hits
    6. Ghost notes

    Priority order (foot hits):
    1. Kick on downbeat/accent
    2. Kick (double-kick)
    3. Hat pedal (close/open)

    Args:
        hit: DrumHit to prioritize.
        beats_per_bar: Beats per bar.

    Returns:
        (priority_tier, velocity): Tuple for sorting (higher is better).
    """
    beat_in_bar = hit.start_beat % beats_per_bar
    is_downbeat = beat_in_bar < 0.1
    is_backbeat = abs(beat_in_bar - 1.0) < 0.1 or abs(beat_in_bar - 3.0) < 0.1

    if hit.limb == "hand":
        # Hand hit priorities
        if hit.kind == "accent" and is_downbeat and hit.voice in ("crash", "ride"):
            priority = 100  # Highest: downbeat crash/ride accent
        elif hit.kind == "main" and is_backbeat and hit.voice == "snare":
            priority = 90  # Snare backbeat
        elif hit.kind == "fill" and "tom" in hit.voice:
            priority = 80  # Tom fill
        elif hit.kind == "roll" and hit.voice == "snare":
            priority = 70  # Snare roll
        elif hit.kind == "timekeep" and hit.voice in ("hat_c", "hat_o", "ride"):
            priority = 60  # Hat/ride timekeep
        elif hit.kind == "ghost":
            priority = 50  # Ghost note (lowest)
        else:
            priority = 40  # Other
    else:
        # Foot hit priorities
        if hit.voice == "kick" and is_downbeat:
            priority = 100  # Kick downbeat
        elif hit.voice == "kick":
            priority = 90  # Regular kick
        elif hit.voice == "hat_pedal":
            priority = 80  # Hat pedal
        else:
            priority = 70  # Other foot

    # Use velocity as tie-breaker
    return (priority, hit.velocity)


def resolve_step_collisions(
    step_hits: List[DrumHit],
    max_hand_hits: int = 2,
    max_foot_hits: int = 2,
    beats_per_bar: float = 4.0,
    logger: Optional[logging.Logger] = None,
) -> List[DrumHit]:
    """Resolve limb collisions at a single step.

    Enforces physical constraints by keeping only the highest-priority hits
    when too many simultaneous hits occur.

    Args:
        step_hits: All hits at this step.
        max_hand_hits: Maximum simultaneous hand hits (default: 2).
        max_foot_hits: Maximum simultaneous foot hits (default: 2).
        beats_per_bar: Beats per bar.
        logger: Optional logger for debug output.

    Returns:
        List[DrumHit]: Filtered hits that respect limb constraints.
    """
    # Partition by limb FIRST: a step with e.g. 4 hand hits and 0 foot hits
    # still violates the hand budget even though the total is within
    # max_hand_hits + max_foot_hits.
    hand_hits = [h for h in step_hits if h.limb == "hand"]
    foot_hits = [h for h in step_hits if h.limb == "foot"]

    if len(hand_hits) <= max_hand_hits and len(foot_hits) <= max_foot_hits:
        # No collision possible: each limb group is within its own budget.
        return step_hits

    kept_hits = []

    # Resolve hand collisions
    if len(hand_hits) > max_hand_hits:
        # Sort by priority (highest first)
        hand_hits_sorted = sorted(
            hand_hits,
            key=lambda h: compute_hit_priority(h, beats_per_bar),
            reverse=True
        )
        kept_hand_hits = hand_hits_sorted[:max_hand_hits]
        dropped_hand_hits = hand_hits_sorted[max_hand_hits:]

        if logger:
            logger.debug(
                f"resolve_step_collisions: step={step_hits[0].start_beat:.3f} "
                f"hands={len(hand_hits)}->{len(kept_hand_hits)} "
                f"dropped=[{', '.join(h.voice + ':' + h.kind for h in dropped_hand_hits)}] "
                f"kept=[{', '.join(h.voice + ':' + h.kind for h in kept_hand_hits)}]"
            )

        kept_hits.extend(kept_hand_hits)
    else:
        kept_hits.extend(hand_hits)

    # Resolve foot collisions
    if len(foot_hits) > max_foot_hits:
        # Sort by priority (highest first)
        foot_hits_sorted = sorted(
            foot_hits,
            key=lambda h: compute_hit_priority(h, beats_per_bar),
            reverse=True
        )
        kept_foot_hits = foot_hits_sorted[:max_foot_hits]
        dropped_foot_hits = foot_hits_sorted[max_foot_hits:]

        if logger:
            logger.debug(
                f"resolve_step_collisions: step={step_hits[0].start_beat:.3f} "
                f"feet={len(foot_hits)}->{len(kept_foot_hits)} "
                f"dropped=[{', '.join(h.voice + ':' + h.kind for h in dropped_foot_hits)}] "
                f"kept=[{', '.join(h.voice + ':' + h.kind for h in kept_foot_hits)}]"
            )

        kept_hits.extend(kept_foot_hits)
    else:
        kept_hits.extend(foot_hits)

    return kept_hits


def apply_constraints(
    events: List[Any],
    beats_per_bar: float = 4.0,
    max_hand_hits: int = 2,
    max_foot_hits: int = 2,
    kick_density_hihat_pedal_limit: float = 0.6,
    fill_duck_hats: bool = True,
    logger: Optional[logging.Logger] = None,
) -> List[Any]:
    """Apply drum limb constraints to a list of events.

    Post-processing pass that enforces physical playability constraints:
    - At most max_hand_hits simultaneous hand hits
    - At most max_foot_hits simultaneous foot hits
    - Suppress hat pedal during high kick density
    - Duck hats during fills

    Args:
        events: List of drum events (NoteEvent objects).
        beats_per_bar: Beats per bar for classification.
        max_hand_hits: Maximum simultaneous hand hits.
        max_foot_hits: Maximum simultaneous foot hits.
        kick_density_hihat_pedal_limit: Kick density threshold to suppress hat pedal.
        fill_duck_hats: Whether to suppress hats during fills.
        logger: Optional logger for debug output.

    Returns:
        List[Any]: Filtered events that respect constraints.
    """
    if not events:
        return events

    # Convert events to DrumHit objects with metadata
    drum_hits = []
    for ev in events:
        pitch = getattr(ev, 'pitch', 0)
        # Support both DrumEvent (beat) and NoteEvent (start_beat)
        start_beat = getattr(ev, 'beat', getattr(ev, 'start_beat', 0.0))
        duration_beats = getattr(ev, 'duration_beats', 0.25)
        velocity = getattr(ev, 'velocity', 64)
        # Preserve original kind if available (for DrumEvent)
        original_kind = getattr(ev, 'kind', '')

        voice, kind, limb = classify_drum_event(pitch, velocity, start_beat, beats_per_bar)

        hit = DrumHit(
            pitch=pitch,
            start_beat=start_beat,
            duration_beats=duration_beats,
            velocity=velocity,
            kind=original_kind or kind,  # Prefer original kind if available
            voice=voice,
            limb=limb,
            channel=int(getattr(ev, 'channel', 9)),
        )
        drum_hits.append(hit)

    # Group hits by step (quantize to 32nd notes for collision detection)
    step_size = 0.125  # 32nd note = 1/8 beat in 4/4
    hits_by_step: Dict[float, List[DrumHit]] = {}

    for hit in drum_hits:
        # Quantize beat to step
        step = round(hit.start_beat / step_size) * step_size
        if step not in hits_by_step:
            hits_by_step[step] = []
        hits_by_step[step].append(hit)

    # Compute kick density per bar for hat pedal suppression
    kick_hits_by_bar: Dict[int, int] = {}
    for hit in drum_hits:
        if hit.voice == "kick":
            bar = int(hit.start_beat / beats_per_bar)
            kick_hits_by_bar[bar] = kick_hits_by_bar.get(bar, 0) + 1

    # Calculate kick density (hits per beat)
    kick_density_by_bar = {
        bar: count / beats_per_bar
        for bar, count in kick_hits_by_bar.items()
    }

    # Identify fill windows (tom activity OR explicit fill events such as
    # snare-roll fills, which carry kind == "fill" but hit no toms).
    fill_windows: Set[float] = set()
    if fill_duck_hats:
        for step, hits in hits_by_step.items():
            tom_count = sum(1 for h in hits if "tom" in h.voice)
            has_fill_kind = any(h.kind == "fill" for h in hits)
            if tom_count >= 1 or has_fill_kind:
                # This step has fill activity, mark as fill window
                fill_windows.add(step)

    # Resolve collisions at each step
    filtered_hits = []
    collision_count = 0

    for step in sorted(hits_by_step.keys()):
        hits = hits_by_step[step]

        # Suppress hat pedal during high kick density
        bar = int(step / beats_per_bar)
        kick_density = kick_density_by_bar.get(bar, 0.0)

        if kick_density > kick_density_hihat_pedal_limit:
            # Remove hat pedal hits
            hits = [h for h in hits if h.voice != "hat_pedal"]

        # Duck hats during fills
        if fill_duck_hats and step in fill_windows:
            # Suppress hat timekeeping (keep accents)
            hits = [h for h in hits if not (h.voice in ("hat_c", "hat_o") and h.kind == "timekeep")]

        # Resolve limb collisions
        original_count = len(hits)
        hits = resolve_step_collisions(
            hits,
            max_hand_hits=max_hand_hits,
            max_foot_hits=max_foot_hits,
            beats_per_bar=beats_per_bar,
            logger=logger,
        )

        if len(hits) < original_count:
            collision_count += 1

        filtered_hits.extend(hits)

    if logger and collision_count > 0:
        logger.info(
            f"[CONSTRAINTS] Resolved {collision_count} collision steps, "
            f"{len(events)} events -> {len(filtered_hits)} events "
            f"(removed {len(events) - len(filtered_hits)})"
        )

    # Convert DrumHit objects back to original event type
    # Detect event type from first event (DrumEvent has 'beat', NoteEvent has 'start_beat')
    if events and hasattr(events[0], 'beat'):
        # DrumEvent type - reconstruct DrumEvent objects
        from .patterns.kit import DrumEvent

        filtered_events = []
        for hit in filtered_hits:
            event = DrumEvent(
                beat=hit.start_beat,
                duration_beats=hit.duration_beats,
                pitch=hit.pitch,
                velocity=hit.velocity,
                kind=hit.kind,
            )
            filtered_events.append(event)
    else:
        # NoteEvent type - reconstruct NoteEvent objects, preserving the
        # source event's channel and kind.
        from ...timeline import NoteEvent

        filtered_events = []
        for hit in filtered_hits:
            event = NoteEvent(
                pitch=hit.pitch,
                start_beat=hit.start_beat,
                duration_beats=hit.duration_beats,
                velocity=hit.velocity,
                channel=hit.channel,
                kind=hit.kind or None,
            )
            filtered_events.append(event)

    return filtered_events
