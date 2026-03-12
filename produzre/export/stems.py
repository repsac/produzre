from __future__ import annotations

"""Full-song MIDI and per-instrument stem export.

This module writes:

1) A full multi-track song MIDI at the run export root.
2) One full-length MIDI stem per instrument under `instruments/<instrument>/`.

Design goals:
- Stable, predictable track ordering (based on `instruments_used`).
- Consistent tempo meta events.
- Optional program_change events when an engine provides a General MIDI program.

Timing convention:
- All note events are written from beat-based timelines using a fixed PPQ.
"""

from pathlib import Path
from typing import Optional

import mido

from ..model import RootConfig
from ..timeline import InstrumentTimeline
from .midi import PPQ, add_tempo_and_name, program_for_instrument, write_timeline_to_track


def write_full_song_midi(
    *,
    cfg: RootConfig,
    song_name: str,
    export_root: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    logger,
) -> Path:
    """Write the full multi-track song MIDI at the export root.

    Output:
        <export_root>/<song_name>.mid

    Track layout:
      - One MIDI track per instrument in `instruments_used`.
      - Track order is preserved as provided, making downstream DAW imports
        deterministic.

    Track content:
      - Adds tempo + track name meta events at time 0.
      - Adds a program_change at time 0 if a program number is configured for
        the instrument *and* the timeline contains at least one note.
      - Writes the full instrument timeline into the track.

    Channel selection for program_change:
      - Uses the channel of the first note event in the timeline when possible.
      - Falls back to channel 0 if unavailable.

    Args:
        cfg: Parsed configuration (tempo and engine program mapping).
        song_name: Sanitized song title used for file naming.
        export_root: Per-run export directory.
        instruments_used: Ordered list of instruments to include.
        timelines: Mapping of instrument name -> full InstrumentTimeline.
        logger: Logger for status output.

    Returns:
        Path: Path to the written multi-track MIDI file.
    """
    out_path = export_root / f"{song_name}.mid"

    mid = mido.MidiFile(ticks_per_beat=PPQ)

    # One track per instrument. Keep order stable/predictable.
    for inst in instruments_used:
        tl = timelines.get(inst)
        if tl is None:
            continue

        track = mido.MidiTrack()
        mid.tracks.append(track)

        add_tempo_and_name(track, float(cfg.song.bpm), f"{inst}")

        # Program change (if configured) and if we have at least one event to infer channel.
        prog = program_for_instrument(cfg, inst)
        if prog is not None and getattr(tl, "events", None):
            try:
                ch = int(tl.events[0].channel)
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

        write_timeline_to_track(track, tl)

    mid.save(out_path)
    if logger is not None:
        try:
            logger.info("Wrote full song MIDI: %s", out_path)
        except Exception:
            pass
    return out_path


def write_instrument_stems(
    *,
    cfg: RootConfig,
    song_name: str,
    instruments_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    logger,
) -> dict[str, Path]:
    """Write one full-length stem MIDI per instrument.

    Output layout:
        <instruments_dir>/<instrument>/<song_name>_<instrument>.mid

    Content:
      - Each file contains a single track for that instrument.
      - Tempo + track name meta events are written at time 0.
      - A program_change is written at time 0 when a program is configured and
        the timeline contains at least one note.

    Args:
        cfg: Parsed configuration (tempo and engine program mapping).
        song_name: Sanitized song title used for file naming.
        instruments_dir: `<run_root>/instruments` directory.
        instruments_used: Ordered list of instruments to export.
        timelines: Mapping of instrument name -> full InstrumentTimeline.
        logger: Logger for status output.

    Returns:
        dict[str, Path]: Mapping of instrument name -> written stem file path.
    """
    out: dict[str, Path] = {}

    for inst in instruments_used:
        tl = timelines.get(inst)
        if tl is None:
            continue

        inst_dir = instruments_dir / inst
        inst_dir.mkdir(parents=True, exist_ok=True)

        out_path = inst_dir / f"{song_name}_{inst}.mid"

        mid = mido.MidiFile(ticks_per_beat=PPQ)
        track = mido.MidiTrack()
        mid.tracks.append(track)

        add_tempo_and_name(track, float(cfg.song.bpm), f"{inst}")

        prog = program_for_instrument(cfg, inst)
        if prog is not None and getattr(tl, "events", None):
            try:
                ch = int(tl.events[0].channel)
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

        write_timeline_to_track(track, tl)
        mid.save(out_path)
        out[inst] = out_path

        if logger is not None:
            try:
                logger.info("Wrote %s stem MIDI: %s", inst, out_path)
            except Exception:
                pass

    return out


#@TODO: search and update code as needed
# Backward-friendly aliases (older code may call these names).
write_song_midi = write_full_song_midi
write_full_song_mid = write_full_song_midi
write_stems = write_instrument_stems