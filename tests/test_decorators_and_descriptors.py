import programs
import pytest
from programs import call_graph, callees, main_graph


def test_decorated_name_is_bound_to_the_result_of_the_decorator(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def trace(f):
            def wrapper():
                return f()
            return wrapper
        @trace
        def g(): pass
        g()
        """,
    )

    assert callees(graph, "main") == ["main.trace", "main.trace.wrapper"]
    assert callees(graph, "main.trace.wrapper") == ["main.g"]


def test_decorated_name_is_not_also_bound_to_the_undecorated_function(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def other(): pass
        def replace(f):
            return other
        @replace
        def g(): pass
        g()
        """,
    )

    assert callees(graph, "main") == ["main.other", "main.replace"]


def test_decorators_apply_bottom_up(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def outer(f):
            def outer_wrapper():
                f()
            return outer_wrapper
        def inner(f):
            def inner_wrapper():
                f()
            return inner_wrapper
        @outer
        @inner
        def g(): pass
        g()
        """,
    )

    assert callees(graph, "main") == [
        "main.inner",
        "main.outer",
        "main.outer.outer_wrapper",
    ]
    assert callees(graph, "main.outer.outer_wrapper") == ["main.inner.inner_wrapper"]
    assert callees(graph, "main.inner.inner_wrapper") == ["main.g"]


def test_decorator_applications_belong_to_the_enclosing_function(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def keep(f):
            return f
        def make():
            class C:
                @keep
                def m(self): pass
            @keep
            def local(): pass
            return C
        make()
        """,
    )

    assert callees(graph, "main") == ["main.make"]
    assert callees(graph, "main.make") == ["main.keep"]


def test_decorator_expression_with_a_call(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def route(path):
            def register(f):
                return f
            return register
        @route("/")
        def index(): pass
        index()
        """,
    )

    assert callees(graph, "main") == [
        "main.index",
        "main.route",
        "main.route.register",
    ]


def test_class_decorator(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def register(cls):
            cls.extra = helper
            return cls
        def helper(self): pass
        @register
        class C:
            def __init__(self): pass
        C().extra()
        """,
    )

    assert callees(graph, "main") == [
        "main.C.__init__",
        "main.helper",
        "main.register",
    ]


def test_name_decorated_by_an_external_also_keeps_the_definition(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        @ext.task
        def job(): pass
        @ext.final
        class Model:
            def run(self): pass
        def use():
            job.delay()
            job()
            Model().run()
        """,
    )

    assert callees(graph, "main") == ["ext.final", "ext.task"]
    assert callees(graph, "main.use") == ["main.Model.run", "main.job"]


def test_decorator_that_returns_itself_terminates(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def same(f):
            return f
        @same
        def same(f):
            return f
        same(same)(same)
        """,
    )

    assert callees(graph, "main") == ["main.same"]


def test_static_method_is_not_bound(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            @staticmethod
            def s(callback):
                callback()
            def m(self):
                self.s(g)
        def g(): pass
        C().s(g)
        C.s(g)
        """,
    )

    assert callees(graph, "main") == ["<builtin>.staticmethod", "main.C.s"]
    assert callees(graph, "main.C.s") == ["main.g"]
    assert callees(graph, "main.C.m") == ["main.C.s"]


def test_static_method_created_by_a_call(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def helper(callback):
            callback()
        def g(): pass
        class C:
            run = staticmethod(helper)
        C().run(g)
        """,
    )

    assert callees(graph, "main.helper") == ["main.g"]


