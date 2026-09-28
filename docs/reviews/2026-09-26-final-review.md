# Final review of the merged examples work

Reviewed `e5de7dc..fd032b6` on `dev`, including the merged transition,
rendering, groove-memory, phrase, register and ownership paths. Changes are
uncommitted. No golden files were regenerated in this pass.

## Fixed interactions

| Problem and root cause | Fix | Regression evidence |
|---|---|---|
| Transition thinning recognized generic melody/lick kinds but missed country fills, double stops and trills. It could remove half a phrase or one voice of a double stop. | Add those composed kinds to the existing phrase protection shared by thinning and pickup admission. | Complete phrases survive across five bar lengths and three offsets; the double-stop case includes simultaneous voices. |
| Quiet backbeats and custom-kit crashes failed the GM-pitch/velocity test for structural drum hits. | Honor semantic kick, snare and crash roles before the legacy fallback. | Velocities 20 through 80, ordinary and remapped snares, and a crash mapped to pitch 51 remain structural; a quiet ghost remains nonstructural. |
| Groove recall used bar duration but omitted grouping, allowing a 3/4 pattern to return in 6/8. | Include resolved groups in memory identity and share the no-harmony meter resolver with composed drums. | Three seeds each for 3/4 versus 6/8 and 6/4 versus 12/8, using classic drum-only sections, never recall the other grouping. |
| Groove-cycle selection always received the song genre even when the instrument selected another genre. | Pass the effective part genre and include it in recall identity. | Rock songs with funk, reggae and jazz drum parts pass the part genre to groove memory. |
| Genre-specific comp, bass and drum DNA redrew country style without the owner's explicit pin. | Forward the arrangement override before genre hints are applied. | All six styles win for country and outlaw-country parts inside a rock song, for all three DNA producers. |
| A per-part classic rhythm-guitar opt-out failed without drums when the song composer was active, because the default registry declared optional drum features mandatory. | Require harmony only; keep using the orchestrator grid and optional drum accents. Custom explicit requirements remain enforced. | Both classic guitar renderers produce positive-length notes in one-bar solo sections across five meters. |
| Ramp-down duration scaling ran after bass gates had been fitted, extending roots into the next attack or section. | Preserve bass gates while retaining the velocity ramp and rhythmic thinning. Correct the transition debug description too. | Five bar lengths and early, exact and late attacks retain nonoverlapping notes and the section boundary. |

All properties are in `tests/test_finish_review.py`. On an archived copy of
`fd032b6`, 22 cases fail and one passes. The passing control is quiet kick
protection, which already worked. All 23 cases pass with the fixes. These are
property checks over meters, offsets, velocities, styles or seeds, not MIDI
snapshots. No random draws or seed streams were added.

## Existing tests and code review

Read the new subsystem tests and changes to existing assertions. Most older
changes move inputs to frozen fixtures. The revised walking test strengthens
coverage from a minimum event count to four quarters per bar. Solo register and
non-root bass-label checks now sample several seeds instead of depending on one
take. Fifth-drop checks retain pitch and downbeat assertions while relaxing a
seed-specific count. The guitar walk test now places its approach at a real
harmonic change. The odd-meter bass-response test pins a counter that leaves a
musical gap, rather than requiring every drawn chorus form to leave one.

Those edits are consistent with the new behavior; they do not replace the need
for interaction tests, which exposed the issues above. The review also checked
shared device windows, bass pickup clearing, drum pickup deduplication, bass
root and chromatic retargeting, body-tap pitch preservation, riff-alone entry,
slap-floor enforcement, and the double-stop exceptions in lead clipping.
The shared grouping resolver removes one duplicated drum-only fallback without
restructuring the large rendering function.

## Musical and header review

This was an event-based musical review. Twenty-two 45-second synthetic previews
were generated with `tools/preview_audio.py`; no claim of an ear-based audition
is made. The spread includes all twelve complete songs, fingerpicked folk
acoustic, funk slap bass, country Telecaster lead, jazz solo kit, and the
country, reggae, jazz, electronic, gospel and prog genre examples.

The detailed bar audit covers Backstreet Strut, Porch Light Waltz, Cold Coffee
Blues, Clockwork Tide, Harbour Road, Backdoor Blue Room, Afterglow Frequency and
Sunday Morning Glory Road. Observations from the final events:

- Porch Light Waltz retains bass on the waltz floor, short vocal-response lead
  fills, and a clear lift: mean drum velocity about 48 in verses and 63 in
  choruses, bass about 80 and 102. No sustained guitar/bass/lead clash candidates
  were found by the audit.
- Clockwork Tide keeps 7/8 grouping changes distinct from its 5/4 bridge, with
  riff doubles in the verses and octave bass in choruses. The arrangement's
  dropped bars remain open. The audit found no sustained clash candidates.
- Harbour Road keeps the one-drop groove and authored bass motif, with a quieter
  dub and rockers choruses. Groove bars and fill bars are distinct; the one-drop
  description is not a promise to suppress every opening crash or fill.
