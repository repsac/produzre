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
from dataclasses import dataclass, field
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
                 register: Tuple[int, int] = (60, 76)):
        self.seed = int(seed)
        self.genre = str(genre or "")
        self.family = genre_family(self.genre)
        self.key = key
        self.mode = mode
        self.bpb = float(beats_per_bar)
        lo, hi = register
        self.dna: SongDNA = compose_dna(
            seed=self.seed, genre=self.genre, key=key, mode=mode, beats_per_bar=self.bpb,
            melody_theme=melody_theme,
            hook_fit=self._fitter(hook_slots, lo + 0.62 * (hi - lo), register),
            verse_fit=self._fitter(verse_slots, lo + 0.38 * (hi - lo), register),
        )
        self.listener = Listener()
        self._plans: Dict[Tuple[str, int, str], List[PlanItem]] = {}
        self._realized: Dict[tuple, List[Note]] = {}
        self._dna_views: Dict[float, SongDNA] = {}
        self._fill_counter = 0
        self.log: List[str] = []

    def comp_dna(self):
        """The rhythm guitar's signature riffs (composer/comping.py), built once."""
        if getattr(self, "_comp_dna", None) is None:
            from .comping import comp_family, compose_comp_dna

            shuffle = comp_family(self.genre) in ("blues", "jazz")
            self._comp_dna = compose_comp_dna(seed=self.seed, genre=self.genre, key=self.key,
                                              mode=self.mode, shuffle=shuffle)
        return self._comp_dna

    def hook_onsets(self) -> List[float]:
        """Attack times of the hook line (hook bar, then answer bar)."""
        return ([n.onset for n in self.dna.hook.notes]
                + [self.dna.hook.length + n.onset for n in self.dna.hook_answer.notes])

    def _fitter(self, slots: Optional[Sequence], anchor: float, register: Tuple[int, int]):
        """Realize a candidate idea over a section's opening bar (DNA ranking)."""
        if not slots:
            return None
        chords = ChordMap(slots, self.key, self.mode)
        lo, hi = register

        def fit(cell: Cell):
            got, cost = realize_cell(cell, 0.0, chords, key=self.key, mode=self.mode,
                                     lo=lo, hi=hi, anchor=anchor, beats_per_bar=self.bpb)
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
        rng = random.Random(stable_seed_int("composer.section", self.seed, ctx.section_id,
                                            st, ctx.occurrence))
        memory_key = (st, ctx.bars, ctx.foreground, ctx.beats_per_bar)
        base_dna = self.dna
        self.dna = self._dna_for(ctx.beats_per_bar)
        try:
            return self._compose(st, ctx, chords, rng, memory_key)
        finally:
            self.dna = base_dna

    def _dna_for(self, bpb: float) -> SongDNA:
        """The DNA fitted to a section's bar length (meter changes)."""
        if abs(bpb - self.bpb) < 1e-6 or self.dna.authored:
            return self.dna
        cached = self._dna_views.get(bpb)
        if cached is None:
            d = self.dna
            fit = lambda c: C.fit_length(c, bpb) if c.length > bpb + 1e-6 else \
                C.Cell(c.notes, bpb, c.name)
            cached = SongDNA(fit(d.hook), fit(d.hook_answer), fit(d.verse), fit(d.bridge),
                             d.licks, d.signature, d.authored)
            self._dna_views[bpb] = cached
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
        exact_key = (memory_key, chords.signature(), ctx.register, ctx.key, ctx.mode)
        if recalled and not lifted and exact_key in self._realized:
            notes = list(self._realized[exact_key])
        else:
            notes = _tidy(self._realize_plan(plan, ctx, chords, rng), ctx.total_beats)
            if st != "solo" and not lifted:
                self._realized.setdefault(exact_key, notes)
        self.listener.observe([n.pitch for n in notes], [n.dur for n in notes])
        self.log.append(
            f"{ctx.section_id} ({st} #{ctx.occurrence + 1}, {ctx.foreground}): "
            f"{'recalled' if recalled else 'composed'} {len(plan)} phrase items, {len(notes)} notes"
        )
        return notes

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
            return self._plan_chorus(ctx, rng) if full else self._plan_chorus_counter(ctx, rng)
        if st == "verse":
            return self._plan_verse(ctx, rng) if full else self._plan_fills(ctx, rng)
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
            if units >= 4 and u == units - 2 and line == 2 and not self.dna.authored:
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

    def _plan_chorus_counter(self, ctx, rng) -> List[PlanItem]:
        """Vocal-song chorus: a sustained guide-tone counter line, then the
        guitar hook as a tag in the last two bars."""
        lo, hi, anchors = self._registers(ctx, "chorus")
        bpb = ctx.beats_per_bar
        items: List[PlanItem] = []
        tag_bars = 2 if ctx.bars >= 6 else 0
        items.append(PlanItem("guide", 0.0, anchor=anchors["chorus"] + 2,
                              end=(ctx.bars - tag_bars) * bpb, role="establish", tag="counter"))
        if tag_bars:
            items += self._hook_line(ctx.bars - 2, ctx, anchors["chorus"], cadence=0,
                                     role="establish", answer_variants=False)
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
        phrase = 4 if ctx.bars >= 4 else max(1, ctx.bars)
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
        if ctx.bars >= line:
            for bar in range(0, ctx.bars - line + 1, line):
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
        """A solo as a story: statement, development, build, climax, resolution."""
        lo, hi, anchors = self._registers(ctx, "solo")
        bpb = ctx.beats_per_bar
        unit = 2 if ctx.bars >= 4 else 1
        units = max(1, ctx.bars // unit)
        climax_u = max(0, min(units - 1, int(round(units * 0.72)) - (1 if units > 2 else 0)))
        base = anchors["solo"]
        top = _solo_top(lo, hi) - 3
        fam = self.family
        energetic = sorted((l for l in LICKS if fam in l.families or "rock" in l.families),
                           key=lambda l: (-l.energy, l.name))
        bank = self.dna.licks or energetic[:3]
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
                    ring = C.Cell((C.CellNote(0.0, bpb, 0, tech="dive" if fam in ("rock", "metal")
                                              else "vib", degree=0),), bpb, "final")
                    items.append(PlanItem("cell", start + bpb, cell=ring, anchor=base, cadence=0,
                                          role="cadence", tag="solo_final"))
            elif u == climax_u:
                used = {i.lick.name for i in items if i.lick is not None}
                hot = next((l for l in energetic if l.energy >= 0.85 and l.name not in used),
                           next((l for l in energetic if l.name not in used), energetic[0]))
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
                dev = C.transpose(self.dna.hook, u)
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
    def _realize_plan(self, plan: List[PlanItem], ctx: LeadContext, chords: ChordMap,
                      rng: random.Random) -> List[Note]:
        lo, hi = ctx.register
        solo = _normalize_type(ctx.section_type) == "solo"
        if solo:
            hi = _solo_top(lo, hi)
        notes: List[Note] = []
        prev: Optional[int] = None
        climax_at = min((i.start for i in plan if i.tag in ("solo_climax", "solo_peak")),
                        default=None)
        peak_hi = hi
        for it in sorted(plan, key=lambda i: i.start):
            if it.start >= ctx.total_beats - 1e-6:
                continue
            # A soloist saves the top of the neck for the climax.
            hi = peak_hi - 4 if climax_at is not None and it.start < climax_at - 1e-6 else peak_hi
            if it.kind == "lick" and it.lick is not None:
                # Move the hand, not teleport it: a lick starts near where the
                # line already is, pulled toward the plan's register.
                anchor = it.anchor if prev is None else 0.6 * it.anchor + 0.4 * prev
                got = realize_lick(it.lick, it.start, chords, key=ctx.key, mode=ctx.mode,
                                   lo=lo, hi=hi, anchor=int(round(anchor)),
                                   beats_per_bar=ctx.beats_per_bar, time_scale=it.time_scale)
            elif it.kind == "guide":
                got = self._guide_line(it, ctx, chords, lo, hi, prev)
            elif it.cell is not None:
                got = self._realize_cell_item(it, ctx, chords, lo, hi, prev, rng, notes)
            else:
                got = []
            if got:
                notes.extend(got)
                prev = got[-1].pitch
        return notes

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
                                     entry_after_rest=after_rest)
            if not got:
                continue
            score = cost
            if len(options) > 1:
                ic = self.listener.mean_information([n.pitch for n in got], [n.dur for n in got],
                                                    context)
                score += IC_WEIGHT * abs(ic - IC_TARGET.get(it.role, 3.0))
                score += 0.05 * k  # ties favor the plainer development
            if best is None or score < best[0]:
                best = (score, got)
        return best[1] if best else []

    def _guide_line(self, it: PlanItem, ctx, chords: ChordMap, lo, hi, prev) -> List[Note]:
        """A sustained descant: one chord tone per chord, moving by step in a
        planned direction (down across one phrase, up across the next), with
        occasional anticipations and passing tones for forward motion."""
        spans = [sp for sp in chords.spans if it.start - 1e-6 <= sp.start < it.end - 1e-6]
        if not spans:
            return []
        anchor = it.anchor
        cand_lo, cand_hi = max(lo, int(anchor) - 6), min(hi, int(anchor) + 7)
        out: List[Note] = []
        history: List[int] = []
        current = prev if prev is not None else int(round(anchor + 4))
        per_phrase = max(1, int(round(4 * ctx.beats_per_bar / max(0.5, spans[0].end - spans[0].start))))
        for i, span in enumerate(spans):
            phrase_pos = i % per_phrase
            direction = -1 if (i // per_phrase) % 2 == 0 else 1
            if phrase_pos == 0 and history:
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
            start = span.start
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


def _sub_context(ctx: LeadContext, bars: int) -> LeadContext:
    return LeadContext(ctx.section_id, ctx.section_type, ctx.occurrence, ctx.is_final_of_type,
                       bars, ctx.beats_per_bar, bars * ctx.beats_per_bar, ctx.key, ctx.mode,
                       ctx.chord_slots, ctx.intensity, ctx.foreground, ctx.next_section_type,
                       ctx.register)


def _tidy(notes: List[Note], total: float) -> List[Note]:
    """Monophonic cleanup: sort, clip overlaps, drop notes past the end."""
    notes = sorted((n for n in notes if 0 <= n.beat < total - 1e-6), key=lambda n: (n.beat, -n.pitch))
    out: List[Note] = []
    for n in notes:
        if out and abs(out[-1].beat - n.beat) < 1e-6:
            continue
        if out and out[-1].beat + out[-1].dur > n.beat - 0.02:
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
