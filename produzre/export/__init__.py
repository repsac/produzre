"""Export subsystem public API.

This module exports Produzre songs to MIDI files and pattern YAML.

Implementation modules:
- export.naming: Export path management and sanitization
- export.midi: MIDI conversion utilities (beats to ticks, track writing)
- export.stems: Full-song and per-instrument MIDI exports
- export.sections: Per-section clip exports
- export.patterns: Pattern detection and sequence YAML generation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable

from ..model import RootConfig
from ..timeline import InstrumentTimeline, SectionTiming

from .naming import create_run_export_dir, sanitize_song_name
from .midi import PPQ, beats_to_ticks
from .stems import (
    write_full_song_midi as _write_full_song_midi_impl,
    write_instrument_stems as _write_instrument_stems_impl,
)
from .sections import write_section_midis as _write_section_midis_impl
from .patterns import write_patterns_and_sequences as _write_patterns_and_sequences_impl


def _effective_song_name(cfg: RootConfig) -> str:
    """Return the sanitized effective song name for export naming."""
    return sanitize_song_name(cfg.get_effective_song_name(), fallback="produzre")


def create_export_root(cfg: RootConfig) -> Path:
    """Create and return the per-run export root directory for this build.

    The export root is created under `cfg.song.exports_root` and includes a
    unique per-run suffix (typically a UTC timestamp) to avoid overwriting prior
    runs.

    Args:
        cfg: Parsed root config.

    Returns:
        Path: Newly-created per-run export root directory.
    """
    logger = logging.getLogger(__name__)
    paths = create_run_export_dir(
        exports_root=cfg.song.exports_root,
        song_name=cfg.get_effective_song_name(),
        logger=logger,
    )
    return paths.root


def write_full_song_midi(
    cfg: RootConfig,
    export_root: Path,
    timelines: Iterable[InstrumentTimeline],
    logger: logging.Logger,
) -> Path:
    """Write a full-song multi-track MIDI from instrument timelines.

    This adapter converts the legacy iterable signature to the newer
    dict-based implementation.

    File path:
        <export_root>/<song_name>.mid

    Args:
        cfg: Parsed root config (tempo and engine program mapping).
        export_root: Per-run export directory.
        timelines: Iterable of `InstrumentTimeline` objects.
        logger: Logger for status output.

    Returns:
        Path: Path to the written full-song MIDI.
    """
    song_name = _effective_song_name(cfg)
    timelines_by_name: Dict[str, InstrumentTimeline] = {tl.instrument: tl for tl in timelines}
    instruments_used = [name for name, tl in timelines_by_name.items() if getattr(tl, "events", None)]
    return _write_full_song_midi_impl(
        cfg=cfg,
        song_name=song_name,
        export_root=export_root,
        instruments_used=instruments_used,
        timelines=timelines_by_name,
        logger=logger,
    )


def write_per_instrument_midis(
    cfg: RootConfig,
    export_root: Path,
    timelines_by_name: Dict[str, InstrumentTimeline],
    logger: logging.Logger,
) -> Dict[str, Path]:
    """Write one full-length stem MIDI per instrument.

    Output layout:
        <export_root>/instruments/<instrument>/<song>_<instrument>.mid

    Args:
        cfg: Parsed root config (tempo and engine program mapping).
        export_root: Per-run export directory.
        timelines_by_name: Mapping of instrument name -> full timeline.
        logger: Logger for status output.

    Returns:
        Dict[str, Path]: Mapping of instrument name -> written stem path.
    """
    song_name = _effective_song_name(cfg)
    instruments_dir = export_root / "instruments"
    instruments_used = [
        name for name, tl in timelines_by_name.items() if getattr(tl, "events", None)
    ]
    return _write_instrument_stems_impl(
        cfg=cfg,
        song_name=song_name,
        instruments_dir=instruments_dir,
        instruments_used=instruments_used,
        timelines=timelines_by_name,
        logger=logger,
    )


def write_section_midis(
    cfg: RootConfig,
    export_root: Path,
    timelines_by_name: Dict[str, InstrumentTimeline],
    section_timings: list[SectionTiming],
    logger: logging.Logger,
    absolute_timing: bool = False,
) -> None:
    """Write per-section MIDI clips for each instrument.

    Output layout:
        <export_root>/instruments/<instrument>/sections/<song>_<instrument>_<section_id>.mid

    Args:
        cfg: Parsed root config.
        export_root: Per-run export directory.
        timelines_by_name: Mapping of instrument name -> full timeline.
        section_timings: Ordered list of section windows.
        logger: Logger for status output.
        absolute_timing: Whether section clips keep song-relative timing.
    """
    song_name = _effective_song_name(cfg)
    instruments_dir = export_root / "instruments"
    instruments_used = list(timelines_by_name.keys())
    _write_section_midis_impl(
        cfg=cfg,
        song_name=song_name,
        instruments_dir=instruments_dir,
        instruments_used=instruments_used,
        timelines=timelines_by_name,
        section_timings=section_timings,
        absolute_timing=absolute_timing,
        logger=logger,
    )


def write_patterns_and_sequences(
    cfg: RootConfig,
    export_root: Path,
    timelines_by_name: Dict[str, InstrumentTimeline],
    section_timings: list[SectionTiming],
    logger: logging.Logger,
) -> None:
    """Export repeating patterns and per-instrument sequence YAML.

    Output layout (per instrument):
        <export_root>/instruments/<instrument>/patterns/...
        <export_root>/instruments/<instrument>/sequence.yaml

    Args:
        cfg: Parsed root config.
        export_root: Per-run export directory.
        timelines_by_name: Mapping of instrument name -> full timeline.
        section_timings: Ordered list of section windows.
        logger: Logger for status output.
    """
    song_name = _effective_song_name(cfg)
    instruments_dir = export_root / "instruments"
    instruments_used = list(timelines_by_name.keys())
    _write_patterns_and_sequences_impl(
        cfg=cfg,
        song_name=song_name,
        instruments_dir=instruments_dir,
        instruments_used=instruments_used,
        timelines=timelines_by_name,
        section_timings=section_timings,
        logger=logger,
    )


__all__ = [
    "PPQ",
    "beats_to_ticks",
    "create_export_root",
    "write_full_song_midi",
    "write_per_instrument_midis",
    "write_section_midis",
    "write_patterns_and_sequences",
]
