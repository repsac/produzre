# Design: Song-Level Theme Bank & Rule-Based Melodic Composition

**Status:** Proposal
**Date:** 2026-08-14
**Audience:** Produzre maintainer
**Scope:** `produzre/themes/` (new), `orchestrate/plan.py`, `orchestrate/build.py`, `orchestrate/render.py`, `melody.py`, `config/parse.py`, all engines (consumption only)

---

## 1. Problem Statement

Produzre's output is deterministic but musically generic. Root cause analysis
(see below) shows the problem is **not determinism** — it is the absence of
**global musical structure**:

1. **No memory across phrases or sections.** `make_motif()` in `lead_gtr`
   generates a fresh motif per phrase; the RNG deliberately mixes the
   arrangement index into section streams so repeated sections differ. Nothing
   recurs, so nothing is recognizable.
2. **No real melody.** `melody.py: build_melody_guide` produces a sinusoidal
   contour (`sin(π·position)`) snapped to chord tones — a contour, not a tune.
3. **No user authorship.** Hundreds of steering parameters exist, but a user
   cannot input a riff, melody, or drum pattern.
4. **Probability-assembled content.** Drum grooves and rhythm patterns are
   built step-by-step from per-voice rates, which averages out to statistical
   mush with no phrase-level identity.

Memorable music is a small amount of distinctive material, repeated with
variation. This proposal adds that capability while keeping the engine fully
deterministic.

## 2. Goals / Non-Goals

### Goals

- **G1.** A song has 1–4 named *themes* (riffs, hooks, motifs) with stable
  identity, generated once per song or supplied by the user.
- **G2.** Every engine can *quote* or *develop* themes — repetition with
  variation is the default behavior, not an accident.
- **G3.** Users can author themes in YAML or import them from MIDI clips;
  engines arrange around user material.
- **G4.** The sinusoidal melody guide is replaced by a guide derived from real
  thematic material.
- **G5.** Full determinism preserved: same config + same seeds → identical
  MIDI, bit-for-bit. `--strict-determinism` keeps passing.
- **G6.** Backward compatible: a config with no `themes:` block behaves exactly
  as today (themes auto-generated from the song seed).

### Non-Goals

- Neural/LLM-based generation inside the engine (an optional two-tier
  workflow where an external composer writes `themes:` YAML is enabled by G3
  but is out of scope for the engine itself).
- Audio rendering. Output remains MIDI.
- Changing the RNG hierarchy, export layer, or engine registry mechanics.

## 3. Core Concepts

### 3.1 Theme

A **Theme** is a short musical idea (typically 1–4 bars) stored as
**rhythm + scale degrees**, not absolute pitches. This is the key
representation decision: degrees make the theme transposable across the
harmony plan, so the same idea can be quoted over any chord.

```python
@dataclass
class ThemeEvent:
    offset_beats: float      # position within the theme, from 0.0
    duration_beats: float
    degree: int              # diatonic scale degree, 1-based (1 = tonic)
    accidental: int = 0      # -1 flat, +1 sharp (e.g. b3, #4)
    octave: int = 0          # octave displacement from theme base register
    accent: bool = False
    tie: bool = False

@dataclass
class Theme:
    name: str                # "main_riff", "chorus_hook", ...
    role: ThemeRole          # RIFF | MELODY | BASS_MOTIF | DRUM_GROOVE
    length_beats: float      # normally 1/2/4 bars of the song's main meter
    events: list[ThemeEvent]
    base_register: tuple[int, int]   # preferred MIDI range for realization
    tags: set[str]           # {"user", "generated", "imported", ...}
```

Why scale degrees of the **key** (not the chord): key-relative degrees keep
the theme melodically stable across chord changes, which is how riffs
actually behave. Realization (§5.4) snaps to chord tones where the harmony
demands it, so vertical correctness is preserved without giving up melodic
identity.

### 3.2 Theme Bank

```python
@dataclass
class ThemeBank:
    themes: dict[str, Theme]             # by name
    by_role: dict[ThemeRole, list[str]]  # role → theme names, priority order
    seed_material_hash: str              # provenance / debug
```

The bank is built **once per song** in `plan_song`, before any section
planning, and published to the plan under a new top-level key:

