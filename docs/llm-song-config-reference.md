# Song configuration reference

Produzre reads a YAML song description and writes MIDI. Use this reference
for version 0.9.0 when writing configs yourself or with an assistant. Run commands from the repository root with
`python produzre_entry.py`, or use a built `produzre` executable.

## File structure

A theme is a recurring musical idea shared across the song.
A recipe supplies style defaults for a section. A persona supplies defaults
for an instrument's playing character. A pocket describes its timing position
ahead of or behind the beat.

```yaml
version: 1
song:
  title: My Song
  bpm: 120
  key: E
  mode: minor
  meter: "4/4"
  genre: rock
  seed: 42
instruments:
  bass:
    persona: tight
    params: {articulation_style: pick}
sections:
  verse:
    type: verse
    bars: 8
    harmony: {progression: "i bVII bVI V7"}
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}
arrangement: [verse, verse]
```

The top-level blocks are `version`, `song`, `sections`, `arrangement`,
`instruments`, `engines`, `exports`, `groove`, and `themes`. The last five are
optional. Global instrument settings supply defaults; a section's `instruments`
block decides which instruments play. Include `harmony: {}` there when using
pitched engines. A harmony progression by itself does not enable that engine.
Arrangement entries must name existing sections.

Use `params` for engine controls and direct instrument fields for `intensity`,
`register`, `solo`, `recipe`, and `genre`. Older configs can use `extra` for
engine controls. Avoid splitting the same control across both forms.

