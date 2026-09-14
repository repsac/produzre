# Rhythm guitar examples

- [strum-style-comparison.yaml](strum-style-comparison.yaml): compare `strum_style: balanced`, `downbeat_heavy`, and `upbeat_heavy` with the same intensity and progression.
- [sustained-chords-demo.yaml](sustained-chords-demo.yaml): sets legacy `sustain_duration` from 0.5 to 4 beats; set `use_patterns: false` to hear those controls because its pop recipe selects patterns.

```bash
python produzre_entry.py build examples/rhythm_gtr/strum-style-comparison.yaml
python produzre_entry.py build examples/rhythm_gtr/sustained-chords-demo.yaml
```

## Choose a renderer and pattern

Genre recipes normally select the pattern renderer. Set `use_patterns: true`
when choosing its controls yourself. Try `chugs` for muted repeated strokes,
`straight_8s` for regular strumming, or `syncopated` for displaced accents.
Genre patterns include `funk_chanks`, `jazz_comp`, `reggae_skank`, and
`country_boom_chuck`.

```yaml
# Inside an instruments block:
rhythm_gtr:
  params:
    use_patterns: true
    style: chugs
    voicing: power
    density: 0.8
    palm_mute: 0.7
```

The legacy renderer has separate grid and sustain controls, including its
singular `chug` style. `follow_hats: true` selects another path when drum
features are available. Do not mix controls from these paths without checking
the [rhythm guitar reference](../../docs/llm-song-config-reference.md#rhythm-guitar-controls).
It lists their complete parameters and defaults.

## Shape the part

`density` changes the number of eligible strokes. `strum_style` moves velocity
emphasis toward downbeats or upbeats. `phrase_len_bars` controls the phrase
cycle; phrase endings can add answers or cadential cuts.

Use `power`, `triad`, `shell`, or `octaves` for voicings. `palm_mute` shortens
muted strokes, `chuck_rate` adds dead strokes, and `sustain_cut_rate` adds
shortened attacks. `strum_ms` spreads the strings in milliseconds. Set it to
zero for simultaneous chord notes.

Pattern `register` can be low, mid, or high. See [theme controls](../../docs/llm-song-config-reference.md#themes)
for riff accents. The accompaniment also leaves room in planned lead windows.

The personas are tight, loose, aggressive, funky, and jangly. See the [preset order](../../docs/llm-song-config-reference.md#recipes-and-personas)
when combining them with recipes or explicit params, or try the
[persona examples](../personas/README.md).

Set swing in the shared `groove` block. The old rhythm-guitar `swing` and
`groove` params were unused and have been removed from presets.