```
themes.bank          → ThemeBank
themes.plan.<sec_id> → ThemeTreatment per section (§5.5)
```

### 3.3 Transformations

All development is expressed as deterministic, pure functions on Themes
(`themes/transform.py`). Each takes an RNG only for *choosing* which
transform to apply — the transforms themselves are exact.

| Transform | Effect | Typical use |
|---|---|---|
| `quote` | Exact restatement, transposed to current harmony | Chorus hook |
| `sequence` | Repeat shifted by N scale steps | Verse development |
| `invert` | Mirror intervals around first degree | Bridge contrast |
| `fragment` | Keep first/last N events only | Intro tease, outro |
| `displace` | Rotate rhythm by k grid steps | Re-grooving a riff |
| `augment` / `diminish` | Scale durations ×2 / ×0.5 | Climax, tension |
| `ornament` | Add approach/passing tones per rules | Solo development |
| `thin` | Remove weak-beat events | Breakdown texture |
| `octave_shift` | ±12 | Final-chorus lift |

### 3.4 Theme Treatment (per section)

`ThemeTreatment` is the arrangement decision for one section: which themes
appear, with which transform, in which register, at which density.

```python
@dataclass
class ThemeTreatment:
    theme_name: str
    transform: str           # key into transform registry
    transform_params: dict
    target_engines: list[str]  # who quotes it here
    density: float           # 0..1, how fully it is stated
```

## 4. Where It Hooks In

### 4.1 New RNG tier (song-material stream)

Current hierarchy: project → song → take → section → instrument → voice →
event.

Add a **song-material** stream derived from the *song* seed (pre-take):

```
derive_rng(song_seed, "themes")      # one stream for the whole bank
```

Design decision: themes derive from the **song seed, not the take seed**.
Consequence: the `variation` knob regenerates arrangement and development
but preserves thematic identity — a take is a new *performance of the same
song*, not a new song. A config flag `themes.vary_per_take: true` opts into
per-take themes for users who want the slot machine.

Implementation note: the bank must be built before any engine RNG streams
are consumed, and theme transforms must each draw from their own derived
sub-stream (`derive_rng(material_rng, theme_name, transform_index)`) so that
adding/removing a theme never perturbs unrelated streams — same discipline
as the existing `_produzre_seed` stashing.

### 4.2 `plan_song` integration

New step in `orchestrate/plan.py`, after harmony-relevant parsing and before
section intensity resolution:

```
bank = themes.build_theme_bank(raw_config, song_seed, harmony_context)
plan["themes.bank"] = bank
```

Then, per section, after ensemble roles are assigned:

```
plan[f"themes.plan.{sec_id}"] = arc.assign_treatments(section, bank, roles, rng)
```

### 4.3 Melody guide replacement

`melody.py` keeps its public API (`build_melody_guide`, `guide_pitch_at`,
`fit_pitch_to_range`) so no engine breaks, but the guide is now built from
the section's `ThemeTreatment` instead of a sine arc:

- Strong-beat targets come from the realized theme events.
- Weak-beat targets interpolate per the composition rules in §6.
- Cadence targets keep the existing "roots at cadences" behavior.

Engines that already consume `melody.guide` (lead_gtr phrase anchors,
acoustic_gtr `melody_amount`, arpeggiator apex notes) automatically inherit
themed melodies with **zero engine changes**.

### 4.4 Engine consumption beyond the guide

| Engine | Change | Behavior |
|---|---|---|
| `lead_gtr` | Moderate | `make_motif` consults `themes.plan.<sec>` first; phrase motifs quote/transform themes instead of sampling genre libraries. Solo sections chain transforms (ornament → sequence → octave_shift) as development. |
| `bass` | Small | When a `RIFF` theme is active, bass rhythm locks to the riff's attack pattern (existing `lock_to_kicks` machinery, new target); on chorus, bass plays the `BASS_MOTIF` verbatim. |
| `rhythm_gtr` | Small | Strum accent map biased to coincide with riff attacks (extends the existing Rule 4 accent boost); `thin` treatment during breakdowns. |
| `drums` | Small | Kick/snare accents double riff attacks at rate `riff_accent_rate` (default 0.5); fills still owned by phrase boundaries, now also at theme phrase ends. `DRUM_GROOVE` themes can supply multi-bar patterns wholesale (see §7). |
| `acoustic_gtr` | None–small | Already shaped by the guide via `melody_amount`; optionally states `MELODY` themes in intros. |
| `arpeggiator` | None | Apex follows the guide; inherits themes for free. |

