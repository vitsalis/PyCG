"""Behaviour tests for micro-benchmark/validate.py."""

import importlib.util
import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest

if sys.version_info < (3, 14):
    pytest.skip("the validator needs Python 3.14 or later", allow_module_level=True)

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "micro-benchmark" / "validate.py"
_spec = importlib.util.spec_from_file_location("benchmark_validate", VALIDATOR_PATH)
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def make_case(root, files, graph=None):
    """Write a snippet directory from {relative path: source} and a call graph."""
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source))
    if graph is not None:
        (root / "callgraph.json").write_text(json.dumps(graph))
    return root


def edges_of(root, files):
    result = validate.trace(make_case(root, files))
    assert result.error is None, result.error
    return result.edges


def test_nested_function_is_named_without_locals(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    def outer():
                        def inner():
                            pass
                        inner()

                    outer()
                """
            },
        )
    )
    assert result.edges == {("main", "main.outer"), ("main.outer", "main.outer.inner")}
    assert result.functions == {"main.outer", "main.outer.inner"}
    assert result.modules == {"main"}


def test_lambdas_are_numbered_per_scope_in_source_order(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                first, second = lambda: 1, lambda: 2
                second()

                def func():
                    third = lambda: 3
                    third()
                    return lambda: 4

                func()()
            """
        },
    )
    assert edges == {
        ("main", "main.<lambda2>"),
        ("main", "main.func"),
        ("main.func", "main.func.<lambda1>"),
        ("main", "main.func.<lambda2>"),
    }


def test_lambda_numbering_follows_source_position_not_evaluation_order(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                f = (lambda: 1) if (lambda: False)() else (lambda: 2)
                f()
                g, h = [lambda: 3 for _ in range(1)][0], (lambda: 4)
                h()
            """
        },
    )
    assert edges == {
        ("main", "main.<lambda2>"),
        ("main", "main.<lambda3>"),
        ("main", "<builtin>.range"),
        ("main", "main.<lambda5>"),
    }


def test_class_instantiation_calls_init_from_the_mro(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Base:
                    def __init__(self):
                        pass

                class Child(Base):
                    def method(self):
                        pass

                class Plain:
                    pass

                Child().method()
                Plain()
            """
        },
    )
    assert edges == {("main", "main.Base.__init__"), ("main", "main.Child.method")}


def test_init_inherited_from_outside_the_snippet_is_named_by_its_owner(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                from collections import UserList

                class Error(Exception):
                    pass

                class Items(UserList):
                    pass

                class Own(Exception):
                    def __init__(self):
                        super().__init__()

                Error()
                Items()
                Own()
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.Exception.__init__"),  # named through Exception
        ("main", "collections.UserList.__init__"),
        ("main", "main.Own.__init__"),
        ("main.Own.__init__", "<builtin>.super"),
        ("main.Own.__init__", "<builtin>.BaseException.__init__"),
    }


def test_instance_call_inherited_from_outside_is_named_through_the_owner(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import functools
                from contextlib import ContextDecorator

                class Bound(functools.partial):
                    pass

                class Tracked(ContextDecorator):
                    def __enter__(self):
                        return self

                    def __exit__(self, *exc_info):
                        return False

                class Own:
                    def __call__(self):
                        pass

                def add(a, b):
                    return a + b

                @Tracked()
                def work():
                    pass

                Bound(add, 1)(2)
                work()
                Own()()
            """
        },
    )
    assert edges == {
        ("main", "functools.partial.__call__"),
        ("main", "main.add"),
        ("main", "contextlib.ContextDecorator.__call__"),
        ("main", "contextlib.ContextDecorator.__call__.inner"),
        ("main", "main.Tracked.__enter__"),
        ("main", "main.work"),
        ("main", "main.Tracked.__exit__"),
        ("main", "main.Own.__call__"),
    }


def test_calls_in_class_body_belong_to_enclosing_scope(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def helper():
                    return 1

                class A:
                    value = helper()

                    @staticmethod
                    def method():
                        pass
            """
        },
    )
    assert edges == {("main", "main.helper"), ("main", "<builtin>.staticmethod")}


def test_builtin_functions_types_and_methods(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                len([1])
                range(3)
                " ".join(["a"])
                {"a": 1}.items()
                str.upper("a")

                class MyList(list):
                    pass

                append = MyList().append  # a bound builtin method object
                append(1)
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.len"),
        ("main", "<builtin>.range"),
        ("main", "<builtin>.str.join"),
        ("main", "<builtin>.dict.items"),
        ("main", "<builtin>.str.upper"),
        ("main", "<builtin>.list.__init__"),
        ("main", "<builtin>.list.append"),
    }


