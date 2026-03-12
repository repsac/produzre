from __future__ import annotations

"""CLI command handlers for song-level operations.

This module implements the `produzre song ...` command family:

- validate: sanity-check a parsed `RootConfig`.
- show-config: print the effective configuration after parsing/normalization.
- build: invoke orchestration to plan and/or render MIDI exports.

The handlers here are intentionally thin: they configure logging, format output,
and delegate real work to the configuration loader and orchestration layers.
"""

import copy
import json
import yaml

from ...logging_setup import configure_logging
from ...model import RootConfig
from ...orchestrate.build import build_song
from ...orchestrate.plan import plan_song
from ...orchestrate.transitions import (
    build_section_transitions_map,
    serialize_section_transitions_map,
)


def cmd_validate(cfg: RootConfig) -> int:
    """CLI handler: validate a loaded RootConfig.

    This command is intended as a fast sanity check that a YAML configuration
    has been parsed correctly and produces a coherent in-memory `RootConfig`.

    Current behavior:
      - Configures verbose console logging (no log file).
      - Logs key, mode, meter, arrangement, section IDs, and derived
        `effective_song_name`.
      - Runs enhanced validation with helpful suggestions for common errors.
      - Does not write any MIDI files.

    Args:
        cfg: The fully parsed configuration object to validate.

    Returns:
        Process-style exit code (0 for success, 1 for warnings).
    """
    logger = configure_logging(verbose=True, log_file=None)
    logger.info("Config version: %s", cfg.version)
    logger.info("Song title: %s", cfg.song.title)
    logger.info("Effective song name: %s", cfg.get_effective_song_name())
    logger.info("Sections: %s", list(cfg.sections.keys()))
    logger.info("Arrangement: %s", cfg.arrangement)

    # Run enhanced validation (Option A - Phase 2)
    try:
        from ...config.validation import validate_section_config

        warnings = []
        for section_id, section in cfg.sections.items():
            # Convert section to dict-like structure for validation
            section_dict = {
                "type": section.type,
                "bars": section.bars,
                "instruments": {},
            }

            # Build instruments dict from section config
            for inst_name in ["drums", "bass", "rhythm_gtr", "lead_gtr", "harmony"]:
                inst_cfg = section.instruments.get(inst_name)
                if inst_cfg:
                    inst_dict = {}
                    if hasattr(inst_cfg, "params") and inst_cfg.params:
                        inst_dict["params"] = dict(inst_cfg.params) if not isinstance(inst_cfg.params, dict) else inst_cfg.params
                    if hasattr(inst_cfg, "extra") and inst_cfg.extra:
                        inst_dict["extra"] = dict(inst_cfg.extra) if not isinstance(inst_cfg.extra, dict) else inst_cfg.extra
                    section_dict["instruments"][inst_name] = inst_dict

            section_warnings = validate_section_config(section_id, section_dict, strict=False)
            warnings.extend(section_warnings)

        if warnings:
            logger.warning("\n=== Configuration Warnings ===")
            for warning in warnings:
                logger.warning(warning)
            logger.info("\n✓ Validation complete with %d warning(s)", len(warnings))
            return 1  # Non-zero to indicate warnings
        else:
            logger.info("✓ Validation OK - no warnings")
            return 0

    except Exception as e:
        logger.debug("Enhanced validation not available: %s", e)
        logger.info("Validation OK.")
        return 0


