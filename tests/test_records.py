import pytest
from programs import analysed, no_rule_sees_what_is_opaque


def _analysis(tmp_path, source):
    return analysed(tmp_path, {"main.py": source}).program.analysis


def _possible(bound):
    return getattr(bound, "_possible", bound._supplied)


def _names(analysis, node):
    return [obj.name for obj in analysis.solver.objects(node)]


def test_equal_sets_of_parameter_names_are_one_object(tmp_path):
    analysis = _analysis(
        tmp_path,
        """
        import re
        values = [3, 1]
        re.compile("a")
        re.compile("b")
        re.compile("c", flags=0)
        sorted(values, key=len)
        sorted(*values)
        """,
    )

    bindings = list(analysis._model_bindings.values())
    sets = [
        names for bound in bindings for names in (bound._supplied, _possible(bound))
    ]
    copies = {}
    for names in sets:
        copies.setdefault(names, set()).add(id(names))
    assert len(bindings) >= 9
    assert {len(ids) for ids in copies.values()} == {1}
    differ = [
        bool(call.star)
        for (call, *_), bound in analysis._model_bindings.items()
        if bound._supplied is not _possible(bound)
    ]
    assert differ and all(differ)


def test_a_binding_tells_what_a_call_supplies(tmp_path):
    analysis = _analysis(
        tmp_path,
        """
        values = [3, 1]
        sorted(values, key=len)
        sorted(*values)
        """,
    )

    given = {
        (bool(call.star), name): (bound.surely(name), bound.given(name))
        for (call, *_), bound in analysis._model_bindings.items()
        if "iterable" in bound
        for name in ("iterable", "key", "reverse")
    }
    assert given == {
        (False, "iterable"): (True, True),
        (False, "key"): (True, True),
        (False, "reverse"): (False, False),
        (True, "iterable"): (False, True),
        (True, "key"): (False, False),
        (True, "reverse"): (False, False),
    }


PLAIN_CALLS = """
import re
def key(x): return x
values = [3, 1]
re.compile("a", flags=0)
sorted(values, key=key)
format(values)
"""


def test_a_plain_call_makes_a_parameter_node_when_a_rule_reads_it(tmp_path):
    generator = analysed(tmp_path, {"main.py": PLAIN_CALLS})
    analysis = generator.program.analysis

    made = {}
    for (call, *_), bound in analysis._model_bindings.items():
        line = int(call.site.split(":")[1])
        made.setdefault(line, set()).update(bound._nodes or ())
    assert made == {5: set(), 6: {"iterable", "key"}, 7: {"value", "format_spec"}}
    assert "main.key" in generator.output()["main"]


def test_a_parameter_node_made_late_holds_what_the_call_binds(tmp_path):
    analysis = _analysis(tmp_path, PLAIN_CALLS)

    bound = {}
    for (call, *rest), binding in analysis._model_bindings.items():
        line = int(call.site.split(":")[1])
        if len(rest) == 1 or line not in bound:
            bound[line] = binding
    holds = [
        _names(analysis, bound[5]["pattern"]),
        _names(analysis, bound[5]["flags"]),
        _names(analysis, bound[7]["format_spec"]),
    ]
    analysis.solve()
    assert holds == [["'a'"], ["0"], ["''"]]
    assert _names(analysis, bound[6]["key"]) == ["main.key"]
    assert _names(analysis, bound[6]["reverse"]) == []
    assert bound[5]["pattern"] is bound[5]["pattern"]
    try:
        bound[5]["no such parameter"]
    except KeyError:
        pass
    else:
        raise AssertionError("a name that the signature does not have")


def test_a_call_that_unpacks_or_passes_twice_is_bound_at_once(tmp_path):
    analysis = _analysis(
        tmp_path,
        """
        import re
        values = [3, 1]
        sorted(values)
        sorted(*values)
        sorted(values, **{})
        re.compile("a", pattern="b")
        print(values)
        """,
    )

    late = {}
    for (call, *_), bound in analysis._model_bindings.items():
        line = int(call.site.split(":")[1])
        late.setdefault(line, set()).add(hasattr(bound, "_nodes"))
    assert late == {4: {True}, 5: {False}, 6: {False}, 7: {False}, 8: {False}}


