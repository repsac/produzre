#!/usr/bin/env python3
"""Batch MIDI analysis pipeline.

Scans a directory tree for MIDI files, runs the full 4-phase analysis pipeline
(parse → classify → extract → mine), and aggregates per-genre statistics for
all learnable engine parameters.

MIDI files can be organized any way you like — the tool recursively finds all
.mid/.midi files under the input directory.  Genre metadata is supplied via an
optional manifest file (YAML or JSONL).  Without a manifest, files are analyzed
under the "__unknown__" genre.

Manifest formats
----------------
YAML (list of entries):
    - file: path/to/song.mid
      genres: [rock, blues]
    - file: another.mid
      genres: [jazz]

JSONL (one JSON object per line):
    {"file": "path/to/song.mid", "genres": ["rock", "blues"]}
    {"file": "another.mid", "genres": ["jazz"]}

File paths in manifests are resolved relative to the manifest's parent directory.

Usage
-----
    # Analyze all MIDI files under a directory (no genre info)
    python tools/batch_analyze.py /path/to/midi/files

    # With a manifest providing genre tags
    python tools/batch_analyze.py /path/to/midi/files --manifest manifest.yaml

    # Limit per-genre sample size and set output directory
    python tools/batch_analyze.py /path/to/midi --max-per-genre 80 --output results/

    # Filter to specific genres
    python tools/batch_analyze.py /path/to/midi --manifest m.yaml --genres rock,jazz,funk

Output
------
- ``genre_stats.json``   — per-genre aggregated statistics (mean, median, stdev, etc.)
- ``file_results.jsonl`` — per-file raw analysis results (for debugging / deep dives)
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Dict, List, Optional, Any

# Add tools/ to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent))

from midi_parse import parse_midi_file, MIDIAnalysis
from role_classify import classify_roles
from groove_extract import extract_groove_features
from pattern_mine import extract_patterns

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MIDI file discovery
# ---------------------------------------------------------------------------

MIDI_EXTENSIONS = {".mid", ".midi"}


def discover_midi_files(directory: Path) -> List[Dict]:
    """Recursively find all MIDI files under *directory*.

    Returns a list of ``{"file": <absolute-path>, "genres": []}`` dicts.
    Genre metadata is empty — use :func:`load_manifest` to attach genres.
    """
    entries = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if Path(fname).suffix.lower() in MIDI_EXTENSIONS:
                entries.append({"file": str(Path(root) / fname), "genres": []})
    logger.info("Discovered %d MIDI files under %s", len(entries), directory)
    return entries


# ---------------------------------------------------------------------------
# Manifest loaders
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: Path) -> List[Dict]:
    """Load a YAML or JSONL manifest → list of ``{"file": ..., "genres": [...]}``.

    File paths in the manifest are resolved relative to the manifest's parent
    directory.  The format is auto-detected by extension:

    - ``.yaml`` / ``.yml``: expects a list of dicts with ``file`` and ``genres`` keys.
      Supports nested ``tracks`` lists (artist-block format) for convenience.
    - ``.jsonl`` / ``.json``: one JSON object per line with ``file`` and ``genres``.

    Returns an empty list if the manifest file does not exist.
    """
    if not manifest_path.exists():
        logger.warning("Manifest not found: %s", manifest_path)
        return []

    base_dir = manifest_path.parent
    ext = manifest_path.suffix.lower()

    if ext in (".yaml", ".yml"):
        return _load_yaml_manifest(manifest_path, base_dir)
    elif ext in (".jsonl", ".json"):
        return _load_jsonl_manifest(manifest_path, base_dir)
    else:
        logger.warning("Unknown manifest format %r — trying JSONL", ext)
        return _load_jsonl_manifest(manifest_path, base_dir)


def _load_yaml_manifest(path: Path, base_dir: Path) -> List[Dict]:
    """Parse a YAML manifest file.

    Supports two layouts:

    Flat list::
        - file: song.mid
          genres: [rock]

    Nested (artist-block) list::
        - artist: Someone
          genres: [rock]
          tracks:
            - file: song.mid
              genres: [blues]   # optional per-track override
    """
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        logger.warning("YAML manifest root is not a list — skipping")
        return []

    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Nested (artist-block) format
        if "tracks" in item:
            artist_genres = item.get("genres", [])
            for track in item["tracks"]:
                if not isinstance(track, dict):
                    continue
                rel = track.get("file", "")
                genres = track.get("genres") or artist_genres or []
                entries.append({
                    "file": str(base_dir / rel),
                    "genres": genres,
                })
        # Flat format
        elif "file" in item:
            entries.append({
                "file": str(base_dir / item["file"]),
                "genres": item.get("genres", []),
            })

    return entries


def _load_jsonl_manifest(path: Path, base_dir: Path) -> List[Dict]:
    """Parse a JSONL manifest file (one JSON object per line)."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rel = d.get("file", "")
            entries.append({
                "file": str(base_dir / rel),
                "genres": d.get("genres", []),
            })
    return entries


