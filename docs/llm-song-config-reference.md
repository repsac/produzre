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

Every internal beat is a quarter note. A bar lasts 4 beats in 4/4, 3 in 3/4 or
6/8, 3.5 in 7/8, and 5 in 5/4. The drum grid has four steps per quarter note.
6/8 groups eighth notes into two dotted-quarter pulses; it does not use the
3/4 backbeat. A section `meter` overrides the song meter. Full-song MIDI and
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
Later values win, including explicit zero. Recipes are selected by genre,
section type, tempo, and section meter. An explicit instrument `recipe` wins
over automatic selection. A section instrument `genre` overrides the global
instrument genre, which overrides `song.genre`.

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
`walking` favors quarter notes. `funk` bass uses slap articulation. `jangly`
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
explicitly set. The global groove overrides persona and recipe swing. Without
a global groove, the resolved drum recipe supplies the band's swing, including
sections where drums are silent. True triplet attacks are not swung again.
Drum fills and pickups follow the same clock.

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
| `role` | `melody`, `riff`, `bass_motif` | `melody` | Choose the theme's musical role. |
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
| `bass.params.lock_to_riff` | 0-1 | 0 | Probability of quoting each realized bass-motif note, falling back to riff. Quoted pitches replace generic notes in that interval. |
| `rhythm_gtr.params.lock_to_riff` | 0-1 | 0 | Probability of adding a riff onset to the accent targets. Chords retain their own voicings. |
| `drums.params.riff_accent_rate` | 0-1 | 0 | Probability of adding a kick at a riff onset. Grid, backbeat spacing, and limb constraints still apply. |
| `drums.params.riff_accent_boost` | Nonnegative multiplier | 1 | Velocity multiplier for existing kick/snare accents near riff onsets. |
| `lead_gtr.params.theme_quote_rate` | 0-1 | 0.65 | Probability of quoting a nearby melody-theme pitch on eligible interior notes. |

Bass, drums, and rhythm guitar require explicit coupling. Lead guitar, acoustic
melody, and the phrase arpeggiator use the shared melody guide automatically.
`grid`, MIDI `source`, drum-groove themes, and section-local theme blocks are not
implemented. Unsupported keys inside a theme raise an error.

## Bass controls

The descriptions retain values from the built-in `tight` persona and label
engine fallbacks. A recipe can replace them. Rates are probabilities in 0-1.

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `density` | 0-1 | persona | Keep more or fewer eligible rhythm slots. Tight: 0.7. |
| `rest_rate` | 0-1 | persona | Remove selected notes to leave gaps. Tight: 0. |
| `rhythm_pattern` | `anchor`, `push`, `drive`, `syncopated`, `rock_riff`, `funk_16ths`, `walking` | persona | Choose the bass attack pattern. Tight: `anchor`. |
| `articulation_style` | `finger`, `pick`, `slap`, `mute` | persona | Change attack, length, and pattern bias. Tight: `finger`. |
| `register_low`, `register_high` | MIDI pitches 0-127 | persona | Inclusive MIDI pitch limits. Tight: 28, 52. |
| `approach_rate`, `chromatic_rate` | 0-1 each | persona | Approach-note probability and chromatic choice. Approaches occur before chord changes. Tight: 0, 0. |
| `max_passing_per_bar` | Integer >= 0 | persona | Passing-note limit per bar. Tight: 0. |
| `root_bias` | 0-1 | 0.65 engine fallback | Chance of including the root among interior chord-tone candidates. |
| `octave_jump_rate`, `fifth_jump_rate`, `pedal_rate` | 0-1 each | persona | Octave changes, fifths at chord changes, and held pitch across chords. Tight: 0, 0, 0. |
| `motion_style` | `stepwise`, `leaping`, `mixed` | `stepwise` | Choose how the bass moves between pitches. |
| `lock_to_kick`, `lock_to_snare`, `lock_to_hat` | 0-1 each | persona | Add notes at kick, accent, or top-cymbal attacks. Zero disables that source. Tight: 0.8, 0, 0. |
| `lock_to_kicks` | Boolean | false | Alternate renderer based on drum kick attacks. Distinct from the probability above. |
| `avoid_fills`, `octave` | Boolean; integer octave | true, 2 | Fill avoidance and starting octave in the alternate kick-locked renderer. |
| `lock_to_riff` | 0-1 | 0 | Theme quotation; see Themes. |
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
| `ride.bell_rate` | 0-1 | 0 | Ride-bell chance, default 0. |
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
| `sustain_mode`, `sustain_duration` | Boolean; 0.1-16 beats | false, 2 | Held chords and maximum sustain in beats (0.1-16). |
| `strum`, `strum_beats`, `strum_dir` | 0-1; nonnegative beats; `down`, `up`, `alt` | 0, derived, `down` | Strum amount, explicit spread in beats, and `down`/`up`/`alt`. |
| `retrigger` | `all`, `beat`, `bar`, `chord`, `accent`, `none` | Derived | `all`, `beat`, `bar`, `chord`, `accent`, or `none`. |
| `reattack_vel`, `reattack_dur`, `reattack_strum` | Nonnegative multipliers | 0.92, 0.75, 0.35 | Repeated-stroke velocity, duration, and spread multipliers. |
| `hit_strategy`, `stab_beats` | `auto`, `sustain`, `stabs`, `chops`, `chug`; positive beats | `auto`, derived | `auto`, `sustain`, `stabs`, `chops`, or `chug`; optional stab duration. |
| `voice_leading`, `voice_range_low`, `voice_range_high` | Boolean; MIDI pitches 0-127 | true, 40, 64 | Voicing movement and MIDI range. |

