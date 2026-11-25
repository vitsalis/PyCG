import sys
import textwrap

import pytest
from programs import call_graph, callees, main_graph

DEFINITIONS = """
import ext
def f(): pass
def g(): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_await_on_an_instance_calls_await_and_gets_what_it_returns(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Deferred:
            def __await__(self):
                yield
                return f
            def __call__(self):
                pass
        async def use():
            handler = await Deferred()
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.Deferred.__await__", "main.f"]


def test_a_coroutine_gives_its_return_value_only_when_awaited(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Box:
            def __await__(self):
                yield
                return g
            def __call__(self):
                pass
        async def make():
            return Box()
        async def awaited():
            box = await make()
            box()
        def not_awaited():
            coroutine = make()
            coroutine()
            coroutine.close()
        """,
    )

    assert callees(graph, "main.awaited") == ["main.Box.__call__", "main.make"]
    assert callees(graph, "main.not_awaited") == [
        "main.make",
        "types.CoroutineType.close",
    ]


def test_an_await_method_that_delegates_to_a_coroutine(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        async def compute():
            return f
        class Deferred:
            def __await__(self):
                return compute().__await__()
        async def use():
            (await ext.fetch())()
            await Deferred()
        """,
    )

    assert callees(graph, "main.Deferred.__await__") == [
        "main.compute",
        "types.CoroutineType.__await__",
    ]
    assert callees(graph, "main.use") == ["ext.fetch", "main.Deferred.__await__"]


def test_async_with_and_for_await_the_results_of_their_methods(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Session:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                pass
            def get(self): pass
        class Items:
            def __aiter__(self):
                return self
            async def __anext__(self):
                return f
        async def use():
            async with Session() as session:
                session.get()
            async for item in Items():
                item()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Items.__aiter__",
        "main.Items.__anext__",
        "main.Session.__aenter__",
        "main.Session.__aexit__",
        "main.Session.get",
        "main.f",
    ]


def test_a_coroutine_handed_to_outside_code_keeps_its_calls(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import asyncio
        async def work():
            return f
        async def main():
            await asyncio.gather(work(), work())
            task = asyncio.create_task(work())
            await asyncio.wait_for(task, 1)
            (await work())()
        asyncio.run(main())
        asyncio.new_event_loop().run_until_complete(main())
        """,
    )

    assert callees(graph, "main") == [
        "asyncio.new_event_loop",
        "asyncio.run",
        "main.main",
    ]
    assert callees(graph, "main.main") == [
        "asyncio.create_task",
        "asyncio.gather",
        "asyncio.wait_for",
        "main.f",
        "main.work",
    ]


def test_a_missing_module_attribute_calls_the_module_getattr(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import api
from api import later as imported
def missing():
    api.fetch()
def defined():
    api.present()
def by_import():
    imported()
""",
            "api.py": """
def _fetch(): pass
def present(): pass
def __getattr__(name):
    return {"fetch": _fetch, "later": _fetch}[name]
""",
        },
    )

    assert callees(graph, "main.missing") == ["api.__getattr__", "api._fetch"]
    assert callees(graph, "main.defined") == ["api.present"]
    assert callees(graph, "main") == ["api.__getattr__"]
    assert callees(graph, "main.by_import") == ["api._fetch"]


def test_a_module_without_getattr_has_no_missing_attributes(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": "import api\napi.fetch()\n",
            "api.py": "def present(): pass\n",
        },
    )

    assert callees(graph, "main") == []


def test_names_from_star_imports_and_submodules_are_bound(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import pkg
import pkg.child
pkg.helper()
pkg.child.run()
def missing():
    pkg.other
""",
            "pkg/__init__.py": """
from pkg.impl import *
def __getattr__(name):
    return name
""",
            "pkg/impl.py": "def helper(): pass\n",
            "pkg/child.py": "def run(): pass\n",
        },
    )

    assert callees(graph, "main") == ["pkg.child.run", "pkg.impl.helper"]
    assert callees(graph, "main.missing") == ["pkg.__getattr__"]


def test_a_name_bound_only_in_code_that_does_not_run_calls_getattr(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import lib, dynamic, facade, proxy
def dead():
    lib.absent()
def type_only():
    lib.Sequence()
def deleted():
    lib.temporary()
def present():
    lib.present()
def namespace():
    dynamic.absent()
def star():
    facade.absent()
def star_present():
    facade.present()
def method():
    proxy.Proxy().method()
def inherited():
    proxy.Proxy().inherited()
""",
            "lib.py": """
from typing import TYPE_CHECKING
def actual(): pass
def present(): pass
def __getattr__(name):
    return actual
if False:
    def absent(): pass
if TYPE_CHECKING:
    from typing import Sequence
temporary = actual
del temporary
""",
            "dynamic.py": """
def actual(): pass
def __getattr__(name):
    return actual
globals()
if False:
    def absent(): pass
""",
            "facade.py": """
from lib import *
def other(): pass
def __getattr__(name):
    return other
""",
            "proxy.py": """
from typing import TYPE_CHECKING
def actual(): pass
class Base:
    def inherited(self): pass
class Proxy(Base):
    def __getattr__(self, name):
        return actual
    if TYPE_CHECKING:
        def method(self): ...
    if False:
        def inherited(self): ...
""",
        },
    )

    assert callees(graph, "main.dead") == ["lib.__getattr__", "lib.actual"]
    assert callees(graph, "main.type_only") == ["lib.__getattr__", "lib.actual"]
    assert callees(graph, "main.deleted") == ["lib.__getattr__", "lib.actual"]
    assert callees(graph, "main.present") == ["lib.present"]
    assert callees(graph, "main.namespace") == [
        "dynamic.__getattr__",
        "dynamic.actual",
    ]
    assert callees(graph, "main.star") == ["facade.__getattr__", "facade.other"]
    assert callees(graph, "main.star_present") == ["lib.present"]
    assert callees(graph, "main.method") == [
        "proxy.Proxy.__getattr__",
        "proxy.actual",
    ]
    assert callees(graph, "main.inherited") == ["proxy.Base.inherited"]


def test_a_star_import_without_all_brings_the_imported_public_submodules(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import pkg.child
import pkg._hidden
from pkg import *
child.run()
_hidden.run()
""",
            "pkg/__init__.py": "",
            "pkg/child.py": "def run(): pass\n",
            "pkg/_hidden.py": "def run(): pass\n",
        },
    )

    assert callees(graph, "main") == ["pkg.child.run"]


