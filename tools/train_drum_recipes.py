#!/usr/bin/env python3
"""Train drum groove recipes from a MIDI archive.

Reads a manifest (produced by :mod:`build_drum_manifest`), loads MIDI files
grouped by genre, quantizes note events to a 16-step grid, computes
statistical groove profiles, and writes recipe YAML files suitable for
the Produzre drums engine.

Pipeline
--------
1. Load manifest, group folders by genre
2. For each genre, load MIDI files (skip corrupted)
3. Quantize note events to a 16-step grid, classify by GM drum map
4. Compute per-step hit probabilities for kick/snare/hat/crash
5. Derive GrooveTemplate fields from probabilities
6. Write recipe YAML per genre

Requires: ``mido`` (``pip install mido``) and ``pyyaml``.

Usage
-----
    python tools/train_drum_recipes.py --manifest manifest.yaml --archive-dir /path/to/midi
    python tools/train_drum_recipes.py --manifest m.yaml --archive-dir midi/ --genres funk rock jazz
    python tools/train_drum_recipes.py --manifest m.yaml --archive-dir midi/ --max-files 500
    python tools/train_drum_recipes.py --manifest m.yaml --archive-dir midi/ --dry-run --verbose
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

try:
    import mido
except ImportError:
    print("ERROR: mido is required. Install with: pip install mido", file=sys.stderr)
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

STEPS_PER_BAR = 16

# ---------------------------------------------------------------------------
# GM Drum Map — pitch ranges to instrument class
# ---------------------------------------------------------------------------

# Standard GM percussion mapping (channel 10, but we scan all channels).
# Pitches are grouped into broad classes for groove profiling.

GM_KICK = {35, 36}  # Acoustic Bass Drum, Bass Drum 1
GM_SNARE = {38, 40}  # Acoustic Snare, Electric Snare
GM_SNARE_GHOST = {38, 40}  # Same pitches, distinguished by velocity
GM_HIHAT_CLOSED = {42, 44}  # Closed Hi-Hat, Pedal Hi-Hat
GM_HIHAT_OPEN = {46}  # Open Hi-Hat
GM_RIDE = {51, 53, 59}  # Ride Cymbal 1, Ride Bell, Ride Cymbal 2
GM_CRASH = {49, 52, 55, 57}  # Crash 1, Chinese, Splash, Crash 2
GM_TOM = {41, 43, 45, 47, 48, 50}  # Low-High Toms

# Extended ranges for non-standard mappings
KICK_RANGE = range(35, 37)
SNARE_RANGE = range(37, 41)
HIHAT_RANGE = range(42, 47)
RIDE_RANGE = range(51, 54)
CRASH_RANGE = range(49, 58)

GHOST_VELOCITY_THRESHOLD = 60  # Velocity below this = ghost note


def classify_pitch(pitch: int) -> Optional[str]:
    """Classify a MIDI drum pitch into an instrument class.

    Returns one of: ``"kick"``, ``"snare"``, ``"hat_closed"``, ``"hat_open"``,
    ``"ride"``, ``"crash"``, ``"tom"``, or ``None`` if unrecognized.
    """
    if pitch in GM_KICK:
        return "kick"
    if pitch in GM_SNARE:
        return "snare"
    if pitch in GM_HIHAT_CLOSED:
        return "hat_closed"
    if pitch in GM_HIHAT_OPEN:
        return "hat_open"
    if pitch in GM_RIDE:
        return "ride"
    if pitch in GM_CRASH:
        return "crash"
    if pitch in GM_TOM:
        return "tom"
    # Fallback: range-based heuristic for non-standard mappings
    if pitch in KICK_RANGE:
        return "kick"
    if pitch in SNARE_RANGE:
        return "snare"
    if pitch in HIHAT_RANGE:
        return "hat_closed"
    if pitch in RIDE_RANGE:
        return "ride"
    if pitch in CRASH_RANGE:
        return "crash"
    return None


# ---------------------------------------------------------------------------
# MIDI Loading & Quantization
# ---------------------------------------------------------------------------

def _detect_ticks_per_bar(mid: mido.MidiFile) -> int:
    """Detect ticks per bar from MIDI file.

    Scans for time signature meta messages. Defaults to 4/4.
    Returns ticks per bar based on ticks_per_beat and time signature.
    """
    tpb = mid.ticks_per_beat or 480
    numerator = 4
    denominator = 4

    for track in mid.tracks:
        for msg in track:
            if msg.type == "time_signature":
                numerator = msg.numerator
                denominator = msg.denominator
                break
        else:
            continue
        break

    # ticks_per_bar = tpb * numerator * (4 / denominator)
    return int(tpb * numerator * 4 / denominator)


def quantize_midi(
    filepath: Path,
    *,
    steps_per_bar: int = STEPS_PER_BAR,
) -> Optional[Dict[str, List[List[Tuple[int, int]]]]]:
    """Load a MIDI file and quantize note events to a step grid.

    Parameters
    ----------
    filepath : Path
        Path to the ``.mid`` file.
    steps_per_bar : int
        Grid resolution (default: 16 for 16th-note grid).

    Returns
    -------
    dict or None
        Maps instrument class to a list of bars, where each bar is a list
        of ``(step_index, velocity)`` tuples.  Returns ``None`` on parse error.
    """
    try:
        mid = mido.MidiFile(str(filepath))
    except Exception:
        return None

    ticks_per_bar = _detect_ticks_per_bar(mid)

    if ticks_per_bar <= 0:
        return None

    ticks_per_step = ticks_per_bar / steps_per_bar

    # Collect all note_on events across all tracks.
    # We scan all channels since drum tracks may not always be on ch10.
    events: Dict[str, List[Tuple[float, int]]] = defaultdict(list)

    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                inst_class = classify_pitch(msg.note)
                if inst_class:
                    events[inst_class].append((abs_tick, msg.velocity))

    if not events:
        return None

    # Find total bars in the file.
    max_tick = 0
    for evts in events.values():
        if evts:
            max_tick = max(max_tick, max(t for t, _ in evts))

    total_bars = max(1, int(max_tick / ticks_per_bar) + 1)

    # Quantize into bars and steps.
    result: Dict[str, List[List[Tuple[int, int]]]] = {}
    for inst_class, evts in events.items():
        bars: List[List[Tuple[int, int]]] = [[] for _ in range(total_bars)]
        for tick, vel in evts:
            bar_idx = int(tick / ticks_per_bar)
            tick_in_bar = tick - bar_idx * ticks_per_bar
            step = int(round(tick_in_bar / ticks_per_step))
            step = max(0, min(steps_per_bar - 1, step))
            if bar_idx < total_bars:
                bars[bar_idx].append((step, vel))
        result[inst_class] = bars

    return result


# ---------------------------------------------------------------------------
# Statistical Groove Profile
# ---------------------------------------------------------------------------

class GrooveProfile:
    """Accumulates hit statistics across many bars for a single genre.

    Tracks per-step hit counts and velocity sums for each instrument class,
    enabling computation of hit probabilities and average velocities.
    """

    def __init__(self, steps_per_bar: int = STEPS_PER_BAR):
        self.steps = steps_per_bar
        # Per-step hit counts for each instrument class.
        self.hits: Dict[str, List[int]] = defaultdict(lambda: [0] * self.steps)
        # Per-step velocity sums (for average velocity computation).
        self.vel_sums: Dict[str, List[float]] = defaultdict(lambda: [0.0] * self.steps)
        self.total_bars = 0
        self.files_loaded = 0
        self.files_failed = 0

    def add_file(self, quantized: Dict[str, List[List[Tuple[int, int]]]]) -> None:
        """Add quantized data from one MIDI file."""
        bar_count = 0
        for inst_class, bars in quantized.items():
            for bar in bars:
                if not bar:
                    continue
                bar_count = max(bar_count, 1)
                for step, vel in bar:
                    self.hits[inst_class][step] += 1
                    self.vel_sums[inst_class][step] += vel

        # Count bars from the longest instrument track.
        max_bars = max((len(bars) for bars in quantized.values()), default=0)
        self.total_bars += max_bars
        self.files_loaded += 1

    def step_probability(self, inst_class: str, step: int) -> float:
        """Return the probability of a hit at this step (0.0 to 1.0)."""
        if self.total_bars == 0:
            return 0.0
        return self.hits[inst_class][step] / self.total_bars

    def step_avg_velocity(self, inst_class: str, step: int) -> float:
        """Return the average velocity at this step."""
        count = self.hits[inst_class][step]
        if count == 0:
            return 0.0
        return self.vel_sums[inst_class][step] / count

    def probabilities(self, inst_class: str) -> List[float]:
        """Return hit probabilities for all steps."""
        return [self.step_probability(inst_class, s) for s in range(self.steps)]


# ---------------------------------------------------------------------------
# Derive GrooveTemplate Fields
# ---------------------------------------------------------------------------

def derive_recipe(
    profile: GrooveProfile,
    *,
    genre: str,
    bpm_range: Optional[Tuple[int, int]] = None,
    feel: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive a recipe YAML structure from a :class:`GrooveProfile`.

    Analyzes per-step hit probabilities to determine kick/snare patterns,
    ghost note positions, hat mode, swing feel, and other groove parameters.

    Parameters
    ----------
    profile : GrooveProfile
        Accumulated statistics from multiple MIDI files.
    genre : str
        Genre name for the recipe tags.
    bpm_range : tuple of int, optional
        ``(min_bpm, max_bpm)`` for recipe tags.
    feel : str, optional
        Feel descriptor (e.g. ``"shuffle"``, ``"straight"``).

    Returns
    -------
    dict
        Recipe structure ready for YAML serialization.
    """

    kick_probs = profile.probabilities("kick")
    snare_probs = profile.probabilities("snare")
    hat_closed_probs = profile.probabilities("hat_closed")
    hat_open_probs = profile.probabilities("hat_open")
    ride_probs = profile.probabilities("ride")
    crash_probs = profile.probabilities("crash")

    # --- kick_base: steps where P(kick) > 0.30 ---
    kick_base = [s for s in range(STEPS_PER_BAR) if kick_probs[s] > 0.30]
    if not kick_base:
        kick_base = [0]  # Fallback: at least the downbeat

    # --- kick_extra_rate: mean P of kick steps NOT in kick_base ---
    non_base_kick = [kick_probs[s] for s in range(STEPS_PER_BAR) if s not in kick_base]
    kick_extra_rate = sum(non_base_kick) / len(non_base_kick) if non_base_kick else 0.0

    # --- double_kick_rate: P of kick on steps 14-15 (end of bar) ---
    end_kicks = [kick_probs[s] for s in [14, 15] if s not in kick_base]
    double_kick_rate = sum(end_kicks) / max(len(end_kicks), 1)

    # --- snare_backbeat_steps: steps with P(snare) in the top tier ---
    max_snare_p = max(snare_probs) if any(snare_probs) else 0.0
    snare_threshold = max(0.25, max_snare_p * 0.60)
    snare_backbeat = [s for s in range(STEPS_PER_BAR) if snare_probs[s] >= snare_threshold]
    if not snare_backbeat:
        snare_backbeat = [4, 12]  # Standard backbeat

    # --- ghost_rate & ghost_steps ---
    snare_non_backbeat = sorted(
        [(s, snare_probs[s]) for s in range(STEPS_PER_BAR)
         if s not in snare_backbeat and snare_probs[s] > 0.03],
        key=lambda x: -x[1],
    )[:6]
    ghost_steps = sorted(s for s, _ in snare_non_backbeat)
    ghost_rate = (
        sum(p for _, p in snare_non_backbeat) / len(snare_non_backbeat)
        if snare_non_backbeat
        else 0.0
    )

    # --- hat_mode: classify hat density ---
    hat_active_steps = sum(1 for p in hat_closed_probs if p > 0.15)

    if hat_active_steps >= 14:
        hat_mode = "16th"
    elif hat_active_steps >= 6:
        hat_mode = "8th"
    else:
        hat_mode = "quarter"

    # --- use_ride: if ride hits rival or exceed hat hits ---
    hat_total = sum(hat_closed_probs)
    ride_total = sum(ride_probs)
    use_ride = ride_total > hat_total * 0.8

    # --- open_hat_rate: mean P of open hat on "&" steps (odd steps) ---
    and_steps = [1, 3, 5, 7, 9, 11, 13, 15]
    open_hat_and = [hat_open_probs[s] for s in and_steps]
    open_hat_rate = sum(open_hat_and) / len(open_hat_and) if open_hat_and else 0.0

    # --- crash_start: P(crash on step 0) > 0.20 ---
    crash_start = crash_probs[0] > 0.20

    # --- crash_phrase_end_rate: P(crash on step 0) overall ---
    crash_phrase_end_rate = crash_probs[0] if crash_probs[0] > 0.05 else 0.0

    # --- Build tags ---
    tags: Dict[str, Any] = {
        "genre": genre,
        "time_signature": "4/4",
        "section_types": ["verse", "chorus"],
    }
    if bpm_range:
        tags["bpm_range"] = list(bpm_range)
    if feel:
        tags["feel"] = feel

    # --- Derive swing from hat pattern ---
    even_hat = sum(hat_closed_probs[s] for s in range(0, STEPS_PER_BAR, 2))
    odd_hat = sum(hat_closed_probs[s] for s in range(1, STEPS_PER_BAR, 2))
    even_ride = sum(ride_probs[s] for s in range(0, STEPS_PER_BAR, 2))
    odd_ride = sum(ride_probs[s] for s in range(1, STEPS_PER_BAR, 2))

    # Use whichever cymbal has more activity.
    if (even_ride + odd_ride) > (even_hat + odd_hat):
        even_cym, odd_cym = even_ride, odd_ride
    else:
        even_cym, odd_cym = even_hat, odd_hat

    swing = 0.0
    if even_cym > 0 and odd_cym > 0.3:
        swing_ratio = odd_cym / even_cym
        if swing_ratio < 0.3:
            swing = 0.35
        elif swing_ratio < 0.5:
            swing = 0.20
        elif swing_ratio < 0.8:
            swing = 0.10

    # --- Assemble recipe ---
    recipe: Dict[str, Any] = {
        "id": _genre_to_recipe_id(genre, feel),
        "instrument": "drums",
        "tags": tags,
        "groove": {
            "hat_mode": hat_mode,
            "use_ride": use_ride,
            "kick_base": kick_base,
            "kick_extra_rate": _round(kick_extra_rate),
            "double_kick_rate": _round(double_kick_rate),
            "snare_backbeat_steps": snare_backbeat,
            "ghost_rate": _round(ghost_rate),
            "ghost_steps": ghost_steps if ghost_steps else [7, 15],
            "open_hat_rate": _round(open_hat_rate),
            "crash_start": crash_start,
            "crash_phrase_end_rate": _round(crash_phrase_end_rate),
        },
        "params": {},
        "voices": {},
    }

    if swing > 0:
        recipe["params"]["swing"] = _round(swing)

    # Add fill_rate heuristic: busier genres get more fills.
    kick_density = len(kick_base) / STEPS_PER_BAR
    if kick_density > 0.2:
        recipe["params"]["fill_rate"] = _round(min(0.35, kick_density * 0.8))
    else:
        recipe["params"]["fill_rate"] = 0.15

    return recipe


