from __future__ import annotations

"""Export orchestration helpers.

This module bridges the build orchestration layer and the export subsystem.

Responsibilities:
- Create a unique per-run export directory (naming + folders).
- Wire built instrument timelines and section timings into the export functions.
- Apply CLI/export flags (sections, patterns, absolute section timing).

The actual MIDI/YAML writing is implemented in the `produzre.export.*`
subpackage; this module only coordinates those calls and returns the export
root directory.
"""

import logging
from pathlib import Path

from ..model import RootConfig
from ..timeline import InstrumentTimeline
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plan import BuildPlan

from ..export.naming import create_run_export_dir, sanitize_song_name
from ..export.stems import write_full_song_midi, write_instrument_stems
from ..export.sections import write_section_midis
from ..export.patterns import write_patterns_and_sequences
from ..export.config import ExportConfig
from ..export.index import generate_export_index, generate_quick_reference


# Helper to read export configuration from cfg.raw.
def _get_export_config(cfg: RootConfig) -> ExportConfig:
    """Read ExportConfig from config or return default DAW preset.

    Reads from cfg.raw using this shape:

    exports:
      mode: daw  # or minimal, debug, custom
      # Optional overrides for custom mode
      write_full_song: true
      write_stems: true
      write_sections: true
      write_patterns: true
      write_index: true
      write_analysis: false
      write_grids: false

    Defaults to 'daw' mode if not specified.
    """
    raw = getattr(cfg, "raw", None) or {}
    exports = raw.get("exports") if isinstance(raw, dict) else None

    if not isinstance(exports, dict):
        return ExportConfig.from_mode("daw")

    mode_str = exports.get("mode", "daw")
    export_config = ExportConfig.from_mode(mode_str)

    # Allow custom overrides when in custom mode
    if mode_str == "custom":
        if "write_full_song" in exports:
            export_config.write_full_song = bool(exports["write_full_song"])
        if "write_stems" in exports:
            export_config.write_stems = bool(exports["write_stems"])
        if "write_sections" in exports:
            export_config.write_sections = bool(exports["write_sections"])
        if "write_patterns" in exports:
            export_config.write_patterns = bool(exports["write_patterns"])
        if "write_index" in exports:
            export_config.write_index = bool(exports["write_index"])
        if "write_analysis" in exports:
            export_config.write_analysis = bool(exports["write_analysis"])
        if "write_grids" in exports:
            export_config.write_grids = bool(exports["write_grids"])

    return export_config


# Helper to read timeline text-dump export settings from cfg.raw.
def _get_textdump_settings(cfg: RootConfig) -> tuple[bool, list[str], int]:
    """Return (enabled, views, subdiv) for timeline text dumps.

    Reads from cfg.raw using this shape:

    exports:
      midi_text:
        enabled: true
        views: [events, grid]
        subdiv: 16

    Defaults are disabled.
    """
    raw = getattr(cfg, "raw", None) or {}
    exports = raw.get("exports") if isinstance(raw, dict) else None
    midi_text = None
    if isinstance(exports, dict):
        midi_text = exports.get("midi_text")

    if not isinstance(midi_text, dict):
        return (False, ["events", "grid", "tab"], 16)

    enabled = bool(midi_text.get("enabled", False))
    views = midi_text.get("views", ["events", "grid", "tab"])
    if not isinstance(views, list) or not all(isinstance(v, str) for v in views):
        views = ["events", "grid", "tab"]

    try:
        subdiv = int(midi_text.get("subdiv", 16))
    except Exception:
        subdiv = 16
    subdiv = 8 if subdiv <= 0 else subdiv

    return (enabled, views, subdiv)


