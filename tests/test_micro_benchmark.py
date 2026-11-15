"""Compare the call graph of each micro-benchmark snippet with its expectation.

Every directory ``micro-benchmark/snippets/<category>/<name>/`` is one case:
PyCG analyses its ``main.py`` and the result must equal ``callgraph.json``.
"""

import json
import sys
from pathlib import Path

import pytest

from pycg.pycg import CallGraphGenerator

SNIPPETS = Path(__file__).resolve().parent.parent / "micro-benchmark" / "snippets"

KNOWN_FAILURES_FILE = Path(__file__).resolve().parent / "known_failures.txt"


def read_known_failures(path):
    """Read `<case id>: <reason>` lines; blank lines and `#` comments are skipped."""
    failures = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            case_id, reason = line.split(": ", 1)
            failures[case_id] = reason
    return failures


# Cases that fail because of known limitations of the analysis. The marks are
# strict: when a case starts to pass, the suite fails until its line is removed.
KNOWN_FAILURES = read_known_failures(KNOWN_FAILURES_FILE)


def version_skip_reason(case):
    """Why the interpreter cannot run the case (its `requires-python`), or None."""
    path = case / "requires-python"
    if not path.is_file():
        return None
    version = path.read_text().strip()
    if sys.version_info >= tuple(int(part) for part in version.split(".")):
        return None
    return f"needs Python {version}"


def snippet_cases():
    cases = []
    for path in sorted(path for path in SNIPPETS.glob("*/*") if path.is_dir()):
        case_id = f"{path.parent.name}/{path.name}"
        marks = []
        if case_id in KNOWN_FAILURES:
            reason = KNOWN_FAILURES[case_id]
            marks.append(
                pytest.mark.xfail(raises=AssertionError, strict=True, reason=reason)
            )
        if skip_reason := version_skip_reason(path):
            marks.append(pytest.mark.skip(reason=skip_reason))
        cases.append(pytest.param(path, id=case_id, marks=marks))
    return cases


CASES = snippet_cases()


def sorted_edges(call_graph):
    return {node: sorted(targets) for node, targets in call_graph.items()}


@pytest.mark.parametrize("snippet", CASES)
def test_call_graph(snippet):
    generator = CallGraphGenerator([str(snippet / "main.py")], str(snippet))
    generator.analyze()

    expected = json.loads((snippet / "callgraph.json").read_text())
    assert sorted_edges(generator.output()) == sorted_edges(expected)


def test_known_failures_are_existing_cases():
    assert set(KNOWN_FAILURES) <= {case.id for case in CASES}


def test_case_that_needs_a_newer_python_is_skipped(tmp_path):
    assert version_skip_reason(tmp_path) is None
    (tmp_path / "requires-python").write_text("3.12\n")
    assert version_skip_reason(tmp_path) is None
    (tmp_path / "requires-python").write_text("99.1\n")
    assert version_skip_reason(tmp_path) == "needs Python 99.1"
