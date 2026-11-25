from programs import callees, main_graph
from test_order_independence import orders

from pycg.analysis import solver


def test_methods_of_builtin_types_return_typed_values(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        text = "  a,b  "
        text.strip().split(",")
        "-".join(["x", "y"]).upper()
        len(text).bit_length()
        str(1).lower()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.int.bit_length",
        "<builtin>.len",
        "<builtin>.str",
        "<builtin>.str.join",
        "<builtin>.str.lower",
        "<builtin>.str.split",
        "<builtin>.str.strip",
        "<builtin>.str.upper",
    ]


def test_a_method_that_the_type_does_not_have_gives_no_edge(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        "text".no_such_method()
        [1, 2].index(1).no_such_method()
        str.no_such_method("x")
        """,
    )

    assert callees(graph, "main") == ["<builtin>.list.index"]


def test_modelled_methods_keep_their_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        handlers = {"f": f}
        handlers.get("f")()
        sorted([g])[0]()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.dict.get",
        "<builtin>.sorted",
        "main.f",
        "main.g",
    ]


def test_generator_methods_are_named_through_their_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def worker():
            yield 1
        g = worker()
        g.send(None)
        g.close()
        """,
    )

    assert callees(graph, "main") == [
        "main.worker",
        "types.GeneratorType.close",
        "types.GeneratorType.send",
    ]


def test_standard_streams_are_text_io_wrappers(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import sys
        from sys import stderr
        def report(text, file=sys.stdout):
            file.write(text)
            file.flush()
        def read():
            return sys.stdin.readline()
        stderr.write("x")
        report("y")
        read()
        """,
    )

    assert callees(graph, "main") == [
        "io.TextIOWrapper.write",
        "main.read",
        "main.report",
    ]
    assert callees(graph, "main.report") == [
        "io.TextIOWrapper.flush",
        "io.TextIOWrapper.write",
    ]
    assert callees(graph, "main.read") == ["io.TextIOWrapper.readline"]


def test_stub_variables_that_hold_a_function_name_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import shutil
        import timeit
        from shutil import rmtree
        from timeit import default_timer
        def use(path):
            timeit.default_timer().is_integer()
            default_timer()
            shutil.rmtree(path)
            rmtree(path, ignore_errors=True)
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.float.is_integer",
        "shutil.rmtree",
        "time.perf_counter",
    ]


def test_other_variables_of_sys_keep_their_stub_types(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import sys
        sys.path.append("x")
        sys.argv.copy()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.list.append", "<builtin>.list.copy"]


def test_methods_of_standard_library_results(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        import logging
        import collections
        pattern = re.compile("a+")
        pattern.match("aa").group()
        logging.getLogger("app").info("started")
        cache = collections.OrderedDict()
        cache.move_to_end("k")
        cache.get("k")
        """,
    )

    assert callees(graph, "main") == [
        "collections.OrderedDict",
        "collections.OrderedDict.get",
        "collections.OrderedDict.move_to_end",
        "logging.Logger.info",
        "logging.getLogger",
        "re.Match.group",
        "re.Pattern.match",
        "re.compile",
    ]


def test_names_that_the_stubs_do_not_have_give_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        re.no_such_function()
        re.compile("a").no_such_method()
        """,
    )

    assert callees(graph, "main") == ["re.compile"]


def test_a_result_of_unknown_type_has_no_invented_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import json
        json.loads("{}").get("k")
        """,
    )

    assert callees(graph, "main") == ["json.loads"]


def test_methods_of_abstract_types_give_no_edge(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        async def start(): pass
        loop = asyncio.new_event_loop()
        loop.run_until_complete(start())
        """,
    )

    assert callees(graph, "main") == ["asyncio.new_event_loop", "main.start"]


def test_a_type_variable_returns_the_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import copy
        import typing
        class Widget:
            def render(self): pass
        copy.copy(Widget()).render()
        """,
    )

    assert "main.Widget.render" in callees(graph, "main")
    assert "copy.copy" in callees(graph, "main")


def test_a_type_variable_that_no_argument_binds_is_its_bound(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import argparse
        subparsers = argparse.ArgumentParser().add_subparsers()
        subparsers.add_parser("info").add_argument("x")
        """,
    )

    assert "argparse.ArgumentParser.add_argument" in callees(graph, "main")


def test_typing_cast_returns_its_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import typing
        class Base:
            def run(self): pass
        class Impl(Base):
            def run(self): pass
        def execute(obj):
            typing.cast(Base, obj).run()
        execute(Impl())
        """,
    )

    assert callees(graph, "main.execute") == ["main.Impl.run", "typing.cast"]