def test_static_method_object_is_callable(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        run = staticmethod(g)
        run()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.staticmethod", "main.g"]


def test_static_method_stored_on_another_class_binds_there(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            @staticmethod
            def s(obj):
                obj.run()
        class B:
            s = A.s
            def run(self): pass
        B().s()
        """,
    )

    assert callees(graph, "main.A.s") == ["main.B.run"]


def test_class_method_binds_the_class_it_is_loaded_through(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            @classmethod
            def create(cls):
                return cls()
        class Child(Base):
            def __init__(self): pass
            def run(self): pass
        Child.create().run()
        Child().create().run()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "main.Base.create",
        "main.Child.__init__",
        "main.Child.run",
    ]
    assert callees(graph, "main.Base.create") == ["main.Child.__init__"]


def test_class_method_of_a_library_class_receives_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Config:
            @classmethod
            def load(cls):
                return cls.defaults()
            @classmethod
            def defaults(cls): pass
        """,
    )

    assert callees(graph, "main.Config.load") == ["main.Config.defaults"]


def test_a_module_name_for_a_stub_class_method_binds_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import tarfile
        def through_module(path):
            tarfile.open(path).close()
        def through_class(path):
            tarfile.TarFile.open(path).close()
        through_module("a.tar")
        through_class("a.tar")
        """,
    )

    assert callees(graph, "main.through_module") == [
        "tarfile.TarFile.close",
        "tarfile.open",
    ]
    assert callees(graph, "main.through_class") == [
        "tarfile.TarFile.close",
        "tarfile.TarFile.open",
    ]


def test_property_read_on_an_instance_calls_the_getter(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        class C:
            @property
            def handler(self):
                return g
        def use(c):
            c.handler()
        use(C())
        """,
    )

    assert callees(graph, "main") == ["<builtin>.property", "main.use"]
    assert callees(graph, "main.use") == ["main.C.handler", "main.g"]


def test_property_setter_and_getter_from_the_decorator_chain(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def h(): pass
        class C:
            @property
            def value(self):
                return self._value
            @value.setter
            def value(self, new):
                new()
                self._value = h
        c = C()
        c.value = g
        c.value()
        """,
    )

    assert "main.h" in callees(graph, "main")
    assert callees(graph, "main.C.value") == ["main.g"]


def test_property_accessor_methods_keep_the_other_accessors(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        class C:
            def get(self):
                return g
            def put(self, value): pass
            def replace(self, value): pass
            plain = property(get, put)
            replaced = plain.setter(replace)
        c = C()
        c.replaced()
        c.replaced = None
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.property",
        "<builtin>.property.setter",
        "main.C.get",
        "main.C.put",
        "main.C.replace",
        "main.g",
    ]


def test_property_getter_and_deleter_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def h(): pass
        class C:
            def __init__(self):
                self.handler = h
            def get(self): pass
            def other(self):
                return g
            def remove(self):
                self.handler()
            plain = property(get)
            regot = plain.getter(other)
            removable = plain.deleter(remove)
        c = C()
        c.regot()
        del c.removable
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.property",
        "<builtin>.property.deleter",
        "<builtin>.property.getter",
        "main.C.__init__",
        "main.C.get",
        "main.C.other",
        "main.C.remove",
        "main.g",
    ]
    assert callees(graph, "main.C.remove") == ["main.h"]


def test_property_created_by_a_call(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        class C:
            def get(self):
                return g
            def put(self, value): pass
            item = property(get, put)
        c = C()
        c.item()
        c.item = g
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.property",
        "main.C.get",
        "main.C.put",
        "main.g",
    ]


def test_property_read_through_the_class_is_the_property(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            @property
            def value(self): pass
        def show(c):
            C.value.fget(c)
        """,
    )

    assert callees(graph, "main.show") == ["main.C.value"]


def test_class_method_called_through_an_instance_binds_its_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            @classmethod
            def make(cls):
                return cls()
        class Child(Base):
            def __init__(self): pass
        def via_instance(obj):
            return obj.make()
        via_instance(Child())
        """,
    )

    assert callees(graph, "main.Base.make") == ["main.Child.__init__"]


WRAPS_PROGRAM = """
import functools
def deco(f):
    @functools.wraps(f)
    def wrapper(*args):
        return f(*args)
    return wrapper
@deco
def g(): pass
@deco
def h(): pass
def use():
    g()
