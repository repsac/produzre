"""Album diversity benchmark: do the songs of one album sound alike?

Writes an album of song configs the way a user would (one genre, varied
keys, tempos, modes, progressions, and seeds, a conventional form), builds
them, and fingerprints every part. Reports, per instrument and section type,
how similar the songs are to each other, and how often recurring devices
appear across the album: the habits a listener would learn to recognize as
"the generator's sound".

Similarity is the mean pairwise Jaccard index between songs' modal bar
patterns (the onset/voice set most often played in that section), so 1.0
means every song plays the same bar. Lower is more varied.

Usage:
    python tools/album_diversity.py --genre hard_rock --songs 10 --out /tmp/album
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import itertools
import json
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile
from typing import Dict, List

import yaml

KEYS = ["E", "A", "D", "G", "C", "F#", "B", "Eb"]
PROGRESSIONS = {
    "minor": {
        "verse": ["i bVII bVI bVII", "i iv bVII i", "i bVI bIII bVII", "i i bVII iv",
                  "i bIII bVII iv", "i v bVI bVII"],
        "prechorus": ["bVI bVII bVI bVII", "iv bVI bVII bVII", "bIII bVII iv iv"],
        "chorus": ["i bVII bVI bVII", "bVI bVII i i", "i bIII bVII bVI", "bVI bIII bVII i"],
        "bridge": ["bVI bVII iv v", "iv v bVI bVII", "bII i bII i"],
    },
    "major": {
        "verse": ["I bVII IV I", "I IV I V", "I V IV IV", "I bVII bVI bVII"],
        "prechorus": ["IV V IV V", "vi IV V V", "ii IV V V"],
        "chorus": ["I V vi IV", "IV V I I", "I bVII IV I", "vi IV I V"],
        "bridge": ["vi IV I V", "bVI bVII I I", "IV iv I I"],
    },
}


# Corpus harmony is intentionally separate from the composer being measured.
GENRE_PROGRESSIONS = {
    "country": ["I IV V I", "I I IV V", "I vi IV V", "I IV I V"],
    "pop": ["I V vi IV", "vi IV I V", "I vi ii V", "IV I V vi"],
    "reggae": ["I IV V IV", "I V vi IV", "vi IV I V", "I ii IV V"],
    "funk": ["i7 i7 iv7 i7", "i7 iv7 i7 bVII", "I7 IV7 I7 V7", "i7 bVII i7 iv7"],
    "jazz": ["ii7 V7 Imaj7 Imaj7", "Imaj7 vi7 ii7 V7", "IVmaj7 ii7 V7 Imaj7"],
}


def album_configs(genre: str, songs: int, seed: int = 1, instruments=None, meter="4/4") -> List[dict]:
    rng = random.Random(seed)
    selected = tuple(instruments or ("drums", "bass", "rhythm_gtr", "lead_gtr"))
    out = []
    for i in range(songs):
        mode = "minor" if rng.random() < 0.7 else "major"
        family = next((g for g in GENRE_PROGRESSIONS if g in genre.lower()), None)
        if family:
            mode = "minor" if family == "funk" else "major"
        prog = PROGRESSIONS[mode] if family is None else {
            st: GENRE_PROGRESSIONS[family] for st in ("verse", "prechorus", "chorus", "bridge")}

        instruments = {"harmony": {}, "drums": {}, "bass": {}, "rhythm_gtr": {}}
        with_lead = dict(instruments, lead_gtr={})
        sections = {
            "intro": {"type": "intro", "bars": 4, "harmony": {"progression": rng.choice(prog["verse"])},
                      "instruments": with_lead},
            "verse": {"type": "verse", "bars": 8, "harmony": {"progression": rng.choice(prog["verse"])},
                      "instruments": instruments},
            "prechorus": {"type": "prechorus", "bars": 4,
                          "harmony": {"progression": rng.choice(prog["prechorus"])},
                          "instruments": instruments},
            "chorus": {"type": "chorus", "bars": 8, "harmony": {"progression": rng.choice(prog["chorus"])},
                       "instruments": with_lead},
            "bridge": {"type": "bridge", "bars": 8, "harmony": {"progression": rng.choice(prog["bridge"])},
                       "instruments": instruments},
            "solo": {"type": "solo", "bars": 8, "harmony": {"progression": rng.choice(prog["verse"])},
                     "instruments": with_lead},
            "outro": {"type": "outro", "bars": 4, "harmony": {"progression": rng.choice(prog["verse"])},
                      "instruments": with_lead},
        }
        out.append({
            "version": 1,
            "song": {"title": f"Album {genre} {i + 1:02d}", "genre": genre, "key": rng.choice(KEYS),
                     "mode": mode, "bpm": rng.randrange(96, 168, 4), "meter": meter,
                     "seed": 1000 + (seed - 1) * 100003 + i * 37, "exports_root": "exports"},
            "exports": {"midi_text": {"enabled": True, "views": ["events"], "subdiv": 16}},
            "sections": sections,
            "arrangement": ["intro", "verse", "prechorus", "chorus", "verse", "prechorus", "chorus",
                            "bridge", "solo", "chorus", "outro"],
        })
        for section in out[-1]["sections"].values():
            section["instruments"] = {"harmony": {}, **{n: {} for n in selected
                if n != "lead_gtr" or len(selected) == 1 or "lead_gtr" in section["instruments"]}}
        if selected == ("acoustic_gtr",):
            out[-1]["instruments"] = {"acoustic_gtr": {"params": {"technique": "fingerpicking"}}}
        if len(selected) == 1:
            out[-1]["song"]["title"] += " " + selected[0]
    return out


def _events(root: str, inst: str) -> List[dict]:
    f = glob.glob(f"{root}/analysis/{inst}/*.events.tsv")
    return list(csv.DictReader(open(f[0]), delimiter="\t")) if f else []


_DRUM_CLASS = {35: "K", 36: "K", 38: "S", 40: "S", 37: "S", 42: "H", 44: "H", 46: "O",
               51: "R", 59: "R", 53: "R", 49: "C", 57: "C", 52: "C", 55: "C",
               41: "T", 43: "T", 45: "T", 47: "T", 48: "T", 50: "T"}


def modal_bars(events: List[dict], bpb: float = 4.0, voice=None,
               relative_pitch: bool = False) -> Dict[str, tuple]:
    """Most common bar pattern per section type (16th grid).

    Tokens are (step, voice): the drum voice, the performed technique, and
    with ``relative_pitch`` the interval above the bar's lowest note, so two
    songs only match when they play the same figure, not merely on the same
    sixteenths.
    """
    bars = collections.defaultdict(set)
    lowest = collections.defaultdict(lambda: 999)
    sec = {}
    for e in events:
        if "fill" in e["kind"] or "pickup" in e["kind"] or "transition" in e["kind"]:
            continue
        b = int((float(e["start_beat_abs"]) + 0.06) // bpb)
        lowest[b] = min(lowest[b], int(e["pitch"]))
    for e in events:
        if "fill" in e["kind"] or "pickup" in e["kind"] or "transition" in e["kind"]:
            continue
        t = float(e["start_beat_abs"])
        b = int((t + 0.06) // bpb)
        tok = voice(e) if voice else ""
        if tok is None:
            continue
        if relative_pitch:
            tok = (tok, (int(e["pitch"]) - lowest[b]) % 12)
        bars[b].add((round((t % bpb) * 4) % max(1, round(bpb * 4)), tok))
        sec[b] = e["section_id"]
    per = collections.defaultdict(list)
    for b in sorted(bars):
        per[sec[b]].append(tuple(sorted(bars[b])))
    return {s: collections.Counter(v).most_common(1)[0][0] for s, v in per.items()}


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def fingerprint(root: str, log: str, bpb: float = 4.0) -> dict:
    fp: dict = {}
    drum = lambda e: _DRUM_CLASS.get(int(e["pitch"]), None)
    fp["drums"] = modal_bars(_events(root, "drums"), bpb=bpb, voice=drum)
    technique = lambda e: re.sub(r"^comp_(riff_|fill_|stop_)?", "", e["kind"] or "")
    fp["bass"] = modal_bars(_events(root, "bass"), bpb=bpb, relative_pitch=True)
    fp["rhythm_gtr"] = modal_bars(_events(root, "rhythm_gtr"), bpb=bpb, voice=technique, relative_pitch=True)
    fp["lead_gtr"] = modal_bars(_events(root, "lead_gtr"), bpb=bpb, relative_pitch=True)
    fp["acoustic_gtr"] = modal_bars(_events(root, "acoustic_gtr"), bpb=bpb, relative_pitch=True)
    # Bass interval habit: pitch classes relative to the most common one.
    bass = [int(e["pitch"]) for e in _events(root, "bass")]
    fp["bass_pitch_spread"] = len(set(p % 12 for p in bass))
    # Devices: habits that would give the generator away.
    kinds = collections.Counter(e["kind"] for e in _events(root, "rhythm_gtr"))
    lead_kinds = collections.Counter(e["kind"] for e in _events(root, "lead_gtr"))
    fp["devices"] = {
        "comp_stop_time": kinds.get("comp_stop_strum", 0) > 0,
        "comp_walkups": sum(v for k, v in kinds.items() if k.startswith("comp_fill")) > 0,
        "lead_dive": sum(v for k, v in lead_kinds.items() if k.endswith("_dive")) > 0,
    }
    fp["riffs"] = sorted(set(re.findall(r"rhythm guitar plays '([^']+)'", log)))
    arr = re.search(r"Composer arrangement: (.*)", log)
    fp["arrangement"] = dict(kv.split("=", 1) for kv in arr.group(1).split(", ")) if arr else {}
    dna = re.search(r"Composer DNA: (.*)", log)
    fp["dna"] = dna.group(1) if dna else ""
    fp["hook_rhythm"] = re.search(r"hook:([^|]*)", fp["dna"]).group(1) if dna else ""
    fp["licks"] = re.search(r"licks:(.*)$", fp["dna"]).group(1).split(",") if dna else []
    drums = _events(root, "drums")
    crash_bars = sorted({int((float(e["start_beat_abs"]) + 0.06) // bpb) for e in drums
                         if _DRUM_CLASS.get(int(e["pitch"])) == "C"})
    fp["crash_every_4"] = bool(crash_bars) and all(b % 4 == 0 for b in crash_bars)
    fill_bars = sorted({int((float(e["start_beat_abs"]) + 0.06) // bpb) for e in drums if "fill" in e["kind"]})
    fp["fill_bar_mod4"] = collections.Counter(b % 4 for b in fill_bars).most_common(1)[0][0] if fill_bars else None
    return fp


def report(fps: List[dict]) -> dict:
    out: dict = {"similarity": {}, "distinct": {}, "devices": {}, "vocabulary": {}}
    for inst in ("drums", "bass", "rhythm_gtr", "lead_gtr", "acoustic_gtr"):
        for sec in ("verse", "chorus", "bridge"):
            pats = [fp.get(inst, {}).get(sec) for fp in fps if fp.get(inst, {}).get(sec)]
            if len(pats) < 2:
                continue
            sims = [jaccard(a, b) for a, b in itertools.combinations(pats, 2)]
            out["similarity"][f"{inst}.{sec}"] = round(statistics.fmean(sims), 3)
            out["distinct"][f"{inst}.{sec}"] = f"{len(set(pats))}/{len(pats)}"
    n = len(fps)
    for dev in fps[0]["devices"]:
        out["devices"][dev] = f"{sum(fp['devices'][dev] for fp in fps)}/{n}"
    # Arrangement habits: the share of songs making the most common choice.
    for habit in sorted({k for fp in fps for k in fp.get("arrangement", {})}):
        counts = collections.Counter(fp["arrangement"].get(habit) for fp in fps
                                     if fp.get("arrangement"))
        if counts:
            value, top = counts.most_common(1)[0]
            out["devices"][f"habit:{habit}"] = f"{top}/{n} ({value})"
    riffs = collections.Counter(r.split("~")[0] for fp in fps for r in fp["riffs"])
    licks = collections.Counter(l for fp in fps for l in fp["licks"])
    out["vocabulary"]["comp_riffs_used"] = dict(riffs.most_common(8))
    out["vocabulary"]["licks_used"] = dict(licks.most_common(8))
    out["vocabulary"]["distinct_hook_rhythms"] = f"{len(set(fp['hook_rhythm'] for fp in fps))}/{n}"
    out["overall_similarity"] = round(statistics.fmean(out["similarity"].values()) if out["similarity"] else 0.0, 3)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--genre", default="hard_rock")
    ap.add_argument("--songs", type=int, default=10)
    ap.add_argument("--out", default="/tmp/album")
    ap.add_argument("--album-seed", type=int, default=1)
    ap.add_argument("--instruments", nargs="+", choices=("drums", "bass", "rhythm_gtr", "lead_gtr", "acoustic_gtr"))
    ap.add_argument("--meter", default="4/4")
    args = ap.parse_args(argv)
    if args.songs < 2:
        ap.error("--songs must be at least 2")
    os.makedirs(args.out, exist_ok=True)
    fps = []
    renders = tempfile.mkdtemp(prefix="renders-", dir=os.path.abspath(args.out))
    for cfg in album_configs(args.genre, args.songs, args.album_seed, args.instruments, args.meter):
        cfg["song"]["exports_root"] = renders
        path = os.path.join(args.out, cfg["song"]["title"].replace(" ", "_") + ".yaml")
        yaml.safe_dump(cfg, open(path, "w"), sort_keys=False)
        r = subprocess.run([sys.executable, "produzre_entry.py", "build", path],
                           capture_output=True, text=True)
        m = re.search(r"Export root: (\S+)", r.stderr)
        if r.returncode or not m:
            print("build failed:", path, r.stderr[-500:])
            return 1
        num, den = map(int, args.meter.split("/"))
        fps.append(fingerprint(m.group(1), r.stderr, num * 4 / den))
    rep = report(fps)
    print(json.dumps(rep, indent=1))
    json.dump(rep, open(os.path.join(args.out, "album_report.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
