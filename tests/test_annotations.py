import pytest
from programs import analysed, call_graph, callees, main_graph

STRATEGIES = """
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass
"""

BOTH = ["main.Fast.__call__", "main.Strategy.__call__"]


def graph_of(tmp_path, source):
    return main_graph(tmp_path, STRATEGIES + source)


def inside(graph, caller):
    return [callee for callee in callees(graph, caller) if callee.startswith("main.")]


def test_a_class_annotation_names_its_instances_and_subclasses(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def run(strategy: Strategy):
    strategy(1)
""",
    )

    assert callees(graph, "main.run") == BOTH


def test_optional_and_union_arms(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import typing
from typing import Callable, Optional, Union
def optional(s: Optional[Strategy]):
    s(1)
def pipe(s: Strategy | None):
    s(1)
def union(s: Union[Strategy, Callable[[int], None]]):
    s(1)
def qualified(s: typing.Optional[typing.Union[int, Strategy]]):
    s(1)
""",
    )

    for function in ("optional", "pipe", "union", "qualified"):
        assert callees(graph, f"main.{function}") == BOTH, function


def test_string_annotations_and_postponed_evaluation(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": "from __future__ import annotations\n"
            + STRATEGIES
            + """
def postponed(s: Strategy):
    s(1)
def quoted(s: "Strategy | None"):
    s(1)
def nested(s: "list['Strategy']"):
    for each in s:
        each(1)
""",
        },
    )

    for function in ("postponed", "quoted", "nested"):
        assert callees(graph, f"main.{function}") == BOTH, function


def test_an_alias_imported_under_type_checking(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "strategies.py": """
import typing
class Base:
    def __call__(self, state): pass
class Fast(Base):
    def __call__(self, state): pass
BaseT = Base | typing.Callable[[int], bool]
""",
            "main.py": """
import typing
import strategies
if typing.TYPE_CHECKING:
    from strategies import BaseT
def run(s: "BaseT"):
    s(1)
""",
        },
    )

    assert callees(graph, "main.run") == [
        "strategies.Base.__call__",
        "strategies.Fast.__call__",
    ]


def test_type_names_the_classes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import typing
class Base:
    @classmethod
    def make(cls): pass
class Child(Base):
    @classmethod
    def make(cls): pass
def build(kind: type[Base]):
    kind.make()
def old_style(kind: typing.Type[Base]):
    kind.make()
""",
    )

    expected = ["main.Base.make", "main.Child.make"]
    assert callees(graph, "main.build") == expected
    assert callees(graph, "main.old_style") == expected


def test_type_names_every_class_below_by_any_path(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Base:
    @staticmethod
    def make(): pass
class Left(Base): pass
class Right(Base): pass
class Both(Left, Right):
    @staticmethod
    def make(): pass
def late():
    return Both
class Later(late()):
    @staticmethod
    def make(): pass
def build(kind: type[Base]):
    kind.make()
""",
    )

    expected = ["main.Base.make", "main.Both.make", "main.Later.make"]
    assert callees(graph, "main.build") == expected


def test_one_level_of_standard_containers(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from collections.abc import Iterable, Sequence
from typing import Dict, List
def each(items: list[Strategy]):
    for s in items:
        s(1)
def old_list(items: List[Strategy]):
    items[0](1)
def sequence(items: Sequence[Strategy]):
    items[0](1)
def iterable(items: Iterable[Strategy]):
    for s in items:
        s(1)
def pairs(items: tuple[Strategy, ...]):
    first, second = items
    first(1)
def mapping(table: dict[str, Strategy]):
    table["x"](1)
def old_mapping(table: Dict[str, Strategy]):
    for s in table.values():
        s(1)
def deeper(items: list[list[Strategy]]):
    for inner in items:
        for s in inner:
            s(1)
""",
    )

    for function in (
        "each",
        "old_list",
        "sequence",
        "iterable",
        "pairs",
        "mapping",
        "old_mapping",
    ):
        assert inside(graph, f"main.{function}") == BOTH, function
    assert callees(graph, "main.deeper") == []


def test_variadic_parameters(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def combine(*strategies: Strategy):
    for s in strategies:
        s(1)
def named(**strategies: Strategy):
    for s in strategies.values():
        s(1)
""",
    )

    assert callees(graph, "main.combine") == BOTH
    assert inside(graph, "main.named") == BOTH


def test_annotations_that_name_no_analysed_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import types
from typing import Any, Callable, TypeVar
T = TypeVar("T", bound=Strategy)
def f(a: object, b: Any, c: Callable, d: T, e: int, g: types.ModuleType, h: type):
    a(1)
    b(1)
    c(1)
    d(1)
    e(1)
    g(1)
    h(1)
""",
    )

    assert inside(graph, "main.f") == []


def test_annotated_and_a_generic_analysed_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from typing import Annotated, Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    def open(self): pass
def annotated(s: Annotated[Strategy, "fast"]):
    s(1)
def boxed(box: Box[int]):
    box.open()
""",
    )

    assert callees(graph, "main.annotated") == BOTH
    assert callees(graph, "main.boxed") == ["main.Box.open"]


