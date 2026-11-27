import json
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from programs import analysed, call_graph, callees, write

from pycg.formats import edges
from pycg.pycg import CallGraphGenerator


def test_positional_only_parameters_with_defaults(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def g(): pass
            def h(): pass
            class Reader:
                def read(self, size=-1, /):
                    size()
            def f(a, cb=g, /):
                a()
                cb()
            Reader().read(h)
            f(h)
            """
        },
    )

    assert callees(graph, "main.Reader.read") == ["main.h"]
    assert callees(graph, "main.f") == ["main.g", "main.h"]


def test_keyword_only_parameters(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def g(): pass
            def h(): pass
            def f(*, a, b=h):
                a()
                b()
            f(a=g)
            """
        },
    )

    assert callees(graph, "main.f") == ["main.g", "main.h"]


def test_keyword_argument_does_not_bind_a_positional_only_parameter(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def g(): pass
            def f(a, /, **kwargs):
                a()
            f(a=g)
            """
        },
    )

    assert callees(graph, "main.f") == []


def test_instances_of_one_class_keep_their_own_attributes(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Box:
                pass
            def f(): pass
            def g(): pass
            a = Box()
            b = Box()
            a.run = f
            b.run = g
            a.run()
            """
        },
    )

    assert callees(graph, "main") == ["main.f"]


def test_bound_method_stored_and_called_later(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Greeter:
                def greet(self):
                    self.helper()
                def helper(self): pass
            def keep(callback):
                return callback
            saved = keep(Greeter().greet)
            saved()
            """
        },
    )

    assert callees(graph, "main") == ["main.Greeter.greet", "main.keep"]
    assert callees(graph, "main.Greeter.greet") == ["main.Greeter.helper"]


def test_methods_of_a_class_instantiated_elsewhere_are_resolved(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Parser:
                def parse(self):
                    self.step()
                    self.handler()
                def step(self): pass
                @staticmethod
                def check(value):
                    value.step()
            class Child(Parser):
                def step(self): pass
            """
        },
    )

    assert callees(graph, "main.Parser.parse") == [
        "main.Child.step",
        "main.Parser.step",
    ]
    assert callees(graph, "main.Parser.check") == []


def test_name_that_a_class_body_binds_is_read_from_globals(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def global_target(): pass
            f = global_target
            class C:
                f = f
            C.f()
            def outer():
                def local_target(): pass
                def lexical(): pass
                f = local_target
                class D:
                    f = f
                    f()
                    lexical()
            outer()
            """
        },
    )

    assert callees(graph, "main") == ["main.global_target", "main.outer"]
    assert callees(graph, "main.outer") == ["main.global_target", "main.outer.lexical"]


def test_annotation_without_value_defines_no_attribute(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Base:
                def method(self): pass
            class Child(Base):
                method: object
            Child().method()
            """
        },
    )

    assert callees(graph, "main") == ["main.Base.method"]


def test_private_names_are_mangled_per_class(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def helper(self): pass
            class C:
                __hook = helper
                def __f(self): pass
                def g(self):
                    self.__f()
                    def inner():
                        self.__hook()
                    inner()
            class D(C):
                def __f(self): pass
                def h(self):
                    self.__f()
            class _Private:
                def __p(self): pass
            C()._C__f()
            D().g()
            D().h()
            _Private()._Private__p()
            """
        },
    )

    assert callees(graph, "main") == [
        "main.C.__f",
        "main.C.g",
        "main.D.h",
        "main._Private.__p",
    ]
    assert callees(graph, "main.C.g") == ["main.C.__f", "main.C.g.inner"]
    assert callees(graph, "main.C.g.inner") == ["main.helper"]
    assert callees(graph, "main.D.h") == ["main.D.__f"]


def test_private_names_imported_in_a_class_are_mangled(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "helper.py": "def _C__f(): pass\ndef __f(): pass\n",
            "main.py": """
            class C:
                from helper import __f
                run = __f
            C.run()
            """,
        },
    )

    assert callees(graph, "main") == ["helper._C__f"]


def test_class_cell_refers_to_the_enclosing_class(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class C:
                def g(self): pass
                def f(self):
                    __class__.g(self)
                    def nested():
                        return __class__
                    nested().g(self)
            C().f()
            """
        },
    )

    assert callees(graph, "main.C.f") == ["main.C.f.nested", "main.C.g"]


