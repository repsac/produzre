from __future__ import annotations

"""MIDI writing utilities used by the export subsystem.

This module provides small helpers for converting Produzre's internal beat-based
representation (quarter-note beats) into MIDI files using `mido`.

Key conventions:
- Internal time is expressed in *beats* (quarter notes), regardless of meter.
- Exports use a consistent PPQ (pulses per quarter note) to map beats to MIDI
  ticks.
- Timeline-to-track writing emits note_on/note_off pairs ordered by absolute tick
  time and then converts to delta-time messages (as required by the MIDI spec).

The functions here are intentionally low-level and side-effect free except for
mutating `mido.MidiTrack` objects.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import mido


# Standard pulses-per-quarter-note used throughout Produzre exports.
PPQ: int = 480


def beats_to_ticks(beats: float, *, ppq: int = PPQ) -> int:
    """Convert quarter-note beats to MIDI ticks.

    Produzre's internal timing unit is the quarter-note beat. MIDI uses integer
    ticks whose resolution is defined by PPQ (pulses per quarter note).

    Args:
        beats: Beat position/duration in quarter-note beats.
        ppq: Pulses per quarter note (tick resolution). Defaults to `PPQ`.

    Returns:
        int: Tick count corresponding to the provided beat value.
    """
    return int(round(float(beats) * ppq))


def parse_meter(meter: Optional[str]) -> tuple[int, int]:
    """Parse a meter string like "6/8" into (numerator, denominator).

    Falls back to (4, 4) when the string is missing or malformed so callers
    can always emit a valid time_signature meta event.

    Args:
        meter: Meter string in "N/D" form (e.g., "4/4", "6/8", "7/8").

    Returns:
        tuple[int, int]: (numerator, denominator).
    """
    try:
        num_s, den_s = str(meter).strip().split("/", 1)
        num = int(num_s)
        den = int(den_s)
        if num > 0 and den > 0:
            return num, den
    except Exception:
        pass
    return 4, 4


def add_time_signature(track: mido.MidiTrack, meter: Optional[str]) -> None:
    """Write a time_signature meta event at time 0.

    Args:
        track: Target MIDI track to mutate.
        meter: Meter string in "N/D" form. Defaults to 4/4 when unparseable.

    Returns:
        None
    """
    num, den = parse_meter(meter)
    track.append(
        mido.MetaMessage("time_signature", numerator=num, denominator=den, time=0)
    )


def add_tempo_and_name(
    track: mido.MidiTrack,
    bpm: float,
    name: str,
    *,
    meter: Optional[str] = None,
) -> None:
    """Write common meta events (track name + tempo [+ time signature]) at time 0.

    Args:
        track: Target MIDI track to mutate.
        bpm: Tempo in beats per minute.
        name: Human-readable track name.
        meter: Optional meter string ("N/D"). When provided, a time_signature
            meta event is also emitted at time 0.

    Returns:
        None
    """
    track.append(mido.MetaMessage("track_name", name=str(name), time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(float(bpm)), time=0))
    if meter is not None:
        add_time_signature(track, meter)


def program_for_instrument(cfg: Any, instrument_name: str) -> Optional[int]:
    """Return the MIDI program number for an instrument, if configured.

    Produzre stores per-instrument defaults in the engine registry
    (`cfg.engines`). Each engine may define a `program` value (General MIDI
    program number) used by DAWs/players to select an appropriate patch.

    This helper is intentionally defensive:
      - If `cfg.engines` is missing or not a mapping, returns None.
      - If the engine is missing, returns None.
      - If `engine.program` is missing/None or cannot be coerced to int,
        returns None.

    Args:
        cfg: A configuration-like object expected to have an `engines` mapping.
        instrument_name: Engine/instrument key to look up.

    Returns:
        Optional[int]: Program number (0-127) if available, otherwise None.
    """
    try:
        engine = cfg.engines.get(instrument_name)  # type: ignore[attr-defined]
    except Exception:
        engine = None

    if engine is None:
        return None

    prog = getattr(engine, "program", None)
    if prog is None:
        return None

    try:
        return int(prog)
    except Exception:
        return None


@dataclass(frozen=True)
class _MidiMsg:
    tick: int
    order: int
    msg: mido.Message


def write_timeline_to_track(track: mido.MidiTrack, timeline: Any, *, ppq: int = PPQ) -> None:
    """Write note events from a timeline into a MIDI track.

    The `timeline` object is expected to expose an iterable attribute `events`.
    Each event must provide (as attributes):
      - start_beat (float): start time in quarter-note beats
      - duration_beats (float): duration in quarter-note beats
      - pitch (int): MIDI note number (0-127)
      - velocity (int): MIDI velocity (0-127)
      - channel (int): MIDI channel (0-15)

    Emission rules:
      - For each event, emit a note_on at `start_beat` and a note_off at
        `start_beat + duration_beats`.
      - Messages are gathered with absolute tick times, then sorted, and finally
        converted to delta times before being appended to `track`.
      - When note_on and note_off share the same tick, note_off is ordered first
        to reduce the chance of overlaps causing stuck notes in some DAWs.

    Args:
        track: Target MIDI track to mutate.
        timeline: Timeline-like object containing note events.
        ppq: Pulses per quarter note (tick resolution). Defaults to `PPQ`.

    Returns:
        None
    """
    events: Iterable[Any] = getattr(timeline, "events", [])

    # First pass: collect note intervals in tick space.
    # notes: (start_tick, end_tick, pitch, vel, ch)
    notes: list[tuple[int, int, int, int, int]] = []

    for ev in events:
        try:
            start = float(ev.start_beat)
            dur = float(ev.duration_beats)
            pitch = int(ev.pitch)
            vel = int(ev.velocity)
            ch = int(ev.channel)
        except Exception:
            continue

        if dur <= 0:
            continue

        start_tick = beats_to_ticks(start, ppq=ppq)
        end_tick = beats_to_ticks(start + dur, ppq=ppq)
        # Sub-tick durations would otherwise emit note_off at (or before) the
        # note_on tick, which sorts the note_off first and leaves the note_on
        # stuck. Guarantee at least 1 tick of audible length.
        if end_tick <= start_tick:
            end_tick = start_tick + 1

        pitch = max(0, min(127, pitch))
        vel = max(0, min(127, vel))
        ch = max(0, min(15, ch))

        notes.append((start_tick, end_tick, pitch, vel, ch))

    # Second pass: de-overlap same-pitch/same-channel notes so note_offs never
    # cross (a later note_off cutting an earlier note, or vice versa).
    # Rules:
    #   - Notes starting at the same tick on the same (channel, pitch): keep
    #     only the longest (velocity as deterministic tie-break).
    #   - An earlier note overlapping a later note's start is truncated to the
    #     later note's start tick.
    by_key: dict[tuple[int, int], list[tuple[int, int, int, int, int]]] = {}
    for n in notes:
        by_key.setdefault((n[4], n[2]), []).append(n)

    deduped: list[tuple[int, int, int, int, int]] = []
    for _key, group in by_key.items():
        group.sort(key=lambda n: (n[0], -(n[1] - n[0]), -n[3]))
        # Drop duplicates that share a start tick (keep first = longest/loudest).
        unique: list[tuple[int, int, int, int, int]] = []
        last_start: Optional[int] = None
        for n in group:
            if last_start is not None and n[0] == last_start:
                continue
            unique.append(n)
            last_start = n[0]
        # Truncate overlaps against the next note's start.
        for i, n in enumerate(unique):
            start_tick, end_tick, pitch, vel, ch = n
            if i + 1 < len(unique):
                next_start = unique[i + 1][0]
                if end_tick > next_start:
                    end_tick = max(next_start, start_tick + 1)
            deduped.append((start_tick, end_tick, pitch, vel, ch))

    msgs: list[_MidiMsg] = []
    for start_tick, end_tick, pitch, vel, ch in deduped:
        # Order: note_off first at the same tick to avoid overlaps/stuck notes.
        msgs.append(_MidiMsg(start_tick, 1, mido.Message("note_on", note=pitch, velocity=vel, channel=ch, time=0)))
        msgs.append(_MidiMsg(end_tick, 0, mido.Message("note_off", note=pitch, velocity=0, channel=ch, time=0)))

    msgs.sort(key=lambda m: (m.tick, m.order, m.msg.type, m.msg.channel, m.msg.note))

    last_tick = 0
    for m in msgs:
        dt = m.tick - last_tick
        if dt < 0:
            dt = 0
        m.msg.time = int(dt)
        track.append(m.msg)
        last_tick = m.tick
