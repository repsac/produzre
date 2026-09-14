"""Enhanced YAML validation with helpful error messages and suggestions.

This module provides musician-friendly validation for Produzre configuration files,
including "Did you mean?" suggestions for common typos and misconfigurations.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
import difflib


# Accepted public keys. Engine defaults may depend on section type or recipe.
KNOWN_ROOT_KEYS = {"version", "song", "sections", "arrangement", "instruments", "engines", "exports", "themes", "groove"}
KNOWN_SONG_KEYS = {
    "title", "bpm", "key", "mode", "meter", "beats_per_bar", "genre", "project",
    "seed", "take", "variation", "humanize_velocity", "humanize_timing", "exports_root",
    "pattern_bars", "pattern_quantize_beats", "pattern_velocity_step", "pattern_merge_repeats",
    "pattern_merge_min_run", "pattern_merge_max", "themes_auto", "params",
}
KNOWN_GROOVE_KEYS = {"swing", "swing_16th", "pocket_ms"}
KNOWN_EXPORT_KEYS = {
    "mode", "write_full_song", "write_stems", "write_sections", "write_patterns",
    "write_index", "write_analysis", "midi_text",
}
KNOWN_MIDI_TEXT_KEYS = {"enabled", "views", "subdiv"}
KNOWN_THEME_KEYS = {"role", "events", "degrees", "rhythm", "length_beats", "register", "octave", "allow_development"}
KNOWN_SECTION_KEYS = {
    "type", "bars", "beats", "meter", "key", "mode", "harmony", "instruments",
    "progression", "intent", "solo", "role", "seed", "variation", "energy", "intensity",
}
KNOWN_TIMING_PARAMS = {"pocket_ms", "push_pull", "timing_jitter_ms", "velocity_humanize"}
KNOWN_COMMON_PARAMS = {"persona", "transitions"} | KNOWN_TIMING_PARAMS
KNOWN_DRUM_PARAMS = {
    "kick_density", "snare_density", "hat_density", "fill_rate", "fill_chatter", "accent_strength",
    "swing", "swing_16th", "phrase_len_bars", "pickup_rate", "downbeat_rate", "fill_length",
    "phrase_end_emphasis", "choke_rate", "flam_rate", "drag_rate", "ghost_rate", "ghost_steps",
    "riff_accent_rate", "riff_accent_boost", "constraints", "voices",
} | (KNOWN_COMMON_PARAMS - {"pocket_ms"})
KNOWN_DRUM_CONSTRAINT_KEYS = {
    "enabled", "max_hand_hits", "max_foot_hits", "fill_duck_hats",
    "kick_density_hihat_pedal_limit",
}
KNOWN_BASS_PARAMS = {
    "density", "rest_rate", "rhythm_pattern", "lock_to_kick", "lock_to_snare", "lock_to_hat",
    "lock_to_kicks", "avoid_fills", "octave", "lock_to_riff", "articulation_style", "chromatic_rate",
    "approach_rate", "octave_jump_rate", "fifth_jump_rate", "pedal_rate", "accent_strength",
    "slap_pop_rate", "slap_thumb_rate", "ghost_perc_rate", "slap_velocity_floor", "pop_velocity_boost",
    "fill_rate", "fill_complexity", "fill_avoid_drums", "solo_density", "solo_register_high",
    "motif_repeat_rate", "motion_style", "register_low", "register_high", "max_passing_per_bar",
    "phrase_len_bars", "phrase_length_bars", "section_role_variation", "root_bias",
} | KNOWN_COMMON_PARAMS
KNOWN_RHYTHM_GTR_PARAMS = {
    "style", "density", "mute", "contrast", "phrase_development", "phrase_len_bars", "sustain_mode",
    "sustain_duration", "strum", "strum_beats", "strum_dir", "strum_style", "retrigger", "hit_strategy",
    "voice_leading", "voice_range_low", "voice_range_high", "use_patterns", "palm_mute", "voicing",
    "register", "register_min", "register_max", "accent_strength", "strum_ms", "chuck_rate",
    "humanize_velocity", "humanize_timing", "downbeat_boost", "sustain_cut_rate", "section_contrast",
    "follow_hats", "accent_syncopation", "octave", "lock_to_riff", "pattern", "reattack_vel",
    "reattack_dur", "reattack_strum", "stab_beats",
} | KNOWN_COMMON_PARAMS
KNOWN_LEAD_GTR_PARAMS = {
    "contour_style", "rest_probability", "phrase_len_bars", "resolution_strength", "theme_quote_rate",
} | KNOWN_COMMON_PARAMS
KNOWN_ACOUSTIC_GTR_PARAMS = {
    "technique", "picking_pattern", "melody_amount", "phrase_variation", "voicing_style", "capo",
    "strum_density", "mute_ratio", "body_tap_ratio", "vel_variation", "timing_variation",
} | KNOWN_COMMON_PARAMS
KNOWN_ARPEGGIATOR_PARAMS = {"pattern", "note_duration", "rest_probability", "octave_range"} | KNOWN_COMMON_PARAMS
KNOWN_DRUM_VOICE_PARAMS = {
    "voices.kick.density", "voices.kick.syncopation", "voices.kick.syncopation.rate",
    "voices.kick.syncopation.placements", "voices.kick.double", "voices.kick.double.rate",
    "voices.kick.double.placements", "voices.snare.density", "voices.snare.ghosts",
    "voices.snare.ghosts.rate", "voices.snare.ghosts.velocity_bias", "voices.snare.ghosts.placements",
    "voices.snare.ghosts.subdiv", "voices.snare.articulation", "voices.snare.articulation.default",
    "voices.hats.density", "voices.hats.open", "voices.hats.open.rate", "voices.hats.open.placements",
    "voices.hats.opens", "voices.hats.opens.rate", "voices.hats.opens.placements",
    "voices.hats.pedal", "voices.hats.pedal.rate", "voices.hats.pedal.placements",
    "voices.hats.accents", "voices.hats.accents.rate", "voices.hats.accents.boost",
    "voices.hats.accents.bias", "voices.hats.accents.placements", "voices.hats.pattern",
    "voices.hats.pattern.rate", "voices.hats.pattern.placements", "voices.hats.velocity",
    "voices.hats.velocity.bias", "voices.crash.rate", "voices.crash.placements",
    "voices.ride.bell_rate", "voices.cymbals.splash_rate", "voices.cymbals.china_rate",
    "voices.toms.groove", "voices.toms.groove.rate", "voices.toms.fills", "voices.toms.fills.rate",
}


class ValidationHelper:
    """Helper class for providing validation suggestions."""

    @staticmethod
    def find_closest_matches(
        invalid_key: str,
        valid_keys: Set[str],
        max_suggestions: int = 3,
        cutoff: float = 0.6,
    ) -> List[str]:
        """Find closest matching valid keys using fuzzy matching.

        Args:
            invalid_key: The invalid key that was provided
            valid_keys: Set of valid key names
            max_suggestions: Maximum number of suggestions to return
            cutoff: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of closest matching keys
        """
        matches = difflib.get_close_matches(
            invalid_key,
            valid_keys,
            n=max_suggestions,
            cutoff=cutoff,
        )
        return matches

    @staticmethod
    def format_suggestion_message(
        invalid_key: str,
        context: str,
        valid_keys: Set[str],
    ) -> str:
        """Format a helpful error message with suggestions.

        Args:
            invalid_key: The invalid key that was provided
            context: Context string (e.g., "drums.params", "bass.params")
            valid_keys: Set of valid key names

        Returns:
            Formatted error message with suggestions
        """
        suggestions = ValidationHelper.find_closest_matches(invalid_key, valid_keys)

        if suggestions:
            if len(suggestions) == 1:
                return f"Unknown parameter '{invalid_key}' in {context}. Did you mean '{suggestions[0]}'?"
            else:
                suggestions_str = "', '".join(suggestions)
                return f"Unknown parameter '{invalid_key}' in {context}. Did you mean one of: '{suggestions_str}'?"
        else:
            return f"Unknown parameter '{invalid_key}' in {context}. No similar parameters found."

    @staticmethod
    def validate_drum_voice_path(path: str, section_id: str) -> Optional[str]:
        """Validate a drums voice configuration path.

        Args:
            path: The configuration path (e.g., "voices.hats.accents.rate")
            section_id: Section ID for error context

        Returns:
            Error message if invalid, None if valid
        """
        if path in KNOWN_DRUM_VOICE_PARAMS:
            return None

        # Check if it's a voice path at all
        if not path.startswith("voices."):
            return None  # Not a voice path, let other validation handle it

        suggestions = ValidationHelper.find_closest_matches(path, KNOWN_DRUM_VOICE_PARAMS)

        if suggestions:
            if len(suggestions) == 1:
                return f"Section '{section_id}': Unknown drums voice parameter '{path}'. Did you mean '{suggestions[0]}'?"
            else:
                suggestions_str = "', '".join(suggestions)
                return f"Section '{section_id}': Unknown drums voice parameter '{path}'. Did you mean one of: '{suggestions_str}'?"
        else:
            return f"Section '{section_id}': Unknown drums voice parameter '{path}'."

    @staticmethod
    def validate_instrument_params(
        params: Dict,
        instrument_name: str,
        section_id: str,
        strict: bool = False,
    ) -> List[str]:
        """Validate instrument parameters and return warnings/errors.

        Args:
            params: Dictionary of parameters
            instrument_name: Name of the instrument
            section_id: Section ID for error context
            strict: If True, unknown params are errors; if False, warnings

        Returns:
            List of warning/error messages
        """
        messages = []

        # Select appropriate known params set
        if instrument_name == "drums":
            known_params = KNOWN_DRUM_PARAMS
        elif instrument_name == "bass":
            known_params = KNOWN_BASS_PARAMS
        elif instrument_name == "rhythm_gtr":
            known_params = KNOWN_RHYTHM_GTR_PARAMS
        elif instrument_name == "lead_gtr":
            known_params = KNOWN_LEAD_GTR_PARAMS
        elif instrument_name == "acoustic_gtr":
            known_params = KNOWN_ACOUSTIC_GTR_PARAMS
        elif instrument_name == "arpeggiator":
            known_params = KNOWN_ARPEGGIATOR_PARAMS
        else:
            return messages  # Custom engines define their own parameters

        for key in params.keys():
            if key not in known_params:
                msg = ValidationHelper.format_suggestion_message(
                    key,
                    f"{instrument_name}.params in section '{section_id}'",
                    known_params,
                )
                if strict:
                    messages.append(f"ERROR: {msg}")
                else:
                    messages.append(f"WARNING: {msg}")

        return messages


def validate_section_config(
    section_id: str,
    section_config: Dict,
    strict: bool = False,
) -> List[str]:
    """Validate a section configuration and return any issues.

    Args:
        section_id: Section identifier
        section_config: Section configuration dictionary
        strict: If True, treat warnings as errors

    Returns:
        List of validation messages (warnings and errors)
    """
    messages = []

    # Validate instruments section
    instruments = section_config.get("instruments", {})
    if not isinstance(instruments, dict):
        messages.append(f"ERROR: Section '{section_id}': 'instruments' must be a mapping")
        return messages

    for instrument_name, instrument_config in instruments.items():
        if not isinstance(instrument_config, dict):
            continue

        # Validate params
        params = instrument_config.get("params", {})
        if isinstance(params, dict):
            param_messages = ValidationHelper.validate_instrument_params(
                params,
                instrument_name,
                section_id,
                strict=strict,
            )
            messages.extend(param_messages)

        # Validate extra
        extra = instrument_config.get("extra", {})
        if isinstance(extra, dict) and instrument_name in ["bass", "rhythm_gtr", "lead_gtr"]:
            # Extra params often overlap with params, validate them too
            extra_messages = ValidationHelper.validate_instrument_params(
                extra,
                instrument_name,
                section_id,
                strict=False,  # Extra is more lenient
            )
            messages.extend(extra_messages)

    return messages


def validate_song_config(
    config: Dict,
    strict: bool = False,
) -> Tuple[List[str], List[str]]:
    """Validate entire song configuration.

    Args:
        config: Song configuration dictionary
        strict: If True, treat warnings as errors

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    # Validate sections
    sections = config.get("sections", {})
    if not isinstance(sections, dict):
        errors.append("ERROR: Top-level 'sections' must be a mapping")
        return errors, warnings

    for section_id, section_config in sections.items():
        if not isinstance(section_config, dict):
            errors.append(f"ERROR: Section '{section_id}' must be a mapping")
            continue

        messages = validate_section_config(section_id, section_config, strict=strict)

        # Split into errors and warnings
        for msg in messages:
            if msg.startswith("ERROR:"):
                errors.append(msg)
            elif msg.startswith("WARNING:"):
                warnings.append(msg)

    return errors, warnings


def format_validation_report(errors: List[str], warnings: List[str]) -> str:
    """Format validation errors and warnings into a readable report.

    Args:
        errors: List of error messages
        warnings: List of warning messages

    Returns:
        Formatted report string
    """
    lines = []

    if errors:
        lines.append("=== Configuration Errors ===")
        for error in errors:
            lines.append(f"  {error}")
        lines.append("")

    if warnings:
        lines.append("=== Configuration Warnings ===")
        for warning in warnings:
            lines.append(f"  {warning}")
        lines.append("")

    if not errors and not warnings:
        lines.append("✓ Configuration validation passed")

    return "\n".join(lines)
