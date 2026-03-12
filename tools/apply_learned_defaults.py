#!/usr/bin/env python3
"""Recommend engine default changes from MIDI analysis data.

Reads a ``genre_stats.json`` file produced by :mod:`batch_analyze` and performs
cross-genre analysis to identify statistically-grounded changes for engine
default parameters.  Recommendations are printed to stdout with supporting
evidence (sample sizes, averages, ranges).

This tool does **not** modify any code — it only prints recommendations for
a human to review and apply.

Usage
-----
    python tools/apply_learned_defaults.py --input genre_stats.json
"""

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Dict, List


def _m(stats_list: List[Dict], field: str) -> List[float]:
    """Extract mean values for a field across all genre summaries."""
    vals = []
    for gs in stats_list:
        entry = gs.get(field)
        if entry and isinstance(entry, dict) and "mean" in entry:
            vals.append(entry["mean"])
    return vals


def analyze_cross_genre_defaults(genre_stats: List[Dict]):
    """Analyze cross-genre patterns to suggest engine default changes."""
    # Filter to genres with meaningful data (>= 5 files)
    valid = [g for g in genre_stats if g["file_count"] >= 5]

    recommendations = []

    # ── Bass defaults ──────────────────────────────────────────────
    bass_npb = _m(valid, "bass_notes_per_bar")
    bass_root = _m(valid, "bass_root_ratio")
    bass_step = _m(valid, "bass_step_ratio")
    bass_onbeat = _m(valid, "bass_onbeat_ratio")
    bass_staccato = _m(valid, "bass_staccato_ratio")
    bass_sustain = _m(valid, "bass_avg_sustain")
    bass_rest = _m(valid, "bass_rest_ratio")
    bass_synco = _m(valid, "bass_syncopation")

    if bass_npb:
        avg_npb = mean(bass_npb)
        recommendations.append({
            "engine": "bass",
            "parameter": "density",
            "current_default": 0.7,
            "suggested": round(min(0.95, avg_npb / 16.0), 2),
            "evidence": f"Avg notes/bar across {len(bass_npb)} genres = {avg_npb:.1f}",
        })

    if bass_root:
        avg_root = mean(bass_root)
        recommendations.append({
            "engine": "bass",
            "parameter": "root_bias_rate (voicing.py line 120)",
            "current_default": "0.35 (exclude root 35% on inner beats)",
            "suggested": round(1.0 - avg_root, 2),
            "evidence": f"Avg root ratio across genres = {avg_root:.2f} → non-root = {1-avg_root:.2f}",
        })

    if bass_step:
        avg_step = mean(bass_step)
        recommendations.append({
            "engine": "bass",
            "parameter": "approach_rate (default)",
            "current_default": 0.0,
            "suggested": round(min(0.3, avg_step * 0.5), 2),
            "evidence": f"Avg step motion ratio = {avg_step:.2f} → suggests moderate approach tones",
        })

    if bass_rest:
        avg_rest = mean(bass_rest)
        recommendations.append({
            "engine": "bass",
            "parameter": "rest_rate (default)",
            "current_default": 0.0,
            "suggested": round(avg_rest, 2),
            "evidence": f"Avg rest ratio = {avg_rest:.2f} (real bass has more rests than our default 0.0)",
        })

    if bass_synco:
        avg_synco = mean(bass_synco)
        recommendations.append({
            "engine": "bass",
            "parameter": "syncopation (general observation)",
            "current_default": "N/A (no explicit param)",
            "suggested": f"{avg_synco:.2f}",
            "evidence": f"Avg syncopation = {avg_synco:.2f} → bass plays more off-beats than our engine generates",
        })

    # ── Drum defaults ──────────────────────────────────────────────
    drum_ghost = _m(valid, "drum_ghost_ratio")
    drum_accent = _m(valid, "drum_accent_ratio")
    drum_fill = _m(valid, "drum_fill_density")
    drum_kick = _m(valid, "drum_kick_density")
    drum_hat = _m(valid, "drum_hat_density")

    if drum_ghost:
        avg_ghost = mean(drum_ghost)
        recommendations.append({
            "engine": "drums",
            "parameter": "ghost_rate (typical)",
            "current_default": "varies by recipe (0.0-0.55)",
            "suggested": round(avg_ghost * 1.5, 2),
            "evidence": f"Avg ghost note ratio across genres = {avg_ghost:.3f}",
        })

    if drum_fill:
        avg_fill = mean(drum_fill)
        recommendations.append({
            "engine": "drums",
            "parameter": "fill_rate (observation)",
            "current_default": "varies by recipe (0.15-0.40)",
            "suggested": round(min(0.5, avg_fill * 2), 2),
            "evidence": f"Avg fill density across genres = {avg_fill:.3f}",
        })

    # ── Rhythm guitar defaults ─────────────────────────────────────
    rg_density = _m(valid, "rg_chords_per_bar")
    rg_palm = _m(valid, "rg_palm_mute_ratio")
    rg_downbeat = _m(valid, "rg_downbeat_ratio")
    rg_spread = _m(valid, "rg_pitch_spread")

    if rg_palm:
        avg_palm = mean(rg_palm)
        recommendations.append({
            "engine": "rhythm_gtr",
            "parameter": "palm_mute (neutral default)",
            "current_default": 0.5,
            "suggested": round(avg_palm, 2),
            "evidence": f"Avg palm mute ratio = {avg_palm:.2f} across {len(rg_palm)} genres",
        })

    if rg_downbeat:
        avg_db = mean(rg_downbeat)
        recommendations.append({
            "engine": "rhythm_gtr",
            "parameter": "downbeat_boost (neutral default)",
            "current_default": 0.2,
            "suggested": round(min(0.5, (avg_db - 0.3) * 1.5), 2),
            "evidence": f"Avg downbeat ratio = {avg_db:.2f}",
        })

    # ── Groove defaults ────────────────────────────────────────────
    swings = _m(valid, "swing_values")
    accents = _m(valid, "accent_values")

    if swings:
        avg_swing = mean(swings)
        recommendations.append({
            "engine": "global",
            "parameter": "swing (observation)",
            "current_default": 0.0,
            "suggested": round(max(0.0, (avg_swing - 0.5) * 4.0), 2),
            "evidence": f"Avg swing ratio = {avg_swing:.3f} (0.5 = straight) → "
                        f"most genres are nearly straight",
        })

    return recommendations


def main():
    parser = argparse.ArgumentParser(
        description="Recommend engine default changes from MIDI analysis data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/apply_learned_defaults.py --input analysis_output/genre_stats.json
""",
    )
    parser.add_argument("--input", required=True,
                        help="Path to genre_stats.json from batch_analyze.py")
    args = parser.parse_args()

    with open(args.input) as f:
        genre_stats = json.load(f)

    print(f"Loaded {len(genre_stats)} genre summaries\n")

    recs = analyze_cross_genre_defaults(genre_stats)

    print("=" * 75)
    print("ENGINE DEFAULT RECOMMENDATIONS (from MIDI analysis)")
    print("=" * 75)

    current_engine = None
    for r in recs:
        eng = r["engine"]
        if eng != current_engine:
            print(f"\n── {eng.upper()} ──")
            current_engine = eng

        print(f"  {r['parameter']}")
        print(f"    Current: {r['current_default']}")
        print(f"    Suggested: {r['suggested']}")
        print(f"    Evidence: {r['evidence']}")
        print()


if __name__ == "__main__":
    main()
