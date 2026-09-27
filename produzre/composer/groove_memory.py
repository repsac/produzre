"""Groove memory: bar-level form for the rhythm section.

Engines draw every bar fresh, so a bass line or drum beat never settles
into a groove: measured over the genre examples, the most common bar
pattern accounted for only ~20% of a section's bars. Real players lock a
pattern and vary it at phrase ends.

This post-pass gives each accompaniment part a bar form. Within every
phrase, "groove" bars restate a source bar, and the phrase's final bar
keeps the engine's own output (fills, turnarounds, pickups: the variation).
Pitched parts are restated chord-relatively: the pattern moves with the
root and each chord tone keeps its role (a third stays a third), which is
how a bassist or guitarist carries a groove through a progression. A
returning section type recalls the groove it established, scaled to the
new occurrence's dynamics, so the second chorus grooves like the first.

All instruments of a section share the same source bars, so couplings the
engines negotiated (kick/bass lock, riff lock) survive the restatement.
The pass is deterministic; copied events get fresh micro-timing so a
restated bar is played again, not pasted.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from .theory import ChordMap, scale_pcs

GROOVE_INSTRUMENTS = ("drums", "bass", "rhythm_gtr", "acoustic_gtr")

# Event kinds that belong to a bar's decoration, never restated or replaced.
# Ride-bell accents ("ride_bell") are occasional by design: restating a
# groove bar without one would erase them.
_PROTECTED_TOKENS = ("fill", "pickup", "turnaround", "cadence", "crash", "transition",
                     "tom", "cymbal", "splash", "china", "stop", "hit", "accent_hit", "bell")
_APPROACH_TOKENS = ("approach", "passing", "chromatic", "walk")

# Genres whose grooves are two-bar phrases (clave, one-drop, funk answers).
_TWO_BAR_GENRES = ("funk", "reggae", "latin", "bossa", "hip_hop", "rnb", "soul", "disco",
                   "ska", "afro", "samba", "salsa")


def _protected(kind: Optional[str]) -> bool:
    k = str(kind or "").lower()
    return any(t in k for t in _PROTECTED_TOKENS)


def _is_approach(kind: Optional[str]) -> bool:
    k = str(kind or "").lower()
    return any(t in k for t in _APPROACH_TOKENS)


def groove_cycle(genre: str, override: Any = None) -> int:
    if override is not None:
        try:
            return 2 if int(override) >= 2 else 1
        except (TypeError, ValueError):
            pass
    g = str(genre or "").lower()
    return 2 if any(t in g for t in _TWO_BAR_GENRES) else 1


def bar_form(bars: int, cycle: int = 1, phrase: int = 4) -> List[Optional[int]]:
    """Source phase for each bar, or None where the engine keeps the bar.

    Returns a list with one entry per bar: an integer ``k`` means "restate
    groove source ``k``" (0 <= k < cycle); None means the bar is a phrase
    end (or too short a section to have a groove) and keeps engine output.
    """
    if bars < 3:
        return [None] * bars
    phrase = phrase if bars >= phrase else bars
    form: List[Optional[int]] = []
    for i in range(bars):
        if i % phrase == phrase - 1 or i == bars - 1:
            form.append(None)
        else:
            form.append(i % cycle)
    return form


def source_bars(form: Sequence[Optional[int]], cycle: int,
                signatures: Optional[Dict[int, Tuple]] = None,
                idiom: Optional[Dict[int, float]] = None) -> Dict[int, int]:
    """Which bar supplies each source phase.

    With ``signatures`` (bar -> onset/pitch signature) the source is the
    *medoid* of its phase: the bar most like the others, i.e. the engine's
    typical groove rather than whichever bar happened to come first. Among
    near-typical bars (within two onsets of the medoid), ``idiom`` (bar ->
    score) picks the most idiomatic one. Ties prefer bar 1 over bar 0, which
    often carries entry decorations.
    """
    out: Dict[int, int] = {}
    for k in range(cycle):
        cands = [i for i, f in enumerate(form) if f == k]
        if not cands:
            continue
        if signatures:
            def spread(i: int) -> Tuple[float, int]:
                a = signatures.get(i, ())
                d = 0.0
                for j in cands:
                    b = signatures.get(j, ())
                    d += len(set(a) ^ set(b))
                return (d, 0 if i != 0 else 1)
            best = min(spread(i)[0] for i in cands)
            near = [i for i in cands if spread(i)[0] <= best + 2 * max(1, len(cands) - 1)]
            out[k] = min(near, key=lambda i: (-(idiom or {}).get(i, 0.0), spread(i), i))
        else:
            order = [i for i in cands if i != 0] + [i for i in cands if i == 0]
            out[k] = order[0]
    return out


def _shift_chord(chord, semis: int):
    if chord is None or not semis:
        return chord
    return replace(chord, pcs=tuple((pc + semis) % 12 for pc in chord.pcs),
                   root_pc=(chord.root_pc + semis) % 12)


def _nearest_delta(a: int, b: int) -> int:
    d = (b - a) % 12
    return d - 12 if d > 6 else d


def map_pitch(pitch: int, src_chord, dst_chord, scale: Sequence[int],
              lo: int = 0, hi: int = 127) -> int:
    """Carry a pitch from one chord to another, keeping its chord role."""
    if src_chord is None or dst_chord is None or src_chord.numeral == dst_chord.numeral:
        return pitch
    delta = _nearest_delta(src_chord.root_pc, dst_chord.root_pc)
    moved = pitch + delta
    rel = (pitch - src_chord.root_pc) % 12
    src_iv = [(pc - src_chord.root_pc) % 12 for pc in src_chord.pcs]
    dst_iv = [(pc - dst_chord.root_pc) % 12 for pc in dst_chord.pcs]
    if rel in src_iv:
        k = src_iv.index(rel)
        if k < len(dst_iv):
            target_pc = (dst_chord.root_pc + dst_iv[k]) % 12
            moved = min((moved + d for d in range(-2, 3) if (moved + d) % 12 == target_pc),
                        key=lambda p: abs(p - moved), default=moved)
    else:
        allowed = set(scale) | set(dst_chord.pcs)
        if moved % 12 not in allowed:
            moved = min((moved + d for d in (-1, 1, -2, 2) if (moved + d) % 12 in allowed),
                        key=lambda p: (abs(p - moved), p), default=moved)
    while moved < lo:
        moved += 12
    while moved > hi:
        moved -= 12
    return moved


def _with_bass_anchor(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A bass source bar with a note on one (see apply_groove_memory)."""
    if not specs or any(s.get("anchor") for s in specs):
        return specs
    first = min((s for s in specs if not s.get("approach")), key=lambda s: s["off"], default=None)
    if first is None or first["off"] < 0.25:
        return specs
    anchor = dict(first, off=0.0, dur=max(0.1, min(first["off"] - 0.02, 1.0)),
                  kind="root", approach=False, anchor=True, expression=None)
    return [anchor] + list(specs)


