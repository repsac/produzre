"""Rhythm feature extraction for cross-instrument coupling.

This module extracts rhythmic "skeleton" features from drums that other instruments
can use to lock into the groove. Features include strong beats, accent patterns,
fill windows, and density metrics.

Design goals:
- Generic: works with any instrument (drums, perc, etc.)
- Lightweight: simple data structures
- Time-indexed: features mapped to beat positions
- Deterministic: same events = same features

Usage:
    # In drums engine:
    from produzre.rhythm_features import extract_rhythm_features
    features = extract_rhythm_features(events, total_beats, beats_per_bar)
    # Store features for other instruments to access

    # In bass engine:
    features = get_rhythm_features("drums")  # From shared context
    if features:
        # Place bass notes on kick strong beats
        for beat in features.strong_beats:
            add_bass_note(beat, ...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class RhythmFeatures:
    """Extracted rhythm features from an instrument (typically drums).

    Attributes:
        strong_beats: Set of beat positions where strong rhythmic events occur.
            For drums: kick hits, especially downbeats and accented kicks.
        accent_beats: Set of beat positions with accented hits.
            For drums: accented snares, crash hits.
        fill_windows: List of (start_beat, end_beat) tuples where fills occur.
            Other instruments should lay back or simplify during fills.
        silence_windows: List of (start_beat, end_beat) tuples with minimal activity.
            Other instruments can fill space here.
        density_per_bar: Dict[bar_idx, density] where density is events per beat.
            For drums: hat density, useful for rhythm guitar to match.
        syncopation_beats: Set of beat positions with syncopated events.
            For drums: off-beat kicks, useful for rhythm guitar palm mutes.
        section_id: Section identifier for these features.
        instrument: Instrument name these features came from.

    Notes:
        - All beat positions are section-relative (0.0 = section start)
        - Bar indices are 0-based
        - Density is calculated as events_in_bar / beats_per_bar
    """

    strong_beats: Set[float] = field(default_factory=set)
    accent_beats: Set[float] = field(default_factory=set)
    fill_windows: List[tuple[float, float]] = field(default_factory=list)
    silence_windows: List[tuple[float, float]] = field(default_factory=list)
    density_per_bar: Dict[int, float] = field(default_factory=dict)
    syncopation_beats: Set[float] = field(default_factory=set)
    section_id: str = ""
    instrument: str = ""


def extract_rhythm_features(
    events: List[Any],
    total_beats: float,
    beats_per_bar: float,
    pitches: Dict[str, int],
    section_id: str = "",
    instrument: str = "drums",
) -> RhythmFeatures:
    """Extract rhythm features from drum events.

    Args:
        events: List of DrumEvent objects with beat, pitch, velocity, kind attributes.
        total_beats: Section duration in beats.
        beats_per_bar: Meter beats per bar.
        pitches: Pitch mapping for identifying voices (kick, snare, hat, etc.).
        section_id: Section identifier.
        instrument: Instrument name.

    Returns:
        RhythmFeatures with extracted rhythmic skeleton.

    Feature Extraction Rules (for drums):
        - Strong beats: Kick hits, especially downbeats and accented
        - Accent beats: Snares with velocity >= 80, crashes
        - Fill windows: Consecutive "fill" kind events
        - Silence windows: Bars with < 0.5 density
        - Density per bar: Hat events per beat in each bar
        - Syncopation beats: Off-beat kicks (not on downbeat or backbeat)

    Notes:
        - Features are section-relative (beat 0.0 = section start)
        - Downbeats: beats 0, 4, 8, ... (in 4/4)
        - Backbeats: beats 2, 6, 10, ... (in 4/4, where snare typically lands)
        - Off-beats: everything else
    """
    bpb = float(beats_per_bar)
    tb = float(total_beats)
    bars = int(tb / bpb) if bpb > 0 else 0

    # Identify drum voices from pitches
    kick_pitch = int(pitches.get("kick", 36))
    snare_pitch = int(pitches.get("snare", 38))
    crash_pitch = int(pitches.get("crash", 49))
    hat_closed = int(pitches.get("hat_closed", 42))
    hat_open = int(pitches.get("hat_open", 46))
    ride_pitch = int(pitches.get("ride", 51))

    hat_pitches = {hat_closed, hat_open, ride_pitch}

    features = RhythmFeatures(section_id=section_id, instrument=instrument)

    # Track events per bar for density calculation
    events_per_bar: Dict[int, List[Any]] = {}
    hat_events_per_bar: Dict[int, int] = {}

    # Fill tracking: collect fill events (and the pitches they use) so windows
    # are built from fill events only. Interleaved non-fill events from OTHER
    # voices (e.g. hats during a tom fill) must not fragment a window.
    fill_events: List[tuple[float, float]] = []  # (beat, end_beat)
    fill_pitch_set: Set[int] = set()
    non_fill_events: List[tuple[float, int]] = []  # (beat, pitch)

    for ev in events:
        beat = float(getattr(ev, "beat", 0.0))
        pitch = int(getattr(ev, "pitch", 0))
        velocity = int(getattr(ev, "velocity", 80))
        kind = str(getattr(ev, "kind", ""))

        bar_idx = int(beat / bpb) if bpb > 0 else 0

        # Track events per bar
        events_per_bar.setdefault(bar_idx, []).append(ev)

        # Count hat events per bar for density
        if pitch in hat_pitches:
            hat_events_per_bar[bar_idx] = hat_events_per_bar.get(bar_idx, 0) + 1

        # Strong beats: kicks (especially downbeats)
        if pitch == kick_pitch:
            features.strong_beats.add(beat)

        # Accent beats: accented snares and crashes
        if (pitch == snare_pitch and velocity >= 80) or pitch == crash_pitch:
            features.accent_beats.add(beat)

        # Syncopation beats: off-beat kicks only. On-beat kicks (downbeats,
        # backbeats, or any integer beat position) are NOT syncopated.
        if pitch == kick_pitch:
            beat_in_bar = beat % bpb if bpb > 0 else beat
            nearest_beat = round(beat_in_bar)
            is_on_beat = abs(beat_in_bar - nearest_beat) < 0.1
            if not is_on_beat:
                features.syncopation_beats.add(beat)

        # Collect fill / non-fill events for window construction below.
        if "fill" in kind:
            end = beat + float(getattr(ev, "duration_beats", 0.25))
            fill_events.append((beat, end))
            fill_pitch_set.add(pitch)
        else:
            non_fill_events.append((beat, pitch))

    # Build fill windows from fill events only. A window ends when:
    #   - the gap to the next fill event exceeds a threshold, or
    #   - a non-fill event of the SAME kind family (same pitch as one of the
    #     fill voices) lands strictly between the current window's end and
    #     the next fill event.
    # Interleaved events from other voices never break a window.
    GAP_THRESHOLD_BEATS = 1.0
    if fill_events:
        fill_events.sort(key=lambda fe: fe[0])
        breaker_beats = sorted(
            b for b, p in non_fill_events if p in fill_pitch_set
        )

        def _breaker_between(lo: float, hi: float) -> bool:
            return any(lo < b <= hi for b in breaker_beats)

        win_start, win_end = fill_events[0]
        for beat, end in fill_events[1:]:
            gap_exceeded = (beat - win_end) > GAP_THRESHOLD_BEATS
            if gap_exceeded or _breaker_between(win_end, beat):
                features.fill_windows.append((win_start, win_end))
                win_start, win_end = beat, end
            else:
                win_end = max(win_end, end)
        features.fill_windows.append((win_start, win_end))

    # Calculate density per bar (hat events per beat)
    for bar_idx in range(bars):
        hat_count = hat_events_per_bar.get(bar_idx, 0)
        density = float(hat_count) / bpb if bpb > 0 else 0.0
        features.density_per_bar[bar_idx] = density

    # Identify silence windows: bars with low overall density
    silence_threshold = 0.5  # events per beat
    for bar_idx in range(bars):
        bar_events = events_per_bar.get(bar_idx, [])
        bar_density = float(len(bar_events)) / bpb if bpb > 0 else 0.0

        if bar_density < silence_threshold:
            bar_start = float(bar_idx) * bpb
            bar_end = min(tb, bar_start + bpb)
            features.silence_windows.append((bar_start, bar_end))

    return features


def is_beat_in_fill(beat: float, features: RhythmFeatures) -> bool:
    """Check if a beat position falls within a fill window.

    Args:
        beat: Beat position (section-relative).
        features: RhythmFeatures to check against.

    Returns:
        True if beat is within any fill window.

    Usage:
        if not is_beat_in_fill(beat, drum_features):
            # Safe to place bass note (not conflicting with fill)
            add_bass_note(beat, ...)
    """
    for start, end in features.fill_windows:
        if start <= beat < end:
            return True
    return False


def is_beat_in_silence(beat: float, features: RhythmFeatures) -> bool:
    """Check if a beat position falls within a silence window.

    Args:
        beat: Beat position (section-relative).
        features: RhythmFeatures to check against.

    Returns:
        True if beat is within any silence window.

    Usage:
        if is_beat_in_silence(beat, drum_features):
            # Opportunity for bass to fill space
            add_bass_note(beat, ...)
    """
    for start, end in features.silence_windows:
        if start <= beat < end:
            return True
    return False


def get_bar_density(bar_idx: int, features: RhythmFeatures) -> float:
    """Get hat density for a specific bar.

    Args:
        bar_idx: Bar index (0-based).
        features: RhythmFeatures to query.

    Returns:
        Density (events per beat) for the bar, or 0.0 if not found.

    Usage:
        density = get_bar_density(2, drum_features)
        # Use density to scale rhythm guitar palm mute frequency
        palm_mute_rate = density * 0.5
    """
    return features.density_per_bar.get(bar_idx, 0.0)