def test_a_method_parameter_stored_on_the_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Retrying:
    def __init__(self, stop: Strategy = None):
        self.stop = stop
    def iter(self):
        self.stop(1)
""",
    )

    assert callees(graph, "main.Retrying.iter") == BOTH


def test_limit_an_annotation_is_believed_when_the_calls_pass_something_else(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
def _helper(s: Strategy):
    s(1)
def use():
    _helper(Fast())
""",
    )

    assert callees(graph, "main._helper") == BOTH


def test_dataclass_fields_get_their_annotated_values(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import dataclasses
from dataclasses import dataclass
from typing import NamedTuple
@dataclasses.dataclass
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
@dataclass(frozen=True)
class Frozen:
    strategy: "Strategy"
    def run(self):
        self.strategy(1)
class Pair(NamedTuple):
    first: Strategy
    def run(self):
        self.first(1)
class Plain:
    strategy: Strategy
    def run(self):
        self.strategy(1)
""",
    )

    assert callees(graph, "main.Config.run") == BOTH
    assert callees(graph, "main.Frozen.run") == BOTH
    assert inside(graph, "main.Pair.run") == BOTH
    assert callees(graph, "main.Plain.run") == []


def test_a_dataclass_made_by_the_package_holds_its_annotated_fields(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import dataclasses
@dataclasses.dataclass
class Config:
    strategy: Strategy
def use():
    config = Config(Fast())
    config.strategy(1)
""",
    )

    assert inside(graph, "main.use") == BOTH


def test_a_recursive_alias_ends(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from typing import Union
Tree = Union[Strategy, list["Tree"]]
def walk(tree: Tree):
    tree(1)
""",
    )

    assert callees(graph, "main.walk") == BOTH


def test_a_subscripted_alias_reads_the_alias(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from typing import Generic, Optional, TypeVar, Union
T = TypeVar("T")
class Box(Generic[T]):
    def run(self): pass
class Bag(Generic[T]):
    def run(self): pass
AnyBox = Union[Box[T], Bag[T]]
MaybeBox = Optional[Box[T]]
type Pair[X] = Box[X] | Bag[X]
Tree = Union[Box[T], list["Tree[T]"]]
Rec = Union[Bag[T], "Rec[T]"]
TABLE = [Box]
def either(box: AnyBox[int]):
    box.run()
def maybe(box: MaybeBox[str]):
    box.run()
def pair(box: Pair[int]):
    box.run()
def text(box: "AnyBox[int]"):
    box.run()
def nested(box: Optional[AnyBox[int]]):
    box.run()
def walk(tree: Tree[int], rec: Rec[int]):
    tree.run()
    rec.run()
def element(box: TABLE[0]):
    box.run()
""",
    )

    both = ["main.Bag.run", "main.Box.run"]
    assert callees(graph, "main.either") == both
    assert callees(graph, "main.maybe") == ["main.Box.run"]
    assert callees(graph, "main.pair") == both
    assert callees(graph, "main.text") == both
    assert callees(graph, "main.nested") == both
    assert callees(graph, "main.walk") == both
    assert callees(graph, "main.element") == []