## 5. Realization: Degrees → Pitches

`themes/realize.py` converts a (possibly transformed) Theme into concrete
pitches for a given chord slot from `harmony.plan.<sec>.chord_slots`:

1. Map `degree + accidental` to a pitch class in the section's key/mode
   (reuse `melody._KEY_PCS` / `_MODE_OFFSETS`; factor these into a shared
   `pitch_utils` to end the duplication between `melody.py` and
   `engine/harmony`).
2. **Chord-tone snapping with memory:** if the degree is a half-step from a
   chord tone and the previous realized note was consonant, snap to the
   chord tone; if it is a genuine color tone (b3 over major in blues, b5),
   keep it — genre rules decide, reusing the existing color-tone tables.
3. Fit into `base_register` via `fit_pitch_to_range`, with voice leading:
   prefer the octave placement nearest the previous realized note.
4. Chord changes mid-theme: each event is realized against the chord slot
   active at its offset, so a riff "tracks" the harmony the way a real
   player would fake it.

Determinism note: realization is a pure function of (theme, harmony plan,
key) — no RNG involved.

## 6. Rule-Based Theme Generation

When the user provides no themes, `themes/compose.py` generates them from
the song seed. The rules matter more than the randomness:

1. **Rhythm first.** Pick a 4–8 event rhythmic cell from a curated library
   (syncopated, driving, sparse, triplet) weighted by genre — a distinctive
   rhythm with plain pitches is a hook; the reverse is noodling.
2. **Pitch skeleton.** Start and end on tonic/chord tones; interior notes
   chosen by: consonant on strong beats, passing/neighbor tones on weak
   beats, any leap > 3 steps followed by contrary stepwise motion.
3. **Question/answer.** A 4-bar theme is two 2-bar phrases; phrase 2 repeats
   phrase 1's rhythm with a different cadence (half vs. full).
4. **Cadence formulas.** Themes end on degree 1 (full), 2 or 5 (half), or
   b7 (blues turnaround), genre-weighted.
5. **Register by role:** RIFF → low-mid (guitar/bass range), MELODY → mid,
   BASS_MOTIF → bass register.

These rules are all deterministic given the stream; the RNG only *selects*
among valid options.

## 7. Drum Grooves as Themes

The same mechanism fixes generic drums. A `DRUM_GROOVE` theme is a 2–4 bar
multi-voice pattern (kick/snare/hat events with micro-timing deltas from
mined real performances via `tools/groove_extract.py`) stored as a theme
with per-voice events instead of degrees:

- Verse/chorus default to quoting the groove verbatim (with the existing
  humanize layer on top — micro-timing, not content).
- `displace`/`thin` transforms give variation without dissolving identity.
- Existing recipe rate-tables remain as the fallback when no groove theme
  matches, so nothing regresses.

This reframes the 51 mined drum recipes from *rate tables* back into
*phrases*, which is what they were extracted from in the first place.

## 8. User-Authored Themes (Config Schema)

```yaml
# Top-level, sibling to instruments:
themes:
  main_riff:
    role: riff
    register: [40, 64]
    grid: 0.25                    # quantization for shorthand input
    events: "1:.5 1:.25 b3:.25 4:.5 .:.5 b5:.25 4:.25 1:1"
    # degree:dur pairs, "." = rest; sum must equal length

  chorus_hook:
    role: melody
    degrees:  [5, 5, 6, 5, 3, 2, 1]
    rhythm:   [0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 1.5]
    octave: 1

  my_imported_lick:
    role: melody
    source: { midi: riffs/lick.mid, quantize: 0.25, track: 0 }
```

- Validation lives in `config/parse.py` (new `_parse_themes`), with the same
  fuzzy "did you mean" treatment as instrument params.
- MIDI import reuses `tools/midi_parse.py` logic (promoted into
  `themes/io.py`): monophonic extraction, quantization to `grid`, pitch →
  degree conversion against the song key.