def test_class_cell_follows_lexical_scoping(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class A:
                def g(self): pass
            __class__ = A
            def outer():
                __class__ = A
                class C:
                    def g(self): pass
                    def m(self):
                        __class__.g(self)
                return C
            class D:
                def g(self): pass
                def uses_global(self):
                    global __class__
                    __class__.g(self)
                def binds(self):
                    __class__ = A
                    __class__.g(self)
            """
        },
    )

    assert callees(graph, "main.outer.C.m") == ["main.outer.C.g"]
    assert callees(graph, "main.D.uses_global") == ["main.A.g"]
    assert callees(graph, "main.D.binds") == ["main.A.g"]


def test_class_attributes(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def f(self=None): pass
            def g(): pass
            class C:
                handler = f
            C.extra = g
            def use():
                C.handler()
                C().handler()
                C.extra()
            """
        },
    )

    assert callees(graph, "main.use") == ["main.f", "main.g"]


def test_instance_with_call_method_is_callable(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Action:
                def __call__(self):
                    pass
            act = Action()
            act()
            """
        },
    )

    assert callees(graph, "main") == ["main.Action.__call__"]


def test_calls_in_class_bodies_belong_to_the_enclosing_scope(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def make(): pass
            class C:
                value = make()
                key = lambda: make()
                class Inner:
                    other = [make() for _ in range(2)]
            def f():
                class D:
                    value = make()
            """
        },
    )

    assert callees(graph, "main") == ["<builtin>.range", "main.make"]
    assert callees(graph, "main.f") == ["main.make"]
    assert callees(graph, "main.C.<lambda1>") == ["main.make"]
    assert not {"main.C", "main.C.Inner", "main.f.D"} & set(graph)


def test_builtin_calls_and_shadowed_builtins(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def len(x): pass
            def f():
                print(len([]))
            """
        },
    )

    assert callees(graph, "main.f") == ["<builtin>.print", "main.len"]


def test_builtins_are_the_same_on_every_python_version(tmp_path):
    graph = call_graph(tmp_path, {"main.py": "frozendict(a=sentinel('x'))\n"})

    assert callees(graph, "main") == ["<builtin>.frozendict", "<builtin>.sentinel"]


def test_externals_stored_and_used_later(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import os
            import sys
            import pool_lib
            from pool_lib import pool
            class Writer:
                def __init__(self):
                    self.paths = os.path
                    self.stream = sys.stdout
                    self.pool = pool
                    self.client = pool_lib.Client()
                def emit(self, x):
                    self.paths.join(x)
                    # A standard stream is an io.TextIOWrapper.
                    self.stream.write(x)
                def query(self):
                    conn = self.pool.conn
                    conn.execute()
                    self.client.send()
            def join(a, b):
                path = os.path
                return path.join(a, b)
            """
        },
    )

    assert callees(graph, "main.Writer.emit") == [
        "io.TextIOWrapper.write",
        "os.path.join",
    ]
    assert callees(graph, "main.Writer.query") == ["pool_lib.pool.conn.execute"]
    assert callees(graph, "main.join") == ["os.path.join"]


def test_elements_of_externals_keep_their_name_and_results_have_none(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import ext
            def use():
                ext.compile("p").match("s").group()
                for item in ext.items():
                    item.run()
                ext.table[0].close()
            """
        },
    )

    assert callees(graph, "main.use") == ["ext.compile", "ext.items", "ext.table.close"]


def test_external_submodule_used_by_its_full_path(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import xml.etree.ElementTree
            def load(text):
                return xml.etree.ElementTree.fromstring(text)
            """
        },
    )

    assert callees(graph, "main.load") == ["xml.etree.ElementTree.fromstring"]


def test_aliased_and_from_imports_make_module_paths_roots(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import xml
            import ext
            import xml.etree.ElementTree as ET
            from ext.pkg import thing
            def load(text):
                return xml.etree.ElementTree.fromstring(text)
            def other():
                ext.pkg.sub.helper()
            """
        },
    )

    assert callees(graph, "main.load") == ["xml.etree.ElementTree.fromstring"]
    assert callees(graph, "main.other") == ["ext.pkg.sub.helper"]


def test_external_base_class(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            from ext import Base
            import other.pkg as alias
            class A(Base):
                def run(self):
                    self.setup()
            A().run()
            alias.tool.make().build()
            """
        },
    )

    assert callees(graph, "main") == [
        "ext.Base.__init__",
        "main.A.run",
        "other.pkg.tool.make",
    ]
    assert callees(graph, "main.A.run") == ["ext.Base.setup"]