def test_an_alias_that_subscripts_itself_ends(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from typing import List, TypeAlias, TypeVar, Union
T = TypeVar("T")
type Loop[X] = Loop[X] | Strategy
type Ping[X] = Pong[X] | Strategy
type Pong[X] = Ping[X]
Plain = Union[Strategy, List[T]]
Plain = Plain[T]
Left = Union[Strategy, List[T]]
Right: TypeAlias = Left[T]
Left = Right[T]
def loop(s: Loop[int], t: "Loop[int]"):
    s(1)
    t(1)
def ping(s: Pong[int]):
    s(1)
def plain(s: Plain[int], t: Left[int]):
    s(1)
    t(1)
""",
    )

    assert callees(graph, "main.loop") == BOTH
    assert callees(graph, "main.ping") == BOTH
    assert callees(graph, "main.plain") == BOTH


def test_names_that_only_a_type_checker_imports(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "strategies.py": """
import typing
class Base:
    def __call__(self, state): pass
class Fast(Base):
    def __call__(self, state): pass
BaseT = Base | typing.Callable[[int], bool]
""",
            "pkg/__init__.py": "",
            "pkg/kinds.py": """
class Kind:
    def run(self): pass
""",
            "main.py": """
from typing import TYPE_CHECKING
import strategies
import pkg.kinds
if TYPE_CHECKING:
    from strategies import BaseT
    import pkg.kinds as kinds
    from pkg import kinds as other
def run(s: "BaseT"):
    s(1)
def make(k: "kinds.Kind", o: "other.Kind"):
    k.run()
    o.run()
class Holder:
    if TYPE_CHECKING:
        from strategies import Fast
    def go(self, f: "Fast"):
        f(1)
""",
        },
    )

    assert callees(graph, "main.run") == [
        "strategies.Base.__call__",
        "strategies.Fast.__call__",
    ]
    assert callees(graph, "main.make") == ["pkg.kinds.Kind.run"]
    assert callees(graph, "main.Holder.go") == ["strategies.Fast.__call__"]


def test_a_type_only_name_does_not_import_its_module(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "extra.py": "class Extra:\n    def run(self): pass\n",
            "main.py": """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from extra import Extra
def use(e: "Extra"):
    e.run()
""",
        },
    )

    assert "extra" not in generator.output()


@pytest.mark.parametrize("submodule", [None, "pkg/X.py", "pkg/X/__init__.py"])
def test_a_type_only_from_import_reads_the_package_attribute(tmp_path, submodule):
    files = {
        "pkg/__init__.py": "class T:\n    def run(self): pass\nX = T\n",
        "main.py": """
import pkg
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import X
def use(value: "X"):
    value.run()
""",
    }
    if submodule is not None:
        files[submodule] = ""
    graph = call_graph(tmp_path, files)

    assert callees(graph, "main.use") == ["pkg.T.run"]


def test_a_type_only_from_import_of_a_private_name_reads_the_package_attribute(
    tmp_path,
):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "class T:\n    def run(self): pass\n_Holder__x = T\n",
            "pkg/_Holder__x.py": "",
            "pkg/__x.py": "",
            "main.py": """
import pkg
from typing import TYPE_CHECKING
class Holder:
    if TYPE_CHECKING:
        from pkg import __x
    def go(self, value: "__x"):
        value.run()
""",
        },
    )

    assert callees(graph, "main.Holder.go") == ["pkg.T.run"]


def test_a_type_only_import_reaches_a_deep_entry_module_through_its_packages(
    tmp_path,
):
    graph = call_graph(
        tmp_path,
        {
            "ns/a/b.py": "import main\nclass T:\n    def run(self): pass\n",
            "main.py": """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import ns.a as sub
def use(x: "sub.b.T"):
    x.run()
""",
        },
        entry_points=("ns/a/b.py",),
    )

    assert callees(graph, "main.use") == ["ns.a.b.T.run"]


DEEP_ENTRY_LAYOUTS = {
    "regular packages": ({"ns/__init__.py": "", "ns/a/__init__.py": ""}, True),
    "namespace packages": ({}, True),
    "a package beside a module of its name": (
        {"ns.py": "def f(): pass\n", "ns/__init__.py": ""},
        True,
    ),
    "a module beside a namespace directory": ({"ns.py": "def f(): pass\n"}, False),
    "a deeper module beside a namespace directory": (
        {"ns/a.py": "def f(): pass\n"},
        False,
    ),
}


@pytest.mark.parametrize("layout", DEEP_ENTRY_LAYOUTS)
def test_a_deep_entry_module_is_linked_only_through_packages(tmp_path, layout):
    extra, linked = DEEP_ENTRY_LAYOUTS[layout]
    graph = call_graph(
        tmp_path,
        {
            **extra,
            "ns/a/b.py": "import main\nclass T:\n    def run(self): pass\n",
            "main.py": """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import ns.a as sub
def use(x: "sub.b.T"):
    x.run()
""",
        },
        entry_points=("ns/a/b.py",),
    )

    assert callees(graph, "main.use") == (["ns.a.b.T.run"] if linked else [])


def test_a_module_that_shadows_a_namespace_directory_has_no_entry_below_it(
    tmp_path,
):
    graph = call_graph(
        tmp_path,
        {
            "ns.py": "def f(): pass\n",
            "ns/a/b.py": "class T:\n    def run(self): pass\nimport main\n",
            "main.py": """
import ns
try:
    ns.a.b.T().run()
except AttributeError:
    pass
""",
        },
        entry_points=("ns/a/b.py",),
    )

    assert callees(graph, "main") == []


@pytest.mark.parametrize("package", [False, True])
def test_a_directory_named_init_is_a_package_only_with_its_own_initializer(
    tmp_path, package
):
    files = {
        "pkg/__init__.py": "",
        "pkg/__init__/b.py": "class T:\n    def run(self): pass\nimport main\n",
        "main.py": """
import pkg
try:
    pkg.__init__.b.T().run()
except AttributeError:
    pass
""",
    }
    if package:
        files["pkg/__init__/__init__.py"] = ""
    graph = call_graph(tmp_path, files, entry_points=("pkg/__init__/b.py",))

    assert callees(graph, "main") == (["pkg.__init__.b.T.run"] if package else [])


def test_a_type_only_dotted_name_walks_the_package_attributes(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "import other as X\n",
            "pkg/X.py": "class T:\n    def run(self): pass\n",
            "other.py": "class T:\n    def run(self): pass\n",
            "main.py": """
import pkg
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import X
    import pkg.X
def use(x: "X.T", y: "pkg.X.T"):
    x.run()
    y.run()
""",
        },
    )

    assert callees(graph, "main.use") == ["other.T.run"]


def test_a_type_only_from_import_of_a_module_member_takes_the_real_module(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "from . import X\nimport other as X\n",
            "pkg/X.py": "class T:\n    def run(self): pass\n",
            "other.py": "class T:\n    def run(self): pass\n",
            "main.py": """
from typing import TYPE_CHECKING
from pkg.X import T
if TYPE_CHECKING:
    from pkg.X import T as AnnoT
def use(x: "AnnoT"):
    x.run()
use(T())
""",
        },
    )

    assert callees(graph, "main.use") == ["pkg.X.T.run"]


def test_a_namespace_directory_does_not_hide_an_outside_package(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "xml/local.py": "",
            "main.py": """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from xml.etree.ElementTree import Element
def use(x: "Element"):
    x.find("child")
""",
        },
    )

    assert callees(graph, "main.use") == ["xml.etree.ElementTree.Element.find"]


def test_a_type_only_from_import_of_a_submodule_that_the_package_does_not_bind(
    tmp_path,
):
    graph = call_graph(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/kinds.py": "class Kind:\n    def run(self): pass\n",
            "main.py": """
import pkg.kinds
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import kinds
    import pkg.kinds as aliased
def use(value: "kinds.Kind", other: "aliased.Kind"):
    value.run()
    other.run()
""",
        },
    )

    assert callees(graph, "main.use") == ["pkg.kinds.Kind.run"]


def test_forward_references(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Node:
    def connect(self, other: "Node"):
        other.run()
    def run(self): pass
def use(x: "Later", y: "AliasT"):
    x.go()
    y.go()
class Later:
    def go(self): pass
AliasT = Later | None
""",
    )

    assert callees(graph, "main.Node.connect") == ["main.Node.run"]
    assert callees(graph, "main.use") == ["main.Later.go"]