"""


@pytest.mark.parametrize("analysed", [False, True])
def test_functools_wraps_returns_the_wrapper(tmp_path, analysed):
    files = {"main.py": WRAPS_PROGRAM}
    if analysed:
        files["functools.py"] = """
        def wraps(wrapped):
            return lambda wrapper: wrapped
        """
    graph = call_graph(tmp_path, files)

    assert callees(graph, "main.use") == ["main.deco.wrapper"]
    assert callees(graph, "main.deco") == [
        "functools.partial.__call__",
        "functools.wraps",
    ]


@pytest.mark.parametrize(
    "decorator",
    [
        pytest.param(
            "class Decorator:\n    __call__ = staticmethod(ext.keep)\n"
            "deco = Decorator()\n",
            id="held as __call__ of an instance",
        ),
        pytest.param(
            "class Decorator:\n    apply = classmethod(ext.keep)\n"
            "deco = Decorator.apply\n",
            id="bound to a class by a class method",
        ),
    ],
)
def test_an_outside_decorator_reached_through_a_call_keeps_the_function(
    tmp_path, decorator
):
    graph = main_graph(
        tmp_path,
        "import ext\n"
        + decorator
        + "@deco\ndef target(): pass\ndef use():\n    target()\n",
    )

    assert "ext.keep" in callees(graph, "main")
    assert callees(graph, "main.use") == ["main.target"]


def test_an_analysed_library_callable_and_its_decorator_are_not_external(tmp_path):
    generator = programs.analysed(
        tmp_path,
        {
            "main.py": WRAPS_PROGRAM,
            "functools.py": "def wraps(wrapped):\n    return lambda w: wrapped\n",
        },
    )

    assert callees(generator.output(), "main.deco") == [
        "functools.partial.__call__",
        "functools.wraps",
    ]
    document = generator.document()
    assert document["definitions"]["functools.wraps"]["kind"] == "function"
    assert document["outside"] == {"functools.partial.__call__": {"known": "stub"}}


@pytest.mark.parametrize(
    "call, callee",
    [
        ("abc.abstractmethod(C())", "abc.abstractmethod"),
        ("dataclasses.dataclass(C())", "dataclasses.dataclass"),
        ("enum.unique(C())", "enum.unique"),
        ("functools.total_ordering(C())", "functools.total_ordering"),
        ("functools.update_wrapper(C(), g)", "functools.update_wrapper"),
        (
            "functools.update_wrapper(wrapped=g, wrapper=C())",
            "functools.update_wrapper",
        ),
        ("functools.wraps(g)(C())", ["functools.partial.__call__", "functools.wraps"]),
        ("typing.final(C())", "typing.final"),
        ("typing.no_type_check(C())", "typing.no_type_check"),
        ("typing.override(C())", "typing.override"),
        ("typing.runtime_checkable(C())", "typing.runtime_checkable"),
    ],
)
def test_each_library_callable_returns_an_instance_argument(tmp_path, call, callee):
    graph = main_graph(
        tmp_path,
        "import abc, dataclasses, enum, functools, typing\n"
        "class C:\n"
        "    def m(self): pass\n"
        "def g(): pass\n"
        f"{call}.m()\n",
    )

    callee = [callee] if isinstance(callee, str) else callee
    assert callees(graph, "main") == sorted([*callee, "main.C.m"])


def test_dataclass_returns_the_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import dataclasses
        from dataclasses import dataclass
        @dataclass
        class Point:
            def norm(self): pass
        @dataclasses.dataclass(frozen=True)
        class Line:
            def length(self): pass
        def use(p, q):
            Point().norm()
            Line().length()
        """,
    )

    assert callees(graph, "main.use") == ["main.Line.length", "main.Point.norm"]


CLOSURES_PROGRAM = """
import contextlib
import functools
from contextlib import asynccontextmanager, contextmanager

@contextmanager
def managed():
    yield

@asynccontextmanager
async def amanaged():
    yield

@functools.lru_cache(maxsize=32)
def square(n):
    return n * n

class C:
    @contextlib.contextmanager
    def cm(self):
        yield

    @functools.lru_cache(maxsize=None, typed=True)
    def m(self):
        pass

    def run(self):
        with self.cm():
            self.m()

def use():
    with managed():
        pass
    square(2)
    square.cache_clear()
    managed().__enter__()

async def ause():
    async with amanaged():
        pass
"""


def test_a_library_decorator_that_returns_a_closure_puts_it_on_the_call_path(
    tmp_path,
):
    graph = main_graph(tmp_path, CLOSURES_PROGRAM)

    assert callees(graph, "main.use") == [
        "contextlib._GeneratorContextManager.__enter__",
        "contextlib.contextmanager.helper",
        "functools._lru_cache_wrapper.__call__",
        "functools._lru_cache_wrapper.cache_clear",
        "main.managed",
        "main.square",
    ]
    assert callees(graph, "main.ause") == [
        "contextlib.asynccontextmanager.helper",
        "main.amanaged",
    ]
    assert callees(graph, "main.C.run") == [
        "contextlib.contextmanager.helper",
        "functools._lru_cache_wrapper.__call__",
        "main.C.cm",
        "main.C.m",
    ]
    assert "functools.lru_cache.decorating_function" in callees(graph, "main")


