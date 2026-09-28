# Solo bass

Full pieces for bass guitar alone. Bass roles only run in band sections
(drums plus a guitar), so a bass by itself always plays the bass engine's
own line and every setting in these files is heard directly.

| File | Style | What it shows |
|---|---|---|
| `funk-slap-bass.yaml` | E dorian funk, 100 BPM | Funk persona and slap articulation: thumb, pops and ghosted dead notes, the two-bar `funk_16ths` cell repeated as a motif in the verses, a busier `syncopated` chorus with fifth jumps, and a `solo: true` section with a wider register and octave leaps |
| `jazz-walking-bass.yaml` | Bb swing, 160 BPM | The walking persona over ii-V-I and iii-VI-ii-V changes: a quarter note on every beat, each chord's root on its downbeat and a scale or half step into the next chord (`chromatic_rate` sets the share of half steps), a two-feel intro and a swung bass solo |
| `melodic-finger-bass.yaml` | D major pop ballad, 84 BPM | Finger articulation with slides and vibrato (pitch bend), a different rhythm pattern for each part of the form (walking, push, syncopated), octave jumps, diatonic fills and a high melodic solo |

## Build

```bash
python produzre_entry.py build examples/bass/solo/funk-slap-bass.yaml
```

Look in `analysis/bass/` of the export for the events table, grid and
tablature. The event `kind` column names what the engine chose for each
note (root, third, approach, slap pop, fill and so on).

## Notes

- Each section includes `harmony: {}`, which gives the bass the chords.
- `solo: true` on a section switches the bass to its solo mode: it uses
  `solo_density` and raises the ceiling to `solo_register_high`.
- A walking line (the walking persona, or `rhythm_pattern: walking`) sounds
  every beat, so `density`, `rest_rate`, fills, slides and vibrato do not
  apply to it; `chromatic_rate` and the register do.
- `rhythm_pattern: anchor` plays beats 1 and 3 (the jazz piece's two-feel
  intro); lower densities fall back toward one note a bar.
