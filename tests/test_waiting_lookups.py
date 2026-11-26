import textwrap

import pytest
from programs import analysed, callees, main_graph, no_rule_sees_what_is_opaque

from pycg.formats import dumps

DEFINITIONS = """
def f(*args): pass
def g(*args): pass
def h(*args): pass
class C:
    pass
class D(C):
    pass
a = C()
b = C()
d = D()
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_method_stored_on_the_class_reaches_every_instance_at_the_load(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            x.run()
        for x in (a, b, d):
            use(x)
        C.run = f
        """,
    )

    assert callees(graph, "main.use") == ["main.f"]


def test_a_method_stored_on_a_subclass_reaches_only_its_instances(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def first(x):
            x.run()
        def second(x):
            x.run()
        first(a)
        first(b)
        second(d)
        D.run = f
        """,
    )

    assert callees(graph, "main.first") == []
    assert callees(graph, "main.second") == ["main.f"]


def test_an_attribute_stored_on_one_instance_reaches_the_loads_of_that_instance(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
        def both(x):
            x.cb()
        def one(x):
            x.cb()
        both(a)
        both(b)
        one(a)
        b.cb = g
        """,
    )

    assert callees(graph, "main.both") == ["main.g"]
    assert callees(graph, "main.one") == []


def test_setattr_on_an_instance_reaches_a_load_that_came_first(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            x.cb()
        use(a)
        use(b)
        setattr(a, "cb", h)
        """,
    )

    assert callees(graph, "main.use") == ["main.h"]


def test_getattr_of_the_class_answers_for_every_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Lazy:
            def __getattr__(self, name):
                return f
        def use(x):
            x.missing()
        use(Lazy())
        use(Lazy())
        """,
    )

    assert callees(graph, "main.use") == ["main.Lazy.__getattr__", "main.f"]


def test_a_special_method_stored_on_the_class_is_called_for_every_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            len(x)
            for item in x:
                pass
        use(a)
        use(b)
        C.__len__ = f
        C.__iter__ = g
        """,
    )

    assert callees(graph, "main.use") == ["<builtin>.len", "main.f", "main.g"]


def test_a_setattr_hook_stored_on_the_class_is_called_for_every_store(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def fill(x):
            x.value = 1
        fill(a)
        fill(b)
        C.__setattr__ = h
        """,
    )

    assert callees(graph, "main.fill") == ["main.h"]


def test_a_property_stored_on_the_class_runs_for_every_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def read(x):
            return x.size
        read(a)
        read(b)
        C.size = property(f)
        """,
    )

    assert callees(graph, "main.read") == ["main.f"]


def test_getattr_answers_no_special_method_and_a_later_one_is_called(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Lazy:
            def __getattr__(self, name):
                return f
        def use(x):
            len(x)
            x.value = 1
        use(Lazy())
        use(Lazy())
        Lazy.__len__ = g
        Lazy.__setattr__ = h
        """,
    )

    assert callees(graph, "main.use") == ["<builtin>.len", "main.g", "main.h"]


def test_a_property_of_a_class_with_getattr_runs_for_every_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Lazy:
            def __getattr__(self, name):
                return f
            @property
            def size(self):
                return g
        def use(x):
            x.size()
            x.other()
        use(Lazy())
        use(Lazy())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Lazy.__getattr__",
        "main.Lazy.size",
        "main.f",
        "main.g",
    ]


UNKNOWN_LATER = """
class A:
    def method(self): pass
class B(A): pass
class C(A): pass
def delay(flag=True):
    return lambda: lambda: lambda: lambda: B if flag else C
base = A
def update():
    global base
    base = delay()()()()()
update()
class Late(base):
    pass
def use(x):
    x.missing()
    x.value = 1
    len(x)
    for item in x:
        item()
    x[0]
    del x.value
use(Late())
use(Late())
"""

GETATTR_ROUNDS = """
def f(): pass
def g(): pass
class Lazy:
    def __getattr__(self, name):
        return f
class Eager:
    def __getattr__(self, name):
        return g
def use(x):
    return x.missing
def call(x):
    use(x)()
for x in (Lazy(), Lazy(), Eager(), Eager()):
    call(x)
"""

STORED_LATER = """
def f(): pass
def g(): pass
class C:
    pass
class D(C):
    def __getitem__(self, index): return f
a, b, d = C(), C(), D()
def use(x):
    x.run()
    x.tool()
    x.size
    len(x)
    for item in x:
        item()
    x.value = 1
    return x.cb
for x in (a, b, d):
    use(x)()
C.run = f
C.tool = staticmethod(g)
C.size = property(g)
C.__len__ = f
C.__setattr__ = g
setattr(a, "cb", g)
b.__dict__["cb"] = f
for name in vars(a):
    getattr(d, name)()
"""

