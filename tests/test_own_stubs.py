"""A package's own stubs: `x.pyi` beside an analysed `x.py` gives the
annotations that the source leaves out. The stub is read for annotations
only: where a parameter, a class attribute or a module variable of the
source has none, the annotation of the same name in the stub is read as if
it were written in the source. The stub defines nothing, calls nothing and
imports nothing; its names resolve through its own imports and to the
module's own classes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from programs import analysed, call_graph, callees, write
from test_order_independence import orders

from pycg.analysis import solver
from pycg.formats import dumps, edges
from pycg.pycg import CallGraphGenerator

SHAPES = """
class Shape:
    def area(self): pass
    def size(self): pass
class Square(Shape):
    def area(self): pass
    def size(self): pass
class Circle(Shape):
    def area(self): pass
"""

ALL_AREAS = ["shapes.Circle.area", "shapes.Shape.area", "shapes.Square.area"]


def graph_of(tmp_path, files):
    """The call graph of `files` with the module `shapes`, an entry point:
    a module that only a stub imports is not analysed."""
    files = {"shapes.py": SHAPES, **files}
    return call_graph(tmp_path, files, entry_points=("main.py", "shapes.py"))


def test_a_parameter_typed_only_in_the_stub_holds_what_the_annotation_names(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            import shapes
            def report(shape):
                shape.area()
            class Canvas:
                def draw(self, shape, *more, **named):
                    shape.area()
                    for each in more:
                        each.size()
                    named["x"].size()
            """,
            "main.pyi": """
            from shapes import Shape, Square
            def report(shape: Shape) -> None: ...
            class Canvas:
                def draw(self, shape: Shape, *more: Square, **named: Square): ...
            """,
        },
    )

    assert callees(graph, "main.report") == ALL_AREAS
    assert callees(graph, "main.Canvas.draw") == ALL_AREAS + ["shapes.Square.size"]


def test_a_stub_parameter_matches_by_name_and_kind(tmp_path):
    # The stub's parameter `shape` annotates the source's `shape` wherever it
    # is; the stub's `*shapes` annotates no plain parameter `shapes`.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            def report(first, shape, shapes):
                shape.area()
                shapes.size()
                first.size()
            """,
            "main.pyi": """
            from shapes import Shape
            def report(shape: Shape, *shapes: Shape) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.report") == ALL_AREAS


def test_a_return_type_in_the_stub_names_nothing_as_in_the_source(tmp_path):
    # The annotation rule reads no return types: one in the stub gives what
    # one in the source gives.
    source = """
    import shapes
    def make(){annotation}:
        return unknown()
    def use():
        make().area()
    """
    in_source = call_graph(
        tmp_path / "source",
        {"shapes.py": SHAPES, "main.py": source.format(annotation=" -> shapes.Shape")},
    )
    in_stub = call_graph(
        tmp_path / "stub",
        {
            "shapes.py": SHAPES,
            "main.py": source.format(annotation=""),
            "main.pyi": "import shapes\ndef make() -> shapes.Shape: ...\n",
        },
    )

    assert in_stub == in_source
    assert callees(in_stub, "main.use") == ["main.make"]


def test_a_class_attribute_typed_only_in_the_stub(tmp_path):
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            class Canvas:
                shape = None
                def draw(self):
                    self.shape.area()
            """,
            "main.pyi": """
            from typing import ClassVar, Optional
            from shapes import Shape
            class Canvas:
                shape: ClassVar[Optional[Shape]]
                def draw(self) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.Canvas.draw") == ALL_AREAS


def test_a_module_variable_typed_only_in_the_stub(tmp_path):
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            current = None
            def run():
                current.area()
            """,
            "main.pyi": """
            import shapes
            current: shapes.Shape | None
            """,
        },
    )

    assert callees(graph, "main.run") == ALL_AREAS


def test_an_annotation_in_the_source_wins_over_the_stub(tmp_path):
    # Python has the source's annotation; the stub fills only what the
    # source leaves out.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            from shapes import Square
            def report(shape: Square, other):
                shape.area()
                other.size()
            class Canvas:
                shape: Square = Square()
                def draw(self):
                    self.shape.size()
            """,
            "main.pyi": """
            from shapes import Shape
            def report(shape: Shape, other: Shape) -> None: ...
            class Canvas:
                shape: Shape
            """,
        },
    )

    assert callees(graph, "main.report") == [
        "shapes.Shape.size",
        "shapes.Square.area",
        "shapes.Square.size",
    ]
    assert callees(graph, "main.Canvas.draw") == ["shapes.Square.size"]


