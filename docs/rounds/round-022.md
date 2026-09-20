# Round 22 - 2026-09-20

Lenses: the demo's denominator, the scorer for the improvement loop

**What this round was.** The mechanism for the framework's own improvement
loop: a defect corpus with a scorer that cannot be gamed by deleting cases
or by counting its own iterations. Two findings fell out of reading the
demo while designing it - the "7 of 7" is a loop counter, and every planted
defect is declared twice in two places that disagree. Both are fixed here
with the mechanism in the same commit. Two more findings are deferred with
their open cases named, so the deferral is a pointer rather than a shrug.

## Findings

| id | severity | rule | found-by | status | summary |
|---|---|---|---|---|---|
| R22-1 | high | 3.7 | reading run-the-guards.sh while designing the corpus | fixed | The demo's "7 of 7" is a loop counter, not a declared total: deleting a whole block yields "6 of 6" and exit 0, and only a string pin in test_examples.py holds the number. The corpus takes its denominator from the manifest set, and a deletion-sensitive test pins the total. |
| R22-2 | med | 8.2 | the same read | fixed | Each planted defect is declared twice, in the source comment and in the script, and the two numberings disagree. A manifest removes the second copy: one file per case, twins and prose together. |
| R22-3 | med | 6.3 | auditing ci_step_lint's scope | deferred | No guard checks a workflow for a pipe that swallows an exit code; 6.3 is convention-only. Seeded as an open corpus case (ci-pipe-swallows-exit-code) in the wave-1 batch. |
| R22-4 | low | 1.1 | reading budget.py's enforcement detector | deferred | The budget gate proves a test MENTIONS an id, not that it asserts. Re-states R1-8 from the corpus side; the corpus budget test asserts genuinely, the gate itself stays text-match until a round pays for more. |

## Corrected premises

- **"The demo counts its defects."** It counts its own blocks. A denominator
  that comes from control flow is a promise the code makes to itself; the
  corpus counts files on disk, which is a promise the tree can check.
- **"Mentioning a budget id enforces it."** The gate matches text, so a test
  that names the id without asserting anything passes it. The corpus budget
  test runs the work at the declared N inside the envelope - mention plus
  measurement, because the gate only checks the mention.
