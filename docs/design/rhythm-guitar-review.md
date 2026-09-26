# Does the rhythm guitar still have rhythm?

Review baseline: `e80f0aa` on `dev`, including `92a4d93`, `8ecd293`,
`89005be`, `5c4a218`, and `e80f0aa`. Changes are uncommitted.

## Verdict

Yes, most sections establish a recognizable figure. The main problem is
not a new idea in every bar. It is too much activity inside the repeated
figure, sometimes coupled to a different rhythmic idea in the drums.
Signature tails and recurring chord slides can occupy space a singer or
another instrument should have. Removing all of them is not a good default:
some are the figure's identity, and blanket restraint reduced album diversity.

This review inspected performed note timelines, not just composition code,
and produced level-matched MP3 pairs. The musical judgments are based on
those rendered events and their harmonic context. No subjective listening
preference win is claimed for the sketch synthesizer previews.

On the ten-song baseline, the two most common onset/technique bars account
for 159/160 verse bars and 230/240 chorus bars, measured separately for each
section occurrence. Added fill/transition devices occupy only 4/160 verse
bars and 24/240 chorus bars. Those counts do not support the theory that
phrase fills constantly destroy the figure. However, all 112 verse bars in
the seven riff-driven songs contain a single-note tail. There are 166 slid
chord gestures across 240 chorus bars. Devices embedded in the repeating
figure are the more important issue.

### Specific musical evidence

Bar numbers below are local to the named section; beat offsets are
zero-based quarter-note beats. The accompanying
[bar sheets](rhythm-guitar-review-bars.txt) give pitches, durations, drums,
bass, and interval candidates.

| Song and location | Producer's reading |
|---|---|
| Album hard rock 08, first chorus bars 1-4, E minor, 156 BPM | This grooves despite frequent slides. The upstroke at 1.5 and slide at 3.0 meet drum attacks. Bar 2's downbeat strum rings for a beat. The initial downbeat omission follows the pushed entrance. Chorus accent alignment is 84.9%; the repeated slide is part of a stable figure, not evidence of constant novelty. |
| Album hard rock 10, first chorus bars 1-3, C major, 164 BPM | Strong strums at 0, 1, 2, 3 sit on the drum skeleton. Sus gestures and walk notes fill between them. Chorus accent alignment is 98.0%. This is a useful counterexample to simply counting techniques. |
| Album hard rock 01, first verse bars 1-4, B minor, 120 BPM | Root/chug motion establishes the riff, but the power attack at 0.75 anticipates the snare at 1.0 by a sixteenth. The 2.5 chug also sits a sixteenth before the 2.75 kick. Two-note and four-note tails alternate every bar. Verse attacks average 9/bar, with only 0.45 beats of silence/bar. This is a stronger candidate for restraint. |
| Album hard rock 03, first verse bars 1-4, E major, 160 BPM | Guitar power moves at 0.75 and 2.25 oppose drums around 1.021 and 2.521. The differences are about 100 ms, much larger than humanization. Bass doubling supports the guitar's figure but cannot reconcile it with the drummer. |
| Band with a singer, verse bars 1-4 | There are 9-10 gestures/bar and a tail every bar. More seriously, bass doubling had replaced the explicit `lock_to_kick: 0.6`. Fixing ownership restores the requested bass role. This example and Instrumental Anthem share seed/material; their matching figures are not independent evidence of album sameness. |
| Funk instrumental, chorus; second verse bar 7 | The chorus has 13.5 gestures/bar, much of it short/percussive. This can be a valid funk texture, but the loud-accent alignment is only 45.7%. There is one measured tail/lead attack coincidence in the second verse's bar 7; the singer showcase has none. There is no evidence for a universal counter-line/tail collision rule. |
| Pop 4/4 and punk 4/4 probes | Pop verse accents align 81.0%; sustained notes overlap, so zero literal silence does not imply frantic activity. Punk's chorus aligns 95.2%, while its signature-riff verse aligns only 36.6% before fixes. The rhythm problem is section-specific. |

The average baseline chorus is busier than the verse: 9.58 versus 8.61
attacks/bar, with 0.61 versus 1.02 silent beats/bar. Some choruses open up,
such as Album 08, but a universal claim that the chorus creates more space
would be false.

## Music theory findings, most serious first

1. **Long power moves can clash with the lead, even when the riff is idiomatic.**
   Album 03's outro bar 1 holds D3/A3 from local beat 2.25 over E major
   while the lead holds G#4. The overlaps are about 0.73 beats: D/G# is a
   tritone and A/G# a minor-second pitch-class relationship. This is a
   stronger concern than a fleeting blues note. The same contour recurs
   over the next chord. It remains a documented musical limitation.
