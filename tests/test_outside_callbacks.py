from programs import callees, main_graph


def test_builtins_call_back_parameters_typed_as_callables(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import functools
        import threading
        def key(x): pass
        def double(x): pass
        def keep(x): pass
        def add(a, b): pass
        def work(): pass
        def use():
            sorted([3, 1], key=key)
            map(double, [1, 2])
            filter(keep, [1])
            functools.reduce(add, [1, 2])
            threading.Thread(target=work)
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.filter",
        "<builtin>.map",
        "<builtin>.sorted",
        "functools.reduce",
        "main.double",
        "main.keep",
        "main.key",
        "threading.Thread",
    ]


def test_parameters_that_are_not_callables_are_not_called_back(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import copy
        import inspect
        import typing
        class C:
            def __call__(self): pass
        def f(): pass
        def use():
            isinstance(f, C)
            callable(C())
            inspect.isclass(f)
            copy.copy(f)
            sorted([f, C()])
            "".join([f])
            print(f)
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.callable",
        "<builtin>.isinstance",
        "<builtin>.print",
        "<builtin>.sorted",
        "<builtin>.str.join",
        "copy.copy",
        "inspect.isclass",
    ]


def test_an_overload_that_takes_any_object_does_not_call_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        def f(): pass
        inspect.iscoroutinefunction(f)
        """,
    )

    assert callees(graph, "main") == ["inspect.iscoroutinefunction"]


def test_a_callable_that_the_function_returns_is_not_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        import typing
        @typing.overload
        def f(x: int) -> int: ...
        def f(x): pass
        class C:
            @abc.abstractmethod
            def m(self): pass
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod", "typing.overload"]


def test_methods_of_outside_values_call_nothing_back(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import asyncio
        import concurrent.futures
        def tick(): pass
        def job(): pass
        def done(future): pass
        async def start():
            loop = asyncio.get_running_loop()
            loop.call_soon(tick)
            # The loop's class is not known: no edge, but a typed result.
            loop.time().is_integer()
            executor = concurrent.futures.ThreadPoolExecutor()
            future = executor.submit(job)
            future.add_done_callback(done)
            future.result()
        """,
    )

    assert callees(graph, "main.start") == [
        "<builtin>.float.is_integer",
        "asyncio.get_running_loop",
        "concurrent.futures.Future.add_done_callback",
        "concurrent.futures.Future.result",
        "concurrent.futures.ThreadPoolExecutor",
        "concurrent.futures.ThreadPoolExecutor.submit",
    ]


def test_re_sub_and_subn_call_a_callable_replacement(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        def repl(m): pass
        def by_keyword(m): pass
        def by_pattern(m): pass
        def counted(m): pass
        def counted_by_pattern(m): pass
        def chosen(m): pass
        def on_bytes(m): pass
        class Replacer:
            def method(self, m): pass
        replacer = Replacer()
        def use(flag):
            re.sub("a", repl, "abc")
            re.sub("a", lambda m: m, "abc")
            re.sub("a", replacer.method, "abc")
            re.sub("a", repl=by_keyword, string="abc")
            re.compile("a").sub(by_pattern, "abc")
            re.subn("a", counted, "abc")
            re.compile("a").subn(counted_by_pattern, "abc")
            replacement = "x" if flag else chosen
            re.sub("a", replacement, "abc")
            re.sub(b"a", on_bytes, b"abc")
        use(True)
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Replacer.method",
        "main.by_keyword",
        "main.by_pattern",
        "main.chosen",
        "main.counted",
        "main.counted_by_pattern",
        "main.on_bytes",
        "main.repl",
        "main.use.<lambda1>",
        "re.Pattern.sub",
        "re.Pattern.subn",
        "re.compile",
        "re.sub",
        "re.subn",
    ]


def test_re_sub_calls_no_replacement_that_is_not_callable(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import functools
        import re
        def repl(m): pass
        def text():
            re.sub("a", "b", "abc")
            re.sub("a", r"\\1", "abc", count=1)
        def partial():
            re.sub("a", functools.partial(repl), "abc")
        def control():
            re.sub("a", repl, "abc")
        text()
        partial()
        control()
        """,
    )

    assert callees(graph, "main.control") == ["main.repl", "re.sub"]
    assert callees(graph, "main.text") == ["re.sub"]
    assert callees(graph, "main.partial") == ["functools.partial", "re.sub"]


def test_limit_the_replacement_gets_no_match_object(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        def repl(m):
            return m.group(0)
        re.sub("a", repl, "abc")
        """,
    )

    assert callees(graph, "main") == ["main.repl", "re.sub"]
    assert callees(graph, "main.repl") == []


