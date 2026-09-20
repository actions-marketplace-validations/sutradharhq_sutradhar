import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sutradhar_guards import corpus
from sutradhar_guards.corpus import (
    CAUGHT,
    FALSE_POSITIVE,
    INVALID,
    MISSED,
    CoverageError,
    CorpusError,
    coverage,
    load_cases,
    score,
)


def _manifest(case_id, guard="swallow_lint", rule="2.7", scar="distribution",
              expected="caught", defective="", clean="", extra="",
              scar_argument="synthetic case for the corpus machinery tests"):
    head = (
        "---\n"
        f"case: {case_id}\n"
        f"guard: {guard}\n"
        f"rule: {rule}\n"
        f"scar: {scar}\n"
    )
    if scar == "distribution":
        head += f"scar_argument: {scar_argument}\n"
    head += f"expected: {expected}\n{extra}---\n"
    return (
        head
        + "\n## defective\n\n```python path=app/units.py\n"
        + defective
        + "```\n\n## clean\n\n```python path=app/units.py\n"
        + clean
        + "```\n"
    )


SWALLOW = (
    "def latest_total(store):\n"
    "    try:\n"
    "        return store.fetch()\n"
    "    except Exception:\n"
    "        return {}\n"
)
PLAIN = (
    "def latest_total(store):\n"
    "    return store.fetch()\n"
)


def _write(root: Path, name: str, text: str) -> None:
    (root / "cases").mkdir(parents=True, exist_ok=True)
    (root / "cases" / name).write_text(text, encoding="utf-8")


def _run(argv: list) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = corpus.main(argv)
    return code, out.getvalue() + err.getvalue()


def _json_of(said: str) -> dict:
    last = [line for line in said.splitlines() if line.startswith("{")][-1]
    return json.loads(last)


def test_a_case_whose_defect_is_not_flagged_is_missed_not_caught(tmp_path):
    """Mutation: in score(), `if defective_rc in spec.catch_codes:` changed
    to `if True:` flips this case to CAUGHT and the exit to 0."""
    _write(tmp_path, "quiet.md",
           _manifest("quiet", defective=PLAIN, clean=PLAIN))
    code, said = _run([str(tmp_path), "--json"])
    assert code == 1
    assert _json_of(said)["cases"] == {"quiet": MISSED}


def test_a_guard_that_flags_the_clean_twin_is_a_false_positive_not_a_catch(
        tmp_path):
    """Mutation: scoring the defective twin first (catch before clean)
    reports this as CAUGHT; the clean side must be judged first."""
    _write(tmp_path, "loud.md",
           _manifest("loud", defective=SWALLOW, clean=SWALLOW))
    code, said = _run([str(tmp_path), "--json"])
    assert code == 1
    assert _json_of(said)["cases"] == {"loud": FALSE_POSITIVE}


def test_an_exit_2_from_a_guard_is_invalid_and_never_a_catch(tmp_path):
    """Mutation: treating any nonzero exit as a catch scores the defective
    twin below as CAUGHT. Exit 2 is out-of-partition (could not run), so
    the verdict is INVALID and the run exits 2, never 0 or 1.

    The defective twin names a metrics file that does not exist, which the
    real obsgate refuses with exit 3 (INCONCLUSIVE, party-attributed); the
    clean twin is satisfied and silent. Unit pins below cover the other
    out-of-partition codes a runner can return (timeout, spawn failure,
    signal)."""
    floor = '{"surfaces": [{"name": "units", "pattern": "units_up"}]}'
    metrics = 'units_up{device="a"} 1\n'
    text = (
        "---\ncase: unwitnessed\nguard: obsgate\nrule: 6.6\n"
        "scar: distribution\nscar_argument: synthetic case for the exit "
        "partition test\nexpected: caught\n---\n"
        "\n## defective\n\n```text path=floor.json\n" + floor + "\n```\n"
        "\n## clean\n\n```text path=floor.json\n" + floor + "\n```\n"
        "```text path=metrics.txt\n" + metrics + "```\n"
    )
    _write(tmp_path, "unwitnessed.md", text)
    code, said = _run([str(tmp_path), "--json"])
    assert code == 2
    assert _json_of(said)["cases"] == {"unwitnessed": INVALID}
    spec = corpus.GUARDS["obsgate"]
    fake = corpus.Case(id="x", guard="obsgate", rule="6.6", scars=(),
                       distribution=True, expected="caught", fixture=None,
                       options=(), defective=(), clean=(), helpers=(),
                       source="x")
    for rc in (2, 3, 124, 125, -9):
        assert score(fake, rc, 0, spec) == INVALID
        assert score(fake, 1, rc, spec) == INVALID


