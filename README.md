# Produzre

Produzre turns a YAML song description into MIDI parts. Choose a key, tempo,
progression, instruments, and section order. It writes a full song and optional
text views.
You also get stems (one MIDI file per instrument), section clips (one section
at a time), and patterns (reusable chunks of notes).

The output is MIDI, so you choose the sounds in your DAW or synthesizer.
Version 0.9.0 adds shared themes, recurring musical ideas that instruments
develop across the song. It also adds melodic development and more coordination
between instruments. See [CHANGELOG.md](CHANGELOG.md) for changes
that affect existing songs.

## Start here

Use Python 3.10 or later. From a source checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python produzre_entry.py build examples/minimal.yaml
```

On Windows, activate with `.venv\Scripts\activate` instead. The runtime
dependencies are Mido and PyYAML. This checkout runs directly; it does not
require an editable package install. `python -m produzre.cli` is another entry
point. If you have built the standalone executable, replace
`python produzre_entry.py` with `produzre` in these commands.

The build prints `Export root:` with the output folder. Import the song's `.mid`
file into a DAW and assign an instrument sound to each track. MIDI channel 10
(zero-based channel 9) uses General MIDI percussion.

```bash
python produzre_entry.py validate examples/minimal.yaml
python produzre_entry.py show-config examples/minimal.yaml
python produzre_entry.py build examples/themes_demo.yaml
```

`validate` checks configuration. `show-config` shows parsed settings and
loaded presets. A recipe supplies style defaults for a section. To see which
recipe a section used, build with `-v`.

## Write a song

A build parses your config, then plans each section's harmony, energy, and themes.
The six note engines, `drums`, `bass`, `rhythm_gtr`, `lead_gtr`, `acoustic_gtr`,
and `arpeggiator`, render the instruments you listed. The harmony engine supplies
chord data without writing notes. Produzre then exports the song and its parts.

```yaml
version: 1
song:
  title: First Song
  bpm: 120
  key: E
  mode: minor
  meter: "4/4"
  genre: rock
  seed: 42
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
  chorus:
    type: chorus
    bars: 8
    harmony: {progression: "bVI bVII i i"}
    instruments:
      harmony: {}
      drums: {}
      bass: {}
      rhythm_gtr: {}
      lead_gtr: {}
arrangement: [verse, chorus, verse, chorus]
```

`sections` defines the parts; `arrangement` puts them in order. Reusing a section
is enough to get another performance of it. Section type shapes dynamics and
phrasing. Explicit `intensity` overrides the automatic intensity arc.

Start with a genre and change a few controls after hearing the result.
A persona is a preset for an instrument's playing character. A pocket describes
where an instrument sits ahead of or behind the beat. See the
[config reference](docs/llm-song-config-reference.md#recipes-and-personas) for
how recipes, personas, and your settings combine.

```yaml
instruments:
  bass:
    persona: pocket
    params:
      articulation_style: finger
      fill_rate: 0.15
  rhythm_gtr:
    params:
      use_patterns: true
      style: funk_chanks
      density: 0.5
```

These settings supply global defaults; a section only plays the instruments it lists.
The [configuration reference](docs/llm-song-config-reference.md) contains all
parameter tables, defaults, meter units, harmony syntax, personas, and examples.

## Themes and groove

A song without authored themes automatically gets a riff, a short repeated
phrase, and a hook, a melody that returns through the song. Lead
guitar, acoustic melody, and phrase arpeggios draw from that shared material.
Bass, drums, and rhythm guitar only couple to the riff when explicitly enabled.

```yaml
themes:
  main_riff:
    role: riff
    register: [36, 60]
    events: "1:.5 1:.5 b3:1 4:1 1:1"
instruments:
  bass:
    params: {lock_to_riff: 1.0}
```

See the [theme controls](docs/llm-song-config-reference.md#themes) for writing
and developing your own material. [themes_demo.yaml](examples/themes_demo.yaml)
is a complete arrangement; the [theme design](docs/design/theme-bank-architecture.md)
explains how the engines share it.

The top-level `groove` block sets shared swing. Pitched instruments can also
set `pocket_ms`; positive milliseconds mean behind the beat.

```yaml
groove:
  swing: 0.6
  swing_16th: 0
  pocket_ms: {bass: 8, rhythm_gtr: 3}
```

You can change meter per section; see [meter and beat units](docs/llm-song-config-reference.md#meter-and-beat-units)
for timing units and how exports carry those changes.

## CLI reference

| Command | Purpose |
|---|---|
| `build <config>` | Render and export the song. |
| `validate <config>` | Check configuration and section references. |
| `show-config <config>` | Print parsed configuration and loaded defaults. |
| `project <subcommand>` | Manage project seeds and metadata. |
| `user <subcommand>` | Manage a local user profile. |

`build`, `validate`, and `show-config` accept `-v`/`--verbose` and
`--song-name <name>`. `show-config --format json` selects JSON instead of YAML.
Use `--help` on a command to inspect its arguments.

| Build flag | Effect |
|---|---|
| `--dry-run` | Load, plan, and render in memory without export files. Initial config setup may create a local project registry. |
| `--no-export-sections` | Skip section clips. |
| `--no-export-patterns` | Skip pattern MIDI and sequence files. |
| `--sections-absolute-timing` | Preserve song positions in section clips instead of starting each at beat zero. |
| `--strict-determinism` | Build twice and compare all generated MIDI files byte for byte. |

```bash
python produzre_entry.py build my-song.yaml --dry-run -v
python produzre_entry.py build my-song.yaml --strict-determinism
python produzre_entry.py build my-song.yaml --song-name "First Song"
```

## Output files

A build creates a timestamped folder under `song.exports_root`, which defaults
to `exports`. The song name is sanitized for filenames.

```text
exports/My_Song_<timestamp>/
  My_Song.mid
  index.yaml
  QUICKREF.txt
  instruments/
    bass/
      My_Song_bass.mid
      sections/My_Song_bass_00_verse.mid
      patterns/My_Song_bass_p001.mid
      sequence.yaml
  analysis/
    bass/
      My_Song_bass.events.tsv
      My_Song_bass.grid.txt
