import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "triage", Path(__file__).resolve().parents[2] / "tests" / "triage.py"
)
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)

CAUSES = {
    "a/known": ("flow/dead-code", "reason a"),
    "a/fixed": ("flow/rebinding", "reason b"),
    "a/newer_python": ("language/new-syntax", "reason c"),
}


def test_a_listed_failure_keeps_its_line():
    result = triage.select(["a/known"], [], {"a/known"}, CAUSES, set())
    assert result.listed == ["a/known"]
    assert not result.regressed and not result.untriaged


def test_a_case_that_passes_now_is_left_out():
    result = triage.select([], [], {"a/known"}, CAUSES, set())
    assert result.listed == []
    assert result.passing == ["a/known"]


def test_a_case_that_was_fixed_and_fails_again_is_a_regression():
    result = triage.select(["a/fixed"], [], {"a/known"}, CAUSES, set())
    assert result.listed == []
    assert result.regressed == ["a/fixed"]


def test_a_regressed_case_comes_back_only_when_readmitted():
    result = triage.select(["a/fixed"], [], set(), CAUSES, {"a/fixed"})
    assert result.listed == ["a/fixed"]
    assert not result.regressed


def test_a_failing_case_without_a_cause_is_untriaged():
    result = triage.select(["a/new"], [], set(), CAUSES, set())
    assert result.listed == []
    assert result.untriaged == ["a/new"]


def test_readmitting_a_case_without_a_cause_does_not_list_it():
    result = triage.select(["a/new"], [], set(), CAUSES, {"a/new"})
    assert result.listed == []
    assert result.untriaged == ["a/new"]


def test_a_case_this_interpreter_cannot_run_keeps_its_line():
    result = triage.select([], ["a/newer_python"], {"a/newer_python"}, CAUSES, set())
    assert result.listed == ["a/newer_python"]


def test_a_case_this_interpreter_cannot_run_is_not_added():
    result = triage.select([], ["a/newer_python"], set(), CAUSES, set())
    assert result.listed == []


def test_the_exit_status_fails_on_a_regression_or_an_untriaged_case():
    assert triage.select(["a/known"], [], {"a/known"}, CAUSES, set()).ok
    assert not triage.select(["a/fixed"], [], set(), CAUSES, set()).ok
    assert not triage.select(["a/new"], [], set(), CAUSES, set()).ok


def test_the_committed_list_has_a_cause_for_every_line():
    listed = triage.read_listed(triage.KNOWN_FAILURES)
    assert listed <= set(triage.CASES)