def test_an_overload_set_names_the_union_of_its_annotations(tmp_path):
    # Every definition of the name counts: the overloads, and the branches
    # of an `if` that only a type checker decides.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            def pick(item, extra=None):
                item.area()
                extra.size()
            """,
            "main.pyi": """
            import sys
            from typing import overload
            from shapes import Circle, Shape, Square
            @overload
            def pick(item: Circle) -> Circle: ...
            @overload
            def pick(item: Square, extra: None = None) -> Square: ...
            if sys.version_info >= (3, 99):
                def pick(item: int, extra: Square) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.pick") == [
        "shapes.Circle.area",
        "shapes.Square.area",
        "shapes.Square.size",
    ]


def test_a_name_that_only_the_stub_defines_is_ignored(tmp_path):
    # The stub adds no function, class, method or variable: `helper`,
    # `Extra`, `Canvas.erase` and `spare` exist only in the stub, and the
    # stub's class `outer` annotates nothing in the function `outer`.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            def report(shape):
                shape.area()
            def outer():
                def report(shape):
                    shape.size()
                shape = None
                shape.size()
                return report
            class Canvas:
                def draw(self):
                    spare.area()
            """,
            "main.pyi": """
            from shapes import Shape
            def report(shape: Shape) -> None: ...
            def helper(shape: Shape) -> None: ...
            spare: Shape
            class Extra:
                def go(self, shape: Shape) -> None: ...
            class Canvas:
                def draw(self) -> None: ...
                def erase(self, shape: Shape) -> None: ...
            class outer:
                shape: Shape
                def report(self, shape: Shape) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.report") == ALL_AREAS
    assert callees(graph, "main.outer.report") == []
    assert callees(graph, "main.outer") == []
    assert callees(graph, "main.Canvas.draw") == []
    assert not [
        node
        for node in graph
        if node.startswith(("main.helper", "main.Extra", "main.Canvas.erase"))
    ]


def test_limit_a_stub_attribute_chain_must_start_at_a_stub_import(tmp_path):
    # Names in the stub resolve without loads: `Canvas.Pen` and `shapes.Shape`
    # through names that the stub does not import name nothing.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            import shapes
            class Canvas:
                def area(self): pass
                class Pen:
                    def area(self): pass
            def report(shape, pen):
                shape.area()
                pen.area()
            """,
            "main.pyi": """
            class Canvas:
                class Pen: ...
            def report(shape: shapes.Shape, pen: Canvas.Pen) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.report") == []


