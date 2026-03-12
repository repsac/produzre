"""Phase 1: MIDI Parsing and Event Extraction Module.

This module handles MIDI file parsing, tempo/time signature extraction,
and normalized event generation for analysis.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import logging

try:
    import mido
except ImportError:
    raise ImportError("mido required for MIDI parsing. Install with: pip install mido")


logger = logging.getLogger(__name__)


@dataclass
class NoteEvent:
    """A single normalized note event."""
    song_id: str
    source_file: str
    track_name: str
    channel: int
    program: int
    note: int
    velocity: int
    start_tick: int
    dur_ticks: int
    start_beat: float
    dur_beats: float
    bar: int
    beat_in_bar: float
    grid16: int  # 16th-note grid position within bar
    is_drum_guess: bool


@dataclass
class MIDIAnalysis:
    """MIDI file analysis results."""
    song_id: str
    source_file: Path
    tempo_map: List[Tuple[int, float]]  # (tick, tempo_bpm)
    time_sigs: List[Tuple[int, int, int]]  # (tick, numerator, denominator)
    ticks_per_beat: int
    events: List[NoteEvent]
    parse_error: Optional[str] = None


def parse_midi_file(
    midi_path: Path,
    song_id: str,
) -> MIDIAnalysis:
    """Parse a MIDI file and extract normalized events."""
    try:
        mid = mido.MidiFile(midi_path)
    except Exception as e:
        return MIDIAnalysis(
            song_id=song_id,
            source_file=midi_path,
            tempo_map=[],
            time_sigs=[],
            ticks_per_beat=480,
            events=[],
            parse_error=f"MIDI parse error: {e}",
        )

    ticks_per_beat = mid.ticks_per_beat
    tempo_map = []
    time_sigs = []
    events = []

    # First pass: extract tempo and time signature changes
    current_tick = 0
    for track_idx, track in enumerate(mid.tracks):
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                tempo_bpm = mido.tempo2bpm(msg.tempo)
                tempo_map.append((tick, tempo_bpm))
            elif msg.type == "time_signature":
                time_sigs.append((tick, msg.numerator, msg.denominator))

    # Default tempo/time sig if none found
    if not tempo_map:
        tempo_map.append((0, 120.0))
    if not time_sigs:
        time_sigs.append((0, 4, 4))

    # Sort tempo/time sig maps
    tempo_map.sort()
    time_sigs.sort()

    # Second pass: extract note events
    for track_idx, track in enumerate(mid.tracks):
        track_name = track.name or f"Track{track_idx}"

        # Track active notes: (channel, note) -> (start_tick, velocity)
        active_notes: Dict[Tuple[int, int], Tuple[int, int]] = {}

        # Track program changes per channel
        programs: Dict[int, int] = {}

        tick = 0
        for msg in track:
            tick += msg.time

            if msg.type == "program_change":
                programs[msg.channel] = msg.program

            elif msg.type == "note_on" and msg.velocity > 0:
                key = (msg.channel, msg.note)
                active_notes[key] = (tick, msg.velocity)

            elif msg.type in ("note_off", "note_on"):  # note_on with vel=0 is note_off
                if msg.type == "note_on" and msg.velocity > 0:
                    continue

                key = (msg.channel, msg.note)
                if key in active_notes:
                    start_tick, velocity = active_notes.pop(key)
                    dur_ticks = tick - start_tick

                    if dur_ticks > 0:
                        # Convert to beats
                        start_beat = tick_to_beat(start_tick, tempo_map, ticks_per_beat)
                        dur_beats = ticks_to_beats(dur_ticks, ticks_per_beat)

                        # Compute bar/beat position
                        bar, beat_in_bar = beat_to_bar_position(
                            start_beat, time_sigs, ticks_per_beat
                        )

                        # 16th-note grid position (0-15 in 4/4)
                        grid16 = int((beat_in_bar % 4.0) * 4.0)

                        # Guess if this is drums (channel 9/10 in GM)
                        is_drum = (msg.channel == 9)

                        # Get program number
                        program = programs.get(msg.channel, 0)

                        events.append(NoteEvent(
                            song_id=song_id,
                            source_file=str(midi_path.name),
                            track_name=track_name,
                            channel=msg.channel,
                            program=program,
                            note=msg.note,
                            velocity=velocity,
                            start_tick=start_tick,
                            dur_ticks=dur_ticks,
                            start_beat=start_beat,
                            dur_beats=dur_beats,
                            bar=bar,
                            beat_in_bar=beat_in_bar,
                            grid16=grid16,
                            is_drum_guess=is_drum,
                        ))

    # Sort events by start time
    events.sort(key=lambda e: e.start_tick)

    return MIDIAnalysis(
        song_id=song_id,
        source_file=midi_path,
        tempo_map=tempo_map,
        time_sigs=time_sigs,
        ticks_per_beat=ticks_per_beat,
        events=events,
    )


def tick_to_beat(tick: int, tempo_map: List[Tuple[int, float]], tpb: int) -> float:
    """Convert absolute tick to beat position."""
    if not tempo_map:
        return tick / tpb

    # Find applicable tempo
    tempo_bpm = tempo_map[0][1]
    for t_tick, t_tempo in tempo_map:
        if tick >= t_tick:
            tempo_bpm = t_tempo
        else:
            break

    # Simple conversion (doesn't account for tempo changes mid-section)
    return tick / tpb


def ticks_to_beats(ticks: int, tpb: int) -> float:
    """Convert tick duration to beat duration."""
    return ticks / tpb


def beat_to_bar_position(
    beat: float,
    time_sigs: List[Tuple[int, int, int]],
    tpb: int,
) -> Tuple[int, float]:
    """Convert beat position to (bar_number, beat_in_bar)."""
    if not time_sigs:
        # Default 4/4
        bar = int(beat // 4.0)
        beat_in_bar = beat % 4.0
        return bar, beat_in_bar

    # Use first time signature (simplified — doesn't handle mid-song changes)
    _, numerator, _ = time_sigs[0]
    beats_per_bar = float(numerator)

    bar = int(beat // beats_per_bar)
    beat_in_bar = beat % beats_per_bar

    return bar, beat_in_bar


def write_events_tsv(events: List[NoteEvent], out_path: Path) -> None:
    """Write events to TSV file."""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("song_id\tsource_file\ttrack_name\tchannel\tprogram\tnote\tvelocity\t"
                "start_beat\tdur_beats\tbar\tbeat_in_bar\tgrid16\tis_drum_guess\n")

        for e in events:
            f.write(
                f"{e.song_id}\t{e.source_file}\t{e.track_name}\t{e.channel}\t{e.program}\t"
                f"{e.note}\t{e.velocity}\t{e.start_beat:.3f}\t{e.dur_beats:.3f}\t"
                f"{e.bar}\t{e.beat_in_bar:.3f}\t{e.grid16}\t{e.is_drum_guess}\n"
            )
