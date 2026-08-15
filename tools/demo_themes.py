#!/usr/bin/env python
"""Demo: realize song-level themes over a real song's harmony (prototype M1).

Loads a Produzre YAML config (with a top-level ``themes:`` block), builds the
harmony plan for every arranged section using the real planning code, applies
the arrangement-arc transform per section type, and prints the realized notes
so you can watch a theme track the harmony across the song.

Optionally writes a dependency-free MIDI file so the result is audible.

Usage:
    python tools/demo_themes.py examples/themes_demo.yaml
    python tools/demo_themes.py examples/themes_demo.yaml --midi exports/themes_demo.mid
    python tools/demo_themes.py examples/themes_demo.yaml --transform "chorus=octave_shift:octaves=1"
"""

from __future__ import annotations

import argparse
import logging
import struct
import sys
from pathlib import Path

# Allow running from the repo root without installing the package, and pick up
# the workspace-local PyYAML (managed runtime ships without it).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / ".demo_deps"))
sys.path.insert(0, str(_REPO_ROOT))

from produzre.config.load import load_root_config
from produzre.harmony.plan import build_harmony_plan
from produzre.themes.io import parse_themes_block
from produzre.themes.model import ThemeRole
from produzre.themes.realize import realize_theme
from produzre.themes.transform import apply_transform

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Default arrangement arc: section type -> transform applied to each theme.
# This mirrors design doc §9 and exists only in the demo (arc.py is M4).
ARC = {
    "intro": ("fragment", {"keep": "first"}),
    "verse": ("quote", {}),
    "prechorus": ("displace", {"shift_beats": 0.5}),
    "chorus": ("quote", {}),
    "bridge": ("invert", {}),
    "solo": ("sequence", {"steps": 2}),
    "breakdown": ("thin", {}),
    "outro": ("fragment", {"keep": "last"}),
}

# Repeat statements get a development bump: 2nd+ chorus lifts the melody.
REPEAT_ARC = {
    "chorus": {"melody": ("octave_shift", {"octaves": 1})},
}


def note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def parse_override(expr: str):
    """Parse 'type=name:k=v,k=v' into (section_type, (name, params))."""
    type_part, _, rest = expr.partition("=")
    name, _, kv = rest.partition(":")
    params = {}
    for pair in filter(None, kv.split(",")):
        k, _, v = pair.partition("=")
        params[k] = float(v) if "." in v else int(v)
    return type_part.strip(), (name.strip(), params)


# ---------------------------------------------------------------------------
# Minimal dependency-free MIDI writer (single tempo, one track per theme)
# ---------------------------------------------------------------------------