For `follow_hats`, `octave` defaults to 3, `density` to 1, and
`accent_syncopation` to true. Use `voicing: power_chord` or `triad` in its params.
These controls are specific to that renderer.

## Lead guitar controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `phrase_len_bars` | Integer >= 1 | persona | Motif length in bars, at least 1. Balanced: 2. |
| `rest_probability` | 0-0.85 | persona | Leave gaps in the lead and inform accompaniment planning. Balanced: 0.25. |
| `resolution_strength` | 0-1 | persona | Favor chord tones and stronger phrase endings. Balanced: 0.45. |
| `contour_style` | `stepwise`, `balanced`, `leaping` | persona | Choose the melodic contour. Balanced persona: `balanced`. |
| `theme_quote_rate` | 0-1 | 0.65 | Quote nearby theme pitches on eligible interior notes. |

Use direct `register: low`, `mid`, `high`, `very_high`, or `full`. Direct
`solo: true` or `role: lead` increases activity and permits wider motion.
Genre selects motif vocabulary; successive phrases develop that motif.
Use contour, rest probability, resolution, and intensity to shape the part.

## Acoustic guitar controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `technique` | `fingerpicking`, `strumming`, `hybrid`, `percussive` | By section | Choose how the acoustic guitar plays. |
| `picking_pattern` | `travis`, `pima`, `broken_chord`, `waltz`, `roll`, `cinematic` | By section | Choose the fingerpicking sequence. |
| `melody_amount` | 0-1 | 0.72 picked/hybrid, otherwise 0 | Control how strongly the treble melody follows the guide. |
| `phrase_variation` | 0-1 | 0.35 | Omit or vary selected picked notes. |
| `voicing_style` | `open`, `barre`, `auto` | persona | Choose the chord shape. Engine fallback: `auto`. |
| `capo` | Integer 0-12 | 0 | Raise chord shapes by this many frets. |
| `strum_density` | 0.05-1 | By section | Control how many eligible strums play. |
| `mute_ratio`, `body_tap_ratio` | 0-1 each | persona | Dampened strokes and body taps. Engine fallback: 0.08, 0. |
| `vel_variation` | Nonnegative velocity units | persona | Velocity-unit variation per hit. Engine fallback: 8. |
| `timing_variation` | Nonnegative quarter-note beats | persona | Timing variation in quarter-note beats. Engine fallback: 0.018. |

Intros, verses, bridges, and outros usually fingerpick; choruses strum;
prechoruses use hybrid playing; breakdowns use percussion. Personas can override these section defaults; the built-in `natural` persona
sets touch and voicing controls. A custom persona can also set technique. Treble melody notes follow the shared
guide while thumb notes and chord shapes remain playable. Each string stops
before its next picked note. Body taps use short low MIDI notes.

## Arpeggiator controls

| Key | Range or values | Default | What it does |
|---|---|---|---|
| `pattern` | `phrase`, `cinematic`, `ostinato`, `up`, `down`, `up_down` | `phrase` | Choose the note sequence. |
| `note_duration` | Quarter-note beats >= 0.125 | 0.5 | Quarter-note spacing, minimum 0.125; clipped at chord boundaries. |
| `rest_probability` | 0-0.65 | 0.08 phrase, 0 legacy | Rest chance, 0-0.65. Legacy patterns are `up`, `down`, and `up_down`. |
| `octave_range` | Integer 1-3 | 2 | Number of octaves, 1-3. |

The phrase pattern follows the shared melody guide. See [file structure](#file-structure) to enable it in a section.

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
| `bridge_start_bars` | 0-2 bars | 1 | Bridge introduction length, clamped to 0-2 bars. |
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
`enabled`, `requires`, `provides`, and `roles` in the `engines` registry, not
instrument params. See the [engine guide](../produzre/engine/ENGINES.md).

## Working from a musical description

Start with tempo, key, genre, section order, and the instruments that should
play. Then adjust only what you hear. For a quieter verse, lower its intensity
or remove an instrument. For walking bass, use the walking persona and a jazz
recipe. For a repeated hook, author a melody theme. For a heavy chorus, try
picked bass, a chugging guitar pattern, and fewer rests.

Use [the examples](../examples/README.md) for complete arrangements, including
rock, funk, acoustic jazz, and theme demonstrations. See
[DETERMINISM.md](../DETERMINISM.md) for seed overrides and project sharing.