def test_postponed_forward_reference(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
from __future__ import annotations
def use(x: Later):
    x.go()
class Later:
    def go(self): pass
""",
        },
    )

    assert callees(graph, "main.use") == ["main.Later.go"]


def test_an_annotation_that_makes_a_scope_gives_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(x: "(lambda: None).__class__", y: "[a for a in b]"):
    pass
def g(x: (lambda: None).__class__):
    pass
""",
    )

    assert callees(graph, "main.f") == []
    assert callees(graph, "main.g") == []


def test_an_ordinary_subscript_is_no_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class C:
    def run(self): pass
def f(): pass
def g(): pass
name = ["run"][0]
getattr(C(), name)()
table = {"a": f, "b": g}
key = ["a"][0]
table[key]()
""",
    )

    assert callees(graph, "main") == ["<builtin>.getattr", "main.C.run", "main.f"]


def test_nested_string_annotations_are_told_apart(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class A:
    def run(self): pass
class B:
    def run(self): pass
def use(xs: "list['A | None'] | list['B | None']"):
    for x in xs:
        x.run()
""",
    )

    assert callees(graph, "main.use") == ["main.A.run", "main.B.run"]


def test_a_typed_dict_gives_no_attributes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
from typing import TypedDict
class Handler:
    def run(self): pass
class Config(TypedDict):
    handler: Handler
def use(cfg: Config):
    cfg.handler.run()
""",
    )

    assert inside(graph, "main.use") == []


@pytest.mark.parametrize("module", ["typing", "typing_extensions"])
def test_a_typed_dict_class_is_a_dict(tmp_path, module):
    graph = main_graph(
        tmp_path,
        f"""
import {module}
class Parameters({module}.TypedDict, total=False):
    size: int
class Sized(Parameters):
    name: str
def make():
    return Parameters(size=1)
def use(params: Sized):
    params.get("size")
make().items()
Sized(size=2, name="a")
""",
    )

    assert callees(graph, "main.make") == ["<builtin>.dict.__init__"]
    assert callees(graph, "main") == [
        "<builtin>.dict.__init__",
        "<builtin>.dict.items",
        "main.make",
    ]
    assert callees(graph, "main.use") == ["<builtin>.dict.get"]


ITERATORS = """
import collections.abc
import dataclasses
import typing
from typing import AsyncIterator
class Chain(collections.abc.AsyncIterator):
    async def __anext__(self): pass
    def close(self): pass
    @classmethod
    def make(cls): pass
class Borrowed(AsyncIterator[int]):
    async def __anext__(self): pass
    def close(self): pass
class Scoped(Borrowed):
    def close(self): pass
    @classmethod
    def make(cls): pass
class Peer:
    def __aiter__(self): return self
    async def __anext__(self): pass
    def close(self): pass
    @classmethod
    def make(cls): pass
"""

CLOSERS = ["main.Borrowed.close", "main.Chain.close", "main.Scoped.close"]


def test_an_outside_class_names_the_analysed_classes_below_it(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATORS
        + """
T = typing.TypeVar("T")
AnyIterable = typing.Union[typing.AsyncIterable[T], typing.Iterable[T]]
def plain(it: AsyncIterator[int]):
    it.close()
def bare(it: collections.abc.AsyncIterator):
    it.close()
def wider(it: typing.AsyncIterable[int]):
    it.close()
def optional(it: typing.Optional[AsyncIterator[int]]):
    it.close()
def union(it: AsyncIterator[int] | int):
    it.close()