# ---------------------------------------------------------------------------
# Genre-stratified sampling
# ---------------------------------------------------------------------------

def sample_by_genre(
    entries: List[Dict],
    max_per_genre: int,
    target_genres: Optional[List[str]] = None,
) -> List[Dict]:
    """Return a stratified sample: up to *max_per_genre* files per genre.

    If an entry has multiple genres, it counts toward all of them.
    Files with no genres are bucketed under ``"__unknown__"``.

    Parameters
    ----------
    entries : list of dict
        Each dict has ``"file"`` (path) and ``"genres"`` (list of strings).
    max_per_genre : int
        Maximum number of files to include per genre.
    target_genres : list of str, optional
        If provided, only these genres are sampled (case-insensitive).

    Returns
    -------
    list of dict
        The selected entries (deduplicated by file path).
    """
    import random
    random.seed(42)

    # Build genre → entries index
    genre_pool: Dict[str, List[Dict]] = defaultdict(list)
    target_set = {t.lower() for t in target_genres} if target_genres else None

    for entry in entries:
        gs = entry.get("genres") or ["__unknown__"]
        for g in gs:
            g_norm = g.strip().lower()
            if target_set and g_norm not in target_set:
                continue
            genre_pool[g_norm].append(entry)

    # Sample per genre
    selected_files = set()
    selected = []
    for genre, pool in sorted(genre_pool.items()):
        random.shuffle(pool)
        count = 0
        for entry in pool:
            if count >= max_per_genre:
                break
            fpath = entry["file"]
            if fpath in selected_files:
                count += 1  # Still counts toward genre budget
                continue
            if not Path(fpath).exists():
                continue
            selected_files.add(fpath)
            selected.append(entry)
            count += 1

    return selected


# ---------------------------------------------------------------------------
# Single-file analysis
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    """All analysis results for a single MIDI file."""
    file: str
    genres: List[str]
    error: Optional[str] = None
    bpm: float = 120.0
    time_sig: str = "4/4"
    groove: Optional[Dict] = None
    drums: Optional[Dict] = None
    bass: Optional[Dict] = None
    rhythm: Optional[Dict] = None
    lead: Optional[Dict] = None


def _timeout_handler(signum, frame):
    raise TimeoutError("File analysis exceeded time limit")


