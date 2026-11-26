import pytest
from programs import analysed


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
    assert all(len(hooks.receivers) == 3 for hooks in analysis._accessor_hooks.values())
    graph = generator.output()
    assert {"main.Shape.area", "main.Getter.__get__"} <= set(graph["main.measure"])
