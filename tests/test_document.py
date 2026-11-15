"""The document that PyCG writes (docs/format.md): its parts, read through
`CallGraphGenerator.document()` and the command line."""

import ast
import inspect
import json
import logging
import re
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from pathlib import Path

import pytest
from programs import analysed, write
from test_micro_benchmark import SNIPPETS, version_skip_reason

import pycg
from pycg.formats import dumps, edges
from pycg.formats.document import CONSTRUCTS
from pycg.pycg import CallGraphGenerator

ROOT = Path(__file__).resolve().parent.parent


def document(tmp_path, files, entry_points=("main.py",)):
    return analysed(tmp_path, files, entry_points).document()


def calls(tmp_path, source, caller="main"):
    return document(tmp_path, {"main.py": source})["calls"].get(caller, [])


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, "-m", "pycg", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return result.stdout


# The whole document


SAMPLE = """\
import re
import foo


class Box:
    def __iter__(self):
        return iter([])


def main(text, callback):
    for item in Box():
        re.compile(text).match(item)
    foo.get.bar()
    callback()
"""


def test_document_of_a_small_program(tmp_path):
    found = document(tmp_path, {"main.py": SAMPLE})

    assert found["format"] == "pycg/1"
    assert found["package"] == {"name": None, "version": None}
    assert found["modules"] == {
        "main": {"file": "main.py", "kind": "source", "status": "analysed"}
    }
    assert found["definitions"] == {
        "main": {"kind": "module", "module": "main", "lines": [1, 14]},
        "main.Box": {
            "kind": "class",
            "module": "main",
            "lines": [5, 7],
            "mro": ["main.Box", "<builtin>.object"],
        },
        "main.Box.__iter__": {"kind": "function", "module": "main", "lines": [6, 7]},
        "main.main": {"kind": "function", "module": "main", "lines": [10, 14]},
    }
    assert found["exports"] == {"main.foo": ["foo"], "main.re": ["re"]}
    assert found["outside"] == {
        "<builtin>.iter": {"known": "stub"},
        "foo.get.bar": {"known": "name"},
        "re.Pattern.match": {"known": "stub"},
        "re.compile": {"known": "stub"},
    }
    assert found["calls"] == {
        "main.Box.__iter__": [
            {"line": 7, "col": 15, "end": [7, 23], "callees": ["<builtin>.iter"]}
        ],
        "main.main": [
            {
                "line": 11,
                "col": 16,
                "end": [11, 21],
                "callees": ["main.Box.__iter__"],
                "implicit": "iteration",
            },
            # `re.compile(text)` and the call of its result's `match` start
            # at one position: the inner call ends first.
            {"line": 12, "col": 8, "end": [12, 24], "callees": ["re.compile"]},
            {"line": 12, "col": 8, "end": [12, 36], "callees": ["re.Pattern.match"]},
            {"line": 13, "col": 4, "end": [13, 17], "callees": ["foo.get.bar"]},
            {
                "line": 14,
                "col": 4,
                "end": [14, 14],
                "callees": [],
                "unresolved": "no value",
            },
        ],
    }


def test_command_line_writes_the_document_compact_with_sorted_keys(tmp_path):
    write(tmp_path, {"main.py": SAMPLE})

    text = run_cli("--package", str(tmp_path), str(tmp_path / "main.py"))

    found = json.loads(text)
    assert text == json.dumps(found, sort_keys=True, separators=(",", ":")) + "\n"
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()
    assert found == generator.document()


CAPPED = """\
def h0(): pass
def h1(): pass
def h2(): pass
for handler in (h0, h1, h2):
    handler()
"""


def test_the_tool_records_the_cap(tmp_path):
    capped = analysed(tmp_path / "2", {"main.py": CAPPED}, cap=2).document()
    uncapped = analysed(tmp_path / "none", {"main.py": CAPPED}, cap=None).document()

    assert capped["tool"]["cap"] == 2
    assert uncapped["tool"]["cap"] is None


def test_command_line_takes_a_cap_or_none(tmp_path):
    write(tmp_path, {"main.py": CAPPED})
    entry = str(tmp_path / "main.py")

    capped = json.loads(run_cli("--cap", "2", entry))
    uncapped = json.loads(run_cli("--cap", "none", entry))

    assert capped["tool"]["cap"] == 2
    assert [site.get("unresolved") for site in capped["calls"]["main"]] == ["saturated"]
    assert uncapped["tool"]["cap"] is None
    assert [site["callees"] for site in uncapped["calls"]["main"]] == [
        ["main.h0", "main.h1", "main.h2"]
    ]


