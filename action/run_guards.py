#!/usr/bin/env python3
# Copyright 2026 Varun Mundra. Licensed under the Apache License, Version 2.0.
# Part of Sutradhar: https://github.com/sutradharhq/sutradhar
"""Run Sutradhar's guards for the GitHub Action (`action.yml` at the root).

`action.yml` is a composite action with one step: it hands every input to
this script through an environment variable and runs it with the runner's
`python3`. Nothing here goes through a shell. An input is never pasted into
a `run:` body - that is the Actions injection hole, and doctrine 2.8's shape
in YAML - and every guard is started as an argument list, so a value cannot
become a command whatever it holds. A value that looks like a shell
metacharacter or a flag where a path belongs is still refused, because it is
far more likely a mistake than a path, and a mistake read as a path scans
the wrong tree and says OK.

What runs by default, with no configuration:

    swallow            swallow_lint.py over PATHS          (2.7)
    interpolation      interpolation_lint.py over PATHS    (2.8)
    conflated-degrade  conflated_degrade_lint.py over PATHS (2.7)
    ci-step            ci_step_lint.py over WORKFLOWS      (6.3, 6.7)

Opt in by naming them in `guards`: `budget` (needs a design-notes directory
and a tests directory, 1.1) and `rounds` (needs round records, 8.1).
`framework_only` and `framework_shape` are refused by name: they gate a
promise only the Sutradhar repository makes, and in an adopter's tree they
can only ever pass (R20-4). A gate that cannot fail is decoration (3.7).

Every guard exits 0 clean, 1 a finding, 2 could not run. Read here as:

    0                  pass
    1                  finding - fails the job
    2                  could not run - fails the job unless
                       on-cannot-run is `skip`, and is never silent
    anything else, or 1/2 with a Python traceback in the output:
                       crashed - fails the job whatever on-cannot-run says.
                       A crash is the instrument's failure, not a verdict
                       about the code (6.8, 6.11), and it is named as such.

`on-cannot-run` defaults to `fail`, because a job that goes green when a
guard read nothing is the R21-2 lie (an OK over zero files) told one level
up. `skip` exists for a tree where a guard deliberately has nothing to read;
each skip still prints the guard's own sentence, raises a warning annotation
and a row in the step summary, and a run in which every selected guard was
skipped fails anyway - nothing was checked, and that is not a pass (2.9).

Usage (the action sets these; locally you can too):

    SUTRADHAR_PATHS=src python3 action/run_guards.py
    python3 action/run_guards.py --selfcheck

Exit 0 every guard that ran passed, 1 a finding or a crashed guard, 2 the
run could not be made: an input refused, or a guard could not run under
`on-cannot-run: fail`, or nothing at all was checked.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

GUARDS_DIR = Path(__file__).resolve().parent.parent / "python" / "sutradhar_guards"

#: name -> script. The order is the order they run in.
SCRIPTS = {
    "swallow": "swallow_lint.py",
    "interpolation": "interpolation_lint.py",
    "conflated-degrade": "conflated_degrade_lint.py",
    "ci-step": "ci_step_lint.py",
    "budget": "budget.py",
    "rounds": "rounds.py",
}
DEFAULT_GUARDS = ("swallow", "interpolation", "conflated-degrade", "ci-step")
OPT_IN_GUARDS = ("budget", "rounds")

#: Named so the refusal can say why, instead of "unknown guard".
REFUSED_GUARDS = {
    "framework-only": "framework_only.py",
    "framework_only": "framework_only.py",
    "framework-shape": "framework_shape.py",
    "framework_shape": "framework_shape.py",
}

#: name -> environment variable action.yml sets. One table, so the test that
#: every declared input reaches this script reads the same names this does.
ENV = {
    "guards": "SUTRADHAR_GUARDS",
    "paths": "SUTRADHAR_PATHS",
    "workflows": "SUTRADHAR_WORKFLOWS",
    "on-cannot-run": "SUTRADHAR_ON_CANNOT_RUN",
    "swallow-baseline": "SUTRADHAR_SWALLOW_BASELINE",
    "conflated-degrade-baseline": "SUTRADHAR_CONFLATED_DEGRADE_BASELINE",
    "interpolation-allowlist": "SUTRADHAR_INTERPOLATION_ALLOWLIST",
    "interpolation-keywords": "SUTRADHAR_INTERPOLATION_KEYWORDS",
    "design-dir": "SUTRADHAR_DESIGN_DIR",
    "tests-dir": "SUTRADHAR_TESTS_DIR",
    "rounds-dir": "SUTRADHAR_ROUNDS_DIR",
}
DEFAULTS = {
    "guards": ",".join(DEFAULT_GUARDS),
    "paths": ".",
    "workflows": ".github/workflows",
    "on-cannot-run": "fail",
    "swallow-baseline": "",
    "conflated-degrade-baseline": "",
    "interpolation-allowlist": "",
    "interpolation-keywords": "",
    "design-dir": "docs/design",
    "tests-dir": "tests",
    "rounds-dir": "docs/rounds",
}

#: A path is letters, digits, and `. _ / -`, and does not start with `-`.
#: Narrow on purpose: everything outside it is either a shell metacharacter
#: or a character no repository path needs, and the refusal names it.
_PATH_RX = re.compile(r"[A-Za-z0-9._/][A-Za-z0-9._/-]*")
_KEYWORDS_RX = re.compile(r"[A-Za-z][A-Za-z ,]*")
_TRACEBACK = "Traceback (most recent call last)"


class Refused(Exception):
    """An input this script will not act on. Exit 2, with the reason."""


def _say(msg: str) -> None:
    print(f"[sutradhar-action] {msg}", flush=True)


def _escape_data(s: str) -> str:
    """GitHub workflow-command data escaping (%, CR, LF)."""
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(s: str) -> str:
    """Workflow-command property escaping: data's, plus `:` and `,`."""
    return _escape_data(s).replace(":", "%3A").replace(",", "%2C")