def test_keyword_and_unpacked_arguments_bind_to_their_parameters(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def key(x): pass
        def other(): pass
        options = {"key": key}
        sorted([1], **options)
        sorted(*[[other]])
        """,
    )

    assert callees(graph, "main") == ["<builtin>.sorted", "main.key"]


def test_builtins_call_the_special_methods_of_their_protocol_parameters(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Number:
            def __abs__(self): pass
            def __round__(self, ndigits=None): pass
            def other(self): pass
        def use():
            abs(Number())
            round(Number())
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.abs",
        "<builtin>.round",
        "main.Number.__abs__",
        "main.Number.__round__",
    ]


def test_library_code_calls_no_method_of_the_analysed_objects_it_gets(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import contextlib
        import heapq
        import logging
        import math
        import threading
        class Worker(threading.Thread):
            def run(self): pass
        class Resource:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Item:
            def __lt__(self, other): pass
            def __trunc__(self): return 0
        class Handler(logging.Handler):
            def emit(self, record): pass
        def use():
            Worker().start()
            with contextlib.ExitStack() as stack:
                stack.enter_context(Resource())
            heapq.heappush([], Item())
            math.trunc(Item())
            logging.getLogger("x").addHandler(Handler())
        """,
    )

    assert [c for c in callees(graph, "main.use") if c.startswith("main.")] == []


def test_a_builtin_calls_the_first_protocol_that_the_class_implements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Deck:
    def __reversed__(self):
        return iter([])
    def __len__(self):
        return 0
class Row:
    def __len__(self):
        return 1
    def __getitem__(self, index):
        return index
reversed(Deck())
reversed(Row())
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.reversed",
        "main.Deck.__reversed__",
        "main.Row.__getitem__",
        "main.Row.__len__",
    ]


def test_reversed_calls_nothing_of_a_class_without_both_len_and_getitem(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import collections.abc
class OnlyItems:
    def __getitem__(self, index):
        return index
class OnlyLength:
    def __len__(self):
        return 1
class ItemsMeta(type):
    def __getitem__(cls, index):
        return index
class Keyed(metaclass=ItemsMeta): pass
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        return index
    def __len__(self):
        return 1
reversed(OnlyItems())
reversed(OnlyLength())
reversed(Keyed)
reversed(View())
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.reversed",
        "main.View.__getitem__",
        "main.View.__len__",
    ]


def test_reversed_of_a_class_calls_its_metaclass(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Backwards(type):
    def __reversed__(cls):
        return iter([])
class Sequence(type):
    def __len__(cls):
        return 1
    def __getitem__(cls, index):
        return index
class Deck(metaclass=Backwards): pass
class Row(metaclass=Sequence): pass
reversed(Deck)
reversed(Row)
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.reversed",
        "main.Backwards.__reversed__",
        "main.Sequence.__getitem__",
        "main.Sequence.__len__",
    ]


def test_sorted_min_and_max_compare_the_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Score:
    def __lt__(self, other): return True
    def __gt__(self, other): return True
    def __le__(self, other): return True
class Low:
    def __lt__(self, other): return True
class High:
    def __gt__(self, other): return True
def by_sorted():
    sorted([Score()])
def by_max():
    max([Score()])
def by_min(a, b):
    min(a, b)
def by_reflection():
    sorted([High()])
by_sorted()
by_max()
by_min(Low(), Low())
by_reflection()
""",
    )

    assert callees(graph, "main.by_sorted") == ["<builtin>.sorted", "main.Score.__lt__"]
    assert callees(graph, "main.by_max") == ["<builtin>.max", "main.Score.__gt__"]
    assert callees(graph, "main.by_min") == ["<builtin>.min", "main.Low.__lt__"]
    assert callees(graph, "main.by_reflection") == [
        "<builtin>.sorted",
        "main.High.__gt__",
    ]


def test_a_key_is_called_on_the_items_and_its_results_are_compared(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Key:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
class Item:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
    def rank(self): return Key()
def key(item):
    return item.rank()
def by_sorted(items):
    sorted(items, key=key)
def by_min(a, b):
    min(a, b, key=key)
def by_max(items):
    max(items, key=key, default=None)
def by_sort(items):
    items.sort(key=key)
by_sorted([Item(), Item()])
by_min(Item(), Item())
by_max([Item(), Item()])
by_sort([Item(), Item()])
""",
    )

    assert callees(graph, "main.key") == ["main.Item.rank"]
    assert callees(graph, "main.by_sorted") == [
        "<builtin>.sorted",
        "main.Key.__lt__",
        "main.key",
    ]
    assert callees(graph, "main.by_min") == [
        "<builtin>.min",
        "main.Key.__lt__",
        "main.key",
    ]
    assert callees(graph, "main.by_max") == [
        "<builtin>.max",
        "main.Key.__gt__",
        "main.key",
    ]
    assert callees(graph, "main.by_sort") == [
        "<builtin>.list.sort",
        "main.Key.__lt__",
        "main.key",
    ]


