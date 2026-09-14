# Follow-up: editorial pass on the rewritten produzre docs

Repo: /Users/edcaspersen/Code/repos/produzre, branch `dev`, working tree has
uncommitted changes from a review and fix pass. Do not commit, stage, push,
tag, or branch. Leave everything in the working tree.

You previously rewrote 19 Markdown files. A second reviewer read the result
and concluded: the structure is right and the facts are accurate, so do not
rewrite again. This pass is editing, not restructuring. Edit in place, keep
every fact, and keep the current file layout (short README, one config
reference with all parameter tables, example READMEs that point at files).

Ground rules carried over: no em-dashes or en-dashes anywhere; short sentences;
no marketing words; check every claim against the code. Do not touch anything
under `docs/reviews/`.

## 1. Voice pass on every rewritten file

Read each file aloud in your head. Fix sentences that a person would not say.
Patterns to hunt, with real examples from the current text:

- Hedged caveats that explain the obvious or defend the tool:
  "Quoting it makes the intended string clear." Say: "Quote it, or YAML reads
  it as a date." "Treat exported tab as a performance aid, not a guarantee of
  fingering for every transformed melody." Say: "Tab is a reading aid; check
  the fingering yourself."
- Nominalized or passive phrasing: "recipes selected during rendering are best
  checked in verbose build logs." Say: "To see which recipe a section used,
  build with -v."
- Abstract openers: the changelog begins "This release develops musical ideas
  across a song and improves how the band shares rhythm, harmony, and space."
  Replace with what the user will notice.
- Sentences that state a rule without the reason: "These are global defaults,
  not an instruction to play in every section." Add the one-clause why: a
  section only plays the instruments it lists.
- Contractions are fine where they read naturally. Address the reader as
  "you". Use "we" nowhere.

Do not shorten further as a goal. The README is 307 lines; 300 to 400 is
fine. Adding a sentence that makes something clearer is allowed.

## 2. Say the MIDI caveat once

"The output is MIDI, so you choose the sounds" appears in `README.md:7`,
`examples/README.md:14`, and `examples/bass/README.md:5` in different words.
Keep it in the README intro only. Delete the other two.

Apply the same rule to any other idea explained in more than one file
(merge order, `harmony: {}`, seed vs take vs variation). Full explanation in
one place, one-line pointer elsewhere.

## 3. Put back two things the README lost

- A short section near the end called "Things that trip people up". Six
  bullets, one line each, drawn from the old README's Common Pitfalls
  (`git show HEAD:README.md`, search for "Common Pitfalls"): required
  `harmony: {}`, quoted meter, Roman numerals not note names, intensity is 0
  to 1, repeat a section by listing it twice, misspelled genres are silently
  ignored so check with show-config. Verify each is still true.
- Three or four sentences under "Start here" or "Write a song" saying how a
  build works: config is parsed, sections are planned (harmony, energy,
  themes), each engine renders its instrument, then everything is exported.
  Name the six note engines once. The old README had "How It Works"; keep it
  to a paragraph, not a section.

## 4. Example READMEs: replace catalogs with listening notes

`examples/bass/README.md` and the other instrument READMEs now carry tables
of every file with its internal song title (for example "BassStyle_Finger").
The title column tells the reader nothing. For each instrument README:

- Keep the "Find a comparison" folder table if there is one.
- Replace the per-file table with one line per file: the link, then what to
  listen for or what setting it isolates. If two files differ by one
  parameter, say which and the two values.
- If a folder has more than eight files, group them under a short heading
  instead of one long table.

Read each YAML before writing its line. Do not guess from the filename.

## 5. Changelog order

Restructure `CHANGELOG.md` for 0.9.0 so it opens with a section "What changes
for existing songs" (regenerated goldens, auto themes on by default, coupling
off by default, arpeggiator defaults, meter now derived from `meter`, swing
zeroed on straight drum recipes). Then "New", then "Fixed", grouped by area
(themes, drums, bass, guitars, groove and meter, export, config). Put the
commit hashes in one line at the end of the release entry, not in headings.

## 6. Define jargon at first use

Search the README and config reference for these words and make sure each is
defined in one short clause the first time it appears in each file: recipe,
persona, take, variation, pocket, theme, riff, hook, occurrence, stem,
section clip, pattern. If a term is defined in the config reference and the
README uses it earlier, the README gets the one-clause definition too.

## 7. Parameter tables

In `docs/llm-song-config-reference.md`, make every parameter table use the
same columns in the same order: Key, Range or values, Default, What it does.
Where the default depends on recipe or persona, write "recipe" or "persona",
not "varies". Add a "when to change it" clause only where it is not obvious.
Do not remove rows.

## 8. Verify before you finish

Script these checks and run them; paste the results into the report.

- Extract every fenced ```yaml block from every Markdown file. For blocks that
  are complete songs (have `song:` and `sections:`), write each to a temp file
  and run `python produzre_entry.py validate <file>`. For fragments, skip but
  list them. Every complete block must validate.
- Extract every fenced ```bash block. For each command that starts with
  `python produzre_entry.py` or `python scripts/`, run it with `--help` (or
  `--dry-run` for build) and confirm it exits 0.
- Check every relative Markdown link and every `#anchor` link resolves to an
  existing file and heading.
- `grep -rnP "\x{2014}|\x{2013}"` (em-dash U+2014, en-dash U+2013) over tracked Markdown,
  YAML, and Python must return nothing.
- Every parameter name mentioned in any README or the config reference must
  appear in the code (grep `produzre/`). List any that do not, and remove them.

## Report

Append a section to `docs/reviews/2026-09-13-fix-pass-report.md` titled
"Docs editorial pass" listing: files edited, the number of sentences changed
in the voice pass per file (rough count), the check results from section 8,
and anything you decided not to change and why.

Do not commit.