2. **A chord-relative minor-pentatonic vocabulary is not automatically a mistake.**
   Album 03 verse bar 2 includes F2 over D major for about 0.23 beats before
   returning to D. That short borrowed minor third belongs in hard-rock or
   blues language. Conversely, a b7 power chord against a sounding major
   third can create both a tritone and a semitone, as above. I did not
   globally quantize power moves or tails to the major scale: it would
   remove intentional mixture without solving phrase coordination.
3. **The scale approach was not always a scale note. Fixed.**
   It always used `target - 2`; approaching C in C major produced Bb.
   It now uses a real scale neighbor and approaches from the side of the
   preceding root, allowing descending as well as ascending motion.
   Chromatic-below approaches remain brief intentional non-chord tones.
   They should be judged by the landing, not rejected merely for a
   momentary semitone under the guitar.
4. **Signature riffs bypassed meter grouping. Fixed.**
   The forced 7/8 riff probe covered only 32/48 verse group starts;
   it now covers 48/48. The 12/8 blues probe improves from 40/64 to 64/64.
   A separate drum-humanization bug shifted a group-start snare at 1.5
   to 1.655 beats under swing. Drum and guitar group starts now agree.
   Grouped riffs attack each group and fit their tail inside the last group.
5. **Playability is plausible but not certified.**
   The 160 BPM example's sixteenths are about 94 ms apart. Low-string
   power shapes and short pentatonic runs are playable vocabulary, but
   folding each riff pitch into MIDI 38-52 can reverse a written contour
   or cause an abrupt position change. D2/Eb2 also require a tuning below
   standard low E. Explicit register bounds work, but there is no string,
   fret, tuning, or hand-position model. I did not silently replace the
   intended low-register rock sound with standard tuning.

Rendered strong-beat lead notes are chord tones in 93/101 attacks in the
singer showcase, 146/157 in the anthem, and 71/72 in the funk showcase,
unchanged by this work. None has a held strong-beat color longer than 0.75
beats without the probe's immediate stepwise resolution. This does not
prove every short color resolves, or replace checking the entire phrase.
The singer and anthem final choruses move from E to F# with the intended
section harmony. Existing hook-resolution and modulation tests also pass.
The rendered singer showcase has
no sustained guitar/bass or guitar/lead minor-second/tritone candidates
under this review's half-beat threshold. The interval scanner is a prompt
for inspection, not a harmony correctness score; register and resolution
matter. No evidence here justifies changing all hooks, turnarounds, or the
final-chorus lift.

## Technical findings and fixes

| Finding | Fix and regression evidence |
|---|---|
| Riff pitch overwrote `base`, the velocity baseline | Use a separate pitch variable. Repeated equal-accent attacks now retain dynamics regardless of interval. Previously the first attack could be near velocity 90 while later ones inherited a MIDI pitch near 40 as their velocity base. |
| Bass doubling overrode explicit line choices | Check the saved ownership decision before doubling. Tests cover kick lock, an explicit rhythm pattern, and explicit `walking: false`. |
| Doubling replaced the entire section with only its riff bars | Keep engine events in transition and ending bars. Tests check the actual first transition and final section, not merely whether some late bass note exists. |
| Composed bass roles/doubling ignored explicit register bounds | Capture explicit bounds before recipe merging and constrain the final line. |
| Signature cache ignored section meter/grouping and rhythm part seed | Key the cache by meter, groups, seed, and optional pocket; use the section's values. |
| Bar-two body could overlap its new tail | Trim the body to the next attack. Checked over 100 seeds. |
| Drum swing moved compound group starts | Suppress swing displacement there while retaining pocket and jitter. |
| Album tool could silently compare fewer songs after a failed build | Fail the benchmark immediately and require at least two songs. |

The new tests assert musical or ownership properties, including grouped
bounds, repeated bodies, dynamics independence and register compliance.
They do not pin one seed's MIDI. Existing uniqueness tests and the album
fingerprint are useful, but neither proves that a groove is appealing.
The old benchmark's `comp_walkups` count includes any `comp_fill`, and
`comp_stop_time` includes other stop-tagged strums. This report uses the
performed gestures and per-bar audit instead of interpreting those labels
as literal counts of techniques.

## Changes and before/after measurements

The shipped default retains full riff figures (`comp_activity: busy`).
Correctness fixes apply automatically. Two opt-in arrangement controls add
restraint:

```yaml
song:
  arrangement_style:
    comp_activity: sparse  # normal also available; busy preserves full figures
```