@pytest.mark.parametrize("value", ["0", "-3", "2.5", "x", "None", "", "²"])
def test_command_line_refuses_another_cap(tmp_path, value):
    write(tmp_path, {"main.py": CAPPED})

    result = subprocess.run(
        [sys.executable, "-m", "pycg", f"--cap={value}", str(tmp_path / "main.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert "--cap" in result.stderr
    assert "a positive integer or none" in result.stderr


def test_command_line_writes_to_a_file(tmp_path):
    write(tmp_path, {"main.py": "print()\n"})
    output = tmp_path / "graph.json"

    printed = run_cli(
        "--package", str(tmp_path), "-o", str(output), str(tmp_path / "main.py")
    )

    assert printed == ""
    assert json.loads(output.read_text())["calls"]["main"] == [
        {"line": 1, "col": 0, "end": [1, 7], "callees": ["<builtin>.print"]}
    ]


# The classic call graph is the edges of the document


@pytest.mark.parametrize(
    "snippet",
    sorted(path for path in SNIPPETS.glob("*/*") if path.is_dir()),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_the_edges_of_the_document_are_consistent(snippet):
    if reason := version_skip_reason(snippet):
        pytest.skip(reason)
    generator = CallGraphGenerator([str(snippet / "main.py")], str(snippet))
    generator.analyze()
    found = generator.document()

    nodes = {
        name
        for name, definition in found["definitions"].items()
        if definition["kind"] != "class"
    }
    assert not nodes & set(found["outside"])
    for caller, sites in found["calls"].items():
        assert caller in nodes
        for site in sites:
            assert set(site["callees"]) <= nodes | set(found["outside"])
            assert site["callees"] == sorted(set(site["callees"]))
            assert site["callees"] or "unresolved" in site
        keys = [
            (
                site.get("module", ""),
                site["line"],
                site["col"],
                *site["end"],
                site.get("implicit", ""),
            )
            for site in sites
        ]
        # Sorted, and one site per node and construct.
        assert keys == sorted(set(keys))
        # A site names its module only where it is not the definition's.
        own = found["definitions"][caller]["module"]
        assert all(site.get("module") != own for site in sites)
    graph = edges(found)
    assert set(graph) == nodes | set(found["outside"])
    assert generator.output() == graph


def test_a_reader_refuses_a_version_that_it_does_not_know(tmp_path):
    found = document(tmp_path, {"main.py": "print()\n"})

    with pytest.raises(ValueError, match="pycg/2"):
        edges({**found, "format": "pycg/2"})


# Call sites


def spans(path):
    """The (line, col, end line, end col) of every node of the module, and
    of every link of a comparison chain, from its left operand to its right
    one (the one site that is not a node)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_bytes())):
        if hasattr(node, "end_col_offset"):
            found.add(span(node, node))
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            found.update(map(span, operands, operands[1:]))
    return found


def span(first, last):
    return (first.lineno, first.col_offset, last.end_lineno, last.end_col_offset)


@pytest.mark.parametrize(
    "snippet",
    sorted(path for path in SNIPPETS.glob("*/*") if path.is_dir()),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_every_site_is_the_span_of_a_node_of_its_caller(snippet):
    if reason := version_skip_reason(snippet):
        pytest.skip(reason)
    generator = CallGraphGenerator([str(snippet / "main.py")], str(snippet))
    generator.analyze()
    found = generator.document()

    modules = {
        name: spans(snippet / module["file"])
        for name, module in found["modules"].items()
        if module.get("status") == "analysed"
    }
    for caller, sites in found["calls"].items():
        own = found["definitions"][caller]["module"]
        for site in sites:
            nodes = modules[site.get("module", own)]
            assert (site["line"], site["col"], *site["end"]) in nodes, (caller, site)


def test_a_call_expression_lists_what_it_calls(tmp_path):
    source = """\
def f(): pass
def g(): pass
h = f if input() else g
h()
"""
    assert calls(tmp_path, source) == [
        {"line": 3, "col": 9, "end": [3, 16], "callees": ["<builtin>.input"]},
        {"line": 4, "col": 0, "end": [4, 3], "callees": ["main.f", "main.g"]},
    ]


def test_each_call_site_is_listed_in_its_caller(tmp_path):
    source = """\
def f(): pass
def g():
    f()
    f()
"""
    assert calls(tmp_path, source, "main.g") == [
        {"line": 3, "col": 4, "end": [3, 7], "callees": ["main.f"]},
        {"line": 4, "col": 4, "end": [4, 7], "callees": ["main.f"]},
    ]


def test_calls_in_a_class_body_or_a_comprehension_belong_to_the_scope_around(
    tmp_path,
):
    source = """\
def f(): pass
class C:
    x = f()
ys = [f() for _ in range(2)]
"""
    assert calls(tmp_path, source) == [
        {"line": 3, "col": 8, "end": [3, 11], "callees": ["main.f"]},
        {"line": 4, "col": 6, "end": [4, 9], "callees": ["main.f"]},
        {"line": 4, "col": 19, "end": [4, 27], "callees": ["<builtin>.range"]},
    ]


def test_a_builtin_that_calls_back_lists_the_function_at_its_call(tmp_path):
    source = """\
def f(x): pass
def key(x): pass
class Sized:
    def __len__(self): return 0
list(map(f, [1]))
sorted([2], key=key)
len(Sized())
"""
    assert calls(tmp_path, source) == [
        {"line": 5, "col": 0, "end": [5, 17], "callees": ["<builtin>.list"]},
        {"line": 5, "col": 5, "end": [5, 16], "callees": ["<builtin>.map", "main.f"]},
        {
            "line": 6,
            "col": 0,
            "end": [6, 20],
            "callees": ["<builtin>.sorted", "main.key"],
        },
        {
            "line": 7,
            "col": 0,
            "end": [7, 12],
            "callees": ["<builtin>.len", "main.Sized.__len__"],
        },
    ]


def test_a_builtin_that_iterates_lists_the_iteration_at_its_call(tmp_path):
    source = """\
class Items:
    def __iter__(self): return iter([])
xs = list(Items())
"""
    assert calls(tmp_path, source) == [
        {
            "line": 3,
            "col": 5,
            "end": [3, 18],
            "callees": ["<builtin>.list", "main.Items.__iter__"],
        },
    ]


def test_iteration_over_a_call_is_a_site_of_its_own(tmp_path):
    source = """\
class Items:
    def __iter__(self): return iter([])
def make(): return Items()
for x in make():
    pass
"""
    assert calls(tmp_path, source) == [
        {"line": 4, "col": 9, "end": [4, 15], "callees": ["main.make"]},
        {
            "line": 4,
            "col": 9,
            "end": [4, 15],
            "callees": ["main.Items.__iter__"],
            "implicit": "iteration",
        },
    ]


def test_a_decorator_is_an_implicit_call_and_a_decorator_factory_a_call(tmp_path):
    source = """\
def deco(f): return f
def factory(): return deco
@deco
def a(): pass
@factory()
def b(): pass
"""
    assert calls(tmp_path, source) == [
        {
            "line": 3,
            "col": 1,
            "end": [3, 5],
            "callees": ["main.deco"],
            "implicit": "decorator",
        },
        {"line": 5, "col": 1, "end": [5, 10], "callees": ["main.factory"]},
        {
            "line": 5,
            "col": 1,
            "end": [5, 10],
            "callees": ["main.deco"],
            "implicit": "decorator",
        },
    ]


def test_the_init_that_a_call_of_a_class_runs_is_a_callee_of_the_call(tmp_path):
    source = """\
class C:
    def __init__(self): pass
class D:
    pass
C()
D()
"""
    # D() calls object.__init__, which the call graph does not report.
    assert calls(tmp_path, source) == [
        {"line": 5, "col": 0, "end": [5, 3], "callees": ["main.C.__init__"]},
    ]


def test_the_calls_of_one_node_and_construct_are_one_site(tmp_path):
    source = """\
class C:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    @property
    def a(self): pass
    @property
    def b(self): pass
for x in C():
    pass
"{0.a} {0.b}".format(C())
"""
    sites = calls(tmp_path, source)

    # The loop's __iter__ and __next__, and the loads of the two fields.
    assert sites[-3:] == [
        {
            "line": 8,
            "col": 9,
            "end": [8, 12],
            "callees": ["main.C.__iter__", "main.C.__next__"],
            "implicit": "iteration",
        },
        {"line": 10, "col": 0, "end": [10, 25], "callees": ["<builtin>.str.format"]},
        {
            "line": 10,
            "col": 0,
            "end": [10, 25],
            "callees": ["main.C.a", "main.C.b"],
            "implicit": "attribute",
        },
    ]


def test_a_comparison_site_spans_its_operands(tmp_path):
    source = """\
class C:
    def __lt__(self, other): return D()
    def __contains__(self, item): return True
class D:
    def __bool__(self): return True
a, b, c = C(), C(), C()
a < b < c
1 in a
"""
    # A comparison of one link is its whole expression. Each link of a
    # chain spans its two operands, with the truth test of its result
    # where the chain goes on.
    assert calls(tmp_path, source) == [
        {
            "line": 7,
            "col": 0,
            "end": [7, 5],
            "callees": ["main.C.__lt__"],
            "implicit": "operator",
        },
        {
            "line": 7,
            "col": 0,
            "end": [7, 5],
            "callees": ["main.D.__bool__"],
            "implicit": "truth",
        },
        {
            "line": 7,
            "col": 4,
            "end": [7, 9],
            "callees": ["main.C.__lt__"],
            "implicit": "operator",
        },
        {
            "line": 8,
            "col": 0,
            "end": [8, 6],
            "callees": ["main.C.__contains__"],
            "implicit": "operator",
        },
    ]


IMPLICIT = {
    "attribute": (
        """\
class C:
    @property
    def p(self): pass
C().p
""",
        (4, 0, [4, 5]),
        ["main.C.p"],
    ),
    "await": (
        """\
class Waits:
    def __await__(self): yield
async def f():
    await Waits()
""",
        (4, 4, [4, 17]),
        ["main.Waits.__await__"],
    ),
    "class": (
        """\
class Meta(type):
    def __init__(cls, name, bases, namespace): pass
class C(metaclass=Meta):
    pass
""",
        (3, 0, [4, 8]),
        ["main.Meta.__init__"],
    ),
    "delete": (
        """\
class C:
    def __delitem__(self, key): pass
del C()[0]
""",
        (3, 4, [3, 10]),
        ["main.C.__delitem__"],
    ),
    "dict": (
        """\
class Key:
    def __hash__(self): return 0
d = {Key(): 1}
""",
        (3, 5, [3, 10]),
        ["main.Key.__hash__"],
    ),
    "format": (
        """\
class C:
    def __format__(self, spec): return ""
f"{C()}"
""",
        (3, 2, [3, 7]),
        ["main.C.__format__"],
    ),
    "iteration": (
        """\
class Items:
    def __iter__(self): return iter([])
for x in Items():
    pass
""",
        (3, 9, [3, 16]),
        ["main.Items.__iter__"],
    ),
    "match": (
        """\
class Seq:
    def __len__(self): return 0
match Seq():
    case []:
        pass
""",
        (4, 9, [4, 11]),
        ["main.Seq.__len__"],
    ),
    "operator": (
        """\
class N:
    def __add__(self, other): pass
N() + N()
""",
        (3, 0, [3, 9]),
        ["main.N.__add__"],
    ),
    "raise": (
        """\
class Error(Exception):
    def __init__(self): pass
raise Error
""",
        (3, 6, [3, 11]),
        ["main.Error.__init__"],
    ),
    "subscript": (
        """\
class C:
    def __getitem__(self, key): pass
C()[0]
""",
        (3, 0, [3, 6]),
        ["main.C.__getitem__"],
    ),
    "truth": (
        """\
class C:
    def __bool__(self): return True
if C():
    pass
""",
        (3, 3, [3, 6]),
        ["main.C.__bool__"],
    ),
    "with": (
        """\
class Lock:
    def __enter__(self): pass
    def __exit__(self, *args): pass
with Lock():
    pass
""",
        (4, 5, [4, 11]),
        ["main.Lock.__enter__", "main.Lock.__exit__"],
    ),
}


@pytest.mark.parametrize("construct", IMPLICIT)
def test_an_implicit_call_names_its_construct(tmp_path, construct):
    source, (line, col, end), callees = IMPLICIT[construct]
    caller = "main.f" if construct == "await" else "main"

    sites = calls(tmp_path, source, caller)

    assert {
        "line": line,
        "col": col,
        "end": end,
        "callees": callees,
        "implicit": construct,
    } in sites


def test_implicit_calls_to_outside_code_are_not_listed(tmp_path):
    source = """\
for x in [1]:
    pass
with open("f") as f:
    pass
"""
    assert calls(tmp_path, source) == [
        {"line": 3, "col": 5, "end": [3, 14], "callees": ["<builtin>.open"]},
    ]


# Unresolved call expressions


def test_a_call_whose_callee_holds_nothing_is_unresolved(tmp_path):
    source = """\
def run(callback):
    callback()
"""
    assert calls(tmp_path, source, "main.run") == [
        {"line": 2, "col": 4, "end": [2, 14], "callees": [], "unresolved": "no value"},
    ]


def test_a_call_of_an_attribute_with_a_computed_name_is_unresolved(tmp_path):
    source = """\
class C:
    def visit(self): pass
def run(name):
    getattr(C(), name)()
"""
    assert calls(tmp_path, source, "main.run") == [
        {"line": 4, "col": 4, "end": [4, 22], "callees": ["<builtin>.getattr"]},
        {
            "line": 4,
            "col": 4,
            "end": [4, 24],
            "callees": [],
            "unresolved": "computed name",
        },
    ]


def test_a_call_of_an_outside_value_without_a_name_is_unresolved(tmp_path):
    # Names of outside code stop two attributes past their root.
    source = """\
import lib
lib.a.b.c()
"""
    assert calls(tmp_path, source) == [
        {
            "line": 2,
            "col": 0,
            "end": [2, 11],
            "callees": [],
            "unresolved": "outside value",
        },
    ]


def test_a_call_of_a_name_without_a_value_is_unresolved(tmp_path):
    source = """\
def run():
    (lambda: None)()()
"""
    found = calls(tmp_path, source, "main.run")

    assert {
        "line": 2,
        "col": 4,
        "end": [2, 22],
        "callees": [],
        "unresolved": "no value",
    } in found


def test_code_that_cannot_run_lists_no_call(tmp_path):
    source = """\
if False:
    missing()
"""
    assert calls(tmp_path, source) == []


# Modules


def test_a_module_that_cannot_be_read_or_parsed_has_failed(tmp_path):
    found = document(
        tmp_path,
        {
            "broken.py": "def oops(:\n",
            "latin.py": b"name = '\xe9'\n",
            "later.py": b"x = 1\ny = '\xe9'\n",
            "main.py": "import broken, latin, later\ndef f(): pass\nf()\n",
        },
    )

    # The cause is the type of the error and where it is, not its message,
    # which changes between versions of Python.
    assert found["modules"] == {
        "broken": {
            "file": "broken.py",
            "kind": "source",
            "status": "failed",
            "cause": "SyntaxError (line 1)",
        },
        "latin": {
            "file": "latin.py",
            "kind": "source",
            "status": "failed",
            "cause": "SyntaxError",
        },
        "later": {
            "file": "later.py",
            "kind": "source",
            "status": "failed",
            "cause": "UnicodeDecodeError (byte 11)",
        },
        "main": {"file": "main.py", "kind": "source", "status": "analysed"},
    }
    # A failed module defines nothing but itself, and calls nothing; its
    # lines are not known.
    assert found["definitions"] == {
        "broken": {"kind": "module", "module": "broken", "lines": [0, 0]},
        "latin": {"kind": "module", "module": "latin", "lines": [0, 0]},
        "later": {"kind": "module", "module": "later", "lines": [0, 0]},
        "main": {"kind": "module", "module": "main", "lines": [1, 3]},
        "main.f": {"kind": "function", "module": "main", "lines": [2, 2]},
    }
    assert found["calls"] == {
        "main": [{"line": 3, "col": 0, "end": [3, 3], "callees": ["main.f"]}]
    }


@contextmanager
def stack_limit(frames):
    """Allow `frames` more frames on the Python stack than the caller uses."""
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(len(inspect.stack(0)) + frames)
    try:
        yield
    finally:
        sys.setrecursionlimit(previous)


def test_a_module_whose_analysis_stops_early_is_partial(tmp_path):
    # Python parses the nested lambdas; the analysis runs out of stack.
    source = "def f(): pass\nf()\nx = " + "lambda: " * 300 + "None\n"
    write(tmp_path, {"main.py": source})
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    with stack_limit(200):
        generator.analyze()
    found = generator.document()

    assert found["modules"] == {
        "main": {
            "file": "main.py",
            "kind": "source",
            "status": "partial",
            "cause": "RecursionError",
        }
    }
    # What the analysis found before it stopped is kept.
    assert found["definitions"]["main"]["lines"] == [1, 3]
    assert found["definitions"]["main.f"]["lines"] == [1, 1]
    assert found["calls"]["main"] == [
        {"line": 2, "col": 0, "end": [2, 3], "callees": ["main.f"]}
    ]


# Files of one module name (review round 3, finding 1)

ONE_MODULE_NAME = {
    "a.py": "def f(): pass\nf()\n",
    "a/__init__.py": "def g(): pass\ng()\n",
    "main.py": "import a\n",
}


@pytest.mark.parametrize(
    "entries",
    [
        ("a.py", "a/__init__.py"),
        ("a/__init__.py", "a.py"),
        ("a.py",),
        ("a.py", "main.py"),
        ("main.py", "a.py"),
    ],
)
def test_a_package_comes_before_a_module_file_of_its_name(tmp_path, entries):
    found = document(tmp_path, ONE_MODULE_NAME, entries)

    # Python imports the package; the module file is listed, not analysed.
    assert found["modules"]["a"] == {
        "file": "a/__init__.py",
        "kind": "source",
        "status": "analysed",
        "shadows": ["a.py"],
    }
    assert found["calls"]["a"] == [
        {"line": 2, "col": 0, "end": [2, 3], "callees": ["a.g"]}
    ]
    assert "a.f" not in found["definitions"]


@pytest.mark.parametrize("entries", [("main.py",), ("main.py", "a.so", "a.abi3.so")])
def test_a_module_file_comes_before_extension_binaries_of_its_name(tmp_path, entries):
    files = {
        "a.py": "def f(): pass\n",
        "a.so": b"",
        "a.abi3.so": b"",
        "main.py": "import a\na.f()\n",
    }
    found = document(tmp_path, files, entries)

    assert found["modules"]["a"] == {
        "file": "a.py",
        "kind": "source",
        "status": "analysed",
        "shadows": ["a.abi3.so", "a.so"],
    }
    assert found["calls"]["main"] == [
        {"line": 2, "col": 0, "end": [2, 5], "callees": ["a.f"]}
    ]


def test_of_two_extension_binaries_of_one_name_the_first_by_name_is_the_module(
    tmp_path,
):
    files = {
        "pkg/__init__.py": "from . import _x\n",
        "pkg/_x.cpython-312-darwin.so": b"",
        "pkg/_x.abi3.so": b"",
    }
    found = document(tmp_path, files, ("pkg/__init__.py",))

    assert found["modules"]["pkg._x"] == {
        "file": "pkg/_x.abi3.so",
        "kind": "extension",
        "shadows": ["pkg/_x.cpython-312-darwin.so"],
    }


@pytest.mark.parametrize("entries", [("a.py", "a.pyi"), ("a.pyi", "a.py")])
def test_a_stub_is_not_source(tmp_path, entries):
    files = {"a.py": "def f(): pass\nf()\n", "a.pyi": "def h() -> None: ...\nh()\n"}
    found = document(tmp_path, files, entries)

    assert found["modules"] == {
        "a": {"file": "a.py", "kind": "source", "status": "analysed"}
    }
    assert found["calls"]["a"] == [
        {"line": 2, "col": 0, "end": [2, 3], "callees": ["a.f"]}
    ]


@pytest.mark.parametrize("entries", [("a.py", "a/x.py"), ("a/x.py", "a.py")])
def test_a_module_file_beside_a_namespace_package_of_its_name(tmp_path, entries):
    files = {"a.py": "def f(): pass\nf()\n", "a/x.py": "def g(): pass\ng()\n"}
    found = document(tmp_path, files, entries)

    # Python imports the module file for `a`; the entry `a/x.py` is analysed
    # as the module `a.x` it names, though no import reaches it.
    assert found["modules"] == {
        "a": {"file": "a.py", "kind": "source", "status": "analysed"},
        "a.x": {"file": "a/x.py", "kind": "source", "status": "analysed"},
    }


# Files that only an entry point names (review round 4, finding 1)

ENTRY_ONLY = {"a.pyw": "def f(): pass\nf()\n", "a": "def g(): pass\ng()\n"}


@pytest.mark.parametrize("entries", [("a.pyw", "a"), ("a", "a.pyw")])
def test_files_that_only_entry_points_name_are_ordered_by_name(tmp_path, entries):
    found = document(tmp_path, ENTRY_ONLY, entries)

    # No file that an import finds: the first by name is the module.
    assert found["modules"] == {
        "a": {
            "file": "a",
            "kind": "source",
            "status": "analysed",
            "shadows": ["a.pyw"],
        }
    }
    assert found["calls"]["a"] == [
        {"line": 2, "col": 0, "end": [2, 3], "callees": ["a.g"]}
    ]


@pytest.mark.parametrize("entries", [("a.pyw", "a"), ("a", "a.pyw")])
def test_a_file_that_an_import_finds_comes_before_entry_only_files(tmp_path, entries):
    files = {**ENTRY_ONLY, "a.py": "def h(): pass\nh()\n"}
    found = document(tmp_path, files, entries)

    assert found["modules"]["a"] == {
        "file": "a.py",
        "kind": "source",
        "status": "analysed",
        "shadows": ["a", "a.pyw"],
    }


@pytest.mark.parametrize("entries", [("a.b.py", "a/b.py"), ("a/b.py", "a.b.py")])
def test_a_file_name_with_a_dot_names_the_module_of_its_parts(tmp_path, entries):
    files = {
        "a/__init__.py": "",
        "a/b.py": "def f(): pass\nf()\n",
        "a.b.py": "def g(): pass\ng()\n",
    }
    found = document(tmp_path, files, entries)

    assert found["modules"]["a.b"] == {
        "file": "a/b.py",
        "kind": "source",
        "status": "analysed",
        "shadows": ["a.b.py"],
    }


def test_a_directory_or_the_roots_init_is_not_an_entry_point(tmp_path, caplog):
    write(tmp_path, {"__init__.py": "x = 1\n", "a/__init__.py": "def g(): pass\ng()\n"})
    entries = ["__init__.py", "a", "a/", "a/__init__.py"]
    generator = CallGraphGenerator([str(tmp_path / e) for e in entries], str(tmp_path))
    with caplog.at_level(logging.WARNING):
        generator.analyze()

    assert generator.document()["modules"] == {
        "a": {"file": "a/__init__.py", "kind": "source", "status": "analysed"}
    }
    assert "a directory is not a module file" in caplog.text
    assert "the package root is not a package" in caplog.text


def test_module_files_are_relative_to_the_root_with_slashes(tmp_path):
    found = document(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/sub/mod.py": "",
            "main.py": "import pkg.sub.mod\n",
        },
    )

    assert {name: module["file"] for name, module in found["modules"].items()} == {
        "main": "main.py",
        "pkg": "pkg/__init__.py",
        "pkg.sub.mod": "pkg/sub/mod.py",
    }


EXTENSIONS = {
    "pkg/__init__.py": """\
from . import _speedups
from ._fast import escape
from .both import g
import pkg._abi
def f():
    _speedups.run()
    escape()
    pkg._abi.go()
    g()
""",
    "pkg/_speedups.cpython-312-darwin.so": b"\x7fELF",
    "pkg/_fast.so": b"\x7fELF",
    "pkg/_abi.abi3.so": b"\x7fELF",
    "pkg/_win.cp312-win_amd64.pyd": b"MZ",
    "pkg/both.py": "def g(): pass\n",
    "pkg/both.cpython-312-darwin.so": b"\x7fELF",
}


def test_extension_modules_are_found_by_their_file_names(tmp_path):
    found = document(tmp_path, EXTENSIONS, ("pkg/__init__.py",))

    assert found["modules"] == {
        "pkg": {"file": "pkg/__init__.py", "kind": "source", "status": "analysed"},
        "pkg._abi": {"file": "pkg/_abi.abi3.so", "kind": "extension"},
        "pkg._fast": {"file": "pkg/_fast.so", "kind": "extension"},
        "pkg._speedups": {
            "file": "pkg/_speedups.cpython-312-darwin.so",
            "kind": "extension",
        },
        # A module with a source file is a source module; its binary is
        # shadowed.
        "pkg.both": {
            "file": "pkg/both.py",
            "kind": "source",
            "status": "analysed",
            "shadows": ["pkg/both.cpython-312-darwin.so"],
        },
        # pkg._win is not imported.
    }


def test_a_call_into_an_extension_module_is_named_by_its_module(tmp_path):
    found = document(tmp_path, EXTENSIONS, ("pkg/__init__.py",))

    assert [site["callees"] for site in found["calls"]["pkg.f"]] == [
        ["pkg._speedups.run"],
        ["pkg._fast.escape"],
        ["pkg._abi.go"],
        ["pkg.both.g"],
    ]
    assert found["outside"] == {
        "pkg._abi.go": {"known": "extension"},
        "pkg._fast.escape": {"known": "extension"},
        "pkg._speedups.run": {"known": "extension"},
    }


# Definitions, exports, outside names, package and tool


def test_definitions_have_their_kind_module_lines_and_mro(tmp_path):
    source = """\
import ext
class Base:
    def run(self):
        return lambda: None
class Child(Base, ext.Mixin):
    pass
def outer():
    def inner(): pass
"""
    found = document(tmp_path, {"main.py": source})

    assert found["definitions"] == {
        "main": {"kind": "module", "module": "main", "lines": [1, 8]},
        "main.Base": {
            "kind": "class",
            "module": "main",
            "lines": [2, 4],
            "mro": ["main.Base", "<builtin>.object"],
        },
        "main.Base.run": {"kind": "function", "module": "main", "lines": [3, 4]},
        "main.Base.run.<lambda1>": {
            "kind": "function",
            "module": "main",
            "lines": [4, 4],
        },
        # Past an outside class, the linearization is outside code.
        "main.Child": {
            "kind": "class",
            "module": "main",
            "lines": [5, 6],
            "mro": ["main.Child", "main.Base", "ext.Mixin"],
        },
        "main.outer": {"kind": "function", "module": "main", "lines": [7, 8]},
        "main.outer.inner": {"kind": "function", "module": "main", "lines": [8, 8]},
    }


def test_of_two_definitions_of_one_name_the_function_and_then_the_first_count(
    tmp_path,
):
    source = """\
import sys
if sys.argv:
    def f(): pass
else:
    def f():
        pass
class g: pass
def g(): pass
"""
    definitions = document(tmp_path, {"main.py": source})["definitions"]

    assert definitions["main.f"] == {
        "kind": "function",
        "module": "main",
        "lines": [3, 3],
    }
    # The call graph has functions, not classes, as nodes.
    assert definitions["main.g"] == {
        "kind": "function",
        "module": "main",
        "lines": [8, 8],
    }


def test_exports_map_the_names_a_module_binds_to_what_they_hold(tmp_path):
    found = document(
        tmp_path,
        {
            "pkg/__init__.py": """\
import sys
from .mod import C, helper as run
from . import mod
if sys.argv:
    from .mod import helper as either
else:
    from .other import helper as either
from requests import get
""",
            "pkg/mod.py": "class C: pass\ndef helper(): pass\n",
            "pkg/other.py": "def helper(): pass\n",
        },
        ("pkg/__init__.py",),
    )

    assert found["exports"] == {
        "pkg.C": ["pkg.mod.C"],
        "pkg.either": ["pkg.mod.helper", "pkg.other.helper"],
        "pkg.get": ["requests.get"],
        "pkg.run": ["pkg.mod.helper"],
        "pkg.sys": ["sys"],
    }


def test_a_method_of_a_third_party_library_with_a_stub_is_known_from_the_stub(
    tmp_path,
):
    source = """\
import requests
import untyped
def fetch(url):
    untyped.get(url).json()
    return requests.get(url).json()
"""
    found = document(tmp_path, {"main.py": source})

    # requests has a stub in typeshed: its methods are named by their class.
    assert found["outside"] == {
        "requests.Response.json": {"known": "stub"},
        "requests.get": {"known": "stub"},
        "untyped.get": {"known": "name"},
    }
    # What code without stubs returns has no name.
    assert [site["callees"] for site in found["calls"]["main.fetch"]] == [
        ["untyped.get"],
        [],
        ["requests.get"],
        ["requests.Response.json"],
    ]


def test_package_name_and_version_come_from_the_command_line(tmp_path):
    write(tmp_path, {"main.py": "print()\n"})

    named = json.loads(
        run_cli(
            "--package",
            str(tmp_path),
            "--package-name",
            "demo",
            "--package-version",
            "2.1.0",
            str(tmp_path / "main.py"),
        )
    )

    assert named["package"] == {"name": "demo", "version": "2.1.0"}


def test_the_tool_is_named_with_its_version_and_typeshed_commit(tmp_path):
    found = document(tmp_path, {"main.py": "print()\n"})

    readme = (ROOT / "pycg/analysis/stub_data/README.md").read_text()
    assert found["tool"] == {
        "name": "pycg",
        "version": pycg.__version__,
        "typeshed": re.search(r"`([0-9a-f]{40})`", readme)[1],
        "cap": 5000,
    }
    # The build backend reads the version from the package: one source.
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "pycg/__init__.py"


def test_a_module_has_the_lines_that_python_numbers(tmp_path):
    # A form feed does not end a line for Python, though str.splitlines()
    # breaks there.
    source = "import empty, last\ndef f():\n    pass\n\x0c\ndef g(): pass\n"
    found = document(tmp_path, {"main.py": source, "empty.py": "", "last.py": "x"})

    assert found["definitions"]["main"]["lines"] == [1, 5]
    assert found["definitions"]["main.g"]["lines"] == [5, 5]
    assert found["definitions"]["empty"]["lines"] == [0, 0]
    # The last line need not end with a newline.
    assert found["definitions"]["last"]["lines"] == [1, 1]


# Determinism

VERSIONS = {
    "main.py": """\
import broken, nul, chain


def deco(f):
    return f


@deco
def show(items, key):
    for item in items:
        match item:
            case {"name": name}:
                print(f"{name!r:>8}")
    return sorted(items, key=lambda item: item[key])
""",
    "broken.py": "x = (\n",
    # A comparison chain, and two definitions of one name.
    "chain.py": """\
class C:
    def __lt__(self, other): return True
a = b = c = C()
a < b < c
if a:
    def f(): a < b
else:
    def f(): b < c
""",
    # Python 3.12 fails to parse it; later versions fail to read it.
    "nul.py": "x = 1\x00\n",
}


def test_the_document_is_the_same_on_every_python_version(tmp_path):
    found = document(tmp_path, VERSIONS)

    tool = found["tool"]
    assert dumps(found) == dumps(
        {
            "format": "pycg/1",
            "tool": tool,
            "package": {"name": None, "version": None},
            "modules": {
                "broken": {
                    "file": "broken.py",
                    "kind": "source",
                    "status": "failed",
                    "cause": "SyntaxError (line 1)",
                },
                "chain": {"file": "chain.py", "kind": "source", "status": "analysed"},
                "main": {"file": "main.py", "kind": "source", "status": "analysed"},
                "nul": {
                    "file": "nul.py",
                    "kind": "source",
                    "status": "failed",
                    "cause": "SyntaxError",
                },
            },
            "definitions": {
                "broken": {"kind": "module", "module": "broken", "lines": [0, 0]},
                "chain": {"kind": "module", "module": "chain", "lines": [1, 8]},
                "chain.C": {
                    "kind": "class",
                    "module": "chain",
                    "lines": [1, 2],
                    "mro": ["chain.C", "<builtin>.object"],
                },
                "chain.C.__lt__": {
                    "kind": "function",
                    "module": "chain",
                    "lines": [2, 2],
                },
                "chain.f": {"kind": "function", "module": "chain", "lines": [6, 6]},
                "main": {"kind": "module", "module": "main", "lines": [1, 14]},
                "main.deco": {"kind": "function", "module": "main", "lines": [4, 5]},
                "main.show": {"kind": "function", "module": "main", "lines": [9, 14]},
                "main.show.<lambda1>": {
                    "kind": "function",
                    "module": "main",
                    "lines": [14, 14],
                },
                "nul": {"kind": "module", "module": "nul", "lines": [0, 0]},
            },
            "exports": {
                "main.broken": ["broken"],
                "main.chain": ["chain"],
                "main.nul": ["nul"],
            },
            "outside": {
                "<builtin>.print": {"known": "stub"},
                "<builtin>.sorted": {"known": "stub"},
            },
            "calls": {
                "chain": [
                    {
                        "line": 4,
                        "col": 0,
                        "end": [4, 5],
                        "callees": ["chain.C.__lt__"],
                        "implicit": "operator",
                    },
                    {
                        "line": 4,
                        "col": 4,
                        "end": [4, 9],
                        "callees": ["chain.C.__lt__"],
                        "implicit": "operator",
                    },
                ],
                "chain.f": [
                    {
                        "line": 6,
                        "col": 13,
                        "end": [6, 18],
                        "callees": ["chain.C.__lt__"],
                        "implicit": "operator",
                    },
                    {
                        "line": 8,
                        "col": 13,
                        "end": [8, 18],
                        "callees": ["chain.C.__lt__"],
                        "implicit": "operator",
                    },
                ],
                "main": [
                    {
                        "line": 8,
                        "col": 1,
                        "end": [8, 5],
                        "callees": ["main.deco"],
                        "implicit": "decorator",
                    }
                ],
                "main.show": [
                    {
                        "line": 13,
                        "col": 16,
                        "end": [13, 37],
                        "callees": ["<builtin>.print"],
                    },
                    {
                        "line": 14,
                        "col": 11,
                        "end": [14, 52],
                        "callees": ["<builtin>.sorted", "main.show.<lambda1>"],
                    },
                ],
            },
        }
    )


def test_an_accessor_that_a_hook_runs_is_at_the_hook(tmp_path):
    found = document(
        tmp_path,
        {
            "main.py": """\
from model import C
def use():
    c = C()
    c.value = 1
""",
            "model.py": """\
class C:
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
    @property
    def value(self): pass
    @value.setter
    def value(self, new): pass
""",
        },
    )

    # The hook calls the setter, in Python's code that its body runs: the
    # site is the hook's definition, not the store in main.
    assert found["calls"]["model.C.__setattr__"] == [
        {
            "line": 2,
            "col": 4,
            "end": [3, 45],
            "callees": ["model.C.value"],
            "implicit": "attribute",
        },
        {
            "line": 3,
            "col": 8,
            "end": [3, 45],
            "callees": ["<builtin>.object.__setattr__"],
        },
    ]
    assert found["calls"]["main.use"] == [
        {
            "line": 4,
            "col": 4,
            "end": [4, 11],
            "callees": ["model.C.__setattr__"],
            "implicit": "attribute",
        },
    ]


def engine_roles():
    """The first name of every role of an implicit call in the engine's
    sources: of the role of each `site_call` (its third argument) and of
    each origin of a `Call` (its seventh) that names a step of a class
    statement, as a tuple or through a variable that the function assigns
    a tuple."""
    roles = set()
    for path in sorted((ROOT / "pycg" / "analysis").glob("*.py")):
        for function in ast.walk(ast.parse(path.read_text())):
            if isinstance(function, ast.FunctionDef):
                roles.update(function_roles(function, path))
    return roles


def function_roles(function, path):
    tuples = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    tuples.setdefault(target.id, []).append(node.value)
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", None))
        position = {"site_call": 2, "Call": 6}.get(name)
        if position is None or len(node.args) <= position:
            continue
        role = node.args[position]
        values = tuples.get(role.id, []) if isinstance(role, ast.Name) else [role]
        for value in values:
            if isinstance(value, ast.Tuple) and isinstance(value.elts[0], ast.Constant):
                yield value.elts[0].value
            else:
                # A copy of another call's origin, or a role built elsewhere.
                assert name == "Call", f"{path.name}:{node.lineno}: role {role}"


def test_every_role_of_the_engine_has_a_construct():
    # Another role must be named in the table (a closed list), and a role
    # that the engine no longer makes leaves it.
    assert engine_roles() == set(CONSTRUCTS)


# Definitions of one qualified name

# Two functions named `a.b.f`, in the package `a` and in the module `a.b`,
# whose calls are at one position of their files (review round 2).
ONE_NAME_IN_TWO_MODULES = {
    "a/__init__.py": """\
def b():
    def f(x):
        x()
""",
    "a/b.py": """\
import json; x = json.loads("null")
def f():
        x()
""",
}


@pytest.mark.parametrize(
    "entries", [("a/__init__.py", "a/b.py"), ("a/b.py", "a/__init__.py")]
)
def test_the_sites_of_two_definitions_of_one_name_are_kept_apart(tmp_path, entries):
    found = document(tmp_path, ONE_NAME_IN_TWO_MODULES, entries)

    # The name's definition is the first by module: the function in `a`.
    assert found["definitions"]["a.b.f"] == {
        "kind": "function",
        "module": "a",
        "lines": [2, 3],
    }
    # Both definitions' sites are listed; one in another module says so.
    assert found["calls"]["a.b.f"] == [
        {"line": 3, "col": 8, "end": [3, 11], "callees": [], "unresolved": "no value"},
        {
            "line": 3,
            "col": 8,
            "end": [3, 11],
            "callees": [],
            "unresolved": "outside value",
            "module": "a.b",
        },
    ]
    # The module `a.b` wins its name over the function `a.b`.
    assert found["calls"]["a.b"] == [
        {"line": 1, "col": 17, "end": [1, 35], "callees": ["json.loads"]}
    ]


def test_a_module_and_a_function_of_one_name_keep_their_sites(tmp_path):
    found = document(
        tmp_path,
        {
            "p/__init__.py": "def helper(): pass\ndef retry():\n    helper()\n",
            "p/retry.py": "def g(): pass\ng()\n",
        },
        ("p/__init__.py", "p/retry.py"),
    )

    assert found["definitions"]["p.retry"]["kind"] == "module"
    # The module's own call stays where it is; the function's call is in
    # the package's file.
    assert found["calls"]["p.retry"] == [
        {"line": 2, "col": 0, "end": [2, 3], "callees": ["p.retry.g"]},
        {
            "line": 3,
            "col": 4,
            "end": [3, 12],
            "callees": ["p.helper"],
            "module": "p",
        },
    ]