def aliased(it: AnyIterable[int]):
    it.close()
def quoted(it: "AsyncIterator[int]"):
    it.close()
def star(*its: AsyncIterator[int]):
    for it in its:
        it.close()
def named(**its: AsyncIterator[int]):
    for it in its.values():
        it.close()
def listed(its: list[AsyncIterator[int]]):
    for it in its:
        it.close()
@dataclasses.dataclass
class Holder:
    it: AsyncIterator[int]
    def go(self):
        self.it.close()
""",
    )

    for function in (
        "plain",
        "bare",
        "wider",
        "optional",
        "union",
        "aliased",
        "quoted",
        "star",
        "named",
        "listed",
        "Holder.go",
    ):
        assert inside(graph, f"main.{function}") == CLOSERS, function


def test_type_of_an_outside_class_names_the_analysed_classes_below_it(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATORS
        + """
def build(kind: type[AsyncIterator[int]], wide: typing.Type[typing.AsyncIterable]):
    kind.make()
    wide.make()
""",
    )

    assert inside(graph, "main.build") == ["main.Chain.make", "main.Scoped.make"]


def test_limit_an_outside_class_does_not_name_a_class_that_only_fits(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATORS
        + """
class Sized(collections.abc.Sized):
    def __len__(self): pass
    def close(self): pass
def plain(it: AsyncIterator[int], kind: type[AsyncIterator]):
    it.close()
    kind.make()
""",
    )

    assert inside(graph, "main.plain") == sorted(
        [*CLOSERS, "main.Chain.make", "main.Scoped.make"]
    )


def test_object_and_type_name_no_analysed_class(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATORS
        + """
class Meta(type):
    def make(cls): pass
def anything(x: object, k: type, c: type[object], m: typing.Type[type]):
    x.close()
    k.make()
    c.make()
    m.make()
def alias(t: typing.Type):
    t.make()
""",
    )

    assert inside(graph, "main.anything") == []
    assert inside(graph, "main.alias") == []


def test_calling_an_instance_of_type_calls_a_class_that_is_not_known(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Opts:
    def __init__(self, meta): pass
class Schema:
    OPTIONS_CLASS: type = Opts
    KIND: type | None = None
    def make(self, meta: type, known: type[Opts]):
        self.OPTIONS_CLASS(meta)
        self.KIND()
        meta()
        meta.mro()
        known(meta)
""",
    )

    assert callees(graph, "main.Schema.make") == [
        "<builtin>.type.mro",
        "main.Opts.__init__",
    ]


def test_a_metaclass_with_its_own_call_keeps_the_edge(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import abc, enum
def lookup(kind: enum.EnumMeta, meta: abc.ABCMeta):
    kind(1)
    meta()
""",
    )

    assert callees(graph, "main.lookup") == ["enum.EnumMeta.__call__"]


def test_type_of_type_names_the_class_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import typing
def build(meta: type[type]):
    return meta("C", (), {})
def alias(meta: typing.Type[type]):
    return meta("C", (), {})
""",
    )

    assert callees(graph, "main.build") == ["<builtin>.type"]
    assert callees(graph, "main.alias") == ["<builtin>.type"]


def test_an_abstract_outside_class_names_what_is_below_it_through_the_stubs(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
import collections.abc
import typing
class Bag(collections.abc.Set):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
class Pool(collections.abc.MutableSet):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def add(self, x): pass
    def discard(self, x): pass
    def tick(self): pass
class Names(list):
    def tick(self): pass
class Store(collections.abc.MutableMapping):
    def __getitem__(self, key): pass
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
def ordered(items: typing.Sequence[str]):
    items.tick()
def sets(items: typing.AbstractSet[str]):
    items.tick()
def mutable(items: typing.MutableSet[str]):
    items.tick()
def table(rows: typing.Mapping[str, int]):
    rows.tick()
""",
    )

    assert inside(graph, "main.ordered") == ["main.Names.tick"]
    assert inside(graph, "main.sets") == ["main.Bag.tick", "main.Pool.tick"]
    assert inside(graph, "main.mutable") == ["main.Pool.tick"]
    assert inside(graph, "main.table") == ["main.Store.tick"]


def test_an_abstract_class_of_the_stubs_names_what_is_below_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import contextlib
import typing
class Manager(contextlib.AbstractAsyncContextManager):
    async def __aexit__(self, *args): pass
    def tick(self): pass
class Plain(contextlib.AbstractContextManager):
    def __exit__(self, *args): pass
    def tick(self): pass
def asynchronous(m: typing.AsyncContextManager[int]):
    m.tick()
def stub_name(m: contextlib.AbstractAsyncContextManager):
    m.tick()
def synchronous(m: typing.ContextManager[int]):
    m.tick()
""",
    )

    assert inside(graph, "main.asynchronous") == ["main.Manager.tick"]
    assert inside(graph, "main.stub_name") == ["main.Manager.tick"]
    assert inside(graph, "main.synchronous") == ["main.Plain.tick"]


