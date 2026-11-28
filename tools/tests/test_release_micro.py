import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


micro = load("release_micro", ROOT / "tools" / "release" / "micro.py")

FAKE_PROGRAM = """\
import json
import sys
from pathlib import Path

arguments = sys.argv[1:]
package = Path(arguments[arguments.index("--package") + 1])
output = Path(arguments[arguments.index("-o") + 1])
behaviour = (package / "BEHAVIOUR").read_text().strip()
if behaviour == "stops":
    print("pycg: not ported: a rule", file=sys.stderr)
    sys.exit(3)
callee = "main.g" if behaviour == "calls g" else "main.h"
document = {
    "format": "pycg/1",
    "definitions": {
        "main": {"kind": "module"},
        "main.g": {"kind": "function"},
        "main.h": {"kind": "function"},
    },
    "outside": {},
    "calls": {"main": [{"callees": [callee]}]},
}
output.write_text(json.dumps(document))
"""
EXPECTED = {"main": ["main.g"], "main.g": [], "main.h": []}


def snippet(snippets, name, behaviour, requires=None):
    case = snippets / name
    case.mkdir(parents=True)
    (case / "main.py").write_text("")
    (case / "BEHAVIOUR").write_text(behaviour)
    (case / "callgraph.json").write_text(json.dumps(EXPECTED))
    if requires is not None:
        (case / "requires-python").write_text(f"{requires}\n")


def run(tmp_path, capsys, cases, known):
    snippets = tmp_path / "snippets"
    for name, behaviour, requires in cases:
        snippet(snippets, name, behaviour, requires)
    failures = tmp_path / "known_failures.txt"
    failures.write_text(
        "# notes\n" + "".join(f"{name}: stream: a reason\n" for name in known)
    )
    program = tmp_path / "pycg"
    program.write_text(f"#!{sys.executable}\n{FAKE_PROGRAM}")
    program.chmod(0o755)
    status = micro.main(
        [str(program), "--snippets", str(snippets), "--known-failures", str(failures)]
    )
    return status, capsys.readouterr().out.splitlines()


def test_cases_that_agree_and_known_failures_that_differ_pass(tmp_path, capsys):
    status, lines = run(
        tmp_path,
        capsys,
        [
            ("a/agrees", "calls g", None),
            ("a/known", "calls h", None),
            ("a/newer", "calls h", "3.15"),
            ("a/older", "calls g", "3.14"),
        ],
        ["a/known"],
    )
    assert status == 0
    assert lines == [
        "skipped a/newer: needs Python 3.15",
        "micro: 4 cases, 2 agree, 1 known failures, 1 skipped, 0 failed",
    ]


def test_a_difference_an_agreeing_known_failure_and_a_stop_fail(tmp_path, capsys):
    status, lines = run(
        tmp_path,
        capsys,
        [
            ("a/differs", "calls h", None),
            ("a/fixed", "calls g", None),
            ("a/stops", "stops", None),
        ],
        ["a/fixed"],
    )
    assert status == 1
    assert lines == [
        "FAILED a/differs: the call graph differs",
        "FAILED a/fixed: a known failure agrees",
        "FAILED a/stops: the program failed: exit 3: pycg: not ported: a rule",
        "micro: 3 cases, 0 agree, 0 known failures, 0 skipped, 3 failed",
    ]
