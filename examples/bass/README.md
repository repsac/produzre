# Bass examples

Start with [baseline/baseline-demo.yaml](baseline/baseline-demo.yaml). Then
compare the articulation files with the same sound patch. Finger, pick, slap,
and mute alter note length, velocity, and note choices.

```bash
python produzre_entry.py build examples/bass/baseline/baseline-demo.yaml
```

## Find a comparison

| Folder | Listen for |
|---|---|
| `articulation` | Finger, pick, slap, and muted note lengths. |
| `rhythm` | Anchor, push, drive, and syncopated attack patterns. |
| `techniques` | Diatonic/chromatic approaches and walking lines. |
| `grooves` | Pedal tones, octave jumps, fifth drops, and combinations. |
| `fills` | Sparse, pocket, and funk fills. |
| `slap` | Thumb, pop, and ghost activity. |
| `advanced` | Featured bass, motion styles, and register changes. |
| `baseline` | Chord changes, minor harmony, and coordination. |

### Baseline

- [baseline/baseline-demo.yaml](baseline/baseline-demo.yaml): compare verse intensity 0.7 with chorus intensity 0.85 over two E dorian progressions.
- [baseline/chord-changes-demo.yaml](baseline/chord-changes-demo.yaml): follow the tight bass through `I IV V I` in C major at 100 BPM.
- [baseline/chord-changes-minor.yaml](baseline/chord-changes-minor.yaml): follow the same persona through `i VI iv V` in A minor at 100 BPM.
- [baseline/negotiation-baseline.yaml](baseline/negotiation-baseline.yaml): hear bass alone at intensity 1.0 and `density: 0.8`; there are no drums to trigger its kick locking.

### Articulation

- [articulation/style-finger.yaml](articulation/style-finger.yaml): hear `articulation_style: finger` with the pocket persona and `density: 0.8`.
- [articulation/style-mute.yaml](articulation/style-mute.yaml): hear `articulation_style: mute` with the tight persona and `rest_rate: 0.2`.
- [articulation/style-pick.yaml](articulation/style-pick.yaml): hear `articulation_style: pick` with the metal persona and `density: 0.9`.
- [articulation/style-slap.yaml](articulation/style-slap.yaml): hear `articulation_style: slap` with the funk persona and syncopated attacks.

### Rhythm

- [rhythm/rhythm-anchor.yaml](rhythm/rhythm-anchor.yaml): hear `rhythm_pattern: anchor` at density 1.0 with no added rests.
- [rhythm/rhythm-drive.yaml](rhythm/rhythm-drive.yaml): hear `rhythm_pattern: drive` at density 0.7 with the metal persona.
- [rhythm/rhythm-push.yaml](rhythm/rhythm-push.yaml): hear `rhythm_pattern: push` at density 0.8 with the tight persona.
- [rhythm/rhythm-syncopated.yaml](rhythm/rhythm-syncopated.yaml): hear `rhythm_pattern: syncopated` at density 0.6 with the funk persona.

### Techniques

- [techniques/passing-chromatic.yaml](techniques/passing-chromatic.yaml): hear chromatic approaches with `approach_rate: 0.8`, `chromatic_rate: 0.4`, and up to three passing notes per bar.
- [techniques/passing-diatonic.yaml](techniques/passing-diatonic.yaml): hear diatonic approaches with `approach_rate: 0.8` and `chromatic_rate: 0`, compared with both at 0 in `passing-none`.
- [techniques/passing-none.yaml](techniques/passing-none.yaml): hear the pocket foundation with `approach_rate: 0`, `chromatic_rate: 0`, and no passing notes.
- [techniques/passing-walking.yaml](techniques/passing-walking.yaml): hear the walking persona at density 0.95 with up to four passing notes per bar.
- [techniques/walking-blues.yaml](techniques/walking-blues.yaml): hear a continuous walking line over eight bars of `I I I I IV IV I I` at 120 BPM.
- [techniques/walking-jazz.yaml](techniques/walking-jazz.yaml): hear a continuous walking line over `I vi ii V` at 140 BPM, with `approach_rate: 0.4`.
- [techniques/walking-vs-pocket.yaml](techniques/walking-vs-pocket.yaml): compare the jazz walking file with pocket bass at density 0.65 and `approach_rate: 0.1`; the progression and tempo match.