`normal` states the full signature figure, then leaves the next bar's tail
open. `sparse` repeats three body bars before a tail, spaces added fills
by eight bars, and reserves most slides for phrase gestures outside bridges.
Transitions and endings retain their existing chosen devices. Restrained
signature candidates also consider the composed drum part's kick/snare
accents after explicit drum controls. This is a scoring bias, not a forced
unison; authored drum patterns remain untouched.

The sparse pair uses the same Album 01-derived YAML in both revisions.
The baseline ignores the new `comp_activity` key. Both versions have the
same seed, harmony, tempo and form.

| Sparse example measurement | Before | After |
|---|---:|---:|
| Verse attacks/bar | 9.00 | 6.75 |
| Verse bars containing a tail | 16/16 | 4/16 |
| Verse silence, beats/bar | 0.45 | 1.46 |
| Verse attacks aligned to kick/snare | 47.9% | 50.9% |
| Verse loud-accent alignment | 43.2% | 38.8% |
| Nearby competing verse accents | 12 | 3 |
| Chorus slides | 22 | 3 |
| Chorus loud-accent alignment | 73.2% | 73.2% |

This is more space and fewer nearby competing attacks, not a blanket
pocket improvement. The velocity fix exposes previously underplayed power
accents, changing which attacks qualify as loud. In the updated unrestrained
Album 01 control, loud-accent alignment is 40.7%, so the sparse option still
does not win that particular metric. Its clearer benefit is phrase space.

Across the default ten-song album, all-attack guitar alignment is unchanged:
45.9% in verses and 51.2% in choruses. Loud-accent alignment changes from
60.8% to 57.3% in verses after correcting dynamics; choruses remain 72.1%.
Default device counts and tail density remain unchanged. The grouped-meter
fixes improve pulse coverage, but their strongest-velocity accent metric
can fall as the figure and dynamics change. No metric here is disguised as
a listening preference score.

### Album diversity guard

Lower is more varied. Both runs contain all ten songs.

| Default album metric | Before | After |
|---|---:|---:|
| Overall, requested album seed 1 | 0.164 | 0.162 |
| Guitar verse / chorus / bridge | 0.076 / 0.079 / 0.126 | 0.076 / 0.079 / 0.126 |
| Distinct guitar patterns in each of those sections | 10/10 | 10/10 |
| Bass bridge | 0.213 | 0.194 |
| Overall, additional album seed 2 | 0.164 | 0.165 |

The additional album's small increase is confined to bass chorus similarity
following the scale-approach correction; guitar similarities are unchanged.
Thus the requested benchmark and guitar diversity guard pass, but a strict
claim that every album metric never increases would be false. Correcting
an out-of-scale note can make a pitch fingerprint less unusual. This
remaining bass tradeoff is explicit, not hidden by the aggregate.

Broad automatic restraint and automatic candidate reranking were tried and
rejected: early versions raised the requested album to about 0.173, and a
later restrained default still raised the second album to 0.171. The final
restraint modes are opt-in. I also rejected changing synthesized cells merely
to drive the similarity number down. The existing default cell grammar and
4/4 riff selection remain intact.

### Preview pairs

The files are full-band sketch renders of the same songs before and after,
with matched stereo RMS within each pair and common peak-safe gain. Most
are 66 seconds; blues is 92 seconds. The synthesizer is not a substitute
for a guitarist's performance or a production mix.

| Pair | Before | After |
|---|---|---|
| Album 01, default dynamics/correctness | [MP3](../../exports/rhythm-review/previews/Album_hard_rock_01-before.mp3) | [MP3](../../exports/rhythm-review/previews/Album_hard_rock_01-after.mp3) |
| Album 03, major-key hard rock | [MP3](../../exports/rhythm-review/previews/Album_hard_rock_03-before.mp3) | [MP3](../../exports/rhythm-review/previews/Album_hard_rock_03-after.mp3) |
| Singer showcase, explicit bass ownership | [MP3](../../exports/rhythm-review/previews/band_with_singer-before.mp3) | [MP3](../../exports/rhythm-review/previews/band_with_singer-after.mp3) |
| Blues 12/8, grouping and drum pulse | [MP3](../../exports/rhythm-review/previews/blues_12_8-before.mp3) | [MP3](../../exports/rhythm-review/previews/blues_12_8-after.mp3) |
| Opt-in sparse Album 01 | [MP3](../../exports/rhythm-review/previews/restrained_hard_rock-before.mp3) | [MP3](../../exports/rhythm-review/previews/restrained_hard_rock-after.mp3) |

