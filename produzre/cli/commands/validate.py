"""CLI command for validating song YAML configuration."""

from __future__ import annotations
import sys
from pathlib import Path

from ...config.load import load_yaml_file
from ...config.validation import validate_song_config, format_validation_report
from ...config.errors import ConfigError


def validate_command(
    yaml_path: str,
    strict: bool = False,
    quiet: bool = False,
) -> int:
    """Validate a song YAML file without building it.

    Args:
        yaml_path: Path to the YAML file to validate
        strict: Treat warnings as errors
        quiet: Suppress success message

    Returns:
        Exit code (0 = success, 1 = errors found)
    """
    path = Path(yaml_path)

    if not path.exists():
        print(f"Error: File not found: {yaml_path}", file=sys.stderr)
        return 1

    try:
        # Load the YAML file
        config = load_yaml_file(path)

        # Validate
        errors, warnings = validate_song_config(config, strict=strict)

        # In strict mode, warnings become errors
        if strict and warnings:
            errors.extend(warnings)
            warnings = []

        # Format and print report
        if errors or warnings:
            report = format_validation_report(errors, warnings)
            print(report)

        if errors:
            print(f"\n✗ Validation failed with {len(errors)} error(s)", file=sys.stderr)
            return 1
        elif warnings:
            print(f"\n⚠ Validation passed with {len(warnings)} warning(s)")
            if not quiet:
                print(f"✓ {yaml_path} is valid (with warnings)")
            return 0
        else:
            if not quiet:
                print(f"✓ {yaml_path} is valid")
            return 0

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def explain_command(
    yaml_path: str,
) -> int:
    """Explain what a song YAML configuration will do.

    Args:
        yaml_path: Path to the YAML file to explain

    Returns:
        Exit code (0 = success, 1 = error)
    """
    path = Path(yaml_path)

    if not path.exists():
        print(f"Error: File not found: {yaml_path}", file=sys.stderr)
        return 1

    try:
        # Load the YAML file
        config = load_yaml_file(path)

        print(f"=== Explanation for {path.name} ===\n")

        # Song metadata
        song = config.get("song", {})
        if song:
            print("Song Configuration:")
            print(f"  Title: {song.get('title', 'Untitled')}")
            print(f"  Tempo: {song.get('bpm', 120)} BPM")
            print(f"  Key: {song.get('key', 'C')} {song.get('mode', 'major')}")
            print(f"  Time signature: {song.get('meter', '4/4')}")
            if 'seed' in song:
                print(f"  Random seed: {song['seed']} (deterministic)")
            print()

        # Instruments
        instruments = config.get("instruments", {})
        if instruments:
            print("Configured Instruments:")
            for inst_name, inst_config in instruments.items():
                if isinstance(inst_config, dict):
                    params = inst_config.get("params", {})
                    if params:
                        print(f"  {inst_name}:")
                        for key, value in params.items():
                            print(f"    - {key}: {value}")
            print()

        # Sections
        sections = config.get("sections", {})
        if sections:
            print(f"Sections ({len(sections)} total):")
            for section_id, section_config in sections.items():
                if isinstance(section_config, dict):
                    section_type = section_config.get("type", "unknown")
                    bars = section_config.get("bars", "?")
                    print(f"  {section_id} ({section_type}, {bars} bars)")

                    # Harmony
                    harmony = section_config.get("harmony", {})
                    if isinstance(harmony, dict):
                        progression = harmony.get("progression", [])
                        if progression:
                            prog_str = " - ".join(progression)
                            print(f"    Chords: {prog_str}")

                    # Instrument overrides
                    section_instruments = section_config.get("instruments", {})
                    if section_instruments:
                        for inst_name, inst_config in section_instruments.items():
                            if isinstance(inst_config, dict):
                                params = inst_config.get("params", {})
                                if params:
                                    print(f"    {inst_name} overrides: {dict(params)}")
            print()

        # Arrangement
        arrangement = config.get("arrangement", [])
        if arrangement:
            print(f"Arrangement ({len(arrangement)} sections):")
            print(f"  {' → '.join(arrangement)}")
            print()

        print("✓ Explanation complete")
        return 0

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
