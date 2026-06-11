"""Transition-aware arranging engine.

This module provides scaffolding for musical transitions between sections,
including energy ramps, pickups, turnarounds, and bridge introductions.

Phase 1: Data structures and stub functions (no-op implementation).
Phase 2: Energy analysis and recipe selection logic.
Phase 3: Timeline manipulation to apply transitions.
Phase 4: Section-level and per-instrument overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging


@dataclass
class EnergyProfile:
    """Energy/intensity metrics for a section or instrument.

    This profile captures musical characteristics that inform transition decisions:
    - Density: notes per beat or events per beat
    - Velocity: average MIDI velocity (1-127)
    - Register: average pitch (MIDI note number)
    - Syncopation: measure of rhythmic complexity (0.0-1.0+)
    - Articulation: placeholder for future articulation analysis

    Attributes:
        density: Notes per beat or events per beat (e.g., 0.5 = sparse, 2.0 = dense).
        avg_velocity: Average MIDI velocity (1-127).
        register_center: Average pitch (MIDI note number, e.g., 60 = middle C).
        syncopation: Rhythmic complexity heuristic (0.0 = straight, 1.0+ = highly syncopated).
        articulation: Placeholder for articulation analysis (default: 0.0).
    """
    density: float = 0.0
    avg_velocity: float = 64.0
    register_center: float = 60.0
    syncopation: float = 0.0
    articulation: float = 0.0


@dataclass
class TransitionRecipe:
    """Describes the type and parameters of a transition.

    A recipe specifies what kind of transition to apply between two sections
    or at a section boundary. Recipes are chosen based on energy profiles
    and transition settings.

    Transition kinds:
        - "none": No transition applied
        - "ramp_up": Gradual increase in energy/density/velocity
        - "ramp_down": Gradual decrease in energy/density/velocity
        - "pickup": Short phrase before section start
        - "turnaround": Phrase at section end to signal change
        - "bridge_start": Special introduction for bridge sections

    Attributes:
        kind: Transition type (see above).
        ramp_bars: Number of bars for ramp transitions (0-2).
        bridge_start_bars: Number of bars for bridge introduction (0-2).
        notes_added: Debug counter for notes added by this transition.
    """
    kind: str = "none"
    ramp_bars: int = 0
    bridge_start_bars: int = 0
    notes_added: int = 0


@dataclass
class TransitionPlan:
    """Complete plan for a transition between two sections.

    A transition plan includes:
    - Source and target sections
    - Instrument being transitioned
    - Recipe describing the transition type
    - Edit windows defining where changes will be made
    - Metadata for debugging

    Edit windows specify beat ranges where timeline modifications occur:
        - "tail": Last N beats of section_a
        - "head": First N beats of section_b

    Attributes:
        section_a_id: ID of the source section.
        section_b_id: ID of the target section.
        instrument: Instrument name being transitioned.
        recipe: The transition recipe to apply.
        edit_windows: Dictionary mapping "tail"/"head" to (start_beat, end_beat) tuples.
        metadata: Debug information (e.g., energy profiles, decision rationale).
    """
    section_a_id: str
    section_b_id: str
    instrument: str
    recipe: TransitionRecipe
    edit_windows: Dict[str, tuple[float, float]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GrooveCues:
    """Groove cues extracted from drums for instrument coordination.

    Provides information about drum patterns that other instruments can use
    to align their transitions and phrases for better musical cohesion.

    Attributes:
        accent_beats: Set of beat positions where drums have strong accents
            (e.g., kick + snare hits, crash cymbals).
        downbeats: Set of beat positions on bar downbeats (beat % beats_per_bar == 0).
        fill_windows: List of (start_beat, end_beat) tuples indicating drum fills.
        kick_beats: Set of beat positions where kick drum hits occur.
        snare_beats: Set of beat positions where snare drum hits occur.
    """
    accent_beats: set[float] = field(default_factory=set)
    downbeats: set[float] = field(default_factory=set)
    fill_windows: list[tuple[float, float]] = field(default_factory=list)
    kick_beats: set[float] = field(default_factory=set)
    snare_beats: set[float] = field(default_factory=set)


def compute_energy_profile(
    events: List[Any],
    beats_total: float,
    meter: str,
    logger: Optional[logging.Logger] = None,
) -> EnergyProfile:
    """Compute energy profile from a list of MIDI events.

    Analyzes musical characteristics to create an energy profile that
    informs transition decisions.

    Metrics computed:
    - Density: notes per beat (event count / beats_total)
    - Avg velocity: mean MIDI velocity (1-127)
    - Register center: mean pitch (MIDI note number)
    - Syncopation: fraction of notes not on integer beats

    Args:
        events: List of MIDI events (NoteEvent or similar with start_beat, pitch, velocity).
        beats_total: Total length of the section in beats.
        meter: Meter string (e.g., "4/4").
        logger: Optional logger for debug output.

    Returns:
        EnergyProfile: Computed energy metrics.
    """
    if not events or beats_total <= 0:
        if logger:
            logger.debug(
                f"compute_energy_profile: no events or invalid beats_total={beats_total}, "
                "returning default profile"
            )
        return EnergyProfile(
            density=0.0,
            avg_velocity=64.0,
            register_center=60.0,
            syncopation=0.0,
            articulation=0.0,
        )

    # Density: notes per beat
    density = len(events) / beats_total

    # Average velocity
    velocities = [getattr(ev, 'velocity', 64) for ev in events]
    avg_velocity = sum(velocities) / len(velocities) if velocities else 64.0

    # Register center: average pitch
    pitches = [getattr(ev, 'pitch', 60) for ev in events]
    register_center = sum(pitches) / len(pitches) if pitches else 60.0

    # Syncopation: fraction of notes not landing on integer beats
    # Use epsilon to handle floating point precision
    eps = 0.01
    syncopated_count = 0
    for ev in events:
        start_beat = getattr(ev, 'start_beat', 0.0)
        # Check if note is off the beat (fractional part > epsilon)
        fractional_part = start_beat % 1.0
        if fractional_part > eps and fractional_part < (1.0 - eps):
            syncopated_count += 1

    syncopation = syncopated_count / len(events) if events else 0.0

    if logger:
        logger.debug(
            f"compute_energy_profile: density={density:.2f} notes/beat, "
            f"velocity={avg_velocity:.1f}, register={register_center:.1f}, "
            f"syncopation={syncopation:.2f}"
        )

    return EnergyProfile(
        density=density,
        avg_velocity=avg_velocity,
        register_center=register_center,
        syncopation=syncopation,
        articulation=0.0,  # Placeholder for future
    )


def choose_transition_recipe(
    profile_a: EnergyProfile,
    profile_b: EnergyProfile,
    settings: Any,  # TransitionSettings from model.py
    rng: Any,
    logger: Optional[logging.Logger] = None,
) -> TransitionRecipe:
    """Choose a transition recipe based on energy profiles and settings.

    Determines what type of transition (if any) should be applied based on:
    - Energy change between sections (density, velocity, register)
    - Transition settings (rates, enabled flags)
    - Random variation (controlled by RNG)

    Decision logic:
    1. Check if transitions are enabled
    2. Compute energy delta (weighted sum of density, velocity, register changes)
    3. Apply strength multiplier
    4. Choose recipe based on threshold:
       - energy_delta > +0.2: ramp_up
       - energy_delta < -0.2: ramp_down
       - else: none

    Args:
        profile_a: Energy profile of source section.
        profile_b: Energy profile of target section.
        settings: TransitionSettings (from config).
        rng: Random number generator for probabilistic decisions.
        logger: Optional logger for debug output.

    Returns:
        TransitionRecipe: Selected transition recipe.
    """
    # Check if transitions are enabled
    if not getattr(settings, 'enabled', True):
        if logger:
            logger.debug("choose_transition_recipe: transitions disabled")
        return TransitionRecipe(kind="none")

    # Get strength multiplier
    strength = getattr(settings, 'strength', 0.5)
    if strength <= 0:
        if logger:
            logger.debug("choose_transition_recipe: strength=0, no transition")
        return TransitionRecipe(kind="none")

    # Compute energy deltas (normalized to 0-1 scale)
    # Density delta: raw difference (notes/beat)
    delta_density = profile_b.density - profile_a.density

    # Velocity delta: normalized to 0-1 (max change is 127)
    delta_velocity = (profile_b.avg_velocity - profile_a.avg_velocity) / 127.0

    # Register delta: normalized to 0-1 (assume max useful range is 48 semitones = 4 octaves)
    delta_register = (profile_b.register_center - profile_a.register_center) / 48.0

    # Weighted sum: density has highest weight, then velocity, then register
    # Weights: density=0.5, velocity=0.3, register=0.2
    energy_delta = (
        0.5 * delta_density +
        0.3 * delta_velocity +
        0.2 * delta_register
    )

    # Apply strength multiplier
    energy_delta *= strength

    # Decision thresholds
    ramp_up_threshold = 0.2
    ramp_down_threshold = -0.2
    bridge_start_threshold = 0.5  # Larger threshold for bridge_start (significant energy jump)

    # Get ramp_bars and bridge_start_bars from settings
    ramp_bars = getattr(settings, 'ramp_bars', 1)
    bridge_start_bars = getattr(settings, 'bridge_start_bars', 1)

    # Choose recipe
    # Priority 1: Bridge start for large energy jumps (smooths section B start)
    if abs(energy_delta) > bridge_start_threshold and bridge_start_bars > 0:
        recipe_kind = "bridge_start"
        recipe = TransitionRecipe(
            kind=recipe_kind,
            ramp_bars=0,
            bridge_start_bars=bridge_start_bars,
            notes_added=0,
        )
    # Priority 2: Ramp up for moderate energy increases
    elif energy_delta > ramp_up_threshold:
        recipe_kind = "ramp_up"
        recipe = TransitionRecipe(
            kind=recipe_kind,
            ramp_bars=ramp_bars,
            bridge_start_bars=0,
            notes_added=0,
        )
    elif energy_delta < ramp_down_threshold:
        recipe_kind = "ramp_down"
        recipe = TransitionRecipe(
            kind=recipe_kind,
            ramp_bars=ramp_bars,
            bridge_start_bars=0,
            notes_added=0,
        )
    else:
        # No ramp needed - check for turnaround or pickup
        # Turnarounds are end-of-phrase figures in the last bar of section A
        turnaround_rate = getattr(settings, 'turnaround_rate', 0.25)
        turnaround_probability = turnaround_rate * strength

        if rng.random() < turnaround_probability:
            recipe_kind = "turnaround"
            recipe = TransitionRecipe(
                kind=recipe_kind,
                ramp_bars=0,
                bridge_start_bars=0,
                notes_added=0,  # Will be updated when turnaround is applied
            )
        else:
            # No turnaround - check for pickup
            # Pickups are short anacrusis phrases before section B starts
            pickup_rate = getattr(settings, 'pickup_rate', 0.35)
            pickup_probability = pickup_rate * strength

            if rng.random() < pickup_probability:
                recipe_kind = "pickup"
                recipe = TransitionRecipe(
                    kind=recipe_kind,
                    ramp_bars=0,
                    bridge_start_bars=0,
                    notes_added=0,  # Will be updated when pickup is applied
                )
            else:
                recipe_kind = "none"
                recipe = TransitionRecipe(kind=recipe_kind)

    if logger:
        logger.debug(
            f"choose_transition_recipe: energy_delta={energy_delta:+.3f} "
            f"(density={delta_density:+.2f}, vel={delta_velocity:+.2f}, "
            f"reg={delta_register:+.2f}) -> recipe={recipe_kind}"
        )

    return recipe


def build_transition_plan(
    section_a: Any,  # SectionConfig
    section_b: Any,  # SectionConfig
    instrument: str,
    settings: Any,  # TransitionSettings
    rng: Any,
    logger: Optional[logging.Logger] = None,
) -> TransitionPlan:
    """Build a complete transition plan between two sections.

    Constructs a plan that includes:
    - Energy profiles for both sections
    - Selected transition recipe
    - Edit windows defining where changes occur
    - Metadata for debugging

    Phase 1: Returns no-op plan (no-op).
    Phase 2: Implement energy analysis and recipe selection.
    Phase 3: Define edit windows based on recipe.

    Args:
        section_a: Source section configuration.
        section_b: Target section configuration.
        instrument: Instrument name.
        settings: TransitionSettings (from config).
        rng: Random number generator.
        logger: Optional logger for debug output.

    Returns:
        TransitionPlan: Complete transition plan.
    """
    if logger:
        logger.debug(
            "build_transition_plan: stub (Phase 1) - returning no-op plan "
            f"for {instrument} transition from {section_a} to {section_b}"
        )

    # Phase 1: Return no-op plan
    section_a_id = getattr(section_a, "id", "unknown_a")
    section_b_id = getattr(section_b, "id", "unknown_b")

    recipe = TransitionRecipe(kind="none")

    return TransitionPlan(
        section_a_id=section_a_id,
        section_b_id=section_b_id,
        instrument=instrument,
        recipe=recipe,
        edit_windows={},
        metadata={"phase": 1, "status": "no-op"},
    )


def scale_velocities(events: List[Any], factor: float) -> None:
    """Scale velocities of events by a factor, clamping to MIDI range.

    Modifies events in-place.

    Args:
        events: List of events with velocity attribute.
        factor: Multiplier for velocity (e.g., 1.2 = +20%, 0.8 = -20%).

    Returns:
        None (modifies events in-place).
    """
    for ev in events:
        if hasattr(ev, 'velocity'):
            new_velocity = int(ev.velocity * factor)
            ev.velocity = max(1, min(127, new_velocity))


def adjust_durations(events: List[Any], factor: float) -> None:
    """Adjust durations of events by a factor.

    Modifies events in-place.

    Args:
        events: List of events with duration_beats attribute.
        factor: Multiplier for duration (e.g., 0.8 = shorter, 1.2 = longer).

    Returns:
        None (modifies events in-place).
    """
    for ev in events:
        if hasattr(ev, 'duration_beats'):
            ev.duration_beats *= factor


def thin_events(
    events: List[Any],
    keep_downbeats: bool = True,
    beats_per_bar: float = 4.0,
) -> List[Any]:
    """Remove every other non-downbeat event to reduce density.

    Args:
        events: List of events with start_beat attribute.
        keep_downbeats: If True, always keep events on downbeats (beat % beats_per_bar == 0).
        beats_per_bar: Beats per bar for downbeat detection.

    Returns:
        List[Any]: Filtered event list (subset of input).
    """
    if not events:
        return events

    result = []
    non_downbeat_count = 0
    eps = 0.01

    for ev in events:
        start_beat = getattr(ev, 'start_beat', 0.0)

        # Check if downbeat
        if keep_downbeats:
            beat_in_bar = start_beat % beats_per_bar
            if beat_in_bar < eps:
                # It's a downbeat, always keep
                result.append(ev)
                continue

        # Non-downbeat: keep every other one
        if non_downbeat_count % 2 == 0:
            result.append(ev)
        non_downbeat_count += 1

    return result


def extract_groove_cues(
    drum_events: List[Any],
    window_start: float,
    window_end: float,
    beats_per_bar: float = 4.0,
    logger: Optional[logging.Logger] = None,
) -> GrooveCues:
    """Extract groove cues from drum events for instrument coordination.

    Analyzes drum patterns to identify rhythmic features that other instruments
    can use for better musical alignment.

    Standard GM drum mapping:
    - Kick: 35, 36
    - Snare: 38, 40
    - Hi-hat closed: 42
    - Hi-hat open: 46
    - Crash: 49, 57

    Args:
        drum_events: List of drum events to analyze.
        window_start: Start beat of analysis window.
        window_end: End beat of analysis window.
        beats_per_bar: Beats per bar for downbeat detection.
        logger: Optional logger for debug output.

    Returns:
        GrooveCues: Extracted groove information.
    """
    cues = GrooveCues()
    eps = 0.01

    # Drum MIDI pitch mappings (General MIDI)
    kick_pitches = {35, 36}
    snare_pitches = {38, 40}
    crash_pitches = {49, 57}

    for ev in drum_events:
        beat = getattr(ev, 'start_beat', 0.0)
        pitch = getattr(ev, 'pitch', 0)
        velocity = getattr(ev, 'velocity', 64)

        # Skip events outside the window
        if not (window_start <= beat < window_end):
            continue

        # Identify downbeats
        beat_in_bar = beat % beats_per_bar
        if beat_in_bar < eps:
            cues.downbeats.add(beat)

        # Track kick hits
        if pitch in kick_pitches:
            cues.kick_beats.add(beat)

        # Track snare hits
        if pitch in snare_pitches:
            cues.snare_beats.add(beat)

        # Identify accent beats: strong hits (velocity >= 90) or kick+snare coincidence
        is_strong_hit = velocity >= 90
        is_kick_snare_combo = pitch in kick_pitches or pitch in snare_pitches

        # Crash cymbals always create accents
        if pitch in crash_pitches:
            cues.accent_beats.add(beat)
        elif is_strong_hit and is_kick_snare_combo:
            cues.accent_beats.add(beat)

    # Detect fill windows: regions with high density (>4 events per beat)
    # Use a sliding window approach
    window_size = 1.0  # 1 beat window
    fill_threshold = 4  # events per beat

    current_beat = window_start
    while current_beat < window_end:
        window_events = [
            ev for ev in drum_events
            if current_beat <= getattr(ev, 'start_beat', 0.0) < current_beat + window_size
        ]

        if len(window_events) >= fill_threshold:
            # This is a fill window
            fill_start = current_beat
            # Extend window as long as density remains high
            fill_end = current_beat + window_size

            while fill_end < window_end:
                next_window_events = [
                    ev for ev in drum_events
                    if fill_end <= getattr(ev, 'start_beat', 0.0) < fill_end + window_size
                ]
                if len(next_window_events) >= fill_threshold:
                    fill_end += window_size
                else:
                    break

            cues.fill_windows.append((fill_start, fill_end))
            current_beat = fill_end  # Skip past the fill
        else:
            current_beat += window_size

    if logger:
        logger.debug(
            f"extract_groove_cues: found {len(cues.kick_beats)} kicks, "
            f"{len(cues.snare_beats)} snares, {len(cues.accent_beats)} accents, "
            f"{len(cues.fill_windows)} fill windows"
        )

    return cues


def choose_pickup_pitch(
    section_b_events: List[Any],
    harmony_plan: Optional[Any] = None,
    instrument: str = "bass",
    rng: Any = None,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Choose a safe pitch for a pickup (anacrusis) note.

    Selects a pitch that approaches the first strong note of section B,
    using chord tones or approach tones for musical coherence.

    Strategy:
    1. Find the first strong note in section B (preferably on downbeat)
    2. If harmony available, get chord tones for that beat
    3. Choose approach tone (1-2 semitones below target) or chord tone
    4. For bass: ensure pitch stays within bass register bounds (E1=28 to E3=52)
    5. Fallback: approach root by step

    Args:
        section_b_events: Events from section B to find target pitch.
        harmony_plan: Optional HarmonyPlan for section B (for chord tones).
        instrument: Instrument name (e.g., "bass", "guitar").
        rng: Random number generator for variation.
        logger: Optional logger for debug output.

    Returns:
        int: MIDI pitch number for the pickup note.
    """
    # Bass register bounds (E1 to E3)
    bass_min = 28  # E1
    bass_max = 52  # E3

    # Default fallback pitch (low E for bass, middle C for others)
    default_pitch = bass_min if instrument == "bass" else 60

    # Find first strong note in section B (downbeat preferred)
    if not section_b_events:
        if logger:
            logger.debug("choose_pickup_pitch: no events in section B, using default pitch")
        return default_pitch

    # Find first event on or near a downbeat (beat % 4 < 0.5)
    target_event = None
    eps = 0.5

    for ev in section_b_events:
        start_beat = getattr(ev, 'start_beat', 0.0)
        beat_in_bar = start_beat % 4.0
        if beat_in_bar < eps:
            target_event = ev
            break

    # If no downbeat event, use first event
    if target_event is None:
        target_event = section_b_events[0]

    target_pitch = getattr(target_event, 'pitch', default_pitch)

    # Choose approach pitch: 1 or 2 semitones below target
    # Use RNG for variation if available
    if rng:
        approach_distance = rng.choice([1, 2])
    else:
        approach_distance = 1

    pickup_pitch = target_pitch - approach_distance

    # Clamp to instrument register
    if instrument == "bass":
        pickup_pitch = max(bass_min, min(bass_max, pickup_pitch))
    else:
        # General MIDI range
        pickup_pitch = max(21, min(108, pickup_pitch))

    if logger:
        logger.debug(
            f"choose_pickup_pitch: target={target_pitch} approach_distance={approach_distance} "
            f"pickup={pickup_pitch}"
        )

    return pickup_pitch


