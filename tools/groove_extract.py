"""Phase 3: Groove and Timing Features Extraction Module.

Analyzes timing micro-variations, swing, push/pull, syncopation, and accents
from parsed MIDI events to characterize the groove feel of each track.
"""

import logging
import json
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from statistics import mean, stdev

from midi_parse import MIDIAnalysis, NoteEvent


logger = logging.getLogger(__name__)


@dataclass
class GrooveFeatures:
    """Groove and timing features for a song."""
    song_id: str

    # Swing ratio: 0.5 = straight, >0.5 = swing (typical jazz ~0.67)
    swing_ratio: float
    swing_confidence: float  # 0.0-1.0, based on sample size

    # Push/pull: negative = rushed/anticipated, positive = dragged
    push_pull_ms: float
    push_pull_confidence: float

    # Syncopation: 0.0 = all on-beat, 1.0 = heavy off-beat emphasis
    syncopation_intensity: float

    # Accent pattern strength: 0.0 = flat dynamics, 1.0 = strong accents
    accent_strength: float

    # Supporting stats
    total_events: int
    eighth_note_pairs: int  # samples used for swing calculation
    grid_deviations_count: int  # events used for push/pull


def extract_groove_features(analysis: MIDIAnalysis) -> GrooveFeatures:
    """Extract groove and timing features from MIDI analysis."""
    if not analysis.events:
        return _empty_features(analysis.song_id)

    # Filter to non-drum events for swing/push-pull analysis
    # (drums often have intentional timing variations)
    melodic_events = [e for e in analysis.events if not e.is_drum_guess]

    if not melodic_events:
        # Drum-only track, use all events
        melodic_events = analysis.events

    # Calculate features
    swing_ratio, swing_conf, eighth_pairs = _calculate_swing(
        melodic_events, analysis.ticks_per_beat
    )

    push_pull, pp_conf, grid_devs = _calculate_push_pull(
        melodic_events, analysis.ticks_per_beat
    )

    syncopation = _calculate_syncopation(melodic_events)

    accent_strength = _calculate_accent_strength(analysis.events)

    return GrooveFeatures(
        song_id=analysis.song_id,
        swing_ratio=swing_ratio,
        swing_confidence=swing_conf,
        push_pull_ms=push_pull,
        push_pull_confidence=pp_conf,
        syncopation_intensity=syncopation,
        accent_strength=accent_strength,
        total_events=len(analysis.events),
        eighth_note_pairs=eighth_pairs,
        grid_deviations_count=grid_devs,
    )


def _empty_features(song_id: str) -> GrooveFeatures:
    """Return empty feature set for tracks with no events."""
    return GrooveFeatures(
        song_id=song_id,
        swing_ratio=0.5,
        swing_confidence=0.0,
        push_pull_ms=0.0,
        push_pull_confidence=0.0,
        syncopation_intensity=0.0,
        accent_strength=0.0,
        total_events=0,
        eighth_note_pairs=0,
        grid_deviations_count=0,
    )


def _calculate_swing(
    events: List[NoteEvent],
    ticks_per_beat: int,
) -> Tuple[float, float, int]:
    """Calculate swing ratio from eighth-note pairs.

    Swing ratio = duration_of_first_eighth / (first + second)
    - 0.5 = straight eighths
    - 0.67 = triplet swing (2:1 ratio)
    - 0.75 = extreme swing (3:1 ratio)

    Returns: (swing_ratio, confidence, num_pairs)
    """
    if not events:
        return 0.5, 0.0, 0

    # Sort events by start time
    sorted_events = sorted(events, key=lambda e: e.start_tick)

    # Find consecutive note pairs on eighth-note grid
    eighth_tick = ticks_per_beat / 2.0
    tolerance = ticks_per_beat * 0.1  # 10% tolerance

    swing_ratios = []

    for i in range(len(sorted_events) - 1):
        e1 = sorted_events[i]
        e2 = sorted_events[i + 1]

        # Check if e1 starts on an eighth-note beat
        beat_offset = e1.start_tick % ticks_per_beat
        on_eighth = (
            abs(beat_offset) < tolerance or
            abs(beat_offset - eighth_tick) < tolerance
        )

        if not on_eighth:
            continue

        # Check if e2 follows e1 within ~1 beat
        gap = e2.start_tick - e1.start_tick
        if gap < eighth_tick * 0.5 or gap > ticks_per_beat * 1.5:
            continue

        # Calculate swing ratio
        # (gap represents the "first eighth" in a pair)
        # Ideal second eighth = ticks_per_beat - gap
        total_pair_duration = ticks_per_beat
        ratio = gap / total_pair_duration

        # Only accept reasonable swing values (0.4 to 0.8)
        if 0.4 <= ratio <= 0.8:
            swing_ratios.append(ratio)

    if not swing_ratios:
        return 0.5, 0.0, 0

    avg_swing = mean(swing_ratios)

    # Confidence based on sample size and consistency
    confidence = min(1.0, len(swing_ratios) / 50.0)
    if len(swing_ratios) >= 3:
        variation = stdev(swing_ratios)
        # Lower variation = higher confidence
        confidence *= max(0.2, 1.0 - variation)

    return avg_swing, confidence, len(swing_ratios)


