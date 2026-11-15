"""Compare the call graph of each micro-benchmark snippet with its expectation.

Every directory ``micro-benchmark/snippets/<category>/<name>/`` is one case:
PyCG analyses its ``main.py`` and the result must equal ``callgraph.json``.
"""

import json
from pathlib import Path

import pytest

from pycg import utils
from pycg.pycg import CallGraphGenerator

SNIPPETS = Path(__file__).resolve().parent.parent / "micro-benchmark" / "snippets"

# Cases that fail because of known limitations of the analysis. The marks are
# strict: when a case starts to pass, the suite fails until its entry is removed.
KNOWN_FAILURES = {
    "assignments/starred": "starred unpacking not modelled",
    "builtins/map": "calls through map() not modelled",
    "classes/static_method_call": "decorator call to builtin staticmethod missed",
    "builtins/types": "methods of builtin types not modelled",
    "decorators/assigned": "flow-insensitive: keeps both decorators bound to the name",
    "decorators/nested_decorators": "stacked decorators: misses the outer wrapper",
    "decorators/return_different_func": "decorated call goes to function, not wrapper",
    "dicts/assign": "flow-insensitive: keeps the overwritten dict value",
    "dicts/nested": "flow-insensitive: keeps the overwritten nested dict value",
    "dicts/update": "dict.update() not modelled",
    "dynamic/eval": "eval() of a string not analysed",
    "kwargs/chained_call": "spurious func2 -> func2 through shared parameters",
    "lists/slice": "list slices not modelled",
    "mro/super_call": "super() not modelled",
}


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
        cases.append(pytest.param(path, id=case_id, marks=marks))
    return cases


CASES = snippet_cases()


def sorted_edges(call_graph):
    return {node: sorted(targets) for node, targets in call_graph.items()}


@pytest.mark.parametrize("snippet", CASES)
def test_call_graph(snippet):
    generator = CallGraphGenerator(
        [str(snippet / "main.py")], str(snippet), -1, utils.constants.CALL_GRAPH_OP
    )
    generator.analyze()

    expected = json.loads((snippet / "callgraph.json").read_text())
    assert sorted_edges(generator.output()) == sorted_edges(expected)


def test_known_failures_are_existing_cases():
    assert set(KNOWN_FAILURES) <= {case.id for case in CASES}