def test_the_denominator_comes_from_the_manifest_set_not_a_loop_counter(
        tmp_path):
    """Mutation: a `step += 1` loop counter as the denominator still prints
    "2 of 2" here, and prints "1 of 1" after the deletion in the next test -
    the pin is that the totals name the manifest set, so only the
    deletion-sensitive assertion below can tell them apart."""
    _write(tmp_path, "a.md", _manifest("a", defective=SWALLOW, clean=PLAIN))
    _write(tmp_path, "b.md", _manifest("b", defective=SWALLOW, clean=PLAIN))
    code, said = _run([str(tmp_path), "--json"])
    assert code == 0
    totals = _json_of(said)["totals"]
    assert totals == {"caught": 2, "expected_caught": 2, "open": 0,
                      "invalid": 0}


def test_deleting_a_case_file_changes_the_total_and_fails(tmp_path):
    """The pair to the denominator test: with one file gone the run must
    report "1 of 1", so a test pinning yesterday's total breaks instead of
    silently counting a smaller corpus as the same green."""
    _write(tmp_path, "a.md", _manifest("a", defective=SWALLOW, clean=PLAIN))
    _write(tmp_path, "b.md", _manifest("b", defective=SWALLOW, clean=PLAIN))
    _, said_before = _run([str(tmp_path), "--json"])
    (tmp_path / "cases" / "b.md").unlink()
    code, said_after = _run([str(tmp_path), "--json"])
    assert code == 0
    assert _json_of(said_before)["totals"]["expected_caught"] == 2
    assert _json_of(said_after)["totals"]["expected_caught"] == 1


def test_a_case_citing_a_scar_no_round_record_contains_is_refused(tmp_path):
    """Mutation: skipping scar resolution when --rounds is given loads this
    case and scores it; the refusal must happen at load, exit 2."""
    rounds = tmp_path / "rounds"
    rounds.mkdir()
    (rounds / "round-009.md").write_text(
        "# Round 9\n\n| R9-9 | low | 2.7 | x | fixed | y |\n")
    doctrine = tmp_path / "DOCTRINE.md"
    doctrine.write_text("**2.7 exceptions\n")
    _write(tmp_path, "orphan.md",
           _manifest("orphan", rule="2.7", scar="R99-9",
                     defective=SWALLOW, clean=PLAIN))
    code, said = _run([str(tmp_path), "--doctrine", str(doctrine),
                       "--rounds", str(rounds)])
    assert code == 2
    assert "R99-9" in said


def test_a_manifest_naming_an_unknown_guard_is_refused_with_exit_2(tmp_path):
    """Mutation: defaulting an unknown guard to a bare subprocess call
    would run whatever argv the manifest smuggled in - the registry owns
    every invocation shape, so the load refuses."""
    _write(tmp_path, "strange.md",
           _manifest("strange", guard="definitely_not_a_guard",
                     defective=SWALLOW, clean=PLAIN))
    code, said = _run([str(tmp_path)])
    assert code == 2
    assert "unknown guard" in said