def check_path(name: str, value: str) -> str:
    """Return ``value`` if it is a plain relative-or-absolute path, else raise.

    A leading `-` is refused as well as the metacharacters: a path of
    `--update-baseline` would reach the guard as a flag and rewrite the
    adopter's baseline instead of checking against it.
    """
    if _PATH_RX.fullmatch(value):
        return value
    bad = sorted({c for c in value if not re.fullmatch(r"[A-Za-z0-9._/-]", c)})
    if value.startswith("-"):
        why = "starts with '-', so a guard would read it as a flag"
    else:
        why = f"contains {' '.join(repr(c) for c in bad)}"
    raise Refused(
        f"input `{name}` value {value!r} {why}. A path here is letters, "
        f"digits, '.', '_', '/' and '-', not starting with '-'; nothing was "
        f"run."
    )


def read_config(environ: "dict[str, str]") -> dict:
    """Inputs from the environment, validated. Raises Refused."""
    raw = {k: environ.get(v, DEFAULTS[k]).strip() for k, v in ENV.items()}

    names = [g for g in re.split(r"[\s,]+", raw["guards"]) if g]
    if not names:
        raise Refused("input `guards` is empty; name at least one guard. "
                      "Nothing was run.")
    guards: list = []
    for g in names:
        if g in REFUSED_GUARDS:
            raise Refused(
                f"guard `{g}` is not offered: {REFUSED_GUARDS[g]} gates a "
                f"promise only the Sutradhar repository makes, and in your "
                f"tree it can only ever pass (R20-4). Nothing was run."
            )
        if g not in SCRIPTS:
            raise Refused(
                f"unknown guard `{g}`. Default: {', '.join(DEFAULT_GUARDS)}; "
                f"opt-in: {', '.join(OPT_IN_GUARDS)}. Nothing was run."
            )
        if g not in guards:
            guards.append(g)

    policy = raw["on-cannot-run"]
    if policy not in ("fail", "skip"):
        raise Refused(
            f"input `on-cannot-run` is {policy!r}; it is `fail` or `skip`. "
            f"Nothing was run."
        )

    paths = [check_path("paths", p) for p in raw["paths"].split()]
    if not paths:
        raise Refused("input `paths` is empty; name the directory that "
                      "holds your Python source. Nothing was run.")

    single = {}
    for key in ("workflows", "swallow-baseline", "conflated-degrade-baseline",
                "interpolation-allowlist", "design-dir", "tests-dir",
                "rounds-dir"):
        v = raw[key]
        if len(v.split()) > 1:
            raise Refused(f"input `{key}` names more than one path: {v!r}. "
                          f"Nothing was run.")
        single[key] = check_path(key, v) if v else ""

    # A baseline or allowlist the adopter NAMED must be there. A typo would
    # otherwise run the ratchet against an empty floor and nobody would know
    # which file had been meant.
    for key in ("swallow-baseline", "conflated-degrade-baseline",
                "interpolation-allowlist"):
        if single[key] and not Path(single[key]).is_file():
            raise Refused(f"input `{key}` names {single[key]}, which is not "
                          f"a file. Nothing was run.")

    kw = raw["interpolation-keywords"]
    if kw and not _KEYWORDS_RX.fullmatch(kw):
        raise Refused(f"input `interpolation-keywords` is {kw!r}; it is a "
                      f"comma-separated list of words such as `sql,cypher`. "
                      f"Nothing was run.")

    return {"guards": guards, "policy": policy, "paths": paths,
            "keywords": kw, **single}