def build_bass_turnaround(
    tail_start: float,
    tail_end: float,
    section_b_events: List[Any],
    rng: Any,
    groove_cues: Optional[GrooveCues] = None,
    logger: Optional[logging.Logger] = None,
) -> List[Any]:
    """Build a bass turnaround figure for the last bar of section A.

    Creates a stepwise run that resolves into the first note of section B.
    The turnaround occupies the last 2 beats of section A.

    When groove cues are available, aligns notes with kick beats for better
    bass-drum coordination.

    Strategy:
    1. Find target pitch: first strong note of section B (downbeat preferred)
    2. Generate 3-4 notes in stepwise motion toward the target
    3. Place notes in the last 2 beats before section B starts
    4. Align with kick beats if groove cues available
    5. Use modest velocities (60-80 range)

    Args:
        tail_start: Start beat of section A tail window.
        tail_end: End beat of section A tail window (= section B start).
        section_b_events: Events from section B to determine target pitch.
        rng: Random number generator for variation.
        groove_cues: Optional groove cues from drums for alignment.
        logger: Optional logger for debug output.

    Returns:
        List[NoteEvent]: Turnaround events to add to timeline.
    """
    from ..timeline import NoteEvent

    # Bass register bounds
    bass_min = 28  # E1
    bass_max = 52  # E3

    # Find target pitch from section B (downbeat preferred)
    target_pitch = bass_min + 12  # Default: E2 (36)
    eps = 0.5

    if section_b_events:
        # Find first downbeat event
        target_event = None
        for ev in section_b_events:
            start_beat = getattr(ev, 'start_beat', 0.0)
            beat_in_bar = start_beat % 4.0
            if beat_in_bar < eps:
                target_event = ev
                break

        if target_event is None:
            target_event = section_b_events[0]

        target_pitch = getattr(target_event, 'pitch', target_pitch)

    # Turnaround occupies last 2 beats of section A
    turnaround_start = tail_end - 2.0
    turnaround_duration = 2.0

    # Generate 3-4 notes stepwise toward target
    num_notes = rng.choice([3, 4]) if rng else 3

    # Start pitch: 3-5 semitones below target (stepwise approach)
    approach_distance = rng.choice([3, 4, 5]) if rng else 4
    start_pitch = target_pitch - approach_distance

    # Clamp to bass register
    start_pitch = max(bass_min, min(bass_max, start_pitch))

    # Determine beat positions for notes
    # If groove cues available, align with kick beats in the turnaround window
    note_beats = []

    if groove_cues and groove_cues.kick_beats:
        # Find kick beats in turnaround window
        turnaround_kicks = sorted([
            beat for beat in groove_cues.kick_beats
            if turnaround_start <= beat < tail_end
        ])

        # Use kick beats if we have enough, otherwise fall back to even spacing
        if len(turnaround_kicks) >= num_notes:
            # Use the last num_notes kicks (closest to section B)
            note_beats = turnaround_kicks[-num_notes:]
        elif len(turnaround_kicks) > 0:
            # Use available kicks and fill in gaps with even spacing
            note_beats = turnaround_kicks
            # Add evenly spaced beats to reach num_notes
            remaining = num_notes - len(note_beats)
            if remaining > 0:
                note_duration = turnaround_duration / num_notes
                for i in range(remaining):
                    beat = turnaround_start + i * note_duration
                    note_beats.append(beat)
                note_beats = sorted(note_beats)[:num_notes]
        else:
            # No kicks available, use even spacing
            note_duration = turnaround_duration / num_notes
            note_beats = [turnaround_start + i * note_duration for i in range(num_notes)]
    else:
        # No groove cues, use even spacing
        note_duration = turnaround_duration / num_notes
        note_beats = [turnaround_start + i * note_duration for i in range(num_notes)]

    # Calculate note duration based on actual spacing
    if len(note_beats) > 1:
        avg_spacing = (note_beats[-1] - note_beats[0]) / (len(note_beats) - 1)
        note_duration = avg_spacing
    else:
        note_duration = turnaround_duration / num_notes

    # Generate stepwise notes at determined beat positions
    turnaround_events = []

    for i, beat in enumerate(note_beats):
        # Calculate pitch: linear interpolation from start to target
        progress = i / (num_notes - 1) if num_notes > 1 else 0.0
        pitch = int(start_pitch + (target_pitch - start_pitch) * progress)
        pitch = max(bass_min, min(bass_max, pitch))

        # Velocity: slightly increasing toward target (60 -> 75)
        # Boost velocity if this beat aligns with a kick accent
        velocity = int(60 + 15 * progress)

        if groove_cues and beat in groove_cues.accent_beats:
            velocity = min(127, int(velocity * 1.15))  # 15% boost for accents

        event = NoteEvent(
            pitch=pitch,
            start_beat=beat,
            duration_beats=note_duration * 0.9,  # Slight staccato
            velocity=velocity,
            channel=0,
        )

        turnaround_events.append(event)

    if logger:
        logger.debug(
            f"build_bass_turnaround: generated {len(turnaround_events)} notes "
            f"from pitch {start_pitch} to {target_pitch} over {turnaround_duration:.2f} beats"
        )

    return turnaround_events