def test_iterating_a_typed_result(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        for match in re.finditer("a", "aa"):
            match.span()
        """,
    )

    assert callees(graph, "main") == ["re.Match.span", "re.finditer"]


def test_code_without_stubs_keeps_its_path_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        ext.client.get()
        ext.Error.no_such_name()
        """,
    )

    assert callees(graph, "main") == ["ext.Error.no_such_name", "ext.client.get"]


def test_caught_exceptions_are_instances_of_their_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        try:
            pass
        except ValueError as error:
            error.with_traceback(None)
            error.no_such_method()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.ValueError.with_traceback"]


def test_an_instance_of_an_outside_class_is_called_through_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import functools
        def add(a, b): pass
        functools.partial(add, 1)(2)
        """,
    )

    assert "functools.partial.__call__" in callees(graph, "main")


def test_a_module_variable_is_a_value_of_its_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import os
        os.environ.get("HOME")
        os.sep.join(["a", "b"])
        """,
    )

    assert callees(graph, "main") == ["<builtin>.str.join", "os._Environ.get"]


def test_calling_a_function_object_gives_no_call_of_its_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import types
        class C:
            def m(self): pass
        def f(): pass
        types.MethodType(f, C())()
        """,
    )

    assert "types.MethodType.__call__" not in callees(graph, "main")
    assert "types.MethodType" in callees(graph, "main")


def test_a_name_that_the_outside_base_does_not_have_is_not_found(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Mixin:
            def helper(self): pass
        class Task(abc.ABC, Mixin):
            def run(self):
                self.sleep()
                self.helper()
        """,
    )

    assert callees(graph, "main.Task.run") == ["main.Mixin.helper"]


def test_inherited_outside_methods_are_named_through_the_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import collections.abc
        class Store(collections.abc.MutableMapping):
            def __getitem__(self, key): pass
            def __setitem__(self, key, value): pass
            def __delitem__(self, key): pass
            def __iter__(self): pass
            def __len__(self): pass
        def use():
            Store().popitem()
            Store().no_such_method()
        """,
    )

    assert callees(graph, "main.use") == ["collections.abc.MutableMapping.popitem"]


def test_a_typing_alias_of_a_collections_abc_class_is_that_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import typing
        import typing_extensions
        import collections.abc
        from typing import AbstractSet, AsyncIterator
        class A(typing.Iterator):
            def __next__(self): pass
        class B(AsyncIterator):
            async def __anext__(self): pass
        class C(AbstractSet):
            def __contains__(self, x): return False
            def __iter__(self): yield from ()
            def __len__(self): return 0
        class D(typing.Iterator[int]):
            def __next__(self): pass
        class E(typing_extensions.Mapping):
            def __getitem__(self, key): pass
            def __iter__(self): yield from ()
            def __len__(self): return 0
        class F(collections.abc.Iterator):
            def __next__(self): pass
        class G(typing.IO):
            pass
        def iterator(): A().__iter__()
        def async_iterator(): B().__aiter__()
        def abstract_set(): C().isdisjoint(())
        def subscripted(): D().__iter__()
        def through_typing_extensions(): E().keys()
        def collections_abc(): F().__iter__()
        def typing_only(): G().close()
        """,
    )

    assert callees(graph, "main.iterator") == ["collections.abc.Iterator.__iter__"]
    assert callees(graph, "main.async_iterator") == [
        "collections.abc.AsyncIterator.__aiter__"
    ]
    assert callees(graph, "main.abstract_set") == ["collections.abc.Set.isdisjoint"]
    assert callees(graph, "main.subscripted") == ["collections.abc.Iterator.__iter__"]
    assert callees(graph, "main.through_typing_extensions") == [
        "collections.abc.Mapping.keys"
    ]
    assert callees(graph, "main.collections_abc") == [
        "collections.abc.Iterator.__iter__"
    ]
    assert callees(graph, "main.typing_only") == ["typing.IO.close"]


