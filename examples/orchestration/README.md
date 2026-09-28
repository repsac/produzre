# Instruments playing together

[rhythm-lock-demo.yaml](rhythm-lock-demo.yaml) shows how the drums, bass
and rhythm guitar line up, one way per section. Build it from the
repository root:

```bash
python produzre_entry.py build examples/orchestration/rhythm-lock-demo.yaml
```

## How the composed band locks

The drummer is composed first and publishes its hits, and the other parts
listen:

- **Signature riffs** are scored against the drummer's kick and snare:
  accents in unison with them win, and no accent lands a sixteenth off the
  backbeat. A riff-driven song's bass can double the riff an octave down
  (`song.arrangement_style.bass_doubles`), and with `comp_activity: normal`
  the bass plays the riff's tail alone every other bar
  ([riff-demo.yaml](../rhythm_gtr/riff-demo.yaml)).
- **Bass roles.** In band sections (drums and a guitar) the bass plays a
  per-song role for each section: the engine's kick-and-chord line, the
  song's own kick pattern, root eighths, octaves, a gallop, or held roots.
- **Arrangement habits** such as the way into a chorus are shared by the
  drums and rhythm guitar ([drum transitions](../drums/TRANSITIONS.md)).
- **Groove memory** makes every part restate the same source bars, so the
  kick and bass lock survives the bar form
  ([groove memory](../../docs/llm-song-config-reference.md#groove-memory)).
- **The lead** is composed before the rhythm guitar plays, and riff chords
  that would ring a semitone or tritone against a held lead note are
  choked to a stab.

## Choosing the lock yourself

These settings take a part off its composed role and use an engine that
follows the drums:

```yaml
# Inside an instruments block:
bass:
  params:
    lock_to_kick: 0.9      # the bass engine line adds notes on the kicks
rhythm_gtr:
  params:
    follow_hats: true      # strum with the drummer's hands
```

Bass `rhythm_pattern`, `walking`, `lock_to_kick` or `lock_to_riff` keep the
bass engine's line, and an authored `bass_motif` theme owns the bass with
its written rhythm and lengths; see
[bass controls](../../docs/llm-song-config-reference.md#bass-controls)
for the difference between added kick locking and the kick-led renderer
(`lock_to_kicks: true`). The drum settings the composed drummer honors
(`ghost_rate`, `fill_rate`, `kick_density`, `hat_density`) change what the
others lock to.

## Themes and transitions

[themes_demo.yaml](../themes_demo.yaml) enables rhythm-guitar and drum riff
coupling next to an authored bass motif; see [theme controls](../../docs/llm-song-config-reference.md#themes) for their different roles.

See the [config reference](../../docs/llm-song-config-reference.md#transitions)
for the transition planner, [DETERMINISM.md](../../DETERMINISM.md) for seed
boundaries, and the [engine guide](../../produzre/engine/ENGINES.md) for plan
and feedback APIs.
