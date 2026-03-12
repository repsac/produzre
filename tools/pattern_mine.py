"""Phase 4: Pattern Mining Module.

Extracts reusable style features for each instrument role without copying
exact patterns. Analyzes:
- Drums: kick/snare/hat densities, fills placement, typical accents
- Bass: root motion, approach notes, syncopation, typical bar shapes
- Rhythm guitar: chord hit placements, strum density, palm-mute vs open
- Lead guitar: phrase lengths, contour, chord-tone bias, rest density
"""

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from statistics import mean, stdev, median

from midi_parse import MIDIAnalysis, NoteEvent
from role_classify import RoleClassification


logger = logging.getLogger(__name__)


@dataclass
class DrumProfile:
    """Drum pattern style profile."""
    song_id: str

    # Density metrics (events per bar)
    kick_density: float
    snare_density: float
    hat_density: float
    crash_density: float

    # Timing features
    kick_on_beat_ratio: float  # % of kicks on strong beats
    snare_backbeat_ratio: float  # % on beats 2 and 4
    hat_offbeat_ratio: float  # % on eighth/sixteenth offbeats

    # Complexity
    polyphony_avg: float  # avg simultaneous drum hits
    fill_density: float  # fills per 8 bars estimate

    # Velocity dynamics
    accent_ratio: float  # % of hits above 80% max velocity
    ghost_ratio: float  # % of hits below 40% max velocity


@dataclass
class BassProfile:
    """Bass pattern style profile."""
    song_id: str

    # Density and rhythm
    notes_per_bar: float
    rest_ratio: float  # proportion of beats with no notes

    # Pitch movement
    root_note_ratio: float  # % of notes on likely root (lowest common pitch)
    step_motion_ratio: float  # % of intervals <= 2 semitones
    leap_avg: float  # average interval size

    # Timing
    on_beat_ratio: float  # % starting on beat 1, 2, 3, 4
    syncopation: float  # % on offbeats

    # Articulation (inferred)
    staccato_ratio: float  # % of notes < 0.3 beats duration
    sustain_avg: float  # average note duration in beats


@dataclass
class RhythmGuitarProfile:
    """Rhythm guitar pattern style profile."""
    song_id: str

    # Strum density
    chords_per_bar: float
    strum_density: float  # simultaneous notes per chord hit

    # Timing placement
    downbeat_ratio: float  # % on beats 1, 3
    upbeat_ratio: float  # % on offbeats
    sustained_ratio: float  # % of long chords (> 1 beat)

    # Voicing
    avg_chord_notes: float  # polyphony
    pitch_spread: float  # avg range of simultaneous notes (semitones)

    # Articulation
    palm_mute_guess: float  # ratio of short, low-vel chords
    accent_variation: float  # stdev of velocities


@dataclass
class LeadGuitarProfile:
    """Lead guitar pattern style profile."""
    song_id: str

    # Phrase structure
    notes_per_bar: float
    rest_ratio: float
    phrase_length_avg: float  # avg continuous notes before rest

    # Melodic contour
    step_motion_ratio: float  # % of intervals <= 2 semitones
    leap_ratio: float  # % of intervals > 5 semitones
    range_semitones: int  # total pitch range

    # Chord-tone tendency (placeholder - requires harmony analysis)
    repetition_ratio: float  # % of repeated pitches

    # Timing
    on_beat_ratio: float
    syncopation: float

    # Articulation
    sustain_avg: float  # average note duration
    bend_slide_guess: float  # ratio of very short grace-note-like events