def _varint(n: int) -> bytes:
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _track_chunk(events, name: str, program: int, channel: int, ppq: int) -> bytes:
    body = bytearray()
    body += b"\x00\xff\x03" + _varint(len(name)) + name.encode()
    body += b"\x00" + bytes([0xC0 | channel, program])
    timeline = []
    for on_b, off_b, pitch, vel in events:
        timeline.append((int(round(on_b * ppq)), 1, bytes([0x80 | channel, pitch, 0])))
        timeline.append((int(round(off_b * ppq)), 1, bytes([0x80 | channel, pitch, 0])))
        timeline.append((int(round(on_b * ppq)), 0, bytes([0x90 | channel, pitch, vel])))
    timeline.sort(key=lambda t: (t[0], t[1]))
    last = 0
    for tick, _order, msg in timeline:
        body += _varint(tick - last) + msg
        last = tick
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def write_midi(path: Path, bpm: float, tracks) -> None:
    ppq = 480
    us_per_qn = int(60_000_000 / bpm)
    cond = b"\x00\xff\x51\x03" + us_per_qn.to_bytes(3, "big") + b"\x00\xff\x2f\x00"
    data = b"MThd" + struct.pack(">IHHH", 6, 1, 1 + len(tracks), ppq)
    data += b"MTrk" + struct.pack(">I", len(cond)) + cond
    for name, program, channel, events in tracks:
        data += _track_chunk(events, name, program, channel, ppq)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config", help="Path to a Produzre YAML config")
    ap.add_argument("--midi", metavar="OUT.mid", help="Also write a playable MIDI file")
    ap.add_argument(
        "--legato",
        action="store_true",
        help="Extend each note to the next onset (sustain; themes are authored "
             "staccato-agnostic, so this better represents how an engine plays them)",
    )
    ap.add_argument(
        "--transform",
        action="append",
        default=[],
        metavar="TYPE=name:k=v",
        help="Override the arc transform for a section type (repeatable)",
    )
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger("produzre.demo")

    arc = dict(ARC)
    for expr in args.transform:
        sec_type, spec = parse_override(expr)
        arc[sec_type] = spec

    cfg = load_root_config(args.config)
    bank = parse_themes_block(cfg.raw.get("themes"), logger)
    if not bank.themes:
        print("No 'themes:' block found in the config; nothing to realize.")
        return 1

    print(f"\nTheme bank: {len(bank.themes)} theme(s), hash {bank.seed_material_hash}")
    for theme in bank.themes.values():
        spelled = " ".join(
            f"{e.degree_label()}:{e.duration_beats:g}" for e in theme.events
        )
        print(f"  {theme.name:<14} role={theme.role.value:<10} "
              f"len={theme.length_beats:g} beats  register={theme.base_register}")
        print(f"    {spelled}")

    song_key = cfg.song.key
    song_mode = cfg.song.mode
    genre = cfg.song.genre or ""

    seen_types: dict[str, int] = {}
    song_beat = 0.0
    midi_events: dict[str, list] = {name: [] for name in bank.themes}

    for sec_id in cfg.arrangement:
        section = cfg.sections[sec_id]
        hplan = build_harmony_plan(cfg, section, logger)
        if hplan is None or not hplan.chord_slots:
            print(f"\n=== {sec_id} ({section.type}) — no harmony plan, skipped")
            continue

        key = section.key or song_key
        mode = section.mode or song_mode
        occurrence = seen_types.get(section.type, 0)
        seen_types[section.type] = occurrence + 1

        print(f"\n=== {sec_id} ({section.type}, {hplan.total_beats:g} beats, "
              f"key {key} {mode}, occurrence {occurrence + 1})")
        slots = "  ".join(
            f"[{s.start_beat:g}-{s.end_beat:g}) {s.numeral}" for s in hplan.chord_slots
        )
        print(f"  chords: {slots}")

        for theme in bank.themes.values():
            transform_name, params = arc.get(section.type, ("quote", {}))
            repeat_spec = REPEAT_ARC.get(section.type, {}).get(theme.role.value)
            if repeat_spec and occurrence > 0:
                transform_name, params = repeat_spec
            developed = apply_transform(theme, transform_name, **params)

            notes = realize_theme(
                developed, hplan.chord_slots,
                key=key, mode=mode, genre=genre,
                total_beats=hplan.total_beats,
            )
            print(f"  {theme.name} [{transform_name}]", )
            for n in notes:
                snap = " (snapped)" if n.snapped else ""
                print(f"    beat {n.beat:6.2f}  {note_name(n.pitch):<4} "
                      f"deg {n.degree_label:<3} over {n.numeral:<5}{snap}")
                midi_events[theme.name].append(
                    (song_beat + n.beat, song_beat + n.beat + n.duration_beats,
                     n.pitch, 96 if theme.role is ThemeRole.RIFF else 104)
                )
        song_beat += hplan.total_beats

    if args.midi:
        programs = {ThemeRole.RIFF: (30, 2), ThemeRole.MELODY: (30, 3),
                    ThemeRole.BASS_MOTIF: (33, 1)}
        tracks = []
        for theme in bank.themes.values():
            prog, ch = programs.get(theme.role, (30, 4))
            events = midi_events[theme.name]
            if args.legato:
                # Sustain each note until the next onset on the same track.
                events = sorted(events)
                events = [
                    (on, events[i + 1][0] if i + 1 < len(events) else off,
                     pitch, vel)
                    for i, (on, off, pitch, vel) in enumerate(events)
                ]
            tracks.append((theme.name, prog, ch, events))
        out = Path(args.midi)
        write_midi(out, float(cfg.song.bpm), tracks)
        print(f"\nMIDI written: {out}")

    print("\nDeterminism check: re-parsing bank… ", end="")
    bank2 = parse_themes_block(cfg.raw.get("themes"), logger)
    print("OK" if bank2.seed_material_hash == bank.seed_material_hash else "MISMATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