## Song settings

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `title` | String | `produzre` | Title and export filename prefix. |
| `bpm` | Positive number; usually 40-240 | 120 | Quarter notes per minute. |
| `key` | C, C#, Db, D, D#, Eb, E, F, F#, Gb, G, G#, Ab, A, A#, Bb, B | `C` | Root note for harmony and melodies. |
| `mode` | Seven modes; aliases below | `ionian` | Scale used for degrees without explicit accidentals. See below. |
| `meter` | "numerator/denominator" | `4/4` | Time signature. Write it as a quoted string, such as `"4/4"`. |
| `beats_per_bar` | Positive quarter-note count | Derived from `meter` | Legacy quarter-note bar length override. Normally omit it. |
| `genre` | Recipe family name | Unset | Selects matching recipes where available. |
| `project` | Project name | Local default project | Project seed to combine with `seed`. |
| `seed` | Integer | 0 | Integer seed for song material and performance. |
| `take` | Integer | 0 | Performance version; preserves the theme bank, the song's stored recurring musical ideas. |
| `variation` | Nonnegative; start at 0-1 | 0 | Bias toward different performance choices; its effect depends on the engine. |
| `themes_auto` | Boolean | true | Compose a riff (a short repeated phrase) and hook (a returning melody) if you supply no themes. |
| `composer` | Boolean | true | Write the lead from song DNA with phrase forms and section memory. See [The composer](#the-composer). `false` restores the 0.9 motif generator. |
| `groove_memory` | Boolean | true | Drums, bass, rhythm and acoustic guitar settle into one groove per section, vary it at phrase ends, and recall it when the section returns. |
| `turnarounds` | Boolean | Unset | Force turnarounds on (`true`) or off (`false`) for every section. Unset: only preset or recipe progressions get them. |
| `final_chorus` | `modulate` or an integer | Unset | Move the last chorus and everything after it up a whole step (`modulate`) or by N semitones. |
| `humanize_velocity` | Nonnegative number | 0 | Legacy song velocity variation used by engines that read it. |
| `humanize_timing` | Nonnegative quarter-note beats | 0 | Legacy song timing variation in beats. Prefer the explicit instrument timing controls below. |
| `exports_root` | Directory path | `exports` | Output parent directory. |
| `pattern_bars` | Integer >= 1 | 1 | Bars in each pattern, a reusable chunk of notes extracted from the performance. |
| `pattern_quantize_beats` | Number >= 0 | 0 | Quantize extracted patterns in quarter-note beats; zero preserves timing. |
| `pattern_velocity_step` | Integer >= 1 | 1 | Velocity bucket width for pattern comparison and output. |
| `pattern_merge_repeats` | Boolean | false | Combine consecutive repetitions into longer pattern blocks. |
| `pattern_merge_min_run` | Integer >= 2 | 2 | Minimum repetition count to combine, at least 2. |
| `pattern_merge_max` | Integer >= 0 | 0 | Maximum repetitions in a combined block; zero means unlimited. |
| `params.transitions` | Mapping; see [Transitions](#transitions) | See Transitions | Arrangement transition settings. |

Modes: `ionian` (`major`), `dorian`, `phrygian`, `lydian`, `mixolydian`,
`aeolian` (`minor`), and `locrian`. Dorian has a raised sixth compared with
natural minor. Lydian raises the fourth of major; mixolydian lowers its seventh.

### Meter and beat units

Odd and compound meters phrase by their beat groups. 6/8 pulses in two dotted
quarters, 7/8 groups its eighths 2+2+3, 5/4 groups its quarters 3+2, and 12/8
pulses in four dotted quarters. Melodies are built group by group, comp riffs
open every group with an attack, and group starts count as strong beats for
chord tones. `song.meter_grouping` (or a section's `meter_grouping`) sets
another grouping, in the meter's own units: `"3+2+2"` for 7/8, `"2+3"` for 5/4.
A grouping that does not add up to a section's bar is ignored there.

Unless you set `chord_rate`, a progression changes chords once per bar in
every meter; a recipe's rate is scaled to the section's bar length.

Every internal beat is a quarter note. A bar lasts 4 beats in 4/4, 3 in 3/4 or
6/8, 3.5 in 7/8, and 5 in 5/4. The drum grid has four steps per quarter note.
6/8 groups eighth notes into two dotted-quarter pulses; it does not use the
3/4 backbeat. The composed drummer plays 6/8 and 12/8 on the dotted-quarter
pulse and its eighths: the backbeat on pulses 2 and 4 in 12/8 (the second
pulse in 6/8), kicks on the eighth grid, and fills of whole pulses. Drum-only
sections get the grouping from their meter, with or without a progression. A section `meter` overrides the song meter. Full-song MIDI and
stems (one MIDI file per instrument) carry time-signature changes; section clips
(one section at a time) and patterns carry their own
meter. Explicit `beats_per_bar` can disagree with the signature, so use `meter`
for ordinary songs.

## Sections and dynamics

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `type` | Section type string | Required | Musical function used for recipes, roles, and phrase development. |
| `bars` | Positive number | Unset | Section length in its own meter. |
| `beats` | Positive quarter-note count | Unset | Length in quarter notes; takes precedence over `bars`. |
| `key`, `mode`, `meter` | Same values as song settings | Song values | Local harmony and meter. |
| `harmony` | Mapping | Automatic when available | `progression`, `chord_rate`, and optional `recipe`. |
| `progression` | Roman-numeral string or list | Unset | Older shorthand for `harmony.progression`. |
| `instruments` | Instrument mapping | Empty | Instruments active in this section. |
| `intensity` | Normally 0-1 | Table below | Overall performance intensity, normally 0-1. |
| `energy` | `low`, `mid`, `high`, or 0-1 | From section type | Transition energy: `low`, `mid`, `high`, or 0-1. |
| `intent` | `drop`, `half_time`, `build`, `stomp`, `open` | Unset | Drum contrast: `drop`, `half_time`, `build`, `stomp`, or `open`. |
| `seed`, `variation` | Integer seed; nonnegative variation | Song values | Local performance overrides. |
| `solo`, `role` | Boolean; role string | Unset | Bass feature hints; instrument `solo: true` also enables lead or bass solos. |

| Type | Initial intensity |
|---|---|
| `intro` | 0.55 |
| `verse` | 0.65 |
| `prechorus` | 0.75 |
| `chorus` | 0.90 |
| `bridge` | 0.70 |
| `solo` | 0.85 |
| `breakdown` | 0.45 |
| `outro` | 0.50 |
| Other | 0.65 |

An occurrence is one appearance of a section in the arrangement.
Implicit intensity rises by 0.05 per repeat of the same section type, up to
0.10 extra. Explicit intensity stays fixed. Instrument intensity overrides
section intensity. Use `enabled: false` to silence an instrument; intensity is
an expression control, so notes can still play at zero.

The composed drummer's velocity follows intensity and energy: a verse at the
defaults (0.65, energy 0.3) plays at its base touch, a default chorus about a
quarter louder, and each implicit repeat a little louder again. A section
handed to the drum engine by `intent` plays at the same dynamics as the
composed sections around it.

The ensemble planner assigns lead activity windows, accompaniment density,
and fill ownership. Short sections still get a lead window. Bass can avoid
drum fills, and rhythm guitar leaves room during lead phrases.

## Harmony

Write Roman numerals as a space-separated string or a list:

```yaml
harmony:
  progression: [i, bVII, bVI, V7]
  chord_rate: 4
```

Uppercase means major and lowercase means minor. An unaltered numeral uses the
section's mode. An accidental prefix is relative to the major scale: in C minor,
`bVII` is Bb and `bVI` is Ab. Supported chord colors include `7`, `maj7`,
`m7`, `sus2`, `sus4`, `dim` or `°`, `°7`, `ø7`, and `aug` or `+`.
Guitar shapes can simplify a color when an exact playable shape is unavailable.

`chord_rate` is quarter notes per chord, independent of meter. In 4/4, 4 means
one chord per bar, 2 means two per bar, and 8 means one every two bars. If omitted,
a matching harmony recipe may supply it; otherwise it is 4. Progressions repeat
to fill the section, and the last chord is clipped at the section boundary.

A **turnaround** marks each arrival. When the next section starts on the
tonic, the second half of the last bar moves to a dominant: `V`, `V7` for
blues, soul, jazz, funk, and country, or `bVII` for modal rock. It is skipped
when the last chord already leads home, such as `V` or `bVII`. Preset and
recipe progressions get turnarounds automatically. Explicit progressions
keep exactly what you wrote unless you set `turnaround: true` in the
section's harmony block or `song.turnarounds: true`.

| Style | Starting progression |
|---|---|
| Major pop | `I V vi IV` |
| Minor rock | `i bVII bVI V7` |
| Blues | `I I I I IV IV I I V IV I V` |
| Jazz | `ii7 V7 Imaj7 vi7` |
| Funk | `i IV i IV` |
| Country | `I IV V I` |
| Reggae | `I IV I V` |
| Soul | `I vi ii V` |
| Latin | `i iv V7 i` |

## Recipes and personas

Merge order is persona, recipe, global instrument params, then section params.
Later values win, including explicit zero. A `persona` on a section's
instrument replaces the global persona for that section only, at the same
lowest layer. Recipes are selected by genre,
section type, tempo, and section meter. An explicit instrument `recipe` wins
over automatic selection. A section instrument `genre` overrides the global
instrument genre, which overrides `song.genre`.

The same genre also chooses the composed player. A drummer, rhythm guitar,
bass or acoustic part whose genre differs from the song's plays that
genre's player (a reggae `genre` on a hard rock song's section gets a
one-drop drummer, a skank and a reggae bass role); the player is seeded
from the song, so repeated sections share it. A lead with its own genre
draws its verse and bridge ideas and licks from that genre and keeps the
song's hook. Arrangement habits (into-chorus devices, endings) stay the
song's, so the band still agrees on them.

Built-in recipe families include rock, hard_rock, soft_rock, alt_rock, prog_rock,
arena_rock, blues_rock, pop_rock, grunge, emo, metal, heavy_metal, punk, ska,
blues, soul, rnb, gospel, jazz, funk, pop, dance_pop, electronic, techno,
new_wave, country, reggae, latin, folk, and classical. Coverage varies by
instrument. Unmatched genres fall back to engine defaults.

Recipes live under `produzre/resources/recipes/<instrument>/`. User files in
`<config-dir>/recipes/<instrument>/` can replace a built-in recipe with the same
id. Persona overrides live under `<config-dir>/personas/`. The config directory
is the parent of the path printed by `project path`.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `bass.persona` | `tight`, `pocket`, `loose`, `funk`, `metal`, `walking`, `dub` | `tight` | Choose the base playing character for bass. |
| `drums.persona` | `tight`, `experimental`, `rock`, `metal`, `funk-lite`, `jazz-lite` | `tight` | Choose the base playing character for drums. |
| `rhythm_gtr.persona` | `tight`, `loose`, `aggressive`, `funky`, `jangly` | `tight` | Choose the base playing character for rhythm guitar. |
| `lead_gtr.persona` | `balanced`, `melodic`, `shredder`, `bluesy`, `ambient` | `balanced` | Choose the base playing character for lead guitar. |
| `acoustic_gtr.persona` | `natural`, `precise`, `expressive`, `percussive`, `delicate` | `natural` | Choose the base playing character for acoustic guitar. |

`tight` favors precise timing; `pocket` and `dub` bass sit behind the beat.
`walking` plays a walking line (`rhythm_pattern: walking`, see Bass controls);
a recipe tunes its feel but never turns it back into a rhythm pattern. `funk`
bass uses slap articulation. `jangly`
guitar rings longer, while `funky` uses short and muted strokes. Lead personas
change phrase length, rests, resolution, and contour. Acoustic personas change
touch, timing, and muting. To change a recipe value, set that control explicitly.

## Shared timing

Put the `groove` block at the top level, beside `song`:

```yaml
groove:
  swing: 0.6
  swing_16th: 0
  pocket_ms: {bass: 8, rhythm_gtr: 3}
```

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `groove.swing` | 0-1 | recipe | Delay eighth-note offbeats by `0.25 * swing` beats. About 0.67 gives triplet swing. Without another source: 0. |
| `groove.swing_16th` | 0-1 | Half of resolved swing | Delay the e/a sixteenths by `0.25 * swing_16th`. Set zero to keep them straight. |
| `groove.pocket_ms` | Instrument names mapped to milliseconds | {} | Positive values play behind the beat, negative ahead. Applies to pitched engines. |
| Instrument `pocket_ms` | Signed milliseconds | Unset | Explicit pitched-instrument offset, ahead of the groove mapping and push/pull. |
| Instrument `push_pull` | Usually -0.2 to 0.2 | persona | Positive pushes ahead. Converted to `-100 * value` ms, capped at 25 ms each way. Also read by drums. Without a preset: 0. |
| Instrument `timing_jitter_ms` | Nonnegative milliseconds | persona | Random timing range in milliseconds, seeded for repeatability. Without a preset: 0. |
| Instrument `velocity_humanize` | 0-1 | persona | Seeded velocity variation. Drums have a 0.05 fallback. Without a preset: 0. |

Drum `params.swing` and `params.swing_16th` override the global groove when
explicitly set. The global groove overrides persona and recipe swing. A
composed drummer's feel comes next: a straight, laid-back or pushing drummer
plays even eighths and a shuffle drummer swings, and the band follows, so a
recipe's swing never reaches a song whose drummer plays straight. Without a
global groove or a composed drummer, the resolved drum recipe supplies the
band's swing, including sections where drums are silent. Compound meters
(6/8, 9/8, 12/8) are already in triplets, so recipe, persona and drummer swing
do not apply there; an explicit swing still does. True triplet attacks are not
swung again. Drum fills and pickups follow the same clock.

Pitched instruments use one shared timing pass after rendering. Explicit
`pocket_ms` wins over the groove mapping, then nonzero `push_pull`, then the
active-groove defaults: bass 8 ms, rhythm/acoustic guitar 3 ms, others 0 ms.
These defaults engage only when a timing indication exists. Drums apply their
own timing pass; use their `push_pull` rather than `pocket_ms`.
`humanize_timing`, `humanize_velocity`, `timing_variation`, and `vel_variation`
are older engine-specific controls with different units, described below.

## Themes

Automatic composition is on by default. With no authored themes, the song seed
creates a one-bar riff and two-bar melody. See [DETERMINISM.md](../DETERMINISM.md) for how takes preserve this material. Set `song.themes_auto: false` to disable automatic
composition. Authored themes still work with that switch off.

```yaml
themes:
  bass_line:
    role: bass_motif
    register: [36, 60]
    events: "1:.5 3:.5 4:1 5:1 1:1"
  hook:
    role: melody
    allow_development: true
    degrees: [5, 6, 5, 4, 2, 1]
    rhythm: [0.5, 0.5, 1, 1, 1, 4]
```

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `role` | `melody`, `riff`, `bass_motif`, `drum_groove` | `melody` | Choose the theme's musical role. A `drum_groove` theme maps degrees to kit voices; see below. |
| `events` | Degree:duration string | Required unless using lists | Space-separated `degree:duration` tokens in quarter-note beats. |
| `degrees`, `rhythm` | Equal-length degree and duration lists | Alternative to `events` | Equal-length lists of degrees and positive durations. |
| `register` | MIDI bounds: 0 <= low <= high <= 127 | Role-dependent | Inclusive `[low, high]` MIDI range. |
| `octave` | Integer | 0 | Integer octave offset added to every sounding event. |
| `length_beats` | Positive quarter-note beats | Sum of durations | Optional length assertion; must match the duration sum. |
| `allow_development` | Boolean | false for authored themes | Allow arrangement transformations. False keeps the written sequence. |

Durations must be finite and positive. Degrees are 1-7 relative to the key and mode. Prefix `b` or `#` for accidentals;
suffix `+` or `-` to shift octaves. `.` or `r` is a rest. Octave offsets are
folded into the selected register when necessary. The tonic and each repeated
statement's final note retain their pitch identity. Limited semitone adjustment
can move interior notes toward the current chord; genre blue notes are retained.

Authored themes replace automatic material as a bank. The first declared theme
for a role is the active source; all named themes remain available in the plan.
See the [theme architecture](design/theme-bank-architecture.md) for default
register ranges and the treatment table.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `bass.params.lock_to_riff` | 0-1 | 0 | Probability of playing each riff onset. With no bass motif, the riff's realized pitches are quoted at the same rate. |
| `bass.params.motif_quote_rate` | 0-1 | 1.0 when a `bass_motif` theme exists | Probability of quoting each motif note's pitch. An authored motif is the bass line: its rhythm and written lengths always play, and a note not quoted plays the chord root near it. 0 turns the coupling off and the bass plays its own line. |
| `rhythm_gtr.params.lock_to_riff` | 0-1 | 0 | Probability of adding a riff onset to the accent targets. Chords retain their own voicings. |
| `drums.params.riff_accent_rate` | 0-1 | 0 | Probability of adding a kick at a riff onset. Grid, backbeat spacing, and limb constraints still apply. |
| `drums.params.riff_accent_boost` | Nonnegative multiplier | 1 | Velocity multiplier for existing kick/snare accents near riff onsets. |
| `drums.params.groove_strength` | 0-1 | 1 when a `drum_groove` theme exists | Crossfade between the groove theme's kit pattern and the genre pattern. 0 disables the theme. |
| `lead_gtr.params.theme_quote_rate` | 0-1 | 0.65 | Probability of quoting a nearby melody-theme pitch on eligible interior notes. |

Bass, drums, and rhythm guitar require explicit coupling to the riff. An
authored `bass_motif` or `drum_groove` theme is itself the opt-in. An
authored `bass_motif` owns the bass in every section, band sections
included: the composer's bass roles and riff doubling step aside for it.
With `lock_to_kicks: true` the kick fills only where the motif rests. Lead
guitar, acoustic melody, and the phrase arpeggiator use the shared melody
guide automatically. `grid`, MIDI `source`, and section-local theme blocks are
not implemented. Unsupported keys inside a theme raise an error.

### Drum groove themes

A `drum_groove` theme is rhythm plus drum voice instead of rhythm plus pitch.
Degrees select the voice:

| Degree | Voice |
|---|---|
| `1` | Kick |
| `2` | Snare |
| `3` | Closed hat |
| `4` | Open hat (joins the hat line, forced open) |
| `5` | Crash (added as an extra hit) |
| `6` | Ride (moves the top-cymbal line to ride) |
| `7` | Tom (added as an extra hit, cycling high, mid, low) |

```yaml
  kit_groove:
    role: drum_groove
    allow_development: false
    events: "1:.5 3:.5 2:.5 3:.5 1:.25 1:.25 3:.5 2:.5 4:.5"
```

The theme replaces the recipe's kick, snare, and hat steps. Voices the theme
does not use stay on the recipe, and genre and persona still control
velocities, ghosts, fills, and humanization. Crash and tom onsets are added
alongside the recipe's own crashes and fills. Arc transforms apply unless the
theme is locked, so a breakdown thins the kit. A groove theme needs no
harmony, so it also plays in drums-only sections; the section length comes
from `bars` and the meter. Pitched roles still need a harmony plan.

## Bass controls

The descriptions retain values from the built-in `tight` persona and label
engine fallbacks. A recipe can replace them. Rates are probabilities in 0-1.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `density` | 0-1 | persona | Keep more or fewer eligible rhythm slots. Tight: 0.7. Every bar keeps at least one note. |
| `rest_rate` | 0-1 | persona | Remove selected notes to leave gaps. Tight: 0. Every bar keeps at least one note. |
| `rhythm_pattern` | `anchor`, `push`, `drive`, `syncopated`, `rock_riff`, `funk_16ths`, `walking` | persona | Choose the bass attack pattern. Tight: `anchor`; walking persona: `walking`. |
| `articulation_style` | `finger`, `pick`, `slap`, `mute` | persona | Change attack, length, and pattern bias. Tight: `finger`. |
| `register_low`, `register_high` | MIDI pitches 0-127 | persona | Inclusive MIDI pitch limits for every bass note, composed roles, riff doubles and groove-memory restatements included. Your values win over a recipe's, a recipe's over the persona's. Tight: 28, 52. |
| `approach_rate`, `chromatic_rate` | 0-1 each | persona | Approach-note probability and chromatic choice. Approaches occur before chord changes. Tight: 0, 0. |
| `max_passing_per_bar` | Integer >= 0 | persona | Passing-note limit per bar. Tight: 0. |
| `root_bias` | 0-1 | 0.65 engine fallback | Chance of including the root among interior chord-tone candidates. |
| `octave_jump_rate`, `fifth_jump_rate`, `pedal_rate` | 0-1 each | persona | Octave changes, fifths at chord changes, and held pitch across chords. Tight: 0, 0, 0. |
| `motion_style` | `stepwise`, `leaping`, `mixed` | `stepwise` | Choose how the bass moves between pitches. |
| `lock_to_kick`, `lock_to_snare`, `lock_to_hat` | 0-1 each | persona | Add notes at kick, accent, or top-cymbal attacks. Zero disables that source. Tight: 0.8, 0, 0. |
| `lock_to_kicks` | Boolean | false | Alternate renderer based on drum kick attacks. Distinct from the probability above. |
| `avoid_fills`, `octave` | Boolean; integer octave | true, 2 | Fill avoidance and starting octave in the alternate kick-locked renderer. |
| `lock_to_riff`, `motif_quote_rate` | 0-1 each | 0; 1.0 with a bass motif | Theme coupling; see Themes. |
| `slide_rate` | 0-1 | 0.2 | Chance a note slides in from one or two semitones below, written as pitch bend. |
| `vibrato_rate` | 0-1 | 0.35 | Chance a note held half a beat or longer gets a gentle pitch-bend vibrato. |
| `accent_strength` | Nonnegative multiplier | persona | Velocity multiplier on accents. Tight: 1.1. |
| `slap_pop_rate`, `slap_thumb_rate`, `ghost_perc_rate` | 0-1 each | persona | Pop, thumb, and percussive ghost choices in slap mode. Tight: 0.4, 0.9, 0. |
| `slap_velocity_floor`, `pop_velocity_boost` | Velocity 1-127; velocity-unit offset | persona | Slap minimum velocity and added pop velocity units. Tight: 70, 15. |
| `fill_rate`, `fill_complexity`, `fill_avoid_drums` | 0-1 each | persona | Fill chance, complexity, and reduction during drum fills. Tight: 0.2, 0.3, 0.8. |
| `phrase_len_bars` | Integer >= 1 | 4 | Fill boundary spacing; `phrase_length_bars` is an alias. |
| `section_role_variation` | Boolean | false | Bias an anchor pattern toward drive in choruses and syncopation in bridge/solo sections. |
| `solo_density`, `solo_register_high` | 0-1; MIDI pitch 0-127 | persona | Density and upper range for featured bass. Tight: 0.85, 64. |
| `motif_repeat_rate` | 0-1 | persona | Repeat solo motifs or two-bar rock/funk onset cells. Tight: 0.3. |

`lock_to_kick: 1` adds kick attacks but does not remove all independent bass
notes. Use `lock_to_kicks: true` for the alternate kick-led renderer. The older
bass `swing` and `syncopation` fields were unused and have been removed from
presets. Use the shared groove and `rhythm_pattern` instead.

A bass line plays every bar. `density` and `rest_rate` thin a bar but never
empty it; whole silent bars come only from the band's arrangement devices
(a drop, stop-time, a riff-alone intro) or rests written into a `bass_motif`. The line's rhythm is drawn once per
section type, so a returning chorus keeps its line instead of redrawing a
thinner one.

### Walking bass

`rhythm_pattern: walking` (the walking persona sets it) plays a walking line
planned a bar at a time. Every beat sounds (dotted quarters in 6/8, 9/8 and
12/8), so every bar has its downbeat in any meter. Each chord starts on its
root; a chord held into a new bar starts that bar on another chord tone. The
last beat before each change steps into the next downbeat by a half step or a
scale step; `chromatic_rate` is the share of half-step approaches. The inner
beats connect the two with chord tones on the strong beats, and the root
sounds only on the downbeat. `register_low` and `register_high` bound the
line. `density`, `rest_rate`, the drum locks, octave jumps, fifth drops,
fills, slides and vibrato do not apply to a walk: they shape rhythm patterns,
and a walk has no gaps to fill. A walking line also keeps the engine's line
in band sections and groove memory leaves it alone. The swing of the song's
groove applies as usual.

## Drum controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `kick_density`, `snare_density` | Nonnegative multipliers | recipe | Scale extra kick/snare activity; they do not remove every template anchor at zero. Engine fallback: 1, 1. |
| `hat_density` | 0-1 | persona | Probability of playing eligible top-cymbal steps. Engine fallback: 1. |
| `fill_rate`, `fill_chatter` | 0-1 each | persona | Phrase-fill probability and extra hat chatter. Engine fallback: 0.25, 0. |
| `fill_length` | `short`, `medium`, `long` | recipe | Choose how much of the bar a fill occupies. Engine fallback: `medium`. |
| `phrase_len_bars` | Integer >= 1 | From meter | Bar spacing for phrase fills. Without a setting: 2 bars when a bar lasts approximately 3 or 6 quarter-note beats, otherwise 4. |
| `phrase_end_emphasis` | Nonnegative multiplier | recipe | Extra weight on phrase-ending fills. Engine fallback: 1.5. |
| `pickup_rate`, `downbeat_rate` | 0-1 each | recipe | Transition pickup and opening crash/kick probabilities. Engine fallback: 0.7, 0.8. |
| `accent_strength` | 0-1 | recipe | Velocity lift for structural accents. Engine fallback: 0.1. |
| `ghost_rate`, `ghost_steps` | 0-1; list of step indices | recipe | Snare ghost probability and zero-based internal step indices. Without a recipe, the groove template supplies both values. |
| `choke_rate`, `flam_rate`, `drag_rate` | 0-1 each | recipe | Performance ornament probabilities. Engine fallback: 0, 0, 0. |
| `swing`, `swing_16th`, `push_pull`, `timing_jitter_ms`, `velocity_humanize` | See [Shared timing](#shared-timing) | See Shared timing | Drum timing and expression; see [Shared timing](#shared-timing). |
| `riff_accent_rate`, `riff_accent_boost` | 0-1; nonnegative multiplier | 0, 1 | Theme kick additions and accent velocity. |
| `groove_strength` | 0-1 | 1 with a drum groove theme | Crossfade between a `drum_groove` theme and the genre pattern; see Themes. |
| `voices` | Voice mapping | recipe | Individual kit voices, below. Persona values supply the base settings. |
| `constraints` | Constraint mapping | Enabled | Limb collisions, hat choking, fill ducking, and foot limits. |

Put voice blocks directly under the drums instrument:

```yaml
instruments:
  drums:
    voices:
      kick:
        syncopation: {rate: 0.3, placements: ["2&", "4a"]}
        double: {rate: 0.2, placements: ["4&"]}
      snare:
        ghosts: {rate: 0.25, placements: ["2a", "4e"], velocity_bias: -8}
        articulation: {default: crossstick}
      hats:
        pattern: {rate: 0.8, placements: ["1", "1&", "2", "2&", "3", "3&", "4", "4&"]}
        open: {rate: 0.2, placements: ["2&", "4&"]}
        pedal: {rate: 0.3, placements: ["2", "4"]}
        accents: {rate: 0.5, placements: ["1", "3"], boost: 12, bias: -4}
        velocity: {bias: 0}
```

Placements count quarter notes from 1 within each bar. Suffix `&` adds 0.5,
`e` adds 0.25, and `a` adds 0.75. Numbers such as 2.5 also work. `steps`-style
internal fields are zero-based sixteenth indices. Empty hat/kick placement
lists disable those candidate positions. Ghost `ghost_steps: []` instead asks
for inferred positions near the backbeat.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `kick.density`, `snare.density`, `hats.density` | Nonnegative densities; hats 0-1 | Inherit drum densities | Override that voice's density. |
| `kick.syncopation.rate`, `.placements` | 0-1; placement list | recipe | Chance and candidates for added kicks. |
| `kick.double.rate`, `.placements` | 0-1; placement list | recipe | Chance and anchor candidates for a two-hit burst. |
| `snare.ghosts.rate`, `.placements`, `.velocity_bias`, `.subdiv` | 0-1; placement list; velocity units; positive integer | recipe | Ghost chance, positions, velocity offset, and placement-grid resolution. Without an override, velocity bias is 0 and resolution is four steps per quarter note. |
| `snare.articulation.default` | `normal`, `rimshot`, `crossstick` | recipe | Choose the backbeat articulation. Without a preset: `normal`. |
| `hats.pattern.rate`, `.placements` | 0-1; placement list | recipe | Top-cymbal density and candidate positions. |
| `hats.open.rate`, `.placements` | 0-1; placement list | recipe | Open hats on selected top-cymbal hits; `opens` is an alias. |
| `hats.pedal.rate`, `.placements` | 0-1; placement list | recipe | Foot-chick chance and positions. Works with ride cymbal too; without a preset, the rate is 0. |
| `hats.accents.rate`, `.placements`, `.boost`, `.bias` | 0-1; placement list; velocity units each | recipe | Accent chance and positions; boost accented hits by 8 velocity units by default, bias unaccented hits by 0. |
| `hats.velocity.bias` | Signed velocity units | 0 | Velocity units added to all hand-played hats/ride, default 0. |
| `toms.groove.rate`, `toms.fills.rate` | 0-1 each | 0, 0 | Additional groove toms and fill runs, default 0. |
| `crash.rate`, `crash.placements` | 0-1; placement list | recipe | Crash chance and candidate positions. |
| `ride.bell_rate` | 0-1 | 0 | Ride-bell chance per ride bar, default 0. Groove memory keeps the bell accents. |
| `cymbals.splash_rate`, `cymbals.china_rate` | 0-1 each | 0, 0 | Extra cymbal probabilities, default 0. |

Voice `params` also accepts the older flat fields: hats `density`, `open_rate`
(or `open_hat_rate`), `pedal_rate`, `accent_rate`; kick `syncopation_rate`,
`double_kick_rate`; snare `ghost_rate`, `ghost_steps`, `ghost_placements`,
`ghost_subdiv`, `ghost_velocity_bias`; toms `groove_rate`, `fills_rate`.
The named concept blocks above take precedence.

Drum constraints run before humanization. They discard same-pitch duplicate
hits, resolve limb collisions, choke open hats, and duck hats during fills.
Very dense kick playing can suppress pedal hats. Fields under `params.constraints`:

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `enabled` | Boolean | true | Apply physical kit constraints. |
| `max_hand_hits` | Integer >= 0 | 2 | Maximum hand-played hits at one grid step. |
| `max_foot_hits` | Integer >= 0 | 2 | Maximum foot-played hits at one grid step. |
| `fill_duck_hats` | Boolean | true | Reduce or remove hand-played hats during fills. |
| `kick_density_hihat_pedal_limit` | Nonnegative kicks per quarter-note beat | 0.6 | Suppress pedal hats above this kick density; short bars use a four-quarter-note denominator. |

## Rhythm guitar controls

There are two renderers. A selected recipe normally enables pattern rendering.
Set `use_patterns: true` explicitly when working without a recipe. Set false
for the legacy chord/grid controls. `follow_hats: true` selects a separate
renderer that follows drum density when drum features are available.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `style` | Styles listed below | recipe | Pattern vocabulary, listed below. Neutral fallback: `auto`. |
| `strum_style` | `balanced`, `downbeat_heavy`, `upbeat_heavy` | persona | Choose which strokes get the velocity emphasis. Neutral fallback: `balanced`. |
| `density` | 0-1 | recipe | Fraction of eligible strokes, scaled by intensity and coordination. Neutral fallback: 0.6. |
| `palm_mute` | 0-1 | recipe | Palm-mute probability. Neutral fallback: 0.06. |
| `voicing` | `power`, `triad`, `shell`, `octaves`, `auto` | recipe | Choose the chord shape. Neutral fallback: `auto`. |
| `register` | `low`, `mid`, `high` | `mid` | `low`, `mid`, or `high` in params for the pattern renderer. |
| `register_min`, `register_max` | MIDI pitches 0-127 | Unset | Explicit MIDI range. |
| `strum_ms` | 0-100 milliseconds | persona | Spread the strings in time; set zero for simultaneous notes. Neutral fallback: 15 ms. |
| `accent_strength` | 0-1 | persona | Set the velocity emphasis on accents. Neutral fallback: 0.5. |
| `chuck_rate`, `sustain_cut_rate` | 0-1 each | persona | Add dead strokes and shortened stabs. Neutral fallback: 0, 0. |
| `humanize_velocity`, `humanize_timing` | 0-1 each | persona | Vary velocity and timing within the engine. Neutral fallback: 0.1, 0.05. |
| `downbeat_boost` | 0-1 | persona | Raise downbeat velocity. Neutral fallback: 0.2. |
| `section_contrast` | 0-1 | 0.7 | Blend section defaults into neutral defaults. |
| `phrase_len_bars`, `phrase_development` | Integer >= 1; Boolean | 4, true | Phrase cycle and bar-to-bar variation. |
| `lock_to_riff` | 0-1 | 0 | Probability of adopting riff accent positions. |
| `vibrato_rate` | 0-1 | 0.4 | Chance a chord held 0.75 beats or longer gets a pitch-bend vibrato. Pitch bend is per channel, so the whole chord moves. |
| `sustain_mode` | Boolean | false | Held chords on either renderer: each chord is strummed when it arrives and restruck every `sustain_duration` beats while it lasts, ringing open unless you set `mute`. It replaces the strum pattern and selects the pattern or grid renderer over composed comping. |
| `sustain_duration` | 0.1-16 beats | 2 in `sustain_mode`, else unset | Longest any strum rings, on every renderer. Without it the pattern renderer rings a strum at most one beat. |
| `push_pull`, `pocket_ms`, `timing_jitter_ms`, `velocity_humanize` | See [Shared timing](#shared-timing) | See Shared timing | One shared feel pass. |

Styles: `auto`, `straight_8s`, `chugs`, `syncopated`, `half_time`, `rock_riff`,
`pop_push`, `funk_chanks`, `jazz_comp`, `blues_shuffle`, `country_boom_chuck`,
`reggae_skank`, and `latin_clave`. The old rhythm `swing` and `groove` knobs did
nothing and were removed from presets; set the top-level groove instead.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `pattern` | Grid pattern string | Section-dependent | Grid pattern, including `gallop` and `syncopated`. |
| `style` | `chug` or unset | Unset | `chug` selects muted gallops. |
| `density`, `contrast` | 0.25-2; 0-1 | 1, 0.75 | Density multiplier (0.25-2) and section contrast (0-1). |
| `mute` | 0-1 | Section-dependent | Mute amount, 0-1. Direct `playstyle: pmute` also works. |
| `strum`, `strum_beats`, `strum_dir` | 0-1; nonnegative beats; `down`, `up`, `alt` | 0, derived, `down` | Strum amount, explicit spread in beats, and `down`/`up`/`alt`. |
| `retrigger` | `all`, `beat`, `bar`, `chord`, `accent`, `none` | Derived | `all`, `beat`, `bar`, `chord`, `accent`, or `none`. |
| `reattack_vel`, `reattack_dur`, `reattack_strum` | Nonnegative multipliers | 0.92, 0.75, 0.35 | Repeated-stroke velocity, duration, and spread multipliers. |
| `hit_strategy`, `stab_beats` | `auto`, `sustain`, `stabs`, `chops`, `chug`; positive beats | `auto`, derived | `auto`, `sustain`, `stabs`, `chops`, or `chug`; optional stab duration. |
| `voice_leading`, `voice_range_low`, `voice_range_high` | Boolean; MIDI pitches 0-127 | true, 40, 64 | Voicing movement and MIDI range. |

For `follow_hats`, `octave` defaults to 3, `density` to 1, and
`accent_syncopation` to true. Use `voicing: power_chord` or `triad` in its params.
These controls are specific to that renderer.

### Composed comping

Unless you pin a rhythm style, the composer writes the rhythm guitar. Each
song draws its own signature figures from an idiomatic vocabulary: dead-note
chucks, bass-string walks, sus4 hammer-ons, slid chords, boogie dyads, stabs,
and gallops. It arranges them so the verse, chorus, and bridge contrast.
Phrases walk up into the next phrase's chord, and the bar before a chorus
is stop-time. A walk only ever leads into a chord change: where the chord
holds, a riff's walking note becomes part of the previous gesture and a
phrase-end walk-up becomes root and fifth. The approach note is chromatic
unless it would rub a semitone against the chord it is played over; then
it is the scale tone below the target (B C into D over A minor, not C#).
Settings that choose a different part keep your choice: `style`,
`strum_style`, `sustain_mode`, `playstyle`, `pattern`, `play_pattern`,
`follow_hats`, `use_patterns`, `recipe`, `lock_to_riff`, and
`composer: false`. Feel settings shape the composed part instead:

| Setting | Effect on composed comping |
|---|---|
| `density` | Below 0.7, thins weak off-beat gestures. |
| `palm_mute` | Chance a plain strum becomes a palm-muted chug. |
| `chuck_rate` | Chance a light upstroke becomes a dead-note chuck. |
| `sustain_cut_rate` | Chance a strum is cut to a stab. |
| `voicing` | `power` or `octaves` plays power shapes throughout. |
| `register_min`, `register_max` | Shapes shift by octaves to fit. |
| `sustain_duration` | Longest any note rings, in beats. |
| `accent_strength`, `downbeat_boost`, `humanize_velocity` | Dynamics. |
| `strum_ms`, `humanize_timing`, `offset_beats`, `style_bias` | Timing and intensity. |

The shared timing controls (`push_pull`, `pocket_ms`, `timing_jitter_ms`,
`velocity_humanize`) apply to every renderer. The pattern and grid
renderers' own controls (`register` presets, `phrase_len_bars`,
`phrase_development`, `section_contrast`, `contrast`, `mute`, `strum`,
`strum_beats`, `strum_dir`,
`retrigger`, `hit_strategy`, `stab_beats`, the `reattack_*` multipliers,
`voice_leading`, `voice_range_low`, `voice_range_high`, `octave`,
`accent_syncopation`, and `vibrato_rate`) are unused by composed comping;
the build logs that they are unused and names `composer: false` as the way
to use them.

## Lead guitar controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `phrase_len_bars` | Integer >= 1 | persona | Motif length in bars, at least 1. Balanced: 2. |
| `rest_probability` | 0-0.85 | persona | Leave gaps in the lead and inform accompaniment planning. Balanced: 0.25. |
| `resolution_strength` | 0-1 | persona | Favor chord tones and stronger phrase endings. Balanced: 0.45. |
| `contour_style` | `stepwise`, `balanced`, `leaping` | persona | Choose the melodic contour. Balanced persona: `balanced`. |
| `theme_quote_rate` | 0-1 | 0.65 | Quote nearby theme pitches on eligible interior notes. Quotes adopt the theme's duration as well as its pitch. |
| `foreground` | `auto`, `full` | `auto` | `full`: the lead carries the melody (instrumental music). `auto`: the lead plays around a singer, with hooks, fills, counter-lines, and solos. Set per section or as a song-level default. |
| `composer` | Boolean | true | Per-section opt-out of the composer. The only lead setting that selects the legacy engine. |
| `ring_out` | 0-1 | 0.85 | How far a note rings into the silence after it. 0 cuts at the grid cell, 1 rings up to the next note. Staccato notes stay short. |
| `ring_max_beats` | 0.5 or more | 4 | Longest note that ring-out may create. |
| `vibrato_rate` | 0-1 | 0.65 | Chance a note held a beat or longer gets pitch-bend vibrato. |
| `bend_rate` | 0-1 | 0.15 | Chance a note is approached with a short bend-in from below. With the composer, 0.15 plays the composed bends as written, lower values keep that share of them (0 removes them), and higher values also bend untagged notes of half a beat or longer, up to all of them at 1. |
| `dive_rate` | 0-1 | 0.3 | Solo sections only. Chance a note held 1.5 beats or longer ends in a whammy dive of 7 to 14 semitones. The solo's final held note always dives when this is above 0. |
| `swell_rate` | 0-1 | 0.25 | Chance a note held 1.5 beats or longer fades in under a volume swell on CC11. |

Pitch expression is seeded and deterministic. Vibrato, bends, slides, and dives
are written as pitch-bend messages at export, and the writer widens the bend
range for a dive. Swells ride channel expression (CC11). Because pitch bend is
per channel, one note's expression moves anything else sounding on that channel.

Set `register` as a direct field or in `params`, as a preset name (`low`,
`mid`, `high`, `very_high`, or `full`, in any case) or a `[low, high]` MIDI
range in either order. Direct
`solo: true` or `role: lead` increases activity and permits wider motion.
Genre selects motif vocabulary; successive phrases develop that motif.
Use contour, rest probability, resolution, and intensity to shape the part.

With the composer on, your lead settings shape the composed line instead of
replacing it. `rest_probability` drops answers, developments, and fills (never
the hook, cadences, or the solo's structural moments). `contour_style` of
`stepwise` or `leaping` changes how leaps are weighed. `vibrato_rate`,
`bend_rate` (0 removes bends, above 0.15 adds them), `dive_rate`, and
`swell_rate` shape the expression, including zero values. A `seed` on the
lead (instrument or section) re-rolls the composed lead: its verse and
bridge ideas, its lick bank, and its phrase choices. The hook and its
answer stay the song's, because the melody guide, the acoustic melody, and
the arpeggiator share them; a section seed changes that section only. `phrase_len_bars`, `theme_quote_rate`,
`resolution_strength`, `ring_out`, and `ring_max_beats` tune only the legacy
generator: the build logs that they are unused and names `composer: false`
as the way to use them. Persona defaults never count as your choice; values
you set in a section's own `extra:` block always do. A numeric `register: [low, high]` is a hard MIDI-note range,
including solos; named presets retain their comfortable-range headroom.
Extremely narrow ranges can constrain authored pitches and melodic contour.

The rhythm guitar follows the same rule; see
[Composed comping](#composed-comping). Its feel settings (`density`,
`palm_mute`, `voicing`, `register_min`, `register_max`,
`accent_strength`, `chuck_rate`, `humanize_velocity`, `humanize_timing`,
`downbeat_boost`, `sustain_cut_rate`, `sustain_duration`, `strum_ms`,
`style_bias`, and `offset_beats`, as params or direct instrument fields)
shape the composed comping. Only the settings that choose a different part
(`style`, `strum_style`, `sustain_mode`, `playstyle`, `pattern`,
`play_pattern`, `follow_hats`, `use_patterns`, `recipe`, a nonzero
`lock_to_riff`, or `composer: false`) select the pattern or grid renderer.
A `register` preset (`low`, `mid`, `high`), `section_contrast`,
`phrase_len_bars`, `phrase_development`, and the other renderer-only
controls are logged as unused; use `register_min` and `register_max` to
place composed comping.

### The composer

With the composer on (the default), the lead is written from the song's DNA.
DNA selection uses the source section's actual key, mode, and meter. The
listener separately penalizes exposed dissonance according to metric position
and harmony, including held notes across changes. This heuristic does not
change the calibrated interval surprise targets.
Once per song it chooses a hook, an answer, a verse idea, a bridge idea, and
three signature licks, picking the most memorable candidates as heard over
your chorus and verse chords. Sections use phrase forms:

| Section | `foreground: full` | `foreground: auto` |
|---|---|---|
| Intro | Hook line | The guitar hook |
| Verse | An 8-bar period on the verse idea | Signature licks at phrase ends |
| Prechorus | A sequence climbing to a held dominant | Same |
| Chorus | Hook lines: state, answer, lift to a summit, close | The song's `chorus_form` around the singer, then the hook as a tag |
| Bridge | A contrasting idea ending on the dominant | A statement, then fills |
| Solo | The song's `solo_story`: climb, melodic, trade, or blues | Same |
| Outro | The hook, then a held tonic | Same |

Under a singer (`foreground: auto`) the chorus follows `chorus_form`.
`lift`: a counter-line climbs line by line to a summit before the tag (stabs
climb in their own voice; guide, octave and fill counters climb as a held
descant). `call`: the lead stays out of each two-bar vocal line and answers
it with one of the song's licks in the singer's held note or breath.
`anthem`: the lead harmonizes the chorus melody (the realized melody theme)
in thirds and sixths, moving with the singer. A pinned `counter` without a
pinned `chorus_form` keeps the plain counter-line.

A section type remembers its material. A returning chorus repeats note for
note while the chords match; the final chorus lifts and ornaments it; a
second verse keeps the melody with small rhythm changes. An authored melody
theme becomes the hook; its final chorus keeps the written notes and moves
the whole line up an octave when it fits (a named register may use the
solo's headroom, a numeric range is a hard bound). When the final chorus
changes key, the key change is the lift. When neither applies, held notes
get vibrato and each line slides into its first note, and the build log
says the octave did not fit. Earlier choruses always play the authored
notes.

Solo stories fill every two-bar unit. `climb` sequences the hook up the
neck to a climax lick; `melodic` sings the hook and its answer; `trade`
fills the lead's bar and plays a pickup out of the band's bar; `blues`
calls and answers in each unit, AAB across four-bar lines, starting from
the song's own licks. A later solo takes its licks further along the bank,
so it is not a replay. A solo straight after another continues it, without
a second hook statement and from higher up, and a solo followed by another
hands over on a held dominant instead of the solo ending.

With `foreground: full`, a country song's lead fills between its own phrases
with its licks (chicken picking, and third or sixth double stops when the
bank has them) at the `lead_fills` rate: the phrase's last bar keeps its
first half and cadence, and the fill answers in the second half. Other
genres fill this way only when `lead_fills` is pinned. `register` sets the melody range, and solos extend
it up to E6. `vibrato_rate`, `dive_rate`, and `swell_rate` still shape
expression; bends, slides, and staccato follow the composed techniques.
`solo: true` or `role: lead` makes any section a solo.

## Acoustic guitar controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `technique` | `fingerpicking`, `strumming`, `hybrid`, `percussive` | By section | Choose how the acoustic guitar plays. |
| `picking_pattern` | `travis`, `pima`, `broken_chord`, `waltz`, `roll`, `cinematic` | By section | Choose the fingerpicking sequence. |
| `melody_amount` | 0-1 | 0.72 picked/hybrid, otherwise 0 | Control how strongly the treble melody follows the guide. |
| `phrase_variation` | 0-1 | 0.35 | Omit or vary selected picked notes. |
| `voicing_style` | `open`, `barre`, `auto` | persona | Choose the chord shape. Engine fallback: `auto`. |
| `capo` | Integer 0-12 | 0 | Finger the chord shapes above a capo at this fret. The part still sounds in the song's key; the capo changes the shapes and their open-string ring. |
| `strum_density` | 0.05-1 | By section | Control how many eligible strums play. |
| `mute_ratio`, `body_tap_ratio` | 0-1 each | persona | Dampened strokes and body taps. Engine fallback: 0.08, 0. |
| `vel_variation` | Nonnegative velocity units | persona | Velocity-unit variation per hit. Engine fallback: 8. |
| `timing_variation` | Nonnegative quarter-note beats | persona | Timing variation in quarter-note beats. Engine fallback: 0.018. |

Intros, verses, bridges, and outros usually fingerpick; choruses strum;
prechoruses use hybrid playing; breakdowns use percussion. Personas can override these section defaults; the built-in `natural` persona
sets touch and voicing controls. A custom persona can also set technique. Treble melody notes follow the shared
guide while thumb notes and chord shapes remain playable. Barre shapes sit at
their lowest position above the capo (B as an A-form at fret 2), and a
picked melody reaches at most nine semitones above the shape and never
above A5 unless a high capo puts the shape itself there. Each string stops
before its next picked note. Body taps use short low MIDI notes.

## Arpeggiator controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `pattern` | `phrase`, `cinematic`, `ostinato`, `up`, `down`, `up_down` | `phrase` | Choose the note sequence. |
| `note_duration` | Quarter-note beats >= 0.125 | 0.5 | Quarter-note spacing, minimum 0.125; clipped at chord boundaries. |
| `rest_probability` | 0-0.65 | 0.08 phrase, 0 legacy | Rest chance, 0-0.65. Legacy patterns are `up`, `down`, and `up_down`. |
| `octave_range` | Integer 1-3 | 2 | Number of octaves, 1-3. |

`phrase` and `cinematic` rotate through up, up-down and down figures, and
the top note of each cycle follows the shared melody guide. `up`, `down`,
`up_down` and `ostinato` are fixed figures and play chord tones only. The
apex is the cycle's highest note whatever the figure (the middle of
`up_down`, the first note of `down`). Chords are spelled from the harmony's
numerals, sevenths and extensions included: `6`, `69`, `9`, `add9`, `b9`,
`#9`, `11`, `#11`, `13`, `b13` and `7b5`; extensions are voiced above the
octave. Velocity follows the instrument's intensity, or the section's
(with its type level and the rise on repeats): about 65 at 0.5, 93 at 0.9
and 100 at 1, with accented bass notes and strong beats. See
[file structure](#file-structure) to enable it in a section.

### Every song its own band

Each song draws its own drummer (kick patterns, what the hands play per
section, backbeat or half-time, ghost notes, fills, crash habits, and a
feel: straight, laid back, pushing, or shuffle), its own rhythm-guitar
figures, a signature riff for riff-driven songs, and its own licks. It also
draws arrangement habits every part agrees on. Pin any of them with
`song.arrangement_style`:

```yaml
song:
  arrangement_style:
    into_chorus: build       # stop | build | fill | push | drop
    phrase_fill: walkup      # walkup | slide | rake | none
    intro: riff_alone        # full | riff_alone
    riff_driven: true        # verses, intro and outro ride a signature riff
    bass_doubles: true       # the bass doubles the riff an octave down
    comp_activity: sparse    # busy | normal | sparse (drawn per song)
    solo_story: melodic      # climb | melodic | trade | blues
    solo_ending: hold        # dive | hold | trill | slide_off
    counter: stabs           # guide | octaves | stabs | fills (lead under a singer)
    chorus_form: anthem      # lift | anthem | call (with or without a singer)
    lead_fills: sparse       # sparse | normal | chatty
    ending: big              # ring | cold | big
    country_style: outlaw    # honky_tonk | bakersfield | outlaw | two_step | ballad | country_rock
```

`country_style` applies to country songs. Without a pin, a genre name
that names the style chooses it (`outlaw_country`, `country_rock`,
`honky_tonk`, `bakersfield`, `texas_country`, `country_ballad`); plain
`country` draws one per song. In 3/4, each country song also draws its
own waltz band: bass on 1 with its own ring length, fifths and walks,
guitar answering on 2 and 3 with its own figure, and a drummer with its
own snare or cross-stick touch and timekeeper.

`comp_activity` is how busy the rhythm guitarist is, drawn per song
(roughly 3 busy, 5 normal, 2 sparse in rock; funk leans busy) and pinned
here. `busy` plays the full figure every bar. `normal` alternates a
signature-riff statement with a bar whose tail rests; a doubling bass plays
that tail alone, so the riff answers itself across the band. `sparse`
repeats the body for three bars, then answers on bar four; it spaces added
phrase fills eight bars apart and reserves slides for phrase gestures
outside bridges. Section transitions and endings keep their selected
devices. In every mode, signature riffs are chosen to lock with the
composed drummer: accents in unison with the kick or snare score up, and
an accent a sixteenth off the backbeat is ruled out when any candidate
avoids it. Riff power moves that would ring against a held lead note a
semitone or tritone away are choked to a stab. Explicit drum patterns are
not inferred or rewritten.

In band sections (drums and a guitar) the bass plays a per-song role for
each section: the engine's line, the song's kick pattern, root eighths,
octaves, a gallop, or held roots, each with the song's own variations.
`rhythm_pattern`, `walking`, `lock_to_kick`, `lock_to_riff`, a motif
quote, a walking persona, or an authored `bass_motif` keep the engine's line.
Those choices also take precedence over automatic `bass_doubles`.
The bass register (yours, else the recipe's or persona's) applies after
composed roles and doubling, and `articulation_style` plays composed notes
too: slap turns beats into thumb hits and octave or offbeat notes into
pops, mute and pick shorten them.

Where the composed drummer plays a section, the bass plays the song's
devices with it, whatever line it plays. Into a chorus: `stop` hits the
downbeat with the band and rests, `drop` drops out for the bar, `push`
anticipates the chorus with the band's hit on the last eighth, `fill`
leaves the last beat to the drum fill, and `build` drives root eighths that
swell into the chorus. At the song's end the bass stops with a `cold`
ending, hits and holds for a `big` one, and holds the root under a `ring`.
A drum part you configured yourself plays straight through these bars, and
so does the bass.

A riff-alone intro needs a guitar to play the riff alone (rhythm or
acoustic guitar in the intro; a lead guitar does not count). With one, the
composed drums and the bass wait out the first half of the intro together.
Without one, or when you configured the drums yourself, the whole band
plays the intro from the top.

The drums are composed unless their params set `voices`, `recipe`,
`pattern`, or `riff_accent_rate`, the section sets `intent`, or a
`drum_groove` theme exists; `composer: false` on the drums also keeps the
drum engine. `ghost_rate`, `fill_rate`, `kick_density`, and `hat_density`
shape the composed drummer in every section: `hat_density` 0.3 or less puts
the hands on quarter notes (dotted quarters in 6/8 and 12/8) and 0.8 or more
on sixteenth-note hats; `kick_density` 0.3 or less keeps the kick on 1 and 3
and 0.7 or more adds an offbeat kick to every beat without a backbeat.
The song's feel applies only when you set no
`swing`, `push_pull`, `timing_jitter_ms`, groove block swing, or song
`humanize_timing`. A `seed` on an instrument or section re-rolls that
part's drummer, comp figures or lead (the lead keeps the song's hook).

Jazz and swing songs get a swing drummer: the ride on every beat with skip
notes on the swung "and" (spang-a-lang, or the jazz waltz's 1, 2&, 3), the
hi-hat foot on 2 and 4 (on 2, on 3, or on 2 and 3 in 3/4), a feathered kick on
every beat with the odd bomb, and the left hand comping quietly between the
beats. Each song draws its own ride figures per section, comping density and
placement, foot, feathering and bombs; `hat_density` moves the ride to plain
quarters or skip notes on every beat. Dance, dance-pop, electronic, techno,
house, disco and EDM songs get a four-on-the-floor drummer: the kick on every
beat, the song's hat figure on the offbeats, clap or snare (or both) on 2 and
4, a percussion layer (shaker, tambourine, cowbell or a chorus ride), intros
that bring the kit in by halves, bridges and breakdowns without the kick (or
at half time), and phrase ends that roll or drop the kick. A prechorus can
build by itself from quarters to sixteenths, and the kick sits out the last
beat before a chorus.

The drums play the `into_chorus` device too: `build` is a snare roll that
rises from eighths to sixteenths over the last bar or two (each song draws
the length), distinct from `fill`. Drums alone keep the backbeat in every
bar and answer on the toms on the last beat of bars 2 and 4 of each phrase.

### Bass hook responses

`hook_response: true` in the bass params (off by default) lets the bass answer
the composed lead. When the lead holds or breathes for 1.25 to 4 beats after
a phrase, the bass fills that hole with the hook's opening rhythm and
contour, over the current chord, starting on a nearby kick and landing on a
chord tone. It answers once per 4-bar phrase and at a section's close; the
groove plays everywhere else. Across six example songs, responses made up
14% of bass notes and cut simultaneous lead and bass attacks by 6%, at a cost
of 2% groove repetition and 6% kick alignment.

`hook_response: develop` uses the same windows but rotates the hook opening,
hook tail and answer motif. The rotation advances with returning section types.
Authored degree/accidental contours are retained relative to the current chord.
Bass `register_low` and `register_high` constrain responses. A very narrow range
may require clamping a pitch when no octave equivalent fits. Neither `true` nor
`develop` is enabled by genre defaults.

Compound shuffle riffs keep dotted-quarter group starts through shared swing.
Generated ideas rephrase for a section's meter/grouping; authored themes keep
their written rhythms. Section settings override global settings even when one
uses a config field and the other uses nested params. Composed rhythm honors
`humanize_timing`, `strum_ms`, octave voicing and explicit register bounds through
its final gestures. The three-tier selector/shaping/legacy rule is unchanged.

Recipe chord rates are bar-relative unless explicitly overridden. A short
section uses a recipe's prefix, so a four-bar blues verse may remain on the
tonic. Use 12 bars for the full form or supply an explicit short progression.

## Groove memory

Engines draw each bar fresh, so without help a bass line or drum beat never
settles. With `song.groove_memory` on (the default), drums, bass, rhythm
guitar, and acoustic guitar get a bar form. In each 4-bar phrase, the first
three bars restate the section's most typical bar. The fourth keeps the
engine's own fill, turnaround, or variation. Funk, reggae, Latin, soul, R&B,
hip-hop, disco, and ska use a two-bar groove.

Restated notes follow the chords and keep their role: a third stays a third,
and approach notes aim at the next chord. A restated bass bar starts on the
root, unless the engine drew a fifth drop (`fifth_jump_rate`) for that bar.
Restated pitches stay inside the bass register. Bars the engine left silent
stay silent. A returning section type brings back its groove at the new
dynamics. A clear intensity lift, such as a final chorus, plays its own
groove instead. Parts that quote a riff or motif theme, walking bass lines,
and soloing parts are left alone.

| Key (instrument params) | Range or values | Default | What it does |
|---|---|---|---|
| `groove_memory` | Boolean | true | Per-instrument opt-out. |
| `groove_cycle_bars` | 1 or 2 | Genre | Groove length in bars. |

## Transitions

Set `song.params.transitions` for arrangement defaults. An instrument's
`params.transitions` replaces the whole settings object for that instrument.
Include every setting you want to keep.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `enabled` | Boolean | true | Enable transition planning. |
| `strength` | Normally 0-1 | 0.5 | Set how strongly transitions stand out. |
| `ramp_bars` | 0-2 bars | 1 | Energy-ramp length, clamped to 0-2 bars. |
| `pickup_rate` | 0-1 | 0.35 | Set the chance of a planned pickup. |
| `turnaround_rate` | 0-1 | 0.25 | Set the chance of a planned turnaround. |
| `bridge_start_bars` | 0-2 bars | 1 | Bridge introduction length in the bridge's meter, clamped to 0-2 bars. The composed drummer's bar keeps every hit; engine drums thin only hand timekeeping, never the kick, backbeat or crash. |
| `debug` | Boolean | false | Detailed transition logging. |

Drum `pickup_rate` and `downbeat_rate` are separate performance controls.
Energy rises favor longer pickups; drops leave more space. Fills are built
on the meter's grid before swing and humanization.

## Export controls

`exports.mode` selects `daw` (default), `minimal`, `debug`, or `custom`.
DAW mode writes the full song, stems, sections, patterns, and index. Minimal
writes only the full song. Debug also enables analysis views. Custom starts
from DAW defaults and accepts these switches:

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `write_full_song` | Boolean | true | Write the combined MIDI. |
| `write_stems` | Boolean | true | Write an entire-song MIDI for each instrument. |
| `write_sections` | Boolean | true | Write per-occurrence instrument clips. |
| `write_patterns` | Boolean | true | Write deduplicated patterns and sequences. |
| `write_index` | Boolean | true | Write `index.yaml` and `QUICKREF.txt`. |
| `write_analysis` | Boolean | false | Enable text analysis using the selected views. |

The CLI skip flags can disable section or pattern exports in any mode.
Select text views with `midi_text.views`; the legacy `write_grids` flag does
not independently control the current text-dump writer.

```yaml
exports:
  midi_text:
    enabled: true
    views: [events, grid, tab]
    subdiv: 16
```

`events` writes TSV note data, `grid` writes a text piano roll, and `tab` writes
available guitar tablature. `subdiv` is display steps per bar, commonly 8, 12,
16, or 32; it does not change performance timing. Sixteen display steps mean
sixteenth notes only in 4/4. Pattern controls live under `song`.

The text views still use the song's bar grid for bar/beat labels, including
sections with another meter. For mixed-meter DAW markers, use `QUICKREF.txt`
or `index.yaml`; for precise event positions, use `start_beat_abs`. MIDI time
signatures and note timing use each section's actual meter.

Instrument fields also include `enabled`, `intensity`, `seed`, `variation`,
`style_bias`, `offset_beats`, `register`, `solo`, `role`, `persona`, `recipe`,
`genre`, `voicing`, and `playstyle`. Support for the last two, offsets, and style
bias is engine-specific. Configure MIDI `channel`, `program`, `priority`,
`enabled`, `requires`, `provides`, and `roles` in the top-level `engines`
block, not instrument params:

```yaml
engines:
  lead_gtr: {program: 40}    # violin
  bass: {program: 42}        # cello
```

Each field overrides the built-in registry; unset fields keep their
defaults. Older configs that put these fields on a global `instruments:`
entry still work. When both blocks set the same field, `engines` wins and
the build logs a warning. On a section's instrument they have no effect,
and the build says so. See the [engine guide](../produzre/engine/ENGINES.md).

The build also logs a warning for any instrument param no built-in engine
reads (a typo or a setting from another instrument), naming the key, where
it was set, and the closest known keys. The part still builds; the
setting is ignored. `produzre validate` reports the same lines.

## Working from a musical description

Start with tempo, key, genre, section order, and the instruments that should
play. Then adjust only what you hear. For a quieter verse, lower its intensity
or remove an instrument. For walking bass, use the walking persona (any
genre) or `rhythm_pattern: walking`. For a repeated hook, author a melody theme. For a heavy chorus, try
picked bass, a chugging guitar pattern, and fewer rests.

Use [the examples](../examples/README.md) for complete arrangements, including
rock, funk, acoustic jazz, and theme demonstrations. See
[DETERMINISM.md](../DETERMINISM.md) for seed overrides and project sharing.

Groove recall compares top-level instrument settings as well as nested params.
Changing a register, seed, variation, or playing configuration starts a new
memory identity. Intensity remains separate, allowing dynamics to scale a
recalled groove. Nested configuration order does not affect this identity.
