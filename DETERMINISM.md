# Determinism

With the same song YAML, project seed, presets, engine code, and dependency
versions, Produzre produces the same MIDI bytes. Output folder timestamps can
change. Build metadata and logs can change too.
A release that fixes musical behavior can change output for an existing seed.
Those changes belong in the changelog and reviewed golden files.

## Seed scopes

| Scope | Inputs and purpose |
|---|---|
| Project | A persistent local seed, selected by `song.project` or the default project. |
| Song material | Effective song seed, genre, key, and mode. Automatic theme composition uses this stream before take variation. |
| Section performance | Song/project seed, take, section id/type, and arrangement position. |
| Instrument | Section stream plus instrument name, unless explicitly overridden. |
| Voice/bar/event | Stable child streams where an engine needs independent local decisions. |

`produzre/rng.py` uses length-prefixed hashing to separate seed components.
Child streams prefer stored seed material instead of a parent's changing random
state. This keeps unrelated random draws from shifting every later choice.

The instruments still respond to each other. Bass may follow kicks;
accompaniment responds to lead activity; constraints resolve collisions among
drum voices. Changing a provider can change its listeners. Some rendering
choices still share a stream inside an engine.

## Seed, take, and variation

| Setting | Use it to |
|---|---|
| `song.seed` | Try new generated themes and performance choices. Written arrangement order stays as supplied. |
| `song.take` | Try another performance of the same theme bank. Notes, fills, and timing can change. |
| `song.variation` | Bias engine variation without changing the written structure. |
| Section `seed` | Replace that section's performance seed. |
| Instrument `seed` | Replace that instrument's performance seed in the section. |
| Section/instrument `variation` | Override the broader variation value. |

Variation precedence is instrument, section, then song. Repeated sections
normally use different arrangement-position streams. Explicit instrument seeds
use section id and instrument name, so they can repeat the same random choices
across occurrences; harmony, intensity, and treatment can still differ.
Moving a section can change its output even if you keep its seed.

```yaml
song:
  seed: 42
  take: 1
  variation: 0.1
sections:
  chorus:
    type: chorus
    bars: 4
    seed: 999
    variation: 0.3
    instruments:
      drums:
        seed: 777
        variation: 0.5
arrangement: [chorus]
```

This drum-only song shows all three override levels. Section and instrument
performance seeds preserve the song-level theme bank. Authored themes also retain
their notes across takes; their arrangement treatment and realization remain
subject to harmony and register.

## Share a performance

Use the [project sharing commands](README.md#seeds-and-projects) to share a
performance; include your custom presets and Produzre version too:

```bash
python produzre_entry.py project export my-song --out my-song-project.yml
python produzre_entry.py project import my-song-project.yml
```

Select `song.project: my-song` on both machines; the
[README](README.md#seeds-and-projects) explains import options and registry locations.

## Verify a build

```bash
python produzre_entry.py build examples/themes_demo.yaml --strict-determinism
```

This builds twice and compares the bytes of all `.mid` files: full song, stems,
section clips, and patterns. Both directories remain available. Success exits
with code 0; a mismatch or error exits with code 1. The check does not compare
`index.yaml`, `QUICKREF.txt`, sequence YAML, or analysis text. Do not combine it
with `--dry-run`, which skips exports and the comparison.

For regression coverage:

```bash
python -m pytest -q tests/test_midi_determinism.py tests/test_seed_variation.py tests/test_themes.py
python tests/test_golden_drums.py
```

A same-version determinism check and a golden comparison answer different
questions. The first asks whether two current builds agree. The second asks
whether expected output has changed. Both are needed for output-changing work.

## Engine author rules

Your renderer receives an instrument RNG. Do not derive the same instrument
scope a second time. Use the supplied RNG, or stable named children:

```python
from produzre.rng import make_voice_rng

voice_rng = make_voice_rng(
    rng, voice_name="ornament", section_id=section.id,
    instrument_name=instrument_name,
)
if voice_rng.random() < 0.2:
    timeline.add_note(
        start_beat=section_start_beat + local_beat,
        duration_beats=0.25, pitch=60, velocity=70, kind="ornament",
    )
```

Other helpers are `stable_seed_int`, `make_section_rng`, `make_instrument_rng`,
`make_bar_rng`, and `make_event_seed`. Follow their keyword arguments in
[rng.py](produzre/rng.py). Never use an unseeded random generator for rendering.
Sort unordered inputs before they affect notes, random draws, or logs.

Shared groove jitter uses stable per-event seeds. The MIDI writer orders
simultaneous note-offs before retriggers, removes overlapping same-channel
same-pitch notes, and gives sub-tick notes a positive duration.

If a build differs unexpectedly, first compare config, project seed, custom
presets, and software versions. Then inspect the TSV `kind` and timing columns.
Check unseeded randomness, set iteration, mutable shared state, and timestamp
metadata. See the [test guide](tests/README.md) for the golden workflow.