def test_limit_lru_cache_is_not_selected_by_the_class_of_its_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import functools
        @functools.lru_cache
        def bare(n): pass
        @functools.lru_cache(maxsize=32)
        def sized(n): pass
        def use():
            bare(1)
        """,
    )

    assert callees(graph, "main.use") == [
        "functools._lru_cache_wrapper.__call__",
        "functools.lru_cache.decorating_function",
        "main.bare",
    ]
    assert "functools._lru_cache_wrapper.__call__" in callees(graph, "main")


def test_limit_a_context_manager_is_made_where_it_is_called_and_yields_nothing(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        from contextlib import contextmanager
        def action(): pass
        @contextmanager
        def managed():
            yield action
        def make():
            return managed()
        def use():
            cm = make()
            with cm as value:
                value()
        """,
    )

    assert callees(graph, "main.make") == [
        "contextlib.contextmanager.helper",
        "main.managed",
    ]
    assert callees(graph, "main.use") == ["main.make"]


def test_limit_a_context_manager_of_a_class_method_object(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from contextlib import contextmanager
        class C:
            @contextmanager
            @classmethod
            def cm(cls):
                yield cls
        def use():
            C.cm().__enter__()
        """,
    )

    assert callees(graph, "main.use") == [
        "contextlib._GeneratorContextManager.__enter__",
        "contextlib.contextmanager.helper",
        "main.C.cm",
    ]


def test_limit_at_a_low_cap_the_closure_values_saturate_the_decorated_name(
    tmp_path,
):
    source = """
        from functools import lru_cache
        @lru_cache(maxsize=32)
        def f(): pass
        f()
        """
    low = programs.analysed(tmp_path / "low", {"main.py": source}, cap=2)
    full = programs.analysed(tmp_path / "full", {"main.py": source})

    assert "main.f" not in callees(low.output(), "main")
    assert "main.f" in callees(full.output(), "main")


def test_wrappers_that_wrap_themselves_terminate(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        f = staticmethod(f)
        f()
        def g(cls): pass
        g = classmethod(g)
        def h(self): return 1
        h = property(h)
        class C:
            m = g
            p = h
        C.m()
        C().p
        """,
    )

    assert "main.f" in callees(graph, "main")
    assert "main.g" in callees(graph, "main")
    assert "main.h" in callees(graph, "main")


def test_wrappers_rebound_through_the_class_terminate(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def f(cls): pass
            def g(): pass
            def h(self): pass
        C.f = classmethod(C.f)
        C.g = staticmethod(C.g)
        C.h = property(C.h)
        C.f()
        C.g()
        C().h
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "<builtin>.property",
        "<builtin>.staticmethod",
        "main.C.f",
        "main.C.g",
        "main.C.h",
    ]


CLASS_METHOD_OF = {
    "function": ("def wrapped(owner):\n    owner.target()\n", "wrapped"),
    "bound method": (
        "class Helper:\n    def run(self, owner):\n        owner.target()\n",
        "Helper().run",
    ),
    "callable instance": (
        "class Helper:\n    def __call__(self, owner):\n        owner.target()\n",
        "Helper()",
    ),
    "static method": (
        "def wrapped(owner):\n    owner.target()\n",
        "staticmethod(wrapped)",
    ),
    "class": (
        "class Maker:\n    def __init__(self, owner):\n        owner.target()\n",
        "Maker",
    ),
    "class method": (
        "class A:\n    @classmethod\n    def run(a, owner):\n        owner.target()\n",
        "A.run",
    ),
}


