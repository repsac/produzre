# Country review: a band identity per song

Baseline: `e4adde4`. Changes are uncommitted on `dev`; nothing was pushed.
The clean, attached `idiom-baseline/produzre` worktree was reused at that
revision. Both checkouts used the same configurations and local project
seed, `352484703`. Album seeds ran sequentially. The supporting scripts,
full MIDI, rhythm audits and audio live under `exports/country-review`.

## Shared style, independent players

A new `composer/country.py` chooses one of six country directions on
`composer.country.style`, independent of all existing streams:

| Style | Direction, not a fixed part |
|---|---|
| `honky_tonk` | Shared shuffle, Carter/chuck figures, chicken picking, thirds and Travis phrases |
| `bakersfield` | Straight, driving bass, low strings, hybrid picking and bright third/sixth figures |
| `outlaw` | Train/chuck figures, softer snares, optional common-tone bass pedal, banjo/Travis vocabulary |
| `two_step` | Dancing bass, offbeat guitar answers, thirds and sixths |
| `ballad` | Longer bass gates, fewer attacks, arpeggio/Carter/hybrid guitar choices, steel-like lead language |
| `country_rock` | Eighth-note bass shapes, strummed choruses, backbeat or train lift and four-quarter chorus kicks |

Pin a style with:

```yaml
song:
  arrangement_style:
    country_style: bakersfield
```

The pin reaches the lead before its lick bank is built, and reaches bass,
comp and drum DNA. Part seeds re-roll that player while retaining the
band's style. Separate player streams choose figures within each direction;
verse and chorus bass rhythms and guitar figures contrast. Existing
patterns, recipes, composer opt-outs, arrangement habits and performance
controls retain their precedence. Honky-tonk's shared swing comes through
the drummer's existing groove clock, whose explicit timing overrides still
win. A solo without drums does not gain that drummer-owned swing clock.

The first benchmark album draws honky-tonk for 01/02, ballad for 03/05/09,
outlaw for 04, two-step for 06/10, and country rock for 07/08. Bakersfield
is exercised by the pinned-style tests. This is a weighted vocabulary
choice, not automatic instrumentation or reharmonization.

## What changed and what the bars do

Positions below are zero-based quarter-note beats. Performed swing and
humanization can move the grid positions slightly. Song numbers refer to
album seed 1.

**Bass.** A player now chooses a recurring rhythm as well as a role:
two-beat, dotted spacing, pickup into 3, driving eighths, sparse holds,
optional short grace approaches, and root/fifth/octave/fifth motion.
Walk type and frequency remain independent. Outlaw pedals are used only
when the pedal belongs to the current chord, avoiding a sustained wrong
bass note. The existing boom-chick role remains the weighted home.

Country 01, verse bar 1, plays G2 at 0, B2 around 1.67 and D2 at 2.01;
chorus bar 1 answers with G2/D3 at 0/2 and shorter .65-beat gates. Country
03, verse bar 1, holds Eb2 for 2.95 beats, then plays G2 on 4; its chorus
holds Eb2 for 3.5 beats. These contrasting rhythms exist before any walk
or grace is added. The album-2 verse-bass regression is reversed in the
measurements below.

**Rhythm guitar.** The forced four-cell country shape is gone. Eight
families now provide their own interchangeable cells: Carter scratch,
alternating muted chucks, train, low-string riffs, two-step offbeats,
arpeggios, hybrid double stops and full strumming. Sub-style changes the
odds; each song draws different cells and section figures. A phrase can
still walk or slide into the next chord. Country comping shortens a
conflicting chord gesture underneath an anticipated held lead note.

Country 01, verse bar 1, uses Carter root/arpeggio/strum gestures, then a
short walk at about 3.66. Its chorus begins with root, upper double stop,
fifth, then a full strum and walk. Country 03 also chooses Carter for its
verse, with a root/arpeggio pickup, upper dyad and two short bass-string
walk gestures. Its bridge draws the arpeggio family. A ballad does not
have to choose arpeggios in every section, and two songs choosing Carter
do not receive the same bar.

**Lead.** Country generation now has chicken-pick, third/sixth double-stop,
steel, banjo, hybrid, Travis and chromatic-approach shapes. Its major-mode
ladder is major pentatonic (including the sixth), with a .12-beat b3-to-3
passing approach. Licks target the third or sixth; sustained arrivals
still defer to the active chord. Explicit minor-mode songs retain their
minor-mode pitch context. The existing hook, phrase memory and register
arc remain intact.