def mine_drum_patterns(
    events: List[NoteEvent],
    song_id: str,
) -> DrumProfile:
    """Extract drum pattern style profile."""
    if not events:
        return _empty_drum_profile(song_id)

    # Separate by approximate drum voice (using MIDI note numbers)
    kicks = [e for e in events if 35 <= e.note <= 36]  # kick drums
    snares = [e for e in events if 38 <= e.note <= 40]  # snares
    hats = [e for e in events if 42 <= e.note <= 46]  # hi-hats
    crashes = [e for e in events if 49 <= e.note <= 57 or e.note == 52]  # crashes/rides

    # Compute bar span
    if not events:
        bars = 1.0
    else:
        max_bar = max(e.bar for e in events)
        bars = max(1.0, float(max_bar + 1))

    # Densities
    kick_density = len(kicks) / bars
    snare_density = len(snares) / bars
    hat_density = len(hats) / bars
    crash_density = len(crashes) / bars

    # Kick on-beat ratio (beat 0, 1, 2, 3)
    kick_on_beat = sum(
        1 for e in kicks
        if abs(e.beat_in_bar - round(e.beat_in_bar)) < 0.1
    ) if kicks else 0
    kick_on_beat_ratio = kick_on_beat / len(kicks) if kicks else 0.0

    # Snare backbeat (beats 1, 3 in 4/4)
    snare_backbeat = sum(
        1 for e in snares
        if abs(e.beat_in_bar - 1.0) < 0.1 or abs(e.beat_in_bar - 3.0) < 0.1
    ) if snares else 0
    snare_backbeat_ratio = snare_backbeat / len(snares) if snares else 0.0

    # Hat offbeat ratio (not on integer beats)
    hat_offbeat = sum(
        1 for e in hats
        if abs(e.beat_in_bar - round(e.beat_in_bar)) > 0.1
    ) if hats else 0
    hat_offbeat_ratio = hat_offbeat / len(hats) if hats else 0.0

    # Polyphony (sample at 16th-note intervals)
    polyphony_samples = _sample_polyphony(events, bars, 0.25)
    polyphony_avg = mean(polyphony_samples) if polyphony_samples else 1.0

    # Fill density (estimate from crashes + high tom/cymbal density in last beat of bars)
    fill_events = sum(
        1 for e in events
        if e.beat_in_bar >= 3.0 and (e.note >= 47 or e.velocity > 100)
    )
    fill_density = fill_events / max(1.0, bars / 8.0)  # fills per 8 bars

    # Velocity dynamics
    velocities = [e.velocity for e in events]
    if velocities:
        max_vel = max(velocities)
        accent_count = sum(1 for v in velocities if v > max_vel * 0.8)
        ghost_count = sum(1 for v in velocities if v < max_vel * 0.4)
        accent_ratio = accent_count / len(velocities)
        ghost_ratio = ghost_count / len(velocities)
    else:
        accent_ratio = 0.0
        ghost_ratio = 0.0

    return DrumProfile(
        song_id=song_id,
        kick_density=kick_density,
        snare_density=snare_density,
        hat_density=hat_density,
        crash_density=crash_density,
        kick_on_beat_ratio=kick_on_beat_ratio,
        snare_backbeat_ratio=snare_backbeat_ratio,
        hat_offbeat_ratio=hat_offbeat_ratio,
        polyphony_avg=polyphony_avg,
        fill_density=fill_density,
        accent_ratio=accent_ratio,
        ghost_ratio=ghost_ratio,
    )


