from __future__ import annotations

"""Pattern extraction and per-instrument sequencer export.

This module identifies repeating rhythmic/melodic "pattern windows" within each
section boundary for each instrument timeline and exports:

- Unique pattern MIDI files (deduplicated by a normalized event signature)
- A per-instrument `sequence.yaml` describing the pattern order per section

Key ideas:
- Pattern detection is *per instrument* and respects *section boundaries*.
- Pattern length is defined in *bars* (`cfg.song.pattern_bars`) but converted to
  beats using each section's effective `beats_per_bar` (supports mixed meters).
- Optional normalization (quantization + velocity bucketing) reduces accidental
  mismatches due to tiny humanization differences.
- Optional merging can collapse consecutive identical windows into longer
  multi-window patterns.

Internal time units:
- All times are expressed in quarter-note beats.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mido
import yaml

from ..model import RootConfig
from ..timeline import InstrumentTimeline, SectionTiming
from .midi import PPQ, add_tempo_and_name, program_for_instrument, write_timeline_to_track


def _quantize(value: float, grid: float) -> float:
    """Quantize a beat value to the nearest rhythmic grid.

    This helper is used when normalizing pattern signatures. Quantization helps
    treat near-identical events as identical even if slight timing differences
    exist (e.g., due to humanization or float rounding).

    Args:
        value: The value (in beats) to quantize.
        grid: Grid size in beats. Examples:
            - 0.25 = 16th-note grid in 4/4
            - 0.5  = 8th-note grid
            - 1.0  = quarter-note grid
            - <= 0 disables quantization

    Returns:
        float: Quantized beat value.
    """
    if grid <= 0:
        return float(value)
    return round(float(value) / grid) * grid


def _bucket_velocity(v: int, step: int) -> int:
    """Bucket MIDI velocity to a coarse step size.

    Velocity bucketing helps avoid creating separate pattern IDs for otherwise
    identical patterns whose velocities differ by a small amount.

    Args:
        v: Raw MIDI velocity (0-127).
        step: Bucket size. For example:
            - 1 keeps velocities unchanged
            - 4 rounds to the nearest multiple of 4
            - <= 1 disables bucketing

    Returns:
        int: Bucketed velocity clamped to [0, 127].
    """
    if step <= 1:
        return int(v)
    v = max(0, min(127, int(v)))
    return int(round(v / step) * step)


def _collect_window_events(
    *,
    timeline: InstrumentTimeline,
    window_start: float,
    window_end: float,
) -> list[Any]:
    """Collect timeline events that overlap a beat window.

    Events are included if they overlap the half-open interval
    `[window_start, window_end)`.

    This function is intentionally tolerant:
      - Skips events missing `start_beat`/`duration_beats`.
      - Skips non-positive durations.

    Args:
        timeline: InstrumentTimeline containing note events.
        window_start: Window start in beats.
        window_end: Window end in beats (exclusive).

    Returns:
        list[Any]: List of event objects overlapping the window.
    """
    out: list[Any] = []
    for ev in getattr(timeline, "events", []) or []:
        try:
            s = float(ev.start_beat)
            d = float(ev.duration_beats)
        except Exception:
            continue
        if d <= 0:
            continue
        e = s + d
        if e <= window_start or s >= window_end:
            continue
        out.append(ev)
    return out


def _write_pattern_midi(
    *,
    cfg: RootConfig,
    song_name: str,
    inst_name: str,
    pid: str,
    out_path: Path,
    events: list[Any],
    run_start: float,
    run_len_beats: float,
    logger,
) -> None:
    """Write a single pattern MIDI file clipped to a pattern run window.

    The source `events` may extend beyond the requested window; this function
    clips each event to `[run_start, run_start + run_len_beats]` and re-bases
    the resulting notes so the pattern starts at beat 0.

    MIDI output:
      - Creates a one-track MidiFile with tempo + track name.
      - Adds a program_change if a program is configured and the pattern
        contains at least one note.
      - Emits note events using `write_timeline_to_track()`.

    Args:
        cfg: RootConfig (tempo and engine program mapping).
        song_name: Sanitized song name prefix.
        inst_name: Instrument name (e.g., "drums").
        pid: Pattern ID (e.g., "p001").
        out_path: Target MIDI file path.
        events: Source events overlapping the window.
        run_start: Absolute start beat of the window.
        run_len_beats: Window length in beats.
        logger: Logger used for informational output.

    Returns:
        None
    """
    pat_tl = InstrumentTimeline(instrument=inst_name)

    for ev in events:
        try:
            s = float(ev.start_beat)
            d = float(ev.duration_beats)
            pitch = int(ev.pitch)
            vel = int(ev.velocity)
            ch = int(ev.channel)
        except Exception:
            continue

        if d <= 0:
            continue

        ev_end = s + d
        # Clip to run window
        cs = max(s, run_start)
        ce = min(ev_end, run_start + run_len_beats)
        cd = ce - cs
        if cd <= 0:
            continue

        pat_tl.add_note(
            start_beat=cs - run_start,
            duration_beats=cd,
            pitch=pitch,
            velocity=vel,
            channel=ch,
        )

    try:
        pat_tl.sort_events()
    except Exception:
        pass

    mid = mido.MidiFile(ticks_per_beat=PPQ)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    add_tempo_and_name(track, float(cfg.song.bpm), f"{inst_name}_{pid}")

    prog = program_for_instrument(cfg, inst_name)
    if prog is not None and getattr(pat_tl, "events", None):
        try:
            ch0 = int(pat_tl.events[0].channel)
        except Exception:
            ch0 = 0
        ch0 = max(0, min(15, ch0))
        track.append(
            mido.Message(
                "program_change",
                program=int(prog),
                channel=ch0,
                time=0,
            )
        )

    write_timeline_to_track(track, pat_tl)
    mid.save(out_path)

    if logger is not None:
        try:
            logger.info("Wrote %s pattern %s: %s", inst_name, pid, out_path)
        except Exception:
            pass


def write_patterns_and_sequences(
    *,
    cfg: RootConfig,
    song_name: str,
    instruments_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    section_timings: list[SectionTiming],
    logger,
) -> dict[str, Path]:
    """Export unique patterns and a per-instrument sequencer YAML.

    Output layout (per instrument):
      - <instruments_dir>/<instrument>/patterns/<song>_<instrument>_p###.mid
      - <instruments_dir>/<instrument>/sequence.yaml

    Pattern detection:
      - Operates independently per instrument.
      - Respects section boundaries (no windows span across sections).
      - Uses `cfg.song.pattern_bars` bars per window.
      - Converts bars -> beats using each section's effective `beats_per_bar`
        from `SectionTiming` (supports mixed meters).

    Normalization options (song-level):
      - `pattern_quantize_beats`: quantize start/duration when computing the
        pattern signature.
      - `pattern_velocity_step`: bucket velocities when computing signature.

    Optional merge:
      - If `pattern_merge_repeats` is True, consecutive identical non-empty
        windows can be merged into longer patterns.
      - `pattern_merge_min_run` controls the minimum run length to merge.
      - `pattern_merge_max` optionally caps the run length (0 means no cap).

    Sequencer YAML:
      - Lists pattern IDs in order for each section.
      - Includes per-section metadata such as beats_per_bar and computed
        pattern_length_beats.
      - Includes a patterns table mapping IDs to filenames and lengths.

    Args:
        cfg: Parsed configuration.
        song_name: Sanitized song title used for file naming.
        instruments_dir: `<run_root>/instruments` directory.
        instruments_used: List of instruments to process.
        timelines: Mapping of instrument name -> full InstrumentTimeline.
        section_timings: Ordered list of SectionTiming entries.
        logger: Logger for status/debug messages.

    Returns:
        dict[str, Path]: Mapping of instrument name -> written sequence.yaml path.
    """

    beats_per_bar_global = float(cfg.song.beats_per_bar)
    pattern_bars = int(getattr(cfg.song, "pattern_bars", 1) or 1)

    # Optional normalization controls.
    quantize_beats = float(getattr(cfg.song, "pattern_quantize_beats", 0.0) or 0.0)
    velocity_step = int(getattr(cfg.song, "pattern_velocity_step", 1) or 1)

    merge_repeats = bool(getattr(cfg.song, "pattern_merge_repeats", False) or False)
    merge_max = int(getattr(cfg.song, "pattern_merge_max", 0) or 0)  # 0 => no max
    merge_min_run = int(getattr(cfg.song, "pattern_merge_min_run", 2) or 2)
    if merge_min_run < 2:
        merge_min_run = 2

    if logger is not None:
        try:
            logger.info("pattern_bars=%s (pattern length is per-section meter)", pattern_bars)
            if quantize_beats > 0:
                logger.info("pattern_quantize_beats=%.4f", quantize_beats)
            if velocity_step > 1:
                logger.info("pattern_velocity_step=%d", velocity_step)
            if merge_repeats:
                if merge_max > 0:
                    logger.info(
                        "pattern_merge_repeats=True (min_run=%d, max=%d)",
                        merge_min_run,
                        merge_max,
                    )
                else:
                    logger.info("pattern_merge_repeats=True (min_run=%d)", merge_min_run)
        except Exception:
            pass

    out_seq_paths: dict[str, Path] = {}

    for inst_name in instruments_used:
        full_tl = timelines.get(inst_name)
        if full_tl is None:
            continue

        inst_dir = instruments_dir / inst_name
        patterns_root = inst_dir / "patterns"
        patterns_root.mkdir(parents=True, exist_ok=True)

        # Map normalized pattern representation -> pattern ID (p001, p002, ...)
        pattern_map: Dict[Tuple, str] = {}
        # Map pattern ID -> relative filename
        pattern_files: Dict[str, str] = {}
        # Map pattern ID -> length in beats
        pattern_lengths: Dict[str, float] = {}
        # Per-section pattern sequences
        sections_seq: Dict[str, list[str]] = {}
        # Per-section metadata (meter + pattern length + timing)
        sections_meta: Dict[str, dict] = {}

        for st in section_timings:
            section_len = float(st.length_beats)
            section_beats_per_bar = float(getattr(st, "beats_per_bar", beats_per_bar_global))
            pattern_len_beats = float(section_beats_per_bar * pattern_bars)

            if logger is not None:
                try:
                    logger.debug(
                        "  %s/%s: section_len=%.2f beats, beats_per_bar=%.2f, pattern_len_beats=%.2f",
                        inst_name,
                        st.id,
                        float(section_len),
                        float(section_beats_per_bar),
                        float(pattern_len_beats),
                    )
                except Exception:
                    pass

            # Walk the section in pattern windows (pattern_bars bars @ this section's meter)
            pos = 0.0
            sequence: list[str] = []
            windows: list[dict] = []  # each: {"pid": str, "start": float, "events": list|None}

            while pos < section_len - 1e-9:
                window_start = float(st.start_beat) + pos
                window_end = min(float(st.end_beat), window_start + pattern_len_beats)

                window_events = _collect_window_events(
                    timeline=full_tl,
                    window_start=window_start,
                    window_end=window_end,
                )

                if not window_events:
                    sequence.append("_")
                    windows.append({"pid": "_", "start": window_start, "events": None})
                    pos += pattern_len_beats
                    continue

                # Normalize: relative timing + duration + pitch + velocity, plus window length
                # to avoid collisions across mixed meters.
                run_start = window_start
                run_len = float(window_end - window_start)

                norm = (round(float(run_len), 6),) + tuple(
                    (
                        round(_quantize(float(ev.start_beat) - run_start, quantize_beats), 6),
                        round(_quantize(float(ev.duration_beats), quantize_beats), 6),
                        int(ev.pitch),
                        _bucket_velocity(int(ev.velocity), velocity_step),
                    )
                    for ev in sorted(window_events, key=lambda e: (float(e.start_beat), int(e.pitch)))
                )

                if norm in pattern_map:
                    pid = pattern_map[norm]
                else:
                    pid = f"p{len(pattern_map) + 1:03d}"
                    pattern_map[norm] = pid

                    out_path = patterns_root / f"{song_name}_{inst_name}_{pid}.mid"
                    _write_pattern_midi(
                        cfg=cfg,
                        song_name=song_name,
                        inst_name=inst_name,
                        pid=pid,
                        out_path=out_path,
                        events=window_events,
                        run_start=run_start,
                        run_len_beats=run_len,
                        logger=logger,
                    )
                    pattern_files[pid] = out_path.name
                    pattern_lengths[pid] = float(run_len)

                sequence.append(pid)
                windows.append({"pid": pid, "start": window_start, "events": window_events})
                pos += pattern_len_beats

            # Optional: merge consecutive identical non-empty windows into longer patterns.
            if merge_repeats and windows:
                raw_sequence = list(sequence)
                merged_sequence: list[str] = []
                i = 0
                while i < len(windows):
                    w = windows[i]
                    if w["pid"] == "_":
                        merged_sequence.append("_")
                        i += 1
                        continue

                    pid0 = str(w["pid"])
                    n = 1
                    while i + n < len(windows) and windows[i + n]["pid"] == pid0:
                        if merge_max > 0 and n >= merge_max:
                            break
                        n += 1

                    if n < merge_min_run:
                        merged_sequence.append(pid0)
                        i += 1
                        continue

                    run_start = float(windows[i]["start"])
                    merged_len_beats = float(pattern_len_beats * n)

                    merged_events = []
                    for k in range(n):
                        evs = windows[i + k]["events"] or []
                        merged_events.extend(evs)

                    merged_norm = (round(merged_len_beats, 6),) + tuple(
                        (
                            round(_quantize(float(ev.start_beat) - run_start, quantize_beats), 6),
                            round(_quantize(float(ev.duration_beats), quantize_beats), 6),
                            int(ev.pitch),
                            _bucket_velocity(int(ev.velocity), velocity_step),
                        )
                        for ev in sorted(merged_events, key=lambda e: (float(e.start_beat), int(e.pitch)))
                        if float(ev.start_beat) >= run_start and float(ev.start_beat) < (run_start + merged_len_beats)
                    )

                    if merged_norm in pattern_map:
                        mpid = pattern_map[merged_norm]
                    else:
                        mpid = f"p{len(pattern_map) + 1:03d}"
                        pattern_map[merged_norm] = mpid

                        out_path = patterns_root / f"{song_name}_{inst_name}_{mpid}.mid"
                        _write_pattern_midi(
                            cfg=cfg,
                            song_name=song_name,
                            inst_name=inst_name,
                            pid=mpid,
                            out_path=out_path,
                            events=merged_events,
                            run_start=run_start,
                            run_len_beats=merged_len_beats,
                            logger=logger,
                        )
                        pattern_files[mpid] = out_path.name
                        pattern_lengths[mpid] = float(merged_len_beats)

                        if logger is not None:
                            try:
                                logger.info(
                                    "Wrote %s merged pattern %s (x%d): %s",
                                    inst_name,
                                    mpid,
                                    n,
                                    out_path,
                                )
                            except Exception:
                                pass

                    merged_sequence.append(mpid)
                    i += n

                sequence = merged_sequence
                if logger is not None:
                    try:
                        logger.debug(
                            "  %s/%s: merged windows %d -> %d",
                            inst_name,
                            st.id,
                            len(raw_sequence),
                            len(sequence),
                        )
                    except Exception:
                        pass

            if sequence:
                sections_seq[st.id] = sequence
                sections_meta[st.id] = {
                    "type": st.type,
                    "start_beat": float(st.start_beat),
                    "end_beat": float(st.end_beat),
                    "length_beats": float(st.length_beats),
                    "beats_per_bar": float(section_beats_per_bar),
                    "pattern_bars": int(pattern_bars),
                    "pattern_length_beats": float(pattern_len_beats),
                    "windows": int(len(sequence)),
                    "windows_raw": int(len(windows)),
                }

        seq_path = inst_dir / "sequence.yaml"
        data = {
            "song_name": song_name,
            "instrument": inst_name,
            "beats_per_bar": beats_per_bar_global,
            "pattern_bars": pattern_bars,
            "pattern_quantize_beats": quantize_beats,
            "pattern_velocity_step": velocity_step,
            "pattern_merge_repeats": merge_repeats,
            "pattern_merge_max": merge_max,
            "pattern_merge_min_run": merge_min_run,
            "pattern_length": {
                "bars": pattern_bars,
                "beats": float(beats_per_bar_global * pattern_bars),
                "note": "If meters vary by section, actual pattern beats per section are section.beats_per_bar * pattern_bars.",
            },
            "patterns": {
                pid: {
                    "file": pattern_files[pid],
                    "length_beats": float(pattern_lengths.get(pid, 0.0)),
                }
                for pid in sorted(pattern_files.keys())
            },
            "sections": sections_seq,
            "sections_meta": sections_meta,
        }

        with seq_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

        if logger is not None:
            try:
                logger.info("Wrote %s sequencer YAML: %s", inst_name, seq_path)
            except Exception:
                pass

        out_seq_paths[inst_name] = seq_path

    return out_seq_paths