Country 01's chorus bar 2 has a late Travis answer, G4-D5-A4-D5-E5, ending
on the major sixth. Country 03's solo bar 7 opens with an unbent Eb5/C6
sixth, then continues through F5-G5-Ab5. The two notes of a double stop
now survive the composer, performer and final timeline cleanup. Marked
staccato country picks keep their gate when swung, instead of being
shortened twice into nearly inaudible notes.

Steel gestures are single-note bends and releases. A held companion note
cannot remain unbent on this engine's one pitch-bend channel, so no such
independent string bend is claimed. Double stops are explicitly unbent.

**Drums.** Each style draws personal kick pickups, timekeeper cells,
train/backbeat sections and snare touch. Choruses can lift through an
open hat/backbeat, a train figure, ride/bell, or four-quarter feet. Soft
snare velocities approximate a brush touch; this does not select a true
brush sample or kit. The prior sparse crash/ride/china policies remain.

Country 01 changes from hat/backbeat in its verse to open-hat/train in the
chorus. In verse bar 1 the kick plays 0, .655 and 2; chorus bar 1 moves
the pickup to 1.655, with quieter train taps between the backbeats.
Country 03 has softer train snare, sparse hats in verse bar 1 and a ride
bell chorus. The chorus changes the hand voice while its long bass gives
the sustained part room.

**Waltz.** Country bass still plays only beat 1 and alternates root/fifth
across bars. Pedal and four-beat rhythm choices cannot override this.
Ordinary guitar bars answer on 2 and 3. Existing phrase/ending gestures
remain available. The ten-song 3/4 album and meter property tests exercise
this after transitions, not only inside the bass helper.

## Matched measurements

The unchanged `tools/album_diversity.py` ran ten-song country albums with
`--album-seed 1` and `--album-seed 2`, sequentially, at each revision.
Both improve. These are all per-part similarity scores, including the
parts that get worse:

| Part | Album 1 before | Album 1 after | Album 2 before | Album 2 after |
|---|---:|---:|---:|---:|
| Drums verse | .302 | .308 | .347 | .302 |
| Drums chorus | .374 | .278 | .374 | .276 |
| Drums bridge | .335 | .330 | .382 | .286 |
| Bass verse | .238 | .126 | .383 | .125 |
| Bass chorus | .201 | .135 | .244 | .135 |
| Bass bridge | .227 | .091 | .257 | .157 |
| Rhythm guitar verse | .289 | .088 | .270 | .071 |
| Rhythm guitar chorus | .204 | .095 | .248 | .128 |
| Rhythm guitar bridge | .091 | .102 | .099 | .140 |
| Lead chorus | .315 | .047 | .194 | .036 |
| **Overall** | **.258** | **.160** | **.280** | **.166** |

The ten-song country waltz album improves from .712 to .694. It stays
relatively similar because bass on 1 and chords on 2/3 are intentionally
shared. The ten-song solo-country-lead score stays .074: this metric mostly
sees recurring hook bars, while the new lick language occurs in answers
and solos. It is not a complete measure of lead identity.

Across the 720 country band bars, guitar gestures decrease from 7.60 to
6.61 per bar; bass notes increase modestly from 3.06 to 3.26. The lead
has attacks in 132 of 240 chorus bars versus 156 before, with 570 notes
versus 594. Some of its similarity improvement therefore reflects the
choice of spaced fills instead of continuous guide lines, not only the
new pitch vocabulary. Chorus drum similarity improves on both albums,
but album-1 verse drums and both guitar bridges remain counterexamples.
I did not add attacks to force those individual cells lower.

Hard rock remains .168, reggae .258, jazz .254 and pop .179. All ten
full-song MIDI files in each of these four control albums are byte-identical
before and after, not merely equal under the similarity metric.

### Pocket and harmonic exposure

`rhythm_review.inspect`, through the existing `breadth_review.py` runner,
audited the same country configurations at both revisions. The new parts
have zero sustained clash candidates, down from one, and 16 near misses,
down from 33. The initial implementation exposed six clash pairs under
anticipated lead notes; the final comp shortening removes those without
changing their attacks.

