"""Section-level lead composition: phrase grammar, memory, and narrative.

``SongComposer`` owns the song's DNA, a ``Listener`` that has heard
everything played so far, and a memory of what each section type played.
For every section it builds an abstract *plan* (which idea, which
development, where, how high, which cadence) and realizes it over that
section's harmony.

Why this sounds composed rather than generated:

* **Economy.** Every phrase derives from the DNA (hook, verse idea, bridge
  idea, lick bank). Nothing is a fresh random draw.
* **Form.** Sections use real phrase grammars: a chorus is a hook line
  stated four times with open and closed cadences; a verse is a period; a
  prechorus climbs by sequence; a bridge contrasts; a solo tells a story
  (statement, development, build, climax, resolution).
* **Memory.** A section type recalls its plan on return: the second chorus
  plays the hook the listener already knows, the final chorus lifts it,
  a second verse keeps the melody with small "new lyric" rhythm changes.
* **Managed surprise.** Where a phrase can be developed several ways, the
  listener model scores each candidate and the composer picks the one
  whose surprise matches the phrase's role (establish, develop, climax,
  cadence).

The composer only emits notes; the lead engine performs them (velocity,
humanization, pitch expression).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from ..rng import stable_seed_int
from . import cells as C
from .cells import Cell
from .dna import SongDNA, compose_dna
from .licks import LICKS, Lick, genre_family, realize_lick
from .listener import Listener
from .realize import Note, realize_cell
from .theory import ChordMap, scale_pcs, tonic_pc

# Target information content (mean bits per note of a phrase, judged in
# context by a listener that has heard the song so far). Calibrated on 3,520
# two-bar phrases of human-composed melodies run through the same Listener:
# P20 = 2.0, P30 = 2.5, median = 3.7, P55 = 4.0, P80 = 5.3. A phrase that
# establishes material should be as settled as a typical restatement, a
# development as surprising as a typical fresh phrase, a climax as
# surprising as the top fifth of human phrases, a cadence settled.
IC_TARGET = {"establish": 2.5, "develop": 4.0, "climax": 5.3, "cadence": 2.0}
IC_WEIGHT = 0.9
CONTEXT_WEIGHT = 4.0


@dataclass
class LeadContext:
    """Everything the composer needs to know about one section occurrence."""

    section_id: str
    section_type: str
    occurrence: int
    is_final_of_type: bool
    bars: int
    beats_per_bar: float
    total_beats: float
    key: str
    mode: str
    chord_slots: Sequence
    intensity: float = 0.7
    foreground: str = "auto"
    next_section_type: Optional[str] = None
    register: Tuple[int, int] = (60, 76)
    strict_register: bool = False
    # User shaping of the composed line (lead `rest_probability` and
    # `contour_style`); None / "balanced" leave the composer's choices alone.
    rest_probability: Optional[float] = None
    contour: str = "balanced"
    # Beat grouping of the section's meter (theory.meter_groups); None means
    # the grouping implied by the bar length.
    groups: Optional[Tuple[float, ...]] = None
    # A lead `seed` (instrument or section): re-rolls the lead's own ideas
    # and phrase choices. None plays the song's.
    seed: Optional[int] = None
    prev_section_type: Optional[str] = None
    # The singer's line in this section, as (beat, duration, pitch): the
    # realized melody theme the rest of the band follows. `foreground: auto`
    # choruses answer or harmonize it.
    melody: Optional[Tuple[Tuple[float, float, int], ...]] = None


@dataclass(frozen=True)
class PlanItem:
    kind: str                     # "cell" | "lick" | "guide"
    start: float                  # section-relative beat
    cell: Optional[Cell] = None
    lick: Optional[Lick] = None
    anchor: float = 70.0          # register placement (MIDI pitch)
    cadence: Optional[int] = None  # diatonic degree index the phrase lands on
    role: str = "establish"
    end: float = 0.0              # for "guide" spans
    time_scale: float = 1.0
    variants: bool = False        # let the listener choose a development
    tag: str = ""


def _normalize_type(section_type: str) -> str:
    st = str(section_type or "verse").strip().lower()
    return {"pre-chorus": "prechorus", "pre_chorus": "prechorus", "hook": "chorus",
            "lead": "solo", "interlude": "bridge", "post-chorus": "chorus"}.get(st, st)


class SongComposer:
    """Composes lead parts for a whole song, section by section."""

    def __init__(self, *, seed: int, genre: str, key: str, mode: str,
                 beats_per_bar: float, melody_theme=None,
                 hook_slots: Optional[Sequence] = None,
                 verse_slots: Optional[Sequence] = None,
                 register: Tuple[int, int] = (60, 76),
                 verse_context: Optional[Tuple[str, str, float, Tuple[float, ...]]] = None,
                 groups: Optional[Tuple[float, ...]] = None, arrangement_overrides=None):
        self.arrangement_overrides = arrangement_overrides if isinstance(arrangement_overrides, dict) else None
        self.seed = int(seed)
        self.genre = str(genre or "")
        self.family = genre_family(self.genre)
        self.key = key
        self.mode = mode
        self.bpb = float(beats_per_bar)
        self.groups = tuple(groups) if groups else None
        lo, hi = register
        self._verse_fit = self._fitter(verse_slots, lo + 0.38 * (hi - lo), register, verse_context)
        self.dna: SongDNA = compose_dna(
            seed=self.seed, genre=self.genre, key=key, mode=mode, beats_per_bar=self.bpb,
            melody_theme=melody_theme, country_style=self.arrangement_dna().country_style,
            hook_fit=self._fitter(hook_slots, lo + 0.62 * (hi - lo), register),
            verse_fit=self._verse_fit,
            groups=self.groups,
        )
        self.listener = Listener()
        self._plans: Dict[tuple, List[PlanItem]] = {}
        self._realized: Dict[tuple, List[Note]] = {}
        self._dna_views: Dict[tuple, SongDNA] = {}
        self._part_dnas: Dict[int, SongDNA] = {}
        # The last plain (unlifted) realization per section memory, with its
        # key: the final chorus lifts an authored line relative to it.
        self._last_plain: Dict[tuple, Tuple[List[Note], str]] = {}
        self._fill_counter = 0
        self.log: List[str] = []

    def part_dna(self, seed: Optional[int]) -> SongDNA:
        """The DNA a lead ``seed`` plays: the song's hook and answer (the
        song-level melody every part shares), with the lead's own verse and
        bridge ideas and lick bank drawn from that seed."""
        if seed is None:
            return self.dna
        cached = self._part_dnas.get(int(seed))
        if cached is None:
            fresh = compose_dna(seed=int(seed), genre=self.genre, key=self.key, mode=self.mode,
                                beats_per_bar=self.bpb,
                                country_style=self.arrangement_dna().country_style,
                                verse_fit=self._verse_fit, groups=self.groups)
            base = self.dna
            # Verse and chorus keep contrasting rhythms against the kept hook.
            verse = fresh.verse if fresh.verse.durations != base.hook.durations else base.verse
            sig = base.signature.split("|verse:")[0] + f"|reseed:{int(seed)}|" + ",".join(
                l.name for l in fresh.licks)
            cached = SongDNA(base.hook, base.hook_answer, verse, fresh.bridge, list(fresh.licks),
                             sig, base.authored)
            self._part_dnas[int(seed)] = cached
        return cached

    def comp_dna(self):
        """The rhythm guitar's signature riffs (composer/comping.py), built once."""
        if getattr(self, "_comp_dna", None) is None:
            from .comping import comp_family, compose_comp_dna

            shuffle = comp_family(self.genre) in ("blues", "jazz")
            self._comp_dna = compose_comp_dna(seed=self.seed, genre=self.genre, key=self.key,
                                              mode=self.mode, shuffle=shuffle,
                                              country_style=self.arrangement_dna().country_style)
        return self._comp_dna

    def arrangement_dna(self):
        """Per-song arrangement habits shared by every part (composer/arrangement.py)."""
        if getattr(self, "_arrangement_dna", None) is None:
            from .arrangement import compose_arrangement_dna

            from .arrangement import apply_overrides

            self._arrangement_dna = apply_overrides(
                compose_arrangement_dna(seed=self.seed, genre=self.genre,
                    country_style_override=(getattr(self, "arrangement_overrides", None) or {}).get("country_style")),
                getattr(self, "arrangement_overrides", None))
        return self._arrangement_dna

    def signature_riff(self, beats_per_bar=None, groups=None, seed=None, pocket=(),
                       backbeat=()):
        """One signature per meter, grouping, part seed and drum pocket."""
        from .theory import default_groups

        bpb = self.bpb if beats_per_bar is None else float(beats_per_bar)
        groups = tuple(groups) if groups else self.groups if bpb == self.bpb else default_groups(bpb)
        seed = self.seed if seed is None else seed
        key = (bpb, groups, seed, tuple(pocket), tuple(backbeat))
        if not hasattr(self, "_signature_riffs"):
            self._signature_riffs = {}
        if key not in self._signature_riffs:
            from .riff import compose_signature_riff

            self._signature_riffs[key] = compose_signature_riff(
                seed=seed, genre=self.genre, beats_per_bar=bpb, groups=groups, pocket=pocket,
                backbeat=backbeat)
        return self._signature_riffs[key]

    def bass_dna(self):
        """The song's bass roles per section (composer/bass.py), built once."""
        if getattr(self, "_bass_dna", None) is None:
            from .bass import compose_bass_dna

            self._bass_dna = compose_bass_dna(seed=self.seed, genre=self.genre,
                                               country_style=self.arrangement_dna().country_style)
        return self._bass_dna

    def drum_dna(self):
        """The song's drummer (composer/drums.py), built once."""
        if getattr(self, "_drum_dna", None) is None:
            from .drums import compose_drum_dna

            self._drum_dna = compose_drum_dna(seed=self.seed, genre=self.genre,
                                              beats_per_bar=self.bpb,
                                              country_style=self.arrangement_dna().country_style)
        return self._drum_dna

    def hook_onsets(self, bpb=None, groups=None) -> List[float]:
        """Attack times of the hook line (hook bar, then answer bar)."""
        dna = self._dna_for(bpb, groups) if bpb is not None else self.dna
        return ([n.onset for n in dna.hook.notes]
                + [dna.hook.length + n.onset for n in dna.hook_answer.notes])

    def _fitter(self, slots: Optional[Sequence], anchor: float, register: Tuple[int, int],
                context=None):
        """Realize a candidate idea over a section's opening bar (DNA ranking)."""
        if not slots:
            return None
        key, mode, bpb = context[:3] if context else (self.key, self.mode, self.bpb)
        chords = ChordMap(slots, key, mode)
        lo, hi = register

        def fit(cell: Cell):
            if abs(bpb - self.bpb) > 1e-6:
                cell = C.fit_length(cell, bpb) if cell.length > bpb else C.Cell(cell.notes, bpb, cell.name)
            groups = context[3] if context and len(context) > 3 else self.groups if abs(bpb - self.bpb) < 1e-6 else None
            got, cost = realize_cell(cell, 0.0, chords, key=key, mode=mode,
                                     lo=lo, hi=hi, anchor=anchor, beats_per_bar=bpb,
                                     groups=groups)
            return [n.pitch for n in got], cost

        return fit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compose_lead(self, ctx: LeadContext) -> List[Note]:
        st = _normalize_type(ctx.section_type)
        chords = ChordMap(ctx.chord_slots, ctx.key, ctx.mode)
        if chords.total <= 0 or ctx.bars <= 0:
            return []
        # A lead seed re-rolls the lead's phrase choices as well as its ideas.
        seed = self.seed if ctx.seed is None else int(ctx.seed)
        rng = random.Random(stable_seed_int("composer.section", seed, ctx.section_id,
                                            st, ctx.occurrence))
        memory_key = (st, ctx.bars, ctx.foreground, ctx.beats_per_bar, ctx.register, ctx.strict_register,
                      ctx.groups, ctx.seed)
        base_dna = self.dna
        self.dna = self._dna_for(ctx.beats_per_bar, ctx.groups, part_seed=ctx.seed)
        try:
            return self._compose(st, ctx, chords, rng, memory_key)
        finally:
            self.dna = base_dna

    def _dna_for(self, bpb: float, groups=None, part_seed: Optional[int] = None) -> SongDNA:
        """The DNA fitted to a section's bar length (meter changes)."""
        source = self.part_dna(part_seed)
        target_groups = tuple(groups) if groups else self.groups if abs(bpb - self.bpb) < 1e-6 else None
        if (abs(bpb - self.bpb) < 1e-6 and target_groups == self.groups) or source.authored:
            return source
        view_key = (bpb, target_groups, part_seed)
        cached = self._dna_views.get(view_key)
        if cached is None:
            d = source
            fit = lambda c: C.fit_length(c, bpb) if c.length > bpb + 1e-6 else \
                C.Cell(c.notes, bpb, c.name)
            if target_groups:
                from .dna import group_figure

                def fit(cell):
                    rng = random.Random(stable_seed_int("composer.meter", self.seed, cell.name,
                                                        bpb, target_groups))
                    figure = group_figure(rng, target_groups, "anthem")
                    steps, sounded = [], 0
                    for duration in figure:
                        steps.append(cell.notes[sounded % len(cell.notes)].step if cell.notes else 0)
                        if duration > 0:
                            sounded += 1
                    return C.cell_from([abs(d) for d in figure], steps,
                                       rests=[d < 0 for d in figure], length=bpb, name=cell.name)
            cached = SongDNA(fit(d.hook), fit(d.hook_answer), fit(d.verse), fit(d.bridge),
                             d.licks, d.signature, d.authored)
            self._dna_views[view_key] = cached
        return cached

    def _line_bars(self, bpb: float) -> int:
        """Bars one hook line (hook + answer) spans."""
        length = self.dna.hook.length + self.dna.hook_answer.length
        return max(2, int(math.ceil(length / bpb - 1e-6)))

    def _compose(self, st, ctx, chords, rng, memory_key) -> List[Note]:
        plan = self._plans.get(memory_key)
        recalled = plan is not None and st != "solo"
        lifted = False
        if not recalled:
            plan = self._plan_section(st, ctx, rng)
            if st != "solo":
                self._plans[memory_key] = plan
        else:
            new_plan = self._recall(plan, st, ctx, rng)
            lifted = new_plan is not plan
            plan = new_plan
        # A returning section over the same chords plays exactly what the
        # listener already knows; only deliberate recall changes (final
        # chorus lift, second-verse rhythm) produce new notes.
        # A harmony line follows the singer, so it is only note for note when
        # the singer's line is too.
        sung = ctx.melody if any(i.kind == "harmony" for i in plan) else None
        exact_key = (memory_key, chords.signature(), ctx.register, ctx.key, ctx.mode,
                     ctx.rest_probability, ctx.contour, sung)
        detail = ""
        if recalled and not lifted and exact_key in self._realized:
            notes = list(self._realized[exact_key])
        else:
            notes = _tidy(self._realize_plan(plan, ctx, chords, rng), ctx.total_beats)
            if lifted and st == "chorus" and self.dna.authored:
                notes, detail = self._lift_authored(notes, ctx, self._last_plain.get(memory_key))
            if ctx.strict_register:
                lo, hi = ctx.register
                notes = [replace(n, pitch=min(
                    (p for p in range(lo, hi + 1) if p % 12 == n.pitch % 12),
                    key=lambda p: (abs(p - n.pitch), p), default=max(lo, min(hi, n.pitch))))
                         for n in notes]
            if st != "solo" and not lifted:
                self._realized.setdefault(exact_key, notes)
        if st != "solo" and not lifted:
            self._last_plain[memory_key] = (notes, ctx.key)
        self.listener.observe([n.pitch for n in notes], [n.dur for n in notes])
        self.log.append(
            f"{ctx.section_id} ({st} #{ctx.occurrence + 1}, {ctx.foreground}): "
            f"{'recalled' if recalled else 'composed'} {len(plan)} phrase items, {len(notes)} notes"
            + (f"; {detail}" if detail else "")
        )
        return notes

    def _lift_authored(self, notes: List[Note], ctx: LeadContext,
                       reference: Optional[Tuple[List[Note], str]]) -> Tuple[List[Note], str]:
        """The final chorus lift for an authored melody.

        Authored notes are never reshaped, so the lift moves the whole line:
        up an octave when it fits (a named register may use the solo's
        headroom, a numeric range is a hard bound). When the final chorus
        changes key, the key change is the lift: the line keeps the octave
        the last chorus sat in, moved by the key change. Either way the held
        notes get vibrato and each line slides into its first note. Only the
        final chorus changes; earlier choruses keep the authored notes.
        """
        lo, hi = ctx.register
        ceiling = hi if ctx.strict_register else _solo_top(lo, hi)
        line = [n for n in notes if n.role == "melody"]
        detail = "final chorus: authored line embellished"
        shift = 0
        if line:
            low, high = min(n.pitch for n in line), max(n.pitch for n in line)
            fits = [k for k in (-12, 0, 12) if low + k >= lo and high + k <= ceiling]
            ref_line = [n for n in (reference[0] if reference else []) if n.role == "melody"]
            moved = (tonic_pc(ctx.key) - tonic_pc(reference[1])) % 12 if reference else 0
            mean = sum(n.pitch for n in line) / len(line)
            if moved and ref_line and fits:
                # Up by the key change (a fourth or less), from where the line was.
                step = moved if moved <= 5 else moved - 12
                target = sum(n.pitch for n in ref_line) / len(ref_line) + step
                shift = min(fits, key=lambda k: (abs(mean + k - target), k))
                detail = "final chorus: the key change lifts the authored line"
            elif 12 in fits:
                shift = 12
                detail = "final chorus: authored line lifted an octave"
            elif line:
                detail = ("final chorus: an octave lift does not fit the register; "
                          "authored line embellished")
        bpb = ctx.beats_per_bar
        line_len = self._line_bars(bpb) * bpb
        out: List[Note] = []
        for n in notes:
            if n.role != "melody":
                out.append(n)
                continue
            tech = n.tech
            if tech is None and n.dur >= 1.5:
                tech = "vib"
            elif tech is None and line_len > 0 and abs(n.beat / line_len - round(n.beat / line_len)) < 1e-6:
                tech = "slide"
            out.append(replace(n, pitch=n.pitch + shift, tech=tech))
        return out, detail

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    def _registers(self, ctx: LeadContext, st: str) -> Tuple[int, int, Dict[str, float]]:
        lo, hi = ctx.register
        span = hi - lo
        anchors = {
            "verse": lo + 0.38 * span,
            "chorus": lo + 0.62 * span,
            "prechorus": lo + 0.45 * span,
            "bridge": lo + 0.5 * span,
            "intro": lo + 0.55 * span,
            "outro": lo + 0.5 * span,
            "breakdown": lo + 0.5 * span,
            "solo": lo + 0.55 * span,
        }
        return lo, hi, anchors

    def _plan_section(self, st: str, ctx: LeadContext, rng: random.Random) -> List[PlanItem]:
        full = ctx.foreground == "full"
        if st == "solo":
            return self._plan_solo(ctx, rng)
        if st == "chorus":
            if not full:
                return self._plan_chorus_counter(ctx, rng)
            return self._with_phrase_fills(ctx, self._plan_chorus(ctx, rng))
        if st == "verse":
            if not full:
                return self._plan_fills(ctx, rng)
            return self._with_phrase_fills(ctx, self._plan_verse(ctx, rng))
        if st == "prechorus":
            return self._plan_prechorus(ctx, rng)
        if st == "bridge":
            return self._plan_bridge(ctx, rng)
        if st == "intro":
            return self._plan_intro(ctx, rng)
        if st == "outro":
            return self._plan_outro(ctx, rng)
        if st == "breakdown":
            return self._plan_breakdown(ctx, rng)
        return self._plan_verse(ctx, rng) if full else self._plan_fills(ctx, rng)

    def _hook_line(self, bar: int, ctx: LeadContext, anchor: float, *,
                   cadence: Optional[int], role: str, answer_variants: bool) -> List[PlanItem]:
        bpb = ctx.beats_per_bar
        start = bar * bpb
        items = [PlanItem("cell", start, cell=self.dna.hook, anchor=anchor,
                          role=role, tag="hook")]
        answer_at = start + self.dna.hook.length
        if answer_at < ctx.total_beats - 1e-6:
            answer = self.dna.hook_answer
            if self.dna.authored:
                # Authored material keeps its own ending.
                cadence, answer_variants = None, False
            else:
                answer = C.fit_length(answer, min(answer.length, ctx.total_beats - answer_at))
                if cadence is not None:
                    answer = C.cadence(answer, cadence)
            items.append(PlanItem("cell", answer_at, cell=answer, anchor=anchor,
                                  cadence=cadence, role="cadence" if cadence is not None else role,
                                  variants=answer_variants, tag="answer"))
        return items

    def _cadence_degree(self, closing: bool, rng: random.Random) -> int:
        # Diatonic ladder indices: 0 tonic, 2 third, 4 fifth, 1 second.
        if closing:
            return 0
        return 4 if rng.random() < 0.6 else 1

    def _plan_chorus(self, ctx, rng) -> List[PlanItem]:
        """Hook lines in an A A' B A'' form: state, answer open, lift, close.

        The third line (B) is where a chorus peaks: the hook is sequenced up
        and answered with a held high note, so the chorus has one summit
        instead of four equal statements. Short choruses keep plain A lines.
        """
        lo, hi, anchors = self._registers(ctx, "chorus")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        line = self._line_bars(bpb)
        units = ctx.bars // line
        for u in range(units):
            last = u == units - 1
            phrase_end = (u % 2 == 1)
            cad = self._cadence_degree(True, rng) if last else (
                self._cadence_degree(False, rng) if phrase_end else None)
            form = self.arrangement_dna().chorus_form
            if form == "call" and u % 2 == 1 and line == 2 and not last and \
                    not self.dna.authored:
                # Call and answer between lines: the hook's shape sequenced
                # down a step, closing on the half cadence.
                items.append(PlanItem("cell", 2 * u * bpb, cell=C.transpose(self.dna.hook, -2),
                                      anchor=anchors["chorus"] - 2, role="develop",
                                      variants=True, tag="hook_call"))
                answer = C.cadence(C.fit_length(self.dna.hook_answer, bpb), 4)
                items.append(PlanItem("cell", (2 * u + 1) * bpb, cell=answer,
                                      anchor=anchors["chorus"] - 2, cadence=4, role="cadence",
                                      tag="answer"))
                continue
            if form == "lift" and units >= 4 and u == units - 2 and line == 2 and \
                    not self.dna.authored:
                lift = rng.choice((1, 2))
                peak_anchor = min(hi - 2, anchors["chorus"] + 3)
                items.append(PlanItem("cell", 2 * u * bpb, cell=C.transpose(self.dna.hook, lift),
                                      anchor=peak_anchor, role="develop", variants=True,
                                      tag="hook_lift"))
                head = C.fragment(self.dna.hook_answer, bpb / 2.0)
                summit = C.concat(head, C.Cell((C.CellNote(0.0, bpb / 2.0, 2, tech="vib"),),
                                               bpb / 2.0)) if head.notes else self.dna.hook_answer
                items.append(PlanItem("cell", (2 * u + 1) * bpb, cell=summit, anchor=peak_anchor,
                                      role="climax", variants=True, tag="summit"))
                continue
            items += self._hook_line(line * u, ctx, anchors["chorus"], cadence=cad,
                                     role="establish", answer_variants=u >= 2 and not last)
        for bar in range(units * line, ctx.bars):
            # Bars left over after whole hook lines: the hook itself when no
            # line fit, otherwise a closing cadence on the liquidated hook.
            cell = C.fit_length(self.dna.hook, bpb) if units == 0 and bar == 0 else \
                C.cadence(C.fit_length(C.liquidate(self.dna.hook), bpb), 0)
            items.append(PlanItem("cell", bar * bpb, cell=cell, anchor=anchors["chorus"],
                                  cadence=None if units == 0 and bar == 0 and ctx.bars > 1 else 0,
                                  role="cadence", tag="chorus_close"))
        return items

    def _auto_chorus_form(self) -> Optional[str]:
        """The chorus form for a lead playing around a singer.

        A pinned ``counter`` with a drawn ``chorus_form`` keeps the plain
        counter-line the user asked for; otherwise the song's chorus form
        (pinned or drawn) shapes the chorus.
        """
        pins = self.arrangement_overrides or {}

        def pinned(name):
            from .arrangement import _CHOICES

            value = pins.get(name)
            return isinstance(value, str) and value.strip().lower() in _CHOICES[name]

        if pinned("counter") and not pinned("chorus_form"):
            return None
        return self.arrangement_dna().chorus_form

    def _plan_chorus_counter(self, ctx, rng) -> List[PlanItem]:
        """Vocal-song chorus: the song's chorus form played around the singer,
        then the guitar hook as a tag in the last two bars.

        ``lift``: the counter-line climbs line by line to a summit before the
        tag. ``call``: the lead stays out of each vocal line and answers it
        with a lick in the singer's hold or breath. ``anthem``: the lead
        harmonizes the chorus melody in thirds and sixths, like a band
        singing along. With no form (a pinned counter), a plain counter-line.
        """
        lo, hi, anchors = self._registers(ctx, "chorus")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        tag_bars = 2 if ctx.bars >= 6 else 0
        body = ctx.bars - tag_bars
        style = self.arrangement_dna().counter
        form = self._auto_chorus_form()
        line = 2
        if form == "anthem" and body >= 1:
            for bar in range(0, body, line):
                items.append(PlanItem("harmony", bar * bpb, anchor=anchors["chorus"] + 2,
                                      end=min(body, bar + line) * bpb, role="establish",
                                      tag="anthem_harmony"))
        elif form == "call" and body >= line:
            items += self._plan_call_answers(ctx, body, anchors)
        elif form == "lift" and body >= 2 * line:
            items += self._plan_counter_lift(ctx, body, style, anchors, hi)
        elif style == "fills":
            # Stay out of the singer's way: answer phrase ends only.
            sub = _sub_context(ctx, ctx.bars - tag_bars)
            items += [i for i in self._plan_fills(sub, rng)]
        else:
            kind = {"octaves": "octaves", "stabs": "stabs"}.get(style, "guide")
            items.append(PlanItem(kind, 0.0, anchor=anchors["chorus"] + 2,
                                  end=(ctx.bars - tag_bars) * bpb, role="establish",
                                  tag="counter"))
        if tag_bars:
            items += self._hook_line(ctx.bars - 2, ctx, anchors["chorus"], cadence=0,
                                     role="establish", answer_variants=False)
        return items

    def _plan_call_answers(self, ctx, body: int, anchors) -> List[PlanItem]:
        """``call`` under a singer: silence under each two-bar vocal line and
        a signature lick in its hold or breath, landing as the singer
        returns."""
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        for bar in range(0, body - 1, 2):
            start, end = bar * bpb, (bar + 2) * bpb
            h_start, h_end = _singer_hole(ctx.melody, start, end, bpb)
            lick = self._next_fill_lick(max_len=h_end - h_start, ctx=ctx)
            if lick is None:
                continue
            placed = _place_lick(lick, h_start, h_end)
            if placed is None:
                continue
            at, scale, lick = placed
            items.append(PlanItem("lick", at, lick=lick, anchor=anchors["chorus"] + 2,
                                  time_scale=scale, tag="call_answer"))
        return items

    def _plan_counter_lift(self, ctx, body: int, style: str, anchors, hi: int) -> List[PlanItem]:
        """``lift`` under a singer: the counter-line climbs line by line to a
        summit just before the hook tag.

        Stabs climb in their own voice. Octave roots are tied to each chord's
        root and fills to their licks' shapes, so neither can carry a climb:
        with those voices the lift is played as the sustained descant.
        """
        bpb = ctx.beats_per_bar
        lines = max(1, body // 2)
        low_anchor = anchors["chorus"] - 1
        peak = max(low_anchor, min(hi - 3, anchors["chorus"] + 5))
        kind = "stabs" if style == "stabs" else "guide"
        items: List[PlanItem] = []
        for u in range(lines):
            start = 2 * u * bpb
            end = (body if u == lines - 1 else 2 * (u + 1)) * bpb
            anchor = low_anchor + (peak - low_anchor) * (u / max(1, lines - 1))
            items.append(PlanItem(kind, start, anchor=anchor, end=end,
                                  role="climax" if u == lines - 1 else "develop",
                                  tag="counter_lift"))
        return items

    def _plan_verse(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "verse")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        units = max(1, ctx.bars // 2)
        idea = self.dna.verse
        for u in range(units):
            bar = 2 * u
            last = u == units - 1
            phrase_end = (u % 2 == 1)
            items.append(PlanItem("cell", bar * bpb, cell=idea, anchor=anchors["verse"],
                                  role="establish" if u % 2 == 0 else "develop",
                                  variants=u >= 2, tag="verse"))
            if bar + 1 < ctx.bars:
                cad = 0 if last else (self._cadence_degree(False, rng) if phrase_end else None)
                cont = C.vary_tail(idea, rng, keep=0.5, end_long=True)
                if cad is not None:
                    cont = C.cadence(cont, cad)
                items.append(PlanItem("cell", (bar + 1) * bpb, cell=cont, anchor=anchors["verse"],
                                      cadence=cad, role="cadence" if cad is not None else "develop",
                                      variants=cad is None, tag="verse_cont"))
        return items

    def _plan_fills(self, ctx, rng) -> List[PlanItem]:
        """Vocal-song verse: answer licks at the end of every phrase."""
        lo, hi, anchors = self._registers(ctx, "verse")
        bpb = ctx.beats_per_bar
        every = {"sparse": 8, "normal": 4, "chatty": 2}.get(self.arrangement_dna().lead_fills, 4)
        phrase = every if ctx.bars >= every else max(1, ctx.bars)
        items: List[PlanItem] = []
        for p_end in range(phrase - 1, ctx.bars, phrase):
            lick = self._next_fill_lick(max_len=bpb * 0.75 + 0.5, ctx=ctx)
            if lick is None:
                continue
            room = max(bpb - 1.0, bpb * 0.6)  # leave the singer the bar's head
            scale = min(1.0, room / lick.length)
            start = (p_end + 1) * bpb - lick.length * scale
            items.append(PlanItem("lick", start, lick=lick, anchor=anchors["verse"] + 4,
                                  time_scale=scale, tag="fill"))
        return items

    def _with_phrase_fills(self, ctx, items: List[PlanItem]) -> List[PlanItem]:
        """Fills between the lead's own melody phrases (``foreground: full``).

        A country lead player answers his own lines with the song's licks
        (chicken picking, double stops), so a country song gets them at its
        ``lead_fills`` rate. Other genres get them only when ``lead_fills``
        is pinned. The phrase's last bar keeps its first half, landing on its
        cadence, and the fill answers in the second half (see
        ``_phrase_end_fill``, which gives way when there is no room).
        """
        pins = self.arrangement_overrides or {}
        pinned = str(pins.get("lead_fills") or "").strip().lower() in ("sparse", "normal", "chatty")
        if not (self.arrangement_dna().country_style or pinned):
            return items
        lo, hi, anchors = self._registers(ctx, "verse")
        bpb = ctx.beats_per_bar
        every = {"sparse": 8, "normal": 4, "chatty": 2}.get(self.arrangement_dna().lead_fills, 4)
        fill_bars = set(range(every - 1, ctx.bars, every))
        out: List[PlanItem] = []
        for it in items:
            bar = int(round(it.start / bpb, 6)) if bpb > 0 else -1
            one_bar = it.cell is not None and it.cell.length <= bpb + 1e-6 and \
                abs(it.start - bar * bpb) < 1e-6
            # Authored cells (pinned degrees before the last note) are never cut.
            authored = one_bar and any(n.degree is not None for n in it.cell.notes[:-1])
            if bar in fill_bars and one_bar and not authored:
                head = C.fragment(it.cell, bpb / 2.0)
                if len(head.notes) >= 1:
                    if it.cadence is not None:
                        head = C.cadence(head, it.cadence)
                    it = replace(it, cell=head)
            out.append(it)
        for p_end in sorted(fill_bars):
            lick = self._next_fill_lick(max_len=bpb, ctx=ctx)
            if lick is None:
                continue
            out.append(PlanItem("lick", p_end * bpb, lick=lick, anchor=anchors["verse"] + 4,
                                end=(p_end + 1) * bpb, tag="phrase_fill"))
        return out

    def _next_fill_lick(self, *, max_len: float, ctx: LeadContext) -> Optional[Lick]:
        bank = self.dna.licks or list(LICKS[:3])
        # Cycle A B A C: repetition first, then the new one.
        order = [0, 1, 0, 2] if len(bank) >= 3 else list(range(len(bank)))
        lick = bank[order[self._fill_counter % len(order)] % len(bank)]
        self._fill_counter += 1
        return lick

    def _plan_prechorus(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "prechorus")
        bpb = ctx.beats_per_bar
        # Climb on whichever idea has the fuller head; a two-note fragment
        # cannot carry a sequence.
        heads = [C.fragment(c, bpb / 2.0) for c in (self.dna.hook, self.dna.verse)]
        frag = max(heads, key=lambda f: len(f.notes))
        if len(frag.notes) < 3:
            frag = self.dna.hook if len(self.dna.hook.notes) >= len(self.dna.verse.notes) \
                else self.dna.verse
        items: List[PlanItem] = []
        for bar in range(ctx.bars):
            rise = bar / max(1, ctx.bars - 1)
            anchor = anchors["prechorus"] + rise * (hi - anchors["prechorus"]) * 0.6
            if bar == ctx.bars - 1:
                # Hold the dominant: the tension the chorus releases.
                held = C.Cell((C.CellNote(0.0, 0.5, 1), C.CellNote(0.5, bpb - 0.5, 1, tech="vib",
                                                                   degree=4)), bpb, "pre_hold")
                items.append(PlanItem("cell", bar * bpb, cell=held, anchor=anchor, cadence=4,
                                      role="climax", tag="pre_hold"))
            else:
                seq = C.fit_length(C.transpose(frag, bar), bpb)
                items.append(PlanItem("cell", bar * bpb, cell=seq, anchor=anchor,
                                      role="develop", tag="pre_seq"))
        return items

    def _plan_bridge(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "bridge")
        bpb = ctx.beats_per_bar
        idea = self.dna.bridge
        items: List[PlanItem] = []
        half = ctx.bars if ctx.foreground == "full" else max(1, ctx.bars // 2)
        for bar in range(half):
            last = bar == half - 1
            cell = C.transpose(idea, -1) if bar % 2 else idea
            if last:
                cell = C.cadence(cell, 4)
            items.append(PlanItem("cell", bar * bpb, cell=cell, anchor=anchors["bridge"],
                                  cadence=4 if last else None,
                                  role="cadence" if last else "develop",
                                  variants=bar >= 2 and not last, tag="bridge"))
        if half < ctx.bars:
            sub = _sub_context(ctx, half)
            items += [PlanItem(i.kind, i.start + half * bpb, i.cell, i.lick, i.anchor, i.cadence,
                               i.role, i.end, i.time_scale, i.variants, i.tag)
                      for i in self._plan_fills(sub, rng)]
        return items

    def _plan_intro(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "intro")
        items: List[PlanItem] = []
        line = self._line_bars(ctx.beats_per_bar)
        first = 0
        if self.arrangement_dna().riff_driven:
            # A riff-driven intro lets the riff speak; the lead waits for the band.
            first = ctx.bars // 2
            if ctx.bars - first < line:
                return items
        if ctx.bars >= line:
            for bar in range(first, ctx.bars - line + 1, line):
                items += self._hook_line(bar, ctx, anchors["intro"],
                                         cadence=0 if bar + 2 * line > ctx.bars else 4,
                                         role="establish", answer_variants=False)
        else:
            items.append(PlanItem("cell", 0.0, cell=C.fragment(self.dna.hook, ctx.beats_per_bar),
                                  anchor=anchors["intro"], role="establish", tag="hook"))
        return items

    def _plan_outro(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "outro")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        body = max(0, ctx.bars - 2)
        line = self._line_bars(bpb)
        for bar in range(0, body - line + 1, line):
            items += self._hook_line(bar, ctx, anchors["outro"],
                                     cadence=4 if bar + line < body else 0,
                                     role="establish", answer_variants=False)
        tail_start = body if body < ctx.bars else max(0, ctx.bars - 1)
        final = C.cadence(C.fit_length(C.liquidate(self.dna.hook), bpb), 0)
        items.append(PlanItem("cell", tail_start * bpb, cell=final, anchor=anchors["outro"],
                              cadence=0, role="cadence", tag="outro_final"))
        if tail_start + 1 < ctx.bars:
            ring = C.Cell((C.CellNote(0.0, bpb, 0, tech="vib", degree=0),), bpb, "ring")
            items.append(PlanItem("cell", (tail_start + 1) * bpb, cell=ring,
                                  anchor=anchors["outro"], cadence=0, role="cadence",
                                  tag="outro_ring"))
        return items

    def _plan_breakdown(self, ctx, rng) -> List[PlanItem]:
        lo, hi, anchors = self._registers(ctx, "breakdown")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        slow = C.fit_length(C.augment(C.liquidate(self.dna.hook), 2.0), 2 * bpb)
        for bar in range(0, ctx.bars, 4):
            items.append(PlanItem("cell", (bar + 2) * bpb if bar + 2 < ctx.bars else bar * bpb,
                                  cell=slow, anchor=anchors["breakdown"], role="establish",
                                  tag="breakdown_swell"))
        return items

    def _plan_solo(self, ctx, rng) -> List[PlanItem]:
        """A solo as a story: statement, development, build, climax, resolution.

        Solos develop across a song. ``chapter`` counts the solos before this
        one: each takes its licks further along the song's bank and its
        hotter vocabulary, so a second solo is not a replay of the first. A
        solo straight after another continues it (no second hook statement,
        starting from where the first climbed to), and a solo followed by
        another hands over on the dominant instead of playing the song's
        final solo ending.
        """
        lo, hi, anchors = self._registers(ctx, "solo")
        bpb = ctx.beats_per_bar
        unit = 2 if ctx.bars >= 4 else 1
        units = max(1, ctx.bars // unit)
        climax_u = max(0, min(units - 1, int(round(units * 0.72)) - (1 if units > 2 else 0)))
        base = anchors["solo"]
        top = _solo_top(lo, hi) - 3
        chapter = max(0, int(ctx.occurrence))
        continues = _normalize_type(ctx.prev_section_type or "") == "solo"
        hands_on = _normalize_type(ctx.next_section_type or "") == "solo"
        if continues:
            base += (top - base) * 0.35
        fam = self.family
        energetic = sorted((l for l in LICKS if fam in l.families or "rock" in l.families),
                           key=lambda l: (-l.energy, l.name))
        bank = _rotate(self.dna.licks or energetic[:3], chapter)
        story = self.arrangement_dna().solo_story
        if story != "climb" and unit == 2 and units >= 2:
            return self._plan_solo_story(story, ctx, units, climax_u, base, top, bank,
                                         energetic, rng, chapter=chapter, continues=continues,
                                         hands_on=hands_on)
        items: List[PlanItem] = []
        for u in range(units):
            bar = u * unit
            start = bar * bpb
            if u < climax_u:
                progress = u / max(1, climax_u)
            else:
                progress = 1.0 - (u - climax_u) / max(1, units - climax_u)
            anchor = base + (top - base) * progress
            if u == 0:
                if continues:
                    # Carry on from the last solo: its idea, already moving.
                    dev = C.vary_rhythm(C.transpose(self.dna.hook, 1 + chapter), rng)
                    items.append(PlanItem("cell", start, cell=dev, anchor=anchor, role="develop",
                                          variants=True, tag="solo_develop"))
                else:
                    items.append(PlanItem("cell", start, cell=self.dna.hook, anchor=anchor,
                                          role="establish", tag="solo_statement"))
                if unit == 2:
                    lick = bank[0]
                    scale = min(1.0, (bpb - 0.5) / lick.length)
                    items.append(PlanItem("lick", start + 2 * bpb - lick.length * scale, lick=lick,
                                          anchor=anchor, time_scale=scale, tag="solo_answer"))
            elif u == units - 1 and units > 1:
                lick = next((l for l in bank if l.name in ("descending_triplets", "bend_release_home",
                                                           "slow_hand_bend")), bank[-1])
                scale = min(1.0, bpb / lick.length)
                items.append(PlanItem("lick", start, lick=lick, anchor=anchor, time_scale=scale,
                                      tag="solo_resolve"))
                if unit == 2:
                    items.append(self._solo_close(start + bpb, bpb, base, hands_on))
            elif u == climax_u:
                used = {i.lick.name for i in items if i.lick is not None}
                hots = ([l for l in energetic if l.energy >= 0.85 and l.name not in used]
                        or [l for l in energetic if l.name not in used] or energetic[:1])
                hot = hots[chapter % len(hots)]
                scale = min(1.0, bpb / hot.length)
                items.append(PlanItem("lick", start, lick=hot, anchor=top, time_scale=scale,
                                      tag="solo_climax"))
                if unit == 2:
                    peak = C.Cell((C.CellNote(0.0, 0.5, 0), C.CellNote(0.5, bpb - 0.5, 2, tech="bend2")),
                                  bpb, "peak")
                    items.append(PlanItem("cell", start + bpb, cell=peak, anchor=top,
                                          role="climax", tag="solo_peak"))
            else:
                # Development: sequence the hook upward, diminish toward the climax.
                dev = C.transpose(self.dna.hook, u + chapter)
                if progress > 0.5:
                    dev = C.vary_rhythm(dev, rng)
                items.append(PlanItem("cell", start, cell=dev, anchor=anchor, role="develop",
                                      variants=True, tag="solo_develop"))
                if unit == 2:
                    lick = bank[u % len(bank)]
                    scale = min(1.0, (bpb - 0.25) / lick.length)
                    items.append(PlanItem("lick", start + 2 * bpb - lick.length * scale, lick=lick,
                                          anchor=anchor + 2, time_scale=scale, tag="solo_lick"))
        return items

    def _solo_close(self, start: float, bpb: float, anchor: float, hands_on: bool) -> PlanItem:
        """The solo's last bar: the song's solo ending, or, when another solo
        follows, a held dominant that hands the next chorus over."""
        if hands_on:
            turn = C.Cell((C.CellNote(0.0, 0.5, 1), C.CellNote(0.5, bpb - 0.5, 1, tech="vib",
                                                              degree=4)), bpb, "solo_turn")
            return PlanItem("cell", start, cell=turn, anchor=anchor, cadence=4, role="cadence",
                            tag="solo_turn")
        return PlanItem("cell", start, cell=self._solo_ending(bpb), anchor=anchor, cadence=0,
                        role="cadence", tag="solo_final")

    def _solo_ending(self, bpb: float) -> Cell:
        """The solo's last gesture, the song's own (composer/arrangement.py)."""
        ending = self.arrangement_dna().solo_ending
        if ending == "dive" and self.family not in ("rock", "metal", "punk"):
            ending = "hold"
        if ending == "trill" and bpb >= 2:
            trill = tuple(C.CellNote(k * 0.125, 0.125, 0, degree=(1 if k % 2 else 0))
                          for k in range(8))
            return C.Cell(trill + (C.CellNote(1.0, bpb - 1.0, 0, tech="vib", degree=0),),
                          bpb, "final")
        tech = {"dive": "dive", "hold": "vib", "slide_off": "fall"}.get(ending, "vib")
        return C.Cell((C.CellNote(0.0, bpb, 0, tech=tech, degree=0),), bpb, "final")

    def _plan_solo_story(self, story: str, ctx, units: int, climax_u: int, base: float,
                         top: float, bank, energetic, rng, *, chapter: int = 0,
                         continues: bool = False, hands_on: bool = False) -> List[PlanItem]:
        """Solos that are not a climb: they sing the hook, trade with the band,
        or take their time like a slow blues.

        Every two-bar unit carries a full phrase. ``trade`` fills the lead's
        bar (a lick, answered by a second one when the first leaves room)
        and leads back in from the band's bar with a pickup. ``blues`` calls
        and answers inside each unit, AAB across its four-bar lines: the
        first line's call returns over the next line's change, then a new
        call answers them. Its vocabulary starts with the song's own licks.
        """
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []

        def lick_at(start, lick, anchor, tag, room=None) -> float:
            room = room if room is not None else bpb
            scale = min(1.0, room / lick.length)
            items.append(PlanItem("lick", start, lick=lick, anchor=anchor, time_scale=scale,
                                  tag=tag))
            return start + lick.length * scale

        def answer_before(end, lick, anchor, room, tag="solo_answer") -> None:
            # An answering lick that ends at `end`, in `room` beats.
            placed = _place_lick(lick, end - room, end) if room >= 1.0 - 1e-6 else None
            if placed is not None:
                items.append(PlanItem("lick", placed[0], lick=placed[2], anchor=anchor,
                                      time_scale=placed[1], tag=tag))

        slow = sorted((l for l in LICKS if l.energy <= 0.6 and
                       (self.family in l.families or "blues" in l.families)),
                      key=lambda l: (l.energy, l.name)) or bank
        # The song's own licks lead the blues vocabulary, so every song's slow
        # blues speaks in its own voice; the shared vocabulary follows.
        vocab = _rotate(list(bank) + [l for l in slow if l not in bank], chapter) or bank
        for u in range(units):
            start = u * 2 * bpb
            progress = u / max(1, units - 1)
            anchor = base + (top - base) * min(1.0, progress * 1.2)
            if u == units - 1:
                lick_at(start, vocab[u % len(vocab)] if story == "blues" else bank[0], base,
                        "solo_resolve")
                items.append(self._solo_close(start + bpb, bpb, base, hands_on))
                continue
            if story == "melodic":
                # The solo sings: hook, answer, the hook lifted, a held summit.
                if u == climax_u:
                    peak = C.Cell((C.CellNote(0.0, 0.5, 0), C.CellNote(0.5, 2 * bpb - 0.5, 2,
                                                                         tech="bend2")),
                                  2 * bpb, "peak")
                    items.append(PlanItem("cell", start, cell=peak, anchor=top, role="climax",
                                          tag="solo_peak"))
                    continue
                k = u + chapter
                hook = self.dna.hook if k % 2 == 0 else C.transpose(self.dna.hook, 2)
                if k >= 2:
                    hook = C.ornament(hook, rng)
                statement = u == 0 and not continues
                items.append(PlanItem("cell", start, cell=hook, anchor=anchor,
                                      role="establish" if statement else "develop",
                                      tag="solo_statement" if statement else "solo_develop"))
                answer = C.fit_length(self.dna.hook_answer, bpb)
                if chapter:
                    # A later solo answers its hooks with new endings.
                    answer = C.vary_tail(answer, rng, keep=0.5)
                items.append(PlanItem("cell", start + bpb, cell=answer, anchor=anchor,
                                      role="develop", variants=k > 0, tag="solo_answer"))
            elif story == "trade":
                # Trading: the lead's bar, then the band's bar, with a pickup
                # from the band's bar into the next trade.
                idx = min(len(energetic) - 1, max(0, units - 1 - u))
                hot = energetic[(idx + chapter) % len(energetic)]
                # The song's own licks alternate with busier trading vocabulary.
                trading = [l for l in energetic if 0.5 <= l.energy < 0.85] or list(bank)
                lick = hot if u == climax_u else (
                    bank[u % len(bank)] if u % 2 == 0 else trading[(u // 2 + chapter) % len(trading)])
                at = top if u == climax_u else anchor
                end = lick_at(start, lick, at, "solo_climax" if u == climax_u else "solo_lick")
                second = bank[(u + 1) % len(bank)]
                answer_before(start + bpb - 0.25, second, at,
                              start + bpb - 0.25 - (end + 0.25))
                nxt = base + (top - base) * min(1.0, (u + 1) / max(1, units - 1) * 1.2)
                items.append(PlanItem("cell", start + 2 * bpb - 1.0, cell=_PICKUP, anchor=nxt - 2,
                                      role="develop", tag="solo_pickup"))
            else:  # blues: call and answer, with room to breathe
                line, pos = divmod(u, 2)
                if u == climax_u:
                    lick_at(start, vocab[u % len(vocab)], top, "solo_climax", room=bpb * 1.5)
                    items.append(PlanItem("cell", start + bpb * 1.5, cell=C.Cell(
                        (C.CellNote(0.0, bpb * 0.5, 2, tech="bend2"),), bpb * 0.5, "cry"),
                        anchor=top, role="climax", tag="solo_peak"))
                    continue
                call = vocab[0] if pos == 0 and line < 2 else vocab[(u + 1) % len(vocab)]
                end = lick_at(start, call, anchor, "solo_lick", room=bpb * 1.5)
                reply = vocab[(u + 2) % len(vocab)]
                if reply is call and len(vocab) > 1:
                    reply = vocab[(u + 3) % len(vocab)]
                resp_end = start + 2 * bpb - 0.5
                answer_before(resp_end, reply, anchor + 2, resp_end - (end + 0.5))
        return items

    # ------------------------------------------------------------------
    # Memory: what changes when a section type returns
    # ------------------------------------------------------------------
    def _recall(self, plan: List[PlanItem], st: str, ctx: LeadContext,
                rng: random.Random) -> List[PlanItem]:
        if st == "chorus" and ctx.is_final_of_type and ctx.occurrence > 0:
            # Final chorus: same hook, lifted and embellished.
            lo, hi = ctx.register
            out = []
            for it in plan:
                lift = 5 if it.anchor + 5 <= hi - 1 else 0
                cell = it.cell
                if cell is not None and it.tag == "answer" and it.cadence is None \
                        and not self.dna.authored:
                    cell = C.ornament(cell, rng)
                out.append(PlanItem(it.kind, it.start, cell, it.lick, it.anchor + lift, it.cadence,
                                    it.role, it.end, it.time_scale, it.variants, it.tag))
            return out
        if st == "verse" and ctx.foreground == "full":
            # Second verse: same melody, "new lyrics" rhythm changes.
            out = []
            for it in plan:
                cell = it.cell
                if cell is not None and it.cadence is None and rng.random() < 0.5:
                    cell = C.vary_rhythm(cell, rng)
                out.append(PlanItem(it.kind, it.start, cell, it.lick, it.anchor, it.cadence,
                                    it.role, it.end, it.time_scale, it.variants, it.tag))
            return out
        return plan

    # ------------------------------------------------------------------
    # Realization
    # ------------------------------------------------------------------
    def _apply_rests(self, plan: List[PlanItem], ctx: LeadContext) -> List[PlanItem]:
        """Honor the lead's ``rest_probability``: drop non-structural phrase
        items (answers, developments, fills) so the line leaves more space,
        on a dedicated seeded stream so default output is untouched."""
        rate = ctx.rest_probability
        if rate is None or rate <= 0:
            return plan
        seed = self.seed if ctx.seed is None else int(ctx.seed)
        rng = random.Random(stable_seed_int("composer.rests", seed, ctx.section_id,
                                            ctx.occurrence))
        kept = []
        for it in plan:
            structural = it.tag in _REST_PROOF_TAGS or it.cadence is not None
            if structural or rng.random() >= min(0.9, float(rate)):
                kept.append(it)
        return kept

    def _realize_plan(self, plan: List[PlanItem], ctx: LeadContext, chords: ChordMap,
                      rng: random.Random) -> List[Note]:
        lo, hi = ctx.register
        solo = _normalize_type(ctx.section_type) == "solo"
        if solo and not ctx.strict_register:
            hi = _solo_top(lo, hi)
        notes: List[Note] = []
        prev: Optional[int] = None
        plan = self._apply_rests(plan, ctx)
        climax_at = min((i.start for i in plan if i.tag in ("solo_climax", "solo_peak")),
                        default=None)
        peak_hi = hi
        for it in sorted(plan, key=lambda i: i.start):
            if it.start >= ctx.total_beats - 1e-6:
                continue
            # A soloist saves the top of the neck for the climax.
            hi = peak_hi - 4 if climax_at is not None and it.start < climax_at - 1e-6 else peak_hi
            if it.kind == "lick" and it.tag == "phrase_fill":
                got = self._phrase_end_fill(it, ctx, chords, lo, hi, prev, notes)
            elif it.kind == "lick" and it.lick is not None:
                # Move the hand, not teleport it: a lick starts near where the
                # line already is, pulled toward the plan's register.
                anchor = it.anchor if prev is None else 0.6 * it.anchor + 0.4 * prev
                if it.tag == "solo_resolve":
                    # The resolution comes home to the solo's own register.
                    anchor = it.anchor
                got = realize_lick(it.lick, it.start, chords, key=ctx.key, mode=ctx.mode,
                                   lo=lo, hi=hi, anchor=int(round(anchor)),
                                   beats_per_bar=ctx.beats_per_bar, time_scale=it.time_scale)
            elif it.kind == "harmony":
                got = self._harmony_line(it, ctx, chords, lo, hi)
            elif it.kind == "guide":
                got = self._guide_line(it, ctx, chords, lo, hi, prev)
            elif it.kind in ("octaves", "stabs"):
                got = self._rhythmic_counter(it, ctx, chords, lo, hi)
            elif it.cell is not None:
                got = self._realize_cell_item(it, ctx, chords, lo, hi, prev, rng, notes)
            else:
                got = []
            if got:
                notes.extend(got)
                prev = got[-1].pitch
        return notes

    def _phrase_end_fill(self, it: PlanItem, ctx, chords, lo, hi, prev,
                         so_far: List[Note]) -> List[Note]:
        """A fill between the lead's own melody phrases (``foreground: full``).

        The phrase's landing note sounds for half a beat (or all of it, when
        shorter) before the fill, which ends on the next phrase's downbeat. No room,
        no fill: the melody always comes first.
        """
        before = [n for n in so_far if it.start - 1e-6 <= n.beat < it.end - 1e-6] or \
            [n for n in so_far if n.beat < it.start]
        last = max(before, key=lambda n: n.beat) if before else None
        hole_start = it.start if last is None else max(it.start, last.beat + min(last.dur, 0.5))
        placed = _place_lick(it.lick, hole_start, it.end) if it.lick is not None else None
        if placed is None:
            return []
        at, scale, lick = placed
        anchor = it.anchor if prev is None else 0.6 * it.anchor + 0.4 * prev
        return realize_lick(lick, at, chords, key=ctx.key, mode=ctx.mode, lo=lo, hi=hi,
                            anchor=int(round(anchor)), beats_per_bar=ctx.beats_per_bar,
                            time_scale=scale)

    def _harmony_line(self, it: PlanItem, ctx, chords: ChordMap, lo, hi) -> List[Note]:
        """``anthem`` under a singer: the chorus melody harmonized a diatonic
        third above, like a band singing along.

        Each harmony note is a diatonic third or sixth above the singer (a
        fourth or fifth only as a last resort), chosen like a second singer
        would: a chord tone where the note is long or on a strong beat, and
        moving with the singer (parallel thirds and sixths) where the chord
        allows, so a repeated sung note keeps one harmony note. The whole line moves by octaves into the lead's
        register (below the singer when above does not fit), so its shape
        survives.
        """
        from .theory import metric_weight

        # Voice the whole section's line, then play this item's part of it,
        # so every line of the chorus sits in the same octave.
        whole = PlanItem("harmony", 0.0, anchor=it.anchor, end=ctx.total_beats)
        sung = [(float(b), float(d), int(p)) for b, d, p in (ctx.melody or ())
                if 0.0 <= float(b) < ctx.total_beats - 1e-6]
        if not sung and not ctx.melody:
            sung = [(n.beat, n.dur, n.pitch)
                    for n in self._own_hook_line(whole, ctx, chords, lo, hi)]
        if not sung:
            return []
        scale = set(scale_pcs(ctx.key, ctx.mode))
        bpb = ctx.beats_per_bar
        voiced: List[Tuple[float, float, int]] = []
        prev_h: Optional[int] = None
        prev_p = 0
        for i, (b, d, p) in enumerate(sung):
            span = chords.at(min(b, chords.total - 0.01))
            pcs = span.pcs if span is not None else tuple(scale)
            mw = metric_weight(b % bpb, bpb, ctx.groups) if bpb > 0 else 1.0

            def cost(iv: int) -> float:
                h = p + iv
                c = {3: 0.0, 4: 0.0, 8: 0.6, 9: 0.6}.get(iv, 1.5)  # thirds, sixths
                if h % 12 not in pcs:
                    # Over a sung passing note the harmony passes too.
                    c += 3.0 * mw + (1.5 if d >= 1.0 else 0.0) if p % 12 in pcs else 0.4
                if prev_h is not None:
                    # Move with the singer (parallel thirds and sixths).
                    c += 0.3 * abs((h - prev_h) - (p - prev_p))
                return c

            options = [iv for iv in (3, 4, 8, 9, 5, 7) if (p + iv) % 12 in scale]
            h = p + min(options, key=lambda iv: (cost(iv), iv)) if options else p + 3
            prev_h, prev_p = h, p
            nxt = sung[i + 1][0] if i + 1 < len(sung) else ctx.total_beats
            voiced.append((b, max(0.1, min(d, nxt - b - 0.02)), h))
        mean = sum(h for _, _, h in voiced) / len(voiced)
        shift = min((-24, -12, 0, 12),
                    key=lambda k: (sum(1 for _, _, h in voiced if not lo <= h + k <= hi),
                                   abs(mean + k - it.anchor), k))
        out: List[Note] = []
        for b, d, h in voiced:
            if not it.start - 1e-6 <= b < it.end - 1e-6:
                continue
            pitch = h + shift
            while pitch > hi:
                pitch -= 12
            while pitch < lo:
                pitch += 12
            out.append(Note(round(b, 4), min(d, it.end - b), pitch, accent=False,
                            tech="vib" if d >= 1.5 else None, role="harmony"))
        return out

    def _own_hook_line(self, it: PlanItem, ctx, chords: ChordMap, lo, hi) -> List[Note]:
        """The hook lines over [start, end), for a song with no melody theme
        to harmonize (the composer's hook is the chorus melody then)."""
        bpb = ctx.beats_per_bar
        out: List[Note] = []
        prev = None
        line = self._line_bars(bpb) * bpb
        t = it.start
        while t < it.end - 1e-6:
            for cell, at in ((self.dna.hook, t), (self.dna.hook_answer, t + self.dna.hook.length)):
                if at >= it.end - 1e-6:
                    continue
                got, _ = realize_cell(cell, at, chords, key=ctx.key, mode=ctx.mode, lo=lo, hi=hi,
                                      anchor=it.anchor - 2, prev_pitch=prev,
                                      beats_per_bar=bpb, exact_degrees=self.dna.authored,
                                      groups=ctx.groups)
                got = [n for n in got if n.beat < it.end - 1e-6]
                out += got
                prev = got[-1].pitch if got else prev
            t += line
        return out

    def _realize_cell_item(self, it: PlanItem, ctx, chords, lo, hi, prev, rng,
                           so_far: List[Note]) -> List[Note]:
        cad_pcs = None
        cell_in = it.cell
        exact = any(n.degree is not None for n in it.cell.notes[:-1])
        if it.cadence is not None and not exact:
            span = chords.at(min(it.start + it.cell.length - 0.01, chords.total - 0.01))
            degree_pc = _degree_pc(it.cadence, ctx.key, ctx.mode)
            cad_pcs = [degree_pc]
            if span is not None and degree_pc not in span.pcs:
                # The harmony has the last word: re-aim the cadence at the
                # nearest scale degree the chord contains, instead of pinning
                # a degree the chord forbids (which flattens the whole line).
                chord_degrees = [d for d in range(-3, 11)
                                 if _degree_pc(d, ctx.key, ctx.mode) in span.pcs]
                if chord_degrees:
                    target = min(chord_degrees, key=lambda d: (abs(d - it.cadence), d))
                    cell_in = C.cadence(it.cell, target)
                    cad_pcs = [_degree_pc(target, ctx.key, ctx.mode)]
                else:
                    cad_pcs = list(span.pcs)
        options = [cell_in]
        if it.variants and not exact:
            options += [C.vary_tail(cell_in, rng, keep=0.5), C.vary_rhythm(cell_in, rng),
                        C.ornament(cell_in, rng)]
        context = [(n.pitch, n.dur) for n in so_far[-4:]]
        after_rest = not so_far or (it.start + (it.cell.notes[0].onset if it.cell.notes else 0.0)
                                    - (so_far[-1].beat + so_far[-1].dur)) >= 0.5
        best = None
        for k, cell in enumerate(options):
            got, cost = realize_cell(cell, it.start, chords, key=ctx.key, mode=ctx.mode,
                                     lo=lo, hi=hi, anchor=it.anchor, prev_pitch=prev,
                                     cadence_pcs=cad_pcs, beats_per_bar=ctx.beats_per_bar,
                                     exact_degrees=exact,
                                     entry_after_rest=after_rest,
                                     leap_scale=_LEAP_SCALE.get(ctx.contour, 1.0),
                                     groups=ctx.groups)
            if not got:
                continue
            score = cost
            if len(options) > 1:
                ic = self.listener.mean_information([n.pitch for n in got], [n.dur for n in got],
                                                    context)
                score += IC_WEIGHT * abs(ic - IC_TARGET.get(it.role, 3.0))
                score += CONTEXT_WEIGHT * self.listener.contextual_cost(
                    got, chords, ctx.beats_per_bar, ctx.groups)
                score += 0.05 * k  # ties favor the plainer development
            if best is None or score < best[0]:
                best = (score, got)
        return best[1] if best else []

    def _rhythmic_counter(self, it: PlanItem, ctx, chords: ChordMap, lo, hi) -> List[Note]:
        """Punctuating counter-parts: octave root stabs on the changes, or
        short chord-tone stabs on the hook's own attacks."""
        bpb = ctx.beats_per_bar
        out: List[Note] = []
        hook_offsets = sorted({round(n.onset % bpb, 3) for n in self.dna.hook.notes})
        for span in chords.spans:
            if span.start < it.start - 1e-6 or span.start >= it.end - 1e-6:
                continue
            end = min(span.end, it.end)
            if it.kind == "octaves":
                root = min((p for p in range(lo, hi - 11) if p % 12 == span.root_pc),
                           key=lambda p: (abs(p - it.anchor), p), default=None)
                if root is None:
                    continue
                t = span.start
                while t < end - 0.25:
                    for p in (root, root + 12):
                        out.append(Note(round(t, 4), 0.45, p, accent=True, tech="stac",
                                        role="stab"))
                    t += max(1.0, (end - span.start) / 2.0)
            else:
                third = span.pcs[1] if len(span.pcs) > 1 else span.root_pc
                pitch = min((p for p in range(lo, hi + 1) if p % 12 == third),
                            key=lambda p: (abs(p - it.anchor), p), default=None)
                if pitch is None:
                    continue
                bar0 = math.floor(span.start / bpb) * bpb
                for off in hook_offsets:
                    t = bar0 + off
                    while t < span.start - 1e-6:
                        t += bpb
                    if t < end - 0.2:
                        out.append(Note(round(t, 4), 0.25, pitch, accent=True, tech="stac",
                                        role="stab"))
        return sorted(out, key=lambda n: (n.beat, n.pitch))

    def _guide_line(self, it: PlanItem, ctx, chords: ChordMap, lo, hi, prev) -> List[Note]:
        """A sustained descant: one chord tone per chord, moving by step in a
        planned direction (down across one phrase, up across the next), with
        occasional anticipations and passing tones for forward motion."""
        spans = [sp for sp in chords.spans if sp.end > it.start + 1e-6 and sp.start < it.end - 1e-6]
        if not spans:
            return []
        anchor = it.anchor
        cand_lo, cand_hi = max(lo, int(anchor) - 6), min(hi, int(anchor) + 7)
        out: List[Note] = []
        history: List[int] = []
        current = prev if prev is not None else int(round(anchor + 4))
        per_phrase = max(1, int(round(4 * ctx.beats_per_bar / max(0.5, spans[0].end - spans[0].start))))
        climbing = it.tag == "counter_lift"
        for i, span in enumerate(spans):
            phrase_pos = i % per_phrase
            direction = -1 if (i // per_phrase) % 2 == 0 else 1
            if climbing:
                # A lifting chorus: every line steps up from where the last
                # one ended, toward (not past) its own higher register.
                goal = min(current + 2, anchor + 4) if history or prev is not None else anchor
            elif phrase_pos == 0 and history:
                # Phrase reset: leap back toward the start of the arc.
                goal = anchor + (4 if direction < 0 else -2)
            else:
                goal = current + 2 * direction
            cands = [p for p in range(cand_lo, cand_hi + 1) if p % 12 in span.pcs]
            if not cands:
                continue

            def cost(p: int) -> float:
                c = abs(p - goal) + 0.12 * abs(p - anchor)
                if history and p == history[-1]:
                    c += 1.5
                if len(history) >= 2 and p == history[-2]:
                    c += 1.0  # no ping-pong
                if p % 12 == span.root_pc:
                    c += 0.6  # roots are the bass's job
                return c

            pitch = min(cands, key=lambda p: (cost(p), p))
            end = min(span.end, it.end)
            start = max(span.start, it.start)
            # Anticipate every other change on longer chords (a syncopated push).
            if i % 2 == 1 and end - start >= 2 and start - 0.5 >= it.start and out:
                start -= 0.5
                last = out[-1]
                out[-1] = Note(last.beat, max(0.25, start - last.beat - 0.02), last.pitch,
                               last.accent, last.tech, last.role)
            elif out and abs(pitch - out[-1].pitch) >= 3 and span.start - 0.5 > out[-1].beat + 0.5:
                # Passing tone into a wider move.
                last = out[-1]
                step = 1 if pitch > last.pitch else -1
                passing = next((q for q in range(last.pitch + step, pitch, step)
                                if q % 12 in scale_pcs(ctx.key, ctx.mode)), None)
                if passing is not None:
                    pt_beat = span.start - 0.5
                    out[-1] = Note(last.beat, max(0.25, pt_beat - last.beat - 0.02), last.pitch,
                                   last.accent, last.tech, last.role)
                    out.append(Note(round(pt_beat, 4), 0.48, passing, role="counter"))
            dur = end - start - 0.05
            if dur <= 0.2:
                continue
            out.append(Note(round(start, 4), dur, pitch, accent=True,
                            tech="vib" if dur >= 2 else None, role="counter"))
            history.append(pitch)
            current = pitch
        return out


_LEAP_SCALE = {"stepwise": 2.0, "balanced": 1.0, "leaping": 0.4}
# Phrase items a rest never removes: the hook statement, cadences, and the
# solo's structural moments carry the form.
_REST_PROOF_TAGS = ("hook", "solo_statement", "solo_climax", "solo_peak", "solo_final",
                    "solo_turn", "outro_final", "outro_ring", "pre_hold")
# The pickup a trading soloist plays at the end of the band's bar.
_PICKUP = C.Cell((C.CellNote(0.0, 0.5, 0), C.CellNote(0.5, 0.5, 1)), 1.0, "pickup")


def _rotate(seq, k: int) -> list:
    """``seq`` started ``k`` places along (a later solo's turn through a bank)."""
    seq = list(seq)
    if not seq:
        return seq
    k %= len(seq)
    return seq[k:] + seq[:k]


def _solo_top(lo: int, hi: int) -> int:
    """Solo ceiling: extend a normal register up to D6 (licks may reach E6,
    the top of a 24-fret neck), but never shrink a register already set high."""
    if hi >= 86:
        return min(125, hi)
    return max(min(86, hi + 9), lo + 12)


def _degree_pc(index: int, key: str, mode: str) -> int:
    from .theory import mode_offsets

    offs = mode_offsets(mode)
    return (tonic_pc(key) + offs[index % 7]) % 12


def _place_lick(lick: Lick, earliest: float,
                end: float) -> Optional[Tuple[float, float, Lick]]:
    """Where a fill goes to finish at ``end`` without starting before
    ``earliest``: (start, time_scale, lick). None when it cannot fit.

    The lick plays at its own speed, or in double time when that keeps
    every note on a sixteenth; any other squeeze would put its notes between
    the beat's subdivisions. A lick still too long loses notes from its
    front (never its landing), the way a player cuts a fill to the room
    left, keeping at least two notes.
    """
    notes = list(lick.notes)
    while len(notes) >= 2:
        shift = notes[0][0]
        cut = Lick(lick.name, lick.families,
                   tuple((round(o - shift, 4), d, i, t) for o, d, i, t in notes),
                   round(lick.length - shift, 4), lick.ladder, lick.energy)
        for scale in (1.0, 0.5):
            if scale < 1.0 and any(abs(o * scale * 4 - round(o * scale * 4)) > 1e-6
                                   for o, _, _, _ in cut.notes):
                continue
            start = math.ceil((end - cut.length * scale) * 4 - 1e-6) / 4.0
            if start >= earliest - 1e-6 and end - start >= 0.75 - 1e-6:
                return start, scale, cut
        notes = notes[1:]
    return None


def _singer_hole(melody, start: float, end: float,
                 bpb: float) -> Tuple[float, float]:
    """Where a guitar answers one vocal line in [start, end).

    The hole is the longest stretch after the line's opening with no new sung
    note, from half a beat into a held note (the singer has landed) or from
    the end of a short one, lasting at least a beat. Without a melody, or
    when the singer never stops, the answer takes the end of the line over
    the singer's last note, as a phrase-end fill does.
    """
    tail = (max(start + bpb * 0.5, end - max(1.5, bpb * 0.6)), end)
    if not melody:
        return tail
    sung = sorted((float(b), float(d)) for b, d, _ in melody if start - 1e-6 <= float(b) < end - 1e-6)
    if not sung:
        return start + bpb, end
    best = None
    for i, (b, d) in enumerate(sung):
        h_start = b + (0.5 if d >= 1.0 else d)
        h_end = sung[i + 1][0] if i + 1 < len(sung) else end
        if h_start < start + bpb * 0.5 or h_end - h_start < 1.0 - 1e-6:
            continue
        if best is None or (h_end - h_start, h_start) > (best[1] - best[0], best[0]):
            best = (h_start, h_end)
    return best or tail


def _sub_context(ctx: LeadContext, bars: int) -> LeadContext:
    return replace(ctx, bars=bars, total_beats=bars * ctx.beats_per_bar)


def _tidy(notes: List[Note], total: float) -> List[Note]:
    """Clip monophonic lines, preserving explicitly unbent country double stops."""
    notes = sorted((n for n in notes if 0 <= n.beat < total - 1e-6), key=lambda n: (n.beat, -n.pitch))
    out: List[Note] = []
    for n in notes:
        together = out and abs(out[-1].beat - n.beat) < 1e-6
        double = together and out[-1].role == n.role == "country_double"
        if together and not double:
            continue
        if out and not double and out[-1].beat + out[-1].dur > n.beat - 0.02:
            prev = out[-1]
            out[-1] = Note(prev.beat, max(0.1, n.beat - prev.beat - 0.02), prev.pitch,
                           prev.accent, prev.tech, prev.role)
        dur = min(n.dur, total - n.beat)
        pitch = n.pitch
        while pitch > 127:
            pitch -= 12
        while pitch < 0:
            pitch += 12
        if dur > 0.05:
            out.append(Note(n.beat, dur, pitch, n.accent, n.tech, n.role))
    return out