def test_builtin_method_reached_through_super_is_named_by_its_definer(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Plugin:
                    def __init_subclass__(cls):
                        super().__init_subclass__()

                class Audio(Plugin):
                    pass

                class Table(dict):
                    @classmethod
                    def fromkeys(cls, keys):
                        return super().fromkeys(keys)

                    def copy(self):
                        return super().copy()

                Table.fromkeys(["a"]).copy()
            """
        },
    )
    assert edges == {
        ("main", "main.Plugin.__init_subclass__"),
        ("main.Plugin.__init_subclass__", "<builtin>.super"),
        ("main.Plugin.__init_subclass__", "<builtin>.object.__init_subclass__"),
        ("main", "<builtin>.classmethod"),
        ("main", "main.Table.fromkeys"),
        ("main.Table.fromkeys", "<builtin>.super"),
        ("main.Table.fromkeys", "<builtin>.dict.fromkeys"),
        ("main", "main.Table.copy"),
        ("main.Table.copy", "<builtin>.super"),
        ("main.Table.copy", "<builtin>.dict.copy"),
    }


def test_implicit_interpreter_calls_to_builtins_are_ignored(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Seq:
                    def __iter__(self):
                        return iter([])

                with open(__file__) as f:
                    pass
                f.__exit__(None, None, None)
                for item in Seq():
                    pass
                d = {}
                d["key"] = 1
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.open"),
        ("main", "_io._IOBase.__exit__"),
        ("main", "main.Seq.__iter__"),
        ("main.Seq.__iter__", "<builtin>.iter"),
    }


def test_explicit_enter_call_as_the_with_item_is_a_call(tmp_path):
    # The call has the source position of the with item, like the calls that
    # the with statement makes.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                with open(__file__).__enter__() as f:
                    pass
                with open(__file__).__exit__(None, None, None) or open(__file__):
                    pass
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.open"),
        ("main", "_io._IOBase.__enter__"),
        ("main", "_io._IOBase.__exit__"),
    }


def test_async_with_calls_snippet_coroutine_methods(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import asyncio

                class Session:
                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *exc_info):
                        return False

                async def start():
                    async with Session():
                        pass

                asyncio.run(start())
            """
        },
    )
    assert edges == {
        ("main", "asyncio.runners.run"),
        ("main", "main.start"),
        ("main.start", "main.Session.__aenter__"),
        ("main.start", "main.Session.__aexit__"),
    }


def test_callback_from_builtin_belongs_to_the_caller_of_the_builtin(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func(x):
                    return x

                def key(x):
                    return x

                def run():
                    return sorted([2, 1], key=key)

                list(map(func, [1, 2]))
                run()
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.list"),
        ("main", "<builtin>.map"),
        ("main", "main.func"),
        ("main", "main.run"),
        ("main.run", "<builtin>.sorted"),
        ("main.run", "main.key"),
    }


def test_comprehension_and_generator_expression_belong_to_enclosing_scope(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func(x):
                    return x

                def run():
                    return [func(x) for x in range(2)], sum(func(x) for x in range(2))

                run()
            """
        },
    )
    assert edges == {
        ("main", "main.run"),
        ("main.run", "main.func"),
        ("main.run", "<builtin>.range"),
        ("main.run", "<builtin>.sum"),
    }


def test_builtin_call_that_the_compiler_inlines_is_recorded(tmp_path):
    # Python 3.14+ compiles any(), all() and tuple() (3.15: also list() and
    # set()) over a generator expression into a loop when the name is the
    # builtin.
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    import shadow

                    def func(x):
                        return x

                    def run(xs):
                        return (
                            any(func(x) for x in xs),
                            all(func(x) for x in xs),
                            tuple(x for x in xs),
                            list(x for x in xs),
                            set(x for x in xs),
                        )

                    class Holder:
                        items = tuple(x for x in [1])

                    any(x for x in [1])
                    run([1])
                """,
                "shadow.py": """
                    def any(items):
                        return True

                    any(x for x in [1])
                """,
            },
        )
    )
    assert result.error is None, result.error
    assert result.edges == {
        ("main", "<builtin>.any"),
        ("main", "<builtin>.tuple"),
        ("main", "main.run"),
        ("main.run", "main.func"),
        ("main.run", "<builtin>.any"),
        ("main.run", "<builtin>.all"),
        ("main.run", "<builtin>.tuple"),
        ("main.run", "<builtin>.list"),
        ("main.run", "<builtin>.set"),
        ("shadow", "shadow.any"),  # the name is not the builtin
    }