def plan(cfg: dict) -> list:
    """[(guard, argv-after-script, could-not-run sentence or None)]."""
    out = []
    for g in cfg["guards"]:
        pre = None
        if g == "swallow":
            args = list(cfg["paths"])
            if cfg["swallow-baseline"]:
                args += ["--baseline", cfg["swallow-baseline"]]
        elif g == "interpolation":
            args = list(cfg["paths"])
            if cfg["keywords"]:
                args += ["--keywords", cfg["keywords"].replace(" ", "")]
            if cfg["interpolation-allowlist"]:
                args += ["--allowlist", cfg["interpolation-allowlist"]]
        elif g == "conflated-degrade":
            args = list(cfg["paths"])
            if cfg["conflated-degrade-baseline"]:
                args += ["--baseline", cfg["conflated-degrade-baseline"]]
        elif g == "ci-step":
            args = [cfg["workflows"] or DEFAULTS["workflows"]]
        elif g == "budget":
            design, tests = cfg["design-dir"], cfg["tests-dir"]
            args = [design, "--tests", tests]
            # budget.py says "nothing to check" and exits 0 over a missing
            # notes directory - right for a hook that runs everywhere, wrong
            # for a guard the adopter asked for by name. Checked here.
            missing = [p for p in (design, tests) if not p or not Path(p).is_dir()]
            if missing:
                pre = (f"budget was asked for, and not a directory: "
                       f"{', '.join(repr(m) for m in missing)}; set "
                       f"`design-dir` and `tests-dir`. Nothing was checked.")
        elif g == "rounds":
            args = [cfg["rounds-dir"] or DEFAULTS["rounds-dir"], "--check"]
        else:  # read_config refuses unknown names; this is a seam, not a path
            raise Refused(f"no plan for guard {g!r}")
        out.append((g, args, pre))
    return out


def classify(code: int, output: str) -> str:
    """pass | finding | cannot-run | crashed."""
    if _TRACEBACK in output:
        return "crashed"
    return {0: "pass", 1: "finding", 2: "cannot-run"}.get(code, "crashed")


def _last_sentence(output: str) -> str:
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return lines[-1] if lines else "(the guard printed nothing)"


def run(cfg: dict, environ: "dict[str, str]") -> int:
    results = []  # (guard, verdict, sentence)
    for guard, args, pre in plan(cfg):
        print(f"::group::sutradhar {guard}", flush=True)
        if pre is not None:
            print(pre, flush=True)
            verdict, sentence, output = "cannot-run", pre, pre
        else:
            cmd = [sys.executable, str(GUARDS_DIR / SCRIPTS[guard]), *args]
            _say("$ " + " ".join(cmd[1:]))
            proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
            # Captured apart, not merged: a guard writes its refusal to
            # stderr at once and its selfcheck line to a buffered stdout, so
            # a merged stream's last line is the selfcheck, and the
            # annotation quoted "selfcheck ok" as the reason a guard could
            # not run. The sentence is stderr's last line when there is one.
            output = proc.stdout + proc.stderr
            # The guard's output quotes the adopter's source (an f-string
            # expression, a path). Stop workflow commands around it, so a
            # line in the code under test cannot speak to the runner.
            token = secrets.token_hex(16)
            print(f"::stop-commands::{token}", flush=True)
            for stream in (proc.stdout, proc.stderr):
                if stream:
                    print(stream, end="" if stream.endswith("\n") else "\n",
                          flush=True)
            print(f"::{token}::", flush=True)
            verdict = classify(proc.returncode, output)
            sentence = (_last_sentence(proc.stderr) if proc.stderr.strip()
                        else _last_sentence(proc.stdout))
            _say(f"{guard}: exit {proc.returncode} -> {verdict}")
        print("::endgroup::", flush=True)
        results.append((guard, verdict, sentence))

    policy = cfg["policy"]
    lines = []
    for guard, verdict, sentence in results:
        if verdict == "pass":
            continue
        if verdict == "cannot-run" and policy == "skip":
            level, label = "warning", "skipped: could not run"
        elif verdict == "cannot-run":
            level, label = "error", "could not run (on-cannot-run: fail)"
        elif verdict == "crashed":
            level, label = "error", "crashed - the guard failed, not your code"
        else:
            level, label = "error", "finding"
        title = _escape_property(f"sutradhar {guard} - {label}")
        print(f"::{level} title={title}::"
              f"{_escape_data(sentence)}", flush=True)
        lines.append((guard, label, sentence))

    ran = [r for r in results if r[1] in ("pass", "finding")]
    bad = [r for r in results if r[1] in ("finding", "crashed")]
    blocked = [r for r in results if r[1] == "cannot-run"]

    if bad:
        code, headline = 1, f"{len(bad)} guard(s) red"
    elif blocked and policy == "fail":
        code, headline = 2, (f"{len(blocked)} guard(s) could not run, and "
                             f"on-cannot-run is `fail`")
    elif not ran:
        code, headline = 2, ("every selected guard was skipped: nothing was "
                             "checked, and that is not a pass (2.9)")
    else:
        code, headline = 0, (f"{len(ran)} guard(s) passed"
                             + (f", {len(blocked)} skipped (could not run)"
                                if blocked else ""))
    _say(headline)

    summary = environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        rows = ["### Sutradhar guards", "", f"**{headline}**", "",
                "| guard | verdict |", "| --- | --- |"]
        for guard, verdict, sentence in results:
            label = {"cannot-run": f"could not run - {sentence}",
                     "crashed": f"crashed - {sentence}"}.get(verdict, verdict)
            rows.append(f"| {guard} | {label.replace('|', '/')} |")
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
    return code


