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

    requests = [
        (owner, name, call, unless)
        for (owner, name, _, unless), call in analysis._dunder_calls.items()
    ]
    attached = [name for _, name, call, _ in requests if call.attached]
    assert attached.count("__len__") == 4 and attached.count("__iter__") == 2
    for owner, name, call, unless in requests:
        analysis.call_dunder(owner, name, call, None, unless)
        work = analysis.solver.work
        analysis.call_dunder(owner, name, call, None, unless)
        assert call.attached and analysis.solver.work == work
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
