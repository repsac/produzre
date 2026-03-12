"""Export index generation for DAW-friendly documentation.

This module generates a song-named YAML file at the export root that documents:
- Song metadata (title, tempo, key, etc.)
- Section timing map (bar numbers, timestamps)
- File inventory (stems, sections, patterns)
- Pattern-to-section mappings for DAW workflow
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import yaml

from ..model import RootConfig
from ..timeline import SectionTiming
from .config import ExportConfig, create_export_metadata


def generate_export_index(
    cfg: RootConfig,
    export_root: Path,
    section_timings: List[SectionTiming],
    instruments_used: List[str],
    export_config: Optional[ExportConfig] = None,
    song_name: Optional[str] = None,
) -> Path:
    """Generate an export metadata YAML named after the song.

    Args:
        cfg: Song configuration
        export_root: Export root directory
        section_timings: List of section timing info
        instruments_used: List of instrument names that were rendered
        export_config: Export configuration (uses DAW default if None)
        song_name: Sanitized song name for the filename (falls back to cfg)

    Returns:
        Path to the generated YAML file
    """
    if export_config is None:
        export_config = ExportConfig.from_mode("daw")

    # Build index structure
    index = create_export_metadata(
        song_title=cfg.song.title,
        bpm=cfg.song.bpm,
        key=cfg.song.key,
        mode=cfg.song.mode,
        meter=cfg.song.meter,
        seed=cfg.song.seed if export_config.include_seed_in_metadata else None,
        config=export_config,
    )

    # Add arrangement info
    index["arrangement"] = {
        "sections": cfg.arrangement,
        "total_sections": len(cfg.arrangement),
    }

    # Add section timing map
    sections_map = {}
    for st in section_timings:
        section_config = cfg.sections.get(st.id)
        section_type = section_config.type if section_config else "unknown"

        sections_map[st.id] = {
            "type": section_type,
            "start_beat": float(st.start_beat),
            "end_beat": float(st.end_beat),
            "length_beats": float(st.length_beats),
            "start_bar": int(st.start_beat / cfg.song.beats_per_bar) + 1,
            "length_bars": int(st.length_beats / cfg.song.beats_per_bar),
        }

        # Add timestamp if useful for DAW sync
        start_seconds = st.start_beat * (60.0 / cfg.song.bpm)
        end_seconds = st.end_beat * (60.0 / cfg.song.bpm)
        sections_map[st.id]["start_time"] = f"{int(start_seconds // 60)}:{int(start_seconds % 60):02d}"
        sections_map[st.id]["end_time"] = f"{int(end_seconds // 60)}:{int(end_seconds % 60):02d}"

    index["sections"] = sections_map

    # Add instruments info
    index["instruments"] = {
        "used": instruments_used,
        "count": len(instruments_used),
    }

    # Add file inventory
    files = {
        "full_song": f"{cfg.get_effective_song_name()}.mid",
        "stems": [],
        "sections": {},
        "patterns": {},
    }

    # List stems
    if export_config.write_stems:
        for inst in instruments_used:
            files["stems"].append(f"instruments/{inst}/{cfg.get_effective_song_name()}_{inst}.mid")

    # List sections
    if export_config.write_sections:
        for inst in instruments_used:
            files["sections"][inst] = []
            for section_id in cfg.arrangement:
                files["sections"][inst].append(
                    f"instruments/{inst}/sections/{cfg.get_effective_song_name()}_{inst}_{section_id}.mid"
                )

    # Note about patterns (actual pattern files would be discovered dynamically)
    if export_config.write_patterns:
        files["patterns"] = {
            "note": "Pattern files are organized by instrument with sequence.yaml for each",
            "location": "instruments/<instrument>/patterns/",
        }

    index["files"] = files

    # Write song-named YAML (e.g., "Blues_Rock_Showcase.yaml")
    base = song_name or cfg.get_effective_song_name()
    index_path = export_root / f"{base}.yaml"
    with open(index_path, "w") as f:
        yaml.dump(index, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return index_path


def generate_quick_reference(
    cfg: RootConfig,
    export_root: Path,
    section_timings: List[SectionTiming],
) -> Path:
    """Generate a quick reference text file for DAW import.

    This creates a simple text file with bar numbers and section names
    that can be easily copied into DAW markers.

    Args:
        cfg: Song configuration
        export_root: Export root directory
        section_timings: List of section timing info

    Returns:
        Path to the generated QUICKREF.txt file
    """
    quickref_path = export_root / "QUICKREF.txt"

    lines = [
        f"Quick Reference: {cfg.song.title}",
        f"Tempo: {cfg.song.bpm} BPM",
        f"Key: {cfg.song.key} {cfg.song.mode}",
        f"Time: {cfg.song.meter}",
        "",
        "Section Markers (for DAW):",
        "=" * 50,
        "",
    ]

    for st in section_timings:
        section_config = cfg.sections.get(st.id)
        section_type = section_config.type if section_config else "unknown"
        start_bar = int(st.start_beat / cfg.song.beats_per_bar) + 1
        length_bars = int(st.length_beats / cfg.song.beats_per_bar)

        lines.append(f"Bar {start_bar:3d} | {st.id:20s} | {section_type:10s} | {length_bars} bars")

    lines.extend([
        "",
        "=" * 50,
        "",
        "Files Generated:",
        f"- Full song: {cfg.get_effective_song_name()}.mid",
        "- Stems: instruments/<instrument>/<song>_<instrument>.mid",
        "- Sections: instruments/<instrument>/sections/<song>_<instrument>_<section>.mid",
        "- Patterns: instruments/<instrument>/patterns/p*.mid",
        "- Sequence: instruments/<instrument>/sequence.yaml",
        "",
        "Import Workflow:",
        "1. Import full song MIDI for reference",
        "2. Import individual stems for mixing",
        "3. Use section clips for arrangement edits",
        "4. Use patterns + sequence.yaml for pattern-based workflow",
    ])

    with open(quickref_path, "w") as f:
        f.write("\n".join(lines))

    return quickref_path