def test_builtin_protocols_name_the_classes_below_them_through_abstract_classes(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
import collections.abc
import typing
class Box(collections.abc.Collection):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
class Countdown(collections.abc.Iterator):
    def __next__(self): pass
    def tick(self): pass
class Backwards(collections.abc.Reversible):
    def __iter__(self): pass
    def __reversed__(self): pass
    def tick(self): pass
class Key(collections.abc.Hashable):
    def __hash__(self): return 0
    def tick(self): pass
class Sized(collections.abc.Sized):
    def __len__(self): return 0
    def tick(self): pass
class Line(collections.abc.Sequence):
    def __getitem__(self, i): pass
    def __len__(self): return 0
    def tick(self): pass
def iterable(a: typing.Iterable[int]):
    a.tick()
def iterator(b: collections.abc.Iterator):
    b.tick()
def collection(c: typing.Collection[int]):
    c.tick()
def container(d: collections.abc.Container):
    d.tick()
def sized(e: typing.Sized):
    e.tick()
def hashable(f: collections.abc.Hashable):
    f.tick()
def reversible(g: typing.Reversible[int]):
    g.tick()
""",
    )

    assert inside(graph, "main.iterable") == [
        "main.Backwards.tick",
        "main.Box.tick",
        "main.Countdown.tick",
        "main.Line.tick",
    ]
    assert inside(graph, "main.iterator") == ["main.Countdown.tick"]
    assert inside(graph, "main.collection") == ["main.Box.tick", "main.Line.tick"]
    assert inside(graph, "main.container") == ["main.Box.tick", "main.Line.tick"]
    assert inside(graph, "main.sized") == ["main.Sized.tick"]
    assert inside(graph, "main.hashable") == ["main.Key.tick"]
    assert inside(graph, "main.reversible") == ["main.Backwards.tick", "main.Line.tick"]


BUILTIN_PROTOCOL_PARAMETERS = """
def protocols(
    a: typing.Iterable[int],
    b: typing.Iterator[int],
    c: typing.Collection[int],
    d: typing.Container[int],
    e: typing.Sized,
    f: typing.Hashable,
    g: typing.Reversible[int],
):
    for each in (a, b, c, d, e, f, g):
        each.ping()
"""


def test_limit_a_builtin_protocol_names_no_class_below_it_through_a_concrete_class(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        CONCRETE_SUBCLASSES
        + """
class Text(str):
    def ping(self): pass
class Row(typing.NamedTuple):
    x: int
    def ping(self): pass
"""
        + BUILTIN_PROTOCOL_PARAMETERS
        + """
def sequence(s: typing.Sequence[int]):
    s.ping()
""",
    )

    assert inside(graph, "main.protocols") == []
    assert inside(graph, "main.sequence") == [
        "main.Names.ping",
        "main.Pair.ping",
        "main.Queue.ping",
        "main.Row.ping",
        "main.Text.ping",
    ]


def test_an_abstract_base_reaches_a_protocol_only_through_abstract_classes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import tokenize
import typing
class Token(tokenize._TokenInfo):
    def ping(self): pass
"""
        + BUILTIN_PROTOCOL_PARAMETERS
        + """
def sequence(s: typing.Sequence[int]):
    s.ping()
""",
    )

    assert inside(graph, "main.protocols") == []
    assert inside(graph, "main.sequence") == ["main.Token.ping"]


def test_one_abstract_path_admits_beside_a_concrete_one(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import collections.abc
import typing
class Names(list):
    def ping(self): pass
class Stream(Names, collections.abc.Iterator):
    def __next__(self): pass
    def ping(self): pass
def use(xs: typing.Iterable[str]):
    xs.ping()
""",
    )

    assert inside(graph, "main.use") == ["main.Stream.ping"]


def test_value_flow_still_reaches_a_subclass_of_a_concrete_builtin(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import typing
class Names(list):
    def __iter__(self): return iter([])
def drain(xs: typing.Iterable[str]):
    for x in xs:
        pass
drain(Names())
""",
    )

    assert inside(graph, "main.drain") == ["main.Names.__iter__"]


CONCRETE_SUBCLASSES = """
import collections
import types
import typing
class Names(list):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Table(dict):
    def ping(self): pass
class Bag(set):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Frozen(frozenset):
    def ping(self): pass
class Pair(tuple):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Queue(collections.deque):
    def ping(self): pass
class Default(collections.defaultdict):
    def ping(self): pass
class Ordered(collections.OrderedDict):
    def ping(self): pass
class Tally(collections.Counter):
    def ping(self): pass
class Chain(collections.ChainMap):
    def ping(self): pass
class Failure(Exception):
    def ping(self): pass
class Mock(typing.Any):
    def ping(self): pass
class Lazy(types.ModuleType):
    def ping(self): pass
"""