def mine_bass_patterns(
    events: List[NoteEvent],
    song_id: str,
) -> BassProfile:
    """Extract bass pattern style profile."""
    if not events:
        return _empty_bass_profile(song_id)

    # Bar count
    max_bar = max(e.bar for e in events)
    bars = max(1.0, float(max_bar + 1))

    # Density
    notes_per_bar = len(events) / bars

    # Rest ratio (beats with no note starts)
    beats_with_notes = set()
    for e in events:
        beat_position = int(e.bar * 4.0 + e.beat_in_bar)
        beats_with_notes.add(beat_position)
    total_beats = bars * 4.0
    rest_ratio = 1.0 - (len(beats_with_notes) / total_beats) if total_beats > 0 else 0.0

    # Root note ratio (most common pitch)
    pitches = [e.note for e in events]
    pitch_counts = Counter(pitches)
    most_common_pitch, most_common_count = pitch_counts.most_common(1)[0]
    root_note_ratio = most_common_count / len(events)

    # Interval analysis
    sorted_events = sorted(events, key=lambda e: e.start_beat)
    intervals = []
    for i in range(len(sorted_events) - 1):
        interval = abs(sorted_events[i + 1].note - sorted_events[i].note)
        intervals.append(interval)

    if intervals:
        step_motion = sum(1 for i in intervals if i <= 2)
        step_motion_ratio = step_motion / len(intervals)
        leap_avg = mean(intervals)
    else:
        step_motion_ratio = 0.0
        leap_avg = 0.0

    # On-beat ratio
    on_beat_count = sum(
        1 for e in events
        if abs(e.beat_in_bar - round(e.beat_in_bar)) < 0.1
    )
    on_beat_ratio = on_beat_count / len(events)

    # Syncopation (offbeat starts)
    syncopation = 1.0 - on_beat_ratio

    # Articulation
    durations = [e.dur_beats for e in events]
    staccato_count = sum(1 for d in durations if d < 0.3)
    staccato_ratio = staccato_count / len(durations)
    sustain_avg = mean(durations)

    return BassProfile(
        song_id=song_id,
        notes_per_bar=notes_per_bar,
        rest_ratio=rest_ratio,
        root_note_ratio=root_note_ratio,
        step_motion_ratio=step_motion_ratio,
        leap_avg=leap_avg,
        on_beat_ratio=on_beat_ratio,
        syncopation=syncopation,
        staccato_ratio=staccato_ratio,
        sustain_avg=sustain_avg,
    )


def mine_rhythm_guitar_patterns(
    events: List[NoteEvent],
    song_id: str,
) -> RhythmGuitarProfile:
    """Extract rhythm guitar pattern style profile."""
    if not events:
        return _empty_rhythm_profile(song_id)

    # Bar count
    max_bar = max(e.bar for e in events)
    bars = max(1.0, float(max_bar + 1))

    # Group simultaneous notes (chords)
    chord_groups = _group_simultaneous_notes(events, tolerance=0.05)
    chords_per_bar = len(chord_groups) / bars

    # Strum density (avg polyphony per chord)
    if chord_groups:
        strum_density = mean(len(cg) for cg in chord_groups)
        avg_chord_notes = strum_density
    else:
        strum_density = 1.0
        avg_chord_notes = 1.0

    # Timing placement
    downbeat_count = sum(
        1 for cg in chord_groups
        if any(abs(e.beat_in_bar - 0.0) < 0.1 or abs(e.beat_in_bar - 2.0) < 0.1 for e in cg)
    )
    upbeat_count = sum(
        1 for cg in chord_groups
        if any(abs(e.beat_in_bar - round(e.beat_in_bar)) > 0.1 for e in cg)
    )
    downbeat_ratio = downbeat_count / len(chord_groups) if chord_groups else 0.0
    upbeat_ratio = upbeat_count / len(chord_groups) if chord_groups else 0.0

    # Sustained chords
    sustained_count = sum(
        1 for cg in chord_groups
        if any(e.dur_beats > 1.0 for e in cg)
    )
    sustained_ratio = sustained_count / len(chord_groups) if chord_groups else 0.0

    # Pitch spread
    pitch_spreads = []
    for cg in chord_groups:
        pitches = [e.note for e in cg]
        if len(pitches) > 1:
            spread = max(pitches) - min(pitches)
            pitch_spreads.append(spread)
    pitch_spread = mean(pitch_spreads) if pitch_spreads else 0.0

    # Palm mute guess (short + low velocity)
    palm_mute_count = sum(
        1 for cg in chord_groups
        if any(e.dur_beats < 0.25 and e.velocity < 70 for e in cg)
    )
    palm_mute_guess = palm_mute_count / len(chord_groups) if chord_groups else 0.0

    # Accent variation
    velocities = [e.velocity for e in events]
    accent_variation = stdev(velocities) if len(velocities) > 1 else 0.0

    return RhythmGuitarProfile(
        song_id=song_id,
        chords_per_bar=chords_per_bar,
        strum_density=strum_density,
        downbeat_ratio=downbeat_ratio,
        upbeat_ratio=upbeat_ratio,
        sustained_ratio=sustained_ratio,
        avg_chord_notes=avg_chord_notes,
        pitch_spread=pitch_spread,
        palm_mute_guess=palm_mute_guess,
        accent_variation=accent_variation,
    )


