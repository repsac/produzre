# Acoustic guitar examples

- [style-comparison.yaml](style-comparison.yaml): hear `travis` fingerpicking, strumming at `strum_density: 0.75`, a `broken_chord` hybrid, and percussion at `body_tap_ratio: 0.35` in four sections.

```bash
python produzre_entry.py build examples/acoustic_gtr/style-comparison.yaml
```

## Choose a technique

Fingerpicking plays individual strings. Strumming spreads chord attacks.
Hybrid combines the two. Percussive playing adds muted notes and body taps.

| Picking pattern | Character |
|---|---|
| `travis` | Alternating thumb and treble fingers. |
| `pima` | A classical thumb/index/middle/ring sequence. |
| `broken_chord` | Chord tones played in order. |
| `waltz` | A three-quarter pattern. |
| `roll` | Continuous rolling notes. |
| `cinematic` | Spaced thumb notes and a moving treble line. |

`melody_amount` controls how strongly treble notes follow the shared melody
guide. The thumb follows the chord voicing. `phrase_variation` introduces
omissions and small changes. Each physical string stops before its next note.

## Shape the performance

`voicing_style` chooses open, barre, or automatic shapes. `capo` raises the
shape by a fret count. `strum_density` changes strum activity, while
`mute_ratio` and `body_tap_ratio` control damped notes and percussion.

Use instrument `intensity` for overall dynamics. `vel_variation` is measured
in MIDI velocity units; `timing_variation` is measured in quarter-note beats.
Set either to zero when comparing exact patterns.

```yaml
# Inside an instruments block:
acoustic_gtr:
  intensity: 0.6
  params:
    technique: fingerpicking
    picking_pattern: travis
    voicing_style: open
    melody_amount: 0.7
    vel_variation: 10
    timing_variation: 0.015
```

The personas are natural, precise, expressive, percussive, and delicate.
Their settings can replace section-derived technique defaults. See
[personas](../personas/README.md) and the
[acoustic reference](../../docs/llm-song-config-reference.md#acoustic-guitar-controls)
for precedence, ranges, and defaults.
