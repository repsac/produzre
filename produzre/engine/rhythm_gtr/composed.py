"""Perform composed rhythm-guitar gestures (produzre/composer/comping.py).

The composer decides *what* the rhythm guitar plays (strums, chucks,
single-note walks, sus hammer-ons, slides, dyads, arpeggios); this module
decides *how it sounds on a guitar*: which strings of a playable chord shape
each gesture uses, strum spread across the strings, dead-note length and
velocity, and slides written as pitch bend.
"""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ...composer.theory import scale_pcs
from ...melody import chord_pitch_classes
from ...timeline import InstrumentTimeline

# (full shape pitches, power shape pitches, numeral) for a section beat.
ShapeLookup = Callable[[float], Optional[Tuple[List[int], List[int], str]]]


def _third_index(pitches: Sequence[int], numeral: str, key: str, mode: str) -> Optional[int]:
    pcs = chord_pitch_classes(numeral, key, mode)
    if len(pcs) < 2:
        return None
    third = pcs[1]
    for i, p in enumerate(pitches):
        if p % 12 == third:
            return i
    return None


def _walk_pitch(target_pc: Optional[int], distance: int, near: int, key: str, mode: str) -> int:
    """A walking note into ``target_pc``, placed near the bass root ``near``.

    ``distance`` 0 is the last note before the target (its chromatic
    leading tone); 1 is the scale tone two steps below the target. Played in
    order they walk up: E F# G# A.
    """
    if target_pc is None:
        return near
    # The target sits just above the root, the way a bassline climbs to it.
    target = near + ((target_pc - near) % 12 or 12)
    if target - near > 7:
        target -= 12
    scale = sorted(scale_pcs(key, mode))
    p = target
    for _ in range(2):
        p -= 1
        while p % 12 not in scale:
            p -= 1
    while p < 40:
        p += 12
        target += 12
    return target - 1 if distance <= 0 else p