def _calculate_push_pull(
    events: List[NoteEvent],
    ticks_per_beat: int,
) -> Tuple[float, float, int]:
    """Calculate push/pull (timing anticipation/drag) in milliseconds.

    Negative values = rushed/anticipated (notes early)
    Positive values = dragged/laid-back (notes late)

    Returns: (push_pull_ms, confidence, num_deviations)
    """
    if not events:
        return 0.0, 0.0, 0

    # Assume 120 BPM as baseline for ms conversion (will be adjusted by tempo)
    # At 120 BPM: 1 beat = 500ms, 1 tick = 500/ticks_per_beat ms
    baseline_bpm = 120.0
    ms_per_tick = (60000.0 / baseline_bpm) / ticks_per_beat

    # Find deviations from nearest grid position (16th notes)
    sixteenth_tick = ticks_per_beat / 4.0
    deviations_ticks = []

    for event in events:
        # Find nearest 16th-note grid position
        nearest_grid = round(event.start_tick / sixteenth_tick) * sixteenth_tick
        deviation = event.start_tick - nearest_grid

        # Only count significant deviations (> 5% of a 16th note)
        if abs(deviation) > sixteenth_tick * 0.05:
            deviations_ticks.append(deviation)

    if not deviations_ticks:
        return 0.0, 0.0, 0

    avg_deviation_ticks = mean(deviations_ticks)
    avg_deviation_ms = avg_deviation_ticks * ms_per_tick

    # Confidence based on sample size
    confidence = min(1.0, len(deviations_ticks) / 100.0)

    return avg_deviation_ms, confidence, len(deviations_ticks)


def _calculate_syncopation(events: List[NoteEvent]) -> float:
    """Calculate syncopation intensity (0.0 = on-beat, 1.0 = heavy off-beat).

    Measures proportion of notes that fall on off-beat positions.
    """
    if not events:
        return 0.0

    onbeat_count = 0
    offbeat_count = 0

    for event in events:
        # Check if note is on a strong beat (0, 1, 2, 3 in 4/4)
        beat_position = event.beat_in_bar

        # Strong beats: exact integers (0.0, 1.0, 2.0, 3.0)
        on_strong_beat = abs(beat_position - round(beat_position)) < 0.05

        if on_strong_beat:
            onbeat_count += 1
        else:
            # Check if on weak eighth (0.5, 1.5, 2.5, 3.5)
            nearest_eighth = round(beat_position * 2.0) / 2.0
            on_eighth = abs(beat_position - nearest_eighth) < 0.05

            if on_eighth and not on_strong_beat:
                offbeat_count += 1

    total = onbeat_count + offbeat_count
    if total == 0:
        return 0.0

    # Syncopation = ratio of off-beat to total
    return offbeat_count / total


def _calculate_accent_strength(events: List[NoteEvent]) -> float:
    """Calculate accent strength (0.0 = flat, 1.0 = strong dynamics).

    Measures velocity variation across events.
    """
    if not events:
        return 0.0

    velocities = [e.velocity for e in events]

    if len(velocities) < 2:
        return 0.0

    avg_vel = mean(velocities)

    # Avoid division by zero
    if avg_vel < 1:
        return 0.0

    variation = stdev(velocities)

    # Normalize: typical variation is 10-30 velocity units
    # Map to 0.0-1.0 scale
    normalized = variation / 30.0

    return min(1.0, normalized)


def write_groove_json(
    song_id: str,
    features: GrooveFeatures,
    out_path: Path,
) -> None:
    """Write groove features to JSON file."""
    data = {
        "song_id": song_id,
        "features": asdict(features),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_groove_summary(
    all_features: Dict[str, GrooveFeatures],
    out_path: Path,
) -> None:
    """Write aggregate groove statistics summary."""
    # Aggregate statistics
    swing_values = []
    push_pull_values = []
    syncopation_values = []
    accent_values = []

    for features in all_features.values():
        if features.swing_confidence > 0.3:
            swing_values.append(features.swing_ratio)

        if features.push_pull_confidence > 0.3:
            push_pull_values.append(features.push_pull_ms)

        if features.total_events > 10:
            syncopation_values.append(features.syncopation_intensity)
            accent_values.append(features.accent_strength)

    # Write TSV summary
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("metric\tcount\tmean\tstdev\tmin\tmax\n")

        metrics = [
            ("swing_ratio", swing_values),
            ("push_pull_ms", push_pull_values),
            ("syncopation", syncopation_values),
            ("accent_strength", accent_values),
        ]

        for metric_name, values in metrics:
            if not values:
                f.write(f"{metric_name}\t0\t0.000\t0.000\t0.000\t0.000\n")
                continue

            count = len(values)
            mean_val = mean(values)
            stdev_val = stdev(values) if len(values) > 1 else 0.0
            min_val = min(values)
            max_val = max(values)

            f.write(
                f"{metric_name}\t{count}\t{mean_val:.3f}\t{stdev_val:.3f}\t"
                f"{min_val:.3f}\t{max_val:.3f}\n"
            )
