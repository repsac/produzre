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

import math

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


def add_channel_setup(
    track: mido.MidiTrack,
    cfg: Any,
    instrument_name: str,
    channel: int,
) -> None:
    """Write patch-selection messages at time 0 for a track's channel.

    Melodic instruments get a `program_change` when their engine configures a
    GM program. The GM percussion channel (9, 0-based) always gets an explicit
    `program_change` 0 (Standard Kit): GM playback ignores it, but DAWs that
    don't assume "channel 10 = drums" on import (e.g. FL Studio) otherwise
    default the track to a melodic patch like Acoustic Piano.

    Args:
        track: Target MIDI track to mutate.
        cfg: Configuration-like object with an `engines` mapping.
        instrument_name: Engine/instrument key (used for program lookup).
        channel: MIDI channel the track's notes live on.

    Returns:
        None
    """
    ch = max(0, min(15, int(channel)))
    if ch == 9:
        track.append(mido.Message("program_change", program=0, channel=ch, time=0))
        return
    prog = program_for_instrument(cfg, instrument_name)
    if prog is None:
        return
    track.append(
        mido.Message("program_change", program=int(prog), channel=ch, time=0)
    )


@dataclass(frozen=True)
class _MidiMsg:
    tick: int
    order: int
    msg: mido.Message