def test_expressions_that_join_values(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def a(): pass
            def b(): pass
            def c(): pass
            def d(): pass
            async def e(): pass
            def g(): pass
            async def make(): return g
            async def run(flag):
                (a if flag else b)()
                (flag or c)()
                if (picked := d):
                    picked()
                await e()
                (await make())()
            """
        },
    )

    assert callees(graph, "main.run") == [
        "main.a",
        "main.b",
        "main.c",
        "main.d",
        "main.e",
        "main.g",
        "main.make",
    ]


def test_assignment_forms(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            def a(): pass
            def b(): pass
            def c(): pass
            class Holder:
                pass
            h = Holder()
            x: object = a
            h.slot = []
            h.slot += [b]
            y = z = c
            x()
            h.slot[0]()
            z()
            """
        },
    )

    assert callees(graph, "main") == ["main.a", "main.b", "main.c"]


def test_calls_inside_compound_statements_are_found(tmp_path):
    names = [f"f{i}" for i in range(14)]
    graph = call_graph(
        tmp_path,
        {
            "main.py": "\n".join(f"def {name}(): pass" for name in names)
            + textwrap.dedent(
                """

                def run(value):
                    if f0():
                        f1()
                    elif f2():
                        pass
                    else:
                        f3()
                    for i in f4():
                        f5()
                    while f6():
                        break
                    try:
                        f7()
                    except f8() as error:
                        pass
                    finally:
                        f9()
                    with f10() as handle:
                        pass
                    match value:
                        case [first] if f11():
                            f12()
                    assert f13(), f"{f0()}"
                """
            )
        },
    )

    assert callees(graph, "main.run") == sorted(f"main.{name}" for name in names)