def apply_transition_plan(
    timeline: Any,  # InstrumentTimeline
    instrument_name: str,
    plan: TransitionPlan,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Apply a transition plan to an instrument timeline.

    Modifies the timeline according to the transition plan:
    - Ramp-up: Increase velocity, shorten durations (more energy)
    - Ramp-down: Decrease velocity, lengthen durations, thin events (less energy)

    Phase 3: Implement ramp transitions (ramp_up, ramp_down).
    Phase 4+: Implement pickup, turnaround, bridge_start.

    Args:
        timeline: InstrumentTimeline to modify.
        instrument_name: Name of the instrument.
        plan: TransitionPlan to apply.
        logger: Optional logger for debug output.

    Returns:
        None (modifies timeline in-place).
    """
    recipe = plan.recipe

    if recipe.kind == "none":
        return

    # Handle pickup transitions
    if recipe.kind == "pickup":
        # Get head window (section B start)
        head_window = plan.edit_windows.get("head")
        if not head_window:
            if logger:
                logger.warning(
                    f"apply_transition_plan: no head window for pickup in {instrument_name}, skipping"
                )
            return

        head_start, head_end = head_window

        # Get events from section B to determine target pitch
        section_b_events = timeline.get_events_in_range(head_start, head_end)

        # Get RNG from metadata if available (for determinism)
        metadata = plan.metadata
        rng = metadata.get("rng") if metadata else None

        # Choose pickup pitch
        pickup_pitch = choose_pickup_pitch(
            section_b_events,
            harmony_plan=None,  # TODO: pass actual harmony plan
            instrument=instrument_name,
            rng=rng,
            logger=logger,
        )

        # Compute pickup beat: last half-beat before section B
        # Use quarter-beat (0.25 beats) duration for short anacrusis
        pickup_duration = 0.25
        pickup_beat = head_start - pickup_duration

        # Use modest velocity for pickup (64-80 range)
        pickup_velocity = 72

        # Add pickup note to timeline
        # Note: timeline.add_note() expects (pitch, start_beat, duration_beats, velocity, channel)
        # We'll create the event directly since we're modifying an existing timeline
        try:
            # Import NoteEvent from timeline module
            from ..timeline import NoteEvent

            pickup_event = NoteEvent(
                pitch=pickup_pitch,
                start_beat=pickup_beat,
                duration_beats=pickup_duration,
                velocity=pickup_velocity,
                channel=0,  # Use default channel
            )

            timeline.events.append(pickup_event)
            recipe.notes_added = 1

            if logger:
                logger.info(
                    f"[PICKUP] {instrument_name} at beat {pickup_beat:.3f}, "
                    f"pitch={pickup_pitch}, dur={pickup_duration}, vel={pickup_velocity}"
                )

        except Exception as e:
            if logger:
                logger.error(
                    f"apply_transition_plan: failed to add pickup for {instrument_name}: {e}"
                )

        return

    # Handle bridge_start transitions
    if recipe.kind == "bridge_start":
        # Get head window (section B start) and metadata
        head_window = plan.edit_windows.get("head")
        if not head_window:
            if logger:
                logger.warning(
                    f"apply_transition_plan: no head window for bridge_start in {instrument_name}, skipping"
                )
            return

        head_start, head_end = head_window
        metadata = plan.metadata

        # Get energy profiles from metadata
        profile_a = metadata.get("profile_a")
        profile_b = metadata.get("profile_b")

        if not profile_a or not profile_b:
            if logger:
                logger.debug(
                    f"apply_transition_plan: missing energy profiles for bridge_start in {instrument_name}"
                )
            return

        # Calculate blend factor: how much to pull B toward A in bar 1
        # Use 0.5 (50%) as default blend - bar 1 is halfway between A and B energy
        blend_factor = 0.5

        # Get events in first bridge_start_bars of section B
        bridge_bars = recipe.bridge_start_bars
        beats_per_bar = 4.0  # TODO: get from section config
        bridge_beats = bridge_bars * beats_per_bar
        bridge_end = head_start + bridge_beats

        bridge_events = timeline.get_events_in_range(head_start, bridge_end)

        if not bridge_events:
            if logger:
                logger.debug(
                    f"apply_transition_plan: no events in bridge window for {instrument_name}"
                )
            return

        # Blend velocity: interpolate between B's velocity and A's velocity
        # target_velocity = B_velocity * (1 - blend) + A_velocity * blend
        target_avg_velocity = profile_b.avg_velocity * (1 - blend_factor) + profile_a.avg_velocity * blend_factor
        current_avg_velocity = profile_b.avg_velocity

        if current_avg_velocity > 0:
            velocity_scale = target_avg_velocity / current_avg_velocity
            scale_velocities(bridge_events, velocity_scale)

        # Blend density: if B is denser than A, thin events in bar 1
        density_ratio = profile_b.density / profile_a.density if profile_a.density > 0 else 1.0

        # If B is significantly denser (>1.5x), thin to reduce density
        if density_ratio > 1.5:
            # Keep approximately (1 - blend_factor) of the events
            # blend_factor=0.5 means keep ~50% of events (thin 50%)
            thinned_events = thin_events(
                bridge_events,
                keep_downbeats=True,
                beats_per_bar=beats_per_bar
            )
            removed_count = len(bridge_events) - len(thinned_events)

            if removed_count > 0:
                # Remove thinned events from timeline
                bridge_event_ids = {id(ev) for ev in bridge_events}
                thinned_event_ids = {id(ev) for ev in thinned_events}

                timeline.events = [
                    ev for ev in timeline.events
                    if id(ev) not in bridge_event_ids or id(ev) in thinned_event_ids
                ]

                recipe.notes_added = -removed_count

            if logger:
                logger.info(
                    f"[BRIDGE_START] {instrument_name} bar 1: blended vel toward A "
                    f"(scale={velocity_scale:.2f}), thinned {removed_count} events "
                    f"(density_ratio={density_ratio:.2f})"
                )
        else:
            if logger:
                logger.info(
                    f"[BRIDGE_START] {instrument_name} bar 1: blended vel toward A "
                    f"(scale={velocity_scale:.2f}), no thinning needed "
                    f"(density_ratio={density_ratio:.2f})"
                )

        return

    # Handle turnaround transitions
    if recipe.kind == "turnaround":
        # Only apply turnarounds to bass for now
        if instrument_name != "bass":
            if logger:
                logger.debug(
                    f"apply_transition_plan: turnaround only implemented for bass, skipping {instrument_name}"
                )
            return

        # Get tail window (end of section A) and head window (start of section B)
        tail_window = plan.edit_windows.get("tail")
        head_window = plan.edit_windows.get("head")

        if not tail_window or not head_window:
            if logger:
                logger.warning(
                    f"apply_transition_plan: missing tail/head windows for turnaround in {instrument_name}"
                )
            return

        tail_start, tail_end = tail_window
        head_start, head_end = head_window

        # Get events from section B to determine target pitch
        section_b_events = timeline.get_events_in_range(head_start, head_end)

        # Get RNG from metadata
        metadata = plan.metadata
        rng = metadata.get("rng") if metadata else None

        # Extract groove cues from drums timeline if available
        groove_cues = metadata.get("groove_cues")

        # Build bass turnaround figure (with optional groove alignment)
        turnaround_events = build_bass_turnaround(
            tail_start,
            tail_end,
            section_b_events,
            rng,
            groove_cues,
            logger,
        )

        if not turnaround_events:
            if logger:
                logger.debug(
                    f"apply_transition_plan: no turnaround events generated for {instrument_name}"
                )
            return

        # Remove existing events in turnaround window (last 2 beats) to avoid collisions
        turnaround_start = tail_end - 2.0
        turnaround_end = tail_end

        # Get events that conflict with turnaround
        conflicting_events = timeline.get_events_in_range(turnaround_start, turnaround_end)
        conflicting_event_ids = {id(ev) for ev in conflicting_events}

        # Remove conflicting events
        if conflicting_event_ids:
            timeline.events = [
                ev for ev in timeline.events
                if id(ev) not in conflicting_event_ids
            ]

        # Add turnaround events
        timeline.events.extend(turnaround_events)
        recipe.notes_added = len(turnaround_events) - len(conflicting_events)

        if logger:
            logger.info(
                f"[TURNAROUND] {instrument_name} added {len(turnaround_events)} notes "
                f"(replaced {len(conflicting_events)} existing), "
                f"net change: {recipe.notes_added:+d} events"
            )

        return

    if recipe.kind not in ("ramp_up", "ramp_down"):
        if logger:
            logger.debug(
                f"apply_transition_plan: recipe {recipe.kind} not yet implemented "
                f"for {instrument_name}"
            )
        return

    # Get tail window from edit_windows
    tail_window = plan.edit_windows.get("tail")
    if not tail_window:
        if logger:
            logger.warning(
                f"apply_transition_plan: no tail window for {instrument_name}, skipping"
            )
        return

    tail_start, tail_end = tail_window

    # Get events in tail window
    tail_events = timeline.get_events_in_range(tail_start, tail_end)

    if not tail_events:
        if logger:
            logger.debug(
                f"apply_transition_plan: no events in tail window for {instrument_name}"
            )
        return

    # Get beats_per_bar for downbeat detection
    # We'll use a default of 4.0, could be improved by passing actual beats_per_bar
    beats_per_bar = 4.0

    if recipe.kind == "ramp_up":
        # Ramp-up: increase energy
        # - Increase velocity by 20%
        # - Shorten durations by 10% (more staccato = more perceived motion)
        scale_velocities(tail_events, 1.2)
        adjust_durations(tail_events, 0.9)

        if logger:
            logger.debug(
                f"apply_transition_plan: ramp_up applied to {len(tail_events)} events "
                f"in {instrument_name} (vel*1.2, dur*0.9)"
            )

    elif recipe.kind == "ramp_down":
        # Ramp-down: decrease energy
        # - Decrease velocity by 20%
        # - Lengthen durations by 10% (more legato = less perceived motion)
        # - Thin events by removing every other non-downbeat
        scale_velocities(tail_events, 0.8)
        adjust_durations(tail_events, 1.1)

        # Thin events (keep downbeats)
        thinned_events = thin_events(tail_events, keep_downbeats=True, beats_per_bar=beats_per_bar)
        removed_count = len(tail_events) - len(thinned_events)

        # Remove thinned events from timeline using identity-based filtering
        if removed_count > 0:
            # Build sets of event IDs
            tail_event_ids = {id(ev) for ev in tail_events}
            thinned_event_ids = {id(ev) for ev in thinned_events}

            # Keep an event if:
            # - It's not in the tail window (not a tail event), OR
            # - It's in the thinned subset (it survived thinning)
            timeline.events = [
                ev for ev in timeline.events
                if id(ev) not in tail_event_ids or id(ev) in thinned_event_ids
            ]

        if logger:
            logger.debug(
                f"apply_transition_plan: ramp_down applied to {len(tail_events)} events "
                f"in {instrument_name} (vel*0.8, dur*1.1, removed {removed_count} events)"
            )

    # Update notes_added counter (negative for notes removed in ramp_down)
    if recipe.kind == "ramp_down":
        removed_count = len(tail_events) - len(thinned_events)
        recipe.notes_added = -removed_count


def evaluate_transitions(
    cfg: Any,  # RootConfig
    plan: Any,  # SongPlan
    timelines: Dict[str, Any],  # Dict[str, InstrumentTimeline]
    logger: Optional[logging.Logger] = None,
) -> List[TransitionPlan]:
    """Evaluate transition opportunities between sections.

    Analyzes energy profiles at section boundaries and generates transition
    plans based on the configured transition settings.

    Phase 2: Compute profiles and log decisions (no timeline modifications).
    Phase 3: Apply timeline modifications based on plans.

    Args:
        cfg: RootConfig with song settings and transition config.
        plan: SongPlan with section timings and arrangement.
        timelines: Dictionary of InstrumentTimeline objects keyed by instrument name.
        logger: Optional logger for debug output.

    Returns:
        List[TransitionPlan]: Generated transition plans (not yet applied).
    """
    from ..rng import make_section_rng

    if logger is None:
        logger = logging.getLogger(__name__)

    # Get transition settings
    song_transitions = getattr(cfg.song, 'transitions', None)
    if song_transitions is None or not getattr(song_transitions, 'enabled', True):
        logger.debug("evaluate_transitions: transitions disabled globally")
        return []

    debug = getattr(song_transitions, 'debug', False)

    # Get arrangement and section timings
    arrangement = getattr(cfg, 'arrangement', [])
    section_timings = getattr(plan, 'section_timings', [])

    # Build section timing lookup
    timing_by_id = {st.id: st for st in section_timings}

    plans = []

    # Iterate through arrangement pairs
    for i in range(len(arrangement) - 1):
        section_a_id = arrangement[i]
        section_b_id = arrangement[i + 1]

        timing_a = timing_by_id.get(section_a_id)
        timing_b = timing_by_id.get(section_b_id)

        if not timing_a or not timing_b:
            if debug:
                logger.debug(
                    f"evaluate_transitions: missing timing for {section_a_id} or {section_b_id}"
                )
            continue

        # Get section configs
        sections = getattr(cfg, 'sections', {})
        section_a_cfg = sections.get(section_a_id)
        section_b_cfg = sections.get(section_b_id)

        if not section_a_cfg or not section_b_cfg:
            continue

        # Find instruments present in both sections
        instruments_a = set(getattr(section_a_cfg, 'instruments', {}).keys())
        instruments_b = set(getattr(section_b_cfg, 'instruments', {}).keys())
        common_instruments = instruments_a & instruments_b

        # Generate RNG for this transition (deterministic)
        runtime = getattr(cfg, 'runtime', None)
        project_seed = getattr(runtime, 'project_seed', 0) if runtime else 0
        song_seed = getattr(cfg.song, 'seed', 0)
        take = getattr(cfg.song, 'take', 0)
        transition_rng = make_section_rng(
            project_seed, song_seed, take,
            f"{section_a_id}_{section_b_id}", "transition"
        )

        for inst_name in sorted(common_instruments):
            timeline = timelines.get(inst_name)
            if not timeline:
                continue

            # Get transition settings (instrument override or song default)
            inst_cfg = getattr(section_a_cfg, 'instruments', {}).get(inst_name)
            inst_transitions = getattr(inst_cfg, 'transitions', None) if inst_cfg else None

            # Resolve effective settings (instrument override takes precedence)
            if inst_transitions is not None:
                effective_settings = inst_transitions
            else:
                effective_settings = song_transitions

            # Get ramp_bars for analysis window
            ramp_bars = getattr(effective_settings, 'ramp_bars', 1)
            if ramp_bars <= 0:
                ramp_bars = 1

            beats_per_bar = timing_a.beats_per_bar

            # Define analysis windows
            # Tail of section A: last ramp_bars
            tail_beats = ramp_bars * beats_per_bar
            tail_start = max(timing_a.start_beat, timing_a.end_beat - tail_beats)
            tail_end = timing_a.end_beat

            # Head of section B: first ramp_bars (or bridge_start_bars for bridge sections)
            section_b_type = getattr(section_b_cfg, 'type', '').lower()
            if section_b_type == 'bridge':
                bridge_bars = getattr(effective_settings, 'bridge_start_bars', 1)
                head_beats = max(bridge_bars, ramp_bars) * beats_per_bar
            else:
                head_beats = ramp_bars * beats_per_bar

            head_start = timing_b.start_beat
            head_end = min(timing_b.end_beat, timing_b.start_beat + head_beats)

            # Get events in analysis windows
            events_a = timeline.get_events_in_range(tail_start, tail_end)
            events_b = timeline.get_events_in_range(head_start, head_end)

            # Compute energy profiles
            profile_a = compute_energy_profile(
                events_a,
                tail_end - tail_start,
                getattr(section_a_cfg, 'meter', '4/4'),
                logger if debug else None,
            )

            profile_b = compute_energy_profile(
                events_b,
                head_end - head_start,
                getattr(section_b_cfg, 'meter', '4/4'),
                logger if debug else None,
            )

            # Choose transition recipe
            recipe = choose_transition_recipe(
                profile_a,
                profile_b,
                effective_settings,
                transition_rng,
                logger if debug else None,
            )

            # Extract groove cues from drums for bass coordination (Phase 7)
            groove_cues = None
            if inst_name == "bass":
                drums_timeline = timelines.get("drums")
                if drums_timeline:
                    # Extract groove cues from drums tail window (turnaround region)
                    drum_events = drums_timeline.get_events_in_range(
                        tail_start, tail_end
                    )
                    groove_cues = extract_groove_cues(
                        drum_events,
                        tail_start,
                        tail_end,
                        beats_per_bar,
                        logger if debug else None,
                    )

            # Build transition plan
            plan_obj = TransitionPlan(
                section_a_id=section_a_id,
                section_b_id=section_b_id,
                instrument=inst_name,
                recipe=recipe,
                edit_windows={
                    "tail": (tail_start, tail_end),
                    "head": (head_start, head_end),
                },
                metadata={
                    "profile_a": profile_a,
                    "profile_b": profile_b,
                    "rng": transition_rng,  # For deterministic pickup pitch selection
                    "groove_cues": groove_cues,  # For bass-drum coordination (Phase 7)
                    "settings": {
                        "enabled": getattr(effective_settings, 'enabled', True),
                        "strength": getattr(effective_settings, 'strength', 0.5),
                        "ramp_bars": getattr(effective_settings, 'ramp_bars', 1),
                    }
                }
            )

            plans.append(plan_obj)

            # Debug logging
            if debug and recipe.kind != "none":
                # Compute energy delta for logging
                delta_density = profile_b.density - profile_a.density
                delta_velocity = (profile_b.avg_velocity - profile_a.avg_velocity) / 127.0
                delta_register = (profile_b.register_center - profile_a.register_center) / 48.0
                energy_delta = (
                    0.5 * delta_density +
                    0.3 * delta_velocity +
                    0.2 * delta_register
                ) * getattr(effective_settings, 'strength', 0.5)

                logger.info(
                    f"[TRANSITION] {section_a_id} -> {section_b_id} inst={inst_name} "
                    f"kind={recipe.kind} energy_delta={energy_delta:+.3f} "
                    f"ramp_bars={recipe.ramp_bars}"
                )

    return plans


# ============================================================================
# Phase N5: Section-level transition planning (lookahead directives)
# ============================================================================


@dataclass
class SectionTransition:
    """Section-level transition directive for engine lookahead (Phase N5).

    Provides high-level guidance for how to lead from one section into the next.
    These directives are computed once per song and stored in the PerformancePlan
    for engines to consult during rendering.

    Attributes:
        section_id: Source section identifier.
        next_section_id: Target section identifier (None if last section).
        next_section_type: Target section type (None if last section).
        energy_ramp: Energy trajectory (-1.0 = ramp down, 0.0 = maintain, +1.0 = ramp up).
        density_ramp: Note density trajectory (-1.0 = thin out, 0.0 = maintain, +1.0 = fill).
        lead_in_bars: Number of bars before transition to start ramping (typically 1-2).
        turnaround_hint: Turnaround intensity ("none", "light", "heavy").
        pickup_hint: Whether to use pickup notes before transition.
        is_first_section: True if this is the first section in the arrangement.
        is_last_section: True if this is the last section in the arrangement.
    """
    section_id: str
    next_section_id: Optional[str]
    next_section_type: Optional[str]
    energy_ramp: float
    density_ramp: float
    lead_in_bars: int
    turnaround_hint: str
    pickup_hint: bool
    is_first_section: bool
    is_last_section: bool


# Section type energy levels for relative comparison
_SECTION_ENERGY_MAP = {
    "intro": 0.3,
    "verse": 0.5,
    "pre_chorus": 0.7,
    "prechorus": 0.7,
    "chorus": 1.0,
    "bridge": 0.8,
    "solo": 0.9,
    "breakdown": 0.4,
    "outro": 0.3,
    "interlude": 0.5,
}


def _compute_section_energy_ramp(current_type: str, next_type: Optional[str]) -> float:
    """Compute energy ramp from current section to next section.

    Args:
        current_type: Current section type.
        next_type: Next section type (None if last section).

    Returns:
        float: Energy ramp value (-1.0 to +1.0).
    """
    if next_type is None:
        return -0.5  # Ramp down for ending

    current_energy = _SECTION_ENERGY_MAP.get(current_type.lower(), 0.5)
    next_energy = _SECTION_ENERGY_MAP.get(next_type.lower(), 0.5)

    # Normalize to -1.0..+1.0 range
    energy_delta = next_energy - current_energy
    return max(-1.0, min(1.0, energy_delta * 2.0))


def _compute_section_density_ramp(current_type: str, next_type: Optional[str]) -> float:
    """Compute density ramp from current section to next section.

    Args:
        current_type: Current section type.
        next_type: Next section type (None if last section).

    Returns:
        float: Density ramp value (-1.0 to +1.0).
    """
    if next_type is None:
        return -0.7  # Thin out for ending

    next_type_lower = next_type.lower()
    current_type_lower = current_type.lower()

    # Density generally follows energy with some variations
    if next_type_lower == "breakdown":
        return -0.8  # Sparse breakdown
    elif next_type_lower == "chorus":
        return 0.8  # Full chorus
    elif next_type_lower == "verse" and current_type_lower == "chorus":
        return -0.5  # Pull back from chorus to verse
    elif next_type_lower == "solo":
        return 0.6  # Build density for solo
    else:
        # Default: follow energy ramp with slight dampening
        energy_ramp = _compute_section_energy_ramp(current_type, next_type)
        return energy_ramp * 0.8


def _compute_section_lead_in_bars(current_type: str, next_type: Optional[str]) -> int:
    """Compute how many bars before transition to start ramping.

    Args:
        current_type: Current section type.
        next_type: Next section type (None if last section).

    Returns:
        int: Number of bars (typically 1-2).
    """
    if next_type is None:
        return 2  # Longer lead-in for ending

    current_type_lower = current_type.lower()
    next_type_lower = next_type.lower()

    # Major transitions get longer lead-in
    if current_type_lower in ("verse", "pre_chorus", "prechorus") and next_type_lower == "chorus":
        return 2  # Build anticipation for chorus
    elif current_type_lower == "chorus" and next_type_lower in ("verse", "bridge"):
        return 1  # Quick pullback
    elif next_type_lower == "breakdown":
        return 2  # Signal the breakdown
    else:
        return 1  # Default lead-in


def _compute_section_turnaround_hint(
    current_type: str,
    next_type: Optional[str],
    is_last_section: bool,
) -> str:
    """Compute turnaround intensity hint.

    Args:
        current_type: Current section type.
        next_type: Next section type (None if last section).
        is_last_section: Whether this is the last section.

    Returns:
        str: Turnaround hint ("none", "light", "heavy").
    """
    if is_last_section:
        return "heavy"  # Strong turnaround for song ending

    if next_type is None:
        return "none"

    current_type_lower = current_type.lower()
    next_type_lower = next_type.lower()

    # Heavy turnaround when returning to beginning or major change
    if current_type_lower == "chorus" and next_type_lower == "verse":
        return "light"  # Gentle return
    elif current_type_lower in ("bridge", "solo") and next_type_lower == "chorus":
        return "heavy"  # Strong return to chorus
    elif next_type_lower == "breakdown":
        return "light"  # Signal breakdown
    else:
        return "none"  # No turnaround needed


def _compute_section_pickup_hint(current_type: str, next_type: Optional[str]) -> bool:
    """Compute whether to use pickup notes before transition.

    Args:
        current_type: Current section type.
        next_type: Next section type (None if last section).

    Returns:
        bool: True if pickup notes recommended.
    """
    if next_type is None:
        return False  # No pickup for ending

    next_type_lower = next_type.lower()
    current_type_lower = current_type.lower()

    # Pickup notes help anticipate major section changes
    if next_type_lower in ("chorus", "solo", "bridge"):
        return True
    elif current_type_lower == "intro" and next_type_lower == "verse":
        return True  # Lead into first verse
    else:
        return False


def transition_occurrence_key(arrangement_index: int, section_id: str) -> str:
    """Return the per-occurrence transitions-map key for a section.

    Repeated sections (the same section id appearing multiple times in the
    arrangement) get distinct directives keyed by their arrangement index.
    """
    return f"{int(arrangement_index):02d}:{section_id}"


def get_section_transition(
    transitions_map: Optional[Dict[str, Any]],
    section_id: str,
    arrangement_index: Optional[int] = None,
):
    """Look up a transition directive, preferring the per-occurrence key.

    Args:
        transitions_map: Map produced by `build_section_transitions_map()` (or
            its serialized form).
        section_id: Section identifier (e.g., "verse1").
        arrangement_index: Optional arrangement occurrence index. When given,
            the per-occurrence entry is preferred; the plain `section_id` key
            (last occurrence) is the backward-compatible fallback.

    Returns:
        The directive (SectionTransition or serialized dict) or None.
    """
    if not transitions_map:
        return None
    if arrangement_index is not None:
        directive = transitions_map.get(
            transition_occurrence_key(arrangement_index, section_id)
        )
        if directive is not None:
            return directive
    return transitions_map.get(section_id)


def build_section_transitions_map(
    planned_sections: list,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, SectionTransition]:
    """Build section-level transition directives for all sections (Phase N5).

    Analyzes the arrangement to generate lookahead hints for each section.
    Each section gets directives for how to transition into the next section.

    These are high-level directives that engines can consult during rendering
    to adjust their output for better musical flow. Unlike the timeline-based
    transitions in evaluate_transitions(), these are computed once per song
    and stored in the PerformancePlan before rendering begins.

    Keying:
      - The primary key is per arrangement occurrence
        (`"<NN>:<section_id>"`, see `transition_occurrence_key()`), so a
        repeated section gets the correct directive for *each* occurrence.
      - For backward compatibility, the directive is ALSO stored under the
        plain `section_id` key; for repeated sections that alias holds the
        last occurrence's directive (legacy behavior). Both keys reference
        the same directive object.

    Args:
        planned_sections: List of PlannedSection objects from BuildPlan.
        logger: Optional logger for debug output.

    Returns:
        Dict[str, SectionTransition]: Map of occurrence-key (and legacy
        section_id alias) -> transition directive.
    """
    transitions_map: Dict[str, SectionTransition] = {}
    num_sections = len(planned_sections)

    for i, ps in enumerate(planned_sections):
        is_first = (i == 0)
        is_last = (i == num_sections - 1)

        # Look ahead to next section
        next_ps = planned_sections[i + 1] if not is_last else None
        next_section_id = next_ps.sec_id if next_ps else None
        next_section_type = next_ps.sec.type if next_ps else None

        current_type = ps.sec.type

        # Compute transition directives
        energy_ramp = _compute_section_energy_ramp(current_type, next_section_type)
        density_ramp = _compute_section_density_ramp(current_type, next_section_type)
        lead_in_bars = _compute_section_lead_in_bars(current_type, next_section_type)
        turnaround_hint = _compute_section_turnaround_hint(current_type, next_section_type, is_last)
        pickup_hint = _compute_section_pickup_hint(current_type, next_section_type)

        directive = SectionTransition(
            section_id=ps.sec_id,
            next_section_id=next_section_id,
            next_section_type=next_section_type,
            energy_ramp=energy_ramp,
            density_ramp=density_ramp,
            lead_in_bars=lead_in_bars,
            turnaround_hint=turnaround_hint,
            pickup_hint=pickup_hint,
            is_first_section=is_first,
            is_last_section=is_last,
        )

        # Primary, per-occurrence key (repeated sections stay distinct) plus a
        # legacy alias under the bare section id (last occurrence wins).
        transitions_map[transition_occurrence_key(i, ps.sec_id)] = directive
        transitions_map[ps.sec_id] = directive

        if logger:
            logger.debug(
                f"Section '{ps.sec_id}' (occurrence {i}, {current_type}) -> '{next_section_id}' ({next_section_type}): "
                f"energy_ramp={energy_ramp:+.1f}, density_ramp={density_ramp:+.1f}, "
                f"lead_in_bars={lead_in_bars}, turnaround={turnaround_hint}, pickup={pickup_hint}"
            )

    return transitions_map


def serialize_section_transitions_map(
    transitions_map: Dict[str, SectionTransition]
) -> Dict[str, Dict]:
    """Serialize section transitions map to plain dict for storage in PerformancePlan.

    Aliased keys (per-occurrence key + legacy section_id key pointing at the
    same directive) serialize to the SAME dict object so in-place adjustments
    (e.g. negotiation feedback) stay consistent across both keys.

    Args:
        transitions_map: Map of occurrence-key / section_id -> SectionTransition.

    Returns:
        Dict[str, Dict]: Serialized transitions map (plain dicts).
    """
    serialized: Dict[str, Dict] = {}
    memo: Dict[int, Dict] = {}
    for section_id, directive in transitions_map.items():
        cached = memo.get(id(directive))
        if cached is None:
            cached = {
                "section_id": directive.section_id,
                "next_section_id": directive.next_section_id,
                "next_section_type": directive.next_section_type,
                "energy_ramp": directive.energy_ramp,
                "density_ramp": directive.density_ramp,
                "lead_in_bars": directive.lead_in_bars,
                "turnaround_hint": directive.turnaround_hint,
                "pickup_hint": directive.pickup_hint,
                "is_first_section": directive.is_first_section,
                "is_last_section": directive.is_last_section,
            }
            memo[id(directive)] = cached
        serialized[section_id] = cached
    return serialized