Raw accented-guitar coincidence with kick/snare **falls from .9489 to
.8690**, so an unconditional numeric pocket pass would be inaccurate.
There are 2,138 accented guitar gestures now, versus 2,135 before; the
coincident count is 1,858 versus 2,026. The denominator is effectively
unchanged. The missing unisons largely belong to new offbeat answers.

For example, country 06, verse bar 1, formerly scores 4/4 accents matched.
The new two-step bar scores 2/3: guitar root and fifth frame dyads/upstrokes
at .5, 1.5 and 2.5, then a strum at 3.5. The drummer keeps the quarter-note
backbeat and selected pickups. Its .5 dyad is an intentional answer,
not a mistimed unison. Country 03, verse bar 1, moves the other way,
from 2/3 to 4/4. I retained these differences because forcing every guitar
accent onto the kick or snare would erase the requested two-step and
hybrid-picking character. The lower near-miss count is useful supporting
evidence, but owner listening still decides whether the interlocks work.

[Machine-readable measurements and selected bars](country-review-metrics.json)
include both album reports, style/player choices, the coincidence counts,
clash counts, and the SHA-256 hashes of all 40 unchanged control MIDIs.
Full audit rows and exact configurations are retained under
`exports/country-review/{baseline,final}/rhythm`.

## Listening

The three band pairs use different drawn styles: country 01 honky-tonk,
03 ballad, and 04 outlaw. These and the waltz are 65-second excerpts.
The unaccompanied country-04 lead preview contains the full piece so its
later lick development can be heard. Each before/after pair is matched
in RMS level and shares peak headroom. These are deterministic sketch-synth
renders, not a claim of realistic brush, twang or pedal-steel samples.

| Piece | Before, e4adde4 | After |
|---|---|---|
| Country 01, honky-tonk | [MP3](../../exports/country-review/previews/Album_country_01-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_01-after.mp3) |
| Country 03, ballad | [MP3](../../exports/country-review/previews/Album_country_03-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_03-after.mp3) |
| Country 04, outlaw | [MP3](../../exports/country-review/previews/Album_country_04-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_04-after.mp3) |
| Country 01, 3/4 | [MP3](../../exports/country-review/previews/Album_country_01_Waltz-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_01_Waltz-after.mp3) |
| Country 04, solo lead | [MP3](../../exports/country-review/previews/Album_country_04_lead_gtr-before.mp3) | [MP3](../../exports/country-review/previews/Album_country_04_lead_gtr-after.mp3) |
| Six-song country sampler | [MP3](../../exports/country-review/previews/country-sampler-before.mp3) | [MP3](../../exports/country-review/previews/country-sampler-after.mp3) |

Sampler order: 01, 03, 04, 06, 07, 10. Each contributes its first eight
verse bars, followed by a one-second gap. This includes two two-step
songs so the comparison tests variation within a style as well as
between styles. No progressions or keys were altered to make the styles
sound different. `previews/sources.json` records the source MIDI, lengths,
levels and sampler order.

## Verification and deliberate limits

- Full suite: 712 passing tests, including the new style, ownership,
  vocabulary and complete double-stop-pipeline properties.
- All 171 examples build with section and pattern exports enabled.
- Strict determinism plus matching MIDI under `PYTHONHASHSEED=1` and `77`
  for all ten country songs, a waltz, solo lead, and four control genres.
- Existing meter tests still cover 3/4, 6/8, 7/8 and 5/4; a rendered waltz
  verifies that post-render transitions do not add a second bass attack.
- Generated licks, riff cells and bass rhythms vary across seeds within
  every pinned style. A loaded YAML test verifies the style pin reaches
  the players and explicit bass walking settings retain engine ownership.

Western swing is left out: a credible version needs coordinated harmony
and jazz voicings rather than a new label on these existing progressions.
Independent string bends, a true brush kit and a fretboard fingering
solver remain unsupported. Explicit harmony and authored patterns are
not rewritten to fit a style. Other genres retain their measured MIDI.
The non-country lead stays monophonic, and the country exception permits
only marked unbent double stops. The solo hook generator and its form
were left alone; this work changes the country lick vocabulary and band
choices rather than replacing the melody composer.

## Follow-up: waltzes and genre hints

