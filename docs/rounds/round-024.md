# Round 24 - 2026-10-02

Lenses: the v0.6.0 outside review, what a pull request can make the Action say, claims that read as guarantees, the framework run under its own Action

**What this round was.** An outside review of v0.6.0 before its tag, every
finding reproduced by the maintainer before any fix. Four were fixed on the
release branch. The Action's verdict word could be written by the pull
request under test, and so could the job summary's markdown (R24-1). The
corpus's "deleting a case fails the run" was true of no run (R24-2). The
Action went red on Sutradhar's own repository (R24-4). The pipe check
flagged case patterns and `[[ =~ ]]` regexes (R24-7). Making the framework
pass its own Action meant reading every finding it raised on this tree. One
was a real conflation and is fixed (R24-3). The rest are explicit
degradations and are banked with reasons in `.github/sutradhar/`, never by
weakening a lint for every adopter (R24-5, R24-6, R24-8). The review's other
findings, and two guard defects already known from an earlier pass, are
recorded as deferred below with the reason for each. CITATION.cff carried
v0.5.2's release date under v0.6.0's version number, and now carries
2026-10-02.

## Findings

| id | severity | rule | found-by | status | summary |
|---|---|---|---|---|---|
| R24-1 | high | 6.8 | the outside review of v0.6.0 before its tag | fixed | run_guards.py called a guard crashed whenever the traceback header appeared anywhere in its output, and the output quotes the pull request: the interpolation lint echoes the adopter's expression and every source lint echoes filenames, on stdout and on stderr alike. An expression or a file named after the header turned a finding into crashed, the guard failed, not your code, and the summary row carried a live image and a rendered link, because only the table bar was escaped. Fixed in two layers, each verified alone. The verdict is the exit code and nothing else: each guard runs under a launcher the script owns, which runs it exactly as the interpreter would and turns an exception escaping the guard into exit 70, a code no guard returns; a guard file that cannot be read is now crashed too, where before it exited 2 and on-cannot-run skip passed it. Every adopter-derived summary string goes through md_inert, which writes ampersand and the angle brackets as character references and backslash-escapes every other ASCII punctuation character, complete by construction rather than by list. Pairs in test_distribution: the reviewer's expression stays a finding with no raw image tag or link in the summary; a guard raising the same text is crashed with that text inert; an absent guard is crashed under skip. Mutants red: the text test restored on the verdict line, the launcher dropped, the escape line, the ampersand line. |
| R24-2 | med | 3.7 | the outside review of v0.6.0 before its tag | fixed | Deleting a corpus case printed 51 of 51 and exited 0, while corpus/README.md said the total is asserted, the draft release notes said a deletion fails the run, and test_deleting_a_case_file_changes_the_total_and_fails asserted only that a count dropped, with exit 0. The R22-1 demo defect one level down: a denominator read off the disk shrinks with the disk. Fixed: corpus/case_count.json declares the total and a full run exits 1 unless exactly that many cases load, naming the shortfall or the excess. Symmetric, with no flag that rewrites it, which is the dialect of uncovered.json beside it and of framework_shape's baseline: a number that only moves in a reviewed diff is a floor, and one a tool rewrites is a counter. A present but malformed declaration exits 2 and is never read as absent. The CI corpus step passes require-case-count, so deleting the declaration itself exits 2. The test is renamed to say what it now asserts and carries the pair; corpus.py's selfcheck carries the shortfall pair and the missing-declaration pair. Mutants red with the selfcheck gate removed beneath them, and the selfcheck red alone. |
| R24-3 | low | 2.7 | the framework run under its own Action, fixing R24-4 | fixed | mcp_server _json_verdict returned None for a guard that printed no JSON and for one that printed JSON that would not parse, so the refusal told the caller the guard printed nothing when it had printed something broken. The refusal was right and its reason was wrong. Fixed the way the conflated-degrade lint asks, not by raising: it returns the verdict and the reason there is none, and the refusal quotes the reason. Pair test: no JSON and broken JSON refused with different reasons; mutant red. |
| R24-4 | med | 6.1 | the outside review of v0.6.0 before its tag | fixed | The Action's defaults run from this repository's root went red on three guards: swallow on the selfcheck wrappers, conflated-degrade on three functions, and the planted defects in examples. A framework red under its own one-line adoption is the first thing an evaluator would see. Fixed per finding (R24-3, R24-5, R24-6, R24-8), and examples, which is broken on purpose, is not scanned. The guard for the fix is a step in the selftest action job that runs uses dot over action, plugin and python with the committed baselines and must pass, and a test that reads that step's inputs out of selftest.yml and runs them offline as a pair: they pass, and the same paths without the baselines are red. Mutants red: a baseline entry removed, the baseline input removed from the workflow step. The CI step itself proves only on GitHub. |
| R24-5 | low | 2.7 | the framework run under its own Action, fixing R24-4 | closed | mcp_server handle_line returns None on a failed notification and on a successful one. Banked, not fixed: JSON-RPC forbids any reply to a notification, so None is the only correct return for both, and the failure is told on the log line just above it, the one place a notification's failure can be told. This is the exact example conflated_degrade_lint's own docstring gives of a conflation to bank. A comment at the site says why. Entries for the source and its byte-identical plugin copy. |
| R24-6 | low | 2.7 | the framework run under its own Action, fixing R24-4 | closed | detectors _module_exports returns None when a module does not parse and when it star-re-exports. Banked, not fixed: to its one caller both mean the imported names cannot be checked, and the parse failure is not silent, because the same detector run reports every file under the root that does not parse as its own violation in the same list. Docstring at the site says so. The residual is R24-17. |
| R24-7 | med | 6.3 | the outside review of v0.6.0 before its tag | fixed | The pipe check flagged a case pattern with an alternation bar and a double-bracket test whose regex holds an alternation bar, as pipes that swallow an exit code; neither is a pipeline in bash, and both are ordinary CI shell. Fixed: a bar between double brackets is blanked, with the closing brackets required to stand as their own word so a bracket class cannot end the test early, and case state is carried across the lines of a step so only a pattern list's bars, up to its closing paren, are blanked. A pattern list with no closing paren on its line blanks nothing, so doubt errs toward flagging. True positives kept: the pipe-and-ampersand form, a pipe after pipefail is turned off, a pipe in a case clause's command, a pipe after the closing brackets. Pairs in the tests, a new pair in the selfcheck, and corpus case ci-pipe-case-pattern-and-regex, whose clean twin the sweep runs forever; the declared case count moves from 54 to 55 with it. Mutants red on the masking call, the clause-end state, the double-bracket blanking and the command-position lookbehind. |
| R24-8 | low | 2.7 | the framework run under its own Action, fixing R24-4 | closed | swallow_lint flags the selfcheck wrapper in rounds, framework_only, budget, obsgate and mcp_server, and in their byte-identical plugin copies: ten sites of one shape, an except that prints SELFCHECK FAILED with the exception's type to stderr and returns False. Banked, not fixed: False is the selfcheck's failure verdict, not an empty result a success could also return, and the print names whose failure it is (6.8). The lint reads print as no handling, which is R24-10, deferred. Ten per-file counts in the swallow baseline. |
| R24-9 | low | 6.3 | the outside review of v0.6.0 before its tag | deferred | A run scalar written as a YAML quoted string holding a pipe into tail is not flagged by the pipe check, a false negative. Deferred: the step reader would need a YAML string reader, and a release fix that guesses at quoting risks the false positives R24-7 just removed. |
| R24-10 | low | 2.7 | the outside review of v0.6.0 before its tag | deferred | swallow_lint flags explicit degradation that runs through a counter, an attribute, traceback print_exc or warnings warn, and its allow-call option is not an Action input. Deferred: widening what counts as handling widens what a real swallow can hide behind, and wants corpus pairs before it lands. R24-8's banked sites are this shape. |
| R24-11 | med | 2.7 | the outside review of v0.6.0 before its tag | deferred | swallow_lint misses an except that assigns an empty literal and falls through, a return nested below the handler's first level, and contextlib suppress. Deferred: three new detection shapes, each owed a corpus case before it ships, not a release-branch change. |
| R24-12 | med | 2.8 | the outside review of v0.6.0 before its tag | deferred | interpolation_lint misses a query built by plus concatenation, by join, and by string Template. Deferred for the same reason as R24-11: detection shapes owed corpus cases first. |
| R24-13 | low | 2.7 | the outside review of v0.6.0 before its tag | deferred | conflated_degrade_lint flags narrow handlers whose exception type already says what failed. Deferred: whether a narrow type makes a None distinguishable to the caller is a design question, not a release fix. |
| R24-14 | low | 2.6 | the outside review of v0.6.0 before its tag | deferred | interpolation_lint scans an in-tree virtualenv whose directory name is not in its vendor list, reporting third-party findings as the adopter's. Deferred to the vendor-list review. |
| R24-15 | low | 2.8 | the outside review of v0.6.0 before its tag | deferred | The Action refuses a paths input holding non-ASCII letters or a space. Deferred: the narrow set is what keeps a shell metacharacter from ever reaching a guard, and widening it needs its own proof that it still does. |
| R24-16 | low | 6.9 | the outside review of v0.6.0 before its tag | deferred | The conflated-degrade annotation carries the guard's last line, which is its advice sentence, not the finding it is about. Deferred: the sentence a guard leads with is a per-guard contract change. |
| R24-17 | low | 2.7 | reading R24-6 | deferred | A relative import that climbs above the scanned root to a module that does not parse is skipped by the import detector with no violation, because that module is outside the walk that reports parse failures. Deferred: rare, and the fix changes the detector's output for adopters' banked baselines. |
| R24-18 | low | 7.2 | the outside review of v0.6.0 before its tag | deferred | The README says plugin guards are pinned byte for byte more broadly than sync_guards pins them. Deferred to the post-release docs pass with the next item. |
| R24-19 | low | 1.4 | the outside review of v0.6.0 before its tag | deferred | No doc sentence says what the Action does on a fork pull request or under pull_request_target, where the workspace is the pull request's code with the base's secrets. Deferred to the post-release docs pass; the Action itself reads no secret. |
| R24-20 | low | 2.9 | an earlier pass over the guards | deferred | budget.py exits 0 with nothing to check when its design-notes directory is missing. The Action already refuses that case for an opt-in budget guard; the CLI and the pre-commit path still read it as a pass. Deferred: changing the CLI's exit is an adopter-visible contract change. |
| R24-21 | low | 2.9 | an earlier pass over the guards | deferred | rounds.py check skips rule-id validation when there is no DOCTRINE.md beside the records, and says so only in passing. Deferred with R24-20, the same contract question. |