def test_a_stub_without_its_source_is_ignored(tmp_path):
    # `pkg/__init__.pyi` beside no `__init__.py` and `alone.pyi` are no
    # module; `pkg/mod.pyi` is the stub of `pkg/mod.py`.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            import alone
            from pkg import mod
            mod.report(None)
            """,
            "alone.pyi": "def lonely() -> None: ...\n",
            "pkg/__init__.pyi": "from shapes import Shape\nx: Shape\n",
            "pkg/mod.py": "def report(shape):\n    shape.area()\n",
            "pkg/mod.pyi": "from shapes import Shape\ndef report(shape: Shape): ...\n",
        },
    )

    assert callees(graph, "pkg.mod.report") == ALL_AREAS
    assert not [node for node in graph if node.startswith(("alone", "pkg.x"))]


def test_a_stub_in_a_subpackage(tmp_path):
    graph = graph_of(
        tmp_path,
        {
            "main.py": "from pkg.sub import mod\nimport pkg.sub\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def first(shape):\n    shape.size()\n",
            "pkg/sub/__init__.pyi": (
                "from ..sub.mod import Shape\ndef first(shape: Shape): ...\n"
            ),
            "pkg/sub/mod.py": (
                "from shapes import Shape\ndef report(shape):\n    shape.area()\n"
            ),
            "pkg/sub/mod.pyi": "from . import mod\ndef report(shape: mod.Shape): ...\n",
        },
    )

    assert callees(graph, "pkg.sub.mod.report") == ALL_AREAS
    assert callees(graph, "pkg.sub.first") == [
        "shapes.Shape.size",
        "shapes.Square.size",
    ]


def test_a_stub_from_import_reads_the_package_attribute(tmp_path):
    # `from pkg import X` reads the attribute `X` that pkg/__init__.py binds;
    # the empty submodule pkg/X.py is not what the name is. So is the
    # attribute chain `pkg.X`.
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "class T:\n    def run(self): pass\nX = T\n",
            "pkg/X.py": "",
            "main.py": """
            import pkg
            def use(value, other):
                value.run()
                other.run()
            """,
            "main.pyi": """
            import pkg
            from pkg import X
            def use(value: X, other: pkg.X): ...
            """,
        },
    )

    assert callees(graph, "main.use") == ["pkg.T.run"]


def test_limit_a_stub_attribute_chain_reads_a_submodule_file(tmp_path):
    # Python: `X` is the module `other` that pkg/__init__.py binds, not the
    # file pkg/X.py, so `X.T` and `pkg.X.T` name `other.T`. The stub reader
    # joins the chain into the dotted name `pkg.X.T`, which the file
    # pkg/X.py resolves, a module that no import analyses (a limit; the
    # same annotation in the source names `other.T`).
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "import other as X\n",
            "pkg/X.py": "class T:\n    def run(self): pass\n",
            "other.py": "class T:\n    def run(self): pass\n",
            "main.py": """
            import pkg
            def use(x, y):
                x.run()
                y.run()
            """,
            "main.pyi": """
            import pkg.X
            from pkg import X
            def use(x: X.T, y: pkg.X.T): ...
            """,
        },
    )

    assert callees(graph, "main.use") == []


def test_stub_names_resolve_through_the_stubs_own_imports(tmp_path):
    # The source binds none of `Shape`, `Sequence`, `abc` or `Square`; the
    # stub imports them, also under `TYPE_CHECKING`, and names the module's
    # own class `Local` without importing it.
    graph = graph_of(
        tmp_path,
        {
            "main.py": """
            import shapes
            class Local:
                def area(self): pass
            def report(shape, many, more, square, local, path):
                shape.area()
                for each in many:
                    each.size()
                for each in more:
                    each.size()
                square.size()
                local.area()
                path.exists()
            """,
            "main.pyi": """
            from __future__ import annotations
            import collections.abc
            from collections.abc import Sequence
            from pathlib import Path
            from typing import TYPE_CHECKING
            from shapes import Shape
            if TYPE_CHECKING:
                from shapes import Square
            class Local: ...
            def report(
                shape: Shape,
                many: Sequence[Square],
                more: collections.abc.Sequence["Square"],
                square: Square,
                local: Local,
                path: Path,
            ) -> None: ...
            """,
        },
    )

    assert callees(graph, "main.report") == [
        "main.Local.area",
        "pathlib.Path.exists",
        *ALL_AREAS,
        "shapes.Square.size",
    ]


def test_a_stub_that_cannot_be_parsed_is_ignored(tmp_path):
    files = {
        "main.py": "import other\ndef report(shape):\n    shape.area()\n",
        "main.pyi": "def report(shape: :\n",
        "other.py": "def size(shape):\n    shape.size()\n",
        "other.pyi": "from shapes import Shape\ndef size(shape: Shape): ...\n",
    }

    first = graph_of(tmp_path, files)
    entries = [str(tmp_path / "main.py"), str(tmp_path / "shapes.py")]
    generator = CallGraphGenerator(entries, str(tmp_path))
    generator.analyze()

    assert callees(first, "main.report") == []
    assert callees(first, "other.size") == ["shapes.Shape.size", "shapes.Square.size"]
    assert generator.output() == first
    assert generator.program.modules["main"].status == "analysed"


# The same annotation in the source and in the stub names the same values:
# type variables, `Self`, a generic class, a protocol and strings as well.
EQUIVALENCE_HEADER = """
from typing import Generic, Optional, Protocol, Self, TypeVar
from shapes import Shape
T = TypeVar("T")
class Box(Generic[T]):
    def area(self): pass