def test_a_manifest_cannot_name_a_command(tmp_path):
    """The security pin (D2): the fixed frontmatter key set is what keeps a
    manifest from becoming a script. Mutation: adding `command` to the
    accepted keys loads this manifest and runs its twins."""
    text = _manifest("sneaky", defective=SWALLOW, clean=PLAIN)
    text = text.replace("expected: caught",
                        "expected: caught\ncommand: do_not_run_this")
    _write(tmp_path, "sneaky.md", text)
    code, said = _run([str(tmp_path)])
    assert code == 2
    assert "never a command" in said


def test_an_open_case_that_is_now_caught_demands_a_manifest_flip(tmp_path):
    """Mutation: scoring open cases as findings-free reports exit 0, and a
    guard that learned the defect never gets its manifest flipped."""
    _write(tmp_path, "learned.md",
           _manifest("learned", expected="open",
                     defective=SWALLOW, clean=PLAIN))
    code, said = _run([str(tmp_path)])
    assert code == 1
    assert "flip" in said


def test_an_empty_corpus_directory_is_refused_with_exit_2(tmp_path):
    """Mutation: returning "0 of 0" with exit 0 reports a trustworthy total
    over nothing measured (the run-the-guards.sh scar, R22-1)."""
    (tmp_path / "cases").mkdir()
    code, said = _run([str(tmp_path)])
    assert code == 2
    assert "no case files" in said
    assert str(tmp_path / "cases") in said


def test_a_rule_that_loses_its_last_case_fails_the_coverage_floor():
    """Mutation: a floor that treats "no case and no entry" as covered
    never demands the sentence. Direct unit on coverage(): rule 2.8 has
    neither a case nor a banked reason, so the floor must refuse."""
    case = corpus.Case(id="x", guard="swallow_lint", rule="2.7", scars=(),
                       distribution=True, expected="caught", fixture=None,
                       options=(), defective=(), clean=(), helpers=(),
                       source="x")
    with pytest.raises(CoverageError, match="2.8"):
        coverage([case], {"2.7", "2.8"}, {}, {})


def test_a_banked_uncovered_rule_that_gained_a_case_must_be_removed():
    """The guard-the-guard half of the ratchet: a floor entry that quietly
    stopped being uncovered must leave, or the floor stops meaning
    anything. Mutation: ignoring stale entries keeps this green."""
    case = corpus.Case(id="x", guard="swallow_lint", rule="2.7", scars=(),
                       distribution=True, expected="caught", fixture=None,
                       options=(), defective=(), clean=(), helpers=(),
                       source="x")
    with pytest.raises(CoverageError, match="no longer uncovered"):
        coverage([case], {"2.7"}, {}, {"2.7": "not yet"})


def test_load_refuses_a_case_id_that_is_not_the_filename(tmp_path):
    (tmp_path / "cases").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cases" / "right-name.md").write_text(
        _manifest("wrong-name", defective=SWALLOW, clean=PLAIN),
        encoding="utf-8")
    with pytest.raises(CorpusError, match="does not match the filename"):
        load_cases(tmp_path)


def test_every_registered_guard_builds_a_runnable_shape(tmp_path):
    """Mutation: changing a builder's arity (or a registry entry's kind)
    without updating its callers breaks every runner adapter at sweep
    time, long after the suite went green. This pins the contract:
    CLI builders return an argv starting at an existing guard file,
    runner builders return a script that parses."""
    import ast

    guards_home = Path(corpus.__file__).resolve().parent
    for name, spec in sorted(corpus.GUARDS.items()):
        if spec.kind == "cli":
            argv = spec.build(tmp_path, ())
            assert argv[1].endswith(f"{spec.module}.py")
            assert Path(argv[1]).is_file(), f"{name}: {argv[1]} is not a file"
            continue
        if spec.two_commit:
            with pytest.raises(corpus.CorpusError):
                spec.build(tmp_path, guards_home, (), None)
            script = spec.build(tmp_path, guards_home, (), "two_commit")
        else:
            script = spec.build(tmp_path, guards_home, (), None)
        ast.parse(script)
        assert spec.module in script, f"{name}: runner never names its guard"