def test_identity_check_with_a_common_constant_is_not_a_call(tmp_path):
    # Python 3.15 loads True, False and None with LOAD_COMMON_CONSTANT, like
    # the check of an inlined builtin call.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                value = True
                nothing = None
                if value is True:
                    pass
                if value is not False:
                    pass
                if nothing is None:
                    pass
                for item in (x for x in [value] if x is True):
                    pass
            """
        },
    )
    assert edges == set()


def test_inlined_builtin_call_counts_only_if_the_builtin_runs(tmp_path):
    # The argument of an inlined call raises before the builtin would run.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                try:
                    any(x for x in 1 / 0)
                except ZeroDivisionError:
                    pass
                try:
                    all(x for x in 5)
                except TypeError:
                    pass
            """
        },
    )
    assert edges == set()


def test_generator_edge_comes_from_the_call_site_not_the_consumer(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def gen():
                    yield 1

                def consume(it):
                    for _ in it:
                        pass

                consume(gen())
            """
        },
    )
    assert edges == {("main", "main.gen"), ("main", "main.consume")}


def test_coroutine_function_that_the_interpreter_calls(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import asyncio

                class Countdown:
                    def __init__(self, n):
                        self.n = n

                    def __aiter__(self):
                        return self

                    async def __anext__(self):
                        if self.n == 0:
                            raise StopAsyncIteration
                        self.n -= 1
                        return self.n

                async def fetch():
                    pass

                async def wait_for(coro):
                    await coro

                async def loop():
                    async for _ in Countdown(2):
                        pass

                async def step():
                    pending = anext(Countdown(1))
                    await pending

                async def start():
                    await loop()
                    await step()
                    await wait_for(fetch())

                asyncio.run(start())
            """
        },
    )
    assert edges == {
        ("main", "asyncio.runners.run"),
        ("main", "main.start"),
        ("main.start", "main.loop"),
        ("main.start", "main.step"),
        ("main.start", "main.fetch"),
        ("main.start", "main.wait_for"),  # but not main.wait_for -> main.fetch
        ("main.loop", "main.Countdown.__init__"),
        ("main.loop", "main.Countdown.__aiter__"),
        ("main.loop", "main.Countdown.__anext__"),
        ("main.step", "main.Countdown.__init__"),
        ("main.step", "<builtin>.anext"),
        ("main.step", "main.Countdown.__anext__"),
    }


def test_coroutine_method_that_the_interpreter_calls_in_a_thread(tmp_path):
    # Coroutine origin tracking is per thread.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import asyncio
                import threading

                class Items:
                    def __init__(self):
                        self.left = 1

                    def __aiter__(self):
                        return self

                    async def __anext__(self):
                        if self.left == 0:
                            raise StopAsyncIteration
                        self.left -= 1
                        return self.left

                async def loop():
                    async for _ in Items():
                        pass

                def run():
                    asyncio.run(loop())

                thread = threading.Thread(target=run)
                thread.start()
                thread.join()
            """
        },
    )
    assert {edge for edge in edges if edge[1].startswith("main.")} == {
        ("main", "main.run"),
        ("main.run", "main.loop"),
        ("main.loop", "main.Items.__init__"),
        ("main.loop", "main.Items.__aiter__"),
        ("main.loop", "main.Items.__anext__"),
    }


def test_generator_function_called_by_library_code(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                from contextlib import contextmanager

                def acquire():
                    pass

                @contextmanager
                def managed():
                    acquire()
                    yield

                def use():
                    with managed():
                        pass

                use()
            """
        },
    )
    assert edges == {
        ("main", "contextlib.contextmanager"),
        ("main", "main.use"),
        ("main.use", "contextlib.contextmanager.helper"),
        ("main.use", "main.managed"),  # the scope whose library call runs it
        ("main.managed", "main.acquire"),
    }