class Areal(Protocol):
    def area(self): ...
class Plot(Areal):
    def area(self): pass
"""


@pytest.mark.parametrize(
    "annotation",
    [
        "Shape",
        "Optional[Shape]",
        "list[Shape]",
        "type[Shape]",
        "'Shape | None'",
        "Box[Shape]",
        "Areal",
        "T",
        "Self",
    ],
)
def test_a_stub_annotation_names_what_the_same_annotation_in_the_source_does(
    tmp_path, annotation
):
    signature = "\nclass Tool:\n    def use(self, x{annotation}):"
    body = """
        x.area()
        x().area()
        for item in x:
            item.area()
"""
    in_source = call_graph(
        tmp_path / "source",
        {
            "shapes.py": SHAPES,
            "main.py": EQUIVALENCE_HEADER
            + signature.format(annotation=f": {annotation}")
            + body,
        },
    )
    in_stub = call_graph(
        tmp_path / "stub",
        {
            "shapes.py": SHAPES,
            "main.py": EQUIVALENCE_HEADER + signature.format(annotation="") + body,
            "main.pyi": EQUIVALENCE_HEADER
            + signature.format(annotation=f": {annotation}")
            + " ...\n",
        },
    )

    assert in_stub == in_source


# Every way to give the entry points and the package root finds the stub of a
# module, whether an entry point names it or an import finds it.
STUBBED = {
    "shapes.py": SHAPES,
    "main.py": "import pkg.mod\n",
    "pkg/__init__.py": "",
    "pkg/mod.py": "import shapes\ndef report(shape):\n    shape.area()\n",
    "pkg/mod.pyi": "from shapes import Shape\ndef report(shape: Shape): ...\n",
}


@pytest.mark.parametrize(
    ("entries", "package"),
    [
        (["main.py"], "."),
        (["main.py"], None),
        (["./main.py"], "./"),
        (["pkg/../main.py"], os.curdir + os.sep),
        (["pkg/mod.py"], "."),
        (["pkg/mod.py", "main.py"], None),
        (["ABSOLUTE/pkg/mod.py"], "ABSOLUTE"),
        (["ABSOLUTE/pkg/mod.py/"], "ABSOLUTE/"),
    ],
)
def test_the_generator_finds_the_stub_however_the_paths_are_given(
    tmp_path, monkeypatch, entries, package
):
    write(tmp_path, STUBBED)
    monkeypatch.chdir(tmp_path)
    entries = [entry.replace("ABSOLUTE", str(tmp_path)) for entry in entries]
    if package is not None:
        package = package.replace("ABSOLUTE", str(tmp_path))
    generator = CallGraphGenerator(entries, package)
    generator.analyze()
    graph = generator.output()

    assert callees(graph, "pkg.mod.report") == ALL_AREAS


@pytest.mark.parametrize("package", [True, False])
def test_the_command_line_finds_the_stub(tmp_path, package):
    write(tmp_path, STUBBED)
    arguments = [str(tmp_path / "main.py"), str(tmp_path / "pkg" / "mod.py")]
    if package:
        arguments += ["--package", str(tmp_path)]
    result = subprocess.run(
        [sys.executable, "-m", "pycg", *arguments],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent,
    )

    graph = edges(json.loads(result.stdout))
    assert callees(graph, "pkg.mod.report") == ALL_AREAS


def test_only_x_pyi_beside_x_py_is_a_stub(tmp_path):
    # Not a stub of another file name, nor of an entry point without the
    # `.py` suffix; `tool.pyi` is the stub of `tool.py`.
    write(
        tmp_path,
        {
            "shapes.py": SHAPES,
            "main.py": "import shapes, tool\ndef report(shape):\n    shape.area()\n",
            "main.py.pyi": "from shapes import Shape\ndef report(shape: Shape): ...\n",
            "script.pyw": "def run(shape):\n    shape.area()\n",
            "script.pyi": "from shapes import Shape\ndef run(shape: Shape): ...\n",
            "tool.py": "def use(shape):\n    shape.area()\n",
            "tool.pyi": "from shapes import Shape\ndef use(shape: Shape): ...\n",
        },
    )
    entries = [str(tmp_path / "main.py"), str(tmp_path / "script.pyw")]
    generator = CallGraphGenerator(entries, str(tmp_path))
    generator.analyze()
    graph = generator.output()

    assert callees(graph, "main.report") == []
    assert callees(graph, "script.run") == []
    assert callees(graph, "tool.use") == ALL_AREAS


def test_a_module_that_only_the_stub_imports_is_not_analysed(tmp_path):
    # Nothing in a stub runs: its imports bring in no module, so a class of
    # a module that the source does not import names nothing.
    graph = call_graph(
        tmp_path,
        {
            "shapes.py": SHAPES,
            "extra.py": "class Extra:\n    def area(self): pass\n",
            "main.py": "import shapes\ndef report(shape, other):\n"
            "    shape.area()\n    other.area()\n",
            "main.pyi": "from shapes import Shape\nfrom extra import Extra\n"
            "def report(shape: Shape, other: Extra): ...\n",
        },
    )

    assert callees(graph, "main.report") == ALL_AREAS
    assert not [node for node in graph if node.startswith("extra")]


def test_a_stub_import_adds_no_module_to_the_program(tmp_path):
    # Reading the stub's imports registers no module: not the extension
    # module `pkg.native`, which would make `pkg.native.run()` an edge, not
    # an analysed module that no source imports, not a missing module.
    files = {
        "main.py": """
        import pkg
        def use(x, y, z):
            pass
        try:
            pkg.native.run()
        except AttributeError:
            pass
        """,
        "pkg/__init__.py": "",
        "pkg/native.so": b"",
        "extra.py": "class Extra:\n    def area(self): pass\n",
    }
    stub = {
        "main.pyi": """
        from pkg.native import C
        from extra import Extra
        from missing import Missing
        def use(x: C, y: Extra, z: Missing): ...
        """
    }
    without = dumps(analysed(tmp_path / "without", files).document())
    document = dumps(analysed(tmp_path / "with", {**files, **stub}).document())

    assert document == without
    assert "pkg.native" not in document


SOURCE_ANNOTATED = {
    "a bare annotation before": "x: object\nx = None\n",
    "a bare annotation after": "x = None\nx: object\n",
    "an annotated assignment before another": "x: object = None\nx = None\n",
    "Any": "from typing import Any\nx: Any\nx = None\n",
    "an annotation in a branch": (
        "if flag:\n    x: object = None\nelse:\n    x = None\n"
    ),
}


@pytest.mark.parametrize("source", SOURCE_ANNOTATED)
def test_a_source_annotation_wins_for_the_whole_binding(tmp_path, source):
    # Any annotation of the binding in the source, wherever it is, keeps the
    # stub's annotation of that name off every assignment to it.
    module = SOURCE_ANNOTATED[source]
    in_class = "class C:\n" + "".join(f"    {line}\n" for line in module.splitlines())
    graph = call_graph(
        tmp_path,
        {
            "main.py": "class Wrong:\n    def ping(self): pass\nflag = input()\n"
            + module
            + "x.ping()\n"
            + in_class
            + "    def go(self):\n        self.x.ping()\n",
            "main.pyi": "class Wrong: ...\nx: Wrong\nclass C:\n    x: Wrong\n",
        },
    )

    assert "main.Wrong.ping" not in callees(graph, "main")
    assert callees(graph, "main.C.go") == []


def test_stub_names_resolve_in_the_stubs_own_namespace(tmp_path):
    # A name that the stub binds to anything but a class or an import names
    # nothing (`str = bytes`, an alias); a stub class names the source's
    # definition of the same qualified name (not the class body's `Right`);
    # a name that the stub does not bind is a builtin or nothing.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Right:
                def good(self): pass
            class Wrong:
                def bad(self): pass
            Alias = Right
            class Local:
                def good(self): pass
            def use(x, local, many):
                x.upper()
                local.good()
                for each in many:
                    each.good()
            def use_alias(alias):
                alias.good()
            class C:
                Right = Wrong
                def use(self, x):
                    x.good()
                    x.bad()
            """,
            "main.pyi": """
            str = bytes
            Alias = Right
            class Right: ...
            def use(x: str, local: Local, many: list[Right]): ...
            def use_alias(alias: Alias): ...
            class C:
                def use(self, x: Right): ...
            """,
        },
    )

    assert callees(graph, "main.use") == ["main.Right.good"]
    assert callees(graph, "main.use_alias") == []
    assert callees(graph, "main.C.use") == ["main.Right.good"]


