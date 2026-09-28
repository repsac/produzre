# Rhythm guitar examples

The rhythm guitar is composed by default. Each song draws its own figures
from an idiomatic vocabulary (dead-note chucks, bass-string walks, sus4
hammer-ons, slid chords, boogie dyads, stabs, gallops), gives each a
personal variation, and arranges them so verse, chorus and bridge
contrast. Phrases walk or slide into the next phrase's chord (a walk only
ever leads into a chord change; where the chord holds, it plays root and
fifth instead), and the bar before a chorus follows the song's way into it. The build log names each figure:

```text
[INFO] Composer: verse rhythm guitar plays 'gen_low:r---x-u-r-a-x-u-'
```

```bash
python produzre_entry.py build examples/rhythm_gtr/comp-feel-demo.yaml
```

## Composed comping

- [comp-feel-demo.yaml](comp-feel-demo.yaml): the same composed verse figure with `density`, `palm_mute`, `chuck_rate`, `sustain_cut_rate` and `voicing: power` changed one at a time.
- [riff-demo.yaml](riff-demo.yaml): a riff-driven song with a doubling bass and `comp_activity: normal`, so the bass plays the riff's tail alone every other bar.

Feel settings shape the composed part per section:

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

Song habits, pinned with `song.arrangement_style`
([reference](../../docs/llm-song-config-reference.md#every-song-its-own-band)):
`riff_driven` (verses, intro and outro ride a signature riff that locks
with the drummer's kick and snare), `bass_doubles`, `comp_activity`
(`busy`, `normal`, `sparse`: how often the riff plays its tail and how
often fills and slides appear), `phrase_fill` (`walkup`, `slide`, `rake`,
`none`) and `into_chorus` (see the
[drum transitions](../drums/TRANSITIONS.md), which the guitar plays too).
A rhythm guitar `seed` re-rolls its figures.

## The classic engine

Settings that choose a different part hand the section to the classic
engine: `style`, `strum_style`, `sustain_mode`, `playstyle`, `pattern`,
`play_pattern`, `follow_hats`, `use_patterns`, `recipe`, a nonzero
`lock_to_riff`, and `composer: false`.

- [classic-engine-demo.yaml](classic-engine-demo.yaml): `composer: false` with pattern styles (`straight_8s`, `chugs`, `pop_push`, `half_time`, `syncopated`), `strum_style`, `phrase_len_bars` and `section_contrast`.

`phrase_len_bars`, `phrase_development`, `section_contrast` and the other
pattern and grid controls (`mute`, `strum`, `retrigger`, `hit_strategy` and
so on) tune only the classic engine; with composed comping the build log
lists them as unused. `sustain_duration` caps how long any strum rings on
every renderer, and `sustain_mode` plays held chords on the classic engine.
The classic engine's other controls, including its grid renderer
(`use_patterns: false`) and `follow_hats`, are in the
[rhythm guitar reference](../../docs/llm-song-config-reference.md#rhythm-guitar-controls).

Rhythm guitar personas (tight, loose, aggressive, funky, jangly) move the
composed part's timing against the beat; see the
[persona examples](../personas/README.md). Set swing in the shared `groove`
block, not on the guitar.