def test_thread_callbacks_belong_to_the_scope_that_starts_the_thread(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import threading
                from concurrent.futures import ThreadPoolExecutor

                def work():
                    pass

                def task():
                    pass

                class Worker(threading.Thread):
                    def run(self):
                        pass

                def start_both():
                    thread = threading.Thread(target=work)
                    thread.start()
                    thread.join()
                    worker = Worker()
                    worker.start()
                    worker.join()

                def submit():
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        executor.submit(task).result()

                start_both()
                submit()
            """
        },
    )
    assert {edge for edge in edges if edge[1].startswith("main.")} == {
        ("main", "main.start_both"),
        ("main", "main.submit"),
        ("main.start_both", "main.work"),
        ("main.start_both", "main.Worker.run"),
        ("main.submit", "main.task"),  # the thread starts inside submit()
    }
    assert not any(validate.UNKNOWN_CALLER in edge for edge in edges)


def test_tracer_runs_no_snippet_code_to_classify_a_callee(tmp_path):
    # A lazy proxy reports the class of its target through a __class__
    # property; isinstance() falls back to it when the real type does not
    # match. The tracer must classify callables by their real type.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                log = []

                class Lazy(list):
                    @property
                    def __class__(self):
                        log.append("__class__")
                        return dict

                    def __call__(self):
                        pass

                lazy = Lazy()
                lazy()
                lazy.append(1)
                if log:
                    raise SystemExit(f"__class__ ran {len(log)} times")
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.property"),
        ("main", "<builtin>.list.__init__"),
        ("main", "main.Lazy.__call__"),
        ("main", "<builtin>.list.append"),
    }


def test_tracer_reads_no_attribute_of_a_replaced_module(tmp_path):
    # A module that replaces itself in sys.modules with an object whose
    # attribute access runs code (lazy loading).
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import lazy

                lazy.Item()
                if lazy.LOG != ["Item", "LOG"]:
                    raise SystemExit(f"attributes read: {lazy.LOG}")
            """,
            "lazy.py": """
                import sys

                LOG = []

                class Item:
                    def __init__(self):
                        pass

                class Module:
                    def __getattr__(self, name):
                        LOG.append(name)
                        return globals()[name]

                sys.modules[__name__] = Module()
            """,
        },
    )
    assert ("main", "lazy.Item.__init__") in edges
    assert ("main", "lazy.Module.__getattr__") in edges


def test_raise_in_a_class_body_with_a_custom_namespace_runs_no_snippet_code(tmp_path):
    # To find the class that `raise Problem` instantiates, the tracer reads
    # the name again from the class namespace, which __prepare__ made.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                LOG = []

                class Namespace(dict):
                    def __contains__(self, key):
                        LOG.append(key)
                        return dict.__contains__(self, key)

                    def __getitem__(self, key):
                        LOG.append(key)
                        return dict.__getitem__(self, key)

                    def __missing__(self, key):
                        LOG.append(key)
                        raise KeyError(key)

                class Meta(type):
                    @classmethod
                    def __prepare__(mcs, name, bases):
                        return Namespace()

                class Problem(Exception):
                    pass

                class Table(metaclass=Meta):
                    try:
                        raise Problem
                    except Problem:
                        pass

                # The class body's own lookups: __name__, then raise and except.
                # Each misses the namespace, so __getitem__ and __missing__ run.
                if LOG != ["__name__"] * 2 + ["Problem"] * 4:
                    raise SystemExit(f"names read: {LOG}")
            """
        },
    )
    assert ("main", "<builtin>.Exception.__init__") in edges  # raise Problem


def test_start_of_a_thread_without_init_does_not_break_the_tracer(tmp_path):
    # Thread.ident is a property that raises AssertionError on such a thread.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import threading

                thread = threading.Thread.__new__(threading.Thread)
                try:
                    thread.start()
                except RuntimeError:  # thread.__init__() not called
                    pass
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.object.__new__"),
        ("main", "threading.Thread.start"),
    }


def test_thread_callback_belongs_to_the_start_call_that_starts_it(tmp_path):
    # A second start() raises RuntimeError and does not start the thread. The
    # timer calls work() later, after the second start().
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import threading

                def work():
                    pass

                def start(timer):
                    timer.start()

                def start_again(timer):
                    try:
                        timer.start()
                    except RuntimeError:
                        pass

                timer = threading.Timer(0.3, work)
                start(timer)
                start_again(timer)
                timer.join()
            """
        },
    )
    assert {edge for edge in edges if edge[1].startswith("main.")} == {
        ("main", "main.start"),
        ("main", "main.start_again"),
        ("main.start", "main.work"),
    }