def test_a_stub_annotates_the_binding_that_an_assignment_makes(tmp_path):
    # `global x` in a class body binds the module's `x`, not `C.x`; `global y`
    # in a function binds the module's `y`; `nonlocal z` binds the local of
    # `outer`, which no stub annotates.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Wrong:
                def ping(self): pass
            x = None
            class C:
                global x
                x = None
            def set_y():
                global y
                y = None
            def use_x():
                x.ping()
            def use_y():
                y.ping()
            def outer():
                z = None
                def inner():
                    nonlocal z
                    z = None
                inner()
                z.ping()
            """,
            "main.pyi": """
            class Wrong: ...
            class C:
                x: Wrong
            y: Wrong
            z: Wrong
            class outer:
                z: Wrong
            """,
        },
    )

    assert callees(graph, "main.use_x") == []
    assert callees(graph, "main.use_y") == ["main.Wrong.ping"]
    assert callees(graph, "main.outer") == ["main.outer.inner"]


def test_a_stub_class_names_the_source_class_definitions_of_its_name(tmp_path):
    # The stub's class `C` names the source's class definitions `main.C`,
    # also one defined after the use and one nested in a class, never what
    # a source variable `C` holds.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Other:
                def run(self): pass
            C = Other
            def use(x, later, inner):
                x.run()
                later.run()
                inner.run()
            class Later:
                def run(self): pass
            class Outer:
                class Inner:
                    def run(self): pass
            """,
            "main.pyi": """
            class C: ...
            class Later: ...
            class Outer:
                class Inner: ...
            def use(x: C, later: Later, inner: Outer.Inner): ...
            """,
        },
    )

    assert callees(graph, "main.use") == ["main.Later.run"]


