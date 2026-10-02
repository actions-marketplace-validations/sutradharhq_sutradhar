# Copyright 2026 Varun Mundra. Licensed under the Apache License, Version 2.0.
# Part of Sutradhar: https://github.com/sutradharhq/sutradhar
"""The two one-line adoption paths: `action.yml` and `.pre-commit-hooks.yaml`.

Both are files a stranger's tooling reads from a clone of this repository,
so their failures land in someone else's CI and never in ours. What can be
pinned offline is pinned here; the GitHub half (the action actually running
on a runner) is the `action` job in .github/workflows/selftest.yml.

No YAML library: the repository ships stdlib only. The action's `run:`
bodies are read with ci_step_lint's own scanner - the reader this repo
already trusts for workflows - and the rest with line patterns over files
whose shape this repository controls. Each test's docstring names the
mutation that was shown to turn it red.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sutradhar_guards import ci_step_lint as csl  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ACTION = REPO / "action.yml"
HOOKS = REPO / ".pre-commit-hooks.yaml"
DRIVER = REPO / "action" / "run_guards.py"
CLEAN = REPO / "python" / "tests" / "fixtures" / "action-clean"
PLANTED = REPO / "examples" / "broken-app" / "app"

#: Gates on a promise only this repository makes; in an adopter's tree they
#: can only pass (R20-4).
FRAMEWORK_ONLY_GATES = {"framework_only.py", "framework_shape.py"}

sys.path.insert(0, str(DRIVER.parent))
import run_guards  # noqa: E402


def _hooks() -> list:
    """[{key: value}] per `- id:` block, values as written."""
    hooks, cur = [], None
    for raw in HOOKS.read_text().splitlines():
        if raw.startswith("#") or not raw.strip():
            continue
        m = re.match(r"^(- )?\s*([\w-]+):\s*(.*)$", raw)
        assert m, f"unreadable line in {HOOKS.name}: {raw!r}"
        if m.group(1):
            cur = {}
            hooks.append(cur)
        cur[m.group(2)] = m.group(3).strip()
    return hooks


def _action_inputs() -> dict:
    """{input name: default} from the top-level `inputs:` block."""
    text = ACTION.read_text()
    block = re.search(r"^inputs:\n(.*?)^\S", text, re.S | re.M).group(1)
    names = re.findall(r"^  ([\w-]+):\s*$", block, re.M)
    defaults = {}
    for name in names:
        part = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\s*$|\Z)",
                         block, re.S | re.M).group(1)
        m = re.search(r"^    default:\s*(.*)$", part, re.M)
        defaults[name] = m.group(1).strip().strip("'\"") if m else None
    return defaults


def _driver(env_extra: dict, tmp_path: Path):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("SUTRADHAR_", "GITHUB_"))}
    env.update(env_extra)
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    return subprocess.run([sys.executable, str(DRIVER)], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=120)


# ── pre-commit ──────────────────────────────────────────────────────────────

def test_every_pre_commit_hook_entry_is_a_committed_executable_file():
    """`language: script` runs the entry file itself from pre-commit's clone,
    so a missing file or a 0644 mode is a hook that fails for every adopter
    with "is not executable" - and never in this repository's own suite.

    Mutation: `chmod -x python/sutradhar_guards/swallow_lint.py` - red.
    """
    hooks = _hooks()
    assert len(hooks) >= 4, hooks  # an empty parse would pass vacuously
    for h in hooks:
        entry = REPO / h["entry"].split()[0]
        assert entry.is_file(), f"{h['id']}: {h['entry']} does not exist"
        assert os.access(entry, os.X_OK), (
            f"{h['id']}: {h['entry']} is not executable; pre-commit's script "
            f"language cannot run it"
        )
        first = entry.read_text().splitlines()[0]
        assert first == "#!/usr/bin/env python3", (h["id"], first)


def test_every_pre_commit_hook_installs_nothing():
    """A `python` hook makes pre-commit pip-install this repository, which
    needs a setup.py or pyproject.toml - a dependency manifest this framework
    refuses to ship (framework_only.py). `script` runs the file as it is.

    Mutation: `language: script` -> `language: python` on the swallow hook - red.
    """
    for h in _hooks():
        assert h["language"] == "script", (h["id"], h["language"])


def test_no_hook_runs_a_gate_only_this_repository_can_fail():
    """framework_only and framework_shape gate this repository's promise; in an
    adopter's tree they can only pass, which is decoration (R20-4, 3.7).

    Mutation: the ci-step hook's entry -> framework_shape.py - red.
    """
    for h in _hooks():
        assert Path(h["entry"]).name not in FRAMEWORK_ONLY_GATES, h


# ── the action ──────────────────────────────────────────────────────────────

def test_the_action_is_composite_and_runs_its_own_driver_with_python3():
    """No Docker, no npm, no install step: a composite action whose one step
    runs a file that exists in this checkout, from the action's own path.

    Mutation: rename action/run_guards.py in the `run:` line to run_guard.py - red.
    """
    text = ACTION.read_text()
    assert re.search(r"^runs:\n  using: composite$", text, re.M)
    bodies = [b for _, _, b in csl.steps(text)]
    assert len(bodies) == 1, bodies
    m = re.fullmatch(r'python3 "\$\{GITHUB_ACTION_PATH\}/([\w/.-]+\.py)"',
                     bodies[0].strip())
    assert m, bodies[0]
    assert (REPO / m.group(1)).is_file(), f"{m.group(1)} does not exist"


def test_no_run_body_in_the_action_interpolates_an_expression():
    """`${{ inputs.x }}` inside `run:` is pasted into the script before the
    shell parses it: an input of `x"; curl ... #` is a command. Every value
    reaches the step through `env:` instead (2.8).

    Mutation: append ` ${{ inputs.paths }}` to the `run:` line - red.
    """
    bodies = [b for _, _, b in csl.steps(ACTION.read_text())]
    assert bodies, "no run: step read - the check below would be vacuous"
    for body in bodies:
        assert "${{" not in body, body


def test_every_action_input_reaches_the_driver():
    """An input declared and never read is a control with no effect (3.1): an
    adopter sets it, nothing changes, and the run says OK.

    Mutation: delete the SUTRADHAR_ROUNDS_DIR line from action.yml's env - red.
    """
    inputs = _action_inputs()
    assert set(inputs) == set(run_guards.ENV), (
        sorted(set(inputs) ^ set(run_guards.ENV)))
    text = ACTION.read_text()
    for name, var in run_guards.ENV.items():
        assert re.search(rf"^\s+{var}: \$\{{\{{ inputs\.{re.escape(name)} \}}\}}$",
                         text, re.M), f"{name} does not reach {var}"


def test_the_action_defaults_are_the_drivers_defaults():
    """Two places hold each default; they must say the same thing, or the
    README documents one behaviour and the runner does another.

    Mutation: action.yml `on-cannot-run` default `fail` -> `skip` - red.
    """
    assert _action_inputs() == run_guards.DEFAULTS


def test_no_default_guard_is_a_gate_only_this_repository_can_fail():
    """Same rule as the hooks, through the driver's own table.

    Mutation: append "framework-shape" to DEFAULT_GUARDS and map it to
    framework_shape.py in SCRIPTS - red.
    """
    for g in run_guards.DEFAULT_GUARDS:
        assert run_guards.SCRIPTS[g] not in FRAMEWORK_ONLY_GATES, g
        assert (run_guards.GUARDS_DIR / run_guards.SCRIPTS[g]).is_file(), g


def test_the_driver_selfcheck_passes():
    """Mutation: `_PATH_RX` widened to `.+` - the selfcheck goes red, as below."""
    assert run_guards.selfcheck()


# ── the driver, through its real seam (2.3) ─────────────────────────────────

def test_the_planted_tree_fails_and_its_clean_twin_passes(tmp_path):
    """A pair (6.7): the same inputs but `paths`, so the red is the planted
    defects and not the action failing at everything.

    Mutation: `classify` returns "pass" for exit 1 - the planted half goes red.
    """
    bad = _driver({"SUTRADHAR_PATHS": str(PLANTED.relative_to(REPO))}, tmp_path)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert "readings.py:23" in bad.stdout and "{device_id}" in bad.stdout
    good = _driver({"SUTRADHAR_PATHS": str(CLEAN.relative_to(REPO))}, tmp_path)
    assert good.returncode == 0, good.stdout + good.stderr
    assert "4 guard(s) passed" in good.stdout


def test_a_shell_command_where_a_path_belongs_is_refused_and_runs_nothing(tmp_path):
    """Mutation: `_PATH_RX` widened to `.+` - the refusal disappears, red."""
    r = _driver({"SUTRADHAR_PATHS": "src; touch x"}, tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "contains ';'" in r.stderr
    assert "::group::" not in r.stdout  # no guard was started


def test_a_flag_where_a_path_belongs_is_refused(tmp_path):
    """`--update-baseline` as a path would rewrite the adopter's floor.

    Mutation: drop the leading-`-` exclusion from `_PATH_RX` - red.
    """
    r = _driver({"SUTRADHAR_PATHS": "--update-baseline"}, tmp_path)
    assert r.returncode == 2 and "starts with '-'" in r.stderr, r.stderr


def test_could_not_run_fails_by_default_and_is_a_named_skip_when_asked(tmp_path):
    """Exit 2 is never a silent pass (2.9). Under `fail` it fails the run;
    under `skip` it passes only because another guard ran, and the skip is
    named with the guard's own sentence - not its selfcheck line.

    Mutation: the `blocked and policy == "fail"` branch's code 2 -> 0 - red.
    """
    nopy = {"SUTRADHAR_PATHS": "docs/design"}
    fail = _driver(nopy, tmp_path)
    assert fail.returncode == 2, fail.stdout
    skip = _driver({**nopy, "SUTRADHAR_ON_CANNOT_RUN": "skip"}, tmp_path)
    assert skip.returncode == 0, skip.stdout + skip.stderr
    warnings = [ln for ln in skip.stdout.splitlines() if ln.startswith("::warning")]
    assert len(warnings) == 3, warnings
    assert all("nothing was scanned" in w for w in warnings), warnings
    assert "skipped" in (tmp_path / "summary.md").read_text()


def test_a_run_where_every_guard_was_skipped_fails_even_under_skip(tmp_path):
    """Mutation: the `not ran` branch's code 2 -> 0 - red."""
    r = _driver({"SUTRADHAR_PATHS": "docs/design", "SUTRADHAR_GUARDS": "swallow",
                 "SUTRADHAR_ON_CANNOT_RUN": "skip"}, tmp_path)
    assert r.returncode == 2, r.stdout
    assert "nothing was checked" in r.stdout


