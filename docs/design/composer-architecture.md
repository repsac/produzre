# Composer architecture

The composer (`produzre/composer/`) turns Produzre from a generator of
plausible bars into something that writes songs. It is deterministic, has no
learned weights beyond one small table of interval statistics, and runs in
milliseconds.

## The diagnosis

Measured against 110 human-composed melodies (film and TV themes) and across
the genre examples, the 0.9 engines failed in one consistent way: **the
randomness and the repetition sat at the wrong levels of the hierarchy.**

| Level | Human music | Produzre 0.9 |
|---|---|---|
| Surface (notes, bars) | Repeats: the riff, the groove, the hook | Random: every bar a fresh draw |
| Structure (phrases, sections) | Develops: cadences, a climax, a lifted last chorus | Static: one chord loop, one template |

Concretely:

- **No memory.** The lead drew a new motif from each section's RNG, so the
  second chorus never repeated the first. Measured over the lead: 0% of
  two-bar windows repeated an earlier window (human median 29%).
- **Grooves were textures.** The most common bar pattern covered 20-30% of a
  section's bass and drum bars (a real groove holds 75% or more).
- **No climax.** The lead touched its highest pitch in 45% of its two-bar
  windows (human 10%): every phrase peaked, so none did.
- **Constant surprise.** The lead's self-information was 4.4 bits per note
  (human 2.7): uniformly unpredictable, which a listener hears as aimless.
- **Harmony without arrival.** Preset progressions looped into the next
  section; nothing set up a return home.

