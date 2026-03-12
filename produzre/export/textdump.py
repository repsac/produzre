from __future__ import annotations

"""Timeline-based text dump exports.

This module writes human-readable + machine-readable views of Produzre-generated
timelines (not MIDI parsing). Outputs are intended for debugging, review, and
LLM-friendly inspection.

Outputs (per instrument):
- events TSV: <song>_<instrument>.events.tsv
- grid text:  <song>_<instrument>.grid.txt

These exports are deterministic because they are derived from the same rendered
InstrumentTimeline objects used to write MIDI.
"""

import csv
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from ..model import RootConfig
from ..timeline import InstrumentTimeline
from ..analysis.grid_format import grid_text_from_rows
from ..analysis.tab_format import tab_text_from_rows, is_guitar_instrument


@dataclass(frozen=True)
class EventRow:
    instrument: str
    section_id: str
    start_beat_abs: float
    duration_beats: float
    pitch: int
    velocity: int
    channel: int
    program: int
    kind: str  # Determinism tag for debugging (e.g., "kick", "ghost", "fill")


@dataclass(frozen=True)
class GridRow:
    """Minimal event row used for ASCII grid rendering.

    This is intentionally separate from EventRow because TSV needs channel/program/section_id,
    while grid formatting only needs timing + pitch/velocity + a label note name.
    """

    instrument: str
    start_beat_abs: float
    duration_beats: float
    pitch: int
    velocity: int
    note: str