ITERATOR_BASES = """
import collections.abc
def f(): pass
class Items(collections.abc.Iterator):
    def __next__(self): return f
class Steps(collections.abc.Generator):
    def __next__(self): return f
    def send(self, value): return f
    def throw(self, *args): pass
class Stream(collections.abc.AsyncIterator):
    async def __anext__(self): return f
class Rows(collections.abc.Sequence):
    def __getitem__(self, index): pass
    def __len__(self): return 0
    def __next__(self): return f
def items():
    for item in Items():
        item()
def steps():
    for step in Steps():
        step()
def explicit():
    Items().__iter__().__next__()
async def stream():
    async for item in Stream():
        item()
    await Stream().__aiter__().__anext__()
def rows():
    for row in Rows():
        row()
"""


def test_iter_of_an_iterator_and_aiter_of_an_async_iterator_return_the_receiver(
    tmp_path,
):
    graph = main_graph(tmp_path, ITERATOR_BASES)

    assert callees(graph, "main.items") == ["main.Items.__next__", "main.f"]
    assert callees(graph, "main.steps") == ["main.Steps.__next__", "main.f"]
    assert callees(graph, "main.explicit") == [
        "collections.abc.Iterator.__iter__",
        "main.Items.__next__",
    ]
    assert callees(graph, "main.stream") == [
        "collections.abc.AsyncIterator.__aiter__",
        "main.Stream.__anext__",
        "main.f",
    ]
    assert callees(graph, "main.rows") == ["main.Rows.__getitem__"]


def test_a_member_of_an_outside_base_is_named_one_step_past_the_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import concurrent.futures
        import multiprocessing
        class Task(concurrent.futures._base.Future): pass
        class Reducer(multiprocessing.reduction.AbstractReducer): pass
        class Pickler(Reducer.ForkingPickler): pass
        def use():
            Task().done()
            Pickler(None).dump(1)
        """,
    )

    assert callees(graph, "main.use") == ["concurrent.futures._base.Future.done"]


def test_object_init_runs_without_an_edge_unless_it_is_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Event(abc.ABC):
            pass
        class Request(Event):
            def __init__(self):
                super().__init__()
        class Error(Exception):
            pass
        def make():
            Event()
            Request()
            Error("x")
        """,
    )

    assert callees(graph, "main.make") == [
        "<builtin>.Exception.__init__",
        "main.Request.__init__",
    ]
    assert callees(graph, "main.Request.__init__") == [
        "<builtin>.super",
        "abc.ABC.__init__",
    ]


def test_explicit_calls_of_object_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Audited:
            def __setattr__(self, name, value):
                super().__setattr__(name, value)
        class Clone:
            def __init__(self, value): pass
            def copy(self):
                return self.__class__(1)
        Audited().x = 1
        Clone(0).copy()
        """,
    )

    assert callees(graph, "main.Audited.__setattr__") == [
        "<builtin>.object.__setattr__",
        "<builtin>.super",
    ]
    assert callees(graph, "main.Clone.copy") == ["main.Clone.__init__"]


def test_decorators_that_library_factories_return_are_named_as_they_run(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import dataclasses
        import functools
        @dataclasses.dataclass(frozen=True)
        class Point:
            x: int = 0
        @dataclasses.dataclass
        class Plain:
            y: int = 0
        def logged(func):
            @functools.wraps(func)
            def wrapper(*args):
                return func(*args)
            return wrapper
        """,
    )

    assert callees(graph, "main") == [
        "dataclasses.dataclass",
        "dataclasses.dataclass.wrap",
    ]
    assert callees(graph, "main.logged") == [
        "functools.partial.__call__",
        "functools.wraps",
    ]


def test_an_attribute_typed_with_type_of_a_type_variable(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from dataclasses import dataclass, fields
        @dataclass
        class Record:
            value: int
        def use():
            fields(Record)[0].type
        """,
    )

    assert callees(graph, "main.use") == ["dataclasses.fields"]


def test_tuple_results_of_different_lengths_at_one_call(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import os.path
        def use():
            for split in (os.path.split, os.path.splitroot):
                head = split("/tmp/file")[0]
                head.upper()
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.str.upper",
        "os.path.split",
        "os.path.splitroot",
    ]


def test_a_class_method_that_returns_self_through_the_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import pathlib
        from datetime import date
        def use():
            date.today().isoformat()
            int.from_bytes(b"\\\\x01", "big").bit_length()
            pathlib.Path.cwd().joinpath("x")
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.int.bit_length",
        "<builtin>.int.from_bytes",
        "datetime.date.isoformat",
        "datetime.date.today",
        "pathlib.Path.cwd",
        "pathlib.Path.joinpath",
    ]


def test_a_module_variable_imported_by_name(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from os import environ
        environ.get("HOME")
        """,
    )

    assert callees(graph, "main") == ["os._Environ.get"]