`tools/musicality.py` measures all of this; see [Measuring](#measuring).

## The approach: form first, surface derived

Human composers decide structure deliberately and derive the surface from a
few ideas. The composer does the same, in four parts.

```
            harmony plans (all sections)
                        │
                        ▼
   ┌────────── Song DNA (dna.py) ──────────┐
   │ hook, answer, verse idea, bridge idea, │   chosen once per song by a
   │ signature lick bank                    │   memorability search over the
   └───────────────────┬────────────────────┘   real chorus/verse chords
                       │
        per section    ▼
   phrase grammar (lead.py) ── plan items ──► realizer (realize.py)
        │   ▲                                    beam search over pitches
        │   └── memory: returning sections recall their plan / notes
        ▼
   Listener (listener.py): picks among candidate developments so each
   phrase's surprise matches its role (establish, develop, climax, cadence)
        │
        ▼
   composer.lead.<section> ──► lead engine performs it (bends, vibrato, dives)

   rhythm section ──► groove memory (groove_memory.py): bar form + recall
   harmony plans ──► cadential phrasing (harmony/phrasing.py): turnarounds
```

### 1. Song DNA

`compose_dna` builds a song's ideas once: a one-bar **hook**, its **answer**
(the hook line's second bar), a **verse idea** with a contrasting rhythm, a
**bridge idea** (inverted and slowed), and a bank of three **signature
licks**.

Ideas are chosen by generate-and-score. A few hundred candidates come from an
idiomatic rhythm vocabulary (16-step patterns with anticipations, dotted
pushes, pickups, and breaths) and a constrained contour walk. Each is scored for
memorability using findings on catchy melodies (Jakubowski et al. 2017;
Huron 2006; Meyer's gap-fill principle):

- a distinctive rhythm: syncopation, internal rhythmic repetition, a held or
  breathing ending, 4-7 notes;
- one signature leap, answered by contrary stepwise motion;
- an arch-like contour with an interior peak and 3-5 distinct pitches;
- a moderate surprise level under the human interval prior (not generic, not
  bizarre).

The best candidates are then **realized over the song's actual chorus (or
verse) chords and re-scored on the pitches a listener would hear**. An idea
whose signature leap the harmony would flatten loses to one that survives.
The seed only chooses among the top few.

An authored melody theme always seeds the hook. An auto-generated one is
replaced by the composer's hook in the theme bank, so the acoustic guitar,
arpeggiator, and lead all share one melodic identity.

### 2. Phrase grammar and memory

`SongComposer.compose_lead` builds an abstract plan for each section:
which idea, which development, where, how high, and which cadence. It then
realizes the plan over that section's harmony.

| Section | Instrumental (`foreground: full`) | Band with singer (`foreground: auto`) |
|---|---|---|
| Intro | Hook line stated, ending open | The guitar hook |
| Verse | Period on the verse idea: open half cadence, closed full cadence | Signature-lick fills at phrase ends, space elsewhere |
| Prechorus | Sequence climbing to a held dominant | Same |
| Chorus | Hook lines A A' B A'': state, answer open, lift to the summit, close | A directed descant (guide tones moving by step), hook as a tag |
| Bridge | Contrasting idea, sequenced, half cadence | Statement, then fills |
| Solo | A story: hook quote, development up the neck, a climax lick and bend, a resolving phrase, a final dive | Same |
| Outro | Hook, then liquidation to a held tonic | Same |

Returning sections use **memory**. The plan for a section type is stored at
its first occurrence. When the chords match, a later occurrence plays exactly
the same notes, so the listener learns the hook. Recall makes three
deliberate changes:

- the **final chorus** lifts the register and ornaments its answers;
- a **second verse** keeps the melody with small rhythm changes, like a new
  lyric;
- the **solo** is never recalled.

### 3. The listener

`Listener` is a deterministic model of melodic expectation. It is a
variable-order (1-3) Markov model over interval and duration tokens with
two sources:

- a **long-term prior**: interval statistics aggregated from human
  melodies (`resources/composer/melodic_prior.json`, counts only);
- a **short-term memory** trained on everything the song has already played.

A motif that has been heard therefore becomes predictable, exactly as it does
for a person.

Where a phrase can be developed several ways (plain restatement, new ending,
rhythmic variation, ornament), each candidate is realized and scored by how
far its information content falls from its role's target. The targets were
calibrated by running the same listener over 3,520 two-bar phrases of human
melodies:

| Role | Target (bits/note) | Human percentile |
|---|---|---|
| cadence | 2.0 | P20 |
| establish | 2.5 | P30 |
| develop | 4.0 | P55 |
| climax | 5.3 | P80 |

This is the part that is new: procedural generators choose notes by rule or
by chance, and learned models absorb expectation statistics implicitly. Here
the composer consults an explicit, self-updating model of *the listener's*
expectations, trained on the song as it unfolds, and spends surprise where
the form calls for it.

### 4. Realization

`realize_cell` fits a cell's rhythm and diatonic contour to the harmony with a
small beam search (width 14). The contour is relative to the note actually
played, so a motif's intervals survive a harmonic adjustment upstream. The
costs:

| Term | Intent |
|---|---|
| Contour deviation, direction flips, frozen steps | Keep the motif recognizable. |
| Non-chord tones weighted by metric strength and duration | Chord tones on strong beats and long notes. |
| Unprepared dissonance (leap into, or entry after silence) | Dissonances approached by step. |
| Minor ninth against a chord tone on a strong beat | Avoid clashes. |
| Leaps over a fifth, over an octave, unrecovered leaps | Singable lines. |
| Distance from the register target | Register plans (verse low, chorus high, solo climbing). |
| Cadence pitch class | Phrase endings land where the form says. |

Cadences re-aim at the nearest chord-tone degree when the chord forbids the
planned degree, instead of fighting the harmony. Licks are placed on the
pentatonic (or diatonic) ladder with their center of pitch at the register
target, and they move by octaves as a whole to fit.

## Rhythm guitar: composed comping

Measured over 94 songs, rhythm guitar played plain quarter notes or a
whole-note sustain in a quarter of all sections. Many full arrangements used
one or two patterns for every section. A genre recipe pinned one style (one
hard-coded cell) for the whole song, and genres without a recipe fell back to
quarter-note strums.

`composer/comping.py` writes the part the way a player with a voice would. A
rhythm part with character mixes techniques inside one figure: dead-note
chucks between chords, single-note bass-string walks into the next chord,
sus4 hammer-ons inside a held chord, chords slid in from a fret below, boogie
dyads, partial-chord stabs, and palm-muted gallops.

- **Vocabulary.** 57 idiomatic riffs across rock, metal, pop, funk,
  reggae and ska, soul and gospel, country and folk, latin, electronic, and
  shuffle/swing (12-step). They are written as readable step strings (`X-mxX-mx`,
  `r-m-X---f-m-X---`, `q-Qq-Qq-yq-Q`) and tagged by energy tier (verse-low,
  build, chorus-drive, contrast, stab).
- **Comp DNA.** Each song draws one riff per tier, weighted by character
  (distinct techniques plus off-beat accents). It then gives each riff a seeded,
  idiom-preserving personal variation: a strum ghosted into a chuck, a hit
  pushed an eighth early, a sus or slide injected, a bass walk into a
  change, or accents and gaps moved in a chug riff. The downbeat never
  changes. Two songs in one genre start from shared vocabulary but play
  different figures.
- **Arrangement.** Verse, prechorus, chorus, bridge, solo, breakdown, and outro
  take contrasting tiers. Phrase ends walk up into the next phrase, the bar
  before a chorus is stop-time (one hit, silence, a chuck-and-upstroke
  pickup), the song ends on a slid or ringing chord, the final chorus kicks
  into the alternate driving figure, and chorus strums that coincide with the
  hook's attacks get the accent.
- **Performance.** `engine/rhythm_gtr/composed.py` plays each gesture on the
  engine's playable chord shapes: strum spread by direction, partial
  upstrokes, 60 ms dead-note chucks, chugs and boogies on the low strings,
  a sus4 that pulls off to the third while the other strings ring, and slides
  written as pitch bend.

Explicit user choices win, in three tiers. Settings that choose a different
part (`style`, `strum_style`, `sustain_mode`, `playstyle`, `pattern`,
`play_pattern`, `follow_hats`, `use_patterns`, `recipe`, a riff lock, or
`composer: false`) keep the engine's previous behavior. Feel settings
(`density`, `palm_mute`, `chuck_rate`, `voicing`, register bounds, dynamics,
timing) are honored by the composed performer. Legacy-engine tuning with no
composed meaning is reported in the build log as unused. The lead follows
the same rule: `rest_probability` and `contour_style` shape the composed line,
expression rates shape its performance, and only `composer: false` selects the
legacy generator. Composed comping carries its own
bar form, so groove memory skips it.

Across the genre examples, section-main rhythm patterns went from 78 to 111
distinct figures. The most common one dropped from 43 sections (plain
quarters) to 27.

## Meter grouping

Odd meters used to be served by stretching 4/4 material: 7/8 cut a figure
short, 5/4 left a gap, 6/8 was treated like 3/4, and a fixed 4-beat harmonic
rhythm changed chords mid-bar. `theory.meter_groups` now describes each bar
as beat groups (6/8 = 3+3 eighths, 7/8 = 2+2+3, 5/4 = 3+2, 12/8 = four dotted
quarters; `meter_grouping` overrides). Group starts are strong metric
positions, so the realizer, the listener, and the performers accent the
meter's pulse; in grouped meters a dissonance on a group start costs extra,
because that is where the ear finds the meter. Song DNA builds odd-meter
ideas from per-group rhythm cells, comp riffs are sliced group by group, and
the default harmonic rhythm is one chord per bar. Plain 4/4 output is
byte-identical.

Measured on the showcase song rebuilt in each meter (lead and rhythm guitar
attacks on non-downbeat group starts, lead chord tones on strong positions):

| Meter | Lead on group starts | Rhythm on group starts | Strong-beat chord tones |
|---|---|---|---|
| 6/8 | 0.43 to 0.69 | 0.85 to 0.96 | 0.95 to 0.99 |
| 7/8 | 0.44 to 0.55 | 0.74 to 0.96 | 0.96 to 0.92 |
| 5/4 | 0.14 to 0.61 | 0.85 to 0.96 | 0.94 to 0.90 |
| 7/8 funk | 0.52 to 0.78 | (style pinned before) | 0.96 to 0.97 |

The 7/8 and 5/4 chord-tone dips come from the lead now landing on group
starts it used to skip, sometimes with a color tone (a ninth on the "+2" of
5/4). They are the next thing to tune.

## Bass responses (opt-in)

`composer/bass_response.py` gives the bass a conversational role. The lead's
composed notes define its holes: 1.25 to 4 beats without an attack, opening
half a beat after the last one so the held note is heard. One hole per 4-bar
phrase (its last), plus the section's close, gets an answer: the hook's
first few attacks and diatonic contour, from the chord root near the bass's
own register, landing on a chord tone and starting on a nearby kick. The
engine's notes inside the hole step aside; everything else keeps its groove.

| Metric (6 songs, bass `hook_response` off to on) | Off | On |
|---|---|---|
| Bass notes that are answers | 0.00 | 0.14 |
| Bass attacks colliding with a lead attack | 0.213 | 0.200 |
| Bass groove lock (top-pattern share) | 0.698 | 0.682 |
| Bass onsets on a kick | 0.588 | 0.554 |

An answer on every hole (tried first) made 26% of bass notes answers and cut
groove lock to 0.55, so the phrase-end rule is deliberate. It stays opt-in
until a listening comparison settles the balance per genre.

## Album diversity: every song its own band

An album of one genre used to sound like one song played ten times.
`tools/album_diversity.py` writes an album the way a user would (one genre,
varied keys, tempos, modes, progressions, and seeds), builds it, and measures
how alike the songs are: the mean pairwise Jaccard index of each part's most
common bar per section, where tokens are the drum voice, the guitar
technique, and the interval above the bar's lowest note. It also reports
the share of songs making the most common arrangement choice.

Ten hard rock songs, the committed composer against this work:

| Part | Before | After |
|---|---|---|
| Drums, verse / chorus / bridge | 0.91 / 0.70 / 0.94 | 0.31 / 0.24 / 0.22 |
| Bass, verse / chorus / bridge | 0.11 / 0.29 / 0.18 | 0.08 / 0.11 / 0.21 |
| Rhythm guitar, verse / chorus / bridge | 0.10 / 0.14 / 0.24 | 0.08 / 0.08 / 0.13 |
| Lead under the chorus | 0.49 | 0.19 |
| Overall | 0.41 | 0.16 |

The bridge bass stays above its baseline: the benchmark's bridges draw from
three progressions, and held or kick-locked roots over the same chords share
shapes more than the engine's busier lines did.
| Songs with stop-time before the chorus | 10/10 | habit, most common choice 4/10 |
| Songs whose solo ends in a dive | 10/10 | 4/10 |

What does it:

- **Drum DNA** (`composer/drums.py`). Each song's drummer: kick patterns
  from per-beat cells (verse and chorus), a timekeeper per section from ten
  archetypes (closed 8ths, 16ths, quarters, open-hat accents, washy
  half-open hats, ride, ride bell, crash-ride, floor-tom pulse, pedal),
  backbeat, half-time, or stomp, a ghost-note style, a synthesized fill
  vocabulary (descending toms, snare crescendos, around the kit, unison
  hits, triplets, flams), fill and crash policies, and a feel (straight,
  laid back, pushing, shuffle) that reaches the whole band through the
  groove clock. The drum engine performs the hits with its kit and
  humanization and still exports the kick features the bass locks to.
- **Arrangement DNA** (`composer/arrangement.py`). Habits every part agrees
  on: how the band goes into a chorus (stop, build, fill, push, drop), how
  phrases end (walk-up, chord slide, dead-note rake, nothing), whether the
  intro starts with the riff alone, the solo's story (climb, melodic,
  trade, slow blues) and ending (dive, held vibrato, trill, fall-off), the
  lead's role under a singer's chorus (guide tones, octave stabs, rhythmic
  stabs on the hook's attacks, fills), whether the song is riff-driven and
  the bass doubles the riff, the chorus form (lift, anthem, call), how
  often the lead fills, and the ending (ring, cold, big finish).
  `song.arrangement_style` pins any of them.
- **Signature riffs** (`composer/riff.py`). Riff-driven songs play a
  generated figure on the low strings: a root power chord, syncopated
  power-chord moves among pentatonic degrees, palm-muted chugs, and a
  single-note tail, with bar two answering bar one. It moves with the chord
  root; the bass can double it in unison.
- **Synthesized comp riffs.** Most songs' comp figures are built from
  one-beat technique cells (tens of thousands of figures per tier) and
  scored for a few techniques that restate themselves, instead of drawn
  from a fixed list.
- **Bass roles** (`composer/bass.py`). In band sections (drums plus a
  guitar) each song picks a bass role per section: the engine's
  kick-and-chord line, locking to the song's own kick pattern, root
  eighths, pumping octaves, a gallop, or held roots, approaching chord
  changes from below. Each role carries per-song variation (silent
  eighths, an octave pop, the octave mask, gallop beats, held-note
  figures, anticipations): a first version without it made bass lines
  more alike across songs (bridge similarity 0.11 to 0.44), because a
  generic role is identical in every song that picks it. Bass `seed`
  overrides re-roll the roles; explicit `rhythm_pattern`, `walking`,
  `lock_to_kick`, riff or motif locks keep the engine line.
- **Generated licks.** Most of a song's lick bank is synthesized from lick
  shapes (cry, run down, run up into a bend, motif, pedal point, pre-bend)
  with per-song rhythm unit, box position, and length.

Explicit settings still win. Drum `voices`, `recipe`, `pattern`, a riff
lock, a section `intent`, or an authored `drum_groove` theme keep the drum
engine; `ghost_rate`, `fill_rate`, `kick_density`, and `hat_density` shape
the composed drummer; an explicit `swing`, `push_pull`, `timing_jitter_ms`,
or song `humanize_timing` keeps the song's feel out; instrument and section
`seed` overrides re-roll that part's DNA.

## Groove memory

`apply_groove_memory` runs right after each accompaniment engine renders
(drums, bass, rhythm guitar, acoustic), before the shared groove clock:

- **Bar form.** Within each 4-bar phrase, groove bars restate a source bar;
  the phrase's last bar keeps the engine's output (fills, turnarounds,
  pickups). Funk, reggae, Latin, and related genres use two-bar grooves.
- **Typical source.** The source is the phase's medoid, the bar most like the
  others, with ties broken toward idiomatic voicing (bass: root on one,
  fifths welcome).
- **Chord-relative restatement.** A restated pitch follows the root and keeps
  its chord role (a third stays a third). Approach notes aim at the next
  bar's chord.
- **Space is kept.** A bar the engine left empty stays empty; decorations
  (crashes, fills, pickups) are never restated or replaced.
- **Recall.** A section type recalls the groove it established when the part
  is configured the same way, scaled to the new occurrence's dynamics. A
  clear intensity lift (0.08 or more, such as a final chorus) plays its own
  groove instead.
- **Coherence.** Every instrument uses the same source bars, so the kick and
  bass lock negotiated by the engines survives.

Copies are re-humanized only when the engine humanized the source, so
grid-exact parts stay exact. Theme-quoting parts (riff and motif locks) and
soloing parts are left alone.

## Harmony: turnarounds and the final lift

`harmony/phrasing.py` splits a section's last bar when the next section
returns to the tonic and the last chord does not already lead there. The
second half becomes V, V7 for blues, soul, jazz, and country, or bVII for modal
rock. Preset and recipe progressions get turnarounds by default. Explicit
progressions opt in with `song.turnarounds: true` or a section's `harmony:
turnaround: true`.

`song.final_chorus: modulate` (or a semitone count) moves the last chorus and
everything after it up a whole step: the direct "gear change". Every pitched
engine follows through `section.key`, and both memory caches transpose.

## Configuration

| Key | Default | Effect |
|---|---|---|
| `song.composer` | true | Compose the lead from song DNA. `false` restores the 0.9 motif generator. |
| `song.groove_memory` | true | Bar form and recall for drums, bass, rhythm and acoustic guitar. |
| `song.turnarounds` | unset (preset/recipe harmony only) | Force turnarounds on or off for every section. |
| `song.final_chorus` | unset | `modulate` (+2) or a semitone count for a final-chorus key change. |
| `harmony.turnaround` | unset | Per-section turnaround override. |
| `lead_gtr` `composer` | true | Per-section opt-out of the composer. |
| `rhythm_gtr` `composer` | true | Opt out of composed comping (explicit style keys also opt out). |
| `lead_gtr` `foreground` | `auto` | `full`: the lead is the melody (instrumental). `auto`: hooks, fills, counter-lines, and solos around a singer. |
| instrument `groove_memory` | true | Per-instrument opt-out. |
| instrument `groove_cycle_bars` | genre | 1 or 2-bar groove cycle. |

## Plan keys

| Key | Content |
|---|---|
| `composer.song` | The `SongComposer` (DNA, listener, memory). |
| `composer.lead.<section>` | Composed notes: beat, duration, pitch, accent, technique, role. |
| `composer.comp.<section>` | Composed rhythm-guitar gestures (riff name, ring, events). |
| `composer.groove_memory` | Established grooves by instrument and section type. |

## Measuring

```bash
python tools/musicality.py --corpus /path/to/reference/midi     # human baseline
python tools/musicality.py exports/<song>/instruments/lead_gtr/*.mid
python tools/preview_audio.py exports/<song>/<song>.mid -o preview.mp3
```

Controlled comparison over the 16 examples with a lead part (same seeds and
configs, new systems toggled off and on), against the median of 110 human
melodies:

| Metric | Human | 0.9 | Composer |
|---|---|---|---|
| Step ratio | 0.52 | 0.34 | 0.45 |
| Exact phrase repeats | 0.29 | 0.00 | 0.39 |
| Varied repeats | 0.18 | 0.52 | 0.14 |
| Novel phrases | 0.50 | 0.41 | 0.47 |
| Rhythm recurrence | 0.69 | 0.38 | 0.69 |
| Self-information (bits) | 2.65 | 4.43 | 3.40 |
| Peak-pitch share | 0.10 | 0.45 | 0.06 |
| Bass groove lock (top-pattern share) | | 0.29 | 0.77 |
| Drum groove lock | | 0.25 | 0.75 |

Averaged over the lead metrics, the distance from the human profile fell
from 1.11 to 0.29 standard deviations.

## Limits and next steps

- The memorability score is a heuristic. The next step is fitting its
  weights against a labeled set of hooks.
- The composer writes the lead and the rhythm guitar; the bass answers the
  lead only when `hook_response` is on. A full bass line derived from the
  DNA (a counter-riff, not just answers) is still open.
- Harmony changes are limited to turnarounds and the final lift. Reharmonizing
  repeats (substitutions, secondary dominants) needs numeral spelling for
  applied chords.
- The listener now adds metric-weighted harmonic exposure to development
  selection. The contextual weights are heuristic; metric grouping (such as
  6/8 versus 3/4) and learned syncopation expectations remain future work.

## Review extension: contextual listening and ownership

The listener keeps its calibrated interval/duration IC unchanged and adds a
separate `contextual_cost` when selecting generated developments. It integrates
non-chord-tone duration across overlapping chord spans, weighted by metric
position. Short stepwise passing tones receive a discount. This avoids mixing
an uncalibrated harmonic heuristic into the published IC percentiles. Authored
cells are not subjected to variant selection.

DNA fitting uses the chosen chorus or fallback section's key, mode, and bar
length; verse fitting uses its own source context. A guide phrase includes the
chord already sounding at its start. Realization computes metric strength from
section-relative attacks, not cell-relative attacks.

Explicit lead phrase and technique parameters select the legacy engine;
numeric registers are hard bounds even during solos. Explicit rhythm density,
voicing, and performance controls likewise take precedence. Groove memory
identifies a part by top-level settings and canonical nested parameters, with
intensity handled separately. Final timeline cleanup follows transition ramps
so later lengthening cannot undo lead monophony.

The [review report](composer-review.md) records confirmed reproductions,
measurements, musical reading, and remaining risks. Reproduce the listener A/B:

```bash
.venv/bin/python tools/composer_review.py --seeds 24 --lead-sheets
.venv/bin/python -m pytest tests/test_composer_review.py -q
```


## Second review: grouping and bass development

See [the round-two report](composer-review-round2.md) for reproductions, the
216-build comparison, raw lead sheets and blinded listening pairs.

Compound shuffle riffs map each three-step beat onto a dotted quarter. Shared
swing preserves group starts while retaining pocket and jitter. Changed section
meters get deterministic grouped DNA views, with grouping included in recall
keys; authored themes keep their rhythms. Comp hook alignment and bass answers
use the same section view.

Bass `hook_response: develop` rotates head, tail and answer cells and advances
on section-type recurrence. Authored contours use relative semitone offsets,
including accidentals. Fast-note durations and explicit bounds survive the
response pass. The default remains off because greater variety has measurable
groove costs. The engine and groove memory still supply the underlying bass.

Settings merge respects section precedence across fields and nested params.
Explicit lead registers, rhythm timing, octave voicing and gesture bounds now
reach the performers. Part selectors still opt out and legacy-only tuning is
still logged unused. The three existing 4/4 examples are byte-identical to
`8ecd293`; affected explicit settings and response modes intentionally change.

Strong-beat color notes in the inspected 7/8 and 5/4 anthem remain unchanged:
held sevenths and sixths resolve to chord tones by leaps. No contextual weights
were retuned. Short blues sections still use the recipe prefix; automatic form
compression is not implied by the one-chord-per-bar default.
