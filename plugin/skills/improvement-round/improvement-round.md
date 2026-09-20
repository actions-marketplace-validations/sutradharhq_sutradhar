# Skill: improvement round - one mechanized step of the self-improving loop

Hand this file to the agent verbatim ("run one improvement round") on the
Monday schedule, ahead of the weekly review. One round proposes ONE
candidate guard, proves it on the defect corpus, and commits to a local
branch for human review. It never pushes.

What stays human, permanently: scars come from reality, merges are
reviewed, doctrine prose lands via backflow decisions. After this skill
ships, the claim is "the loop is mechanized except reality and review",
never "autonomous self-improvement".

The ground rules live in `robustness-loop.md` in this same directory -
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
python scripts/rounds.py docs/rounds/ --floors .
```

- On `REST`, propose pruning or corpus work, NOT new guards.
- On `INSUFFICIENT`, say so and stop. A round that cannot read its own
  stop rule has nothing to steer by.

## Phase 0b - one in flight at a time

Refuse to start if the previous round's branch is unreviewed. Two
candidate branches means two competing claims about the same corpus,
and the review cannot hold both in its head at once.

## Phase 1 - pick the target, in one sentence

Read the corpus `open`/`MISSED` list (`corpus.py corpus/`), the residual
register, and the backflow register. Pick the highest-yield target and
say why in one sentence: the rule with no case, the open case closest
to a guard, or the MISSED case whose guard exists but does not catch.

## Phase 2 - author the case from the scar prose

Write the manifest in `corpus/cases/` following `corpus/README.md`:
frontmatter, defective/clean twins, helper fences before the twins,
engineering vocabulary only. Then:

```bash
python scripts/corpus.py corpus/ --case <new-case-id>
```

It must score MISSED before the guard exists. If it scores anything
else, the case is wrong, not early - fix the twins, not the verdict.

## Phase 3 - write the guard, run the four-command gate

Selection is composed, not built - four commands, four exit codes,
accept only on `0 / 0 / 0 / 0`:

```bash
python3 python/sutradhar_guards/corpus.py corpus/ --case <new-case-id>
python3 python/sutradhar_guards/corpus.py corpus/ --sweep <guard-name>
python3 python/sutradhar_guards/verify_guard.py --repo . --commit HEAD \
  --guard-cmd "python3 -m pytest python/tests/<new-test>.py -q"
python3 python/sutradhar_guards/corpus.py corpus/
```

The second command is the cross-case sweep: the guard over EVERY clean
twin, which catches a guard that flags everything. The third proves the
guard red on the revert. The fourth holds the denominator and the
coverage floor.

## Phase 4 - commit locally with the evidence quoted

One commit on a local branch: the case, the guard, the updated floor
files if the coverage partition moved. The message quotes the gate's
four exit codes and the mutation that showed the guard red. Never push:
the maintainer runs the gates, does their own mutation at the runtime
seam, and pushes.

## Phase 5 - memo, even when quiet

Write the round memo to `docs/rounds/` in the house format either way.
A round that proposed nothing records what it read, what it ruled out,
and why - un-recorded dead ends get re-explored at full price.
