import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "tools_check", Path(__file__).resolve().parents[1] / "tools" / "check.py"
)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


@pytest.mark.parametrize(
    ("changed", "names"),
    [
        ([], ["lint"]),
        (["README.md", "docs/design.md", "docs/format.md"], ["lint"]),
        (["pycg/analysis/solver.py"], ["lint", "engine"]),
        (["tools/generate_stubs.py"], ["lint", "engine"]),
        (["tests/unit/test_mro.py"], ["lint", "engine"]),
        (["tests/known_failures.txt"], ["lint", "engine"]),
        (["tests/test_micro_benchmark.py"], ["lint", "micro"]),
        (["tests/test_benchmark_validator.py"], ["lint", "micro"]),
        (
            ["evaluation/micro-benchmark/snippets/classes/call/main.py"],
            ["lint", "micro"],
        ),
        (["evaluation/micro-benchmark/validate.py"], ["lint", "micro", "evaluation"]),
        (["evaluation/common/gate.py"], ["lint", "evaluation"]),
        (["AGENTS.md"], ["lint", "evaluation"]),
        (["pyproject.toml"], ["lint", "engine", "evaluation"]),
        (["uv.lock"], ["lint", "engine", "evaluation"]),
        (["Makefile", ".github/workflows/ci.yml"], ["lint"]),
        (
            [
                "pycg/pycg.py",
                "evaluation/micro-benchmark/README.md",
                "evaluation/README.md",
            ],
            ["lint", "engine", "micro", "evaluation"],
        ),
    ],
)
def test_a_change_runs_the_checks_of_what_it_touches(changed, names):
    assert check.scoped(changed) == names


@pytest.mark.parametrize(
    "path",
    [
        "pycg/pycg.py",
        "evaluation/micro-benchmark/snippets/a/b/callgraph.json",
        "evaluation/metrics.json",
        "tools/check.py",
        "tests/known_failures.txt",
        "pyproject.toml",
        "uv.lock",
        "Makefile",
        ".github/workflows/ci.yml",
    ],
)
def test_a_change_that_can_move_the_metrics_runs_the_evaluation(path):
    needed, lines = check.detect_eval(["README.md", path], "origin/main")
    assert needed and lines[1:] == [f"- `{path}`"]


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/design.md",
        "AGENTS.md",
        "tests/unit/test_mro.py",
        "tests/known_failures.txt.orig",
        "pycg-notes.md",
        "Makefile.local",
    ],
)
def test_another_change_skips_the_evaluation(path):
    needed, lines = check.detect_eval([path], "origin/main")
    assert not needed and lines[0].startswith("### Evaluation: skipped")


def test_an_unreadable_diff_runs_the_evaluation():
    needed, lines = check.detect_eval(None, "origin/nowhere")
    assert needed and "unreadable" in lines[0]


def test_an_unknown_base_leaves_the_diff_unreadable():
    assert check.changed_files("refs/heads/no-such-branch-of-pycg") is None


def test_the_diff_has_the_changes_and_the_untracked_files(monkeypatch):
    answers = {
        ("merge-base", "base", "HEAD"): ["abc"],
        ("diff", "--no-renames", "--name-only", "abc"): ["pycg/a.py", "b.md"],
        ("ls-files", "--others", "--exclude-standard"): ["new.py", "b.md"],
    }
    monkeypatch.setattr(check, "git", lambda *args: answers[args])
    assert check.changed_files("base") == ["b.md", "new.py", "pycg/a.py"]
    answers[("ls-files", "--others", "--exclude-standard")] = None
    assert check.changed_files("base") is None


def test_detect_eval_appends_its_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check, "changed_files", lambda base: ["docs/design.md"])
    outputs = tmp_path / "outputs"
    outputs.write_text("other=1\n")
    assert check.main(["--base", "x", "--detect-eval", str(outputs)]) == 0
    assert outputs.read_text() == "other=1\neval=false\n"
    assert capsys.readouterr().out.startswith("### Evaluation: skipped")


def test_a_failed_check_prints_its_output_and_fails_the_run(monkeypatch, capsys):
    monkeypatch.setattr(check, "changed_files", lambda base: [])
    monkeypatch.setattr(
        check, "CHECKS", {"lint": (sys.executable, "-c", "print('bad'); exit(1)")}
    )
    assert check.main(["--base", "x"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("lint         FAIL") and "bad" in out