def test_lambdas_are_named_per_enclosing_scope(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class C:
                key = (lambda: 1)
                def m(self):
                    return (lambda: 2)()
            f = lambda: 3
            f()
            C().m()
            def target(): pass
            pick = lambda: target
            pick()()
            """
        },
    )

    assert callees(graph, "main") == [
        "main.<lambda1>",
        "main.<lambda2>",
        "main.C.m",
        "main.target",
    ]
    assert callees(graph, "main.C.m") == ["main.C.m.<lambda1>"]
    assert "main.C.<lambda1>" in graph


def test_reexported_function_has_one_name(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "from .impl import func\n",
            "pkg/impl.py": "def func(): pass\n",
            "main.py": """
            import pkg.impl
            from pkg import func
            from pkg.impl import func as same
            func()
            same()
            pkg.func()
            def through_submodule():
                pkg.impl.func()
            """,
        },
    )

    assert callees(graph, "main") == ["pkg.impl.func"]
    assert callees(graph, "main.through_submodule") == ["pkg.impl.func"]
    assert "pkg.func" not in graph


def test_star_import_and_import_inside_a_function(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "helpers.py": """
            from .private import *
            def public(): pass
            def _hidden(): pass
            """,
            "lib/__init__.py": "",
            "lib/api.py": """
            __all__ = ["listed"]
            def listed(): pass
            def unlisted(): pass
            """,
            "main.py": """
            from helpers import *
            from lib.api import *
            def run():
                import lib.api as api
                public()
                listed()
                api.unlisted()
            """,
        },
    )

    assert callees(graph, "main.run") == [
        "helpers.public",
        "lib.api.listed",
        "lib.api.unlisted",
    ]


def test_all_is_used_only_when_assigned_one_literal(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "listed.py": """
            __all__ = ("p",)
            def p(): pass
            def q(): pass
            """,
            "named.py": """
            NAME = "f"
            __all__ = [NAME]
            def f(): pass
            def g(): pass
            """,
            "merged.py": """
            __all__ = ["a"] + ["b"]
            __all__ += ("c",)
            def a(): pass
            def b(): pass
            def c(): pass
            def d(): pass
            """,
            "extended.py": """
            __all__ = ["x"]
            __all__.extend(["y"])
            def x(): pass
            def y(): pass
            def z(): pass
            """,
            "main.py": """
            from listed import *
            from named import *
            from merged import *
            from extended import *
            def use():
                p(); q()
                f(); g()
                a(); b(); c(); d()
                x(); y(); z()
            """,
        },
    )

    assert callees(graph, "main.use") == [
        "extended.x",
        "extended.y",
        "extended.z",
        "listed.p",
        "merged.a",
        "merged.b",
        "merged.c",
        "merged.d",
        "named.f",
        "named.g",
    ]


def test_star_import_imports_submodules_listed_in_all(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": '__all__ = ["child"]\n',
            "pkg/child.py": "def target(): pass\n",
            "pkg/unlisted.py": "def other(): pass\n",
            "main.py": "from pkg import *\nchild.target()\n",
        },
    )

    assert callees(graph, "main") == ["pkg.child.target"]
    assert "pkg.unlisted" not in graph


def test_cyclic_imports_terminate(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "a.py": "import b\ndef fa():\n    b.fb()\n",
            "b.py": "import a\ndef fb():\n    a.fa()\n",
            "main.py": "import a\na.fa()\n",
        },
    )

    assert callees(graph, "a.fa") == ["b.fb"]
    assert callees(graph, "b.fb") == ["a.fa"]


def test_entry_points_without_package_use_their_common_directory(tmp_path):
    files = {
        "app/main.py": "from util.tools import tool\ntool()\n",
        "app/util/__init__.py": "",
        "app/util/tools.py": "def tool(): pass\n",
        "app/util/run.py": "from .tools import tool\ntool()\n",
    }
    graph = call_graph(
        tmp_path, files, entry_points=["app/util/run.py", "app/main.py"], package=False
    )

    assert callees(graph, "main") == ["util.tools.tool"]
    assert callees(graph, "util.run") == ["util.tools.tool"]


def test_single_entry_point_without_package_uses_its_directory(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "src/main.py": "import helper\nhelper.f()\n",
            "src/helper.py": "def f(): pass",
        },
        entry_points=["src/main.py"],
        package=False,
    )

    assert callees(graph, "main") == ["helper.f"]


def test_multiple_entry_points_share_imported_modules(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "one.py": "import shared\nshared.f()\n",
            "two.py": "from shared import f\nf()\n",
            "shared.py": "def f(): pass\n",
        },
        entry_points=["one.py", "two.py"],
    )

    assert graph == {
        "one": ["shared.f"],
        "two": ["shared.f"],
        "shared": [],
        "shared.f": [],
    }


def test_module_that_cannot_be_parsed_is_skipped_with_a_warning(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        graph = call_graph(
            tmp_path,
            {
                "broken.py": "def oops(:\n",
                "latin.py": b"name = '\xe9'\n",
                "main.py": "import broken, latin\ndef f(): pass\nf()\n",
            },
        )

    assert graph == {"main": ["main.f"], "main.f": [], "broken": [], "latin": []}
    warned = " ".join(record.getMessage() for record in caplog.records)
    assert "broken.py" in warned
    assert "latin.py" in warned


def test_encoding_declaration_is_honoured(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": b"# -*- coding: latin-1 -*-\ndef f():\n    return '\xe9'\nf()\n",
        },
    )

    assert graph == {"main": ["main.f"], "main.f": []}


def test_invalid_escape_sequence_is_not_an_error(tmp_path):
    graph = call_graph(tmp_path, {"main.py": "x = '\\d'\nprint(x)\n"})

    assert graph == {"main": ["<builtin>.print"], "<builtin>.print": []}


def test_self_referential_structures_terminate(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import ext
            class Node:
                def walk(self):
                    self.walk()
                    return self.next.walk()
            node = Node()
            node.next = node
            node.walk()
            cursor = ext.start
            while cursor:
                cursor.visit()
                cursor = cursor.parent
            def recurse(n):
                return recurse(recurse)
            recurse(recurse)
            class Callable:
                pass
            Callable.__call__ = Callable()
            Callable()()
            class Init:
                pass
            Init.__init__ = Init
            Init()
            """
        },
    )

    assert "main.Node.walk" in callees(graph, "main.Node.walk")
    externals = [name for name in callees(graph, "main") if name.startswith("ext")]
    assert externals == ["ext.start.visit"]
    assert callees(graph, "main.recurse") == ["main.recurse"]


ALTERNATIVE_BASES = """
import sys
class Root:
    def m(self): pass
    def n(self): pass
{first}
{second}
class C(A if sys.argv else B):
    pass
C().m()
C().n()
"""
CLASS_A = "class A:\n    def m(self): pass"
CLASS_B = "class B(Root):\n    pass"