def test_multi_module_snippet_names_modules_by_path(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    from pkg.mod import func
                    func()
                """,
                "pkg/__init__.py": """
                    def setup():
                        pass

                    setup()
                """,
                "pkg/mod.py": """
                    def helper():
                        pass

                    def func():
                        helper()

                    helper()
                """,
            },
        )
    )
    assert result.error is None
    assert result.modules == {"main", "pkg", "pkg.mod"}
    assert result.edges == {
        ("pkg", "pkg.setup"),
        ("pkg.mod", "pkg.mod.helper"),
        ("main", "pkg.mod.func"),
        ("pkg.mod.func", "pkg.mod.helper"),
    }


def test_eval_calls_belong_to_the_scope_that_runs_eval(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                eval("func() or len([])")
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.eval"),
        ("main", "main.func"),
        ("main", "<builtin>.len"),
    }


def test_lazily_evaluated_type_scopes_are_not_nodes(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    def make():
                        return int

                    type Handler = make()
                    type Pair[T: make()] = tuple[T, T]

                    def handle[U: int = make()](value: U) -> U:
                        return value

                    def define():
                        type Local = make()
                        return Local

                    handle(1)
                    Handler.__value__
                    define().__value__
                """
            },
        )
    )
    assert result.error is None, result.error
    assert result.functions == {"main.make", "main.handle", "main.define"}
    assert result.edges == {
        ("main", "main.handle"),
        ("main", "main.make"),
        ("main", "main.define"),
        ("main.define", "main.make"),  # the scope that defines the alias
    }


def test_failing_assert_does_not_call_assertion_error(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def is_empty():
                    return False

                def describe():
                    return "message"

                def assert_():
                    assert is_empty(), describe()

                def explicit():
                    raise AssertionError(describe())

                def in_message():  # the message is a call expression
                    assert is_empty(), AssertionError(describe())

                for func in (assert_, explicit, in_message):
                    try:
                        func()
                    except AssertionError:
                        pass
            """
        },
    )
    assert edges == {
        ("main", "main.assert_"),
        ("main", "main.explicit"),
        ("main.assert_", "main.is_empty"),
        ("main.assert_", "main.describe"),
        ("main.explicit", "main.describe"),
        ("main.explicit", "<builtin>.AssertionError"),
        ("main", "main.in_message"),
        ("main.in_message", "main.is_empty"),
        ("main.in_message", "main.describe"),
        ("main.in_message", "<builtin>.AssertionError"),
    }


def test_library_internals_are_not_recorded(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import json
                json.dumps([1])
            """
        },
    )
    assert edges == {("main", "json.dumps")}


def test_library_closure_is_named_by_its_definition_site(tmp_path):
    # functools.wraps copies __module__ and __qualname__ of the snippet
    # function to the wrapper; the code object keeps where it is defined.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import functools

                @functools.singledispatch
                def describe(value):
                    pass

                describe(1)
            """
        },
    )
    assert edges == {
        ("main", "functools.singledispatch"),
        ("main", "functools.singledispatch.wrapper"),
        ("main", "main.describe"),
    }


def test_callees_outside_the_snippet_match_any_name_that_resolves_to_them(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                import collections
                import contextlib
                import fractions
                import operator
                import os
                import random
                import threading

                class Error(Exception):
                    pass

                class Worker(threading.Thread):
                    pass

                " ".join(["a"])
                {"a": 1}.items()
                dict.fromkeys(["a"])
                os.path.join("a", "b")
                random.random()  # a builtin method bound to a hidden instance
                random.shuffle([1, 2])  # a Python method bound to that instance
                fractions.Fraction.from_float(0.5)  # a Python classmethod
                Error()
                worker = Worker()
                worker.start()
                worker.join()
                # Defined elsewhere, named by the path that the snippet uses.
                collections.UserDict().update({"a": 1})
                stack = contextlib.ExitStack()
                stack.callback(len, [])
                stack.close()
                operator.add(1, 2)
            """
        },
        graph={
            "main": [
                "<builtin>.str.join",
                "<builtin>.dict.items",
                "<builtin>.dict.fromkeys",
                "os.path.join",
                "random.random",
                "random.shuffle",
                "fractions.Fraction.from_float",
                "<builtin>.Exception.__init__",
                "threading.Thread.__init__",
                "threading.Thread.start",
                "threading.Thread.join",
                "collections.UserDict",
                "collections.UserDict.update",
                "contextlib.ExitStack",
                "contextlib.ExitStack.callback",
                "contextlib.ExitStack.close",
                "operator.add",
            ],
            "<builtin>.str.join": [],
            "<builtin>.dict.items": [],
            "<builtin>.dict.fromkeys": [],
            "os.path.join": [],
            "random.random": [],
            "random.shuffle": [],
            "fractions.Fraction.from_float": [],
            "<builtin>.Exception.__init__": [],
            "threading.Thread.__init__": [],
            "threading.Thread.start": [],
            "threading.Thread.join": [],
            "collections.UserDict": [],
            "collections.UserDict.update": [],
            "contextlib.ExitStack": [],
            "contextlib.ExitStack.callback": [],
            "contextlib.ExitStack.close": [],
            "operator.add": [],
        },
    )
    assert validate.validate(case) == []