def test_the_items_are_found_through_the_bound_parameters(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Item:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
class Fallback:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
def key(item): return item
def unpacked(items):
    sorted(*[items])
def arguments(a, b, c):
    max(*[a, b], c)
def with_default(items):
    max(items, default=Fallback())
def sort(items):
    items.sort()
def options(items, **kwargs):
    sorted(items, **kwargs)
unpacked([Item(), Item()])
arguments(Item(), Item(), Item())
with_default([Item(), Item()])
sort([Item(), Item()])
options([Item()])
options([Item()], key=key)
""",
    )

    assert callees(graph, "main.unpacked") == ["<builtin>.sorted", "main.Item.__lt__"]
    assert callees(graph, "main.arguments") == ["<builtin>.max", "main.Item.__gt__"]
    assert callees(graph, "main.with_default") == [
        "<builtin>.max",
        "main.Item.__gt__",
    ]
    assert callees(graph, "main.sort") == ["<builtin>.list.sort", "main.Item.__lt__"]
    assert callees(graph, "main.options") == [
        "<builtin>.sorted",
        "main.Item.__lt__",
        "main.key",
    ]


def test_classes_are_compared_by_their_metaclass(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Meta(type):
    def __lt__(cls, other): return False
class A(metaclass=Meta): pass
class B(metaclass=Meta): pass
def key(x): return A
def by_items():
    sorted([A, B])
def by_key():
    min([1, 2], key=key)
by_items()
by_key()
""",
    )

    assert callees(graph, "main.by_items") == ["<builtin>.sorted", "main.Meta.__lt__"]
    assert callees(graph, "main.by_key") == [
        "<builtin>.min",
        "main.Meta.__lt__",
        "main.key",
    ]


def test_a_type_variable_bound_through_variadic_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def a(): pass
def b(): pass
def c(): pass
max(a, b, c, key=lambda f: f.__name__)()
""",
    )

    assert {"main.a", "main.b", "main.c"} <= set(callees(graph, "main"))


def test_only_the_unpacked_value_of_a_callable_parameter_is_called_back(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def key(x):
    return x
def fallback(): pass
max([1], **{"key": key, "default": fallback})
""",
    )

    assert callees(graph, "main") == ["<builtin>.max", "main.key"]


def test_a_static_special_method_is_called_by_a_builtin(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Empty:
    @staticmethod
    def __len__():
        return 0
len(Empty())
""",
    )

    assert "main.Empty.__len__" in callees(graph, "main")


def test_int_calls_the_first_conversion_that_the_class_defines(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Number:
    def __int__(self): return 1
    def __index__(self): return 2
class Index:
    def __index__(self): return 2
int(Number())
int(Index())
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.int",
        "main.Index.__index__",
        "main.Number.__int__",
    ]


def test_a_builtin_calls_the_plain_methods_of_a_protocol_parameter(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Log:
    def write(self, text): pass
    def flush(self): pass
    def report(self):
        print("x", file=self)
class Table:
    def keys(self): return ["a"]
    def __getitem__(self, key): return 1
    def __iter__(self): return iter([])
Log().report()
frozendict(Table())
""",
    )

    assert callees(graph, "main.Log.report") == ["<builtin>.print", "main.Log.write"]
    assert {"main.Table.keys", "main.Table.__getitem__"} <= set(callees(graph, "main"))
    assert "main.Table.__iter__" not in callees(graph, "main")


def test_one_site_that_binds_two_receivers_calls_its_callback_back(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class First(classmethod): pass
        class Second(classmethod): pass
        def f(cls): pass
        for kind in (First, Second):
            kind(f)
        """,
    )

    assert callees(graph, "main") == ["<builtin>.classmethod.__init__", "main.f"]
