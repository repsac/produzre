# App findings from the examples upgrade (2026-09-26)

Rewriting the examples meant writing about 90 new configs against the
current app: 31 genre songs, 12 songs, 12 solo pieces, and the rewritten
instrument demos. The agents writing them reported the bugs and limits
below. Several were found independently by more than one writer. They are
deduplicated here and ranked by how much they limit real songs.

## Resolution

Every finding below is fixed, each with property tests (1060 passing), and
the examples no longer work around any of them.

| Findings | Fix | Commit |
|---|---|---|
| 1, 2, 3, 4, 10, 12, 14, 15 (drum knobs), 27 | Composed drum dynamics, compound-meter drummer and swing, jazz and dance players, audible builds, bridge-start keeps its first bar, solo backbeat kept, density knobs in every section, protected ride bell | `114885d` |
| 5, 6, 9, 11, 19, 20, 21, 22 | Walking lines, no silent bars or thinning choruses, bass plays into-chorus devices and endings, one riff-alone intro rule, enforced registers, root on beat 1, authored motif ownership, articulation on composed roles | `5806bf3` |
| 7, 8 (chorus_form), 15 (bend_rate), 16, 17, 18, 26 | Lead register forms, chorus_form under auto, bend_rate range, lead seeds, authored final-chorus lift, dense and developing solos, country fills, arpeggiator guide, extensions and dynamics | `eb52dec` |
| 8 (engines block, section persona, unknown params), 13, 23, 24, 25, 28 | `engines:` block, section personas, unknown-key warnings, walks only into chord changes, capo and barre ranges, sustain_duration, corrected docs | `21893b1` |
| 8 (section and instrument genre) | A part's own genre chooses its composed player | `2cd2a73` |

Found while fixing and also fixed: the drum engine always played the tight
persona, and unknown song and section keys were silent (`65cd51e`); drums
and comp disagreed on which sections play the into-chorus device, and
transition pickups ignored the instrument's register, the incoming key and
the meter, and were added into silence (`a26bf19`).

## High impact

1. **Composed drums ignore section intensity and energy.** Velocity is
   `base_velocity * plan vel` (`engine/drums/__init__.py`, the composed
   branch). A verse at 0.4 and a chorus at 1.0 play at the same level, and
   repeated choruses do not grow. Solo drum pieces have no dynamic shape,
   and a section handed to the engine by `intent` plays about 15 velocity
   units louder than the composed sections around it.
2. **Compound meters are wrong in the composed drummer.** 12/8 puts the
   snare on pulses 2, 3 and 4 and adds off-grid kicks. 6/8 hand voices
   (`hat4`, `pedal4`, `ride_bell`) and the accent rule are quarter-based.
   Recipe swing leaks into 12/8 and makes each triplet uneven. With
   `composer: false` the drum engine plays a correct 12/8. Drum-only
   sections without a harmony progression also lose the meter grouping
   (`render.py` passes `groups` only with a harmony plan), so 6/8 falls
   back to a 3/4 grid.
3. **The composed jazz drummer is not idiomatic.** The right hand draws
   random per-beat cells, so some beats have no ride (13 to 53 ride hits
   over an 8-bar head, where swing time has about 48). There is no hi-hat
   foot on 2 and 4, the kick lands on random beats, comping snares land at
   backbeat velocity, and 3/4 is worse (one seed had no timekeeping).
4. **No electronic or four-on-the-floor drummer.** Dance pop, electronic
   and techno examples use a locked `drum_groove` theme instead.
5. **Walking bass as documented does not walk.** The jazz recipe's density
   overrides the walking persona (recipes merge above personas), the
   persona's hat/snare/kick locks add swung eighths, groove memory turns a
   walk into repeated roots, and the walking persona does not set
   `rhythm_pattern: walking`. Examples set density 1, rest_rate 0, locks 0
   and `groove_memory: false`.
6. **Bass engine lines leave holes in band sections.** Low-density recipes
   (blues, blues rock, folk, gospel, pop chorus) leave whole bars silent, and
   repeated choruses can thin out (50, then 25, then 18 notes).
7. **`register: [lo, hi]` at instrument level crashes the lead**
   (`AttributeError: 'list' object has no attribute 'lower'` in
   `engine/lead_gtr/register.py:34`). It works under `params`.
8. **Silent no-ops.** None of these log anything:
   - the documented top-level `engines:` block (program, channel) is
     ignored; `build_engine_registry` reads only `instruments:`;
   - section and instrument `genre` overrides change only recipes; the
     composer builds every part from `song.genre`;
   - a section-level `persona:` does not apply its params;
   - `arrangement_style.chorus_form` does nothing with `foreground: auto`;
   - unknown params (`phrase_bars`, `fill_len_beats`,
     `kick_syncopation_rate`, `leap_probability`) are accepted silently.

