# Drum performance

The drums have two performers. The composed drummer is the default; the
classic engine plays when you choose it. They share the kit, the
humanization pass, and the groove clock that the rest of the band follows.

## The composed drummer

Each song draws its own drummer (`produzre/composer/drums.py`): two kick
patterns (one for verse-like sections, a busier one for chorus, solo and
outro), a timekeeper and backbeat per section type, a ghost-note style, a
fill vocabulary, a crash habit, and a feel. The build log prints it:

```text
[INFO] Composer drums: kick x..x.x.../x...xx.., chorus=ride8/backbeat, ..., ghosts=light, fills every 8 (big:ga/snare_only), crash every 8, feel straight
```

What you can shape, per section, in the drum params:

| Setting | Effect on the composed drummer |
|---|---|
| `ghost_rate` | 0: no ghost notes. Below 0.3: a grace note before the backbeat every other bar. 0.3 or more: a grace before and after every backbeat. |
| `fill_rate` | 0: no fills. Below 0.5: a fill every 8 bars. 0.5 or more: every 4 bars. 0.75 or more: one-beat fills every 2 bars as well. |
| `kick_density` | 0.3 or less: kick on 1 and 3 only. 0.7 or more: the verse plays the chorus kick pattern. |
| `hat_density` | 0.3 or less: quarter-note hands. 0.8 or more: sixteenths. Verse and prechorus. |

Fills carry their own crescendo: each hit's velocity rises through the
fill, and a big fill ends on the next section's crash. See
[groove-shaping-demo.yaml](groove-shaping-demo.yaml) and
[fills-demo.yaml](fills-demo.yaml).

### Feel and timing

The drummer's feel (straight, laid back, pushing, or shuffle) reaches the
whole band through the shared groove clock. It applies only when you set
no timing of your own. Any of these keep the song's feel out and use yours:

- drum `swing`, `swing_16th`, `push_pull`, or `timing_jitter_ms`;
- `swing` or `swing_16th` in the top-level `groove` block;
- song `humanize_timing`.

A song-wide drum `persona` (under `instruments.drums`) supplies timing
jitter and velocity humanization for the composed drummer as well; its
pattern settings (`fill_rate`, `hat_density`, voice rates) do not count as
your choice and leave the drummer's DNA alone.

`song.take` redraws the humanization and keeps the parts; a drum `seed`
redraws the drummer. See [take-demo.yaml](take-demo.yaml).

## The classic engine

Set `composer: false` in the drum params, or use a part selector (`voices`,
`recipe`, `pattern`, `riff_accent_rate`, a section `intent`, or a
`drum_groove` theme), and the section is played by the genre-template
engine. Its performance ornaments work only there:

| Setting | Ornament | Event kinds in the TSV |
|---|---|---|
| `choke_rate` | Open hats, crashes and splashes are grabbed short (0.05 to 0.1 beats). The ride chokes at a fifth of the rate. | `crash_choke`, `open_hat_choke`, `ride_choke`, `fill_choke` |
| `flam_rate` | A grace note about 0.04 beats before an accented or backbeat snare, at 50 to 60% velocity. | `flam_grace`, `snare_flam`, `fill_flam` |
| `drag_rate` | Two grace notes, about 0.06 and 0.03 beats before the snare, at 45 to 55% velocity. A note gets a flam or a drag, not both. | `drag_grace`, `snare_drag`, `fill_drag` |

Ornaments run before humanization, so grace notes keep their spacing
while the whole figure moves with the groove. Fills ramp their velocity
through the fill in both performers.

[classic-engine-demo.yaml](classic-engine-demo.yaml) plays a plain verse,
then all three ornaments, then the engine's phrase, fill-length, pickup and
downbeat controls. Count the ornaments in its export:

```bash
cut -f12 exports/<export>/analysis/drums/*_drums.events.tsv | sort | uniq -c
```

When the composed drummer is playing, the build log lists any of these
settings you set as unused and names `composer: false` as the way to use
them.