- User themes are marked `tags={"user"}`: engines must quote them **more**
  faithfully (transforms restricted to sequence/octave/thin unless
  `allow_development: true`), because user material is intent, not clay.

### Two-tier composition workflow (enabled, not built)

Because themes are plain YAML, anything can write them — including an LLM or
the user iterating in a chat. The engine becomes the deterministic renderer
of a composed plan: stochastic invention upstream, reproducible realization
downstream. No engine support needed beyond this spec.

## 9. Arrangement Arc

`themes/arc.py` assigns treatments per section type (defaults overridable in
config):

| Section type | Default treatment |
|---|---|
| intro | `fragment(main, first_half)` at low density, one engine only |
| verse | RIFF stated by bass/rhythm_gtr; MELODY rests or `thin` |
| prechorus | `thin(drums)` + rising `sequence` of hook fragment |
| chorus | Full `quote` of all themes; drums double riff attacks |
| bridge | `invert` or `displace` of MELODY; RIFF absent |
| solo | Development chain over MELODY (ornament → sequence) |
| breakdown | `thin` + `fragment`; texture only |
| outro | `fragment(main)` restatement, thinning to end |

Repeat statements escalate via the existing macro-dynamics intensity; the
arc multiplies treatment density by section intensity, so the current
energy system composes instead of conflicting.

## 10. Determinism & Compatibility Guarantees

- One new RNG stream at song level; all theme/transform draws derive from it
  via length-prefixed hashing, independent of engine stream consumption.
- Realization is RNG-free.
- `--strict-determinism` double-build comparison unchanged and passing.
- No `themes:` block → auto-generation path, which is itself deterministic;
  golden MIDI for existing examples **will change** (engines now quote
  themes), so golden files are regenerated once with a changelog note.
- New golden tests: (a) same seed → identical bank serialization;
  (b) different seed → different bank; (c) `variation` changes development
  but not theme identity (unless `vary_per_take`).

## 11. Phased Implementation

| Milestone | Deliverable | Engines touched | Risk |
|---|---|---|---|
| **M1: Data model + input** | `themes/{model,io,realize,transform}.py`; YAML parsing + validation; MIDI import; `themes.bank` in plan; textdump inspection of realized themes | None | Low |
| **M2: Themed melody** | Guide built from treatments; lead_gtr quotes/develops themes | lead_gtr, melody.py | Medium |
| **M3: Rhythm-section coupling** | Bass/rhythm_gtr/drums riff-locking; DRUM_GROOVE themes | bass, rhythm_gtr, drums | Medium |
| **M4: Arc + auto-compose** | `arc.py`, `compose.py`, arrangement defaults, config overrides | plan.py | Low |
| **M5: Docs + examples** | Config reference update, themed example songs, ENGINES.md note on `themes.bank` | None | Low |

Each milestone ships behind the same behavior: no `themes:` config →
sensible defaults. M1 alone is user-visible (authored riffs in arrangements).

## 12. Success Criteria

Qualitative: an example song's MIDI, played with GM sounds, has a
recognizable hook by the second chorus.

Measurable proxies (testable in CI):
- **Motif recurrence ratio:** fraction of lead/acoustic notes within sections
  that match a bank theme (transposition-invariant). Target ≥ 0.6 in
  choruses vs. ~0 today.
- **Cross-section identity:** same-theme correlation between verse 1 and
  verse 2 ≥ 0.8 (today: ~0 by construction).
- Determinism suite green; strict double-build hashes equal.

## 13. Open Questions

1. **Key-relative vs. chord-relative degrees** for user input — key-relative
   proposed; is a chord-relative escape hatch (`relative_to: chord`) needed?
2. **Meter changes** mid-song: themes are beat-grids; quote under a new
   meter via re-quantization, or restrict themes to the main meter?
3. **Theme length vs. section length:** loop themes longer than slots, or
   stretch? (Proposal: loop, with cadence guaranteed at phrase ends.)
4. **Persona interaction:** should personas modulate transform *choice*
   (e.g. jazz persona favors ornament/displace)? Proposed: yes, via existing
   persona param merge, no new machinery.
5. **Priority when themes conflict with fills/lead windows:** coordinator
   rules need one new rule — theme statements win accent priority over
   generic accents.