def test_a_concrete_outside_class_names_no_class_below_it(tmp_path):
    graph = main_graph(
        tmp_path,
        CONCRETE_SUBCLASSES
        + """
import typing_extensions
def concrete(
    a: list[int],
    b: typing.List[int],
    c: typing.Dict[str, int],
    d: typing.Set[int],
    e: typing.FrozenSet[int],
    f: typing.Tuple[int, ...],
    g: tuple[()],
    h: typing.Deque[int],
    i: typing.DefaultDict[str, int],
    j: typing.OrderedDict[str, int],
    k: typing_extensions.OrderedDict,
    l: typing.Counter[str],
    m: typing.ChainMap[str, int],
    n: BaseException,
    o: typing.Any,
    p: types.ModuleType,
):
    for each in (a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p):
        each.ping()
def classes(
    a: type[list[int]],
    b: typing.Type[typing.List[int]],
    c: type[tuple[()]],
    d: type[dict],
):
    for each in (a, b, c, d):
        each.make()
def sequence(a: typing.Sequence[int], b: type[typing.Sequence[int]]):
    a.ping()
    b.make()
def sets(a: typing.AbstractSet[int], b: type[typing.AbstractSet[int]]):
    a.ping()
    b.make()
""",
    )

    assert inside(graph, "main.concrete") == []
    assert inside(graph, "main.classes") == []
    assert inside(graph, "main.sequence") == [
        "main.Names.make",
        "main.Names.ping",
        "main.Pair.make",
        "main.Pair.ping",
        "main.Queue.ping",
    ]
    assert inside(graph, "main.sets") == [
        "main.Bag.make",
        "main.Bag.ping",
        "main.Frozen.ping",
    ]


def test_an_empty_tuple_annotation_is_a_tuple(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import typing
def instance(a: tuple[()]):
    a.count(1)
def alias(a: typing.Tuple[()]):
    a.count(1)
def kind(k: type[tuple[()]]):
    k()
def optional_kind(k: typing.Optional[type[tuple[()]]]):
    k()
""",
    )

    for function in ("instance", "alias"):
        assert callees(graph, f"main.{function}") == ["<builtin>.tuple.count"]
    for function in ("kind", "optional_kind"):
        assert callees(graph, f"main.{function}") == ["<builtin>.tuple"]


def test_an_annotated_assignment_stores_what_its_annotation_names(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import copy
import typing
class Runner:
    default: Strategy = None
    def __init__(self, given):
        self.strategy: Strategy = copy.copy(given)
        self.many: list[Strategy] = []
        self.table: dict[str, Strategy] = {}
        self.slots = {}
        self.slots["a"]: Strategy = None
    def attribute(self):
        self.strategy(1)
    def listed(self):
        for s in self.many:
            s(1)
    def mapped(self):
        self.table["x"](1)
    def subscript(self):
        self.slots["a"](1)
    def class_level(self):
        self.default(1)
def local(given):
    s: typing.Optional[Strategy] = copy.copy(given)
    s(1)
CURRENT: Strategy = None
def module_level():
    CURRENT(1)
""",
    )

    for caller in (
        "Runner.attribute",
        "Runner.listed",
        "Runner.mapped",
        "Runner.subscript",
        "Runner.class_level",
        "local",
        "module_level",
    ):
        assert inside(graph, f"main.{caller}") == BOTH, caller


def test_an_annotated_assignment_keeps_its_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Other:
    def __call__(self, state): pass
def run():
    s: Strategy = Other()
    s(1)
""",
    )

    assert inside(graph, "main.run") == sorted([*BOTH, "main.Other.__call__"])


TYPEHINT = """
import sys
from typing import TYPE_CHECKING
class Table:
    def insert(self):
        self.storage()
    def storage(self): pass
def with_typehint(baseclass):
    if TYPE_CHECKING:
        return baseclass
    return object
"""

DATABASE = """
class Database(TableBase):
    def __getattr__(self, name):
        return getattr(Table(), name)
def later():
    TableBase().insert()
"""


def test_a_class_statement_reads_its_bases_without_declared_values(tmp_path):
    graph = main_graph(
        tmp_path,
        TYPEHINT + "TableBase: type[Table] = with_typehint(Table)" + DATABASE,
    )

    assert callees(graph, "main.Table.insert") == ["main.Table.storage"]
    assert callees(graph, "main.later") == ["<builtin>.object", "main.Table.insert"]


def test_limit_a_base_read_through_a_join_keeps_the_declared_values(tmp_path):
    graph = main_graph(
        tmp_path,
        TYPEHINT
        + """
if sys.argv:
    TableBase: type[Table] = with_typehint(Table)
else:
    TableBase: type[Table] = with_typehint(Table)
"""
        + DATABASE,
    )

    assert "main.Database.__getattr__" in callees(graph, "main.Table.insert")


def test_an_annotation_without_a_value_names_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
s: Strategy
def run(given):
    t: Strategy
    t = given
    t(1)
class Plain:
    strategy: Strategy
    def __init__(self, given):
        self.strategy = given
    def run(self):
        self.strategy(1)
def module_level():
    s(1)
""",
    )

    for function in ("run", "Plain.run", "module_level"):
        assert inside(graph, f"main.{function}") == [], function