def mine_lead_guitar_patterns(
    events: List[NoteEvent],
    song_id: str,
) -> LeadGuitarProfile:
    """Extract lead guitar pattern style profile."""
    if not events:
        return _empty_lead_profile(song_id)

    # Bar count
    max_bar = max(e.bar for e in events)
    bars = max(1.0, float(max_bar + 1))

    # Density
    notes_per_bar = len(events) / bars

    # Rest ratio (gaps > 0.5 beats between notes)
    sorted_events = sorted(events, key=lambda e: e.start_beat)
    gaps = []
    for i in range(len(sorted_events) - 1):
        gap = sorted_events[i + 1].start_beat - (sorted_events[i].start_beat + sorted_events[i].dur_beats)
        gaps.append(gap)

    rest_count = sum(1 for g in gaps if g > 0.5)
    rest_ratio = rest_count / len(gaps) if gaps else 0.0

    # Phrase length (avg notes between rests)
    phrase_lengths = []
    current_phrase_len = 1
    for gap in gaps:
        if gap > 0.5:
            phrase_lengths.append(current_phrase_len)
            current_phrase_len = 1
        else:
            current_phrase_len += 1
    if current_phrase_len > 1:
        phrase_lengths.append(current_phrase_len)
    phrase_length_avg = mean(phrase_lengths) if phrase_lengths else 1.0

    # Interval analysis
    intervals = []
    for i in range(len(sorted_events) - 1):
        interval = abs(sorted_events[i + 1].note - sorted_events[i].note)
        intervals.append(interval)

    if intervals:
        step_motion = sum(1 for i in intervals if i <= 2)
        step_motion_ratio = step_motion / len(intervals)
        leap_count = sum(1 for i in intervals if i > 5)
        leap_ratio = leap_count / len(intervals)
    else:
        step_motion_ratio = 0.0
        leap_ratio = 0.0

    # Range
    pitches = [e.note for e in events]
    range_semitones = max(pitches) - min(pitches) if pitches else 0

    # Repetition
    repeated_count = sum(1 for i in intervals if i == 0)
    repetition_ratio = repeated_count / len(intervals) if intervals else 0.0

    # Timing
    on_beat_count = sum(
        1 for e in events
        if abs(e.beat_in_bar - round(e.beat_in_bar)) < 0.1
    )
    on_beat_ratio = on_beat_count / len(events)
    syncopation = 1.0 - on_beat_ratio

    # Articulation
    durations = [e.dur_beats for e in events]
    sustain_avg = mean(durations)

    # Grace notes / bends (very short notes < 0.1 beats)
    grace_count = sum(1 for d in durations if d < 0.1)
    bend_slide_guess = grace_count / len(durations)

    return LeadGuitarProfile(
        song_id=song_id,
        notes_per_bar=notes_per_bar,
        rest_ratio=rest_ratio,
        phrase_length_avg=phrase_length_avg,
        step_motion_ratio=step_motion_ratio,
        leap_ratio=leap_ratio,
        range_semitones=range_semitones,
        repetition_ratio=repetition_ratio,
        on_beat_ratio=on_beat_ratio,
        syncopation=syncopation,
        sustain_avg=sustain_avg,
        bend_slide_guess=bend_slide_guess,
    )


def _sample_polyphony(events: List[NoteEvent], bars: float, interval: float) -> List[int]:
    """Sample polyphony at regular intervals."""
    if not events:
        return []

    max_beat = bars * 4.0
    samples = []

    beat = 0.0
    while beat < max_beat:
        active = sum(
            1 for e in events
            if e.start_beat <= beat < e.start_beat + e.dur_beats
        )
        samples.append(active)
        beat += interval

    return samples