def test_a_star_import_with_all_brings_only_the_listed_names(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import pkg.child
from pkg import *
child.run()
""",
            "pkg/__init__.py": "__all__ = []\n",
            "pkg/child.py": "def run(): pass\n",
        },
    )

    assert callees(graph, "main") == []


def test_a_star_import_of_an_outside_module_binds_the_exports_of_its_stub(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
from facade import *
from glob import *
from string import *
def use():
    join("a", "b")
    escape("a")
    has_magic("a")
    Template("a").substitute()
""",
            "facade.py": "from os.path import *\n",
        },
    )

    assert callees(graph, "main.use") == [
        "glob.escape",
        "os.path.join",
        "string.Template",
        "string.Template.substitute",
    ]


def test_builtins_reached_through_the_module_are_the_builtins(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import builtins
        import builtins as b
        from builtins import getattr as get
        class Handler:
            def run(self): pass
        def through_import():
            get(Handler(), "run")()
        def through_module():
            builtins.getattr(Handler(), "run")()
            b.len([])
        """,
    )

    assert callees(graph, "main.through_import") == [
        "<builtin>.getattr",
        "main.Handler.run",
    ]
    assert callees(graph, "main.through_module") == [
        "<builtin>.getattr",
        "<builtin>.len",
        "main.Handler.run",
    ]


LAZY_MODULES = {
    "report.py": "def setup(): pass\ndef build(): pass\nsetup()\n",
    "audit.py": "def record(): pass\nrecord()\n",
}

lazy_syntax = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` is Python 3.15 syntax"
)


def lazy_graph(tmp_path, main):
    return call_graph(tmp_path, {"main.py": main, **LAZY_MODULES})


@lazy_syntax
def test_a_lazy_import_that_the_module_never_reads_does_not_run(tmp_path):
    graph = lazy_graph(
        tmp_path, "lazy import report\nlazy import audit\nreport.build()\n"
    )

    assert "audit" not in graph
    assert callees(graph, "report") == ["report.setup"]
    assert callees(graph, "main") == ["report.build"]


@lazy_syntax
def test_a_read_anywhere_in_the_module_runs_a_lazy_import(tmp_path):
    graph = lazy_graph(
        tmp_path,
        """
lazy from audit import record
def later():
    record()
""",
    )

    assert callees(graph, "audit") == ["audit.record"]
    assert callees(graph, "main.later") == ["audit.record"]


def test_a_module_listed_in_lazy_modules_is_imported_lazily(tmp_path):
    graph = lazy_graph(
        tmp_path,
        """
__lazy_modules__ = ["audit"]
import audit
import report
report.build()
""",
    )

    assert "audit" not in graph
    assert callees(graph, "report") == ["report.setup"]


def test_lazy_modules_applies_only_to_later_top_level_imports(tmp_path):
    graph = lazy_graph(
        tmp_path,
        """
import report
__lazy_modules__ = ["audit", "report"]
try:
    import audit
except ImportError:
    pass
""",
    )

    assert callees(graph, "report") == ["report.setup"]
    assert callees(graph, "audit") == ["audit.record"]


def test_a_module_that_uses_its_namespace_reads_every_lazy_import(tmp_path):
    graph = lazy_graph(
        tmp_path,
        """
__lazy_modules__ = ["audit"]
import audit
globals()["audit"].record()
""",
    )

    assert callees(graph, "audit") == ["audit.record"]


@pytest.mark.parametrize(
    "change", ["__lazy_modules__.clear()", '__lazy_modules__ += ["report"]']
)
def test_a_lazy_modules_that_is_not_one_literal_makes_no_import_lazy(tmp_path, change):
    graph = lazy_graph(
        tmp_path,
        f"""
__lazy_modules__ = ["audit"]
{change}
import audit
""",
    )

    assert callees(graph, "audit") == ["audit.record"]


def test_limit_a_coroutine_names_an_attribute_that_it_lacks(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        async def work():
            pass
        def use():
            pending = work()
            try:
                pending.cancel()
            except AttributeError:
                pass
            pending.close()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.work",
        "types.CoroutineType.cancel",
        "types.CoroutineType.close",
    ]


def test_limit_an_operator_on_a_string_constant_gives_no_receiver(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(count):
            ("ab" * count).upper()
            "abc"[1:].strip()
        """,
    )

    assert callees(graph, "main.use") == []