def _note_name(pitch: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    p = int(pitch)
    n = names[p % 12]
    octv = (p // 12) - 1
    return f"{n}{octv}"


def _iter_timeline_events(tl: InstrumentTimeline) -> Iterable[Any]:
    """Best-effort event iterator over InstrumentTimeline.

    Supports common representations:
    - tl.notes
    - tl.events
    - tl.iter_notes()
    """
    if hasattr(tl, "iter_notes") and callable(getattr(tl, "iter_notes")):
        return tl.iter_notes()
    if hasattr(tl, "notes"):
        return getattr(tl, "notes")
    if hasattr(tl, "events"):
        return getattr(tl, "events")
    raise TypeError("InstrumentTimeline has no recognizable event container (notes/events/iter_notes).")


def _event_fields(ev: Any) -> tuple[float, float, int, int, int, int, str]:
    """Extract (start_beat, duration_beats, pitch, velocity, channel, program, kind)."""
    start = float(getattr(ev, "start_beat", getattr(ev, "start", 0.0)))
    dur = float(getattr(ev, "duration_beats", getattr(ev, "duration", 0.25)))
    pitch = int(getattr(ev, "pitch"))
    vel = int(getattr(ev, "velocity", 100))
    ch = int(getattr(ev, "channel", 0))
    prog = int(getattr(ev, "program", 0))
    kind = str(getattr(ev, "kind", ""))
    return start, dur, pitch, vel, ch, prog, kind


def _assign_section_id(start_beat: float, section_timings: Optional[list[Any]]) -> str:
    if not section_timings:
        return ""
    for st in section_timings:
        s0 = float(getattr(st, "start_beat", 0.0))
        s1 = float(getattr(st, "end_beat", 0.0))
        if start_beat >= s0 and start_beat < s1:
            return str(getattr(st, "id", getattr(st, "section_id", "")))
    return ""


def _beats_per_bar(cfg: RootConfig) -> float:
    # Try a few common places; default 4.
    song = getattr(cfg, "song", None)
    for attr in ("beats_per_bar", "beats_per_measure"):
        if song is not None and hasattr(song, attr):
            try:
                return float(getattr(song, attr))
            except Exception:
                pass
    return 4.0


def _clean_str(s: Any) -> str:
    """Return a safe text string for TSV output.

    We explicitly strip NUL characters ("\x00") because they cause `diff` and many
    text tools to treat the TSV as binary.
    """
    if s is None:
        return ""
    txt = str(s)
    return txt.replace("\x00", "")


def write_events_tsv(
    *,
    cfg: RootConfig,
    song_name: str,
    analysis_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    section_timings: Optional[list[Any]],
    logger: logging.Logger,
) -> dict[str, Path]:
    """Write per-instrument events TSV dumps."""
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    bpb = _beats_per_bar(cfg)

    for inst in instruments_used:
        tl = timelines[inst]
        inst_dir = analysis_dir / inst
        inst_dir.mkdir(parents=True, exist_ok=True)
        path = inst_dir / f"{song_name}_{inst}.events.tsv"

        rows: list[EventRow] = []
        for ev in _iter_timeline_events(tl):
            start, dur, pitch, vel, ch, prog, kind = _event_fields(ev)
            sec_id = _assign_section_id(start, section_timings)

            rows.append(
                EventRow(
                    instrument=inst,
                    section_id=sec_id,
                    start_beat_abs=start,
                    duration_beats=dur,
                    pitch=pitch,
                    velocity=vel,
                    channel=ch,
                    program=prog,
                    kind=kind,
                )
            )

        rows.sort(key=lambda r: (r.start_beat_abs, r.pitch))

        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(
                [
                    "instrument",
                    "section_id",
                    "bar",
                    "beat",
                    "start_beat_abs",
                    "duration_beats",
                    "pitch",
                    "note",
                    "velocity",
                    "channel",
                    "program",
                    "kind",  # Determinism debugging tag
                ]
            )

            for r in rows:
                bar = int(math.floor(r.start_beat_abs / bpb)) + 1
                beat_in_bar = (r.start_beat_abs % bpb) + 1.0
                w.writerow(
                    [
                        _clean_str(r.instrument),
                        _clean_str(r.section_id),
                        bar,
                        f"{beat_in_bar:.3f}",
                        f"{r.start_beat_abs:.3f}",
                        f"{r.duration_beats:.3f}",
                        r.pitch,
                        _clean_str(_note_name(r.pitch)),
                        r.velocity,
                        r.channel,
                        r.program,
                        _clean_str(r.kind),  # Determinism debugging tag
                    ]
                )

        logger.info("Wrote events TSV: %s", path)
        out[inst] = path

    return out


def write_grids(
    *,
    cfg: RootConfig,
    song_name: str,
    analysis_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    section_timings: Optional[list[Any]],
    subdiv: int,
    logger: logging.Logger,
) -> dict[str, Path]:
    """Write per-instrument ASCII grid dumps (piano-roll style; drums use GM names)."""
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    bpb = _beats_per_bar(cfg)
    steps_per_bar = int(subdiv)

    for inst in instruments_used:
        tl = timelines[inst]
        inst_dir = analysis_dir / inst
        inst_dir.mkdir(parents=True, exist_ok=True)
        path = inst_dir / f"{song_name}_{inst}.grid.txt"

        # Collect events into lightweight rows for the shared grid formatter.
        rows: list[GridRow] = []
        max_beat = 0.0
        for ev in _iter_timeline_events(tl):
            start, dur, pitch, vel, ch, prog, kind = _event_fields(ev)
            max_beat = max(max_beat, start + dur)
            rows.append(
                GridRow(
                    instrument=inst,
                    start_beat_abs=start,
                    duration_beats=dur,
                    pitch=pitch,
                    velocity=vel,
                    note="" if inst == "drums" else _note_name(pitch),
                )
            )

        bars_total = int(math.ceil(max_beat / bpb)) if max_beat > 0 else 1

        txt = grid_text_from_rows(
            rows,
            beats_per_bar=bpb,
            subdiv=steps_per_bar,
            instrument=inst,
            bars_total=bars_total,
        )

        with path.open("w", encoding="utf-8") as f:
            f.write(txt)

        logger.info("Wrote grid dump: %s", path)
        out[inst] = path

    return out


def write_tabs(
    *,
    cfg: RootConfig,
    song_name: str,
    analysis_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    section_timings: Optional[list[Any]],
    subdiv: int,
    logger: logging.Logger,
) -> dict[str, Path]:
    """Write per-instrument ASCII tab dumps for guitar instruments only.

    Non-guitar instruments are silently skipped.
    """
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    bpb = _beats_per_bar(cfg)
    steps_per_bar = int(subdiv)

    for inst in instruments_used:
        if not is_guitar_instrument(inst):
            continue

        tl = timelines[inst]
        inst_dir = analysis_dir / inst
        inst_dir.mkdir(parents=True, exist_ok=True)
        path = inst_dir / f"{song_name}_{inst}.tab.txt"

        rows: list[GridRow] = []
        max_beat = 0.0
        for ev in _iter_timeline_events(tl):
            start, dur, pitch, vel, ch, prog, kind = _event_fields(ev)
            max_beat = max(max_beat, start + dur)
            rows.append(
                GridRow(
                    instrument=inst,
                    start_beat_abs=start,
                    duration_beats=dur,
                    pitch=pitch,
                    velocity=vel,
                    note=_note_name(pitch),
                )
            )

        bars_total = int(math.ceil(max_beat / bpb)) if max_beat > 0 else 1

        txt = tab_text_from_rows(
            rows,
            beats_per_bar=bpb,
            subdiv=steps_per_bar,
            instrument=inst,
            bars_total=bars_total,
        )

        with path.open("w", encoding="utf-8") as f:
            f.write(txt)

        logger.info("Wrote tab dump: %s", path)
        out[inst] = path

    return out


def write_timeline_text_dumps(
    *,
    cfg: RootConfig,
    song_name: str,
    analysis_dir: Path,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    section_timings: Optional[list[Any]],
    views: list[str],
    subdiv: int,
    logger: logging.Logger,
) -> dict[str, dict[str, Path]]:
    """Write requested text dump views for each instrument.

    Views:
      - "events": TSV list of events with bar/beat info
      - "grid": ASCII piano-roll / drum grid
      - "tab": ASCII guitar tablature (guitar instruments only)
    """
    analysis_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Path]] = {inst: {} for inst in instruments_used}

    vset = {v.strip().lower() for v in (views or [])}
    if not vset:
        vset = {"events", "grid"}

    if "events" in vset:
        ev_paths = write_events_tsv(
            cfg=cfg,
            song_name=song_name,
            analysis_dir=analysis_dir,
            instruments_used=instruments_used,
            timelines=timelines,
            section_timings=section_timings,
            logger=logger,
        )
        for inst, p in ev_paths.items():
            results[inst]["events"] = p

    if "grid" in vset:
        grid_paths = write_grids(
            cfg=cfg,
            song_name=song_name,
            analysis_dir=analysis_dir,
            instruments_used=instruments_used,
            timelines=timelines,
            section_timings=section_timings,
            subdiv=subdiv,
            logger=logger,
        )
        for inst, p in grid_paths.items():
            results[inst]["grid"] = p

    if "tab" in vset:
        tab_paths = write_tabs(
            cfg=cfg,
            song_name=song_name,
            analysis_dir=analysis_dir,
            instruments_used=instruments_used,
            timelines=timelines,
            section_timings=section_timings,
            subdiv=subdiv,
            logger=logger,
        )
        for inst, p in tab_paths.items():
            results[inst]["tab"] = p

    return results