@pytest.mark.parametrize("order", ["A first", "B first"])
def test_alternative_bases_are_alternative_hierarchies(tmp_path, order):
    first, second = (CLASS_A, CLASS_B) if order == "A first" else (CLASS_B, CLASS_A)
    source = ALTERNATIVE_BASES.format(first=first, second=second)
    graph = call_graph(tmp_path, {"main.py": source})

    assert callees(graph, "main") == ["main.A.m", "main.Root.m", "main.Root.n"]


def test_cyclic_and_inconsistent_inheritance_terminate(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class A: pass
            class B: pass
            Base = A
            class A(Base):
                def m(self): pass
            Base = A
            class X(A, B): pass
            class Y(B, A): pass
            class Z(X, Y): pass
            Z().m()
            Left = Right = object
            class P(Right):
                def p(self): pass
            class Q(Left):
                def q(self): pass
            def swap():
                global Left, Right
                Left, Right = P, Q
            Q().p()
            """
        },
    )

    assert callees(generator.output(), "main") == ["main.A.m", "main.P.p"]
    classes = generator.document()["definitions"]
    assert classes["main.P"]["mro"] == ["main.P", "main.Q", "<builtin>.object"]
    assert classes["main.Q"]["mro"] == ["main.Q", "main.P", "<builtin>.object"]
    assert classes["main.Z"]["mro"] == [
        "main.Z",
        "main.X",
        "main.A",
        "main.A",
        "main.B",
        "main.Y",
        "<builtin>.object",
    ]


def test_deeply_nested_code_is_analysed(tmp_path):
    chain = " + ".join(["f()"] * 3000)
    elifs = "".join(f"elif x == {i}:\n    g()\n" for i in range(1500))
    conditions = f"if x:\n    g()\n{elifs}else:\n    h()\n"
    definitions = "def f(): pass\ndef g(): pass\ndef h(): pass\n"
    graph = call_graph(
        tmp_path,
        {"main.py": f"{definitions}x = {chain}\n{conditions}"},
    )

    assert callees(graph, "main") == ["main.f", "main.g", "main.h"]


def test_too_deep_module_is_analysed_in_part_with_a_warning(tmp_path, caplog):
    attribute_chain_that_parses_but_is_too_deep_to_build = "x" + ".a" * 4000
    with caplog.at_level(logging.WARNING):
        graph = call_graph(
            tmp_path,
            {
                "deep.py": "import ext\nx = ext\ny = "
                + attribute_chain_that_parses_but_is_too_deep_to_build
                + "\n",
                "main.py": "import deep\ndef f(): pass\nf()\n",
            },
        )

    assert callees(graph, "main") == ["main.f"]
    assert "deep.py" in caplog.text


def test_entry_point_outside_the_package_is_skipped(tmp_path, caplog):
    write(tmp_path, {"pkg/main.py": "print()\n", "other.py": "print()\n"})
    generator = CallGraphGenerator(
        [str(tmp_path / "pkg" / "main.py"), str(tmp_path / "other.py")],
        str(tmp_path / "pkg"),
    )
    with caplog.at_level(logging.WARNING):
        generator.analyze()

    assert generator.output() == {"main": ["<builtin>.print"], "<builtin>.print": []}
    assert "other.py" in caplog.text


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def run_cli(args, seed):
    return run_python(None, args, seed)


def run_python(code, args, seed):
    environment = dict(os.environ, PYTHONHASHSEED=str(seed))
    command = ["-m", "pycg"] if code is None else ["-c", code]
    result = subprocess.run(
        [sys.executable, *command, *args],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
        cwd=REPOSITORY_ROOT,
    )
    return result.stdout


DETERMINISM_PROGRAM = {
    "main.py": """
    from pkg import *
    from pkg.shapes import Square, Circle
    import ext
    square, circle = Square(1), Circle(2)
    square.draw(ext.canvas)
    circle.draw(ext.canvas)
    run = lambda f: f()
    run(helper)
    """,
    "pkg/__init__.py": "def helper(): pass\n",
    "pkg/shapes.py": """
    class Shape:
        def draw(self, canvas):
            canvas.line(self.area())
    class Square(Shape):
        def __init__(self, side): self.side = side
        def area(self): return self.side
    class Circle(Shape):
        def __init__(self, r): self.r = r
        def area(self): return self.r
    shapes = [Square(1), Circle(1)]
    first, second = Square, Circle
    first(2).draw(second)
    """,
}


POINTS_TO_SCRIPT = """
import json, sys
from pycg.pycg import CallGraphGenerator
generator = CallGraphGenerator(sys.argv[2:], sys.argv[1])
generator.analyze()
print(json.dumps(generator.output_points_to()))
"""


def test_output_is_the_same_for_every_hash_seed(tmp_path):
    write(tmp_path, DETERMINISM_PROGRAM)
    entries = [str(tmp_path / "main.py"), str(tmp_path / "pkg" / "shapes.py")]
    outputs = []
    for seed in (0, 1, 12345):
        document = run_cli(["--package", str(tmp_path), *entries], seed)
        points_to = run_python(POINTS_TO_SCRIPT, [str(tmp_path), *entries], seed)
        outputs.append((document, points_to))

    assert outputs[0] == outputs[1] == outputs[2]
    assert edges(json.loads(outputs[0][0]))["pkg.shapes.Shape.draw"] == [
        "ext.canvas.line",
        "pkg.shapes.Circle.area",
        "pkg.shapes.Square.area",
    ]


ORDER_PROGRAM = {
    "main.py": """
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from pkg import shapes
    class Bag(dict):
        pass
    def has(bag):
        return "key" in bag
    has(Bag())
    """,
    "pkg/__init__.py": "",
}


ORDER_SCRIPT = """
import json, sys
from pycg.analysis import semantics, stubs
from pycg.pycg import CallGraphGenerator
made = []
external = semantics.Analysis.external
def recorded_external(analysis, name, *args):
    made.append(["external", name])
    return external(analysis, name, *args)
semantics.Analysis.external = recorded_external
for method in ("find", "definition", "member", "mro"):
    original = getattr(stubs.Stubs, method)
    def recorded(stub_data, *args, _original=original, _name=method):
        made.append([_name, *map(str, args)])
        return _original(stub_data, *args)
    setattr(stubs.Stubs, method, recorded)
CallGraphGenerator(sys.argv[2:], sys.argv[1]).analyze()
print(json.dumps(made))
"""


def test_the_analysis_makes_its_externals_and_stub_queries_in_one_order(tmp_path):
    write(tmp_path, ORDER_PROGRAM)
    arguments = [str(tmp_path), str(tmp_path / "main.py")]
    orders = [run_python(ORDER_SCRIPT, arguments, seed) for seed in (0, 1, 2, 3)]

    assert len(set(orders)) == 1
    made = json.loads(orders[0])
    assert ["external", "typing.TYPE_CHECKING"] in made
    assert ["member", "builtins.dict", "__contains__"] in made


MODULES_PROGRAM = {
    "main.py": "import pkg.alpha, pkg.beta, pkg.inner.gamma, delta, epsilon\n",
    "pkg/__init__.py": "",
    "pkg/alpha.py": "",
    "pkg/beta.py": "",
    "pkg/inner/__init__.py": "",
    "pkg/inner/gamma.py": "",
    "delta.py": "",
    "epsilon.py": "",
}


MODULES_SCRIPT = """
import json, sys
from pycg.analysis import semantics
from pycg.pycg import CallGraphGenerator
made = []
module = semantics.Analysis.module
def recorded_module(analysis, name):
    made.append(name)
    return module(analysis, name)
semantics.Analysis.module = recorded_module
CallGraphGenerator(sys.argv[2:], sys.argv[1]).analyze()
print(json.dumps(made))
"""


def test_the_analysis_makes_its_modules_in_one_order(tmp_path):
    write(tmp_path, MODULES_PROGRAM)
    arguments = [str(tmp_path), str(tmp_path / "main.py")]
    orders = [run_python(MODULES_SCRIPT, arguments, seed) for seed in (0, 1, 2, 3)]

    assert len(set(orders)) == 1
    assert "pkg.inner.gamma" in json.loads(orders[0])


def test_assignment_graph_shows_points_to_sets(tmp_path):
    source = "def f(): pass\nclass C: pass\ng = f\nc = C()\n"
    assignment = analysed(tmp_path, {"main.py": source}).output_points_to()

    assert assignment["main.g"] == ["main.f"]
    assert assignment["main.c"] == ["main.C@main:4:4"]
    assert list(assignment) == sorted(assignment)


def test_document_for_a_program_with_an_outside_base(tmp_path):
    write(
        tmp_path,
        {
            "main.py": """
            from ext import Base
            class A(Base):
                def m(self):
                    print()
            A().m()
            """
        },
    )
    output = json.loads(
        run_cli(["--package", str(tmp_path), str(tmp_path / "main.py")], 0)
    )

    assert output["definitions"]["main.A"]["mro"] == ["main.A", "ext.Base"]
    assert output["definitions"]["main.A.m"]["lines"] == [4, 5]
    assert output["outside"] == {
        "<builtin>.print": {"known": "stub"},
        "ext.Base.__init__": {"known": "name"},
    }
    assert output["calls"] == {
        "main": [
            {"line": 6, "col": 0, "end": [6, 3], "callees": ["ext.Base.__init__"]},
            {"line": 6, "col": 0, "end": [6, 7], "callees": ["main.A.m"]},
        ],
        "main.A.m": [
            {"line": 5, "col": 8, "end": [5, 15], "callees": ["<builtin>.print"]}
        ],
    }


def test_stdlib_json_package_is_analysed_deterministically():
    package = Path(json.__file__).parent
    entries = sorted(str(path) for path in package.rglob("*.py"))

    def analyse():
        generator = CallGraphGenerator(entries, str(package))
        generator.analyze()
        return generator.output()

    first = analyse()
    assert analyse() == first
    assert "decoder.JSONDecoder.raw_decode" in first["decoder.JSONDecoder.decode"]


@pytest.mark.parametrize("flag", ["--max-iter", "--operation"])
def test_removed_options_are_rejected(flag):
    result = subprocess.run(
        [sys.executable, "-m", "pycg", flag, "1", "x.py"],
        capture_output=True,
        text=True,
        cwd=REPOSITORY_ROOT,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_each_load_of_an_instance_gets_what_its_lookup_finds(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Base:
                def speak(self): return self
                @property
                def size(self): return self
            class Dog(Base):
                def speak(self):
                    return super().speak()
            def early(animal):
                return animal.speak
            def measure(animal):
                return animal.size
            first, second = Dog(), Dog()
            a = early(first)
            b = early(second)
            a()
            def late(animal):
                return animal.speak
            c = late(first)
            d = measure(first)
            e = measure(second)
            """
        },
    )
    graph = generator.output()
    assert "main.Dog.speak" in graph["main"]
    assert "main.Base.speak" in graph["main.Dog.speak"]
    assert set(graph["main.measure"]) == {"main.Base.size"}
    points_to = generator.output_points_to()
    first = [name for name in points_to["main.first"] if "@main" in name]
    second = [name for name in points_to["main.second"] if "@main" in name]
    assert len(first) == 1 and len(second) == 1 and first != second
    bound = {f"<bound main.Dog.speak of {dog}>" for dog in first + second}
    assert set(points_to["main.a"]) == set(points_to["main.b"]) == bound
    assert points_to["main.c"] == [f"<bound main.Dog.speak of {first[0]}>"]
    assert set(points_to["main.d"]) == set(points_to["main.e"]) == {*first, *second}