def selfcheck() -> bool:
    """Each refusal and each verdict word, with a case it must get right."""
    problems = []

    def refused(env: dict) -> bool:
        try:
            read_config(env)
        except Refused:
            return True
        return False

    for bad in ("src; rm -rf /", "$(id)", "a`b`", "src|tee", "--update-baseline",
                "src\nfoo && bar"):
        if not refused({"SUTRADHAR_PATHS": bad}):
            problems.append(f"path {bad!r} was accepted")
    for ok in ("src", "app/core ./lib", "."):
        if refused({"SUTRADHAR_PATHS": ok}):
            problems.append(f"plain path {ok!r} was refused")
    if not refused({"SUTRADHAR_GUARDS": "swallow,framework_shape"}):
        problems.append("framework_shape was accepted as a guard")
    if not refused({"SUTRADHAR_GUARDS": "swalow"}):
        problems.append("a misspelled guard was accepted")
    if not refused({"SUTRADHAR_ON_CANNOT_RUN": "ignore"}):
        problems.append("on-cannot-run accepted a third value")
    cfg = read_config({})
    if cfg["guards"] != list(DEFAULT_GUARDS) or cfg["policy"] != "fail":
        problems.append(f"defaults drifted: {cfg['guards']} {cfg['policy']}")

    tb = f"{_TRACEBACK}:\n  File \"x.py\"\nKeyError: 'k'\n"
    for (code, out), want in (((0, "ok"), "pass"), ((1, "found"), "finding"),
                              ((2, "nothing was scanned"), "cannot-run"),
                              ((1, tb), "crashed"), ((2, tb), "crashed"),
                              ((127, ""), "crashed"), ((-9, ""), "crashed")):
        got = classify(code, out)
        if got != want:
            problems.append(f"exit {code} classified {got!r}, not {want!r}")

    for p in problems:
        print(f"[sutradhar-action] SELFCHECK FAILED: {p}")
    if not problems:
        print("[sutradhar-action] selfcheck ok: metacharacter and flag-shaped "
              "paths refused, plain paths accepted, framework-only gates and "
              "unknown guards refused, defaults are the four source/CI guards "
              "with on-cannot-run fail, a traceback reads as crashed rather "
              "than a finding")
    return not problems


def main(argv: "list | None" = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--selfcheck"]:
        return 0 if selfcheck() else 1
    if argv:
        print(f"[sutradhar-action] takes no arguments (inputs arrive as "
              f"environment variables) or --selfcheck; got {argv}",
              file=sys.stderr)
        return 2
    if sys.version_info < (3, 9):
        print(f"[sutradhar-action] python3 is {sys.version.split()[0]}; the "
              f"guards need 3.9 or newer. Nothing was run.", file=sys.stderr)
        return 2
    try:
        cfg = read_config(dict(os.environ))
    except Refused as exc:
        print(f"::error title=sutradhar - input refused::"
              f"{_escape_data(str(exc))}", flush=True)
        print(f"[sutradhar-action] {exc}", file=sys.stderr)
        return 2
    return run(cfg, dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