def analyze_one(entry: Dict, timeout_sec: int = 30) -> FileResult:
    """Run the full 4-phase pipeline on a single MIDI file.

    Phases:
        1. **Parse** — extract raw MIDI events, tempo, time signature
        2. **Classify** — assign instrument roles (drums, bass, rhythm, lead)
        3. **Groove** — extract swing, syncopation, push/pull
        4. **Patterns** — mine per-role statistics (density, intervals, etc.)

    Parameters
    ----------
    entry : dict
        Must contain ``"file"`` (path) and optionally ``"genres"`` (list).
    timeout_sec : int
        Per-file timeout in seconds (default 30).  Uses ``SIGALRM`` on
        Unix systems; on Windows the timeout is not enforced.

    Returns
    -------
    FileResult
        Populated result dataclass.  Check ``.error`` for failures.
    """
    fpath = entry["file"]
    genres = entry.get("genres", [])
    result = FileResult(file=fpath, genres=genres)

    # Set per-file timeout (Unix only)
    use_alarm = hasattr(signal, "SIGALRM")
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_sec)

    try:
        path = Path(fpath)
        song_id = path.stem

        # Phase 1: Parse
        analysis = parse_midi_file(path, song_id)
        if analysis.parse_error:
            result.error = analysis.parse_error
            return result

        if not analysis.events:
            result.error = "no events"
            return result

        # Extract BPM and time sig
        if analysis.tempo_map:
            result.bpm = analysis.tempo_map[0][1]
        if analysis.time_sigs:
            _, num, den = analysis.time_sigs[0]
            result.time_sig = f"{num}/{den}"

        # Phase 2: Classify roles
        roles = classify_roles(analysis)
        role_map = {}
        for rc in roles:
            if rc.confidence >= 0.4:
                key = (rc.track_name, rc.channel)
                role_map[key] = rc.role

        # Build per-role event lists
        role_events: Dict[str, list] = defaultdict(list)
        for ev in analysis.events:
            key = (ev.track_name, ev.channel)
            role = role_map.get(key, "other")
            role_events[role].append(ev)

        # Phase 3: Groove
        groove = extract_groove_features(analysis)
        result.groove = asdict(groove)

        # Phase 4: Pattern mining (returns dict: role_name → dataclass)
        profiles = extract_patterns(analysis, roles)
        if "drums" in profiles:
            result.drums = asdict(profiles["drums"])
        if "bass" in profiles:
            result.bass = asdict(profiles["bass"])
        if "rhythm" in profiles:
            result.rhythm = asdict(profiles["rhythm"])
        if "lead" in profiles:
            result.lead = asdict(profiles["lead"])

    except Exception as e:
        result.error = str(e)
    finally:
        if use_alarm:
            signal.alarm(0)  # Cancel pending alarm
            signal.signal(signal.SIGALRM, old_handler)

    return result


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class GenreStats:
    """Accumulator for per-genre statistics across multiple files."""
    genre: str
    file_count: int = 0
    # BPM
    bpm_values: List[float] = field(default_factory=list)
    # Groove
    swing_values: List[float] = field(default_factory=list)
    push_pull_values: List[float] = field(default_factory=list)
    syncopation_values: List[float] = field(default_factory=list)
    accent_values: List[float] = field(default_factory=list)
    # Drums
    drum_kick_density: List[float] = field(default_factory=list)
    drum_snare_density: List[float] = field(default_factory=list)
    drum_hat_density: List[float] = field(default_factory=list)
    drum_ghost_ratio: List[float] = field(default_factory=list)
    drum_accent_ratio: List[float] = field(default_factory=list)
    drum_fill_density: List[float] = field(default_factory=list)
    drum_kick_onbeat_ratio: List[float] = field(default_factory=list)
    drum_snare_backbeat_ratio: List[float] = field(default_factory=list)
    drum_hat_offbeat_ratio: List[float] = field(default_factory=list)
    drum_polyphony: List[float] = field(default_factory=list)
    # Bass
    bass_notes_per_bar: List[float] = field(default_factory=list)
    bass_root_ratio: List[float] = field(default_factory=list)
    bass_step_ratio: List[float] = field(default_factory=list)
    bass_leap_avg: List[float] = field(default_factory=list)
    bass_onbeat_ratio: List[float] = field(default_factory=list)
    bass_syncopation: List[float] = field(default_factory=list)
    bass_staccato_ratio: List[float] = field(default_factory=list)
    bass_avg_sustain: List[float] = field(default_factory=list)
    bass_rest_ratio: List[float] = field(default_factory=list)
    bass_pitch_low: List[int] = field(default_factory=list)
    bass_pitch_high: List[int] = field(default_factory=list)
    # Rhythm guitar
    rg_chords_per_bar: List[float] = field(default_factory=list)
    rg_strum_polyphony: List[float] = field(default_factory=list)
    rg_downbeat_ratio: List[float] = field(default_factory=list)
    rg_upbeat_ratio: List[float] = field(default_factory=list)
    rg_sustained_ratio: List[float] = field(default_factory=list)
    rg_pitch_spread: List[float] = field(default_factory=list)
    rg_palm_mute_ratio: List[float] = field(default_factory=list)
    rg_accent_variation: List[float] = field(default_factory=list)


def _safe_append(lst, d, key):
    """Append value from dict to list if key exists and value is numeric."""
    v = d.get(key)
    if v is not None and isinstance(v, (int, float)) and v == v:  # not NaN
        lst.append(float(v))