def test_a_class_body_reads_its_stub_class_by_path(tmp_path):
    # A method of the stub's `Outer` names `Inner`, the class of its own
    # body: the source's `Outer.Inner`.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Outer:
                class Inner:
                    def run(self): pass
                def use(self, inner):
                    inner.run()
            """,
            "main.pyi": """
            class Outer:
                class Inner: ...
                def use(self, inner: Inner): ...
            """,
        },
    )

    assert callees(graph, "main.Outer.use") == ["main.Outer.Inner.run"]


def test_private_names_are_the_variables_that_python_binds(tmp_path):
    # In a class body `__x` is `_C__x`: `global __x` binds the module's
    # `_C__x`, which the stub's module `__x` does not annotate; the source's
    # `_D__x: object` is the annotation of `D`'s `__x`, so the stub's does not
    # apply; the stub's `D.__y` annotates `D`'s `__y`, which is `_D__y`.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Wrong:
                def ping(self): pass
            class C:
                global __x
                __x = None
            class D:
                _D__x: object
                __x = None
                __y = None
            def use_c():
                _C__x.ping()
            def use_dx():
                D._D__x.ping()
            def use_dy():
                D._D__y.ping()
            """,
            "main.pyi": """
            class Wrong: ...
            __x: Wrong
            class D:
                __x: Wrong
                __y: Wrong
            """,
        },
    )

    assert callees(graph, "main.use_c") == []
    assert callees(graph, "main.use_dx") == []
    assert callees(graph, "main.use_dy") == ["main.Wrong.ping"]