def test_each_instance_gets_the_class_attributes_bound_to_itself(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            import pathlib
            class Base:
                def speak(self): return self
                @staticmethod
                def plain(): pass
                @classmethod
                def make(cls): return cls
                def __getattr__(self, name): return self
            class Dog(Base):
                pass
            class Place(pathlib.PurePosixPath):
                pass
            def talk(animal):
                animal.plain()
                animal.make()
                animal.missing
                return animal.speak()
            first = talk(Dog())
            second = talk(Dog())
            here = Place("a").with_name("b")
            there = Place("c").with_name("d")
            """
        },
    )
    graph = generator.output()
    assert set(graph["main.talk"]) >= {
        "main.Base.speak",
        "main.Base.plain",
        "main.Base.make",
        "main.Base.__getattr__",
    }
    points_to = generator.output_points_to()
    dogs = [name for name in points_to["main.first"] if "@main" in name]
    assert len(dogs) == 2 and points_to["main.second"] == points_to["main.first"]
    assert [
        name for name in points_to["main.Base.speak.self"] if "@main" in name
    ] == dogs
    assert [name for name in points_to["main.here"] if "@main" in name] == [
        name for name in points_to["main.here"] if name.startswith("main.Place@main")
    ]
    assert len([name for name in points_to["main.here"] if "@main" in name]) == 1