@pytest.mark.parametrize("kind", sorted(CLASS_METHOD_OF))
def test_a_class_method_binds_the_class_to_a_function_only(tmp_path, kind):
    definitions, wrapped = CLASS_METHOD_OF[kind]
    graph = main_graph(
        tmp_path,
        definitions
        + "class C:\n"
        + "    @staticmethod\n    def target(): pass\n"
        + f"    make = classmethod({wrapped})\n"
        + "C.make()\n",
    )

    targets = [caller for caller, called in graph.items() if "main.C.target" in called]
    assert (targets != []) == (kind == "function"), kind


def test_class_method_of_a_static_method_of_itself_terminates(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def f(*args): pass
        C.f = classmethod(staticmethod(C.f))
        C.f()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "<builtin>.staticmethod",
        "main.C.f",
    ]


def test_wrappers_rebound_through_an_instance_terminate(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def f(cls): pass
            def g(self): pass
            def h(self): pass
        c = C()
        C.f = classmethod(c.f)
        C.g = staticmethod(c.g)
        C.h = property(c.h)
        c.f()
        c.g()
        c.h
        """,
    )

    assert {"main.C.f", "main.C.g", "main.C.h"} <= set(callees(graph, "main"))


def test_modelled_builtins_bind_unpacked_and_keyword_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import functools
        def f(): pass
        def g(): pass
        def h(): pass
        def get(self):
            return h
        class C:
            def m(self): pass
            def __len__(self): return 0
            p = property(**{"fget": get})
            s = staticmethod(*[g])
        def use(c):
            len(*(c,))
            getattr(*(c, "m"))()
            c.p()
            C.s()
            functools.update_wrapper(wrapped=g, wrapper=f)()
        use(C())
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.getattr",
        "<builtin>.len",
        "functools.update_wrapper",
        "main.C.__len__",
        "main.C.m",
        "main.f",
        "main.g",
        "main.get",
        "main.h",
    ]


def test_accessors_that_are_bound_methods_or_callable_instances(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        def other(): pass
        class Getter:
            def get(self, obj):
                return obj.handler
        class Caller:
            def __call__(self, obj):
                return obj.spare
        class C:
            def __init__(self):
                self.handler = target
                self.spare = other
            value = property(Getter().get)
            called = property(Caller())
        def use():
            C().value()
            C().called()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.C.__init__",
        "main.Caller.__call__",
        "main.Getter.get",
        "main.other",
        "main.target",
    ]


def test_attribute_deletion_calls_the_deleter_and_delattr(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def remove(self): pass
            item = property(fdel=remove)
        class D:
            def __delattr__(self, name): pass
        def use(c, d):
            del c.item
            del d.anything
        def builtin(c):
            delattr(c, "item")
        use(C(), D())
        builtin(C())
        """,
    )

    assert callees(graph, "main.use") == ["main.C.remove", "main.D.__delattr__"]
    assert callees(graph, "main.builtin") == ["<builtin>.delattr", "main.C.remove"]


ATTRIBUTE_HOOKS = """
class Base:
    pass
class Plain:
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
class Replacing:
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
    def __getattribute__(self, name):
        return None
    def __setattr__(self, name, value):
        self.__dict__[name] = value
    def __delattr__(self, name): pass
class Delegating(Base):
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
    def __delattr__(self, name):
        Base.__delattr__(self, name)
class Inheriting(Replacing):
    pass
class Restoring(Replacing):
    __getattribute__ = object.__getattribute__
    __setattr__ = object.__setattr__
    __delattr__ = object.__delattr__
"""
HOOKED_CLASSES = (
    "Plain",
    "Replacing",
    "Delegating",
    "Inheriting",
    "Restoring",
)


def hooked_graph(tmp_path):
    uses = "".join(
        f"def use_{name}(obj):\n"
        "    obj.item\n"
        "    obj.item = 1\n"
        "    del obj.item\n"
        f"use_{name}({name}())\n"
        for name in HOOKED_CLASSES
    )
    return main_graph(tmp_path, ATTRIBUTE_HOOKS + uses)