def cmd_show_config(cfg: RootConfig, fmt: str) -> int:
    """CLI handler: print the effective configuration to stdout.

    Produzre supports both YAML config input and CLI overrides; this command
    prints the *effective* configuration after parsing and normalization so a
    user can confirm exactly what will be used during a build.

    Output contents:
      - Top-level version
      - Song settings (including derived `effective_song_name`)
      - Runtime metadata (project name and effective seed) when available
      - Fully expanded section definitions, including per-instrument settings
      - Final arrangement list

    Args:
        cfg: Parsed `RootConfig` to render.
        fmt: Output format. Expected values are "json" or "yaml".

    Returns:
        Process-style exit code (0 for success).
    """
    logger = configure_logging(verbose=True, log_file=None)
    logger.info("Loaded config; printing effective configuration (%s)...", fmt)

    data = {
        "version": cfg.version,
        "song": {
            "title": cfg.song.title,
            "bpm": cfg.song.bpm,
            "key": cfg.song.key,
            "mode": cfg.song.mode,
            "meter": cfg.song.meter,
            "project": getattr(cfg.song, "project", None),
            "beats_per_bar": cfg.song.beats_per_bar,
            "pattern_bars": cfg.song.pattern_bars,
            "seed": cfg.song.seed,
            "variation": cfg.song.variation,
            "humanize_velocity": cfg.song.humanize_velocity,
            "humanize_timing": cfg.song.humanize_timing,
            "exports_root": cfg.song.exports_root,
            "effective_song_name": cfg.get_effective_song_name(),
            "params": {
                "transitions": {
                    "enabled": cfg.song.transitions.enabled,
                    "strength": cfg.song.transitions.strength,
                    "ramp_bars": cfg.song.transitions.ramp_bars,
                    "pickup_rate": cfg.song.transitions.pickup_rate,
                    "turnaround_rate": cfg.song.transitions.turnaround_rate,
                    "bridge_start_bars": cfg.song.transitions.bridge_start_bars,
                    "debug": cfg.song.transitions.debug,
                }
            },
        },
        "runtime": (
            {
                "project_name": cfg.runtime.project_name if cfg.runtime else None,
                "song_seed": cfg.runtime.song_seed if cfg.runtime else None,
                "effective_seed": cfg.runtime.effective_seed if cfg.runtime else None,
                "projects_registry_path": cfg.runtime.projects_registry_path if cfg.runtime else None,
            }
            if getattr(cfg, "runtime", None)
            else None
        ),
        "sections": {
            sid: {
                "type": s.type,
                "bars": s.bars,
                "beats": s.beats,
                "meter": s.meter,
                "key": s.key,
                "mode": s.mode,
                "harmony": (
                    {
                        "progression": s.harmony.progression,
                        "chord_rate": s.harmony.chord_rate,
                        "extra": s.harmony.extra,
                    }
                    if s.harmony
                    else None
                ),
                "instruments": {
                    iname: {
                        "enabled": ic.enabled,
                        "intensity": ic.intensity,
                        "style_bias": ic.style_bias,
                        "offset_beats": ic.offset_beats,
                        "seed": ic.seed,
                        "variation": ic.variation,
                        "groove": ic.groove,
                        "voicing": ic.voicing,
                        "register": ic.register,
                        "role": ic.role,
                        "patterns": ic.patterns,
                        "solo": ic.solo,
                        "humanize_velocity": ic.humanize_velocity,
                        "humanize_timing": ic.humanize_timing,
                        "params": (
                            {
                                "transitions": {
                                    "enabled": ic.transitions.enabled,
                                    "strength": ic.transitions.strength,
                                    "ramp_bars": ic.transitions.ramp_bars,
                                    "pickup_rate": ic.transitions.pickup_rate,
                                    "turnaround_rate": ic.transitions.turnaround_rate,
                                    "bridge_start_bars": ic.transitions.bridge_start_bars,
                                    "debug": ic.transitions.debug,
                                }
                            }
                            if ic.transitions
                            else None
                        ),
                        "extra": ic.extra,
                    }
                    for iname, ic in s.instruments.items()
                },
                "extras": s.extras,
            }
            for sid, s in cfg.sections.items()
        },
        "arrangement": cfg.arrangement,
        "engines": {
            ename: {
                "module_path": eng.module_path,
                "priority": eng.priority,
                "channel": eng.channel,
                "program": eng.program,
                "enabled": eng.enabled,
                "requires": eng.requires,
                "provides": eng.provides,
                "roles": eng.roles,
            }
            for ename, eng in cfg.engines.items()
        },
    }

    # Phase P1: surface persona/effective debug metadata when present.
    personas = getattr(cfg, "_personas", None)
    effective = getattr(cfg, "_effective", None)

    # Fallback: these may also exist in cfg.raw if the model did not allow setattr.
    if personas is None and isinstance(getattr(cfg, "raw", None), dict):
        personas = cfg.raw.get("_personas")
    if effective is None and isinstance(getattr(cfg, "raw", None), dict):
        effective = cfg.raw.get("_effective")

    if personas is not None:
        data["_personas"] = personas
    if effective is not None:
        data["_effective"] = effective

    # Phase N5: Add section-level transitions map (lookahead directives)
    try:
        # Plan the song to get BuildPlan with planned sections
        build_plan = plan_song(cfg=cfg, logger=logger)

        # Build transitions map from planned sections
        transitions_map = build_section_transitions_map(
            build_plan.planned_sections,
            logger=logger,
        )

        # Serialize for output
        serialized_transitions = serialize_section_transitions_map(transitions_map)
        data["_transitions"] = serialized_transitions

        logger.debug(f"Added transitions map with {len(transitions_map)} section directives")
    except Exception as e:
        logger.debug(f"Could not compute transitions map: {e}")
        # Don't fail show-config if transitions can't be computed

    # Optional: per-section merged view that resolves instrument defaults + section overrides.
    # This is musician-friendly because it shows what will actually be used per section,
    # without requiring users to mentally merge `_effective` + `sections.*.instruments.*.extra`.
    def _deep_merge(base: dict, override: dict) -> dict:
        out = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    if isinstance(effective, dict) and isinstance(effective.get("instruments"), dict):
        base_instruments = effective.get("instruments", {})
        sections_effective: dict = {}
        for sid, sdata in data.get("sections", {}).items():
            insts = sdata.get("instruments", {})
            merged_insts: dict = {}
            for iname, icfg in insts.items():
                base_cfg = base_instruments.get(iname, {}) if isinstance(base_instruments, dict) else {}
                # Section overrides are stored under `extra` (engine-facing overrides), so merge those.
                extra_cfg = icfg.get("extra", {}) if isinstance(icfg, dict) else {}
                if isinstance(base_cfg, dict) and isinstance(extra_cfg, dict):
                    merged = _deep_merge(base_cfg, extra_cfg)
                else:
                    merged = base_cfg or extra_cfg
                merged_insts[iname] = merged
            sections_effective[sid] = {"instruments": merged_insts}

        data["_sections_effective"] = sections_effective

    if fmt == "json":
        print(json.dumps(data, indent=2))
    else:  # yaml
        # Avoid YAML anchors/aliases to keep output musician-friendly.
        # Shared references can occur when we reuse dict objects across sections.
        class _NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, _data):  # type: ignore[override]
                return True

        payload = copy.deepcopy(data)
        print(
            yaml.dump(
                payload,
                sort_keys=False,
                allow_unicode=True,
                Dumper=_NoAliasDumper,
            )
        )
    return 0


