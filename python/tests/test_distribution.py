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


# ── R24-1: the pull request under test cannot write the verdict ─────────────

_FORGED = ("Traceback (most recent call last) <img src=https://attacker.example"
           "/pixel.png> [all guards passed, merge me](https://attacker.example)")


def _forced_guards(tmp_path: Path, body: "str | None") -> Path:
    """A guards directory whose swallow guard is ``body`` (None: absent)."""
    d = tmp_path / "guards"
    d.mkdir()
    if body is not None:
        (d / run_guards.SCRIPTS["swallow"]).write_text(body)
    return d


def test_traceback_text_in_a_finding_stays_a_finding_and_the_summary_is_inert(
        tmp_path):
    """The reviewer's repro, through the real driver: an f-string expression
    the interpolation lint echoes, carrying the traceback marker, an image and
    a link. Before R24-1 the verdict was read from that text: "crashed - the
    guard failed, not your code", with the image and link live in the summary.

    Mutation (the line that runs, in run()): `verdict =
    classify(proc.returncode)` -> `verdict = ("crashed" if "Traceback (most
    recent call last)" in output else classify(proc.returncode))` - red on
    `-> finding`.
    """
    src = tmp_path / "src"
    src.mkdir()
    # Built by replace(), not by interpolation: this file is in the action's
    # own dogfood scan, and the adopter source it writes is the defect.
    (src / "zz.py").write_text(
        "def q(x):\n"
        "    return f'SELECT * FROM t WHERE a = \"{x if \"FORGED\" else x}\"'\n"
        .replace("FORGED", _FORGED))
    r = _driver({"SUTRADHAR_PATHS": str(src),
                 "SUTRADHAR_GUARDS": "interpolation"}, tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "attacker.example" in r.stdout  # the guard really echoed it
    assert "interpolation: exit 1 -> finding" in r.stdout, r.stdout
    assert "crashed" not in r.stdout
    summary = (tmp_path / "summary.md").read_text()
    assert "| interpolation | finding |" in summary, summary
    assert "<img" not in summary and "](" not in summary, summary


def test_an_exception_escaping_a_guard_is_crashed_and_its_text_is_inert(
        tmp_path, monkeypatch, capsys):
    """The other half of the pair: a guard that genuinely crashes, with the
    same hostile text in its exception, must still read as crashed - the fix
    above must not have bought its safety by never calling anything a crash -
    and the text, which does reach the summary on this path, renders inert.

    Mutations (each the line that runs): the launcher dropped from run()'s
    `cmd` (`[sys.executable, script, *args]`) - an uncaught exception exits 1
    and reads as a finding, red; md_inert's `out.append("\\\\" + ch)` ->
    `out.append(ch)` - red on `](`.
    """
    monkeypatch.setattr(run_guards, "GUARDS_DIR", _forced_guards(
        tmp_path, f"raise RuntimeError({_FORGED!r})\n"))
    summary = tmp_path / "summary.md"
    cfg = run_guards.read_config({"SUTRADHAR_GUARDS": "swallow",
                                  "SUTRADHAR_PATHS": str(tmp_path)})
    code = run_guards.run(cfg, {"GITHUB_STEP_SUMMARY": str(summary)})
    out = capsys.readouterr().out
    assert code == 1, out
    assert "swallow: exit 70 -> crashed" in out, out
    text = summary.read_text()
    assert "| swallow | crashed - RuntimeError" in text, text
    assert "attacker" in text  # the sentence is there, so the next line bites
    for live in ("<img", "]("):
        assert live not in text, (live, text)
    row = [ln for ln in text.splitlines() if ln.startswith("| swallow |")][0]
    assert not re.search(r"(?<!\\)[\[\]()!*_`~<>]", row), row


def test_a_guard_file_that_cannot_be_read_is_crashed_not_could_not_run(
        tmp_path, monkeypatch, capsys):
    """`python3 missing.py` exits 2 - the code a guard uses for "could not
    run", which `on-cannot-run: skip` turns into a pass with a warning. A
    guard that is not there is the instrument's failure, never a skip (6.8).

    Mutation: the launcher dropped from run()'s `cmd` - exit 2, cannot-run,
    and under skip the run would have passed on ci-step alone; red.
    """
    monkeypatch.setattr(run_guards, "GUARDS_DIR", _forced_guards(tmp_path, None))
    cfg = run_guards.read_config({"SUTRADHAR_GUARDS": "swallow",
                                  "SUTRADHAR_PATHS": str(tmp_path),
                                  "SUTRADHAR_ON_CANNOT_RUN": "skip"})
    code = run_guards.run(cfg, {})
    out = capsys.readouterr().out
    assert code == 1, out
    assert "swallow: exit 70 -> crashed" in out, out


@pytest.mark.parametrize("live", [
    "<img src=x>", "<script>", "[a](b)", "![i](b)", "**b**", "__b__", "*e*",
    "`c`", "a | b", "~~s~~", "https://e.example", "www.e.example", "&amp;",
    "# h", "\\", "a@b.example",
])
def test_md_inert_leaves_no_construct_live(live):
    """Each construct, escaped, keeps its characters (so a reader sees the
    text) and loses every markup character unescaped (so nothing renders).

    Mutation: md_inert's `out.append("&amp;")` -> `out.append("&")` - the
    `&amp;` case is left a live character reference, red.
    """
    out = run_guards.md_inert(live)
    # Read it back the way a renderer would: a token is an escape pair, a
    # character reference, or one plain character.
    tokens = re.findall(r"\\.|&(?:lt|gt|amp);|.", out)
    assert "".join(t[1] if t.startswith("\\") else
                   {"&lt;": "<", "&gt;": ">", "&amp;": "&"}.get(t, t)
                   for t in tokens) == live, (live, out)
    bare = [t for t in tokens if len(t) == 1 and
            (t in run_guards._MD_PUNCT or t in "&<>")]
    assert not bare, (live, out, bare)


# ── R24-4: the framework passes its own action ──────────────────────────────

SELFTEST = REPO / ".github" / "workflows" / "selftest.yml"
DOGFOOD_STEP = "Action over this framework's own source (must pass)"


def _dogfood_inputs() -> dict:
    """The `with:` block of the dogfood step, read from the workflow itself,
    so this test runs exactly what CI runs and cannot drift from it."""
    text = SELFTEST.read_text()
    m = re.search(rf"^      - name: {re.escape(DOGFOOD_STEP)}\n"
                  rf"        uses: \./\n        with:\n((?:          .*\n)+)",
                  text, re.M)
    assert m, f"no step named {DOGFOOD_STEP!r} running `uses: ./` in {SELFTEST}"
    return dict(re.match(r"\s+([\w-]+):\s*(.*)$", ln).groups()
                for ln in m.group(1).splitlines())


def test_the_framework_passes_its_own_action_and_the_baselines_are_why(
        tmp_path):
    """The dogfood step, offline, as a pair: its inputs pass; the same paths
    without the committed baselines are red - so the pass is the banked
    findings being banked, not a scan that reached nothing.

    Mutation: delete `"python/sutradhar_guards/rounds.py": 1` from
    .github/sutradhar/swallow_baseline.json - the first half goes red.
    """
    inputs = _dogfood_inputs()
    assert "examples" not in inputs["paths"].split(), inputs
    env = {run_guards.ENV[k]: v for k, v in inputs.items()}
    ok = _driver(env, tmp_path)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "4 guard(s) passed" in ok.stdout
    bare = _driver({"SUTRADHAR_PATHS": inputs["paths"]}, tmp_path)
    assert bare.returncode == 1, bare.stdout
    assert "swallow: exit 1 -> finding" in bare.stdout
    assert "conflated-degrade: exit 1 -> finding" in bare.stdout