DESCRIPTOR_AND_DATACLASS = """
import dataclasses
def f(): pass
class Named:
    def __set_name__(self, owner, name): pass
    def __get__(self, obj, owner=None): return f
@dataclasses.dataclass
class Point:
    x: int = 0
    named = Named()
def use(p):
    p.x
    p.named()
    p.y = p.x
    return p.y
for p in (Point(), Point()):
    use(p)
"""

SHARED_HOOK_SITE = """
class D:
    x = "ok"
    def __format__(self, spec): return "d"
class C:
    def __getattribute__(self, name): return D()
answer = "{0.x.x}".format(C())
"""

FALLBACK_THEN_METHOD = """
class C:
    def __getattr__(self, name): pass
def length(self): return 1
def later(): return lambda: lambda: length
def use(x):
    len(x)
def other(x):
    len(x)
use(C())
other(C())
c = C()
C.__len__ = later()()()
len(c)
"""

STORE_DECIDED_LATER = """
def f(): pass
def g(): pass
class Field:
    def __get__(self, obj, owner=None): return f
    def __set__(self, obj, value): obj.written()
class Lazy:
    def __get__(self, obj, owner=None): return g
def later(): return lambda: lambda: Field()
class C:
    lazy = Lazy()
    def written(self): pass
class D(C):
    pass
def store(x):
    x.field = g
    x.lazy = f
    x.plain = f
    x.slow = g
    return x.field, x.lazy, x.plain, x.slow
for x in (C(), C(), D()):
    for value in store(x):
        value()
C.field = Field()
D.slow = later()()()
"""

INVARIANT_PROGRAMS = {
    "shared hook site": SHARED_HOOK_SITE,
    "fallback then method": FALLBACK_THEN_METHOD,
    "unknown later": UNKNOWN_LATER,
    "getattr rounds": GETATTR_ROUNDS,
    "stored later": STORED_LATER,
    "descriptor and dataclass": DESCRIPTOR_AND_DATACLASS,
    "store decided later": STORE_DECIDED_LATER,
}


def _at_once(patch):
    from pycg.analysis.hierarchy import Hierarchy
    from pycg.analysis.semantics import Analysis

    def later(self, cls, attr, receiver, after, unless, rule, *args):
        rule(receiver, *args)

    def read_field(self, instance, name, dst):
        self.add_edge(self.field(instance, name), dst)

    patch.setattr(Hierarchy, "later", later)
    patch.setattr(Analysis, "read_field", read_field)


def _document_and_first_rounds(root, source, cap, at_once, monkeypatch):
    from pycg.analysis import solver
    from pycg.analysis.semantics import Analysis

    analyses = []
    rounds = {}
    count = [0]

    def record():
        solver_ = analyses[0].solver
        for node in analyses[0].named_nodes:
            for obj in solver_.objects(node):
                rounds.setdefault((node.label, obj.name), count[0])

    with monkeypatch.context() as patch:
        if at_once:
            _at_once(patch)
        init = Analysis.__init__
        fire = solver.Solver._fire

        def recorded_init(self, *args, **kwargs):
            init(self, *args, **kwargs)
            analyses.append(self)

        def recorded_fire(self):
            record()
            count[0] += 1
            return fire(self)

        patch.setattr(Analysis, "__init__", recorded_init)
        patch.setattr(solver.Solver, "_fire", recorded_fire)
        generator = analysed(root, {"main.py": source}, cap=cap)
        record()
    return dumps(generator.document()), rounds


@pytest.mark.parametrize("cap", [None, 1, 2, 3])
@pytest.mark.parametrize("program", INVARIANT_PROGRAMS)
def test_rules_that_wait_give_what_rules_run_at_once_give_in_every_round(
    tmp_path, monkeypatch, program, cap
):
    source = INVARIANT_PROGRAMS[program]
    waited = _document_and_first_rounds(
        tmp_path / "waited", source, cap, False, monkeypatch
    )
    at_once = _document_and_first_rounds(
        tmp_path / "at once", source, cap, True, monkeypatch
    )

    assert waited[0] == at_once[0]
    assert waited[1] == at_once[1]


@pytest.mark.parametrize("cap", [1, 2])
def test_no_rule_that_waits_sees_an_instance_of_a_class_that_became_unknown(
    tmp_path, monkeypatch, cap
):
    no_rule_sees_what_is_opaque(monkeypatch)
    analysis = analysed(tmp_path, {"main.py": UNKNOWN_LATER}, cap=cap).program.analysis

    (late,) = [cls for cls in analysis.classes if cls.name == "main.Late"]
    assert late.unknown


def test_an_instance_attribute_that_nothing_stores_has_no_node(tmp_path):
    source = """
    class C:
        pass
    def use(x):
        return x.read, x.written, x.set
    c = C()
    use(c)
    c.written = use
    setattr(c, "set", use)
    """
    points_to = analysed(tmp_path, {"main.py": source}).output_points_to()

    assert points_to["main.C@main:6:4.written"] == ["main.use"]
    assert points_to["main.C@main:6:4.set"] == ["main.use"]
    assert "main.C@main:6:4.read" not in points_to