Exact MIDI sources and gain values are in
`exports/rhythm-review/previews/sources.json`. Exports and previews are
ignored build artifacts in this workspace; the report, summarized metrics,
bar sheets, tests and audit tool are reviewable source files.

## Measurement and validation

- Baseline full suite: 632 passed. Final full suite: 652 passed.
- All 171 example YAML files build, including all three composer showcases.
- Eight focused configs pass strict determinism and byte comparisons under
  `PYTHONHASHSEED=1,77,999`, including compound/odd meters, major hard rock,
  the singer showcase and the opt-in sparse arrangement.
- Nineteen focused configs per revision provide the rendered bar audit:
  ten album songs, the sparse variant, three showcases, pop, punk, blues
  12/8, and forced signature-riff 6/8 and 7/8 probes.
- The album benchmark was run before/after for two album seeds. The second
  album changes harmony, keys and tempos but shares the benchmark's song
  seeds, so it is not a fully independent seed generalization test.
- No commits, pushes or golden regeneration. `git diff --check` passes.

An attack is a performed gesture, clustering same-kind string notes within
0.075 beats, not each chord string counted separately. A loud accent has
at least 90% of its bar's peak MIDI velocity, excluding dead-note chucks.
Alignment means within 0.1 quarter-note beat of an actual kick or non-ghost
snare. Nearby competition means an off-quarter accent more than 0.1 and no
more than 0.3 beats from such a drum attack; use that diagnostic in 4/4 only.
Silence is the complement of sounding guitar note intervals, not a perceptual
masking model. Sustained interval candidates require at least half a beat of
overlap and are not automatically errors. MIDI velocity is an imperfect
proxy for loudness, and the velocity fix changes accent membership.

Reproduce with `tools/rhythm_review.py --out <directory>` and
`tools/album_diversity.py --genre hard_rock --songs 10 --out <directory>`
using `.venv/bin/python`. Add `--album-seed 2` for the additional album.
Use the identical audit script at each revision. Durable summary data:
[rhythm-guitar-review-metrics.json](rhythm-guitar-review-metrics.json).
Raw per-bar JSON and validation records are under `exports/rhythm-review`.

## Next work and deliberate non-changes

1. Coordinate long riff power moves with actual lead holds, preserving blues
   inflections but avoiding the demonstrated outro clashes. Prefer a
   chord-aware candidate choice or a shorter articulation over blanket
   scale quantization.
2. Improve the opt-in pocket objective against performed drum timing and
   phrase context. An average candidate-score gain does not guarantee a
   loud-accent alignment gain in a particular rendered song.
3. Run blinded owner auditions and new song seeds before enabling restraint
   by default. Include vocal recordings: literal MIDI silence is not the
   same as room for a singer.
4. Add tuning/string/fret constraints before making stronger playability
   claims. Preserve the present dropped-register rock idiom meanwhile.

I left repeated slides that demonstrably support the groove, existing
chorus forms, lead hooks, short blues colors, and genre vocabulary intact.
The unresolved long-note clashes and imperfect pocket are real limitations;
none is concealed by the successful build and determinism checks.

## Follow-up: restraint as a habit, locked riffs

The review above left restraint opt-in and the pocket bias off by default.
The follow-up makes `comp_activity` a per-song habit (roughly 3 busy, 5
normal, 2 sparse for rock), scores every signature riff against the song's
drum DNA, rules out accents a sixteenth off the backbeat, chokes riff power
moves that clash with a held lead note, and lets a doubling bass play the
tails the guitar leaves open. Measured on the same ten-song album with
`tools/rhythm_review.py`:

| Album measurement | Before | After |
|---|---:|---:|
| Verse attacks/bar | 8.61 | 7.61 |
| Verse bars with a tail | 112/160 | 88/160 |
| Verse near-miss accents/bar | 0.97 | 0.46 |
| Verse loud-accent alignment | 57.3% | 59.0% |
| Verse silence, beats/bar | 1.02 | 1.30 |
| Outro sustained guitar/lead clashes | 18 | 0 |
| All sustained guitar/lead clashes | 22 | 2 |

Verse loud-accent alignment in the showcases: singer and anthem 65% to
86%, funk 61% to 87%, punk 38% to 71%. Choruses, prechoruses and bridges
are unchanged. Album similarity rises from 0.162 to 0.168 (album seed 2:
0.165 to 0.169), almost all in bass verses (0.08 to 0.14): more riffs now
sit on root chugs, which resemble the driving-eighths bass role of other
songs. Every part remains far below the 0.41 of the original generator.
