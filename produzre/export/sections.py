from __future__ import annotations

"""Per-section MIDI export helpers.

This module supports the "sections" export feature, which writes one MIDI file
per song section (verse/chorus/bridge/etc.) per instrument.

Key behaviors:
- Slicing respects section boundaries using beat-based timing.
- Notes overlapping section edges are clipped (not discarded).
- Section MIDI timing can be:
    - section-relative (starts at beat 0), or
    - song-relative/absolute (keeps original beat positions)

These exports are intended for DAW workflows (e.g., assembling and editing
arrangements via per-section clips).
"""

from pathlib import Path
from typing import Dict, List

import mido

from ..model import RootConfig
from ..timeline import InstrumentTimeline, SectionTiming
from .midi import PPQ, add_tempo_and_name, program_for_instrument, write_timeline_to_track


def slice_timeline_for_section(
    *,
    timeline: InstrumentTimeline,
    section: SectionTiming,
    absolute_timing: bool,
) -> InstrumentTimeline:
    """Slice an instrument timeline to a section's time window.

    The input `timeline` contains beat-based note events for a single instrument
    across the entire song. This function extracts only the events that overlap
    the requested section window:

      - Events fully outside the section are skipped.
      - Events that overlap section edges are *clipped* to the section boundary.

    Timing modes:
      - If `absolute_timing` is False, the returned timeline is shifted so the
        section starts at beat 0 (DAW-friendly "clip" behavior).
      - If `absolute_timing` is True, event times remain song-relative (useful
        when you want the section MIDI to line up on the full song timeline).

    Robustness:
      - Events missing `start_beat`/`duration_beats` are skipped.
      - Non-positive durations are skipped.
      - Output events are sorted when possible for determinism.

    Args:
        timeline: Full-song `InstrumentTimeline` for one instrument.
        section: `SectionTiming` window with `start_beat` and `end_beat`.
        absolute_timing: Whether to keep song-relative timing.

    Returns:
        InstrumentTimeline: A new timeline containing only the clipped events
        that fall within the section window.
    """
    start = float(section.start_beat)
    end = float(section.end_beat)
    shift = 0.0 if absolute_timing else start

    out = InstrumentTimeline(instrument=getattr(timeline, "instrument", ""))

    for ev in getattr(timeline, "events", []) or []:
        try:
            ev_start = float(ev.start_beat)
            ev_dur = float(ev.duration_beats)
        except Exception:
            continue

        if ev_dur <= 0:
            continue

        ev_end = ev_start + ev_dur

        # Skip notes that do not overlap this section.
        if ev_end <= start or ev_start >= end:
            continue

        # Clip note to the section window.
        clipped_start = max(ev_start, start)
        clipped_end = min(ev_end, end)
        clipped_dur = clipped_end - clipped_start
        if clipped_dur <= 0:
            continue

        out.add_note(
            start_beat=clipped_start - shift,
            duration_beats=clipped_dur,
            pitch=int(ev.pitch),
            velocity=int(ev.velocity),
            channel=int(ev.channel),
        )

    # Keep deterministic ordering.
    try:
        out.sort_events()
    except Exception:
        pass

    return out


def write_section_midis(
    *,
    cfg: RootConfig,
    song_name: str,
    instruments_dir: Path,
    instruments_used: List[str],
    timelines: Dict[str, InstrumentTimeline],
    section_timings: List[SectionTiming],
    absolute_timing: bool,
    logger,
) -> Dict[str, List[Path]]:
    """Write per-section MIDI files for each instrument.

    For each instrument in `instruments_used`, this function:
      1) Slices the full-song timeline into each section window.
      2) Writes a MIDI file per section.

    Output layout:
        <instruments_dir>/<instrument>/sections/<song_name>_<instrument>_<section_id>.mid

    MIDI content:
      - Creates a one-track MIDI file per section.
      - Writes tempo + track name meta events at time 0.
      - Emits a program_change at time 0 if the instrument has a configured
        program number AND the section contains at least one note.
      - Writes note events in beats->ticks using the shared PPQ.

    Empty sections:
      - If a section contains no notes for an instrument, an empty MIDI file is
        still written (tempo/name only). This makes downstream DAW imports and
        scripting predictable.

    Logging:
      - Logs one info line per written file when `logger` is provided.

    Args:
        cfg: Parsed configuration (tempo and engine program mapping).
        song_name: Sanitized song title used for file naming.
        instruments_dir: `<run_root>/instruments` directory.
        instruments_used: Instrument keys to export.
        timelines: Mapping of instrument name -> full InstrumentTimeline.
        section_timings: Ordered list of SectionTiming windows.
        absolute_timing: Whether section MIDIs keep song-relative timing.
        logger: Logger for status output.

    Returns:
        Dict[str, List[Path]]: Mapping of instrument name -> list of written
        section MIDI file paths in section order.
    """
    out: Dict[str, List[Path]] = {}

    for inst in instruments_used:
        tl = timelines.get(inst)
        if tl is None:
            continue

        inst_dir = instruments_dir / inst
        sections_dir = inst_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)

        out[inst] = []

        for st in section_timings:
            sec_tl = slice_timeline_for_section(
                timeline=tl,
                section=st,
                absolute_timing=absolute_timing,
            )

            out_path = sections_dir / f"{song_name}_{inst}_{st.id}.mid"

            mid = mido.MidiFile(ticks_per_beat=PPQ)
            track = mido.MidiTrack()
            mid.tracks.append(track)

            add_tempo_and_name(track, float(cfg.song.bpm), f"{inst}_{st.id}")

            prog = program_for_instrument(cfg, inst)
            if prog is not None and getattr(sec_tl, "events", None):
                try:
                    ch = int(sec_tl.events[0].channel)
                except Exception:
                    ch = 0
                ch = max(0, min(15, ch))
                track.append(
                    mido.Message(
                        "program_change",
                        program=int(prog),
                        channel=ch,
                        time=0,
                    )
                )

            write_timeline_to_track(track, sec_tl)
            mid.save(out_path)
            out[inst].append(out_path)

            if logger is not None:
                try:
                    logger.info("Wrote %s section %s: %s", inst, st.id, out_path)
                except Exception:
                    pass

    return out


# Backward-friendly aliases
write_section_midi_files = write_section_midis
