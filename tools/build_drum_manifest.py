#!/usr/bin/env python3
"""Build a YAML manifest from a directory tree of drum MIDI files.

Walks an archive directory, classifies each MIDI-containing folder by genre,
region, generation, BPM, time signature, feel, and musical function using
keyword matching against path components, then writes a structured YAML
manifest for downstream training scripts (e.g. :mod:`train_drum_recipes`).

The manifest is **folder-level**: each entry represents a directory containing
``.mid`` files, with metadata extracted from the full path hierarchy.  This
makes it easy to organize MIDI files in genre/artist/album folder structures
and have the metadata inferred automatically.

Metadata extraction
-------------------
- **Genre** — matched from path components against ~60 genre keywords
  (rock, jazz, funk, metal, etc.) plus SD2 kit names and GM MIDI Pack folders.
- **Region** — world music regions (africa, asia, caribbean, etc.).
- **BPM** — extracted from path/filename patterns like ``120bpm``, ``bpm120``,
  or bare 3-digit prefixes.
- **Time signature** — patterns like ``3/4``, ``6/8``, ``3-4``.
- **Feel** — straight, shuffle, swing, triplet, half_time, etc.
- **Function** — fill, intro, ending, groove, loop, verse, chorus, etc.

Usage
-----
    python tools/build_drum_manifest.py /path/to/midi/archive
    python tools/build_drum_manifest.py /path/to/archive --output manifest.yaml
    python tools/build_drum_manifest.py /path/to/archive --compact
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Metadata keyword tables
# ---------------------------------------------------------------------------

# Genre detection: keyword -> canonical genre tag.
# Keywords are matched case-insensitively against path components.
GENRE_KEYWORDS: dict[str, str] = {
    # Rock family
    "rock": "rock",
    "rock'n'roll": "rock_n_roll",
    "rock_n_roll": "rock_n_roll",
    "rockabilly": "rockabilly",
    "classic rock": "rock",
    "indie": "indie",
    "grunge": "grunge",
    "alternative": "alternative",
    "punk": "punk",
    "post-punk": "punk",
    "pop punk": "punk",
    "emo": "emo",
    # Metal family
    "metal": "metal",
    "heavy metal": "metal",
    "thrash": "thrash_metal",
    "death": "death_metal",
    "black metal": "black_metal",
    "doom": "doom_metal",
    "prog metal": "progressive_metal",
    "djent": "djent",
    "metalcore": "metalcore",
    "extreme": "extreme_metal",
    "metal_foundry": "metal",
    # Blues / soul / R&B
    "blues": "blues",
    "soul": "soul",
    "motown": "motown",
    "r&b": "rnb",
    "rnb": "rnb",
    "rb": "rnb",
    "rhythm and blues": "rnb",
    "gospel": "gospel",
    # Jazz
    "jazz": "jazz",
    "bebop": "bebop",
    "cool": "cool_jazz",
    "big band": "big_band",
    "fusion": "fusion",
    # Funk / disco
    "funk": "funk",
    "funky": "funk",
    "disco": "disco",
    "boogie": "boogie",
    # Pop
    "pop": "pop",
    "ballad": "ballad",
    # Country / americana
    "country": "country",
    "americana": "americana",
    "bluegrass": "bluegrass",
    "western": "country",
    "nashville": "country",
    "music_city": "country",
    # Electronic
    "electronic": "electronic",
    "edm": "electronic",
    "techno": "techno",
    "house": "house",
    "trance": "trance",
    "drum_n_bass": "drum_n_bass",
    "dnb": "drum_n_bass",
    "breakbeat": "breakbeat",
    "dubstep": "dubstep",
    "industrial": "industrial",
    "synthwave": "synthwave",
    "electronica": "electronic",
    # Hip-hop
    "hip hop": "hip_hop",
    "hip-hop": "hip_hop",
    "hiphop": "hip_hop",
    "rap": "hip_hop",
    "trap": "trap",
    "boom bap": "boom_bap",
    # Latin / dance
    "latin": "latin",
    "bossa": "bossa_nova",
    "bossa nova": "bossa_nova",
    "samba": "samba",
    "cha cha": "cha_cha",
    "chacha": "cha_cha",
    "mambo": "mambo",
    "salsa": "salsa",
    "rumba": "rumba",
    "cumbia": "cumbia",
    "merengue": "merengue",
    "tango": "tango",
    "paso": "paso_doble",
    "charleston": "charleston",
    # Reggae family
    "reggae": "reggae",
    "ska": "ska",
    "dub": "dub",
    "reggaeton": "reggaeton",
    # Swing / vintage
    "swing": "swing",
    "shuffle": "shuffle",
    "waltz": "waltz",
    "march": "march",
    "twist": "twist",
    "polka": "polka",
    # World / regional (also genres)
    "afro": "afrobeat",
    "afrobeat": "afrobeat",
    "afro-cuban": "afro_cuban",
    "calypso": "calypso",
    "flamenco": "flamenco",
    # Progressive
    "progressive": "progressive",
    "prog": "progressive",
    # Other
    "linear": "linear",
    "odd meter": "odd_meter",
    "cocktail": "cocktail",
    "songwriter": "songwriter",
}

# Region detection
REGION_KEYWORDS: dict[str, str] = {
    "africa": "africa",
    "african": "africa",
    "djembe": "africa",
    "dun": "africa",
    "shakere": "africa",
    "talking drum": "africa",
    "asia": "asia",
    "asian": "asia",
    "tabla": "south_asia",
    "taiko": "east_asia",
    "samul nori": "east_asia",
    "janggu": "east_asia",
    "gamelan": "southeast_asia",
    "south america": "south_america",
    "brazilian": "south_america",
    "cuban": "caribbean",
    "afro-cuban": "caribbean",
    "afro_cuban": "caribbean",
    "caribbean": "caribbean",
    "middle east": "middle_east",
    "arabic": "middle_east",
    "persian": "middle_east",
    "europe": "europe",
    "european": "europe",
    "celtic": "europe",
    "world": "world",
    "world inspire": "world",
    "world beats": "world",
}

# Generation / decade detection (regex patterns)
GENERATION_PATTERNS: list[tuple[str, str]] = [
    (r"\b50.?s\b", "1950s"),
    (r"\b1950", "1950s"),
    (r"\b60.?s\b", "1960s"),
    (r"\b1960", "1960s"),
    (r"\b70.?s\b", "1970s"),
    (r"\b1970", "1970s"),
    (r"\b80.?s\b", "1980s"),
    (r"\b1980", "1980s"),
    (r"\b90.?s\b", "1990s"),
    (r"\b1990", "1990s"),
    (r"\b2000s\b", "2000s"),
    (r"\bmodern\b", "modern"),
    (r"\bvintage\b", "vintage"),
    (r"\bclassic\b", "classic"),
    (r"\bstudio\b", "studio"),
]

# Musical function detection
FUNCTION_KEYWORDS: dict[str, str] = {
    "fill": "fill",
    "fills": "fill",
    "fillpack": "fill",
    "intro": "intro",
    "ending": "ending",
    "outro": "ending",
    "groove": "groove",
    "beat": "groove",
    "loop": "loop",
    "loops": "loop",
    "breakdown": "breakdown",
    "break": "break",
    "bridge": "bridge",
    "verse": "verse",
    "chorus": "chorus",
    "transition": "transition",
    "variation": "variation",
    "theme": "groove",
    "song": "song",
    "song loops": "song",
    "demo": "demo",
    "pattern": "groove",
    "noise": "texture",
    "hi-hat": "texture",
    "percussion": "percussion",
}

# Feel / subdivision
FEEL_KEYWORDS: dict[str, str] = {
    "straight": "straight",
    "shuffle": "shuffle",
    "swing": "swing",
    "triplet": "triplet",
    "halftime": "half_time",
    "half time": "half_time",
    "half_time": "half_time",
    "double time": "double_time",
    "double_time": "double_time",
    "sixteenth": "16th",
    "eighth": "8th",
    "quarternote": "quarter",
    "quarter": "quarter",
}

# SD2 kit name -> genre mapping (common Superior Drummer 2 kit names)
SD2_KIT_GENRES: dict[str, list[str]] = {
    "metal_foundry": ["metal"],
    "the_metal_foundry": ["metal"],
    "dfh": ["rock", "metal"],
    "library_of_the_extreme": ["extreme_metal"],
    "latin_percussion": ["latin"],
    "latin": ["latin"],
    "funk": ["funk"],
    "jazz": ["jazz"],
    "cocktail": ["cocktail", "jazz"],
    "pop_rock": ["pop", "rock"],
    "pop#rock": ["pop", "rock"],
    "americana": ["americana", "country"],
    "roots": ["roots", "americana"],
    "monster_midi": ["mixed"],
    "songwriters": ["songwriter"],
    "custom#vintage": ["vintage"],
    "n.y": ["studio"],
    "new_york": ["studio"],
    "music_city": ["country"],
    "progressive": ["progressive"],
}

# GM MIDI Pack genre folder -> genre mapping
GM_GENRE_MAP: dict[str, list[str]] = {
    "rock": ["rock"],
    "blues": ["blues"],
    "country": ["country"],
    "electronic": ["electronic"],
    "funk": ["funk"],
    "funk hh rb": ["funk", "rnb"],
    "fusion": ["fusion"],
    "jazz": ["jazz"],
    "metal": ["metal"],
    "progressive": ["progressive"],
    "punk": ["punk"],
    "rb": ["rnb"],
    "world beats": ["world"],
    "ac percussion": ["percussion", "world"],
    "twisted": ["experimental"],
}


# ---------------------------------------------------------------------------
# BPM + time signature extraction
# ---------------------------------------------------------------------------

_BPM_RE = [
    re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE),
    re.compile(r"bpm\s*(\d{2,3})", re.IGNORECASE),
    # Bare number at start of filename (GM MIDI Pack style): "060 Blues Rock"
    re.compile(r"^(\d{3})\s"),
    # Number with underscore: "BrownJames_110", "Linear_85"
    re.compile(r"_(\d{2,3})(?:\.|$)"),
]


def _extract_bpm(text: str) -> Optional[int]:
    """Try to extract BPM from a text string."""
    for pat in _BPM_RE:
        m = pat.search(text)
        if m:
            bpm = int(m.group(1))
            if 30 <= bpm <= 300:
                return bpm
    return None


_TIMESIG_RE = re.compile(r"(\d+)\s*[/#]\s*(\d+)")
_TIMESIG_DASH_RE = re.compile(r"(\d+)-(\d+)")


def _extract_time_signature(text: str) -> Optional[str]:
    """Try to extract time signature like 4/4, 6/8, 3/4."""
    m = _TIMESIG_RE.search(text)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if 1 <= num <= 15 and den in (2, 4, 8, 16):
            return f"{num}/{den}"

    # Dash-separated: "3-4" means 3/4
    m = _TIMESIG_DASH_RE.search(text)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if 1 <= num <= 15 and den in (2, 4, 8, 16):
            return f"{num}/{den}"

    # Special: "nothing but three" -> 3/4
    if "three" in text.lower() and "nothing" in text.lower():
        return "3/4"

    return None


# ---------------------------------------------------------------------------
# Metadata extraction from path
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, replace common separators with spaces."""
    t = text.lower()
    t = t.replace("@", " ").replace("#", " ").replace("_", " ").replace("-", " ")
    t = t.replace("\u00b4", "'").replace("`", "'")
    return t


