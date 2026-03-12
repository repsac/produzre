"""Phase 2: Instrument Role Classification Module.

Classifies MIDI tracks/channels as drums, bass, rhythm guitar, or lead guitar
based on pitch range, density, polyphony, and sustain patterns.
"""

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from midi_parse import MIDIAnalysis, NoteEvent


logger = logging.getLogger(__name__)


@dataclass
class RoleClassification:
    """Classification result for a track/channel."""
    track_name: str
    channel: int
    role: str  # "drums", "bass", "rhythm", "lead", "other"
    confidence: float  # 0.0–1.0
    rationale: str
    event_count: int
    pitch_range: Tuple[int, int]  # (min, max)
    avg_pitch: float
    polyphony_score: float  # 0.0 (monophonic) to 1.0 (highly polyphonic)
    density_score: float  # events per beat


def classify_roles(analysis: MIDIAnalysis) -> List[RoleClassification]:
    """Classify instrument roles for all tracks/channels in a MIDI file."""
    if not analysis.events:
        return []

    # Group events by (track_name, channel)
    track_channel_events: Dict[Tuple[str, int], List[NoteEvent]] = defaultdict(list)
    for event in analysis.events:
        track_channel_events[(event.track_name, event.channel)].append(event)

    classifications = []

    for (track_name, channel), events in track_channel_events.items():
        classification = _classify_track_channel(
            track_name, channel, events, analysis.song_id
        )
        classifications.append(classification)

    return classifications


def _classify_track_channel(
    track_name: str,
    channel: int,
    events: List[NoteEvent],
    song_id: str,
) -> RoleClassification:
    """Classify a single track/channel."""
    if not events:
        return RoleClassification(
            track_name=track_name,
            channel=channel,
            role="other",
            confidence=0.0,
            rationale="No events",
            event_count=0,
            pitch_range=(0, 0),
            avg_pitch=0.0,
            polyphony_score=0.0,
            density_score=0.0,
        )

    # === Feature extraction ===

    # 1. Drums: GM channel 9 (0-indexed) is always drums
    if channel == 9:
        return RoleClassification(
            track_name=track_name,
            channel=channel,
            role="drums",
            confidence=1.0,
            rationale="GM percussion channel 9",
            event_count=len(events),
            pitch_range=(_get_pitch_range(events)),
            avg_pitch=sum(e.note for e in events) / len(events),
            polyphony_score=_compute_polyphony(events),
            density_score=_compute_density(events),
        )

    # 2. Pitch statistics
    pitches = [e.note for e in events]
    pitch_range = (min(pitches), max(pitches))
    avg_pitch = sum(pitches) / len(pitches)

    # 3. Polyphony (how many notes overlap at any time)
    polyphony_score = _compute_polyphony(events)

    # 4. Density (events per beat)
    density_score = _compute_density(events)

    # 5. Sustain lengths
    avg_duration = sum(e.dur_beats for e in events) / len(events)

    # === Classification logic ===

    role = "other"
    confidence = 0.0
    rationale_parts = []

    # Bass: low pitch range, mostly monophonic, moderate density
    if avg_pitch < 55 and pitch_range[1] < 65:
        role = "bass"
        confidence = 0.9
        rationale_parts.append("low pitch range")
        if polyphony_score < 0.3:
            confidence += 0.1
            rationale_parts.append("monophonic")

    # Lead: melodic range (60–84), monophonic, moderate to high density
    elif 60 <= avg_pitch <= 84 and polyphony_score < 0.4:
        role = "lead"
        confidence = 0.7
        rationale_parts.append("melodic range, monophonic")
        if density_score < 6.0:  # not too dense
            confidence += 0.2
            rationale_parts.append("moderate density")

    # Rhythm: wide range, polyphonic (chords), short sustains
    elif polyphony_score > 0.5 and avg_duration < 0.5:
        role = "rhythm"
        confidence = 0.8
        rationale_parts.append("polyphonic, short sustains")

    # Fallback heuristics
    elif avg_pitch < 50:
        role = "bass"
        confidence = 0.5
        rationale_parts.append("very low pitch")

    elif polyphony_score > 0.6:
        role = "rhythm"
        confidence = 0.6
        rationale_parts.append("highly polyphonic")

    else:
        role = "other"
        confidence = 0.3
        rationale_parts.append(f"ambiguous (avg_pitch={avg_pitch:.0f}, poly={polyphony_score:.2f})")

    rationale = "; ".join(rationale_parts)

    return RoleClassification(
        track_name=track_name,
        channel=channel,
        role=role,
        confidence=min(1.0, confidence),
        rationale=rationale,
        event_count=len(events),
        pitch_range=pitch_range,
        avg_pitch=avg_pitch,
        polyphony_score=polyphony_score,
        density_score=density_score,
    )


def _get_pitch_range(events: List[NoteEvent]) -> Tuple[int, int]:
    """Get (min, max) pitch range."""
    pitches = [e.note for e in events]
    return (min(pitches), max(pitches))


def _compute_polyphony(events: List[NoteEvent]) -> float:
    """Compute polyphony score (0.0 = monophonic, 1.0 = highly polyphonic).

    Strategy: Sample at regular intervals and count simultaneous notes.
    """
    if not events:
        return 0.0

    # Sort events by start time
    sorted_events = sorted(events, key=lambda e: e.start_beat)

    # Sample at 0.25-beat intervals
    max_beat = max(e.start_beat + e.dur_beats for e in events)
    sample_interval = 0.25
    num_samples = int(max_beat / sample_interval) + 1

    polyphony_samples = []

    for i in range(num_samples):
        sample_beat = i * sample_interval
        # Count notes active at this beat
        active = sum(
            1 for e in sorted_events
            if e.start_beat <= sample_beat < e.start_beat + e.dur_beats
        )
        polyphony_samples.append(active)

    if not polyphony_samples:
        return 0.0

    # Average polyphony
    avg_poly = sum(polyphony_samples) / len(polyphony_samples)

    # Normalize: 1 voice = 0.0, 3+ voices = 1.0
    return min(1.0, avg_poly / 3.0)


def _compute_density(events: List[NoteEvent]) -> float:
    """Compute note density (events per beat)."""
    if not events:
        return 0.0

    total_duration = max(e.start_beat + e.dur_beats for e in events)
    if total_duration <= 0:
        return 0.0

    return len(events) / total_duration


def write_roles_json(
    song_id: str,
    classifications: List[RoleClassification],
    out_path: Path,
) -> None:
    """Write role classifications to JSON file."""
    data = {
        "song_id": song_id,
        "classifications": [asdict(c) for c in classifications],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_role_summary(
    all_classifications: Dict[str, List[RoleClassification]],
    out_path: Path,
) -> None:
    """Write aggregate role distribution summary."""
    # Aggregate by role
    role_counts: Counter = Counter()
    role_confidences: Dict[str, List[float]] = defaultdict(list)

    for song_id, classifications in all_classifications.items():
        for cls in classifications:
            role_counts[cls.role] += 1
            role_confidences[cls.role].append(cls.confidence)

    # Write TSV
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("role\tcount\tavg_confidence\n")

        for role in ["drums", "bass", "rhythm", "lead", "other"]:
            count = role_counts.get(role, 0)
            confidences = role_confidences.get(role, [])
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            f.write(f"{role}\t{count}\t{avg_conf:.3f}\n")