def test_members_of_the_metaclass_of_an_outside_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class API(abc.ABC):
            pass
        class Implementation:
            pass
        API.register(Implementation)
        """,
    )

    assert callees(graph, "main") == ["abc.ABC.register"]


def test_self_on_an_analysed_receiver_is_the_receiver_and_a_new_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import pathlib
        class Local(pathlib.PurePosixPath):
            def mark(self): pass
        def tag(): pass
        def use(path):
            path.tag = tag
            copy = path.with_suffix(".x")
            copy.tag()
            copy.mark()
        use(Local("a"))
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Local.mark",
        "main.tag",
        "pathlib.PurePosixPath.with_suffix",
    ]


def test_a_metaclass_method_does_not_hide_what_object_defines(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class C(abc.ABC):
            pass
        C()
        C.register(int)
        """,
    )

    assert callees(graph, "main") == ["abc.ABC.register"]


def test_a_stub_new_gives_an_instance_of_the_class_it_is_given(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class S(str):
            def __new__(cls, value):
                return super().__new__(cls, value)
            def go(self): pass
        class E(Exception):
            def __new__(cls, *args):
                return super().__new__(cls, *args)
            def go(self): pass
        class T(tuple):
            def __new__(cls, a, b):
                return tuple.__new__(cls, (a, b))
            def go(self): pass
        S("x").go()
        E().go()
        T(1, 2).go()
        str.__new__(str, "x").upper()
        """,
    )

    assert {
        "main.E.go",
        "main.S.go",
        "main.T.go",
        "<builtin>.str.upper",
    } <= set(callees(graph, "main"))


def test_a_class_with_base_named_tuple_is_a_tuple_subclass(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from typing import NamedTuple
        class Point(NamedTuple):
            x: int
            def total(self):
                return self.x
        Point(1).total()
        Point(1).count(1)
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.tuple.count",
        "main.Point.total",
    ]


def test_an_alias_of_an_outside_class_is_a_type_on_every_python(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import pathlib
        Failure = PythonFinalizationError | None
        MaybePath = pathlib.Path | None
        def report(error: Failure, path: MaybePath):
            error.add_note("details")
            path.exists()
        """,
    )

    assert {
        "<builtin>.PythonFinalizationError.add_note",
        "pathlib.Path.exists",
    } <= set(callees(graph, "main.report"))


def test_limit_results_are_the_union_over_overloads(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import subprocess
        subprocess.check_output(["ls"], text=True).splitlines()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.bytes.splitlines",
        "<builtin>.str.splitlines",
        "subprocess.check_output",
    ]


def test_limit_a_result_whose_class_python_chooses_at_run_time_keeps_its_stub_type(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        import importlib.resources
        from xml.sax import make_parser
        def cb(): pass
        async def run():
            asyncio.get_running_loop().call_later(1, cb)
            asyncio.new_event_loop().stop()
        def parse(stream):
            make_parser().parse(stream)
        def data():
            importlib.resources.files("pkg").joinpath("x.bin").open("rb").read()
        """,
    )

    assert callees(graph, "main.run") == [
        "asyncio.get_running_loop",
        "asyncio.new_event_loop",
    ]
    assert callees(graph, "main.parse") == [
        "xml.sax.make_parser",
        "xml.sax.xmlreader.XMLReader.parse",
    ]
    assert callees(graph, "main.data") == ["importlib.resources.files"]


def test_open_gives_the_class_that_a_constant_mode_selects(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import io
        import os
        import pathlib
        def text():
            open("p").close()
        def text_mode():
            open("p", "rt").close()
        def updated_text():
            open("p", mode="a+").close()
        def read():
            open("p", "rb").close()
        def write():
            open("p", mode="wb").close()
        def append():
            open("p", "ab", -1).close()
        def exclusive():
            open("p", "xb").close()
        def update():
            open("p", "r+b").close()
        def raw():
            open("p", "rb", 0).close()
        def raw_by_keyword():
            open("p", "wb", buffering=0).close()
        def line_buffered():
            io.open("p", "w", 1).close()
        def descriptor():
            os.fdopen(3, "rb").close()
        def path():
            pathlib.Path("p").open("wb").close()
        def path_text():
            pathlib.Path("p").open().close()
        text()
        text_mode()
        updated_text()
        read()
        write()
        append()
        exclusive()
        update()
        raw()
        raw_by_keyword()
        line_buffered()
        descriptor()
        path()
        path_text()
        """,
    )

    def closed(caller):
        return [c for c in callees(graph, caller) if c.endswith(".close")]

    assert closed("main.text") == ["io.TextIOWrapper.close"]
    assert closed("main.text_mode") == ["io.TextIOWrapper.close"]
    assert closed("main.updated_text") == ["io.TextIOWrapper.close"]
    assert closed("main.read") == ["io.BufferedReader.close"]
    assert closed("main.write") == ["io.BufferedWriter.close"]
    assert closed("main.append") == ["io.BufferedWriter.close"]
    assert closed("main.exclusive") == ["io.BufferedWriter.close"]
    assert closed("main.update") == ["io.BufferedRandom.close"]
    assert closed("main.raw") == ["io.FileIO.close"]
    assert closed("main.raw_by_keyword") == ["io.FileIO.close"]
    assert callees(graph, "main.line_buffered") == [
        "io.TextIOWrapper.close",
        "io.open",
    ]
    assert callees(graph, "main.descriptor") == [
        "io.BufferedReader.close",
        "os.fdopen",
    ]
    assert callees(graph, "main.path") == [
        "io.BufferedWriter.close",
        "pathlib.Path",
        "pathlib.Path.open",
    ]
    assert closed("main.path_text") == ["io.TextIOWrapper.close"]