def accumulate_result(stats: GenreStats, result: FileResult):
    """Add a single file's results to the genre stats accumulator."""
    stats.file_count += 1
    stats.bpm_values.append(result.bpm)

    if result.groove:
        _safe_append(stats.swing_values, result.groove, "swing_ratio")
        _safe_append(stats.push_pull_values, result.groove, "push_pull_ms")
        _safe_append(stats.syncopation_values, result.groove, "syncopation_intensity")
        _safe_append(stats.accent_values, result.groove, "accent_strength")

    if result.drums:
        d = result.drums
        _safe_append(stats.drum_kick_density, d, "kick_density")
        _safe_append(stats.drum_snare_density, d, "snare_density")
        _safe_append(stats.drum_hat_density, d, "hat_density")
        _safe_append(stats.drum_ghost_ratio, d, "velocity_ghost_ratio")
        _safe_append(stats.drum_accent_ratio, d, "velocity_accent_ratio")
        _safe_append(stats.drum_fill_density, d, "fill_density")
        _safe_append(stats.drum_kick_onbeat_ratio, d, "kick_onbeat_ratio")
        _safe_append(stats.drum_snare_backbeat_ratio, d, "snare_backbeat_ratio")
        _safe_append(stats.drum_hat_offbeat_ratio, d, "hat_offbeat_ratio")
        _safe_append(stats.drum_polyphony, d, "polyphony_avg")

    if result.bass:
        b = result.bass
        _safe_append(stats.bass_notes_per_bar, b, "notes_per_bar")
        _safe_append(stats.bass_root_ratio, b, "root_note_ratio")
        _safe_append(stats.bass_step_ratio, b, "step_motion_ratio")
        _safe_append(stats.bass_leap_avg, b, "leap_avg")
        _safe_append(stats.bass_onbeat_ratio, b, "on_beat_ratio")
        _safe_append(stats.bass_syncopation, b, "syncopation")
        _safe_append(stats.bass_staccato_ratio, b, "staccato_ratio")
        _safe_append(stats.bass_avg_sustain, b, "sustain_avg")
        _safe_append(stats.bass_rest_ratio, b, "rest_ratio")

    if result.rhythm:
        r = result.rhythm
        _safe_append(stats.rg_chords_per_bar, r, "chords_per_bar")
        _safe_append(stats.rg_strum_polyphony, r, "avg_chord_notes")
        _safe_append(stats.rg_downbeat_ratio, r, "downbeat_ratio")
        _safe_append(stats.rg_upbeat_ratio, r, "upbeat_ratio")
        _safe_append(stats.rg_sustained_ratio, r, "sustained_ratio")
        _safe_append(stats.rg_pitch_spread, r, "pitch_spread")
        _safe_append(stats.rg_palm_mute_ratio, r, "palm_mute_guess")
        _safe_append(stats.rg_accent_variation, r, "accent_variation")


def _summarize(values: List[float]) -> Optional[Dict]:
    """Summarize a list of values → {mean, median, stdev, min, max, n}."""
    if not values:
        return None
    s = {"n": len(values), "mean": round(mean(values), 4), "median": round(median(values), 4)}
    s["min"] = round(min(values), 4)
    s["max"] = round(max(values), 4)
    if len(values) >= 2:
        s["stdev"] = round(stdev(values), 4)
    return s


def summarize_genre(stats: GenreStats) -> Dict:
    """Convert a :class:`GenreStats` accumulator to a summary dict.

    Each list field is reduced to ``{mean, median, stdev, min, max, n}``.
    """
    out = {"genre": stats.genre, "file_count": stats.file_count}
    for fname in vars(stats):
        val = getattr(stats, fname)
        if isinstance(val, list) and val and fname != "genre":
            summary = _summarize([float(v) for v in val])
            if summary:
                out[fname] = summary
    return out


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch MIDI analysis pipeline — analyzes MIDI files and "
                    "aggregates per-genre statistics for engine parameters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all .mid files under a directory
  python tools/batch_analyze.py ~/midi-collection

  # With a manifest providing genre tags
  python tools/batch_analyze.py ~/midi-collection -m manifest.yaml

  # Filter to specific genres, limit sample size
  python tools/batch_analyze.py ~/midi -m m.yaml --genres rock,jazz --max-per-genre 50

  # Custom output directory
  python tools/batch_analyze.py ~/midi --output analysis-results/