def export_all(
    *,
    cfg: RootConfig,
    export_sections: bool,
    export_patterns: bool,
    sections_absolute_timing: bool,
    instruments_used: list[str],
    timelines: dict[str, InstrumentTimeline],
    plan: "BuildPlan",
    logger: logging.Logger,
) -> Path:
    """Write all exports for a build based on export flags.

    This function is invoked after timelines have been fully rendered. It
    creates the per-run export directory and then writes, in order:

      1) Full multi-track song MIDI (root)
      2) Full-length per-instrument stem MIDIs (`instruments/<inst>/`)
      3) Optional per-section MIDIs (`instruments/<inst>/sections/`)
      4) Optional pattern MIDIs + per-instrument sequencer YAML
      5) Optional export index (index.yaml + QUICKREF.txt)

    Naming:
      - Uses the effective song name from config and sanitizes it for file paths.
      - Falls back to "produzre" when no title is provided.

    Inputs:
      - `instruments_used` controls deterministic ordering.
      - `timelines` is filtered down to those instruments only.
      - Section windows are taken from `plan.section_timings`.

    Args:
        cfg: Parsed root configuration.
        export_sections: Whether to write per-section MIDI clips.
        export_patterns: Whether to write unique patterns + sequence YAML.
        sections_absolute_timing: If True, section MIDI exports retain song-
            relative timing; otherwise they are re-based to start at beat 0.
        instruments_used: Ordered list of instrument keys to export.
        timelines: Mapping of instrument name -> full-song InstrumentTimeline.
        plan: BuildPlan containing section timing windows.
        logger: Logger for status output.

    Returns:
        Path: The per-run export root directory.

    Notes:
        - This function always writes the full song MIDI and per-instrument stems.
          Sections/patterns are controlled by flags.
        - Empty timelines will still produce valid MIDI containers (tempo/name only).
        - ExportConfig can be customized via cfg.raw.exports block.
    """
    # Read export configuration from config (with DAW defaults)
    export_config = _get_export_config(cfg)

    # CLI flags override config settings for backward compatibility
    if not export_sections:
        export_config.write_sections = False
    if not export_patterns:
        export_config.write_patterns = False

    song_name = sanitize_song_name(cfg.get_effective_song_name(), fallback="produzre")
    paths = create_run_export_dir(
        exports_root=cfg.song.exports_root,
        song_name=song_name,
        logger=logger,
    )
    export_root = paths.root
    instruments_dir = paths.instruments_dir

    timelines_by_name = {name: timelines[name] for name in instruments_used}

    # Filter out planning-only engines (e.g., harmony produces no musical
    # MIDI events — it only contributes a chord plan for other engines).
    # These are identified by having "planning" in their engine roles.
    planning_only = set()
    for name in instruments_used:
        engine = cfg.engines.get(name)
        if engine and "planning" in engine.roles:
            planning_only.add(name)
    if planning_only:
        instruments_used = [n for n in instruments_used if n not in planning_only]
        timelines_by_name = {n: timelines_by_name[n] for n in instruments_used}
    section_timings = list(plan.section_timings)

    # Full song MIDI (always written unless explicitly disabled)
    if export_config.write_full_song:
        write_full_song_midi(
            cfg=cfg,
            song_name=song_name,
            export_root=export_root,
            instruments_used=instruments_used,
            timelines=timelines_by_name,
            logger=logger,
        )

    # Per-instrument stems
    if export_config.write_stems:
        write_instrument_stems(
            cfg=cfg,
            song_name=song_name,
            instruments_dir=instruments_dir,
            instruments_used=instruments_used,
            timelines=timelines_by_name,
            logger=logger,
        )

    # Per-section MIDIs
    if export_config.write_sections:
        write_section_midis(
            cfg=cfg,
            song_name=song_name,
            instruments_dir=instruments_dir,
            instruments_used=instruments_used,
            timelines=timelines_by_name,
            section_timings=section_timings,
            absolute_timing=sections_absolute_timing,
            logger=logger,
        )
    else:
        logger.info("Section exports disabled; skipping per-section MIDIs.")

    # Pattern MIDIs + sequence.yaml
    if export_config.write_patterns:
        write_patterns_and_sequences(
            cfg=cfg,
            song_name=song_name,
            instruments_dir=instruments_dir,
            instruments_used=instruments_used,
            timelines=timelines_by_name,
            section_timings=section_timings,
            logger=logger,
        )
    else:
        logger.info("Pattern exports disabled; skipping pattern MIDIs and sequencer YAML.")

    # Optional: timeline-based text dumps (events TSV + ASCII grid) for debugging and review.
    textdump_enabled, textdump_views, textdump_subdiv = _get_textdump_settings(cfg)

    # Merge textdump settings with export_config
    if export_config.write_analysis or textdump_enabled:
        try:
            from ..export.textdump import write_timeline_text_dumps

            analysis_dir = export_root / "analysis"
            write_timeline_text_dumps(
                cfg=cfg,
                song_name=song_name,
                analysis_dir=analysis_dir,
                instruments_used=instruments_used,
                timelines=timelines_by_name,
                section_timings=section_timings,
                views=textdump_views,
                subdiv=textdump_subdiv,
                logger=logger,
            )
        except Exception as e:
            logger.exception("Text dump export failed: %s", e)
    else:
        logger.info("Text dump exports disabled; skipping analysis text outputs.")

    # Generate export index (DAW workflow documentation)
    if export_config.write_index:
        try:
            index_path = generate_export_index(
                cfg=cfg,
                export_root=export_root,
                section_timings=section_timings,
                instruments_used=instruments_used,
                export_config=export_config,
                song_name=song_name,
            )
            logger.info(f"Generated export index: {index_path.name}")

            quickref_path = generate_quick_reference(
                cfg=cfg,
                export_root=export_root,
                section_timings=section_timings,
            )
            logger.info(f"Generated quick reference: {quickref_path.name}")
        except Exception as e:
            logger.exception("Export index generation failed: %s", e)

    logger.info("MIDI export complete.")
    return export_root