def test_unmatched_outside_callee_is_shown_under_its_defining_name(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import os\nos.path.join('a', 'b')\n"},
        graph={"main": []},
    )
    assert validate.validate(case) == [
        "missing edge: main -> posixpath.join",
        "missing node: posixpath.join",
    ]


def test_two_names_for_one_callee_match_only_once(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import os\nos.path.join('a', 'b')\n"},
        graph={
            "main": ["os.path.join", "posixpath.join"],
            "os.path.join": [],
            "posixpath.join": [],
        },
    )
    assert validate.validate(case) == ["unobserved edge: main -> posixpath.join"]


def test_resolving_expected_names_imports_nothing(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": "import os\nos.path.join('a', 'b')\n",
            "marker.py": "open('imported', 'w').close()\ndef func():\n    pass\n",
        },
        # marker.func sorts first, so it is resolved while matching os.path.join.
        graph={
            "main": ["marker.func", "os.path.join"],
            "marker.func": [],
            "os.path.join": [],
        },
    )
    assert validate.validate(case) == ["unobserved edge: main -> marker.func"]
    assert not (case / "imported").exists()


def test_bare_raise_of_a_class_calls_its_inherited_init(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Error(Exception):
                    pass

                class Outer:
                    class Inner(Exception):
                        pass

                def raise_class():
                    raise Error

                def raise_attribute():
                    raise Outer.Inner from None

                def raise_instance(error):
                    raise error

                calls = [
                    (raise_class, ()),
                    (raise_attribute, ()),
                    (raise_instance, (Error(),)),
                ]
                for func, arg in calls:
                    try:
                        func(*arg)
                    except Exception:
                        pass
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.Exception.__init__"),
        ("main", "main.raise_class"),
        ("main", "main.raise_attribute"),
        ("main", "main.raise_instance"),
        ("main.raise_class", "<builtin>.Exception.__init__"),
        ("main.raise_attribute", "<builtin>.Exception.__init__"),
    }


def test_missing_external_module_is_stubbed_and_named_by_dotted_path(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    from ext import Cls, parent
                    import ext.sub as sub

                    class Child(parent):
                        def run(self):
                            self.parent_fn()

                    class Own(parent):
                        def __init__(self):
                            super().__init__()

                    Cls().fun()
                    Child().run()
                    Own()
                    sub.function()
                """
            },
        )
    )
    assert result.error is None
    assert result.stubbed == {"ext", "ext.sub"}
    assert result.edges == {
        ("main", "ext.Cls"),
        ("main", "ext.Cls.fun"),
        ("main", "ext.parent.__init__"),
        ("main", "main.Child.run"),
        ("main.Child.run", "ext.parent.parent_fn"),
        ("main", "main.Own.__init__"),
        ("main.Own.__init__", "<builtin>.super"),
        ("main.Own.__init__", "ext.parent.__init__"),
        ("main", "ext.sub.function"),
    }


def test_stub_works_in_with_for_raise_except_and_super(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import ext

                def work():
                    pass

                def recover():
                    pass

                def never():
                    pass

                def fail():
                    raise ext.Failure  # not a call expression

                class Repository(ext.Model):
                    def save(self):
                        super().save().commit()

                    def load(self):
                        pass

                with ext.lock() as lock:
                    work()
                with ext.guard:
                    pass
                for name in ext.names():
                    never()  # a stub iterates over nothing
                for name in ext.registry:
                    never()
                if list(ext.names()) != []:
                    raise SystemExit("a stub gave items")
                converted = list(map(ext.convert, [1]))  # builtin code calls it
                try:
                    raise ext.Error("failed")
                except ext.Error:
                    recover()
                try:
                    fail()
                except ext.Failure:
                    pass
                Repository().save()
            """
        },
    )
    assert edges == {
        ("main", "ext.lock"),
        ("main", "main.work"),
        ("main", "ext.names"),
        ("main", "<builtin>.list"),
        ("main", "<builtin>.map"),
        ("main", "ext.Error"),
        ("main", "main.recover"),
        ("main", "main.fail"),
        ("main", "ext.Model.__init__"),
        ("main", "main.Repository.save"),
        ("main.Repository.save", "<builtin>.super"),
        ("main.Repository.save", "ext.Model.save"),
        ("main.Repository.save", "ext.Model.save.commit"),
    }