**Waltz band per song.** `country.WaltzPlayer` is drawn per song on its
own stream and shared by bass, comp and drum DNA, only in 3/4 with
one-beat groups. Bass: beat 1 always; ring length (.9, 1.9 or 2.9 beats);
root/fifth habit (by bar, only on a held chord, or root only); walks
across 2 and 3 into a chord change (every change, every other, or phrase
ends; diatonic or chromatic), with verse and chorus contrasting. Guitar:
the song's figure on 2 and 3 (pah-pah, choked, pah with upstrokes,
sixths, arpeggio, ringing ballad strum), chorus differing from verse,
weighted by country style. Drums: kick on 1 with an occasional "and of 3"
pickup, snare or cross-stick on 2 and 3 (or one of them), optional foot
hi-hat, a timekeeper figure, and no ghost notes.

| Waltz album | Before (0ce5367) | After |
|---|---:|---:|
| Album seed 1 overall | .694 | .522 |
| Album seed 2 overall | .693 | .507 |
| Rhythm guitar verse (seed 1 / 2) | 1.00 / 1.00 | .226 / .495 |
| Drums verse (seed 1 / 2) | .304 / .294 | .502 / .392 |
| Bass chorus and bridge | 1.00 | 1.00 |

The drums are more alike than before on this metric. The old variety
came from sixteenth-note kick pickups, train snares and ghost notes that
do not belong in a waltz; the new drummer is idiomatic, with fewer
dimensions for the metric to see (the cross-stick and snare share a
class, and ring lengths are invisible). Waltz bass bars read 1.0 because
every waltz bass bar starts with a root on 1; walks, ring length and
fifths are the audible differences. Ten-song albums are noisy at this
level: an earlier draft with fewer drum options scored .435 and .481,
with the same design.

**Genre hints.** `style_hint` maps genre names to a style (`outlaw`,
`country_rock`/`rock`/`southern`/`modern`, `honky`, `bakersfield`,
`texas`/`two_step`/`dance_hall`, `ballad`). Plain `country` still draws
all six; a pinned `country_style` still wins. Hints apply only when the
genre contains "country": a bare `honky_tonk` or `bakersfield` genre is
not yet treated as country by the other parts.

**Unchanged output.** Fifteen 4/4 songs (country, hard rock, pop, reggae,
jazz) are byte-identical to 0ce5367; the ten-song 4/4 country albums
remain .160 and .166. 722 tests pass; all 171 examples build; a waltz and
an `outlaw_country` waltz pass strict determinism and identical MIDI
across two PYTHONHASHSEED values.


## Follow-up: reviewing the waltz band (e4573a7)

Baseline `e4573a7` was checked out in the clean, reusable
`idiom-baseline/produzre` worktree. The final changes remain uncommitted on
`dev`. All render destinations for this review are outside the repository,
under `/tmp/produzre-country-meter-review`. The same configurations were
used at both revisions, apart from their external output destinations.
Albums ran sequentially at each revision, with ten songs for each of
album seeds 1, 2 and 3. This includes both 3/4 and unchanged 6/8 controls.

### 1. Waltz drums: more player choices, mixed similarity results

The drummer now chooses its waltz hand voice independently of the 4/4
country groove: closed hat, ride, pedal-hat chicks, or a restrained
floor-tom pulse for ballads. Chorus choices open the hat on beat 3 or
move to ride, with an optional bell accent on beat 1. Bell replaces a
hand hit; it does not add another layer. Soft ballad hand velocities
supply a lighter touch. These are normal GM kit voices, not real brush
sweeps. Extending a snare note would not honestly synthesize a brush.

Kick still owns beat 1, with at most an eighth-note pickup after beat 3.
Snare or cross-stick answers on 2 and/or 3; optional foot hats sit with
those accents. Ordinary phrase fills now last one or two beats and use
simple eighths on snare, toms or a mixed path. The inherited extra-kick
and rim/ghost paths are disabled for waltzes. Authored arrangement endings
and explicit patterns retain their existing behavior.

Album 1, song 06, verse bar 1, has A2 held for 1.9 beats, guitar A2/F#3
sixths on beats 2 and 3, and cross-stick plus ride on those two beats.
Album 2, song 03, verse bar 1, uses E2 held for 1.9 beats, full guitar
answers on 2 and 3, pedal-hat chicks on both, and a soft snare only on 3.
Those are different allocations of the same three-beat pulse, not added
sixteenth-note activity. Across the three albums, drum hits fall from
17,765 to 14,602. Bass notes rise from 2,850 to 3,134 as the independent
stream chooses more existing walks; guitar gestures rise modestly from
7,635 to 7,844. The six-song sampler makes the comparison
available at matched clip levels.