class GrooveMemory:
    """Per-song store of established grooves, keyed by section type."""

    def __init__(self) -> None:
        self._store: Dict[tuple, Dict[str, Any]] = {}

    def get(self, key: tuple) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    def put(self, key: tuple, value: Dict[str, Any]) -> None:
        self._store.setdefault(key, value)


def apply_groove_memory(
    events: List[Any],
    *,
    instrument: str,
    section_start: float,
    beats_per_bar: float,
    bars: int,
    chord_slots: Optional[Sequence],
    key: str,
    mode: str,
    genre: str,
    bpm: float,
    memory: Optional[GrooveMemory],
    memory_key: Optional[tuple],
    seed: int,
    cycle_override: Any = None,
    intensity: Optional[float] = None,
    register: Optional[Tuple[int, int]] = None,
) -> Tuple[List[Any], Dict[str, Any]]:
    """Restate groove bars in ``events`` (this section's new events).

    Returns (new_events, report). Events are NoteEvent-like objects with
    start_beat / duration_beats / pitch / velocity / kind. ``register``
    bounds restated pitches (the part's own range; bass default 24-64).
    """
    report: Dict[str, Any] = {"applied": False}
    if bars < 3 or beats_per_bar <= 0 or not events:
        return events, report
    # Theme-locked parts (riff / motif quotes) already carry authored
    # identity; restating bars chord-relatively would bend the quotes.
    quoted = sum(1 for e in events if any(t in str(e.kind or "").lower()
                                          for t in ("motif", "riff", "theme")))
    if quoted >= 0.25 * len(events):
        return events, report
    # A walking bass line is through-composed: every bar walks to the next
    # chord, so restating one bar's contour would stop the walk.
    walking = sum(1 for e in events if str(e.kind or "").startswith("walk_"))
    if instrument == "bass" and walking >= 0.5 * len(events):
        return events, report
    cycle = groove_cycle(genre, cycle_override)
    form = bar_form(bars, cycle)

    chords = ChordMap(chord_slots, key, mode) if chord_slots else None
    scale = scale_pcs(key, mode)
    pitched = instrument != "drums"
    eps = 1e-6

    def bar_of(ev) -> int:
        local = float(ev.start_beat) - section_start
        # Nearest-step bar membership: an anticipated downbeat belongs to
        # the bar it anticipates.
        return int((local + 0.06) // beats_per_bar)

    by_bar: Dict[int, List[Any]] = {}
    for ev in events:
        by_bar.setdefault(bar_of(ev), []).append(ev)

    def groove_part(bar_events: Sequence[Any]) -> List[Any]:
        return [e for e in bar_events if not _protected(getattr(e, "kind", None))]

    def signature(b: int) -> Tuple:
        start = section_start + b * beats_per_bar
        return tuple(sorted({(round((float(e.start_beat) - start) * 12), int(e.pitch) if not pitched else 0)
                             for e in groove_part(by_bar.get(b, []))}))

    def idiom(b: int) -> float:
        """Idiomatic voicing of a bar (bass: root on one, fifths welcome)."""
        if instrument != "bass":
            return 0.0
        bar_ev = sorted(groove_part(by_bar.get(b, [])), key=lambda e: e.start_beat)
        if not bar_ev:
            return -5.0
        score = 0.0
        first = bar_ev[0]
        on_one = abs(float(first.start_beat) - (section_start + b * beats_per_bar)) < 0.1
        kind = str(first.kind or "")
        if on_one and kind.startswith("root"):
            score += 1.0
        elif on_one and kind.startswith("third"):
            score -= 1.0
        if any(str(e.kind or "").startswith("fifth") for e in bar_ev[1:]):
            score += 0.5
        return score

    sources = source_bars(form, cycle, {b: signature(b) for b in range(bars)},
                          {b: idiom(b) for b in range(bars)})
    if len(sources) < cycle:
        return events, report

    def spec(ev, bar_idx: int) -> Dict[str, Any]:
        bar_start = section_start + bar_idx * beats_per_bar
        off = float(ev.start_beat) - bar_start
        ref = bar_idx * beats_per_bar + (beats_per_bar if _is_approach(ev.kind) else max(0.0, off))
        chord = chords.at(min(ref, chords.total - eps)) if chords is not None else None
        # A groove bar's bass downbeat is the root (beat-1 tie-break): a fifth
        # or third on one is the engine's variation, kept in phrase-end bars
        # but never restated into every bar.
        anchor = instrument == "bass" and abs(off) < 0.06 and not _is_approach(ev.kind)
        return {"off": off, "dur": float(ev.duration_beats), "pitch": int(ev.pitch),
                "vel": int(ev.velocity), "kind": ev.kind, "channel": ev.channel,
                "expression": getattr(ev, "expression", None), "chord": chord,
                "approach": _is_approach(ev.kind), "anchor": anchor}

    stored = memory.get(memory_key) if memory is not None and memory_key is not None else None
    if stored is not None and stored.get("bpb") != beats_per_bar:
        stored = None
    if stored is not None and stored.get("cycle") != cycle:
        stored = None
    if stored is not None and pitched and str(stored.get("mode") or mode).lower() != str(mode).lower():
        stored = None  # a new mode changes chord qualities; start a fresh groove
    lifted_from = None
    if stored is not None and intensity is not None and stored.get("intensity") is not None \
            and intensity - stored["intensity"] >= 0.08:
        # The arrangement is lifting (e.g., a final chorus): play this
        # occurrence's own, more intense groove instead of the recalled one.
        lifted_from, stored = stored, None

    fresh = {k: [spec(e, b) for e in groove_part(by_bar.get(b, []))] for k, b in sources.items()}
    if instrument == "bass" and lifted_from is not None and \
            sum(len(v) for v in fresh.values()) < sum(len(v) for v in lifted_from["specs"].values()):
        # A lift never thins the bass: when this occurrence's own groove is
        # sparser than the one the section established, the established
        # groove returns at the new dynamics.
        stored = lifted_from
    if stored is None:
        source_specs = fresh
        vel_ratio = 1.0
        if memory is not None and memory_key is not None:
            memory.put(memory_key, {"bpb": beats_per_bar, "cycle": cycle, "specs": fresh,
                                    "intensity": intensity, "key": key, "mode": mode})
    else:
        source_specs = stored["specs"]
        from .theory import tonic_pc

        key_shift = _nearest_delta(tonic_pc(stored.get("key") or key), tonic_pc(key))
        if key_shift and pitched:
            # Recalled in a new key (final-chorus modulation): move with it.
            # Move the source chords too, so chord-relative mapping measures
            # from the new key instead of undoing the shift.
            source_specs = {k: [dict(sp, pitch=sp["pitch"] + key_shift,
                                     chord=_shift_chord(sp["chord"], key_shift)) for sp in v]
                            for k, v in source_specs.items()}
        # Keep this occurrence's dynamics (e.g., a louder last chorus).
        now = [s["vel"] for k in fresh for s in fresh[k]]
        then = [s["vel"] for k in source_specs for s in source_specs[k]]
        vel_ratio = (sum(now) / len(now)) / (sum(then) / len(then)) if now and then else 1.0
        vel_ratio = max(0.8, min(1.25, vel_ratio))

    if not any(source_specs.get(k) for k in range(cycle)):
        return events, report

    if instrument == "bass":
        # The beat-1 rule holds in every restated bar: a source bar whose
        # first note comes after the downbeat gets a root on one, held up to
        # that note, so no groove bar leaves the one to the rest of the band.
        source_specs = {k: _with_bass_anchor(v) for k, v in source_specs.items()}

    # Re-humanize copies only if the engine humanized the source: a part
    # rendered dead on the grid (humanize off) must stay on the grid.
    def _off_grid(off: float) -> float:
        return min(abs(off * 12 - round(off * 12)) / 12, abs(off * 4 - round(off * 4)) / 4)

    all_specs = [sp for k in source_specs for sp in source_specs[k]]
    humanized = any(_off_grid(sp["off"]) > 0.002 for sp in all_specs)
    vel_varied = len({sp["vel"] for sp in all_specs}) > 2

    template = events[0]
    out: List[Any] = []
    restated = 0
    for b in sorted(set(list(by_bar) + list(range(bars)))):
        bar_events = by_bar.get(b, [])
        phase = form[b] if 0 <= b < bars else None
        if phase is None:
            out.extend(bar_events)
            continue
        kept = [e for e in bar_events if _protected(getattr(e, "kind", None))]
        if not groove_part(bar_events):
            # The engine rested here on purpose (sparse parts breathe):
            # a restatement must not fill deliberate space.
            out.extend(bar_events)
            continue
        rng = random.Random(stable_seed_int("groove_memory", seed, instrument, b))
        bar_start = section_start + b * beats_per_bar
        jitter_beats = 0.004 * bpm / 60.0 if humanized else 0.0  # ~4 ms
        for s in source_specs.get(phase, []):
            start = bar_start + s["off"]
            # Don't double a kept decoration (crash on 1, pickup on the and-of-4).
            if not pitched and any(abs(k.start_beat - start) < 0.1 and k.pitch == s["pitch"]
                                   for k in kept):
                continue
            pitch = s["pitch"]
            kind = s["kind"]
            if pitched and chords is not None and s["chord"] is not None:
                ref = b * beats_per_bar + (beats_per_bar if s["approach"] else max(0.0, s["off"]))
                dst = chords.at(min(ref, chords.total - eps))
                # An explicit register wins; the acoustic's picked melody
                # tops out at A5 (composer/acoustic.py).
                lo, hi = register or {"bass": (24, 64), "acoustic_gtr": (40, 81)}.get(
                    instrument, (36, 96))
                pitch = map_pitch(pitch, s["chord"], dst, scale, lo, hi)
                if s.get("anchor") and dst is not None:
                    # The downbeat is the root (the beat-1 tie-break): a fifth
                    # or third on one in the source bar is that bar's
                    # variation, not the groove. A fifth drop or a tonic
                    # pedal the engine drew for this very bar
                    # (fifth_jump_rate, pedal_rate) is kept.
                    own = [e for e in groove_part(bar_events)
                           if abs(float(e.start_beat) - bar_start) < 0.06]
                    # (A root keeps its own label, articulation included.)
                    pc, kind = dst.root_pc, (kind if str(kind).startswith("root") else "root")
                    if own and str(own[0].kind or "").startswith(("fifth_drop", "pedal")) \
                            and int(own[0].pitch) % 12 in dst.pcs:
                        pc, kind = int(own[0].pitch) % 12, own[0].kind
                    if pitch % 12 != pc:
                        near = [p for p in range(lo, hi + 1) if p % 12 == pc]
                        if near:
                            pitch = min(near, key=lambda p: (abs(p - pitch), p))
                    if pc == dst.root_pc and not str(kind).startswith("root"):
                        kind = "root"
            vel = int(round(s["vel"] * vel_ratio)) + (rng.randint(-3, 3) if vel_varied else 0)
            jitter = rng.uniform(-jitter_beats, jitter_beats)
            if abs(s["off"]) < 1e-6:
                jitter = abs(jitter)  # never drag a downbeat into the previous bar
            dur = s["dur"]
            if instrument == "bass" and chords is not None and not s["approach"]:
                # A restated bass note never rings into the next chord: that
                # would carry this chord's pitch over the new harmony.
                span = chords.at(min(b * beats_per_bar + max(0.0, s["off"]), chords.total - eps))
                if span is not None:
                    dur = max(0.05, min(dur, float(span.end) - (b * beats_per_bar + s["off"]) - 0.02))
            new = replace(template, start_beat=start + jitter,
                          duration_beats=dur, pitch=pitch,
                          velocity=max(1, min(127, vel)), channel=s["channel"],
                          kind=kind,
                          expression=dict(s["expression"]) if isinstance(s["expression"], dict)
                          else s["expression"])
            out.append(new)
            restated += 1
        out.extend(kept)
    # Pitched parts: identical onset + pitch duplicates collapse.
    if pitched:
        seen = set()
        deduped = []
        for e in sorted(out, key=lambda e: (round(e.start_beat, 3), e.pitch, -e.velocity)):
            k = (round(e.start_beat, 3), e.pitch)
            if k in seen:
                continue
            seen.add(k)
            deduped.append(e)
        out = deduped
    out.sort(key=lambda e: (e.start_beat, e.pitch))
    report = {"applied": True, "cycle": cycle, "restated": restated,
              "recalled": stored is not None, "form": "".join(
                  "-" if f is None else "ab"[f] for f in form)}
    return out, report
