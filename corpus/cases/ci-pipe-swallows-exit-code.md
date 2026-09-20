---
case: ci-pipe-swallows-exit-code
guard: ci_step_lint
rule: 6.3
scar: R22-3
expected: open
---

A build piped through `tail` reports tail's exit code, and a failed
build reads as success. No guard checks a workflow for a pipe that
swallows an exit code; 6.3 is convention-only (R22-3). Both twins name
only reachable scripts, so the reachability guard stays silent on both
and this case scores MISSED: open, honestly measured, waiting on the
pipe check rather than on a fix to these files. The reachable script is
manifest data in the helper fence below - both twins name it, so the
reachability guard stays silent on both by construction.

```python path=scripts/ok.py
print("reachable")
```

## defective

```yaml path=workflows/ci.yml
name: ci
on: [push]
jobs:
  guards:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/ok.py src/ | tail -5
```

## clean

```yaml path=workflows/ci.yml
name: ci
on: [push]
jobs:
  guards:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/ok.py src/
```