- Cold Coffee Blues keeps the 12/8 pulse and authored bass contour. Its lead
  leaves room in the verses and takes the solo. The audit's tritone candidates
  largely pair thirds and sevenths of dominant chords, which belong in this
  harmony; no blanket consonance filter was added.
- Jazz preserves feathered kicks, swing skips and continuous walking bass.
  Syncopated comping need not coincide with every drum attack. The interval
  audit includes passing bass notes and seventh-chord tensions, so its raw
  candidate count is not treated as an error count.
- Gospel retains two dotted-quarter pulses, rolling piano and a quieter bridge.
  Mean bass velocities are about 79 in verses, 99 in choruses and 61 in the
  bridge. Electronic retains the offbeat hats and sixteenth bass/ostinato;
  inspection confirmed the sixteenth-bass headers, so they were kept.
- Country lead transition tails now retain their composed fills and double
  stops. The fixes preserve existing material and space rather than adding
  ornamental activity.

All 138 example headers and inline listening comments were read alongside
configuration and rendered evidence. Corrections:

- Funk instrumental: the actual non-rock solo ending is a hold, not a dive.
- Funk slap solo: the sparse intro is thumb-led, not mostly ghost notes, and
  the solo reaches G4, matching its explicit upper limit.
- Passing-tone demos: the drive pattern uses a sixteenth grid with gaps, not
  a strict eighth-note line.
- Drum phrasing, instrumental anthem, funk, reggae and Latin: distinguish
  composed phrase forms from the groove-memory pass for eligible engine parts.
- Genre details: the arena-rock piano joins after the guitar opening; the
  mashup's reggae drummer plays rockers; the electronic kick description allows
  its written breakdown and fill gaps.
- Seed examples: the drum-only seed override leaves the other tracks unchanged
  in this comparison; a section override also changes following guitar gates;
  the take example now describes the actual drum, guitar and bass differences
  without claiming every note changes velocity or that drum pickup pitches change.

The per-file audit and full event summaries are saved at
`/tmp/produzre-finish-review/header-audit.md` and
`/tmp/produzre-finish-review/final/event-audit.json`. Previews and cross-hash
manifests are in `previews/` and `spread-results.json` under that scratch directory.

## Documentation

Updated the configuration reference, architecture, historical findings, README,
determinism guide and changelog. Corrections cover the development version,
138-example count, optional drum dependencies for solo classic guitar, meter-relative default harmonic rhythm, numeric lead bounds,
compound bass anchors, mixed-genre style pins, groove-memory ownership and
identity, protected transition material and bass gates. Export indices use the
song-named YAML file; the stale `index.yaml` descriptions were corrected.
README no longer says all lead technique controls choose the legacy performer
or that every chorus approach is stop-time.

## Validation

- Original suite: 1,194 passed.
- Final full suite: 1,217 passed in 164.44 seconds.
- New regression cases: 23 passed; 22 fail on `fd032b6`, one existing-behavior
  control passes there.
- Every example: 138 of 138 strict builds passed, no warning, error, unused
  composer setting or forbidden dash. All use `produzre-examples`.
- Edge matrix: 84 of 84 strict builds passed across six meters, six solo
  instruments and full band, one-bar sections, key changes and meter changes.
- Per-part composer opt-outs with the song composer on: 10 of 10 strict builds
  passed, covering drums, bass, rhythm guitar, lead and acoustic in 3/4 and 6/8.
- `PYTHONHASHSEED=1` versus `8675309`: 22 examples, 6,330 MIDI files compared
  byte for byte, all equal. Final rebuilt MIDI also matches those manifests.
- Previews: 22 rendered successfully. `previews/index.md` links each one.
- All 16 edited example configs are structurally identical to HEAD; changes
  are comments only. Whitespace checks and added-text dash checks pass.

All dedicated example, edge-case, cross-hash, event-audit and preview exports use
`/tmp/produzre-finish-review`. The initial test invocation used the repository's
existing fixture behavior, which writes relative `exports` directories; the
final full-suite runs use an archived scratch copy so those fixtures also write
outside the checkout. Existing checkout exports were not deleted or moved,
because other tooling is active in the repository.

## Worktree housekeeping

The leftover branch is merged into `dev` and its worktree is clean. PID 19013
was still a Claude process associated with this repository. Its working
directory was the main checkout, so it was not established that the agent had
released the locked worktree. Following the owner's live-agent exception, the
worktree, lock and branch were left intact. Neither Codex worktree was touched.

`git worktree list` before and after, unchanged:

```text
/Users/edcaspersen/Code/repos/produzre                                           fd032b6 [dev]
/Users/edcaspersen/.codex/worktrees/idiom-baseline/produzre                      e4573a7 (detached HEAD)
/Users/edcaspersen/.codex/worktrees/rhythm-review-baseline/produzre              e80f0aa (detached HEAD)
/Users/edcaspersen/Code/repos/produzre/.claude/worktrees/agent-a795a23723b53471d e846fef [worktree-agent-a795a23723b53471d] locked
```

Raw captures are `worktrees-before.txt` and `worktrees-after.txt` in the scratch
review directory. No cleanup or branch deletion is claimed.