def test_a_hook_that_the_class_defines_is_the_caller_of_the_accessors(tmp_path):
    graph = hooked_graph(tmp_path)

    accessors = {"get": "__getattribute__", "change": "__setattr__"}
    accessors["remove"] = "__delattr__"
    assert callees(graph, "main.use_Plain") == [
        "main.Plain.change",
        "main.Plain.get",
        "main.Plain.remove",
    ]
    for name, owner in [
        ("Replacing", "Replacing"),
        ("Inheriting", "Replacing"),
        ("Delegating", "Delegating"),
    ]:
        assert callees(graph, f"main.use_{name}") == sorted(
            f"main.{owner}.{hook}" for hook in accessors.values()
        )
        for accessor, hook in accessors.items():
            assert f"main.{owner}.{accessor}" in callees(graph, f"main.{owner}.{hook}")
    assert callees(graph, "main.use_Restoring") == [
        "main.Replacing.change",
        "main.Replacing.get",
        "main.Replacing.remove",
    ]


def test_a_hook_stored_after_the_class_and_python_s_own_both_call_the_accessor(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        class P:
            def change(self, value): pass
            item = property(fset=change)
        def put(self, name, value):
            object.__setattr__(self, name, value)
        P.__setattr__ = put
        def use():
            P().item = 1
        """,
    )

    assert callees(graph, "main.use") == ["main.P.change", "main.put"]
    assert "main.P.change" in callees(graph, "main.put")


def test_getattr_runs_from_the_load_site_under_a_delegating_hook(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def __getattribute__(self, name):
                return object.__getattribute__(self, name)
            def __getattr__(self, name):
                return None
        def use(c):
            c.missing
        use(C())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.C.__getattr__",
        "main.C.__getattribute__",
    ]


def test_super_loads_run_the_getter_and_not_the_class_hook(tmp_path):
    graph = main_graph(
        tmp_path,
        ATTRIBUTE_HOOKS
        + """
class Child(Replacing):
    def via_super(self):
        return super().item
Child().via_super()
""",
    )

    assert callees(graph, "main.Child.via_super") == [
        "<builtin>.super",
        "main.Replacing.get",
    ]


def test_attribute_hooks_of_external_classes_are_not_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from lib import Base
        class Hooked:
            def __getattribute__(self, name):
                return object.__getattribute__(self, name)
        class Mine(Base):
            pass
        def use(mine):
            mine.handler.run()
            mine.other = 1
        use(Mine())
        """,
    )

    assert not [name for name in callees(graph, "main.use") if "__" in name]


@pytest.mark.parametrize(
    "assign",
    [
        "D.__setattr__ = put",
        'setattr(D, "__setattr__", put)',
        pytest.param(
            'name = "__setattr__"\nsetattr(D, name, put)',
            id="setattr with a name decided at a fixpoint",
        ),
    ],
)
def test_hooks_assigned_outside_class_bodies_are_called(tmp_path, assign):
    graph = main_graph(
        tmp_path,
        f"""
def target(): pass
def put(self, name, value):
    value()
class D:
    pass
{assign}
def use():
    D().anything = target
""",
    )

    assert callees(graph, "main.use") == ["main.put"]
    assert callees(graph, "main.put") == ["main.target"]


ASSIGNED_HOOKS = {
    "__getattribute__": ("def hook(self, name):\n    return target", "C().anything()"),
    "__delattr__": ("def hook(self, name):\n    target()", "del C().anything"),
    "__setattr__": (
        "def hook(self, name, value):\n    value()",
        "C().anything = target",
    ),
}


GETTERS = ("__getattr__", "__getattribute__")
HOOK_ACCESSES = {
    "__getattr__": "C().missing()",
    "__getattribute__": "C().anything()",
    "__setattr__": "C().anything = 1",
    "__delattr__": "del C().anything",
}
HOOK_KINDS = {
    "function": ("hook", "main.hook"),
    "lambda": ("lambda *args: {body}", "main.<lambda1>"),
    "bound method": ("Helper().run", "main.Helper.run"),
    "callable instance": ("Caller()", "main.Caller.__call__"),
    "staticmethod": ("staticmethod(hook)", "main.hook"),
    "classmethod": ("classmethod(hook)", "main.hook"),
}
PLACES = {
    "class body": "class C:\n    {hook} = {value}\n",
    "assignment": "class C:\n    pass\nC.{hook} = {value}\n",
    "setattr": 'class C:\n    pass\nsetattr(C, "{hook}", {value})\n',
}


HOOK_CASES = [
    (hook, kind, place)
    for hook in sorted(HOOK_ACCESSES)
    for kind in sorted(HOOK_KINDS)
    for place in sorted(PLACES)
    if hook != "__getattr__" or place == "class body"
]