The original verse-drum score improves for two album seeds and worsens
for one. The voice-aware verse score improves on all three. Chorus
drums still get more alike on two seeds, even with exact kit voices.
This remains a limitation, not a metric success to hide. I kept the
limited, idiomatic chorus lifts rather than adding arbitrary attacks to
force lower numbers.

### 2. The metric: retain history and add audible dimensions

`album_diversity.py` retains its original modal-onset score unchanged.
It now also reports `performance_similarity`: a normalized distribution
of all non-fill note tokens, using quarter-beat gate buckets for pitched
parts and exact GM pitches for drums. Cross-stick, snare, closed hat,
pedal hat and bell are therefore distinct. Two-bar pitch anchors retain
alternating fifths and occasional walks. Transposition, velocity changes
and tiny timing differences do not create artificial novelty.

This is a supplement, not a replacement score. Relative two-bar pitches
also reflect chord movement, so it is not a pure player-style measure.
A short note and a held note differ substantially under token overlap;
this does not quantify how much a listener prefers either. The matched
configs and separate historical score keep those limitations visible.
The old bass scores of 1.0 were largely a blind spot: the duration-aware
baseline already shows substantial bass variation. The new verse bass
is actually more alike on all three seeds under the supplemental metric.

Original modal score, before -> after:

| Part | Album seed 1 | Album seed 2 | Album seed 3 |
|---|---:|---:|---:|
| drums.verse | 0.502 -> 0.342 | 0.392 -> 0.361 | 0.404 -> 0.424 |
| drums.chorus | 0.389 -> 0.383 | 0.401 -> 0.481 | 0.393 -> 0.514 |
| drums.bridge | 0.430 -> 0.439 | 0.417 -> 0.366 | 0.416 -> 0.505 |
| bass.verse | 0.800 -> 0.800 | 0.533 -> 0.593 | 0.800 -> 0.422 |
| bass.chorus | 1.000 -> 1.000 | 1.000 -> 0.681 | 0.681 -> 0.500 |
| bass.bridge | 1.000 -> 1.000 | 1.000 -> 0.800 | 0.867 -> 0.593 |
| rhythm_gtr.verse | 0.226 -> 0.323 | 0.495 -> 0.537 | 0.299 -> 0.368 |
| rhythm_gtr.chorus | 0.381 -> 0.398 | 0.400 -> 0.594 | 0.412 -> 0.392 |
| rhythm_gtr.bridge | 0.425 -> 0.313 | 0.336 -> 0.402 | 0.494 -> 0.339 |
| lead_gtr.chorus | 0.069 -> 0.069 | 0.095 -> 0.095 | 0.059 -> 0.059 |
| **Overall** | **.522 -> .507** | **.507 -> .491** | **.483 -> .412** |

Supplemental performance score, recomputed from both revisions with the
same final analysis code:

| Part | Album seed 1 | Album seed 2 | Album seed 3 |
|---|---:|---:|---:|
| drums.verse | 0.427 -> 0.247 | 0.263 -> 0.228 | 0.307 -> 0.242 |
| drums.chorus | 0.275 -> 0.274 | 0.266 -> 0.307 | 0.280 -> 0.411 |
| drums.bridge | 0.339 -> 0.283 | 0.257 -> 0.257 | 0.280 -> 0.244 |
| bass.verse | 0.133 -> 0.235 | 0.153 -> 0.161 | 0.098 -> 0.168 |
| bass.chorus | 0.097 -> 0.120 | 0.113 -> 0.103 | 0.103 -> 0.107 |
| bass.bridge | 0.142 -> 0.118 | 0.149 -> 0.109 | 0.114 -> 0.094 |
| rhythm_gtr.verse | 0.235 -> 0.282 | 0.358 -> 0.345 | 0.130 -> 0.235 |
| rhythm_gtr.chorus | 0.134 -> 0.210 | 0.167 -> 0.218 | 0.282 -> 0.288 |
| rhythm_gtr.bridge | 0.136 -> 0.162 | 0.281 -> 0.176 | 0.200 -> 0.144 |
| lead_gtr.chorus | 0.069 -> 0.069 | 0.085 -> 0.085 | 0.082 -> 0.082 |

