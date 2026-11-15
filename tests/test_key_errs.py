"""Compare the key errors found in each key-error snippet with its expectation.

Every directory ``micro-benchmark-key-errs/snippets/<category>/<name>/`` is one
case: PyCG analyses its ``main.py`` and the result must equal ``key_errs.json``.
"""

import json
from pathlib import Path

import pytest

from pycg import utils
from pycg.pycg import CallGraphGenerator

SNIPPETS = (
    Path(__file__).resolve().parent.parent / "micro-benchmark-key-errs" / "snippets"
)

# Cases that fail because of known limitations of the analysis. The marks are
# strict: when a case starts to pass, the suite fails until its entry is removed.
KNOWN_FAILURES = {
    "assignments/starred": "starred unpacking not modelled",
    "dicts/update": "dict.update() not modelled",
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


@pytest.mark.parametrize("snippet", CASES)
def test_key_errors(snippet):
    generator = CallGraphGenerator(
        [str(snippet / "main.py")], str(snippet), -1, utils.constants.KEY_ERR_OP
    )
    generator.analyze()

    expected = json.loads((snippet / "key_errs.json").read_text())
    assert generator.output_key_errs() == expected


def test_known_failures_are_existing_cases():
    assert set(KNOWN_FAILURES) <= {case.id for case in CASES}