def test_each_binding_of_a_stub_name_contributes(tmp_path):
    # An import in one branch and a class in the other: the annotation names
    # what each names.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import other
            class C:
                def local(self): pass
            def use(x):
                x.local()
                x.foreign()
            """,
            "other.py": "class C:\n    def foreign(self): pass\n",
            "main.pyi": """
            import sys
            if sys.version_info >= (4, 0):
                from other import C
                def use(x: C): ...
            else:
                class C: ...
                def use(x: C): ...
            """,
        },
    )

    assert callees(graph, "main.use") == ["main.C.local", "other.C.foreign"]


def test_only_names_that_a_stub_assignment_binds_are_its_bindings(tmp_path):
    # `registry[str] = None` binds no `str`, and `obj.attr = 1` no `obj`.
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def use(x, y):
                x.upper()
                y.append(1)
            """,
            "main.pyi": """
            registry: dict[type, object]
            registry[str] = None
            list.attr = 1
            a, (b, *c) = 1, (2, 3)
            def use(x: str, y: list[int]): ...
            """,
        },
    )

    assert callees(graph, "main.use") == [
        "<builtin>.list.append",
        "<builtin>.str.upper",
    ]


def test_an_import_in_a_stub_class_body_binds_there(tmp_path):
    # The first scope that binds `T` is the class body, by an import.
    graph = call_graph(
        tmp_path,
        {
            "other.py": "class T:\n    def run(self): pass\n",
            "main.py": """
            class C:
                from other import T
                def use(self, x):
                    x.run()
            """,
            "main.pyi": """
            class C:
                from other import T
                def use(self, x: T): ...
            """,
        },
    )

    assert callees(graph, "main.C.use") == ["other.T.run"]


# Stubs with a scope declaration, which the stub reader does not read: a
# class statement under `global T`, a method under `global f` (the stub's
# module function `f`, not `C.f`), a class under `global str` (the module's
# `str`, not the builtin).
SCOPE_DECLARATIONS = {
    "global class": (
        """
        class C:
            global T
            class T:
                def run(self): pass
            def use(self, x):
                x.run()
        def use(x):
            x.run()
        """,
        """
        class C:
            global T
            class T: ...
            def use(self, x: T): ...
        def use(x: T): ...
        """,
    ),
    "global function": (
        """
        class C:
            def f(self, x):
                x.upper()
        C().f(None)
        """,
        """
        class C:
            global f
            def f(self, x: str): ...
        """,
    ),
    "global builtin name": (
        """
        def use(x):
            x.upper()
        """,
        """
        class C:
            global str
            class str: ...
        def use(x: str): ...
        """,
    ),
}


@pytest.mark.parametrize("program", SCOPE_DECLARATIONS)
def test_limit_a_stub_with_a_scope_declaration_is_not_read(
    tmp_path, monkeypatch, program
):
    # A stub with a `global` or `nonlocal` statement is not read: the module
    # is analysed as if it had no stub, under every order.
    source, stub = SCOPE_DECLARATIONS[program]
    write(tmp_path / "without", {"main.py": source})
    write(tmp_path / "with", {"main.py": source, "main.pyi": stub})
    for order in orders().values():
        monkeypatch.setattr(solver.Solver, "order", order)
        graphs = []
        for root in (tmp_path / "without", tmp_path / "with"):
            generator = CallGraphGenerator([str(root / "main.py")], str(root))
            generator.analyze()
            graphs.append(generator.output())

        assert graphs[1] == graphs[0]


def test_private_names_in_a_stub_class_body_are_mangled(tmp_path):
    # In the class `C`, `from other import __T` imports `other._C__T`, and
    # `other.__T` reads `other._C__T`.
    graph = call_graph(
        tmp_path,
        {
            "other.py": """
            class __T:
                def run(self): pass
            class _C__T:
                def run(self): pass
            """,
            "main.py": """
            import other
            class C:
                from other import __T as T
                import other
                def use(self, x):
                    x.run()
                def use_attribute(self, x):
                    x.run()
            """,
            "main.pyi": """
            class C:
                from other import __T as T
                import other
                def use(self, x: T): ...
                def use_attribute(self, x: other.__T): ...
            """,
        },
    )

    assert callees(graph, "main.C.use") == ["other._C__T.run"]
    assert callees(graph, "main.C.use_attribute") == ["other._C__T.run"]