```

Each instrument gets the same folder layout. Section filenames include the
zero-based occurrence number, which counts each appearance in the arrangement.
Pattern IDs identify deduplicated note windows;
`sequence.yaml` records their order, with `_` for silence. Repeated section ids
remain distinct in the sequence and index. Pattern meter is part of its identity.

Use the full song for a first listen, stems for separate sounds, or section clips
for rearranging. `QUICKREF.txt` lists DAW bar markers. `index.yaml` records section
times, meters, instruments, and file paths. These text files include build metadata
and are outside the MIDI byte-determinism check.

Enable text analysis with:

```yaml
exports:
  midi_text:
    enabled: true
    views: [events, grid, tab]
    subdiv: 16
```

The grid shows one row per pitch and one column per display step. In a 4/4 bar,
a 16-step header reads `1e&a2e&a3e&a4e&a`. `X` marks velocity 110 or higher,
`^` marks 92-109, `x` marks 70-91, and `.` marks quieter notes. Ghost snares
may use `g`. A dash means no attack.

Guitar tab shows strings from high E at the top to low E at the bottom. Numbers
are frets, zero is an open string, and aligned numbers are simultaneous notes.
Tab is a reading aid; check the fingering yourself.

The events TSV has columns `instrument`, `section_id`, `bar`, `beat`,
`start_beat_abs`, `duration_beats`, `pitch`, `note`, `velocity`, `channel`,
`program`, and `kind`. Bar and beat labels start at 1; absolute beat starts at 0.
`kind` explains the event source, such as `snare_ghost`, `fill`, `root_cadence`,
`theme_riff`, or `crash_transition`.

Text bar labels use the song's grid. For mixed-meter songs, use the index or
QUICKREF for DAW bar markers and the TSV's absolute beats for event timing.
The [export reference](docs/llm-song-config-reference.md#export-controls)
also covers minimal, debug, and custom output modes.

## Seeds and projects

`seed` chooses generated material, `take` selects a performance version, and
`variation` sets a bias toward different performance choices. See
[DETERMINISM.md](DETERMINISM.md) for overrides, instrument dependencies,
and what you need to reproduce the same MIDI.

A local project stores another seed that participates in generation. Two people
with the same song YAML may get different performances until they share that
project seed. A default project is created when first needed.

```bash
python produzre_entry.py project create my-album --seed 12345 --notes "Album demos"
python produzre_entry.py project list
python produzre_entry.py project show my-album -v
python produzre_entry.py project export my-album --out my-album-project.yml
python produzre_entry.py project import my-album-project.yml
```

Select it with `song.project: my-album`. Project import accepts `--overwrite`.
Export includes the seed unless `--no-seed` is set; custom metadata can be
selected with `--include genre,band` or `--include-all-custom`.

Other project commands are `path`, `set-owner <name> <owner>`,
`set-custom <name> <key> <value>`, and `unset-custom <name> <key>`.
Project commands accept `-v`/`--verbose`; `show -v` reveals the seed.

The registry is `projects.yml` under the platform's config directory:

| Platform | Default directory |
|---|---|
| macOS | `~/Library/Application Support/produzre/` |
| Linux | `$XDG_CONFIG_HOME/produzre/`, or `~/.config/produzre/` |
| Windows | `%APPDATA%\produzre\` |

Use `project path` to find it and back it up. `user path` locates the neighboring
profile. User commands are `show`, `path`, `set <field> <value>`,
`set-custom <key> <value>`, and `unset-custom <key>`. Standard profile fields
are `name`, `email`, `url`, `company`, and `band`.

## Things that trip people up

- Include `harmony: {}` in a section's instrument list when using pitched engines; see [why](docs/llm-song-config-reference.md#file-structure).
- Write meters as quoted strings, such as `meter: "4/4"`; the parser also accepts unquoted `4/4`.
- Use Roman numerals for progressions, such as `I V vi IV`, rather than note names such as `C G Am F`.
- Use intensity in the normal 0-1 range: write `0.7` for 70 percent.
- Repeat a section by listing its id twice in `arrangement`.
- Check genre spelling with `show-config`: unmatched names silently fall back to defaults; `build -v` confirms recipe selection.

## Examples and development

The [example library](examples/README.md) has 166 configs covering instruments,
genres, personas, seeds, and orchestration. Start with a simple genre example,
then compare it with a longer arrangement.

```bash
python scripts/build_all_examples.py --dir genres/rock
python scripts/build_all_examples.py
```

For config-writing assistants, use the [configuration reference](docs/llm-song-config-reference.md).
The existing [Song Builder GPT](https://chatgpt.com/g/g-69b2d0cda0088191a7126921c82fedbc-produzre-song-builder)
and [Claude setup guide](docs/produzre-claude-project-setup.md) are optional entry
points. Describe the musical result, then validate and audition the generated YAML.

Developers can add engines through the [engine registry and interface](produzre/engine/ENGINES.md).
See [tests/README.md](tests/README.md) for behavioral, golden, and determinism checks.

To build a standalone executable for the current platform:

```bash
python -m pip install pyinstaller
python scripts/build_executable.py
```

The result is `dist/produzre` on macOS/Linux or `dist/produzre.exe` on Windows.
Use `--clean` on the build script for a clean rebuild. The executable bundles
Python and runtime dependencies.