## Arrangement and parts

9. **The bass ignores every `into_chorus` device** and plays through
   stop-time and drop bars, although the docs call these habits every part
   agrees on.
10. **`into_chorus: build` sounds like `fill` on drums.** The big fill spans
    the bar, so the snare-eighth build never sounds.
11. **Riff-alone intro: drums and bass disagree** when the intro has no
    rhythm or acoustic guitar. The drums play from bar 1, while the bass
    (`_is_band_section` counts the lead) waits half the intro.
12. **The bridge-start transition thins the composed drummer's first bar**
    (drops the crash and the beat-2 snare) and hardcodes 4 beats per bar
    (`orchestrate/transitions.py`, `bridge_start`).
13. **Rhythm guitar `~walk` variation adds a chromatic walk note every
    bar**, even when the chord does not change (C#3 over Am, over Fmaj7).
14. **Composed solo drums spend half of each phrase's backbeats on tom
    answers**; a rock verse keeps 8 real backbeats in 8 bars.
15. **Feel knobs have narrow reach:** `hat_density` affects only verse and
    prechorus hands, `kick_density` only verse-like sections, and
    `bend_rate` above 0.15 adds no composed bends.

## Lead guitar

16. A lead `seed` (instrument or section) does not re-roll the composed
    lead; it changes only humanization.
17. With an authored melody theme, the final chorus does not lift (only
    velocity rises).
18. The blues and trade solo stories are sparse over a 12-bar solo (one or
    two notes a bar), two consecutive solo sections come out nearly
    identical, and country licks and double stops appear only in the solo.

## Bass details

19. Recipe `register_high` is not enforced (Latin reached A3 against 52).
20. Groove memory kept the chord fifth on every verse downbeat with the pop
    recipe, against the documented root tie-break on beat 1.
21. `bass_motif` keeps its rhythm only on the `lock_to_kicks` path (with
    fixed 0.8-beat notes); elsewhere pitches are quoted on the engine's
    slots. An authored `bass_motif` alone does not keep the engine line in
    band sections, and needs an explicit `motif_quote_rate`.
22. `articulation_style: slap` has no effect where the composer gives the
    bass one of its roles.

## Guitars and keys

23. **`capo` breaks the composed fingerstyle:** thumb, inner voice and
    melody shift by different amounts (B2 under E4/C4/F#4, a D6 melody).
24. Acoustic `voicing_style: barre` with a picked melody reaches G6.
25. Rhythm `sustain_duration` does nothing on the pattern renderer; the
    grid renderer plays one quiet dyad per bar.
26. The arpeggiator applies the melody guide to every pattern (the docs
    say only `phrase`), plays triads only, and plays at velocity 80 to 94
    regardless of instrument intensity.
27. Classic drums: `ride.bell_rate` produced no bell hits.

## Documentation

28. The lead-guitar section of `docs/llm-song-config-reference.md` says
    rhythm `density`, `palm_mute`, `voicing` and register settings select
    the legacy path; the Composed comping section and the code say they
    shape composed comping.

## Second round

Removing the examples' workarounds exposed more issues. All are fixed with
property tests (1194 passing):

| Area | Fixed | Commit |
|---|---|---|
| Drums and transitions | Ramps keep composed fills, builds and devices (device windows) and use the section's meter; drums never get pitched pickups; `drop` plays closed hats; one hit per voice per step; solo tom answers stay out of build bars; groove memory recalls only a section with the same intent | `40dbce4` |
| Lead and arpeggiator | Octave counters sound both notes in every bar; `dive_rate` scales dives across solo phrases and logs match what plays; trills survive swing; a riff-alone intro holds back the lead and arpeggiator too | `8d19158` |
| Bass | Root on beat 1 of every new chord (engine, roles, groove memory, modulated sections); composed bass follows section dynamics; an explicit pattern beats the walking heuristic and style bias; 6/8 uses the pulse; pickups replace overlapped notes; real final notes; the slap floor holds, also after transitions; motif and riff-lock precedence is logged | `1a9f7ee`, `1d128c8` |
| Guitars, export, groove memory | Body taps keep their pitch; chromatic approaches stay a half step from their target; a section's first chord sits with the rest; tabs are relative to the capo | `e846fef` |

## Reproducibility

Composed parts combine the song seed with a per-user project seed, so an
example header describing a drummer, picking figure or lick bank held only
on the machine that wrote it. Fixed with a built-in project,
`produzre-examples`, whose seed is the same on every installation; every
example sets `song.project: produzre-examples`, so its header describes
what every user hears.