def perform_comp(
    events: Sequence[dict],
    *,
    timeline: InstrumentTimeline,
    section_start_beat: float,
    shape_at: ShapeLookup,
    key: str,
    mode: str,
    intensity: float,
    bpm: float,
    ring: float,
    rng: random.Random,
    strum_ms: float = 14.0,
    timing_jitter_ms: float = 6.0,
    feel: Optional[dict] = None,
    beats_per_bar: float = 4.0,
) -> int:
    """Render composed comp events; returns the number of notes written.

    ``feel`` carries the user's explicit rhythm settings: ``density`` below
    0.7 thins weak off-beat gestures, ``palm_mute`` turns plain strums into
    chugs, ``chuck_rate`` turns light upstrokes into dead-note chucks,
    ``sustain_cut_rate`` cuts strums to stabs, and ``accent_strength``,
    ``downbeat_boost`` and ``humanize_velocity`` shape dynamics. They use
    their own random stream, so a default build is unchanged.
    """
    feel = dict(feel or {})
    feel_rng = random.Random(7919 + len(events))

    def _f(name: str) -> Optional[float]:
        try:
            return float(feel[name]) if feel.get(name) is not None else None
        except (TypeError, ValueError):
            return None

    density, palm, chuck_rate = _f("density"), _f("palm_mute"), _f("chuck_rate")
    cut, accent_strength = _f("sustain_cut_rate"), _f("accent_strength")
    downbeat_boost, vel_humanize = _f("downbeat_boost"), _f("humanize_velocity")
    accent_gain = 1.0 + 0.24 * accent_strength if accent_strength is not None else 1.12
    vel_spread = int(round(8 * vel_humanize)) if vel_humanize is not None else 4
    base = int(80 * max(0.45, min(1.3, intensity)))
    beats_per_ms = bpm / 60000.0
    written = 0
    ordered = sorted(events, key=lambda e: float(e["beat"]))
    for idx, ev in enumerate(ordered):
        beat = float(ev["beat"])
        dur = float(ev["dur"])
        kind = str(ev["kind"])
        shape = shape_at(beat)
        if shape is None:
            continue
        full, power, numeral = shape
        full = sorted(full) or sorted(power)
        power = sorted(power) or full[:2]
        if not full:
            continue
        # Chugs, boogies and bass-string lines live on the low strings.
        while power and power[0] - 12 >= 40:
            power = [p - 12 for p in power]
        # The bass-string root: the lowest sounding root among both shapes.
        root_pc = power[0] % 12
        root = min((p for p in full + power if p % 12 == root_pc), default=power[0])
        accent = bool(ev.get("accent"))
        tag = str(ev.get("tag") or "comp")
        on_beat = abs(beat - round(beat)) < 1e-6
        if density is not None and density < 0.7 and not accent and not on_beat \
                and tag == "comp" and feel_rng.random() >= density / 0.7:
            continue
        if palm is not None and kind == "strum" and not accent and tag == "comp" \
                and feel_rng.random() < palm:
            kind = "chug"
        if chuck_rate is not None and kind == "up" and feel_rng.random() < chuck_rate:
            kind = "chuck"
        vel = base * (accent_gain if accent else 0.95)
        if downbeat_boost is not None and beats_per_bar > 0 and abs(beat % beats_per_bar) < 1e-6:
            vel *= 1.0 + downbeat_boost
        expression: Optional[dict] = None
        notes: List[Tuple[int, float, float]] = []  # (pitch, offset, dur)
        direction = str(ev.get("direction") or "down")
        spread = True

        if kind in ("strum", "slide"):
            ps = full if direction == "down" else sorted(full)[-max(3, len(full) - 2):]
            # A stop-time hit or a final chord rings through its silence.
            d = dur if tag == "comp_stop" else min(dur, ring)
            if cut is not None and tag == "comp" and feel_rng.random() < cut:
                d = min(d, 0.15)
            notes = [(p, 0.0, d) for p in ps]
            if direction == "up":
                vel *= 0.82
            if kind == "slide":
                expression = {"bend_in": {"semitones": rng.choice([1, 2]), "ramp_beats": 0.12}}
        elif kind == "up":
            notes = [(p, 0.0, min(dur, ring, 0.5)) for p in full[-3:]]
            vel *= 0.72
            direction = "up"
        elif kind in ("rpower", "rchug", "rsingle"):
            # Signature-riff gestures: shapes moved along the low strings.
            iv = int(ev.get("interval") or 0)
            riff_root = root + iv
            while riff_root < 38:
                riff_root += 12
            while riff_root > 52:
                riff_root -= 12
            if kind == "rsingle":
                notes = [(riff_root, 0.0, max(0.1, dur))]
                spread = False
            elif kind == "rchug":
                shape = (riff_root, riff_root + 12) if str(feel.get("voicing") or "").lower() == "octaves" \
                    else (riff_root, riff_root + 7)
                notes = [(p, 0.0, min(dur, 0.18)) for p in shape]
                vel *= 0.84
            else:
                shape = (riff_root, riff_root + 12) if str(feel.get("voicing") or "").lower() == "octaves" \
                    else (riff_root, riff_root + 7, riff_root + 12)
                notes = [(p, 0.0, max(0.12, dur)) for p in shape]
                vel *= 1.06
        elif kind == "chuck":
            notes = [(p, 0.0, 0.06) for p in full[-4:]]
            vel = 34 + rng.randint(0, 12)
            spread = False
        elif kind == "chug":
            notes = [(p, 0.0, min(dur, 0.18)) for p in power]
            vel *= 0.86
        elif kind == "power":
            notes = [(p, 0.0, min(dur, max(ring, 0.5))) for p in power]
        elif kind == "stab":
            notes = [(p, 0.0, min(dur, 0.22)) for p in full[-3:]]
            vel *= 1.05
        elif kind == "root":
            notes = [(root, 0.0, min(dur, 0.5))]
            spread = False
        elif kind == "fifth":
            notes = [(root + 7, 0.0, min(dur, 0.5))]
            spread = False
        elif kind == "walk":
            notes = [(_walk_pitch(ev.get("target_pc"), int(ev.get("arp_index") or 0), root,
                                  key, mode), 0.0, min(dur, 0.3))]
            vel *= 0.9
            spread = False
        elif kind in ("dyad", "dyad5", "dyad6", "dyad7"):
            if kind == "dyad":
                ps = full[-2:]
            else:
                ps = [root, root + {"dyad5": 7, "dyad6": 9, "dyad7": 10}[kind]]
            notes = [(p, 0.0, min(dur, max(0.2, ring))) for p in ps]
        elif kind == "sus":
            t = _third_index(full, numeral, key, mode)
            d = min(dur, ring)
            if t is None:
                notes = [(p, 0.0, d) for p in full]
            else:
                third = full[t]
                pcs = chord_pitch_classes(numeral, key, mode)
                lift = 2 if (pcs[1] - pcs[0]) % 12 == 3 else 1   # minor or major third to the 4th
                hammer = min(0.5, d / 2.0)
                notes = [(p, 0.0, d) for i, p in enumerate(full) if i != t]
                notes.append((third + lift, 0.0, hammer))
                notes.append((third, hammer, max(0.1, d - hammer)))
        elif kind == "arp":
            order = full
            p = order[int(ev.get("arp_index") or 0) % len(order)]
            # Let it ring into the next notes, like a picked chord shape.
            notes = [(p, 0.0, max(dur, min(ring, 2.0)))]
            vel *= 0.85
            spread = False
        else:
            continue

        if direction == "up":
            notes = sorted(notes, key=lambda n: -n[0])
        jitter = rng.uniform(-timing_jitter_ms, timing_jitter_ms) * beats_per_ms
        start = section_start_beat + beat + (abs(jitter) if beat == 0 else jitter)
        step = strum_ms * beats_per_ms / max(1, len(notes) - 1) if spread and len(notes) > 1 else 0.0
        for n_i, (pitch, offset, d) in enumerate(notes):
            lo, hi = _f("register_min"), _f("register_max")
            if lo is not None or hi is not None:
                low, high = max(0, int(lo) if lo is not None else 0), min(127, int(hi) if hi is not None else 127)
                pitch = min((p for p in range(low, high + 1) if p % 12 == pitch % 12),
                            key=lambda p: (abs(p - pitch), p), default=max(low, min(high, pitch)))
            v = int(vel * (1.0 - 0.03 * n_i if direction == "down" else 1.0)) + \
                rng.randint(-4, 4) * vel_spread // 4
            note_start = start + offset + (n_i * step if offset == 0 else 0.0)
            # A picked chord can ring, but the country waltz releases it
            # before the harmony changes underneath the bass.
            if ev.get("release_beat") is not None:
                d = min(d, section_start_beat + float(ev["release_beat"]) - note_start)
                if d <= 0:
                    continue
            timeline.add_note(
                start_beat=note_start,
                duration_beats=max(0.04, d),
                pitch=int(max(0, min(127, pitch))),
                velocity=max(1, min(127, v)),
                kind=f"{tag}_{kind}" if not tag.endswith(kind) else tag,
                expression=expression if n_i == 0 else None,
            )
            written += 1
    return written