def test_limit_the_annotation_of_a_local_assignment_is_read_as_if_evaluated(
    tmp_path,
):
    graph = call_graph(
        tmp_path,
        {
            "mod.py": """
class Thing:
    def run(self): pass
def __getattr__(name):
    return Thing
""",
            "main.py": """
import mod
def f(v):
    x: mod.Other = v
    x.run()
f(None)
""",
        },
    )

    assert callees(graph, "main.f") == ["mod.Thing.run", "mod.__getattr__"]


def test_a_string_annotation_runs_no_attribute_hook(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "mod.py": """
class Thing:
    def run(self): pass
def __getattr__(name):
    return Thing
""",
            "main.py": """
import mod
def f(v: "mod.Other", w: "mod.Thing"):
    v.run()
    w.run()
""",
        },
    )

    assert callees(graph, "main") == []
    assert callees(graph, "main.f") == ["mod.Thing.run"]


def test_the_fields_of_a_ctypes_structure_hold_their_types(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ctypes
        class Point(ctypes.Structure):
            _fields_ = (("x", ctypes.c_int),)
            def show(self): pass
        class Rect(ctypes.Structure):
            _fields_ = [("origin", Point), ("count", ctypes.c_uint32)]
            def use(self):
                self.origin.show()
                self.count.bit_length()
        """,
    )

    assert callees(graph, "main.Rect.use") == [
        "<builtin>.int.bit_length",
        "main.Point.show",
    ]


def test_an_import_in_an_except_clause_of_type_checking_names_a_type(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "shapes.py": "class Shape:\n    def area(self): pass\nclass Other: pass\n",
            "main.py": """
from typing import TYPE_CHECKING
import shapes
if TYPE_CHECKING:
    try:
        from shapes import Other
    except ImportError:
        from shapes import Shape
def use(shape: "Shape"):
    shape.area()
""",
        },
    )

    assert callees(graph, "main.use") == ["shapes.Shape.area"]


def test_a_string_annotation_that_does_not_parse_names_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def run(strategy: "Strategy ("):
    strategy(1)
""",
    )

    assert callees(graph, "main.run") == []


def test_an_annotation_of_class_in_a_method_names_its_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Runner:
    def run(self): pass
    def copy(self):
        other: __class__ = make()
        other.run()
""",
    )

    assert callees(graph, "main.Runner.copy") == ["main.Runner.run"]


def test_a_class_annotation_naming_a_class_bound_builtin_names_both(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Holder:
    str = Fast
    def use(self, text: str):
        text.upper()
        text(1)
""",
    )

    assert callees(graph, "main.Holder.use") == [
        "<builtin>.str.upper",
        "main.Fast.__call__",
    ]


def test_a_subscript_without_arguments_names_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
from typing import Annotated, Type
def run(first: Annotated[()], second: Type[()]):
    first(1)
    second(1)
""",
    )

    assert callees(graph, "main.run") == []


def test_only_ctypes_structures_with_literal_fields_hold_their_types(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ctypes, sys
        class Plain:
            pass
        class NotStructure(Plain):
            _fields_ = [("x", ctypes.c_int)]
        Base = ctypes.Structure if sys.argv else ctypes.Union
        class Either(Base):
            _fields_ = [("x", ctypes.c_int)]
        class Array(ctypes.Structure):
            _fields_ = [("xs", ctypes.c_int * 4), ("y", ctypes.c_int)]
        class Called(ctypes.Structure):
            _fields_ = make()
        class Short(ctypes.Structure):
            _fields_ = [("x",)]
        class Unnamed(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int)]
        def use(n: NotStructure, e: Either, a: Array, c: Called, s: Short, u: Unnamed):
            n.x.bit_length()
            e.x.as_integer_ratio()
            a.xs.bit_length()
            a.y.conjugate()
            c.x.bit_length()
            s.x.bit_length()
            u.x.bit_length()
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.int.as_integer_ratio",
        "<builtin>.int.conjugate",
    ]


def test_a_class_decorator_that_is_no_dataclass_gives_no_field_values(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def keep(cls):
    return cls
@keep
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
""",
    )

    assert callees(graph, "main.Config.run") == []


def test_a_string_annotation_reads_a_member_defined_on_a_class_only(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            class Inner:
                def m(self): pass
        class Other:
            def m(self): pass
        class Meta(type):
            def __getattr__(cls, name): return Other
        class Dynamic(metaclass=Meta): pass
        c = C()
        def member(x: "C.Inner"): x.m()
        def of_instance(x: "c.Inner"): x.m()
        def of_function(x: "member.Inner"): x.m()
        def through_getattr(x: "Dynamic.Inner"): x.m()
        """,
    )

    assert callees(graph, "main.member") == ["main.C.Inner.m"]
    assert callees(graph, "main.of_instance") == []
    assert callees(graph, "main.of_function") == []
    assert callees(graph, "main.through_getattr") == []


def test_a_decorator_that_may_be_either_dataclass_form_holds_the_fields_once(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import dataclasses
import sys
make = dataclasses.dataclass if sys.argv else dataclasses.dataclass(frozen=True)
@make
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
""",
    )

    assert callees(graph, "main.Config.run") == BOTH