@pytest.mark.parametrize("name", ["framework_shape", "framework-only"])
def test_a_framework_only_gate_is_refused_by_name(tmp_path, name):
    """Refused, and the refusal says why - "unknown guard" would leave an
    adopter guessing whether a spelling would fix it.

    Mutation: `if g in REFUSED_GUARDS:` -> `if False:` in read_config - the
    name falls through to "unknown guard" with no R20-4, red."""
    r = _driver({"SUTRADHAR_GUARDS": name}, tmp_path)
    assert r.returncode == 2 and "R20-4" in r.stderr, r.stderr


def test_an_opt_in_budget_with_no_design_notes_cannot_run(tmp_path):
    """budget.py itself exits 0 with "nothing to check" over a missing notes
    directory; asked for by name, that is a check that never ran.

    Mutation: `if missing:` -> `if False:` in plan()'s budget branch - red.
    """
    tests = {"SUTRADHAR_GUARDS": "budget", "SUTRADHAR_TESTS_DIR": "python/tests"}
    r = _driver({**tests, "SUTRADHAR_DESIGN_DIR": "no/such"}, tmp_path)
    assert r.returncode == 2, r.stdout
    assert "not a directory: 'no/such';" in r.stdout
    # The other half of the pair: this repository's own notes and tests run
    # the real guard to a pass, so the refusal above is not refusing budget.
    ok = _driver({**tests, "SUTRADHAR_DESIGN_DIR": "docs/design"}, tmp_path)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "[budget] OK" in ok.stdout
