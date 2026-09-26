"""Build the song-level composer and connect it to the theme bank.

The composer is created once per build, after harmony planning, so the DNA
can be chosen by how it sounds over the song's real chorus and verse
chords. When the song's melody theme was auto-generated (not authored), the
composer's hook replaces it in the bank: every consumer of the melody guide
(acoustic treble melody, arpeggio apex notes, legacy lead quoting) then
shares the same hook as the lead guitar, instead of two unrelated melodies
competing in one song. Authored melody themes are never replaced; they seed
the composer's hook instead.
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from typing import Any, List, Optional, Sequence, Tuple

from ..engine.lead_gtr.register import get_register_bounds
from .lead import SongComposer, _normalize_type
from .realize import realize_cell
from .theory import ChordMap, diatonic_index, meter_groups, mode_offsets, tonic_pc


def section_groups(cfg: Any, sec: Any, meter: Any) -> Optional[Tuple[float, ...]]:
    """A section's beat grouping: its own ``meter_grouping``, the song's, or
    the time signature's default (6/8 -> 3+3 eighths, 7/8 -> 2+2+3, 5/4 -> 3+2).

    An override that does not add up to the section's bar is ignored, so a
    song-level ``"2+2+3"`` only shapes its 7/8 sections.
    """
    if meter is None:
        return None
    override = None
    extras = getattr(sec, "extras", None) if sec is not None else None
    if isinstance(extras, dict):
        override = extras.get("meter_grouping")
    if override is None:
        raw = getattr(cfg, "raw", None)
        song = raw.get("song", {}) if isinstance(raw, dict) else {}
        if isinstance(song, dict):
            override = song.get("meter_grouping")
    try:
        return meter_groups(int(meter.numerator), int(meter.denominator), override)
    except (AttributeError, TypeError, ValueError):
        return None


def composer_enabled(cfg: Any) -> bool:
    raw = getattr(cfg, "raw", None)
    song = raw.get("song", {}) if isinstance(raw, dict) else {}
    value = song.get("composer", True) if isinstance(song, dict) else True
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "off", "no", "legacy", "0")
    return bool(value)


def lead_register(cfg: Any, lead_cfg: Any = None) -> Tuple[int, int]:
    """Resolve the lead register (preset name or [lo, hi]).

    ``lead_cfg`` is a section's merged lead config; without one the global
    ``instruments.lead_gtr`` block is used.
    """
    reg = None
    if lead_cfg is not None:
        reg = getattr(lead_cfg, "register", None)
        extra = getattr(lead_cfg, "extra", None)
        if reg is None and isinstance(extra, dict):
            nested = extra.get("extra") if isinstance(extra.get("extra"), dict) else {}
            reg = nested.get("register") or extra.get("register")
    if reg is None:
        raw = getattr(cfg, "raw", None)
        data = (raw.get("instruments") or {}).get("lead_gtr") if isinstance(raw, dict) else None
        if isinstance(data, dict):
            reg = data.get("register") or (data.get("params") or {}).get("register") \
                or (data.get("extra") or {}).get("register")
    if isinstance(reg, (list, tuple)) and len(reg) == 2:
        lo, hi = int(reg[0]), int(reg[1])
        return max(0, min(127, lo)), max(0, min(127, hi))
    else:
        lo, hi = get_register_bounds(str(reg) if reg else "mid")
    # Melodies need a little headroom above the preset's comfortable top.
    lo = max(0, min(int(lo), 110))
    hi = max(hi + 3, lo + 14)
    return lo, min(125, hi)  # licks may reach 2 above: stay inside MIDI


def _first_source(plan: Any, types: Sequence[str]):
    for ps in getattr(plan, "planned_sections", ()):
        hp = getattr(ps, "harmony_plan", None)
        if hp is None or not getattr(hp, "chord_slots", None):
            continue
        if _normalize_type(getattr(ps.sec, "type", "")) in types:
            return ps
    return None


def build_song_composer(cfg: Any, plan: Any, theme_bank: Any,
                        logger: Optional[logging.Logger] = None) -> Optional[SongComposer]:
    log = logger or logging.getLogger("produzre")
    if not composer_enabled(cfg):
        log.info("Composer disabled (song.composer: false); using legacy lead phrasing.")
        return None
    song = cfg.song
    melody_theme = None
    if theme_bank is not None:
        for theme in getattr(theme_bank, "themes", {}).values():
            if getattr(theme.role, "value", "") == "melody" and "user" in theme.tags:
                melody_theme = theme
                break
    hook_source = (_first_source(plan, ("chorus",)) or _first_source(plan, ("verse", "intro"))
                   or next((ps for ps in getattr(plan, "planned_sections", ())
                            if getattr(getattr(ps, "harmony_plan", None), "chord_slots", None)), None))
    verse_source = _first_source(plan, ("verse",)) or hook_source

    def source_context(source):
        sec = source.sec if source is not None else song
        hp = source.harmony_plan if source is not None else None
        bpb = float(getattr(getattr(hp, "meter", None), "beats_per_bar", None)
                    or getattr(song, "beats_per_bar", 4) or 4)
        slots = [s for s in hp.chord_slots if s.start_beat < bpb * 2 - 1e-6] if hp else None
        return (slots, getattr(sec, "key", None) or song.key,
                getattr(sec, "mode", None) or song.mode, bpb,
                section_groups(cfg, sec if source is not None else None, getattr(hp, "meter", None)))

    hook_slots, key, mode, bpb, groups = source_context(hook_source)
    verse_slots, verse_key, verse_mode, verse_bpb, verse_groups = source_context(verse_source)
    composer = SongComposer(
        seed=int(getattr(song, "seed", 0) or 0),
        genre=str(getattr(song, "genre", "") or ""),
        key=str(key or "C"),
        mode=str(mode or "major"),
        beats_per_bar=bpb,
        melody_theme=melody_theme,
        hook_slots=hook_slots,
        verse_slots=verse_slots,
        verse_context=(verse_key, verse_mode, verse_bpb, verse_groups),
        register=lead_register(cfg),
        groups=groups,
    )
    composer.hook_slots = hook_slots
    raw = getattr(cfg, "raw", None)
    song_raw = raw.get("song", {}) if isinstance(raw, dict) else {}
    composer.arrangement_overrides = song_raw.get("arrangement_style") \
        if isinstance(song_raw, dict) else None
    log.info("Composer arrangement: %s", composer.arrangement_dna().signature)
    log.info("Composer drums: %s", composer.drum_dna().signature)
    log.info("Composer DNA: %s", composer.dna.signature)
    return composer


def adopt_hook_into_bank(composer: SongComposer, theme_bank: Any, logger=None) -> Any:
    """Replace an auto-generated melody theme with the composer's hook line."""
    if theme_bank is None or not getattr(theme_bank, "themes", None):
        return theme_bank
    from ..themes.model import Theme, ThemeEvent, ThemeRole

    names = [n for n, t in theme_bank.themes.items()
             if t.role is ThemeRole.MELODY and "generated" in t.tags]
    if not names:
        return theme_bank
    slots = getattr(composer, "hook_slots", None)
    if not slots:
        return theme_bank
    chords = ChordMap(slots, composer.key, composer.mode)
    old = theme_bank.themes[names[0]]
    lo, hi = old.base_register
    anchor = lo + 0.62 * (hi - lo)
    bpb = composer.bpb
    notes, _ = realize_cell(composer.dna.hook, 0.0, chords, key=composer.key, mode=composer.mode,
                            lo=lo, hi=hi, anchor=anchor, beats_per_bar=bpb)
    prev = notes[-1].pitch if notes else None
    answer, _ = realize_cell(composer.dna.hook_answer, bpb, chords, key=composer.key,
                             mode=composer.mode, lo=lo, hi=hi, anchor=anchor, prev_pitch=prev,
                             beats_per_bar=bpb)
    line = notes + answer
    if len(line) < 3:
        return theme_bank
    t = tonic_pc(composer.key)
    offs = mode_offsets(composer.mode)
    # Same octave base the theme realizer uses (themes/realize.py).
    base = t + 12 * math.floor(((lo + hi) / 2 - 6 - t) / 12)
    events: List[ThemeEvent] = []
    for n in line:
        idx = diatonic_index(n.pitch, composer.key, composer.mode)
        whole = int(idx) if float(idx).is_integer() else int(idx + 0.5)
        accidental = 0 if float(idx).is_integer() else -1
        deg = whole % 7
        octave = round((n.pitch - (base + offs[deg] + accidental)) / 12)
        events.append(ThemeEvent(round(n.beat, 4), n.dur, deg + 1, accidental,
                                 int(octave), accent=n.accent))
    length = 2.0 * bpb
    new_theme = Theme(name=old.name, role=ThemeRole.MELODY, length_beats=length,
                      events=tuple(events), base_register=old.base_register,
                      tags=frozenset({"generated", "composer"}))
    themes = dict(theme_bank.themes)
    themes[names[0]] = new_theme
    bank = type(theme_bank)(themes=themes)
    bank.finalize()
    if logger:
        logger.info("Composer hook adopted as melody theme '%s' (hash %s)",
                    old.name, bank.seed_material_hash)
    return bank
