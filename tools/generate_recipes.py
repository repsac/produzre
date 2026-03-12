#!/usr/bin/env python3
"""Generate bass recipes and tuning recommendations from MIDI analysis data.

Reads a ``genre_stats.json`` file produced by :mod:`batch_analyze` and generates:

1. **Bass recipe YAML files** — one per genre with sufficient data
2. **Drum tuning recommendations** — suggested ghost/fill/swing values per genre
3. **Rhythm guitar tuning recommendations** — voicing, density, palm-mute per genre

The generated recipes are written to the Produzre recipes directory
(``produzre/resources/recipes/bass/`` by default).  A JSON tuning report is also
written with drum and rhythm guitar recommendations.

Usage
-----
    python tools/generate_recipes.py --input genre_stats.json
    python tools/generate_recipes.py --input genre_stats.json --output-bass recipes/bass/
    python tools/generate_recipes.py --input genre_stats.json --output-report report.json
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_mean(summary: Dict, field: str, default: float = 0.0) -> float:
    """Get the mean value from a genre summary field."""
    entry = summary.get(field)
    if entry and isinstance(entry, dict):
        return entry.get("mean", default)
    return default


def _get_median(summary: Dict, field: str, default: float = 0.0) -> float:
    """Get the median value from a genre summary field."""
    entry = summary.get(field)
    if entry and isinstance(entry, dict):
        return entry.get("median", default)
    return default


def _round(v: float, decimals: int = 2) -> float:
    return round(v, decimals)


# ---------------------------------------------------------------------------
# Bass recipe generation
# ---------------------------------------------------------------------------

# Map from analysis genre names to recipe IDs
GENRE_TO_RECIPE_ID = {
    "rock": "rock",
    "hard rock": "hard_rock",
    "blues rock": "blues_rock",
    "blues": "blues",
    "country": "country",
    "jazz": "jazz",
    "funk": "funk",
    "soul": "soul",
    "r&b": "rnb",
    "reggae": "reggae",
    "pop": "pop",
    "pop rock": "pop_rock",
    "alternative rock": "alt_rock",
    "punk rock": "punk",
    "metal": "metal",
    "heavy metal": "heavy_metal",
    "electronic": "electronic",
    "latin": "latin",
    "folk": "folk",
    "classical": "classical",
    "progressive rock": "prog_rock",
    "soft rock": "soft_rock",
    "grunge": "grunge",
    "ska": "ska",
    "gospel": "gospel",
    "techno": "techno",
    "dance-pop": "dance_pop",
    "arena rock": "arena_rock",
    "new wave": "new_wave",
    "emo": "emo",
}


def _density_to_pattern(density: float) -> str:
    """Map bass notes-per-bar to a rhythm pattern."""
    if density >= 12:
        return "drive"       # Very busy: 16th-note driving
    elif density >= 6:
        return "push"        # Active: pushing on off-beats
    elif density >= 3:
        return "anchor"      # Standard: quarter notes
    else:
        return "anchor"      # Sparse: whole/half notes


def _density_to_density_param(notes_per_bar: float) -> float:
    """Map notes-per-bar to the 0.0-1.0 density parameter."""
    # 1 note/bar → ~0.25, 4 notes/bar → 0.5, 8 notes/bar → 0.75, 16+ → 0.95
    return _round(min(0.95, max(0.2, notes_per_bar / 16.0)), 2)


def _staccato_to_articulation(staccato_ratio: float) -> str:
    """Map staccato ratio to articulation style."""
    if staccato_ratio >= 0.5:
        return "mute"
    elif staccato_ratio >= 0.3:
        return "pick"
    else:
        return "finger"


def _bpm_range(bpm_median: float) -> List[int]:
    """Generate a BPM range from median BPM."""
    low = max(40, int(bpm_median * 0.7))
    high = min(240, int(bpm_median * 1.3))
    return [low, high]


def generate_bass_recipe(genre: str, recipe_id: str, stats: Dict) -> str:
    """Generate a single bass recipe YAML string from genre statistics."""
    bpm = _get_median(stats, "bpm_values", 120)
    notes_per_bar = _get_mean(stats, "bass_notes_per_bar", 4)
    root_ratio = _get_mean(stats, "bass_root_ratio", 0.5)
    step_ratio = _get_mean(stats, "bass_step_ratio", 0.3)
    onbeat_ratio = _get_mean(stats, "bass_onbeat_ratio", 0.7)
    syncopation = _get_mean(stats, "bass_syncopation", 0.2)
    staccato_ratio = _get_mean(stats, "bass_staccato_ratio", 0.2)
    avg_sustain = _get_mean(stats, "bass_avg_sustain", 0.5)
    rest_ratio = _get_mean(stats, "bass_rest_ratio", 0.1)
    leap_avg = _get_mean(stats, "bass_leap_avg", 4.0)

    # Groove features
    swing = _get_mean(stats, "swing_values", 0.5)
    push_pull = _get_mean(stats, "push_pull_values", 0.0)
    accent = _get_mean(stats, "accent_values", 0.3)

    # Derived parameters
    density = _density_to_density_param(notes_per_bar)
    rhythm_pattern = _density_to_pattern(notes_per_bar)
    bpm_rng = _bpm_range(bpm)

    # Articulation: blend staccato ratio and sustain length
    if staccato_ratio >= 0.5 or avg_sustain < 0.3:
        articulation = "mute"
    elif staccato_ratio >= 0.3 or avg_sustain < 0.5:
        articulation = "pick"
    else:
        articulation = "finger"

    # Approach rate: higher step_ratio suggests more passing motion
    approach_rate = _round(min(0.5, step_ratio * 0.6), 2)
    chromatic_rate = _round(min(0.3, (1.0 - step_ratio) * 0.15), 2)

    # Octave jump: driven by leap_avg (bigger avg leaps → more octave jumps)
    # Also inversely related to density (busier lines jump less)
    octave_jump = _round(min(0.35, max(0.0, (leap_avg - 2.0) * 0.05 + rest_ratio * 0.3)), 2)

    # Fifth drop: larger leaps + off-beat tendency
    fifth_jump = _round(min(0.3, max(0.0, (leap_avg - 3.0) * 0.04 + (1.0 - onbeat_ratio) * 0.2)), 2)

    # Swing: convert from 0.5-centered ratio to 0.0-1.0 param
    swing_param = _round(max(0.0, (swing - 0.5) * 4.0), 2)  # 0.5→0, 0.55→0.2, 0.67→0.68

    # Motion style: driven by step_ratio and syncopation
    if step_ratio >= 0.5:
        motion_style = "stepwise"
    elif leap_avg >= 5.0 or syncopation >= 0.4:
        motion_style = "mixed"
    else:
        motion_style = "stepwise"

    # Lock to kick: higher for genres with strong rhythmic alignment
    lock_to_kick = _round(min(0.8, onbeat_ratio * 0.8), 2)

    # Root bias: how often bass plays root on non-downbeats
    # Real data shows ~25% root ratio; scale to a 0.15-0.80 parameter range
    root_bias = _round(min(0.8, max(0.15, root_ratio * 2.5)), 2)

    # Build YAML
    lines = [
        f"id: {recipe_id}",
        f"instrument: bass",
        f"tags:",
        f"  genre: \"{genre}\"",
        f"  time_signature: \"4/4\"",
        f"  bpm_range: [{bpm_rng[0]}, {bpm_rng[1]}]",
        f"  section_types: [verse, chorus, bridge, default]",
        f"params:",
        f"  density: {density}",
        f"  rhythm_pattern: \"{rhythm_pattern}\"",
        f"  articulation_style: \"{articulation}\"",
        f"  register_low: 28",
        f"  register_high: 52",
        f"  approach_rate: {approach_rate}",
        f"  chromatic_rate: {chromatic_rate}",
        f"  max_passing_per_bar: {2 if approach_rate > 0.05 else 1}",
        f"  octave_jump_rate: {octave_jump}",
        f"  fifth_jump_rate: {fifth_jump}",
        f"  rest_rate: {_round(rest_ratio, 2)}",
        f"  root_bias: {root_bias}",
        f"  motion_style: \"{motion_style}\"",
        f"  swing: {swing_param}",
        f"  lock_to_kick: {lock_to_kick}",
        f"  accent_strength: {_round(1.0 + accent * 0.5, 2)}",
        f"  syncopation: {_round(syncopation, 2)}",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Drum recipe tuning recommendations
# ---------------------------------------------------------------------------

def generate_drum_recommendations(genre: str, stats: Dict) -> Dict[str, Any]:
    """Generate drum recipe tuning recommendations from statistics."""
    kick_dens = _get_mean(stats, "drum_kick_density", 2.0)
    snare_dens = _get_mean(stats, "drum_snare_density", 2.0)
    hat_dens = _get_mean(stats, "drum_hat_density", 4.0)
    ghost_ratio = _get_mean(stats, "drum_ghost_ratio", 0.1)
    accent_ratio = _get_mean(stats, "drum_accent_ratio", 0.3)
    fill_dens = _get_mean(stats, "drum_fill_density", 0.1)
    kick_onbeat = _get_mean(stats, "drum_kick_onbeat_ratio", 0.7)
    snare_backbeat = _get_mean(stats, "drum_snare_backbeat_ratio", 0.7)
    hat_offbeat = _get_mean(stats, "drum_hat_offbeat_ratio", 0.3)
    swing = _get_mean(stats, "swing_values", 0.5)

    # Determine hat mode from density
    if hat_dens >= 7:
        hat_mode = "16th"
    elif hat_dens >= 3:
        hat_mode = "8th"
    else:
        hat_mode = "quarter"

    return {
        "genre": genre,
        "hat_mode": hat_mode,
        "hat_density_observed": _round(hat_dens),
        "kick_density_observed": _round(kick_dens),
        "snare_density_observed": _round(snare_dens),
        "ghost_rate_suggested": _round(min(0.6, ghost_ratio * 1.5), 2),
        "fill_rate_suggested": _round(min(0.5, fill_dens * 2), 2),
        "swing_suggested": _round(max(0.0, (swing - 0.5) * 4.0), 2),
        "kick_extra_rate_suggested": _round(max(0.0, 1.0 - kick_onbeat), 2),
        "open_hat_rate_suggested": _round(hat_offbeat * 0.5, 2),
    }


# ---------------------------------------------------------------------------
# Rhythm guitar recipe tuning
# ---------------------------------------------------------------------------

def generate_rg_recommendations(genre: str, stats: Dict) -> Dict[str, Any]:
    """Generate rhythm guitar tuning recommendations from statistics."""
    chords_per_bar = _get_mean(stats, "rg_chords_per_bar", 4.0)
    polyphony = _get_mean(stats, "rg_strum_polyphony", 3.0)
    downbeat = _get_mean(stats, "rg_downbeat_ratio", 0.5)
    upbeat = _get_mean(stats, "rg_upbeat_ratio", 0.3)
    sustained = _get_mean(stats, "rg_sustained_ratio", 0.3)
    pitch_spread = _get_mean(stats, "rg_pitch_spread", 12.0)
    palm_mute = _get_mean(stats, "rg_palm_mute_ratio", 0.2)
    accent_var = _get_mean(stats, "rg_accent_variation", 10.0)

    # Derive style
    if chords_per_bar >= 6:
        style = "syncopated"
    elif chords_per_bar >= 3:
        style = "straight_8s"
    else:
        style = "half_time"

    # Voicing from spread
    if pitch_spread <= 8:
        voicing = "power"
    elif pitch_spread <= 15:
        voicing = "triad"
    else:
        voicing = "shell"

    return {
        "genre": genre,
        "style_suggested": style,
        "voicing_suggested": voicing,
        "density_suggested": _round(min(1.0, chords_per_bar / 8.0), 2),
        "palm_mute_suggested": _round(palm_mute, 2),
        "downbeat_boost_suggested": _round(min(0.5, (downbeat - 0.3) * 1.5), 2),
        "strum_polyphony_observed": _round(polyphony),
        "sustained_ratio_observed": _round(sustained),
        "accent_variation_observed": _round(accent_var),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate bass recipes and tuning recommendations from MIDI analysis data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/generate_recipes.py --input analysis_output/genre_stats.json
  python tools/generate_recipes.py --input stats.json --output-bass my_recipes/bass/
  python tools/generate_recipes.py --input stats.json --output-report tuning.json
""",
    )
    parser.add_argument("--input", type=str, required=True,
                        help="Path to genre_stats.json from batch_analyze.py")
    parser.add_argument("--output-bass", type=str, default="produzre/resources/recipes/bass",
                        help="Output directory for bass recipe YAMLs (default: produzre/resources/recipes/bass)")
    parser.add_argument("--output-report", type=str, default="tuning_report.json",
                        help="Output path for tuning recommendations JSON (default: tuning_report.json)")
    parser.add_argument("--min-files", type=int, default=3,
                        help="Minimum files in a genre to generate a recipe (default: 3)")
    args = parser.parse_args()

    # Load stats
    with open(args.input) as f:
        genre_stats = json.load(f)

    print(f"Loaded {len(genre_stats)} genre summaries from {args.input}")

    # Filter to genres with enough data
    valid = [g for g in genre_stats if g["file_count"] >= args.min_files]
    print(f"Genres with >= {args.min_files} files: {len(valid)}")

    # Generate bass recipes
    bass_dir = Path(args.output_bass)
    bass_dir.mkdir(parents=True, exist_ok=True)
    bass_count = 0

    for gs in valid:
        genre = gs["genre"]
        recipe_id = GENRE_TO_RECIPE_ID.get(genre)
        if not recipe_id:
            continue

        # Only generate if we have bass data
        if not gs.get("bass_notes_per_bar"):
            continue

        yaml_content = generate_bass_recipe(genre, recipe_id, gs)
        out_path = bass_dir / f"{recipe_id}.yaml"
        with open(out_path, "w") as f:
            f.write(yaml_content)
        bass_count += 1
        print(f"  Bass recipe: {out_path}")

    print(f"\nGenerated {bass_count} bass recipes in {bass_dir}/")

    # Generate tuning report
    report = {
        "drums": [],
        "rhythm_gtr": [],
    }

    for gs in valid:
        genre = gs["genre"]
        if gs.get("drum_kick_density"):
            report["drums"].append(generate_drum_recommendations(genre, gs))
        if gs.get("rg_chords_per_bar"):
            report["rhythm_gtr"].append(generate_rg_recommendations(genre, gs))

    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nTuning report: {report_path}")
    print(f"  Drum recommendations: {len(report['drums'])}")
    print(f"  Rhythm guitar recommendations: {len(report['rhythm_gtr'])}")


if __name__ == "__main__":
    main()
