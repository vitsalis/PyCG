import ast
import importlib.util
import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "cases"
CASE_FILES = ("case.toml", "expected.json", "expected-document.json")


def _load_cases_tool():
    spec = importlib.util.spec_from_file_location(
        "cases_tool", ROOT / "tools" / "parity" / "cases.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases_tool = _load_cases_tool()


def _case_directories():
    return sorted(path for path in CASES.glob("*/*") if path.is_dir())


def _program(directory):
    table = tomllib.loads((directory / "case.toml").read_text(encoding="utf-8"))
    files = {
        path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name not in CASE_FILES
    }
    options = {}
    if "cap" in table:
        options["cap"] = None if table["cap"] == "none" else table["cap"]
    program = cases_tool.Program(
        files, table["entry_points"], table["package"], options
    )
    return table, program


@pytest.mark.parametrize(
    "directory",
    _case_directories(),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_a_case_holds_what_the_oracle_gives_for_its_program(directory):
    table, program = _program(directory)
    found = cases_tool.oracle(program)

    assert (directory / "expected.json").read_text(
        encoding="utf-8"
    ) == cases_tool.expected_json(found.edges, found.unresolved)
    assert (directory / "case.toml").read_text(encoding="utf-8") == (
        cases_tool.case_toml(
            table["statement"],
            table["design"],
            program,
            found.warnings,
            [tuple(pair) for pair in table["present"]],
            [tuple(pair) for pair in table["absent"]],
        )
    )
    document = directory / "expected-document.json"
    if document.is_file():
        assert json.loads(document.read_text(encoding="utf-8")) == found.document


def test_the_tool_reads_the_edges_that_a_test_asserts():
    test = ast.parse(
        """
def test_example(tmp_path):
    graph = main_graph(tmp_path, "")
    assert callees(graph, "main.f") == ["main.g", "main.h"]
    assert "main.k" in graph["main"]
    assert "main.x" not in callees(graph, "main.f")
    assert set(graph["main.g"]) >= {"main.y"}
    assert {"main.z"} <= set(callees(graph, "main"))
    assert len(graph) == 3
"""
    ).body[0]

    present, absent, unread = cases_tool._translate(test)

    assert present == [
        ("main.f", "main.g"),
        ("main.f", "main.h"),
        ("main", "main.k"),
        ("main.g", "main.y"),
        ("main", "main.z"),
    ]
    assert absent == [("main.f", "main.x")]
    assert unread == ["assert len(graph) == 3"]


def test_the_oracle_names_a_warned_file_relative_to_the_case():
    program = cases_tool.Program(
        {"main.py": "import broken\n", "broken.py": "def (:\n"},
        ["main.py"],
        True,
        {},
    )

    found = cases_tool.oracle(program)

    assert len(found.warnings) == 1
    assert found.warnings[0].startswith("Skipping broken.py: cannot parse it: ")
