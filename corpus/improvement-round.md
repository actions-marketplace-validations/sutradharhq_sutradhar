# Skill: improvement round - one mechanized step of the self-improving loop

Hand this file to the agent verbatim ("run one improvement round") on the
Monday schedule, ahead of the weekly review. One round proposes ONE
candidate guard, proves it on the defect corpus, and commits to a local
branch for human review. It never pushes.

What stays human, permanently: scars come from reality, merges are
reviewed, doctrine prose lands via backflow decisions. After this skill
ships, the claim is "the loop is mechanized except reality and review",
never "autonomous self-improvement".

**Where this runs.** A checkout of this repository, from its root. Every
command below uses this repository's own paths. The corpus scorer does
not ship to adopters yet (a scorer with no cases can only ever refuse),
so neither does this skill: it lives beside the corpus, not in
`agent/skills/`, whose every file ships. Both move into the copy set
together, and the skill gets its plugin wrapper then.

The ground rules live in `agent/skills/robustness-loop.md` -
one worktree per agent, stage named files only, bounded waits, honest
labels, finish the scope. Read that file first if you have not run a
round before; this file does not restate it. Three rules are specific
to this loop and non-negotiable here:

1. Case before guard, always. Never author a case from guard output.
2. One candidate at a time. Commit locally, never push.
3. Write the round memo even when nothing was proposed (2.9: a quiet
   week says so explicitly, or silence reads as success).

## Phase 0 - read the stop rule first

```bash
python3 python/sutradhar_guards/rounds.py docs/rounds/ --floors .
```

- On `REST`, propose pruning or corpus work, NOT new guards.
- On `INSUFFICIENT`, say so and stop. A round that cannot read its own
  stop rule has nothing to steer by.
- If the report lists deletion candidates (8.1), read them before anything
  else: pruning a rule nobody cites is a round's worth of work on its own.

## Phase 0b - one in flight at a time

```bash
git branch --list 'improvement/*' --no-merged main
```

If that prints anything, stop: the previous round's branch is still
unreviewed. Two candidate branches are two competing claims about the same
corpus, and the review cannot hold both at once. Say which branch is
waiting and end the round with the memo (phase 5).

Otherwise create this round's branch in a worktree of its own:
`improvement/<YYYY-MM-DD>`.

## Phase 1 - pick the target, in one sentence

```bash
python3 python/sutradhar_guards/corpus.py corpus/ --rounds docs/rounds/ --backflow docs/backflow.md
```

Read its open/MISSED lines and its coverage line, then
`corpus/uncovered.json` (the queue: every uncovered rule with the case idea
it is waiting for), the residual register, and the backflow register.
Pick the highest-yield target and say why in one sentence: an open case
closest to a guard, a MISSED case whose guard exists but does not catch, or
an uncovered rule whose case idea is concrete enough to write today.

## Phase 2 - author the case from the scar prose

Write the manifest in `corpus/cases/` following `corpus/README.md`:
frontmatter, defective/clean twins, helper fences before the twins,
engineering vocabulary only. Author it from the rule's scar in
`DOCTRINE.md` and the finding it cites - never from what a guard prints.
Then:

```bash
python3 python/sutradhar_guards/corpus.py corpus/ --case <new-case-id>
```

It must score MISSED before the guard exists. If it scores anything
else, the case is wrong, not early - fix the twins, not the verdict.

## Phase 3 - write the guard, commit, then run the gate

Write the guard and its test. Commit them with the case on the round
branch first: `verify_guard` reverts a commit, so the gate needs one to
exist. A local branch is cheap to rewrite if the gate refuses.

Selection is composed, not built - four commands, four exit codes,
accept only on `0 / 0 / 0 / 0`:

```bash
python3 python/sutradhar_guards/corpus.py corpus/ --case <new-case-id>
python3 python/sutradhar_guards/corpus.py corpus/ --sweep <guard-name>
python3 python/sutradhar_guards/verify_guard.py --repo . --commit HEAD \
  --guard-cmd "python3 -m pytest python/tests/<new-test>.py -q"
python3 python/sutradhar_guards/corpus.py corpus/ --rounds docs/rounds/ --backflow docs/backflow.md
```

The second command is the cross-case sweep: the guard over EVERY clean
twin, which catches a guard that flags everything. The third proves the
guard red on the revert. The fourth holds the denominator and the
coverage floor; a rule the case newly covers must leave
`corpus/uncovered.json` in the same commit, or the floor refuses.

**A brand-new guard module only reverts to an import error.** When the
commit adds the module, `verify_guard` deletes it and the test dies at
collection - a red it reports as `VERIFIED (weak)`, because a crash is not
the named test failing. That proves the test imports the module, nothing
more. So also weaken the detection line itself (the line that RUNS, 2.2)
and show the test go red; that mutation is the evidence that counts.

## Phase 4 - record the evidence in the commit

Amend the round commit so its message quotes the gate's four exit codes
and the detection-line mutation that showed the guard red, with the
command that ran it. Never push: the maintainer runs the gates, does their
own mutation at the runtime seam, and pushes.

## Phase 5 - memo, even when quiet

Write the round memo to `docs/rounds/` in the house format either way.
A round that proposed nothing records what it read, what it ruled out,
and why - un-recorded dead ends get re-explored at full price.
