from __future__ import annotations

"""Beat-based event timeline primitives.

Produzre represents musical time internally in quarter-note beats measured from
song start. Instrument engines render note events into `InstrumentTimeline`
objects, which are later exported to MIDI by converting beats to ticks using a
fixed PPQ.

This module defines:
- `NoteEvent`: a minimal note representation (start/duration/pitch/velocity/channel)
- `SectionTiming`: song-relative section windows (start/end beats + beats-per-bar)
- `InstrumentTimeline`: an append-only collection of note events for one instrument

The structures here are intentionally lightweight and serialization-friendly.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NoteEvent:
    """A single MIDI-like note event expressed in beat space.

    Attributes:
        start_beat: Song-relative start time in quarter-note beats.
        duration_beats: Note duration in quarter-note beats.
        pitch: MIDI note number (0-127).
        velocity: MIDI velocity (0-127).
        channel: MIDI channel (0-15). Defaults to 9 (GM channel 10, 0-based)
            which is the conventional drums channel.
        kind: Optional metadata tag for debugging and analysis. For example:
            - Drums: "kick", "snare", "ghost", "fill", "crash_transition"
            - Bass: "root", "fifth", "passing"
            Used for determinism debugging and TSV analysis exports.

    Notes:
        Produzre keeps events in beat units until export. MIDI export converts
        beats to ticks based on PPQ and emits note_on/note_off messages.
    """
    start_beat: float
    duration_beats: float
    pitch: int
    velocity: int
    channel: int = 9  # default to GM drums channel 10 (0-based index)
    kind: Optional[str] = None  # Optional metadata for debugging/analysis


@dataclass
class SectionTiming:
    """Timing information for a single section in song-beat space.

    A `SectionTiming` describes a half-open time window `[start_beat, end_beat)`
    in *song-global* beat coordinates.

    Attributes:
        id: Section identifier (e.g., "verse1").
        type: Section type label (e.g., "verse", "chorus").
        start_beat: Song-relative start time in beats.
        end_beat: Song-relative end time in beats (exclusive).
        beats_per_bar: Beats-per-bar for this section expressed in quarter-note
            beats. This is used for bar-based reporting and for pattern window
            sizing in mixed-meter songs.

    Notes:
        `beats_per_bar` is intentionally stored per section to support mixed
        meters. For example, 6/8 would typically be 3.0 quarter-note beats per
        bar.
    """
    id: str
    type: str
    start_beat: float
    end_beat: float
    beats_per_bar: float

    @property
    def length_beats(self) -> float:
        """Return the section length in beats."""
        return self.end_beat - self.start_beat


@dataclass
class InstrumentTimeline:
    """Collected note events for a single instrument across the whole song.

    The timeline is populated by instrument engines during rendering.

    Attributes:
        instrument: Instrument key (e.g., "drums", "bass").
        events: List of `NoteEvent` entries in song-relative beat time.
        default_channel: Optional MIDI channel sourced from the engine spec
            (`engines.yml` `channel:`). When set, it takes precedence over the
            built-in instrument-name map for events added without an explicit
            channel.

    Notes:
        Events may be appended in any order. Call `sort_events()` after
        rendering to ensure deterministic ordering for export.
    """
    instrument: str
    events: List[NoteEvent] = field(default_factory=list)
    default_channel: Optional[int] = None

    def add_note(
        self,
        start_beat: float,
        duration_beats: float,
        pitch: int,
        velocity: int,
        channel: Optional[int] = None,
        kind: Optional[str] = None,
    ) -> None:
        """Append a note event to the timeline.

        If `channel` is not provided, a per-instrument default channel is
        selected via `_resolve_channel()`.

        Args:
            start_beat: Song-relative start time in beats.
            duration_beats: Duration in beats.
            pitch: MIDI note number (0-127).
            velocity: MIDI velocity (0-127).
            channel: Optional MIDI channel (0-15). If None, an instrument
                default channel is used.
            kind: Optional metadata tag for debugging/analysis (e.g., "kick", "ghost").

        Returns:
            None
        """
        ch = self._resolve_channel(channel)
        self.events.append(
            NoteEvent(
                start_beat=start_beat,
                duration_beats=duration_beats,
                pitch=pitch,
                velocity=velocity,
                channel=ch,
                kind=kind,
            )
        )

    def _resolve_channel(self, channel: Optional[int]) -> int:
        """Resolve the MIDI channel for a note event.

        If an explicit channel is provided, it is returned unchanged.
        Otherwise, a simple per-instrument mapping is used so exported tracks
        can be distinguished by DAWs and program_change messages can target the
        correct channel.

        Notes:
            Channel numbers are 0-based in `mido`/MIDI messages (0-15). The GM
            drums channel is conventionally channel 10, which is 9 in 0-based
            numbering.

        Args:
            channel: Optional explicit channel.

        Returns:
            int: Resolved MIDI channel.
        """
        if channel is not None:
            return channel

        # Prefer the engine-spec channel (engines.yml `channel:`), plumbed in
        # by the orchestrator when the timeline is created.
        if self.default_channel is not None:
            return int(self.default_channel)

        # Assign distinct channels per instrument so GM program changes and
        # DAWs can distinguish parts more easily.

        # Known instruments → MIDI channels (channel 9 = GM drums).
        # Unmapped instruments default to channel 0 (piano).
        mapping = {
            "drums": 9,
            "bass": 1,
            "rhythm_gtr": 2,
            "rhythm": 2,
            "acoustic_gtr": 3,
            "lead_gtr": 4,
            "lead": 4,
            "harmony": 5,
            "arpeggiator": 6,
        }

        return mapping.get(self.instrument, 0)


    def sort_events(self) -> None:
        """Sort events in place for deterministic export.

        Events are ordered by (start_beat, pitch). Engines may emit events out of
        order during rendering; sorting helps ensure deterministic MIDI output
        and improves human readability when debugging.

        Returns:
            None
        """
        self.events.sort(key=lambda ev: (ev.start_beat, ev.pitch))

    def get_events_in_range(
        self,
        beat_start: float,
        beat_end: float,
    ) -> List[NoteEvent]:
        """Get all events that start within a beat range.

        Returns events where start_beat is in [beat_start, beat_end).

        Args:
            beat_start: Start of beat range (inclusive).
            beat_end: End of beat range (exclusive).

        Returns:
            List[NoteEvent]: Events starting in the specified range.
        """
        return [
            ev for ev in self.events
            if beat_start <= ev.start_beat < beat_end
        ]
