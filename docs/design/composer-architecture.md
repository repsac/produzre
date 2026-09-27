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
| Chorus | Hook lines A A' B A'': state, answer open, lift to the summit, close | The song's chorus form around the singer (a climbing descant, answers in the singer's holds, or a harmony line), hook as a tag |
| Bridge | Contrasting idea, sequenced, half cadence | Statement, then fills |
| Solo | A story (climb, melodic, trade, blues): every two-bar unit a full phrase, a climax, a resolving phrase and the song's ending | Same |
| Outro | Hook, then liquidation to a held tonic | Same |

Returning sections use **memory**. The plan for a section type is stored at
its first occurrence. When the chords match, a later occurrence plays exactly
the same notes, so the listener learns the hook. Recall makes three
deliberate changes:

- the **final chorus** lifts the register and ornaments its answers (an
  authored line moves up an octave when it fits, or rises with a final key
  change, and is otherwise embellished without new pitches);
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
  written as pitch bend. Shapes are voice-led chord to chord; the section's
  first chord leads from the home position (`voicings.home_voicing`: the
  tonic at its lowest position), so it is not left at whatever octave its
  root falls in (a minor key's bVI used to open a chorus around fret 13).

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
  humanization, scales them by the section's dynamics
  (`section_level`: intensity, energy and the planner's repeat escalation),
  and still exports the kick features the bass locks to. Jazz and dance
  songs get their own players (`JazzKit`, `DanceKit`), and `for_meter` lays
  any drummer out for 6/8 and 12/8.
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
  `lock_to_kick`, riff or motif locks keep the engine line, and so do a
  walking line (the walking persona) and an authored `bass_motif`, which
  the engine plays with its written rhythm and lengths. Composed notes take
  the bass's `articulation_style` (slap thumb and pop, mute, pick) and its
  register (user, else recipe, else persona), as engine notes do.
- **Bass in the arrangement** (`render.py`, `_apply_bass_arrangement_pass`;
  `composer/bass.py`, `device_bar`). Where the composed drummer plays a
  section, the bass plays the song's `into_chorus` device and ending with it,
  whatever line it plays: stop (a hit on one, then rest), drop (out for the
  bar), push (the band's hit on the last eighth), fill (the last beat left
  to the drums), build (root eighths swelling into the chorus), and the cold,
  big or ring ending. The bars are published as the timeline's
  `device_windows`, so the transition pass does not add a turnaround or
  pickup on top of a device (or of a walking line's last bar, which walks
  into the next section itself). A riff-alone intro follows one rule for
  every part (`arrangement.riff_alone_intro`): it needs a rhythm or acoustic
  guitar to play the riff alone, and the composed drums, the bass, the lead,
  the arpeggiator and every other part that is not the riff then wait out
  the same bars; without one, or with drums the user configured, the band
  plays from the top.
- **Walking bass** (`engine/bass/walking.py`). A walk is planned a bar at a
  time, not thinned from a rhythm pattern: every beat sounds (dotted
  quarters in compound meters), each chord starts on its root, the last
  beat steps into the next downbeat (chromatic at `chromatic_rate`, else a
  scale step), and the inner beats connect them with chord tones on strong
  beats and no repeated root. Each bar draws a shape (climb, fall, or spell
  the chord) on the line's own seed stream. Density, rests, drum locks and
  fills do not apply. The walking persona sets `rhythm_pattern: walking`,
  and a recipe cannot replace it.
- **Every bar plays.** The engine line's rhythm is drawn on a stream keyed
  by section type, so a returning chorus keeps its line, and a bar the
  density and rest draws would empty keeps its first eligible note. Kick
  locks draw per hit, so a drummer's extra kick never reshuffles the rest
  of the line.
- **Generated licks.** Most of a song's lick bank is synthesized from lick
  shapes (cry, run down, run up into a bend, motif, pedal point, pre-bend)
  with per-song rhythm unit, box position, and length.

Explicit settings still win. Drum `voices`, `recipe`, `pattern`, a riff
lock, a section `intent`, or an authored `drum_groove` theme keep the drum
engine; `ghost_rate`, `fill_rate`, `kick_density`, and `hat_density` shape
the composed drummer; an explicit `swing`, `push_pull`, `timing_jitter_ms`,
or song `humanize_timing` keeps the song's feel out; instrument and section
`seed` overrides re-roll that part's DNA.

## Rhythm review: restraint and correctness

The rhythm audit found that repeated figures already dominate sections;
the main excess was a single-note tail in every signature-riff bar, some
figures with a slide every bar, and riff accents a sixteenth off the
drummer's kick and snare. Restraint is a per-song habit,
`ArrangementDNA.comp_activity`, drawn on its own seed stream (so the other
habits are unchanged) and pinned by `song.arrangement_style`. `busy` plays
the full figure. `normal` alternates a full signature statement and a
body-only bar; the render prepass publishes the open tails as `answers`,
and a doubling bass plays them alone. `sparse` keeps three body bars before
a tail, spaces added fills eight bars apart, and limits slides outside
bridge figures. Transition and ending devices retain priority. Sparse
slides settle into a seeded plain chord gesture, preserving differences
between players.

Signature candidates are scored against the song's drum DNA (verse kick
string and backbeat, `_riff_pocket` in render.py) in every mode, so every
riff section of a song plays the same riff. Kick or snare unisons score
up, a syncopated accent the kick doubles scores more, and an accent within
a sixteenth of the backbeat is excluded whenever a candidate avoids it.
After the lead is composed, `yield_to_lead` chokes riff power moves that
would sustain a semitone, tritone, or major seventh against a held lead
note; the attack stays, so the riff keeps its rhythm and shape.

An explicit drum pattern remains owned by its engine, and a song whose
drums the user wrote gets no pocket bias. Signature recall keys include
meter, grouping, part seed and pocket; grouped riffs attack each group and
keep their tails inside it. Bar-two answers cannot overlap the body.

Performed riff pitches no longer overwrite the velocity baseline. Drum
humanization, like the shared groove clock, preserves group starts.
Bass ownership is checked before doubling; explicit line controls and
registers win, and non-riff transition bars retain their bass. Scale
approaches use a real scale neighbor on the side of the incoming root
closest to the previous root; chromatic-below approaches retain their
existing behavior.

See [the review](rhythm-guitar-review.md), its rendered bar sheets and
metrics for the musical findings and limits of the pocket measurements.

## Groove memory

`apply_groove_memory` runs right after each accompaniment engine renders
(drums, bass, rhythm guitar, acoustic), before the shared groove clock:

- **Bar form.** Within each 4-bar phrase, groove bars restate a source bar;
  the phrase's last bar keeps the engine's output (fills, turnarounds,
  pickups). Funk, reggae, Latin, and related genres use two-bar grooves.
- **Typical source.** The source is the phase's medoid, the bar most like the
  others, with ties broken toward idiomatic voicing (bass: root on one,
  fifths welcome after it). A restated bass bar starts on the root; a fifth
  or third on one in the source was that bar's variation, and only a fifth
  drop the engine drew for the restated bar itself (`fifth_jump_rate`)
  keeps its fifth. Restated bass pitches stay inside the bass register.
- **Chord-relative restatement.** A restated pitch follows the root and keeps
  its chord role (a third stays a third). Approach notes aim at the chord
  they resolve into (the next change inside the bar, else the next bar's).
  A chromatic approach (tagged so, or outside the key) keeps its semitone
  distance to the new root instead of snapping onto the scale, and then
  sits in the octave beside the note that chord is played on; a bass line
  whose next bar opens elsewhere (a kept fifth drop) resolves to that root.
  Unpitched gestures (acoustic `body_tap`) keep their fixed pitch, key
  shifts included.
- **Space is kept.** A bar the engine left empty stays empty; decorations
  (crashes, fills, pickups) are never restated or replaced.
- **Recall.** A section type recalls the groove it established when the part
  is configured the same way, scaled to the new occurrence's dynamics. A
  clear intensity lift (0.08 or more, such as a final chorus) plays its own
  groove instead.
- **Coherence.** Every instrument uses the same source bars, so the kick and
  bass lock negotiated by the engines survives.

Copies are re-humanized only when the engine humanized the source, so
grid-exact parts stay exact. Theme-quoting parts (riff and motif locks),
walking bass lines (through-composed: every bar walks to the next chord)
and soloing parts are left alone.

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
| `composer.drums.<section>` | Composed drum hits (beat, voice, velocity scale, kind). |
| `composer.drum_dna.<section>` | The effective drummer for the section (after feel knobs, laid out for its meter). |
| `composer.drums_feel.<section>` | The drummer's feel for the groove clock (swing, sixteenth swing, push/pull). |
| `composer.drums_handoff.<section>` | Set when an `intent` hands a composed song's section to the drum engine. |

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

## Solo and genre breadth review

See [the breadth review](composer-breadth-review.md) for the three-revision
comparison, six genre albums, solo and meter probes, audio pairs, and
remaining diversity tradeoffs.

A lone enabled lead defaults to full foreground unless the user explicitly
chooses another role. Solo drums keep their foot pulse and backbeat while a
four-bar dynamic pattern develops the groove; bars 2 and 4 of each phrase
answer on the toms on their last beat (or with the song's fill there). An unpinned solo
fingerpicking part uses `composer/acoustic.py`: seeded two-bar treble and
thumb figures, chord-tone melody, root/fifth bass, chorus pinches, phrase
answers and a final hold. Explicit picking patterns, other techniques,
authored melodies and composer opt-outs retain their engines.

Country uses root/fifth bass and comping, train/backbeat drum choices and
short fills. Reggae has one-drop kick/rim placement with varied hand
figures. Jazz has a swing drummer (see the drum review below): a continuous
ride with skip notes, the hi-hat foot, feathered kicks and quiet comping. These genres no longer randomly request rock signature riffs;
explicit arrangement overrides still apply. Reggae and jazz retain their
bass engines instead of receiving generic pumping roles.

Effective drum DNA is published after overrides for riff/bass pocket
selection. Shared swing resets per bar, matching drums in odd meters.
Triplet fills use thirds of a beat. Sparse bass approaches must occur
within a quarter note of a chord change, preserving walking approaches
without sustaining passing tones as long pedals.

## Country players

`composer/country.py` draws a shared sub-style on its own seed stream:
`honky_tonk`, `bakersfield`, `outlaw`, `two_step`, `ballad`, or `country_rock`.
`song.arrangement_style.country_style` pins it. The choice reaches lead DNA
before its lick bank is composed, as well as bass, comp and drum DNA.
Each player then draws a personal figure on a separate stream. Part seed
changes retain the band's selected style. Existing part selectors and
performance settings keep their precedence.

A genre name that already says which country it is chooses the style:
`outlaw_country` is outlaw, `country_rock` or `southern country` is country
rock, `honky_tonk`, `bakersfield`, `texas`/`two_step` and `ballad` likewise.
A pinned `country_style` still wins; plain `country` draws one. Bare
country aliases are normalized in `genres.py` at configuration loading,
including instrument overrides. Bare `rock` and `ballad` stay unchanged;
style hints match complete words only within country names.

Country waltzes (3/4 with three one-beat groups, not 6/8) get a
`WaltzPlayer`, with independent `composer.country.waltz.bass`, `.comp`
and `.drums` streams. Bass, comp and drum DNA share the resolved player. The bass always owns beat 1; the player
chooses how long it rings, whether a held chord moves to its fifth (every
other bar, only on a held chord, or never), and whether it walks across
2 and 3 into a chord change (every change, every other, or phrase ends;
diatonic or chromatic). The guitar answers on 2 and 3 with the song's
figure (pah-pah, choked, pah with upstrokes, sixths, arpeggios, or a
ringing ballad strum), and the chorus figure differs from the verse.
The drummer keeps the kick on 1 (sometimes a pickup on the "and" of 3),
plays snare or cross-stick on 2 and 3 or a lighter touch on one of them,
adds an optional foot hi-hat, and draws a timekeeper figure; ghost notes
stay out of the waltz. The hand can use hat, ride, pedal-hat chicks or a
soft ballad floor pulse, with chorus opening or bell accents. Short
one/two-beat eighth-note fills keep the three-beat phrase. Non-chord
bass walk notes release quickly, and composed guitar notes release at
harmony changes. Other meters produce identical output.

Country lead cleanup permits explicitly marked, unbent double stops.
Single-note bends remain channel-wide; independent string bends are not
supported. Already-staccato country picks retain their gate length when
swung, then undergo the normal phrase and section boundary clipping.
See [the country review](country-review.md) for measurements, listening
pairs, configuration examples and limitations.

## Drum review: dynamics, meters and idioms

The examples pass (2026-09-26) found the composed drummer flat, wrong in
compound meters, unidiomatic in jazz and missing for dance music.

- **Dynamics.** Composed velocities were `base * hit scale`, so a verse at
  intensity 0.4 and a chorus at 1.0 played alike and repeats never grew.
  The engine now multiplies by `section_level(intensity, energy)`: 1.0 for
  a default verse, about 1.24 for a default chorus, rising with the
  planner's +0.05 per repeat. Instrument intensity outranks the section's.
  A section handed to the engine by `intent` gets the same level; the
  engine's templates sit about 15% above the composed touch at the same
  base velocity (kick and snare means over genres and seeds), which the
  handoff removes.
- **Compound meters.** `_snare_steps` put the 12/8 backbeat on every pulse
  after the first and the kick cells, hand offsets and accents were
  quarter-based. `for_meter` lays the DNA out on the dotted-quarter pulse
  (its own seed stream): backbeat on pulses 2 and 4 (half time on 3),
  eighth-grid kick cells, pulse cells for idiom hands and trains, open hats
  on the pulse's last eighth, fills of whole pulses. Recipe, persona and
  drummer swing are zero in compound meters (the engine path too); explicit
  swing still applies. Drum-only sections take their grouping from the
  meter rather than the harmony plan.
- **Feel precedence.** The drummer's feel is published for every feel, so a
  straight drummer keeps recipe swing (punk_triplet's 0.35) out of the band.
  Explicit drum swing, the groove block and song `humanize_timing` still win.
- **Jazz.** `JazzKit` replaces random per-beat cells: ride on every beat plus
  skip notes (per-section figures: spang, skips every beat, a late skip, an
  alternating skip on 3), the hi-hat foot (2 and 4; in 3/4 on 2, 3 or both),
  a feathered kick on every beat with per-song bombs, comping at 0.34 to
  0.5 of base on per-song spots and density, softer triplet fills. Every
  seed keeps time: each beat of every groove bar has a ride (or closed-hat
  stick) stroke.
- **Dance.** `DanceKit` (dance, electronic, techno, house, disco, EDM
  genres, matched on words): kick on every beat, offbeat hat figures per
  section, clap/snare/both on 2 and 4, a percussion layer, intro entries by
  halves, kickless or half-time breakdowns, self-building prechoruses,
  roll or kick-drop phrase ends, a pickup kick, and some songs with swung
  sixteenths.
- **Build.** The big fill spanned the bar, so the snare eighths never
  sounded. A build is now its own device: one or two bars (per song) of
  snare rising from eighths to sixteenths, the groove's backbeat giving way,
  the kick on every beat under the sixteenths, no fill.
- **Bridge start.** The transition thinned every other non-downbeat event
  (crash on the half beat, the beat-2 snare) and assumed 4 beats. It now
  uses the bridge's meter, leaves composed drums alone, and thins only hand
  timekeeping of engine drums.
- **Solo drums.** Half of each phrase's backbeats became tom answers. The
  backbeat now stays; bars 2 and 4 answer on their last beat.
- **Feel knobs.** `hat_density` and `kick_density` apply to every section
  type, idiom hand patterns, jazz and dance players and the country waltz.
- **Ride bell.** Groove memory restated groove bars from a source bar, so
  occasional `ride_bell` accents vanished; bell kinds are now protected
  decorations.

## Drum and transition follow-ups (2026-09-26)

Found after the drum review, in the examples' exports:

- **Ramps and the drummer's own transitions.** The transition `ramp_down`
  thinned every other non-downbeat note of the tail with 4 beats per bar
  from beat 0, so composed fills and builds lost half their hits (a 6/8
  build kept 7 of 12 snares), and a pushing persona (`push_pull`) moved
  downbeats off the grid and the next section's first hits into the tail,
  so personas played different hits. `plan_drum_section(windows=...)`
  reports the spans the drummer arranged itself (fills, build bars,
  stop/drop/push bars, the ending); the render publishes them as
  `composer.drums_windows.<section>` and the drum engine registers them in
  `InstrumentTimeline.device_windows`, as the bass does for its device
  bars. Every recipe that edits the tail skips a tail with a device window
  (the bridge start checks its head). Ramps use the outgoing section's
  meter with its bar lines as origin, take tail events by the step they sit
  on (0.06 beats either side), and thin only drum hands.
- **Drum pickups.** `choose_pickup_pitch` gave drums the first head note
  minus a step (MIDI 34 or 35). Drums now get a snare on the last sixteenth
  in the kit's own snare pitch, skipped where the composed drummer ends the
  section or the bar already has a fill, pickup or snare there.
- **Drop intent.** Its "no open hats" applied only when neither the user nor
  the recipe set an open-hat rate, so genre recipes kept theirs. Only the
  user's own `voices.hats` rate now outranks a drop or stomp.
- **One hit per voice per step.** Entry and ending kicks on the groove's
  downbeat kick, two-bar answer kicks on kicks, and an accent crash played on
  the ride (`accent_voice: ride`) over the ride stroke doubled notes.
  `one_hit_per_voice` keeps the stronger hit (an accent merged into a stroke
  keeps the accent's role and ring); the engine does the same per pitch
  within 0.02 beats (a pickup's hand jitter; a flam grace is 0.06 early and
  stays).
- **Solo answers.** Tom answers were layered over build bars. Bars holding a
  fill, build or device play as arranged.
- **Groove memory and intent.** A section's groove was recalled by section
  type, so a half-time bridge replayed the preceding drop bridge. The
  recall key includes the section's intent.

## Lead and arpeggiator review (2026-09-26)

The examples rewrite found seven lead and arpeggiator problems. What changed:

- **Register.** `register` may be a direct field or a param, a preset name
  in any case or a `[low, high]` range in either order, on the composed and
  legacy paths alike (a list at instrument level used to crash the legacy
  lead). `engine/lead_gtr/register.py` owns the parsing.
- **Chorus forms under a singer.** `chorus_form` used to shape only
  `foreground: full`. Under `auto`: `lift` climbs a counter-line line by line
  to a summit before the tag, `call` leaves each two-bar vocal line alone and
  answers it with a signature lick in the singer's held note or breath
  (`_singer_hole`), and `anthem` harmonizes the chorus melody in thirds and
  sixths, moving with the singer. The singer's line is the section's realized
  melody theme (`themes.realized.<section>`), passed as `LeadContext.melody`;
  without one the composer harmonizes its own hook lines. A pinned `counter`
  with a drawn form keeps the plain counter-line.
- **Bends.** `bend_rate` above 0.15 adds bends to untagged composed notes of
  half a beat or longer, on a per-note stream, reaching every such note at 1.
- **Lead seeds.** An instrument or section `seed` on the lead now reaches the
  composer (`LeadContext.seed`): `SongComposer.part_dna` keeps the song's
  hook and answer, the song-level melody the band shares, and draws the
  verse idea, bridge idea and lick bank from the seed; phrase choices use it
  too. Before, the seed changed only humanization.
- **Authored final chorus.** Authored degrees fixed the octave through the
  previous note, so the anchor lift never moved them. `_lift_authored` moves
  the whole line: an octave when it fits, the key change when the final
  chorus modulates, otherwise embellishment only (logged).
- **Solos.** The blues and trade stories played one lick per two bars, and
  the blues story ignored the song's bank. Blues now calls and answers in
  every unit (AAB across four-bar lines, the song's licks first), and trade
  fills the lead's bar and plays a pickup from the band's bar. Later solos
  rotate through the bank, a solo after a solo continues it, and a solo
  before a solo hands over on the dominant. Fills and answers that must fit
  a hole play at their own speed or in double time on the sixteenth grid,
  trimmed from the front if needed (`_place_lick`).
- **Country fills with the lead as melody.** A country song's full-foreground
  verses and choruses answer their own phrases with the song's licks at the
  `lead_fills` rate (the phrase's last bar keeps its first half); other
  genres do so only when `lead_fills` is pinned.
- **Arpeggiator.** The melody guide now shapes only `phrase` and
  `cinematic`; the apex is the top of each cycle (it was the last note, the
  wrong note for `up_down` and `down`); chords spell sevenths and extensions
  (6, 9, 11, 13 and alterations); velocity spans about 30 to 100 with
  intensity, plus bass and metric accents.

## Guitar, export and groove-memory review (2026-09-26, second round)

Found after the examples rewrite; each fix has property tests in
`tests/test_guitar_export_fixes.py`.

- **Body taps.** Groove memory mapped the acoustic's `body_tap` (a fixed
  E2 dead note) chord-relatively, so restated taps changed pitch with the
  chords. Unpitched gestures now keep their pitch.
- **Chromatic approaches.** Restatement snapped out-of-key approach notes
  onto the scale (C before D instead of C#). They are now transposed with
  the root and placed a half step from the note they resolve into. The
  bass engine resolves its own approaches the same way: the chord change
  after an approach lands on the root it stepped toward, not on a fifth
  drop, pedal or octave jump drawn for the new chord. A walking line's last
  bar aimed at the key's tonic in a register the next section did not use;
  it now aims at the next section's first chord (`next_first_numeral` in the
  transition context) where that section's walk opens.
- **Section-start voicing.** The rhythm guitar's first chord of a section had
  no previous shape, so a movable shape sat at its root's octave: harbour
  road's choruses opened on F an octave above the rest. The first chord now
  leads from the home position.
- **Section-start dynamics.** The transition planner measured pitched parts
  per note, so a verse ending in four-note dead-note chucks looked denser
  than a chorus of three-note stabs; the "energy jump" triggered a bridge
  start that pulled the chorus's first bar toward the chucks' velocity.
  Pitched parts are now measured per gesture (notes within a strum's spread
  are one attack), with chucks, ghosts and body taps left out of the
  loudness. Drums still count every hit.
- **Capo in tabs.** Tabs ignored the capo. Parts record `capo_windows` on
  their timeline; the tab view writes frets relative to the capo and a
  `CAPO` line. A pitch struck twice within one tab step is one fretted note
  (it was forced onto a second string).

## Lead and arpeggiator follow-ups (2026-09-26)

Found after the review above, in the examples' exports:

- **Octave stabs.** `counter: octaves` played single notes: the composer's
  `_tidy`, the section render's post-feel clip and the build's final clip
  all kept one note per attack, and only country double stops were marked
  as two strings. Octave stabs now carry the role `stab_octave`, and
  `composer.realize.DOUBLE_STOP_ROLES` / `sounds_with` are the one rule
  every monophonic clip uses (a double stop's two notes also share their
  timing humanization and move together under the groove clock). The
  root's octave had to fit the register whole, so some chords (Bm in a
  `[62, 81]` register) got no stab at all; the stab now falls back to the
  fifth's octave (then another chord tone's), plays the root alone in a
  register narrower than an octave, and every bar a chord holds gets one.
- **`dive_rate` in composed solos** only touched the final `dive` note.
  It now works like `bend_rate`: 0.3 plays the composed dives as written,
  0 holds them, higher values dive held solo notes (1.5 beats or longer,
  the phrase endings) on a per-note stream, all of them at 1.
- **Solo ending in the log.** A drawn `dive` ending plays only in rock,
  metal and punk (`arrangement.DIVE_FAMILIES`); elsewhere the note is held.
  The arrangement DNA now resolves that when it is drawn, so the
  signature says `hold`, and each solo's composer line names the ending it
  played. A pinned `solo_ending: dive` dives in any genre.
- **Trills under swing.** The trill ending's 32nds sat on sixteenth
  positions the groove clock swung one by one, reordering them into
  0.01-beat notes. Trill notes are tagged `trill`: the performance shares
  one humanization offset across the ornament and the groove clock moves it
  as a whole with its first note, keeping its note lengths.
- **Riff-alone intros mean the riff alone.** The lead and the arpeggiator
  played from bar 1 while the drums and bass waited. The band's entry bar
  (`render._band_entry_bar`, from `arrangement.riff_alone_intro` and
  `intro_entry_bar`) is now shared: the lead composer plans its intro hook
  from that bar (`LeadContext.entry_bar`), and every part that is not a
  riff player (`RIFF_PLAYERS`), drums and bass aside, drops what it would
  play before it. The drums are composed before the lead so the entry is
  known.