def _group_simultaneous_notes(
    events: List[NoteEvent],
    tolerance: float = 0.05,
) -> List[List[NoteEvent]]:
    """Group notes that start at approximately the same time."""
    if not events:
        return []

    sorted_events = sorted(events, key=lambda e: e.start_beat)
    groups = []
    current_group = [sorted_events[0]]

    for i in range(1, len(sorted_events)):
        if abs(sorted_events[i].start_beat - current_group[0].start_beat) < tolerance:
            current_group.append(sorted_events[i])
        else:
            groups.append(current_group)
            current_group = [sorted_events[i]]

    if current_group:
        groups.append(current_group)

    return groups


def _empty_drum_profile(song_id: str) -> DrumProfile:
    return DrumProfile(
        song_id=song_id,
        kick_density=0.0,
        snare_density=0.0,
        hat_density=0.0,
        crash_density=0.0,
        kick_on_beat_ratio=0.0,
        snare_backbeat_ratio=0.0,
        hat_offbeat_ratio=0.0,
        polyphony_avg=0.0,
        fill_density=0.0,
        accent_ratio=0.0,
        ghost_ratio=0.0,
    )


def _empty_bass_profile(song_id: str) -> BassProfile:
    return BassProfile(
        song_id=song_id,
        notes_per_bar=0.0,
        rest_ratio=0.0,
        root_note_ratio=0.0,
        step_motion_ratio=0.0,
        leap_avg=0.0,
        on_beat_ratio=0.0,
        syncopation=0.0,
        staccato_ratio=0.0,
        sustain_avg=0.0,
    )


def _empty_rhythm_profile(song_id: str) -> RhythmGuitarProfile:
    return RhythmGuitarProfile(
        song_id=song_id,
        chords_per_bar=0.0,
        strum_density=0.0,
        downbeat_ratio=0.0,
        upbeat_ratio=0.0,
        sustained_ratio=0.0,
        avg_chord_notes=0.0,
        pitch_spread=0.0,
        palm_mute_guess=0.0,
        accent_variation=0.0,
    )


def _empty_lead_profile(song_id: str) -> LeadGuitarProfile:
    return LeadGuitarProfile(
        song_id=song_id,
        notes_per_bar=0.0,
        rest_ratio=0.0,
        phrase_length_avg=0.0,
        step_motion_ratio=0.0,
        leap_ratio=0.0,
        range_semitones=0,
        repetition_ratio=0.0,
        on_beat_ratio=0.0,
        syncopation=0.0,
        sustain_avg=0.0,
        bend_slide_guess=0.0,
    )


def extract_patterns(
    analysis: MIDIAnalysis,
    classifications: List[RoleClassification],
) -> Dict[str, any]:
    """Extract pattern profiles for all instrument roles in a track.

    Returns dict with keys: 'drums', 'bass', 'rhythm', 'lead' (if present).
    """
    profiles = {}

    # Group events by role
    role_events = defaultdict(list)
    for cls in classifications:
        role_events[cls.role].extend([
            e for e in analysis.events
            if e.track_name == cls.track_name and e.channel == cls.channel
        ])

    # Extract profiles
    if 'drums' in role_events and role_events['drums']:
        profiles['drums'] = mine_drum_patterns(role_events['drums'], analysis.song_id)

    if 'bass' in role_events and role_events['bass']:
        profiles['bass'] = mine_bass_patterns(role_events['bass'], analysis.song_id)

    if 'rhythm' in role_events and role_events['rhythm']:
        profiles['rhythm'] = mine_rhythm_guitar_patterns(role_events['rhythm'], analysis.song_id)

    if 'lead' in role_events and role_events['lead']:
        profiles['lead'] = mine_lead_guitar_patterns(role_events['lead'], analysis.song_id)

    return profiles


def write_profiles_json(
    song_id: str,
    profiles: Dict[str, any],
    out_dir: Path,
) -> None:
    """Write instrument profiles to separate JSON files."""
    for role, profile in profiles.items():
        out_path = out_dir / f"{song_id}.{role}.json"
        data = {
            "song_id": song_id,
            "role": role,
            "profile": asdict(profile),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