@pytest.mark.parametrize(
    ("cap", "callees"),
    [
        (None, ["<builtin>.sorted", "main.first", "main.second"]),
        (1, ["<builtin>.sorted"]),
    ],
)
def test_a_call_that_passes_a_keyword_twice_is_bound_at_once(tmp_path, cap, callees):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            def first(x): return x
            def second(x): return x
            sorted([], key=first, key=second)
            """
        },
        cap=cap,
    )

    assert generator.output()["main"] == callees


def test_a_special_method_call_is_attached_once(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Sized:
                def __len__(self): return 1
                def __iter__(self): return iter(())
            def measure(x):
                len(x)
                for item in x: pass
                return len(x)
            measure(Sized()); measure(Sized())
            """
        },
    )
    analysis = generator.program.analysis

    requests = {
        call: (name, unless)
        for (_, name, _, unless), call in analysis._dunder_calls.items()
    }
    attached = [
        (owner, call, *requests[call])
        for call, owners in analysis._dunder_owners.items()
        for owner in (owners if type(owners) is set else (owners,))
    ]
    names = [name for _, _, name, _ in attached]
    assert names.count("__len__") == 4 and names.count("__iter__") == 2
    assert len({call for _, call, name, _ in attached if name == "__len__"}) == 2
    for owner, call, name, unless in attached:
        work = analysis.solver.work
        analysis.call_dunder(owner, name, call, None, unless)
        assert analysis.solver.work == work
    assert generator.output()["main.measure"] == [
        "<builtin>.len",
        "main.Sized.__iter__",
        "main.Sized.__len__",
    ]


def test_the_calls_of_a_class_share_the_set_of_its_instances(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Shape:
                def __init__(self): pass
            class Square(Shape):
                def __new__(cls): return Shape()
                def __init__(self): pass
            def make():
                Shape(); Shape(); Shape()
                Square(); Square()
            make()
            """
        },
    )
    analysis = generator.program.analysis

    classes = {
        call: owner
        for (owner, name, _, _), call in analysis._dunder_calls.items()
        if name == "__new__"
    }
    by_class = {}
    for new, returned in analysis._new_results.items():
        by_class.setdefault(classes[new], []).append(returned)
    seen = {
        len(records): {id(record.instances) for record in records}
        for records in by_class.values()
    }
    assert {count: len(sets) for count, sets in seen.items()} == {4: 1, 2: 1}
    assert generator.output()["main.make"] == [
        "main.Shape.__init__",
        "main.Square.__new__",
    ]


def test_a_call_after_the_instances_of_its_class_saturated_shares_none(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class C:
                def __new__(cls):
                    return object.__new__(cls)
                def __init__(self):
                    pass
            class D(C):
                pass
            class E(C):
                pass
            class K1:
                def next(self): return K2()
            class K2:
                def next(self): return K3()
            class K3:
                def next(self): return C
            class L:
                def d(self): return D
                def e(self): return E
            def early():
                C()
            def middle():
                L().d()()
                L().e()()
            def late():
                K1().next().next().next()()
            early()
            middle()
            late()
            """
        },
        cap=4,
    )
    graph = generator.output()

    assert "main.C.__init__" in graph["main.early"]
    assert "main.C.__init__" not in graph["main.late"]
    assert "main.C.__new__" in graph["main.late"]


def test_the_instances_of_a_class_iterated_at_a_site_share_one_record(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Indexed:
                def __getitem__(self, index): return index
            class Plain:
                pass
            def loop(values):
                for value in values:
                    pass
            loop(Indexed()); loop(Indexed()); loop(Indexed())
            loop(Plain()); loop(Plain())
            """
        },
    )
    analysis = generator.program.analysis

    records = {
        cls.name: sequences for (cls, *_), sequences in analysis._sequences.items()
    }
    assert sorted(records) == ["main.Indexed", "main.Plain"]
    assert len(records["main.Indexed"].objects) == 3
    assert records["main.Indexed"].found and not records["main.Plain"].found
    assert len(records["main.Plain"].objects) == 2
    assert "main.Indexed.__getitem__" in generator.output()["main.loop"]


def test_the_receivers_of_an_accessor_at_a_site_share_one_record(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Getter:
                def __get__(self, instance, owner): return instance
            class Shape:
                described = Getter()
                @property
                def area(self): return 1
            def measure(shape):
                shape.area
                shape.described
            measure(Shape()); measure(Shape()); measure(Shape())
            """
        },
    )
    analysis = generator.program.analysis

    records = list(analysis._accessor_receivers.values())
    assert sorted(len(record.receivers) for record in records) == [3, 3]
    assert {record.width for record in records} == {1, 2}
    hooks = list(analysis._accessor_hooks.values())
    assert len(hooks) == 1
    assert sorted(len(receivers) for receivers in hooks[0].receivers.values()) == [3, 3]
    graph = generator.output()
    assert {"main.Shape.area", "main.Getter.__get__"} <= set(graph["main.measure"])