@pytest.mark.parametrize(("hook", "kind", "place"), HOOK_CASES)
def test_every_hook_is_whatever_the_class_attribute_holds(tmp_path, hook, kind, place):
    body = "target" if hook in GETTERS else "target()"
    value, callee = HOOK_KINDS[kind]
    if kind == "lambda" and place == "class body":
        callee = "main.C.<lambda1>"
    program = (
        "import functools\n"
        "def target(): pass\n"
        f"def hook(*args):\n    return {body}\n"
        f"class Helper:\n    def run(self, *args):\n        return {body}\n"
        f"class Caller:\n    def __call__(self, *args):\n        return {body}\n"
        + PLACES[place].format(hook=hook, value=value.format(body=body))
        + f"def use():\n    {HOOK_ACCESSES[hook]}\n"
    )
    graph = main_graph(tmp_path, program)

    if hook in GETTERS:
        assert callees(graph, "main.use") == sorted([callee, "main.target"])
        assert "main.target" not in callees(graph, callee)
    else:
        assert callees(graph, "main.use") == [callee]
        assert callees(graph, callee) == ["main.target"]


@pytest.mark.parametrize("place", ["assignment", "setattr"])
def test_limit_getattr_assigned_after_the_class_is_not_called(tmp_path, place):
    graph = main_graph(
        tmp_path,
        "def target(): pass\n"
        "def hook(self, name):\n    return target\n"
        + PLACES[place].format(hook="__getattr__", value="hook")
        + "def use():\n    C().missing()\n",
    )

    assert callees(graph, "main.use") == []


@pytest.mark.parametrize("hook", sorted(HOOK_ACCESSES))
def test_limit_a_partial_hook_is_not_called(tmp_path, hook):
    body = "target" if hook in GETTERS else "target()"
    graph = main_graph(
        tmp_path,
        "import functools\n"
        "def target(): pass\n"
        f"def hook(*args):\n    return {body}\n"
        f"class C:\n    {hook} = functools.partial(hook, 1)\n"
        f"def use():\n    {HOOK_ACCESSES[hook]}\n",
    )

    assert "main.hook" not in callees(graph, "main.use")
    assert "main.hook" not in callees(graph, "main")


def test_getattr_of_a_subclass_body_hides_its_bases(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def a(): pass
        def b(): pass
        class Base:
            def __getattr__(self, name):
                return b
        class Sub(Base):
            def __getattr__(self, name):
                return a
        Sub().missing()
        """,
    )

    assert callees(graph, "main") == ["main.Sub.__getattr__", "main.a"]


def test_getattr_of_a_base_runs_for_a_subclass_that_defines_none(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        class Base:
            def __getattr__(self, name):
                return target
        class Sub(Base):
            pass
        Sub().missing()
        """,
    )

    assert callees(graph, "main") == ["main.Base.__getattr__", "main.target"]


def test_limit_a_getter_that_raises_attribute_error_does_not_call_getattr(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def fetch(): pass
        class Lazy:
            def __get__(self, obj, owner=None):
                raise AttributeError("value")
        class Node:
            value = Lazy()
            @property
            def parent(self):
                raise AttributeError("parent")
            def __getattr__(self, name):
                return fetch
        def use():
            node = Node()
            node.parent()
            node.value()
        """,
    )

    assert callees(graph, "main.use") == ["main.Lazy.__get__", "main.Node.parent"]


@pytest.mark.parametrize("name", sorted(ASSIGNED_HOOKS))
def test_a_hook_named_late_still_runs_for_earlier_accesses(tmp_path, name):
    definition, access = ASSIGNED_HOOKS[name]
    graph = main_graph(
        tmp_path,
        f"def target(): pass\n{definition}\nclass C:\n    pass\n"
        f'name = f"{name}"\nsetattr(C, name, hook)\ndef use():\n    {access}\n',
    )

    caller_of_target = "main.use" if name in GETTERS else "main.hook"
    assert "main.hook" in callees(graph, "main.use")
    assert "main.target" in callees(graph, caller_of_target)
    other_caller = "main.hook" if caller_of_target == "main.use" else "main.use"
    assert "main.target" not in callees(graph, other_caller)