def cmd_build(
    cfg: RootConfig,
    dry_run: bool,
    verbose: bool,
    export_sections: bool,
    export_patterns: bool,
    sections_absolute_timing: bool,
    strict_determinism: bool = False,
) -> int:
    """CLI handler: build a song (or run a dry-run plan) from a RootConfig.

    This is the main entry point for producing MIDI exports.

    Behavior:
      - Configures logging according to `verbose` (console only here).
      - Delegates orchestration to `produzre.orchestrate.build.build_song`.
      - Supports dry-run mode which performs planning/logging but does not write
        MIDI files.
      - Controlled exports:
          - `export_sections`: write per-section MIDI slices.
          - `export_patterns`: write per-pattern MIDI files and per-instrument
            `sequence.yaml`.
          - `sections_absolute_timing`: choose whether section MIDIs are
            song-relative (absolute) or section-relative (start at beat 0).
      - Strict determinism mode:
          - Builds the song twice and compares MIDI outputs byte-for-byte.
          - Useful for regression testing and verifying RNG consistency.

    Args:
        cfg: Parsed configuration.
        dry_run: If True, plan/log only (no files).
        verbose: If True, enable debug-level logging.
        export_sections: If True, export per-section MIDI files.
        export_patterns: If True, export repeating patterns + sequence YAML.
        sections_absolute_timing: If True, keep section MIDI note times aligned
            to the full song timeline.
        strict_determinism: If True, verify determinism by building twice
            and comparing MIDI hashes.

    Returns:
        Process-style exit code (0 for success, 1 for determinism failure).
    """
    logger = configure_logging(verbose=verbose, log_file=None)

    # First build
    result_1 = build_song(
        cfg=cfg,
        dry_run=dry_run,
        export_sections=export_sections,
        export_patterns=export_patterns,
        sections_absolute_timing=sections_absolute_timing,
        logger=logger,
    )

    # If strict determinism mode, build again and compare
    if strict_determinism and not dry_run:
        logger.info("\n=== Strict Determinism Check ===")
        logger.info("Building song a second time to verify deterministic output...")

        import hashlib
        from pathlib import Path

        # Collect MIDI files from first build
        export_root_1 = Path(result_1.export_root) if result_1.export_root else None
        if not export_root_1:
            logger.error("No export root found for first build")
            return 1

        midi_files_1 = sorted(export_root_1.rglob("*.mid"))
        if not midi_files_1:
            logger.error("No MIDI files found in first build")
            return 1

        # Build hash map for first build
        hash_map_1 = {}
        for midi_file in midi_files_1:
            rel_path = midi_file.relative_to(export_root_1)
            with open(midi_file, "rb") as f:
                hash_map_1[str(rel_path)] = hashlib.sha256(f.read()).hexdigest()

        # Second build
        result_2 = build_song(
            cfg=cfg,
            dry_run=dry_run,
            export_sections=export_sections,
            export_patterns=export_patterns,
            sections_absolute_timing=sections_absolute_timing,
            logger=logger,
        )

        # Collect MIDI files from second build
        export_root_2 = Path(result_2.export_root) if result_2.export_root else None
        if not export_root_2:
            logger.error("No export root found for second build")
            return 1

        midi_files_2 = sorted(export_root_2.rglob("*.mid"))

        # Build hash map for second build
        hash_map_2 = {}
        for midi_file in midi_files_2:
            rel_path = midi_file.relative_to(export_root_2)
            with open(midi_file, "rb") as f:
                hash_map_2[str(rel_path)] = hashlib.sha256(f.read()).hexdigest()

        # Compare file counts
        if len(hash_map_1) != len(hash_map_2):
            logger.error(
                f"Different number of MIDI files: {len(hash_map_1)} vs {len(hash_map_2)}"
            )
            return 1

        # Compare hashes
        differences = []
        for rel_path, hash_1 in hash_map_1.items():
            if rel_path not in hash_map_2:
                differences.append(f"Missing in build 2: {rel_path}")
                continue

            hash_2 = hash_map_2[rel_path]
            if hash_1 != hash_2:
                differences.append(
                    f"Hash mismatch for {rel_path}:\n"
                    f"  Build 1: {hash_1}\n"
                    f"  Build 2: {hash_2}"
                )

        for rel_path in hash_map_2:
            if rel_path not in hash_map_1:
                differences.append(f"Missing in build 1: {rel_path}")

        if differences:
            logger.error("\n=== Determinism Check FAILED ===")
            logger.error(f"Found {len(differences)} difference(s):")
            for diff in differences:
                logger.error(diff)
            logger.error("\nBuilds with same seed produced different MIDI outputs!")
            return 1
        else:
            logger.info(f"\n✓ Determinism check PASSED - {len(hash_map_1)} MIDI files are byte-identical")
            logger.info("Build 1: %s", export_root_1)
            logger.info("Build 2: %s", export_root_2)

    return 0
