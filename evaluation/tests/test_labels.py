"""Behaviour tests for evaluation/common/labels.py: which pull requests get
`metrics-changed` and `benchmark-changed`. Hand-made results and paths."""

import importlib.util
import json
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "evaluation_labels", EVALUATION / "common" / "labels.py"
)
labels = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(labels)


def counts(tp, fp, fn):
    return {"tp": tp, "fp": fp, "fn": fn, "precision": 0.5, "recall": 0.5}


def result(micro=(10, 1, 2), inside=(20, 3, 4), outside=(30, 5, 6)):
    return {
        "micro": {"total": {"raw": {"all": counts(*micro)}}},
        "macro": {
            "summed": {"raw": {"inside": counts(*inside), "outside": counts(*outside)}}
        },
    }


@pytest.mark.parametrize(
    "path",
    [
        "evaluation/macro-benchmark/ground-truth/jmespath.ledger",
        "evaluation/macro-benchmark/ground-truth/jmespath.json",
        "evaluation/macro-benchmark/dynamic/h11.json",
        "evaluation/macro-benchmark/projects.toml",
        "evaluation/macro-benchmark/test-environments/bottle.txt",
        "evaluation/common/same_function.json",
        "micro-benchmark/snippets/classes/call/callgraph.json",
        "micro-benchmark/snippets/a/b/c/callgraph.json",
        "micro-benchmark/snippets/callgraph.json",
        "tests/known_failures.txt",
        "evaluation/metrics.json",
        ".github/workflows/ci.yml",
    ],
)
def test_a_protected_path_is_protected(path):
    assert labels.protected(path)


@pytest.mark.parametrize(
    "path",
    [
        "pycg/pycg.py",
        "micro-benchmark/snippets/classes/call/main.py",
        "micro-benchmark/callgraph.json",
        "evaluation/macro-benchmark/projects.py",
        "evaluation/macro-benchmark/ground-truth",
        "evaluation/macro-benchmark/dynamic-notes.md",
        "evaluation/common/same_function.py",
        "evaluation/metrics.json.new",
        "tests/known_failures.txt.orig",
        "tests/triage.py",
        "docs/.github/x",
        "github/workflows/ci.yml",
    ],
)
def test_another_path_is_not_protected(path):
    assert not labels.protected(path)


def test_agents_md_lists_every_protected_path():
    text = (EVALUATION.parent / "AGENTS.md").read_text(encoding="utf-8")
    for pattern in labels.PROTECTED:
        assert f"`{pattern}`" in text, pattern


def test_equal_counts_change_no_metric():
    assert labels.decide(result(), result(), []) == ({}, [])


@pytest.mark.parametrize(
    ("changed", "name"),
    [
        ({"micro": (11, 1, 1)}, "micro"),
        ({"inside": (20, 4, 4)}, "macro inside"),
        ({"outside": (30, 5, 7)}, "macro outside"),
    ],
)
def test_a_changed_count_changes_the_metrics(changed, name):
    moved, touched = labels.decide(result(**changed), result(), [])
    assert list(moved) == [name] and touched == []


def test_only_protected_paths_of_the_diff_are_listed():
    changed = ["pycg/pycg.py", "evaluation/metrics.json", ".github/CODEOWNERS"]
    _, touched = labels.decide(result(), result(), changed)
    assert touched == [".github/CODEOWNERS", "evaluation/metrics.json"]


def test_the_command_writes_the_outputs_and_the_markdown(tmp_path, capsys):
    paths = {}
    for name, data in (("pr", result(micro=(11, 1, 1))), ("base", result())):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data))
    changed = tmp_path / "changed.txt"
    changed.write_text("pycg/pycg.py\n")
    outputs = tmp_path / "outputs"
    argv = [str(paths["pr"]), str(paths["base"]), str(changed), str(outputs)]
    assert labels.main(argv) == 0
    assert outputs.read_text() == "metrics-changed=true\nbenchmark-changed=false\n"
    out = capsys.readouterr().out
    assert "  - micro: 10/1/2 -> 11/1/1" in out
    assert "- `benchmark-changed`: no (no protected file changed)" in out