def _round(v: float, decimals: int = 2) -> float:
    """Round a float to N decimals."""
    return round(v, decimals)


def _genre_to_recipe_id(genre: str, feel: Optional[str] = None) -> str:
    """Convert genre + feel into a recipe id."""
    base = genre.strip().lower().replace(" ", "_").replace("-", "_")
    if feel:
        return f"{base}_{feel.strip().lower()}"
    return base


# ---------------------------------------------------------------------------
# Manifest Processing
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load a YAML manifest (as produced by :mod:`build_drum_manifest`)."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def group_folders_by_genre(
    manifest: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group manifest folders by their primary genre.

    Returns
    -------
    dict
        ``{genre: [folder_entry, ...]}``
    """
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for folder in manifest.get("folders", []):
        genres = folder.get("genres", [])
        if genres:
            # Use first (primary) genre.
            primary = str(genres[0]).strip().lower()
            groups[primary].append(folder)
    return dict(groups)


def collect_bpm_range(folders: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
    """Extract BPM range from folder metadata."""
    bpms: List[int] = []
    for folder in folders:
        for b in folder.get("bpm", []):
            try:
                bpms.append(int(b))
            except (ValueError, TypeError):
                pass
    if not bpms:
        return None
    return (min(bpms), max(bpms))


def collect_feel(folders: List[Dict[str, Any]]) -> Optional[str]:
    """Detect dominant feel from folder metadata."""
    feels: Dict[str, int] = defaultdict(int)
    for folder in folders:
        feel_val = folder.get("feel")
        if feel_val is None:
            continue
        if isinstance(feel_val, str):
            feels[feel_val.strip().lower()] += 1
        elif isinstance(feel_val, list):
            for f in feel_val:
                feels[str(f).strip().lower()] += 1
    if not feels:
        return None
    return max(feels, key=feels.get)


# ---------------------------------------------------------------------------
# Main Training Pipeline
# ---------------------------------------------------------------------------

def _print_probability_grid(profile: GrooveProfile, genre: str) -> None:
    """Print a visual per-step probability grid for debugging."""
    instruments = ["kick", "snare", "hat_closed", "hat_open", "ride", "crash"]
    header = f"  Step:  " + "".join(f"{s:5d}" for s in range(STEPS_PER_BAR))
    print(f"\n  Probability grid for '{genre}' ({profile.total_bars} bars):")
    print(header)
    print("  " + "-" * (9 + 5 * STEPS_PER_BAR))
    for inst in instruments:
        probs = profile.probabilities(inst)
        if max(probs) < 0.01:
            continue
        cells = ""
        for p in probs:
            if p > 0.5:
                cells += f" {p:.2f}"[0:5]
            elif p > 0.1:
                cells += f"  .{int(p*100):02d}"[0:5]
            elif p > 0.01:
                cells += f"  .{int(p*100):02d}"[0:5]
            else:
                cells += "    ."
        print(f"  {inst:>10s} {cells}")
    print()


def train_genre(
    genre: str,
    folders: List[Dict[str, Any]],
    archive_root: Path,
    *,
    max_files: int = 2000,
    verbose: bool = False,
) -> Optional[Dict[str, Any]]:
    """Train a recipe for a single genre from its MIDI files.

    Parameters
    ----------
    genre : str
        Genre name.
    folders : list of dict
        Manifest folder entries for this genre.
    archive_root : Path
        Root path of the MIDI archive.
    max_files : int
        Maximum number of MIDI files to process per genre.
    verbose : bool
        If True, print raw probability grids.

    Returns
    -------
    dict or None
        Recipe dict, or ``None`` if insufficient data.
    """
    profile = GrooveProfile()
    files_processed = 0

    for folder in folders:
        if files_processed >= max_files:
            break

        folder_path = archive_root / folder["path"]
        if not folder_path.is_dir():
            continue

        for filename in folder.get("files", []):
            if files_processed >= max_files:
                break

            filepath = folder_path / filename
            if not filepath.exists():
                continue

            quantized = quantize_midi(filepath)
            if quantized is None:
                profile.files_failed += 1
                continue

            profile.add_file(quantized)
            files_processed += 1

    if profile.files_loaded < 3:
        logger.warning(
            "Genre '%s': only %d files loaded (need >= 3), skipping.",
            genre, profile.files_loaded,
        )
        return None

    logger.info(
        "Genre '%s': loaded %d files (%d bars), %d failed.",
        genre, profile.files_loaded, profile.total_bars, profile.files_failed,
    )

    if verbose:
        _print_probability_grid(profile, genre)

    bpm_range = collect_bpm_range(folders)
    feel = collect_feel(folders)

    recipe = derive_recipe(profile, genre=genre, bpm_range=bpm_range, feel=feel)

    # Add training stats (stripped before writing to YAML).
    recipe["_stats"] = {
        "files_loaded": profile.files_loaded,
        "files_failed": profile.files_failed,
        "total_bars": profile.total_bars,
        "folders": len(folders),
    }

    return recipe


def write_recipe_yaml(recipe: Dict[str, Any], output_path: Path) -> None:
    """Write a recipe dict to a YAML file."""
    # Remove internal stats before writing.
    stats = recipe.pop("_stats", {})

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Auto-generated drum recipe for {recipe['tags']['genre']}\n")
        f.write(f"# Trained from {stats.get('files_loaded', '?')} MIDI files ")
        f.write(f"({stats.get('total_bars', '?')} bars)\n\n")
        yaml.dump(recipe, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info("Wrote recipe: %s", output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Train drum groove recipes from a MIDI archive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Reads a manifest YAML (produced by build_drum_manifest.py), loads MIDI files
by genre, computes per-step hit probabilities on a 16-step grid, and writes
one recipe YAML per genre to the output directory.

Examples:
  python tools/train_drum_recipes.py --manifest manifest.yaml --archive-dir midi/
  python tools/train_drum_recipes.py --manifest m.yaml --archive-dir midi/ --genres funk jazz
  python tools/train_drum_recipes.py --manifest m.yaml --archive-dir midi/ --dry-run --verbose
""",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to the archive manifest YAML (from build_drum_manifest.py)",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        required=True,
        help="Root directory of the MIDI archive",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("produzre/resources/recipes/drums"),
        help="Directory to write recipe YAML files (default: produzre/resources/recipes/drums)",
    )
    parser.add_argument(
        "--genres",
        nargs="*",
        help="Only train these genres (default: all)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=2000,
        help="Max MIDI files to process per genre (default: 2000)",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=3,
        help="Minimum MIDI files required to produce a recipe (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print derived recipes without writing files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw per-step probability grids for debugging",
    )

    args = parser.parse_args(argv)

    # Load manifest.
    if not args.manifest.exists():
        logger.error("Manifest not found: %s", args.manifest)
        logger.error("Generate one first with: python tools/build_drum_manifest.py <archive_dir>")
        sys.exit(1)

    logger.info("Loading manifest: %s", args.manifest)
    manifest = load_manifest(args.manifest)

    meta = manifest.get("meta", {})
    logger.info(
        "Archive: %d files across %d folders",
        meta.get("total_midi_files", 0),
        meta.get("total_folders", 0),
    )

    # Group by genre.
    genre_groups = group_folders_by_genre(manifest)
    logger.info("Found %d genres in manifest.", len(genre_groups))

    # Filter genres if requested.
    if args.genres:
        requested = {g.strip().lower().replace("-", "_") for g in args.genres}
        genre_groups = {g: f for g, f in genre_groups.items() if g in requested}
        if not genre_groups:
            logger.error("No matching genres found. Available: %s",
                         ", ".join(sorted(group_folders_by_genre(manifest).keys())))
            sys.exit(1)

    # Sort genres by folder count (largest first) for better progress feedback.
    sorted_genres = sorted(genre_groups.items(), key=lambda x: -len(x[1]))

    recipes_written = 0
    recipes_skipped = 0

    for genre, folders in sorted_genres:
        total_files = sum(f.get("file_count", 0) for f in folders)
        logger.info(
            "Training '%s': %d folders, ~%d files...",
            genre, len(folders), total_files,
        )

        recipe = train_genre(
            genre, folders, args.archive_dir,
            max_files=args.max_files,
            verbose=args.verbose,
        )

        if recipe is None:
            recipes_skipped += 1
            continue

        if args.dry_run:
            print(f"\n--- {genre} ---")
            yaml.dump(recipe, sys.stdout, default_flow_style=False, sort_keys=False)
            recipes_written += 1
            continue

        output_path = args.output_dir / f"{recipe['id']}.yaml"

        # Don't overwrite hand-authored recipes.
        if output_path.exists():
            try:
                existing_text = output_path.read_text(encoding="utf-8")
                if "Auto-generated" not in existing_text:
                    logger.info(
                        "Skipping '%s': hand-authored recipe exists at %s",
                        genre, output_path,
                    )
                    recipes_skipped += 1
                    continue
            except Exception:
                pass

        write_recipe_yaml(recipe, output_path)
        recipes_written += 1

    logger.info(
        "Done. %d recipes written, %d skipped.",
        recipes_written, recipes_skipped,
    )


if __name__ == "__main__":
    main()