def _expression_msgs(
    start_tick: int,
    end_tick: int,
    ch: int,
    expression: Any,
    *,
    ppq: int = PPQ,
) -> list[_MidiMsg]:
    """Render a note's pitch-expression spec into pitchwheel messages.

    The spec is precomputed in beat space by the engine (see
    `NoteEvent.expression`), so this helper only needs tick coordinates.
    Supported keys:
      - "bend_in": {"semitones": float, "ramp_beats": float} — start bent
        down by N semitones and ramp linearly back to center.
      - "vibrato": {"depth_cents": float, "period_beats": float,
        "delay_beats": float} — sine-shaped wheel wobble after a delay.
      - "dive": {"semitones": int, "drop_beats": float} — whammy-bar dive:
        ramps the wheel to full down over drop_beats and holds it until the
        note ends. The channel's bend range is temporarily widened via RPN 0/0
        (pitch bend sensitivity) so dives can exceed the GM +/-2 default.
      - "swell": {"from": int, "ramp_beats": float, "to": int} — feedback /
        volume-pedal swell: channel expression (CC11) ramps from -> to over
        ramp_beats, quieting the attack. Restored to 127 at note end if the
        swell ends below full.

    Assumes the GM default pitch-bend range of +/-2 semitones (except during a
    dive, which sets and restores its own range). The wheel is always returned
    to center at the note's end tick so the next note on the channel starts
    clean.
    """
    out: list[_MidiMsg] = []
    if not isinstance(expression, dict) or end_tick <= start_tick:
        return out

    step = max(10, ppq // 16)
    semitone_to_wheel = 8191.0 / 2.0  # GM default: +/-2 semitones

    def clamp_wheel(v: float) -> int:
        return max(-8192, min(8191, int(round(v))))

    bend = expression.get("bend_in")
    if isinstance(bend, dict):
        try:
            semis = float(bend.get("semitones", 0.0))
            ramp_beats = float(bend.get("ramp_beats", 0.0))
        except Exception:
            semis, ramp_beats = 0.0, 0.0
        ramp_ticks = min(beats_to_ticks(max(0.0, ramp_beats), ppq=ppq), end_tick - start_tick)
        if semis > 0 and ramp_ticks > 0:
            start_val = -semis * semitone_to_wheel
            t = start_tick
            while t < start_tick + ramp_ticks:
                frac = (t - start_tick) / ramp_ticks
                out.append(_MidiMsg(t, 0, mido.Message(
                    "pitchwheel", pitch=clamp_wheel(start_val * (1.0 - frac)),
                    channel=ch, time=0)))
                t += step
            out.append(_MidiMsg(start_tick + ramp_ticks, 0, mido.Message(
                "pitchwheel", pitch=0, channel=ch, time=0)))

    vib = expression.get("vibrato")
    if isinstance(vib, dict):
        try:
            depth_cents = float(vib.get("depth_cents", 0.0))
            period_beats = float(vib.get("period_beats", 0.0))
            delay_beats = float(vib.get("delay_beats", 0.0))
        except Exception:
            depth_cents, period_beats, delay_beats = 0.0, 0.0, 0.0
        delay_ticks = beats_to_ticks(max(0.0, delay_beats), ppq=ppq)
        period_ticks = beats_to_ticks(period_beats, ppq=ppq) if period_beats > 0 else 0
        vib_start = start_tick + delay_ticks
        if depth_cents > 0 and period_ticks > 0 and vib_start < end_tick:
            depth_wheel = (depth_cents / 100.0) * semitone_to_wheel
            t = vib_start
            while t < end_tick:
                phase = 2.0 * math.pi * ((t - vib_start) / period_ticks)
                out.append(_MidiMsg(t, 0, mido.Message(
                    "pitchwheel", pitch=clamp_wheel(depth_wheel * math.sin(phase)),
                    channel=ch, time=0)))
                t += step

    dive = expression.get("dive")
    if isinstance(dive, dict):
        try:
            d_semis = float(dive.get("semitones", 0.0))
            drop_beats = float(dive.get("drop_beats", 0.0))
        except Exception:
            d_semis, drop_beats = 0.0, 0.0
        drop_ticks = min(beats_to_ticks(max(0.0, drop_beats), ppq=ppq), end_tick - start_tick)
        if d_semis > 0 and drop_ticks > 0:
            semis_i = max(1, min(24, int(round(d_semis))))
            # Widen the channel's bend range for the dive (RPN 0/0 = pitch
            # bend sensitivity). control_change sorts before pitchwheel at the
            # same tick, so the range is set before the wheel moves.
            for ctrl, val in ((101, 0), (100, 0), (6, semis_i), (38, 0)):
                out.append(_MidiMsg(start_tick, 0, mido.Message(
                    "control_change", control=ctrl, value=val, channel=ch, time=0)))
            t = start_tick
            while t < start_tick + drop_ticks:
                frac = (t - start_tick) / drop_ticks
                out.append(_MidiMsg(t, 0, mido.Message(
                    "pitchwheel", pitch=clamp_wheel(-8191.0 * frac),
                    channel=ch, time=0)))
                t += step
            out.append(_MidiMsg(start_tick + drop_ticks, 0, mido.Message(
                "pitchwheel", pitch=-8191, channel=ch, time=0)))
            # Hold at the bottom until the note ends; then re-center and
            # restore the GM default +/-2 range (order 2 keeps the restore
            # after the wheel reset at this tick).
            out.append(_MidiMsg(end_tick, 0, mido.Message(
                "pitchwheel", pitch=0, channel=ch, time=0)))
            for ctrl, val in ((101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)):
                out.append(_MidiMsg(end_tick, 2, mido.Message(
                    "control_change", control=ctrl, value=val, channel=ch, time=0)))

    swell = expression.get("swell")
    if isinstance(swell, dict):
        try:
            v_from = int(swell.get("from", 64))
            s_ramp_beats = float(swell.get("ramp_beats", 0.0))
            v_to = int(swell.get("to", 127))
        except Exception:
            v_from, s_ramp_beats, v_to = 64, 0.0, 127
        v_from = max(0, min(127, v_from))
        v_to = max(0, min(127, v_to))
        ramp_ticks = min(beats_to_ticks(max(0.0, s_ramp_beats), ppq=ppq), end_tick - start_tick)
        if ramp_ticks > 0 and v_from != v_to:
            # Feedback swell: channel expression (CC11) fades the note in like
            # a volume pedal. The first message lands at the start tick ahead
            # of the note_on, so the attack is quiet.
            t = start_tick
            while t < start_tick + ramp_ticks:
                frac = (t - start_tick) / ramp_ticks
                val = int(round(v_from + (v_to - v_from) * frac))
                out.append(_MidiMsg(t, 0, mido.Message(
                    "control_change", control=11, value=val, channel=ch, time=0)))
                t += step
            out.append(_MidiMsg(start_tick + ramp_ticks, 0, mido.Message(
                "control_change", control=11, value=v_to, channel=ch, time=0)))
            # Restore full expression at note end if the swell ended low.
            if v_to < 127:
                out.append(_MidiMsg(end_tick, 0, mido.Message(
                    "control_change", control=11, value=127, channel=ch, time=0)))

    if out:
        out.append(_MidiMsg(end_tick, 0, mido.Message(
            "pitchwheel", pitch=0, channel=ch, time=0)))
    return out


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
    # notes: (start_tick, end_tick, pitch, vel, ch, expression)
    notes: list[tuple[int, int, int, int, int, Any]] = []

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

        notes.append((start_tick, end_tick, pitch, vel, ch, getattr(ev, "expression", None)))

    # Second pass: de-overlap same-pitch/same-channel notes so note_offs never
    # cross (a later note_off cutting an earlier note, or vice versa).
    # Rules:
    #   - Notes starting at the same tick on the same (channel, pitch): keep
    #     only the longest (velocity as deterministic tie-break).
    #   - An earlier note overlapping a later note's start is truncated to the
    #     later note's start tick.
    by_key: dict[tuple[int, int], list[tuple[int, int, int, int, int, Any]]] = {}
    for n in notes:
        by_key.setdefault((n[4], n[2]), []).append(n)

    deduped: list[tuple[int, int, int, int, int, Any]] = []
    for _key, group in by_key.items():
        group.sort(key=lambda n: (n[0], -(n[1] - n[0]), -n[3]))
        # Drop duplicates that share a start tick (keep first = longest/loudest).
        unique: list[tuple[int, int, int, int, int, Any]] = []
        last_start: Optional[int] = None
        for n in group:
            if last_start is not None and n[0] == last_start:
                continue
            unique.append(n)
            last_start = n[0]
        # Truncate overlaps against the next note's start.
        for i, n in enumerate(unique):
            start_tick, end_tick, pitch, vel, ch, expr = n
            if i + 1 < len(unique):
                next_start = unique[i + 1][0]
                if end_tick > next_start:
                    end_tick = max(next_start, start_tick + 1)
            deduped.append((start_tick, end_tick, pitch, vel, ch, expr))

    msgs: list[_MidiMsg] = []
    expr_spans: list[tuple[int, int, int, Any]] = []
    for start_tick, end_tick, pitch, vel, ch, expr in deduped:
        # Order: note_off first at the same tick to avoid overlaps/stuck notes.
        msgs.append(_MidiMsg(start_tick, 1, mido.Message("note_on", note=pitch, velocity=vel, channel=ch, time=0)))
        msgs.append(_MidiMsg(end_tick, 0, mido.Message("note_off", note=pitch, velocity=0, channel=ch, time=0)))
        # Pitch expression (vibrato / bend-in) is rendered after a per-channel
        # conflict pass below, using the final, de-overlapped tick span.
        if expr:
            expr_spans.append((start_tick, end_tick, ch, expr))

    # Pitchwheel is channel-wide: two overlapping expression windows on the
    # same channel would fight over the wheel. Resolve like a player would —
    # the newer note wins; the older window stops (re-centered) where the
    # newer one begins. This matters for polyphonic parts (e.g. sustained
    # rhythm-guitar chords ringing into the next strum).
    by_ch: dict[int, list[tuple[int, int, Any]]] = {}
    for st, en, ch, expr in expr_spans:
        by_ch.setdefault(ch, []).append((st, en, expr))
    for ch, spans in by_ch.items():
        spans.sort(key=lambda s: s[0])
        for i, (st, en, expr) in enumerate(spans):
            eff_end = en
            if i + 1 < len(spans):
                eff_end = min(en, spans[i + 1][0])
            if eff_end <= st:
                continue
            # _expression_msgs resets the wheel to 0 at eff_end, which also
            # covers the truncation point.
            msgs.extend(_expression_msgs(st, eff_end, ch, expr, ppq=ppq))

    # Note: pitchwheel messages have no `.note` attribute — tolerate that.
    msgs.sort(key=lambda m: (m.tick, m.order, m.msg.type, m.msg.channel, getattr(m.msg, "note", 0)))

    last_tick = 0
    for m in msgs:
        dt = m.tick - last_tick
        if dt < 0:
            dt = 0
        m.msg.time = int(dt)
        track.append(m.msg)
        last_tick = m.tick
