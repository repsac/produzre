"""Export configuration and preset modes for DAW-friendly workflows.

This module defines export preset modes that control which files are generated
and how they are named/organized for optimal DAW integration.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ExportMode(Enum):
    """Export preset modes for different workflows."""

    DAW = "daw"           # Full export optimized for DAW workflow (default)
    MINIMAL = "minimal"   # Minimal export (full song MIDI only)
    DEBUG = "debug"       # Debug export (includes analysis files, grids, TSV)
    CUSTOM = "custom"     # Custom export (user-defined settings)


@dataclass
class ExportConfig:
    """Configuration for export behavior and file generation.

    Attributes:
        mode: Export preset mode (daw, minimal, debug, custom)

        # File generation flags
        write_full_song: Generate full song MIDI
        write_stems: Generate per-instrument stem MIDIs
        write_sections: Generate per-section clip MIDIs
        write_patterns: Generate pattern library + sequence YAML
        write_index: Generate export index YAML with metadata
        write_analysis: Generate analysis TSV files
        write_grids: Generate text grid visualizations

        # Naming options
        include_meter_in_names: Include time signature in pattern names
        include_length_in_names: Include bar length in pattern names
        include_role_in_names: Include instrument role tags
        timestamp_format: Timestamp format for run directories

        # Organization
        group_by_instrument: Group files by instrument (vs by type)
        flatten_structure: Use flat directory structure

        # Metadata
        include_seed_in_metadata: Include RNG seed in metadata
        include_build_info: Include build timestamp and version
    """

    mode: ExportMode = ExportMode.DAW

    # File generation flags
    write_full_song: bool = True
    write_stems: bool = True
    write_sections: bool = True
    write_patterns: bool = True
    write_index: bool = True
    write_analysis: bool = False
    write_grids: bool = False

    # Naming options
    include_meter_in_names: bool = True
    include_length_in_names: bool = True
    include_role_in_names: bool = False
    timestamp_format: str = "%Y%m%d_%H%M%S"

    # Organization
    group_by_instrument: bool = True  # instruments/drums/ vs patterns/p001/
    flatten_structure: bool = False

    # Metadata
    include_seed_in_metadata: bool = True
    include_build_info: bool = True

    @classmethod
    def from_mode(cls, mode: str = "daw") -> ExportConfig:
        """Create an ExportConfig from a preset mode name.

        Args:
            mode: Mode name ("daw", "minimal", "debug", or "custom")

        Returns:
            ExportConfig with preset applied
        """
        try:
            export_mode = ExportMode(mode.lower())
        except ValueError:
            export_mode = ExportMode.DAW

        if export_mode == ExportMode.MINIMAL:
            return cls(
                mode=export_mode,
                write_full_song=True,
                write_stems=False,
                write_sections=False,
                write_patterns=False,
                write_index=False,
                write_analysis=False,
                write_grids=False,
            )
        elif export_mode == ExportMode.DEBUG:
            return cls(
                mode=export_mode,
                write_full_song=True,
                write_stems=True,
                write_sections=True,
                write_patterns=True,
                write_index=True,
                write_analysis=True,
                write_grids=True,
                include_seed_in_metadata=True,
                include_build_info=True,
            )
        elif export_mode == ExportMode.DAW:
            return cls(
                mode=export_mode,
                write_full_song=True,
                write_stems=True,
                write_sections=True,
                write_patterns=True,
                write_index=True,
                write_analysis=False,
                write_grids=False,
                include_meter_in_names=True,
                include_length_in_names=True,
            )
        else:  # CUSTOM
            return cls(mode=export_mode)

    def should_write_file(self, file_type: str) -> bool:
        """Check if a file type should be written based on config.

        Args:
            file_type: Type of file ("full_song", "stems", "sections",
                      "patterns", "index", "analysis", "grids")

        Returns:
            True if file type should be written
        """
        file_type_lower = file_type.lower()

        if file_type_lower in ("full", "full_song", "song"):
            return self.write_full_song
        elif file_type_lower in ("stem", "stems", "instruments"):
            return self.write_stems
        elif file_type_lower in ("section", "sections", "clips"):
            return self.write_sections
        elif file_type_lower in ("pattern", "patterns", "library"):
            return self.write_patterns
        elif file_type_lower in ("index", "metadata"):
            return self.write_index
        elif file_type_lower in ("analysis", "tsv"):
            return self.write_analysis
        elif file_type_lower in ("grid", "grids", "visualization"):
            return self.write_grids
        else:
            return True  # Unknown types default to enabled


def format_pattern_name(
    instrument: str,
    pattern_id: str,
    meter: Optional[str] = None,
    length_bars: Optional[int] = None,
    role: Optional[str] = None,
    config: Optional[ExportConfig] = None,
) -> str:
    """Format a pattern filename according to export config.

    Args:
        instrument: Instrument name (e.g., "drums", "bass")
        pattern_id: Pattern identifier (e.g., "p001", "p002")
        meter: Time signature (e.g., "4/4")
        length_bars: Pattern length in bars
        role: Instrument role tag (e.g., "groove", "fill", "lead")
        config: Export configuration (uses DAW defaults if None)

    Returns:
        Formatted pattern filename (without extension)

    Examples:
        >>> format_pattern_name("drums", "p001", "4/4", 1)
        'drums_p001_4-4_1bar'
        >>> format_pattern_name("bass", "p002", role="groove")
        'bass_p002_groove'
    """
    if config is None:
        config = ExportConfig.from_mode("daw")

    parts = [instrument, pattern_id]

    if config.include_meter_in_names and meter:
        # Convert "4/4" to "4-4" for filename safety
        meter_safe = meter.replace("/", "-")
        parts.append(meter_safe)

    if config.include_length_in_names and length_bars:
        bar_label = f"{length_bars}bar" if length_bars == 1 else f"{length_bars}bars"
        parts.append(bar_label)

    if config.include_role_in_names and role:
        parts.append(role)

    return "_".join(parts)


def create_export_metadata(
    song_title: str,
    bpm: float,
    key: str,
    mode: str,
    meter: str,
    seed: Optional[int] = None,
    config: Optional[ExportConfig] = None,
) -> dict:
    """Create export metadata dictionary.

    Args:
        song_title: Song title
        bpm: Tempo
        key: Key signature
        mode: Mode (major, minor, etc.)
        meter: Time signature
        seed: Random seed (if applicable)
        config: Export configuration

    Returns:
        Metadata dictionary ready for YAML export
    """
    if config is None:
        config = ExportConfig.from_mode("daw")

    metadata = {
        "song": {
            "title": song_title,
            "bpm": bpm,
            "key": key,
            "mode": mode,
            "meter": meter,
        },
        "export": {
            "mode": config.mode.value,
        },
    }

    if config.include_seed_in_metadata and seed is not None:
        metadata["song"]["seed"] = seed

    if config.include_build_info:
        from datetime import datetime, timezone
        metadata["build"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "generator": "Produzre",
        }

    return metadata