def test_a_file_opened_in_a_with_statement_has_the_class_of_its_mode(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def load(path):
            with open(path, "rb") as f:
                return f.read()
        load("p")
        """,
    )

    assert callees(graph, "main.load") == [
        "<builtin>.open",
        "io.BufferedReader.read",
    ]


def test_a_mode_or_buffering_from_a_default_selects_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def run(self, mode="rb"):
                open("p", mode).close()
        def method():
            return "run"
        # The method is reached only through a computed name, which the
        # completion resolves.
        getattr(C(), method())()
        def uncalled(mode="rb"):
            open("p", mode).close()
        def unbuffered(size=0):
            open("p", "rb", size).close()
        """,
    )

    def closed(caller):
        return [c for c in callees(graph, caller) if c.endswith(".close")]

    assert closed("main.C.run") == ["io.BufferedReader.close"]
    assert closed("main.uncalled") == ["io.BufferedReader.close"]
    assert closed("main.unbuffered") == ["io.FileIO.close"]


def test_a_mode_read_through_a_class_attribute_selects_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import enum
        class Options:
            mode = "rb"
            size = 0
        class Mode(enum.StrEnum):
            WRITE = "wb"
        def read():
            open("p", Options.mode).close()
        def raw():
            open("p", "wb", Options.size).close()
        def write():
            open("p", Mode.WRITE).close()
        read()
        raw()
        write()
        """,
    )

    def closed(caller):
        return [c for c in callees(graph, caller) if c.endswith(".close")]

    assert closed("main.read") == ["io.BufferedReader.close"]
    assert closed("main.raw") == ["io.FileIO.close"]
    assert closed("main.write") == ["io.BufferedWriter.close"]


def test_limit_an_argument_that_another_open_of_the_same_step_gives(
    tmp_path, monkeypatch
):
    source = """
        import re
        class Options:
            mode = "rb"
        def repl(match):
            names = open("/dev/null", "r", match.end()).readlines()
            names.append("mode")
            open("/dev/null", getattr(Options, names[-1])).close()
            return ""
        re.sub("r", repl, "r")
        """
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        graph = main_graph(tmp_path / name.replace(" ", "-"), source)

        found = [c for c in callees(graph, "main.repl") if c.startswith("io.")]
        assert found == [
            "io.BufferedRandom.close",
            "io.BufferedReader.close",
            "io.BufferedWriter.close",
            "io.TextIOWrapper.close",
            "io.TextIOWrapper.readlines",
        ], name


def test_open_with_modes_that_are_not_one_constant(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def two(mode):
            open("p", mode).close()
        def unknown(mode: str):
            open("p", mode).close()
        def missing(mode):
            open("p", mode).close()
        def buffering(size):
            open("p", "rb", size).close()
        def rejected():
            open("p", "rw").close()
            open("p", "w", 0).close()
        def unpacked(args):
            open("p", *args).close()
        two("r")
        two("wb")
        unknown("r")
        buffering(0)
        buffering(4096)
        rejected()
        unpacked(["r"])
        """,
    )

    def closed(caller):
        return [c for c in callees(graph, caller) if c.endswith(".close")]

    buffered = [
        "io.BufferedRandom.close",
        "io.BufferedReader.close",
        "io.BufferedWriter.close",
        "io.TextIOWrapper.close",
    ]
    assert closed("main.two") == ["io.BufferedWriter.close", "io.TextIOWrapper.close"]
    assert closed("main.unknown") == buffered
    assert closed("main.missing") == buffered
    assert closed("main.unpacked") == sorted([*buffered, "io.FileIO.close"])
    assert closed("main.buffering") == [
        "io.BufferedReader.close",
        "io.FileIO.close",
    ]
    assert closed("main.rejected") == []