### Grooves

- [grooves/groove-combined.yaml](grooves/groove-combined.yaml): combine octave and fifth jumps at 0.3 each with `pedal_rate: 0.2`.
- [grooves/groove-fifth-drops.yaml](grooves/groove-fifth-drops.yaml): hear picked drive with `fifth_jump_rate: 0.7` and `octave_jump_rate: 0.1`.
- [grooves/groove-octave-jumps.yaml](grooves/groove-octave-jumps.yaml): hear slap octave movement with `octave_jump_rate: 0.6` and `fifth_jump_rate: 0.1`.
- [grooves/groove-pedal-tones.yaml](grooves/groove-pedal-tones.yaml): hear the dub persona hold a foundation with `pedal_rate: 0.8` and `rest_rate: 0.3`.

### Fills

- [fills/fills-funk.yaml](fills/fills-funk.yaml): hear busy slap fills with `fill_rate: 0.6` and `fill_complexity: 0.8`.
- [fills/fills-minimal.yaml](fills/fills-minimal.yaml): hear sparse fingerstyle fills with `fill_rate: 0.1` and `fill_complexity: 0.3`.
- [fills/fills-pocket.yaml](fills/fills-pocket.yaml): hear a middle ground with `fill_rate: 0.4` and `fill_complexity: 0.5`.

### Slap

- [slap/slap-conservative.yaml](slap/slap-conservative.yaml): hear restrained slap with `slap_pop_rate: 0.3` and `ghost_perc_rate: 0.1`.
- [slap/slap-funk.yaml](slap/slap-funk.yaml): hear more pops and ghosts at `slap_pop_rate: 0.7` and `ghost_perc_rate: 0.25`.
- [slap/slap-vs-finger.yaml](slap/slap-vs-finger.yaml): hear the fingerstyle counterpart to conservative slap with the same anchor pattern, density 0.7, and rest rate 0.1.

### Advanced

- [advanced/motion-style-demo.yaml](advanced/motion-style-demo.yaml): compare `motion_style: stepwise`, `leaping`, and `mixed` across a full band arrangement; articulation and density change too.
- [advanced/solo-comparison.yaml](advanced/solo-comparison.yaml): hear the same bass settings move from verse to `solo: true` and back over the same progression.
- [advanced/solo-funk.yaml](advanced/solo-funk.yaml): hear a slap bass feature with `role: lead`, syncopated attacks, and `chromatic_rate: 0.3`.
- [advanced/solo-pocket.yaml](advanced/solo-pocket.yaml): hear fingerstyle accompaniment become a solo over `I vi ii V`, then return to the verse.

The articulation, rhythm, fill, and groove files also change seeds or other
settings; use their listed values to choose a starting point for your own comparison.

## Controls to try

Use `rhythm_pattern` for the onset vocabulary and `density` for activity.
`rest_rate` removes notes. `motion_style` selects stepwise, leaping, or mixed
pitch movement. `approach_rate` and `chromatic_rate` control approaches into
chord changes.

See [bass controls](../../docs/llm-song-config-reference.md#bass-controls)
for drum locking and the alternate kick-led renderer.

Try [themes_demo.yaml](../themes_demo.yaml) to hear bass quote a theme;
the [theme controls](../../docs/llm-song-config-reference.md#themes) explain coupling.

For walking bass, start from the walking persona and a jazz recipe. For funk,
try slap articulation, a syncopated pattern, and moderate kick locking. For
metal, try picked articulation and a drive pattern. Full defaults, ranges,
and fill controls are in the [bass reference](../../docs/llm-song-config-reference.md#bass-controls).

```yaml
# Inside an instruments block:
bass:
  params:
    articulation_style: slap
    rhythm_pattern: syncopated
    density: 0.9
    lock_to_kick: 0.7
```

To build a comparison group:

```bash
for file in examples/bass/articulation/*.yaml; do
  python produzre_entry.py build "$file"
done
```

The event TSV records each note's `kind`, including approach, fill, cadence,
and theme quotation. Use it with the piano roll to check what a control changed.
