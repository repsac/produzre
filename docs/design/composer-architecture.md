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
| `lead_gtr` `foreground` | `auto` | `full`: the lead is the melody (instrumental). `auto`: hooks, fills, counter-lines, and solos around a singer. |
| instrument `groove_memory` | true | Per-instrument opt-out. |
| instrument `groove_cycle_bars` | genre | 1 or 2-bar groove cycle. |

## Plan keys

| Key | Content |
|---|---|
| `composer.song` | The `SongComposer` (DNA, listener, memory). |
| `composer.lead.<section>` | Composed notes: beat, duration, pitch, accent, technique, role. |
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
- The composer writes the lead. Bass and rhythm guitar gain form through
  groove memory but do not yet derive lines from the DNA. A bass counter-line
  from the hook's rhythm is the natural next piece.
- Harmony changes are limited to turnarounds and the final lift. Reharmonizing
  repeats (substitutions, secondary dominants) needs numeral spelling for
  applied chords.
- The listener models pitch intervals and durations, not meter position or
  harmony. Adding metric position would let it judge syncopation surprise.