def _tokenize(text: str) -> list[str]:
    """Split normalized text into alphanumeric tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", _normalize(text)) if t]


def _match_keywords(text: str, keyword_map: dict[str, str]) -> list[str]:
    """Find all matching keywords in text, return unique canonical values.

    Matching is done on word boundaries: the text is split into alphanumeric
    tokens, single-word keywords must equal a token exactly, and multi-word
    keywords must match a contiguous token subsequence.  This prevents
    substring false positives like "dublin" -> "dub" or "house" matching
    inside "warehouse".
    """
    tokens = _tokenize(text)
    if not tokens:
        return []
    found: list[str] = []
    # Sort by length descending so longer matches take priority
    for kw, canonical in sorted(keyword_map.items(), key=lambda x: -len(x[0])):
        if canonical in found:
            continue
        kw_tokens = _tokenize(kw)
        if not kw_tokens:
            continue
        n = len(kw_tokens)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == kw_tokens:
                found.append(canonical)
                break
    return found


def _detect_source_library(top_level: str) -> str:
    """Map top-level folder name to a canonical library ID.

    Recognizes common drum sample library naming conventions (Superior
    Drummer 2, GM MIDI Pack, decade-themed packs, etc.).  Falls back to
    a slugified version of the folder name.
    """
    norm = _normalize(top_level)
    if "sd2" in norm:
        return "sd2"
    if "gm midi pack" in norm or "gm_midi_pack" in norm:
        return "gm_midi_pack"
    if "50" in norm and "drummer" in norm:
        return "50s_drummer"
    if "60" in norm and "drummer" in norm:
        return "60s_drummer"
    if "70" in norm and "drummer" in norm:
        return "70s_drummer"
    if "80" in norm and "drummer" in norm:
        return "80s_drummer"
    if "modern" in norm and "drummer" in norm:
        return "modern_drummer"
    if "studio" in norm and "drummer" in norm:
        return "studio_drummer"
    if "vintage" in norm and "drummer" in norm:
        return "vintage_drummer"
    # Use the folder name itself as ID (slugified)
    slug = re.sub(r"[^a-z0-9]+", "_", norm).strip("_")
    return slug or "unknown"


def _extract_sd2_genres(path_parts: list[str]) -> list[str]:
    """Extract genres from SD2-style path components."""
    genres: list[str] = []
    for part in path_parts:
        norm = _normalize(part)
        # Strip numeric prefix: "000003@THE_METAL_FOUNDRY" -> "the metal foundry"
        clean = re.sub(r"^\d+\s*", "", norm).strip()
        for key, genre_list in SD2_KIT_GENRES.items():
            if key in clean:
                for g in genre_list:
                    if g not in genres:
                        genres.append(g)
    return genres


def _extract_gm_genres(path_parts: list[str]) -> list[str]:
    """Extract genres from GM MIDI Pack path components."""
    genres: list[str] = []
    for part in path_parts:
        norm = _normalize(part)
        # GM folder format: "gm - rock 1", "gm - fusion"
        m = re.match(r"gm\s*-\s*(.+?)(?:\s+\d+)?$", norm)
        if m:
            genre_key = m.group(1).strip()
            for key, genre_list in GM_GENRE_MAP.items():
                if key in genre_key:
                    for g in genre_list:
                        if g not in genres:
                            genres.append(g)
        else:
            # Sub-genre folders like "Blues Rock", "Latin"
            # (word-boundary matching; see _match_keywords)
            for canonical in _match_keywords(norm, GENRE_KEYWORDS):
                if canonical not in genres:
                    genres.append(canonical)
    return genres


def extract_folder_metadata(
    rel_path: str,
    filenames: list[str],
) -> dict:
    """Extract all metadata for a folder from its path and file list.

    Parameters
    ----------
    rel_path : str
        Path relative to the archive root directory.
    filenames : list of str
        List of ``.mid`` filenames in this folder.

    Returns
    -------
    dict
        Metadata dict with keys: ``path``, ``library``, ``file_count``,
        ``genres``, ``region``, ``generation``, ``bpm``, ``time_signature``,
        ``feel``, ``function``, ``files``.
    """
    parts = Path(rel_path).parts
    top_level = parts[0] if parts else ""
    library = _detect_source_library(top_level)

    # Combine all path components for keyword search
    full_text = " ".join(parts)

    # --- Genres ---
    if library == "sd2":
        genres = _extract_sd2_genres(list(parts))
    elif library == "gm_midi_pack":
        genres = _extract_gm_genres(list(parts))
    else:
        genres = []

    # General keyword matching across all parts
    for part in parts:
        for g in _match_keywords(part, GENRE_KEYWORDS):
            if g not in genres:
                genres.append(g)

    # --- Region ---
    regions: list[str] = []
    for part in parts:
        for r in _match_keywords(part, REGION_KEYWORDS):
            if r not in regions:
                regions.append(r)

    # --- Generation ---
    generations: list[str] = []
    for pattern, gen in GENERATION_PATTERNS:
        if re.search(pattern, full_text, re.IGNORECASE):
            if gen not in generations:
                generations.append(gen)

    # --- BPM ---
    bpms: set[int] = set()
    # From path components
    for part in parts:
        b = _extract_bpm(part)
        if b:
            bpms.add(b)
    # From filenames (sample a few)
    for fn in filenames[:20]:
        b = _extract_bpm(fn)
        if b:
            bpms.add(b)

    # --- Time signature ---
    time_sigs: list[str] = []
    for part in parts:
        ts = _extract_time_signature(part)
        if ts and ts not in time_sigs:
            time_sigs.append(ts)

    # --- Feel ---
    feels: list[str] = []
    for part in parts:
        for f in _match_keywords(part, FEEL_KEYWORDS):
            if f not in feels:
                feels.append(f)

    # --- Musical function ---
    functions: list[str] = []
    for part in parts:
        for f in _match_keywords(part, FUNCTION_KEYWORDS):
            if f not in functions:
                functions.append(f)
    # Also check filenames for function clues
    fn_text = " ".join(filenames[:20])
    for f in _match_keywords(fn_text, FUNCTION_KEYWORDS):
        if f not in functions:
            functions.append(f)

    return {
        "path": rel_path,
        "library": library,
        "file_count": len(filenames),
        "genres": genres or None,
        "region": regions[0] if regions else None,
        "generation": generations[0] if generations else None,
        "bpm": sorted(bpms) if bpms else None,
        "time_signature": time_sigs[0] if time_sigs else None,
        "feel": feels[0] if feels else None,
        "function": functions or None,
        "files": filenames,
    }


# ---------------------------------------------------------------------------
# YAML streaming writer (avoids loading large manifests into memory)
# ---------------------------------------------------------------------------

def _yaml_quote(s: str) -> str:
    """Quote a string for YAML if it contains special characters."""
    if not s:
        return '""'
    needs_quote = any(c in s for c in ":#{}[]&*!|>'\",@`\u00b4")
    needs_quote = needs_quote or s.startswith(("-", " "))
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _yaml_list_inline(items: list) -> str:
    """Render a short list as inline YAML: [a, b, c]."""
    if not items:
        return "[]"
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(_yaml_quote(item))
        else:
            parts.append(str(item))
    return "[" + ", ".join(parts) + "]"


def _write_folder_entry(f, entry: dict, compact: bool) -> None:
    """Write a single folder entry to the YAML stream."""
    f.write(f'\n  - path: {_yaml_quote(entry["path"])}\n')
    f.write(f'    library: {_yaml_quote(entry["library"])}\n')
    f.write(f'    file_count: {entry["file_count"]}\n')

    if entry.get("genres"):
        f.write(f'    genres: {_yaml_list_inline(entry["genres"])}\n')
    if entry.get("region"):
        f.write(f'    region: {_yaml_quote(entry["region"])}\n')
    if entry.get("generation"):
        f.write(f'    generation: {_yaml_quote(entry["generation"])}\n')
    if entry.get("bpm"):
        f.write(f'    bpm: {_yaml_list_inline(entry["bpm"])}\n')
    if entry.get("time_signature"):
        f.write(f'    time_signature: {_yaml_quote(entry["time_signature"])}\n')
    if entry.get("feel"):
        f.write(f'    feel: {_yaml_quote(entry["feel"])}\n')
    if entry.get("function"):
        f.write(f'    function: {_yaml_list_inline(entry["function"])}\n')

    if not compact and entry.get("files"):
        files = entry["files"]
        # Use inline format for short lists, block for long ones
        if len(files) <= 8:
            f.write(f'    files: {_yaml_list_inline(files)}\n')
        else:
            f.write("    files:\n")
            for fn in sorted(files):
                f.write(f"      - {_yaml_quote(fn)}\n")


# ---------------------------------------------------------------------------
# Main walk
# ---------------------------------------------------------------------------

def build_manifest(
    archive_dir: str,
    output_path: str,
    compact: bool = False,
) -> None:
    """Walk *archive_dir* and write a YAML manifest to *output_path*.

    Parameters
    ----------
    archive_dir : str
        Root directory to scan for MIDI files.
    output_path : str
        Path to write the output YAML manifest.
    compact : bool
        If True, omit individual filenames (folder metadata only).
    """
    archive = Path(archive_dir)
    if not archive.is_dir():
        print(f"Error: directory not found: {archive_dir}", file=sys.stderr)
        sys.exit(1)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {archive_dir} ...")

    # First pass: count totals for the header
    total_files = 0
    total_folders = 0
    library_counts: dict[str, int] = {}

    # Collect folder entries
    folder_entries: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(archive):
        # Sort for determinism
        dirnames.sort()

        midi_files = sorted(
            fn for fn in filenames
            if fn.lower().endswith((".mid", ".midi"))
        )
        if not midi_files:
            continue

        rel_path = os.path.relpath(dirpath, archive)
        entry = extract_folder_metadata(rel_path, midi_files)

        total_files += len(midi_files)
        total_folders += 1

        lib = entry["library"]
        library_counts[lib] = library_counts.get(lib, 0) + len(midi_files)

        folder_entries.append(entry)

        # Progress reporting
        if total_folders % 1000 == 0:
            print(f"  ... {total_folders} folders, {total_files} files so far")

    print(f"Scan complete: {total_folders} folders, {total_files} MIDI files")
    print(f"Writing manifest to {output_path} ...")

    # Sort entries by path for deterministic output
    folder_entries.sort(key=lambda e: e["path"])

    # Build library summary
    libraries = {}
    for lib, count in sorted(library_counts.items(), key=lambda x: -x[1]):
        libraries[lib] = {"file_count": count}

    # Write YAML
    with output.open("w", encoding="utf-8") as f:
        f.write("# Drum MIDI Archive Manifest\n")
        f.write(f"# Generated by tools/build_drum_manifest.py\n")
        f.write(f"# {total_files} MIDI files across {total_folders} folders\n\n")

        f.write("meta:\n")
        f.write(f'  generated: "{datetime.now(timezone.utc).isoformat()}"\n')
        f.write(f"  archive_root: {_yaml_quote(archive_dir)}\n")
        f.write(f"  total_midi_files: {total_files}\n")
        f.write(f"  total_folders: {total_folders}\n")

        f.write("\nlibraries:\n")
        for lib, info in libraries.items():
            f.write(f"  {lib}:\n")
            f.write(f'    file_count: {info["file_count"]}\n')

        f.write(f"\nfolders:\n")
        for entry in folder_entries:
            _write_folder_entry(f, entry, compact=compact)

    file_size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Done. Manifest: {output_path} ({file_size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build a YAML manifest from a directory tree of drum MIDI files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Metadata is automatically extracted from folder names and file paths using
keyword matching.  Recognized patterns include genre names, BPM values,
time signatures, feel descriptors, and drum library naming conventions
(Superior Drummer 2, GM MIDI Pack, etc.).

Examples:
  python tools/build_drum_manifest.py /path/to/midi/archive
  python tools/build_drum_manifest.py /path/to/archive --output manifest.yaml
  python tools/build_drum_manifest.py /path/to/archive --compact
""",
    )
    parser.add_argument(
        "archive_dir",
        help="Root directory containing drum MIDI files (searched recursively)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output YAML path (default: <archive_dir>/manifest.yaml)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Omit individual filenames (folder metadata only)",
    )
    args = parser.parse_args()

    output = args.output or str(Path(args.archive_dir) / "manifest.yaml")
    build_manifest(args.archive_dir, output, compact=args.compact)


if __name__ == "__main__":
    main()