def test_subclass_of_a_stub_reaches_it_through_super_and_leaves_it_unchanged(
    tmp_path,
):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import ext

                class Repo(ext.Base):
                    def save(self):
                        super().save()

                    @classmethod
                    def load(cls):
                        return super().load()

                class Cached(Repo):
                    def fetch(self):
                        return super().fetch()

                class Tagged(ext.Base, tag="a"):  # a keyword for the real base
                    pass

                assert "save" not in vars(ext.Base)
                ext.Base.save()
                ext.Base().save()
                Repo().save()
                Repo.load()
                Cached().fetch()
                Tagged()
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.classmethod"),
        ("main", "<builtin>.vars"),
        ("main", "ext.Base.save"),
        ("main", "ext.Base"),
        ("main", "ext.Base.__init__"),
        ("main", "main.Repo.save"),
        ("main.Repo.save", "<builtin>.super"),
        ("main.Repo.save", "ext.Base.save"),
        ("main", "main.Repo.load"),
        ("main.Repo.load", "<builtin>.super"),
        ("main.Repo.load", "ext.Base.load"),
        ("main", "main.Cached.fetch"),
        ("main.Cached.fetch", "<builtin>.super"),
        ("main.Cached.fetch", "ext.Base.fetch"),
    }


def test_stub_subclasses_keep_cooperative_method_resolution(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import ext

                def work():
                    pass

                class A(ext.Base):
                    def f(self):
                        super().f()

                class B(ext.Base):
                    def f(self):
                        work()

                class C(A, B):
                    pass

                C().f()  # A.f, then B.f through super(), as for a real base
                try:
                    class Twice(ext.Base, ext.Base):
                        pass
                except TypeError:  # duplicate base class
                    pass
                else:
                    raise SystemExit("a duplicate stub base was accepted")
            """
        },
    )
    assert edges == {
        ("main", "ext.Base.__init__"),
        ("main", "main.A.f"),
        ("main.A.f", "<builtin>.super"),
        ("main.A.f", "main.B.f"),
        ("main.B.f", "main.work"),
    }


def test_names_that_stub_subclasses_add_change_no_attribute(tmp_path):
    # Subclasses of one stub share the place where super() finds stub
    # attributes. A name that one subclass defines gives the stub there, as
    # attribute lookup on the stub does, and never hides what the stub's own
    # classes define (BaseException.args).
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import ext

                class A(ext.Base):
                    def only_in_a(self):
                        pass

                class B(ext.Base):
                    def args(self):
                        pass

                    def use(self):
                        return super().only_in_a

                if B().use() is not ext.Base.only_in_a:
                    raise SystemExit("super() gave another object than the stub")
                if A().only_in_a is ext.Base.only_in_a:
                    raise SystemExit("A's own method is hidden")
                if A("x").args != ("x",):
                    raise SystemExit("B's name hides BaseException.args for A")
            """
        },
    )
    assert edges == {
        ("main", "ext.Base.__init__"),
        ("main", "main.B.use"),
        ("main.B.use", "<builtin>.super"),
    }


def test_stub_subclass_class_hooks_see_the_stub_through_super(tmp_path):
    # __init_subclass__ runs while type.__new__ creates the class, so the
    # names must be in place before that.
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import ext

                class Base(ext.Base):
                    def __init_subclass__(cls):
                        super().__init_subclass__()
                        cls().run()

                class Child(Base):
                    def run(self):
                        super().run()
            """
        },
    )
    assert edges == {
        ("main", "main.Base.__init_subclass__"),
        ("main.Base.__init_subclass__", "<builtin>.super"),
        ("main.Base.__init_subclass__", "ext.Base.__init_subclass__"),
        ("main.Base.__init_subclass__", "ext.Base.__init__"),
        ("main.Base.__init_subclass__", "main.Child.run"),
        ("main.Child.run", "<builtin>.super"),
        ("main.Child.run", "ext.Base.run"),
    }


def test_missing_submodule_of_a_real_package_is_an_error(tmp_path):
    result = validate.trace(
        make_case(tmp_path, {"main.py": "import pkg.missing\n", "pkg/__init__.py": ""})
    )
    assert result.error is not None
    assert "ModuleNotFoundError" in result.error


def test_snippet_that_raises_reports_error_and_keeps_earlier_edges(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                func()
                raise ValueError("boom")
            """
        },
        graph={
            "main": ["main.func", "<builtin>.ValueError"],
            "main.func": [],
            "<builtin>.ValueError": [],
        },
    )
    result = validate.trace(case)
    assert result.edges == {("main", "main.func"), ("main", "<builtin>.ValueError")}
    assert result.error == "ValueError: boom (main.py:6)"
    assert validate.validate(case) == [
        "snippet did not finish: ValueError: boom (main.py:6)"
    ]