## Deliberately not done

- No lint rule was weakened to make R24-4 pass. Every banked finding is in a
  baseline the ratchet still checks, at `.github/sutradhar/`, outside the
  root locations the guards honour by default, so neither the planted-tree
  run nor an adopter's run can pick it up.
- The draft release notes are outside this repository and were not edited.
  Their corpus paragraph needs the sentence R24-2 made true: the total is
  declared in `corpus/case_count.json`, and a deletion that does not lower
  it fails the run.
- R24-1's escaping covers the step summary, which GitHub renders as
  markdown. Annotations render as plain text and were already escaped as
  workflow-command data; they were not changed.

## Ruled out, and why

- Deciding a crash from stderr rather than from the merged output. Guards
  write findings that name adopter files to stderr as well, so stderr is
  as forgeable as stdout. Only the exit code is the guard's alone, and
  `classify` no longer takes the output at all.
- Wrapping the summary text in a code span instead of escaping it. Inert in
  plain CommonMark, but a code span still ends a table cell at a bar and
  needs a fence longer than any backtick run in the text; per-character
  escaping has neither edge.
- A `--expect-cases N` flag carried only in the CI step. The reviewer's
  repro, run without it, would still have read 51 of 51 and passed. The
  declaration is a file every full run reads; the flag only refuses its
  absence.