def test_a_private_module_operand_in_a_stub_class_body_is_mangled(tmp_path):
    # In the class `C`, `import __m as m` imports `_C__m`; `import __p.a`
    # imports `__p.a` as written (a dotted operand is not mangled) and binds
    # `_C__p`, which `__p` in an annotation of the class reads.
    graph = call_graph(
        tmp_path,
        {
            "__m.py": "class T:\n    def run(self): pass\n",
            "_C__m.py": "class T:\n    def run(self): pass\n",
            "__p/__init__.py": "",
            "__p/a.py": "class T:\n    def run(self): pass\n",
            "_C__p/__init__.py": "",
            "_C__p/a.py": "class T:\n    def run(self): pass\n",
            "main.py": """
            import __m, _C__m, __p.a, _C__p.a
            class C:
                def use(self, x):
                    x.run()
                def use_dotted(self, x):
                    x.run()
            """,
            "main.pyi": """
            class C:
                import __m as m
                import __p.a
                def use(self, x: m.T): ...
                def use_dotted(self, x: __p.a.T): ...
            """,
        },
    )

    assert callees(graph, "main.C.use") == ["_C__m.T.run"]
    assert callees(graph, "main.C.use_dotted") == ["__p.a.T.run"]


PRIVATE_MODULE_FILES = {
    "__m.py": "class T:\n    def run(self): pass\n",
    "_C__m.py": "class T:\n    def run(self): pass\n",
    "a/__init__.py": "",
    "a/__b.py": "",
    "a/_C__b.py": "",
    "pkg/__init__.py": "",
    "pkg/__m.py": "class T:\n    def run(self): pass\n",
    "pkg/_C__m.py": "class T:\n    def run(self): pass\n",
}


@pytest.mark.parametrize(
    ("statement", "imported", "not_imported"),
    [
        ("import __m", "_C__m", "__m"),
        ("import __m as m", "_C__m", "__m"),
        ("from __m import T", "_C__m", "__m"),
        ("from .__m import T", "pkg._C__m", "pkg.__m"),
        ("import a.__b", "a.__b", "a._C__b"),
        ("import __m.T", "__m", "_C__m"),
    ],
)
def test_a_class_body_imports_the_module_that_python_imports(
    tmp_path, statement, imported, not_imported
):
    # Python mangles the module operand of an import in a class body when it
    # is one private name, and a dotted operand not at all.
    files = {**PRIVATE_MODULE_FILES, "pkg/main.py": f"class C:\n    {statement}\n"}
    generator = analysed(tmp_path, files, entry_points=("pkg/main.py",))

    assert imported in generator.program.modules
    assert not_imported not in generator.program.modules


@pytest.mark.parametrize(
    ("package", "statement"),
    [("pkg", "from . import __x"), ("_C__pkg", "from __pkg import __x")],
)
def test_a_class_body_from_import_of_a_private_submodule(tmp_path, package, statement):
    # Python's from-list keeps the written `__x`, so the import runs the
    # submodule `__x`; the name that it then reads from the package, and
    # binds, is `_C__x` (CPython 3.12 and 3.15).
    files = {
        f"{package}/__init__.py": "def hit(): pass\n_C__x = hit\n",
        f"{package}/__x.py": "def hit(): pass\nhit()\n",
        f"{package}/_C__x.py": "def hit(): pass\nhit()\n",
        "main.py": f"class C:\n    {statement}\n    __x()\n",
    }
    if package == "pkg":
        files["pkg/main.py"] = files.pop("main.py")
    entry = "pkg/main.py" if package == "pkg" else "main.py"
    generator = analysed(tmp_path, files, entry_points=(entry,))
    graph = generator.output()

    assert f"{package}.__x" in generator.program.modules
    assert f"{package}._C__x" not in generator.program.modules
    assert callees(graph, f"{package}.__x") == [f"{package}.__x.hit"]
    assert callees(graph, entry.removesuffix(".py").replace("/", ".")) == [
        f"{package}.hit"
    ]