""",
    )
    parser.add_argument("input_dir", type=str,
                        help="Directory containing MIDI files (searched recursively)")
    parser.add_argument("-m", "--manifest", type=str, default=None,
                        help="Path to a YAML or JSONL manifest with genre metadata")
    parser.add_argument("--max-per-genre", type=int, default=80,
                        help="Max files to sample per genre (default: 80)")
    parser.add_argument("--output", type=str, default="analysis_output",
                        help="Output directory for results (default: analysis_output)")
    parser.add_argument("--genres", type=str, default=None,
                        help="Comma-separated list of genres to include (default: all)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Per-file analysis timeout in seconds (default: 30)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover or load MIDI files
    if args.manifest:
        manifest_path = Path(args.manifest)
        logger.info("Loading manifest: %s", manifest_path)
        all_entries = load_manifest(manifest_path)
        logger.info("  → %d entries from manifest", len(all_entries))
    else:
        all_entries = discover_midi_files(input_dir)

    if not all_entries:
        logger.error("No MIDI files found. Check the input directory or manifest.")
        sys.exit(1)

    # Parse target genres
    target_genres = None
    if args.genres:
        target_genres = [g.strip() for g in args.genres.split(",") if g.strip()]
        logger.info("Filtering to genres: %s", target_genres)

    # Sample
    logger.info("Sampling up to %d files per genre...", args.max_per_genre)
    sample = sample_by_genre(all_entries, args.max_per_genre, target_genres)
    logger.info("Selected %d unique files to analyze", len(sample))

    # Count genres in sample
    genre_counts = Counter()
    for e in sample:
        for g in (e.get("genres") or ["__unknown__"]):
            genre_counts[g.strip().lower()] += 1
    logger.info("Genre distribution in sample:")
    for g, c in genre_counts.most_common(40):
        logger.info("  %5d  %s", c, g)

    # Run analysis
    genre_accumulators: Dict[str, GenreStats] = {}
    results = []
    errors = 0
    t0 = time.time()

    for i, entry in enumerate(sample):
        if (i + 1) % 50 == 0 or i == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info("  [%d/%d] %.1f files/sec  (errors: %d)",
                        i + 1, len(sample), rate, errors)

        result = analyze_one(entry, timeout_sec=args.timeout)
        results.append(result)

        if result.error:
            errors += 1
            continue

        # Accumulate into genre stats
        for g in (entry.get("genres") or ["__unknown__"]):
            g_norm = g.strip().lower()
            if g_norm not in genre_accumulators:
                genre_accumulators[g_norm] = GenreStats(genre=g_norm)
            accumulate_result(genre_accumulators[g_norm], result)

    elapsed = time.time() - t0
    logger.info("Analysis complete: %d files in %.1fs (%.1f/sec), %d errors",
                len(sample), elapsed, len(sample) / elapsed if elapsed > 0 else 0, errors)

    # Summarize
    genre_summaries = []
    for g_norm in sorted(genre_accumulators.keys()):
        summary = summarize_genre(genre_accumulators[g_norm])
        genre_summaries.append(summary)

    # Write outputs
    summary_path = out_dir / "genre_stats.json"
    with open(summary_path, "w") as f:
        json.dump(genre_summaries, f, indent=2)
    logger.info("Wrote genre stats: %s (%d genres)", summary_path, len(genre_summaries))

    results_path = out_dir / "file_results.jsonl"
    with open(results_path, "w") as f:
        for r in results:
            f.write(json.dumps(asdict(r), default=str) + "\n")
    logger.info("Wrote per-file results: %s (%d files)", results_path, len(results))

    # Quick summary to stdout
    print("\n" + "=" * 70)
    print("GENRE ANALYSIS SUMMARY")
    print("=" * 70)
    for s in genre_summaries:
        g = s["genre"]
        n = s["file_count"]
        bpm = s.get("bpm_values", {})
        swing = s.get("swing_values", {})
        bass_npb = s.get("bass_notes_per_bar", {})
        drum_kd = s.get("drum_kick_density", {})

        line = f"{g:25s}  n={n:3d}"
        if bpm:
            line += f"  bpm={bpm.get('median', '?'):6.1f}"
        if swing:
            line += f"  swing={swing.get('mean', '?'):.3f}"
        if bass_npb:
            line += f"  bass_npb={bass_npb.get('mean', '?'):.2f}"
        if drum_kd:
            line += f"  kick_dens={drum_kd.get('mean', '?'):.2f}"
        print(line)

    print(f"\nFull results: {summary_path}")


if __name__ == "__main__":
    main()