def test_snippet_output_and_clean_exit_do_not_matter(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import sys\nprint('noise')\nsys.exit(0)\n"},
        graph={
            "main": ["<builtin>.print", "sys.exit"],
            "<builtin>.print": [],
            "sys.exit": [],
        },
    )
    assert validate.validate(case) == []


def test_snippet_module_named_like_a_loaded_module_is_an_error(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path, {"main.py": "import json\n", "json.py": "def f():\n    pass\n"}
        )
    )
    assert result.error == "snippet modules have the names of loaded modules: json"


def test_binary_output_does_not_break_the_run(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import sys\nsys.stdout.buffer.write(b'\\xff')\n"},
        graph={"main": ["_io.BufferedWriter.write"]},
    )
    result = validate.trace(case)
    assert result.error is None


def test_nonzero_exit_after_the_trace_is_written_is_an_error(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path, {"main.py": "import atexit, os\natexit.register(os._exit, 5)\n"}
        )
    )
    assert result.error == "exit status 5"


def test_snippet_that_hangs_times_out(tmp_path):
    result = validate.trace(
        make_case(tmp_path, {"main.py": "while True:\n    pass\n"}), timeout=2
    )
    assert result.error == "timed out after 2s"


def test_correct_ground_truth_has_no_problems(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                def unused():
                    pass

                func()
            """
        },
        graph={"main": ["main.func"], "main.func": [], "main.unused": []},
    )
    assert validate.validate(case) == []


def test_ground_truth_missing_an_edge_and_a_node_is_reported(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                func()
                len([])
            """
        },
        graph={"main": ["main.func"], "main.func": []},
    )
    assert validate.validate(case) == [
        "missing edge: main -> <builtin>.len",
        "missing node: <builtin>.len",
    ]


def test_ground_truth_with_an_extra_edge_and_node_is_reported(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                def other():
                    pass

                func()
            """
        },
        graph={
            "main": ["main.func", "main.other"],
            "main.func": [],
            "main.other": [],
            "main.ghost": [],
        },
    )
    assert validate.validate(case) == [
        "unobserved edge: main -> main.other",
        "unexpected node: main.ghost",
    ]


def test_case_without_ground_truth_or_with_bad_ground_truth(tmp_path):
    case = make_case(tmp_path, {"main.py": "pass\n"})
    assert validate.validate(case) == ["callgraph.json not found"]
    (case / "callgraph.json").write_text('{"main": "not a list"}')
    [problem] = validate.validate(case)
    assert problem.startswith("bad callgraph.json:")


def test_command_line_reports_failures_with_exit_status(tmp_path, capsys):
    good = make_case(tmp_path / "good", {"main.py": "pass\n"}, graph={"main": []})
    bad = make_case(tmp_path / "bad", {"main.py": "len([])\n"}, graph={"main": []})
    assert validate.main([str(good)]) == 0
    assert validate.main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "missing edge: main -> <builtin>.len" in out


def test_case_that_needs_a_newer_python_is_skipped(tmp_path, capsys):
    current = make_case(
        tmp_path / "current",
        {"main.py": "pass\n", "requires-python": "3.14\n"},
        graph={"main": []},
    )
    newer = make_case(
        tmp_path / "newer",
        {"main.py": "syntax of the future\n", "requires-python": "99.1\n"},
        graph={"main": []},
    )
    assert validate.main([str(current), str(newer)]) == 0
    out = capsys.readouterr().out
    assert f"{current}: ok" in out
    assert f"{newer}: skipped (needs Python 99.1)" in out
    assert "2 cases, 0 failed, 1 skipped" in out


def test_whole_benchmark_matches_its_ground_truth(capsys):
    status = validate.main([])
    assert status == 0, capsys.readouterr().out