def test_a_constrained_type_variable_is_the_constraint_its_value_is(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import glob
        def text():
            glob.escape("x").upper()
        def data():
            glob.escape(b"x").lower()
        def other():
            glob.escape(bytearray(b"x")).lower()
        text()
        data()
        other()
        """,
    )

    assert "<builtin>.str.upper" in callees(graph, "main.text")
    assert "<builtin>.bytes.upper" not in callees(graph, "main.text")
    assert "<builtin>.bytes.lower" in callees(graph, "main.data")
    assert "<builtin>.str.lower" not in callees(graph, "main.data")
    assert "<builtin>.bytearray.lower" not in callees(graph, "main.other")


def test_limit_an_outside_base_hides_a_mixin_with_a_shared_ancestor(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from collections import UserDict
        from collections.abc import MutableMapping
        class Mixin(MutableMapping):
            def popitem(self):
                return ("x", None)
        class C(UserDict, Mixin):
            pass
        C().popitem()
        """,
    )

    assert "collections.UserDict.popitem" in callees(graph, "main")
    assert "main.Mixin.popitem" not in callees(graph, "main")


def test_a_parameter_annotated_with_an_outside_class_has_its_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import logging
        import re
        import threading
        import typing
        from typing import Optional
        def use(
            logger: logging.Logger,
            pattern: "re.Pattern[str]",
            event: Optional[threading.Event],
            names: list[str],
            kind: type[ValueError],
            items: typing.Iterable[str],
        ):
            logger.info("x")
            pattern.match("x")
            event.wait()
            names[0].upper()
            kind("x")
            # An abstract type does not fix the class: no edge.
            items.no_such_method()
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.ValueError",
        "<builtin>.str.upper",
        "logging.Logger.info",
        "re.Pattern.match",
        "threading.Event.wait",
    ]


def test_a_parameter_typed_awaitable_binds_what_the_argument_finishes_with(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        class Result:
            def done(self): pass
        async def main():
            return Result()
        async def later():
            return Result()
        asyncio.run(main()).done()
        def use():
            asyncio.Runner().run(later()).done()
        """,
    )

    assert "main.Result.done" in callees(graph, "main")
    assert "main.Result.done" in callees(graph, "main.use")


def test_awaiting_a_typed_result_gives_the_typed_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        async def use():
            (await asyncio.create_subprocess_exec("ls")).wait()
        """,
    )

    assert "asyncio.subprocess.Process.wait" in callees(graph, "main.use")


def test_async_with_and_async_for_on_stub_objects_await_their_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        async def use():
            async with asyncio.timeout(1) as t:
                t.expired()
            reader, writer = await asyncio.open_connection("h", 1)
            async for line in reader:
                line.decode()
        """,
    )

    assert {
        "asyncio.Timeout.expired",
        "<builtin>.bytes.decode",
    } <= set(callees(graph, "main.use"))


def test_awaiting_an_instance_without_await_gives_the_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        class Result:
            def done(self): pass
        class Later:
            def __await__(self):
                yield
                return 1
        async def make():
            return Result()
        async def use():
            (await asyncio.wait_for(make(), 1)).done()
            (await asyncio.sleep(0, Result())).done()
            await Later()
        asyncio.run(use())
        """,
    )

    assert {"main.Result.done", "main.Later.__await__"} <= set(
        callees(graph, "main.use")
    )


def test_a_class_method_returning_self_gives_the_class_it_was_loaded_through(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        from datetime import datetime
        datetime.fromordinal(739000).timestamp()
        """,
    )

    assert "datetime.datetime.timestamp" in callees(graph, "main")