def test_the_receivers_of_a_stub_method_at_a_site_share_one_call(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            import pathlib
            class Location(pathlib.PurePosixPath):
                pass
            def rename(path):
                return path.with_suffix(".txt")
            first = rename(Location("a"))
            rename(Location("b")); rename(Location("c"))
            """
        },
    )
    analysis = generator.program.analysis

    groups = {
        callee.name: found
        for (_, callee, _, _), found in analysis._bound_groups.items()
    }
    (group,) = groups["pathlib.PurePosixPath.with_suffix"]
    assert len(group.receivers) == 3
    assert generator.output()["main.rename"] == ["pathlib.PurePosixPath.with_suffix"]
    first = generator.output_points_to()["main.first"]
    instances = [name for name in first if name.startswith("main.Location@main")]
    assert len(instances) == 3


def test_each_instance_binds_the_hook_at_every_site_that_it_reaches(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Logged:
                def __setattr__(self, name, value): pass
                def __delattr__(self, name): pass
            class Keeper:
                def put(self, name, value): pass
            class Kept:
                pass
            def paint(shape):
                shape.color = 1
                shape.width = 2
            def erase(shape):
                del shape.color
            first = Logged()
            second = Logged()
            paint(first); paint(second); erase(first)
            keeper = Keeper()
            Kept.__setattr__ = keeper.put
            paint(Kept()); paint(Kept())
            """
        },
    )
    graph = generator.output()
    assert {"main.Logged.__setattr__", "main.Keeper.put"} <= set(graph["main.paint"])
    assert "main.Logged.__delattr__" in graph["main.erase"]
    points_to = generator.output_points_to()
    receivers = points_to["main.Logged.__setattr__.self"]
    assert len(receivers) == 2 and all("main.Logged@" in name for name in receivers)
    assert points_to["main.Keeper.put.self"] == points_to["main.keeper"]


def test_a_site_that_reaches_a_saturated_hook_lookup_calls_no_hook(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class C:
                pass
            def h1(self, name, value): pass
            def h2(self, name, value): pass
            def h3(self, name, value): pass
            C.__setattr__ = h1
            def early(c):
                c.a = 1
            def late(c):
                c.b = 1
            def s1(): return s2
            def s2(): return s3
            def s3(): return (h2, h3)
            for hook in s1()()():
                C.__setattr__ = hook
            def l1(): return l2
            def l2(): return l3
            def l3(): return l4
            def l4(): return l5
            def l5(): return late
            c = C()
            early(c)
            l1()()()()()(c)
            """
        },
        cap=2,
    )

    graph = generator.output()
    assert graph["main.early"] == ["main.h1"]
    assert graph["main.late"] == []


def test_a_hook_whose_class_became_unknown_is_not_called_at_a_later_site(
    tmp_path, monkeypatch
):
    no_rule_sees_what_is_opaque(monkeypatch)
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Caller:
                def __call__(self, name, value): pass
            class Base:
                pass
            Holder = Base
            def b1(): return b2
            def b2(): return b3
            def b3(): return b4
            def b4(): return b5
            def b5(): return (int, str)
            for base in b1()()()()():
                Holder = base
            class Late(Holder, Caller):
                def __call__(self, name, value): pass
            class C:
                pass
            C.__setattr__ = Late()
            def early(c):
                c.a = 1
            def late(c):
                c.b = 1
            def l1(): return l2
            def l2(): return l3
            def l3(): return l4
            def l4(): return l5
            def l5(): return l6
            def l6(): return l7
            def l7(): return l8
            def l8(): return late
            c = C()
            early(c)
            l1()()()()()()()()(c)
            """
        },
        cap=2,
    )

    graph = generator.output()
    assert [cls.name for cls in generator.program.analysis.classes if cls.unknown] == [
        "main.Late"
    ]
    assert graph["main.early"] == ["main.Late.__call__"]
    assert graph["main.late"] == []


def test_the_receivers_of_a_builtins_method_at_a_site_share_one_call(tmp_path):
    generator = analysed(
        tmp_path,
        {
            "main.py": """
            class Table(dict):
                pass
            def walk(table):
                for key in table:
                    key.strip()
                return table.copy()
            first = walk(Table(a=1))
            walk(Table(b=2)); walk(Table(c=3))
            """
        },
    )
    analysis = generator.program.analysis

    groups = {
        callee.name: found
        for (_, callee, _, _), found in analysis._bound_groups.items()
    }
    for name in ("<builtin>.dict.__iter__", "<builtin>.dict.copy"):
        (group,) = groups[name]
        assert len(group.receivers) == 3
    assert generator.output()["main.walk"] == ["<builtin>.dict.copy"]
    assert generator.output_points_to()["main.first"] == ["dict@main:7:11"]