### 3. Noise and independent streams

`waltz_player` now has separate `composer.country.waltz.bass`, `.comp`
and `.drums` streams. A property test injects another drum draw and
checks that bass lengths, alternation, walks and guitar figures remain
identical. Splitting the old shared stream necessarily changes existing
3/4 choices once; those changes are included in the measurements.
The lead is not re-rolled.

The original overall score has a three-seed mean of .504 before and
.470 after, with ranges .483-.522 and .412-.507 respectively. Each album
improves, but the after range is wider. Three albums expose this noise;
they do not establish a population-level improvement. The per-part
counterexamples above matter as much as the overall mean.

### 4. Walk harmony, guitar releases and pocket

Non-chord bass passing notes now last .20 beats rather than .85. Chord
tones retain their .85-beat walk gates. Beat-1 ownership, walk placement
on beats 2 and 3, and the approach to the next root remain intact.
For example, album 1 song 03 verse bar 1 plays Eb2 (.9 beats), F2 (.2),
and G2 (.85) over Eb. The F passes quickly instead of hanging beneath
the held chord. The following bar arrives on Ab.

The audit also revealed arpeggios ringing across chord changes. The
performer normally lengthens an arpeggio beyond its planned note gate;
country waltz plans now supply a harmony-release boundary that the
performer respects. In album 1 song 03 bridge bars 1-2, the old Eb-chord
G4 rang for about half a beat against the incoming Ab bass. It now
releases at the change. This fix is restricted to composed country 3/4.

The guitar now observes the bass player's `change` alternation habit
on a held chord, as well as `bar` alternation. A root against a fifth was
consonant, not one of the audit's sustained clash intervals. Matching
the habit makes the low-string intent clearer. The bass can still choose
an octave instead of a fifth; that root/fifth combination remains a
legitimate part of the voicing. Explicit part seeds can intentionally
choose different players.

The audit's bar size and grouping already support 3/4. Its old overlap
loop missed notes carried in from the previous bar. I fixed that blind
spot and ran the same expanded audit against both revisions. A pair is
assigned to the bar where its overlap starts, so carry-ins are not
counted twice. These are semitone/tritone exposure candidates held for
at least half a beat, not a complete psychoacoustic dissonance model.

| Album | Sustained candidates before -> after | Pocket before -> after | Near misses before -> after |
|---|---:|---:|---:|
| Seed 1 | 22 -> 0 | .9090 -> .8846 | 8 -> 1 |
| Seed 2 | 66 -> 0 | .8848 -> .8117 | 0 -> 2 |
| Seed 3 | 87 -> 0 | .8909 -> .8641 | 1 -> 0 |

All 2,160 waltz bars have zero final sustained candidates. Pocket does
not pass an unconditional numeric non-regression test. It measures
accent coincidence with kick/snare, excluding the hand timekeeper.
Album 2 song 06 verse bar 1 goes from 2/2 to 1/2 accents matched: the
new guitar answers on 2 and 3, while the snare answers only on 3 and
the ride keeps eighths across both. The beat-2 guitar is on the ride
pulse, not late. Song 08 in that album stays 2/3 matched, with
cross-stick on 2 and hat on 3. These are deliberate lighter waltz
allocations. They still need listening judgment; the lower total near
misses (9 to 3) is not proof of a better pocket.

### 5. 6/8: reviewed, deliberately unchanged

A country 6/8 band should feel two dotted-quarter pulses, with bass on
1 and 4 of the eighth-note count, chordal or picked answers around those
pulses, and a restrained backbeat on the second pulse. It should not
borrow the waltz's three equal quarter-note answers. The existing grouped
path already supplies the two bass pulses and per-song 4/4 country DNA
for its other choices. I left generation unchanged in this follow-up.

Across three ten-song 6/8 albums, all 30 MIDI files are byte-identical.
Overall scores remain .295, .308 and .312, a mean of .305 and range
.295-.312. Full per-part values are in the linked measurements. The
seed-1 audit remains at .7719 pocket, 18 near misses and 18 sustained
candidates. Thus 6/8 is not being presented as a solved ballad player.
A future compound-meter pass should address those exposures and build
coordinated slow-ballad figures on their own streams. Extending the
3/4 fix blindly would hide that separate musical problem.

### 6. Genre aliases and hint boundaries

`produzre/genres.py` owns the alias mapping. Song and instrument genres
are normalized when configuration is parsed, so the same canonical name
reaches arrangement, engines, recipe selection and composer parts.
`honky`, `honky_tonk`, `bakersfield`, `outlaw`, `two_step`, `texas`,
`dance_hall` and `western` resolve to explicit country names; spaces,
hyphens and case are accepted. `western` uses the honky-tonk direction,
not a claim of a new western-swing harmony engine.

Hints now match whole underscore-delimited words rather than arbitrary
substrings. Bare `rock`, `ballad`, `modern` and `southern` remain outside
country. `country_rockabilly`, `country_modernism` and `country_texasville`
do not accidentally pin a style. An explicit `country_style` still wins.
A rendered property test confirms that bare `outlaw` and
`outlaw_country` produce the same band with a ballad pin.

### Tempo, lead and user ownership

Section contrast now includes a chorus hand-voice lift as well as the
existing bass and guitar contrast. I did not add tempo thresholds:
shorter real-time notes already follow from a faster tempo, and a global
BPM threshold would not know whether a user intended a broad or brisk
three-beat feel. The 72-BPM ballad and 184-BPM honky-tonk previews expose
that choice for listening. Slow/fast adaptation remains a future musical
decision, not a new hidden override.

The lead's meter-aware phrasing, sixths and existing country lick bank
are unchanged; lead-chorus fingerprints match at all three seeds. This
pass concentrates on the rhythm players and harmony releases.
Patterns, recipes and composed-part opt-outs retain their ownership.
An explicit low or high `hat_density` now also reaches the waltz hand
figure, instead of being overwritten by the waltz default. Its test
checks the rendered voice and grid. No new brush articulation or
independent string-bend capability is claimed.

### Listening and validation

The previews use the deterministic sketch synth. They are not realistic
brush or acoustic-instrument recordings, and no listening preference is
claimed from the numerical scores alone. The sketch synth now distinguishes
cross-stick from snare, pedal-hat chick from closed hat, and bell from
ride. Both revisions use that same renderer; synth changes do not alter
MIDI. Properties check distinct voices, decay and repeatability. The sampler uses the first
eight verse bars of album-1 songs 01, 03, 04, 06, 08 and 10, with a
one-second gap. Before/after source clips are level matched, then joined
with ffmpeg and re-encoded to MP3 rather than stream-copied.

| Preview | Before | After |
|---|---|---|
| Six-song waltz sampler | [MP3](/tmp/produzre-country-meter-review/previews/waltz-sampler-before.mp3) | [MP3](/tmp/produzre-country-meter-review/previews/waltz-sampler-after.mp3) |
| Slow ballad, 72 BPM | [MP3](/tmp/produzre-country-meter-review/previews/slow-ballad-before.mp3) | [MP3](/tmp/produzre-country-meter-review/previews/slow-ballad-after.mp3) |
| Fast waltz, 184 BPM | [MP3](/tmp/produzre-country-meter-review/previews/fast-waltz-before.mp3) | [MP3](/tmp/produzre-country-meter-review/previews/fast-waltz-after.mp3) |

- Full suite: 745 tests pass, including 23 new property cases.
- All 171 examples build with section and pattern exports enabled.
- Strict determinism and identical MIDI under `PYTHONHASHSEED=1` and `77`
  pass for 22 probes: ten seed-1 waltzes, one waltz each from seeds 2/3,
  three 6/8 songs, five 4/4 genres, and both tempo previews.
- Ten 4/4 songs each in country, hard rock, pop, reggae and jazz are
  byte-identical to baseline. The 30 compound-meter controls are also
  byte-identical. No 4/4 generation change is intended.
- Tests cover isolated player streams, alias equivalence and false
  positives, short passing notes, register, held-chord alternation,
  drum voices and fill placement, metric sensitivity, harmony releases,
  and explicit hat control. Existing waltz ownership tests still pass.

[Detailed measurements and selected bars](country-meter-review-metrics.json)
include both metrics, all six albums, audit totals and the 80 unchanged
MIDI hashes. Exact configs, logs, all audit rows, preview sources and
validation scripts are retained under
`/tmp/produzre-country-meter-review`. Audio and render files are external
review artifacts; they are not tracked in the repository.
