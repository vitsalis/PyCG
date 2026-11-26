import types

import pytest

from pycg.analysis import solver as solver_module
from pycg.analysis.attributes import Load, _Deliver
from pycg.analysis.hierarchy import _Bind
from pycg.analysis.model import BUILTIN_MODULE, Signature
from pycg.analysis.semantics import Analysis
from pycg.analysis.solver import Constraint, Each, Node, Solver


class Marker:
    def __init__(self, name):
        self.name = name


SATURATED = Marker("<saturated>")


class Recorder(Constraint):
    def __init__(self, result=None):
        self.applied = []
        self.result = result

    def apply(self, obj):
        self.applied.append(obj)

    def results(self):
        return (self.result,)


def names(node, solver):
    if isinstance(solver, Analysis):
        solver = solver.solver
    return [obj.name for obj in solver.objects(node)]


def call_graph(analysis):
    graph = {}
    for (caller, _site, _construct), callees in analysis.site_edges.items():
        graph.setdefault(caller, {}).update(callees)
    return graph


def objects(analysis, node):
    return analysis.solver.objects(node)


def test_each_calls_a_rule_with_its_arguments_and_names_its_results():
    class Rules:
        def __init__(self):
            self.seen = []

        def rule(self, obj, extra):
            self.seen.append((obj, extra))

    rules, plain = Rules(), []
    a, b, result = Marker("a"), 1, Node()
    of_method = Each(rules.rule, "x", results=(result,))
    of_function = Each(lambda obj, extra: plain.append((obj, extra)), "y")
    only_markers = Each(rules.rule, "z", kinds=(Marker,), results=(result, None))
    for each in (of_method, of_function, only_markers):
        each.apply(a)
        each.apply(b)

    assert rules.seen == [(a, "x"), (b, "x"), (a, "z")]
    assert plain == [(a, "y"), (b, "y")]
    assert [each.results() for each in (of_method, of_function, only_markers)] == [
        (result,),
        (),
        (result, None),
    ]
    assert of_method.captured() == ("x",)


def test_each_keeps_no_bound_method_and_no_tuple_of_one_result():
    class Rules:
        def rule(self, obj):
            pass

    each = Each(Rules().rule, results=(Node(),))
    kept = [getattr(each, slot) for slot in Each.__slots__]

    assert not any(
        isinstance(value, (types.MethodType, tuple)) and value for value in kept
    )


def test_objects_propagate_along_edges():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    solver.add_edge(a, b)
    solver.add_edge(b, c)
    solver.add_object(a, Marker("x"))
    solver.solve()

    assert names(c, solver) == ["x"]


def test_one_successor_is_kept_without_a_dict():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    x = Marker("x")

    solver.add_edge(a, b)
    solver.add_edge(a, b)
    assert a.successors is b
    solver.add_object(a, x)
    solver.solve()
    assert a.successors is b and names(b, solver) == ["x"]
    solver.add_edge(a, c)
    solver.add_edge(a, b)
    assert list(a.successors) == [b, c]
    solver.solve()
    assert names(c, solver) == ["x"]
    assert solver.work["edges"] == 2


def test_an_edge_to_a_merged_successor_leads_to_its_representative():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    x, y = Marker("x"), Marker("y")
    solver.add_edge(a, b)
    solver.add_edge(b, c)
    solver.add_edge(c, b)
    solver.add_object(b, x)
    solver.solve()
    assert solver.work["merged"] == 1

    solver.add_object(a, y)
    solver.solve()
    assert names(b, solver) == names(c, solver) == ["x", "y"]


def test_a_cycle_through_one_successor_is_collapsed():
    solver = Solver(SATURATED)
    a, b = Node("a"), Node("b")
    solver.add_edge(a, b)
    solver.add_edge(b, a)
    solver.add_object(a, Marker("x"))
    solver.solve()

    assert solver.work["merged"] == 1
    assert names(a, solver) == names(b, solver) == ["x"]
    solver.add_object(b, Marker("y"))
    solver.solve()
    assert names(a, solver) == ["x", "y"]


def test_new_edge_carries_objects_that_arrived_earlier():
    solver = Solver(SATURATED)
    a, b = Node("a"), Node("b")
    solver.add_object(a, Marker("x"))
    solver.solve()
    solver.add_edge(a, b)
    solver.solve()

    assert names(b, solver) == ["x"]


def test_cycle_terminates_and_shares_all_objects():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    solver.add_edge(a, b)
    solver.add_edge(b, c)
    solver.add_edge(c, a)
    solver.add_object(a, Marker("x"))
    solver.add_object(b, Marker("y"))
    solver.solve()

    for node in (a, b, c):
        assert sorted(names(node, solver)) == ["x", "y"]


def test_constraint_sees_every_object_exactly_once():
    solver = Solver(SATURATED)
    a, b = Node("a"), Node("b")
    solver.add_edge(a, b)
    first, second = Marker("first"), Marker("second")
    solver.add_object(a, first)
    solver.solve()

    recorder = Recorder()
    solver.attach(b, recorder)
    solver.add_object(a, second)
    solver.add_object(a, first)
    solver.solve()

    assert recorder.applied == [first, second]


def test_constraint_attached_before_propagation_sees_objects_once():
    solver = Solver(SATURATED)
    node = Node("a")
    obj = Marker("x")
    solver.add_object(node, obj)
    recorder = Recorder()
    solver.attach(node, recorder)
    solver.solve()

    assert recorder.applied == [obj]


def test_constraint_may_add_objects_to_its_own_node():
    solver = Solver(SATURATED)
    node = Node("x")

    class Grow(Constraint):
        def apply(self, obj):
            if len(obj.name) < 5:
                solver.add_object(node, Marker(obj.name + "a"))

    solver.attach(node, Grow())
    solver.add_object(node, Marker("a"))
    solver.solve()

    assert names(node, solver) == ["a", "aa", "aaa", "aaaa", "aaaaa"]


@pytest.mark.parametrize(
    "order",
    [solver_module.Order(), solver_module.LastInFirstOut()],
    ids=["first in, first out", "last in, first out"],
)
def test_constraints_see_a_node_after_propagation_has_filled_it(order, monkeypatch):
    monkeypatch.setattr(Solver, "order", order)
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    seen = []

    class Snapshot(Constraint):
        def apply(self, obj):
            seen.append(names(c, solver))

    solver.attach(c, Snapshot())
    solver.add_object(c, Marker("y"))
    solver.add_edge(a, b)
    solver.add_edge(b, c)
    solver.add_object(a, Marker("x"))
    solver.solve()

    assert [sorted(snapshot) for snapshot in seen] == [["x", "y"], ["x", "y"]]


def test_points_to_order_does_not_depend_on_object_identity():
    def run():
        solver = Solver(SATURATED)
        sources = [Node(f"s{i}") for i in range(20)]
        sink = Node("sink")
        for i, source in enumerate(sources):
            solver.add_edge(source, sink)
            solver.add_object(source, Marker(f"o{i}"))
        solver.solve()
        return names(sink, solver)

    assert run() == run() == [f"o{i}" for i in range(20)]


def test_objects_include_those_not_yet_propagated():
    solver = Solver(SATURATED)
    a, b = Node("a"), Node("b")
    solver.add_edge(a, b)
    solver.add_object(a, Marker("x"))
    solver.solve()
    solver.add_object(a, Marker("y"))

    assert names(a, solver) == ["x", "y"]
    assert names(b, solver) == ["x"]


def test_holds_agrees_with_objects_in_every_state_of_a_node():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    x, y, z, other = Marker("x"), Marker("y"), Marker("z"), Marker("other")
    solver.add_edge(a, b)
    solver.add_edge(b, a)
    solver.add_object(a, x)
    solver.solve()
    solver.add_object(b, y)
    seen = {}

    class Adds(Constraint):
        def apply(self, obj):
            solver.add_object(c, z)
            seen[obj] = (solver.holds(c, z), solver.holds(c, other))

    solver.add_object(c, x)
    solver.add_object(c, y)
    solver.attach(c, Adds())

    for node in (a, b, c):
        for obj in (x, y, z, other):
            assert solver.holds(node, obj) == (obj in solver.objects(node))
    assert solver.holds(a, y) and not solver.holds(a, other)
    solver.solve()
    assert seen == dict.fromkeys((x, y, z), (True, False))
    for node in (a, b, c):
        for obj in (x, y, z, other):
            assert solver.holds(node, obj) == (obj in solver.objects(node))


def test_a_saturated_node_holds_the_saturated_value_only():
    solver = Solver(SATURATED, cap=1)
    node = Node("node")
    x, y = Marker("x"), Marker("y")
    solver.add_object(node, x)
    solver.add_object(node, y)
    solver.solve()
    solver.add_object(node, Marker("late"))

    assert solver.holds(node, SATURATED)
    assert not solver.holds(node, x)


def test_objects_are_listed_in_the_order_they_first_arrived():
    solver = Solver(SATURATED)
    a, b, sink = Node("a"), Node("b"), Node("sink")
    first, second = Marker("first"), Marker("second")
    solver.add_object(a, first)
    solver.add_object(b, second)
    solver.solve()
    solver.add_edge(b, sink)
    solver.add_edge(a, sink)
    recorder = Recorder()
    solver.attach(sink, recorder)
    solver.solve()

    assert names(sink, solver) == ["first", "second"]
    assert recorder.applied == [first, second]


@pytest.mark.parametrize(
    "size",
    [
        pytest.param(3, id="small set"),
        pytest.param(100, id="set large enough to keep the selection"),
    ],
)
def test_constraints_of_some_kinds_see_those_objects_once_in_order(size):
    class Other(Marker):
        pass

    solver = Solver(SATURATED)
    a, b = Node("a"), Node("b")
    solver.add_edge(a, b)
    objects = [(Other if i % 3 else Marker)(f"o{i}") for i in range(size)]
    late = [Other("late"), Marker("late")]
    seen = {"a": [], "b": [], "all": []}
    for obj in objects:
        solver.add_object(a, obj)
    solver.solve()
    solver.attach(a, Each(seen["a"].append, kinds=(Other,)))
    solver.attach(b, Each(seen["b"].append, kinds=(Other,)))
    solver.attach(b, Each(seen["all"].append))
    for obj in late:
        solver.add_object(a, obj)
    solver.solve()

    others = [obj for obj in objects + late if isinstance(obj, Other)]
    assert seen == {"a": others, "b": others, "all": objects + late}


def test_constant_node_gives_its_object_to_edges_and_constraints_at_once():
    solver = Solver(SATURATED)
    x = Marker("x")
    constant = solver.constant(x)
    target = Node("target")
    solver.add_edge(constant, target)
    recorder = Recorder()
    solver.attach(constant, recorder)
    solver.solve()

    assert names(target, solver) == ["x"]
    assert recorder.applied == [x]
    assert solver.objects(constant) == [x]


def test_constant_node_receives_nothing_else():
    solver = Solver(SATURATED)
    constant = solver.constant(Marker("x"))

    with pytest.raises(ValueError):
        solver.add_object(constant, Marker("y"))
    with pytest.raises(ValueError):
        solver.add_edge(Node("n"), constant)


def cycle(solver, count):
    nodes = [Node(f"n{i}") for i in range(count)]
    for src, dst in zip(nodes, nodes[1:] + nodes[:1]):
        solver.add_edge(src, dst)
    return nodes


ORDERS = {
    "first in, first out": solver_module.Order,
    "last in, first out": solver_module.LastInFirstOut,
    "reversed": solver_module.Reversed,
    "random 1": lambda: solver_module.Shuffled(1),
    "random 2": lambda: solver_module.Shuffled(2),
}


def ring_copied(size):
    solver = Solver(SATURATED, cap=5000)
    nodes = [Node(f"v{i}") for i in range(size)]
    x = Marker("x")
    solver.add_object(nodes[0], x)
    solver.add_object(nodes[1], x)
    solver.solve()
    for i in range(size):
        solver.add_edge(nodes[i], nodes[(i + 1) % size])
    for i in range(2, size):
        solver.add_object(nodes[i], Marker(f"o{i}"))
    solver.solve()
    expected = sorted(["x"] + [f"o{i}" for i in range(2, size)])
    for node in nodes:
        assert sorted(names(node, solver)) == expected
    return solver.work["copied"]


@pytest.mark.parametrize("order", ORDERS)
def test_a_known_cycle_is_collapsed_before_objects_go_round_it(order, monkeypatch):
    monkeypatch.setattr(Solver, "order", ORDERS[order]())
    small, medium, large = (ring_copied(size) for size in (40, 80, 160))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def dense_tail_edge_visits(size, monkeypatch):
    visits = 0
    successors = solver_module._successor_list

    def counted(node):
        nonlocal visits
        found = successors(node)
        visits += len(found)
        return found

    monkeypatch.setattr(solver_module, "_successor_list", counted)
    solver = Solver(SATURATED, cap=5000)
    x = Marker("x")
    tail = [Node(f"t{i}") for i in range(size)]
    for i in range(size):
        solver.add_object(tail[i], x)
        for j in range(i + 1, size):
            solver.add_edge(tail[i], tail[j])
    solver.solve()
    visits = 0
    sources = [Node(f"s{i}") for i in range(size * size)]
    for source in sources:
        solver.add_edge(source, tail[0])
        solver.add_object(source, x)
    solver.solve()
    for node in tail + sources:
        assert names(node, solver) == ["x"]
    return visits


@pytest.mark.parametrize("order", ORDERS)
def test_searches_for_cycles_walk_about_as_many_edges_as_propagation(
    order, monkeypatch
):
    monkeypatch.setattr(Solver, "order", ORDERS[order]())
    for size in (20, 40, 80):
        edges = size * (size - 1) // 2 + size * size
        assert dense_tail_edge_visits(size, monkeypatch) <= 2 * edges


def merged_ring_copied(size):
    solver = Solver(SATURATED, cap=5000)
    nodes = [Node(f"v{i}") for i in range(size)]
    values = [Marker(str(i)) for i in range(size - 1)]
    solver.add_object(nodes[0], values[0])
    for i in range(1, size):
        solver.add_object(nodes[i], values[i - 1])
    solver.solve()
    before = solver.work["copied"]
    for i in range(size):
        solver.add_edge(nodes[i], nodes[(i + 1) % size])
    solver.solve()
    for node in nodes:
        assert sorted(names(node, solver)) == sorted(v.name for v in values)
    return solver.work["copied"] - before


@pytest.mark.parametrize("order", ORDERS)
def test_merging_a_cycle_copies_its_union_once(order, monkeypatch):
    monkeypatch.setattr(Solver, "order", ORDERS[order]())
    small, medium, large = (merged_ring_copied(size) for size in (20, 40, 80))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def test_cycle_is_collapsed_and_every_node_keeps_the_whole_set():
    solver = Solver(SATURATED)
    nodes = cycle(solver, 4)
    solver.add_object(nodes[0], Marker("x"))
    solver.add_object(nodes[2], Marker("y"))
    solver.solve()

    assert solver.work["merged"] == 3
    for node in nodes:
        assert names(node, solver) == ["x", "y"]


def test_each_constraint_of_a_collapsed_cycle_fires_once_per_object():
    solver = Solver(SATURATED)
    a, b, c = nodes = cycle(solver, 3)
    recorders = [Recorder() for _ in nodes]
    for node, recorder in zip(nodes, recorders):
        solver.attach(node, recorder)
    x, y = Marker("x"), Marker("y")
    solver.add_object(a, x)
    solver.add_object(c, y)
    solver.solve()
    late = Recorder()
    solver.attach(b, late)
    z = Marker("z")
    solver.add_object(c, z)
    solver.solve()

    assert solver.work["merged"] == 2
    for recorder in recorders + [late]:
        assert sorted(o.name for o in recorder.applied) == ["x", "y", "z"]


def test_cycle_that_closes_after_objects_arrived_is_collapsed():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    recorders = [Recorder() for _ in range(3)]
    for node, recorder in zip((a, b, c), recorders):
        solver.attach(node, recorder)
    x, y = Marker("x"), Marker("y")
    solver.add_object(a, x)
    solver.add_object(c, y)
    solver.add_edge(a, b)
    solver.add_edge(b, c)
    solver.solve()
    solver.add_edge(c, a)
    solver.solve()

    assert solver.work["merged"] == 2
    for recorder in recorders:
        assert sorted(o.name for o in recorder.applied) == ["x", "y"]


def test_successor_of_a_collapsed_cycle_gets_objects_still_in_flight():
    solver = Solver(SATURATED)
    a, b, c = cycle(solver, 3)
    out = Node("out")
    solver.add_edge(b, out)
    solver.add_object(a, Marker("x"))
    solver.add_object(c, Marker("y"))
    solver.solve()

    assert solver.work["merged"] == 2
    assert names(out, solver) == ["x", "y"]


def test_edge_added_while_a_cycle_is_collapsed_carries_the_whole_set():
    solver = Solver(SATURATED)
    a, b, c = cycle(solver, 3)
    out = Node("out")
    x, y = Marker("x"), Marker("y")

    class AddEdgeOnY(Constraint):
        def apply(self, obj):
            if obj is y:
                solver.add_edge(b, out)

    solver.attach(a, AddEdgeOnY())
    solver.add_object(b, x)
    solver.add_object(c, y)
    solver.solve()

    assert solver.work["merged"] == 2
    assert names(out, solver) == ["x", "y"]


def test_constraint_attached_to_a_collapsed_node_sees_every_object_once():
    solver = Solver(SATURATED)
    a, b = cycle(solver, 2)
    x, y = Marker("x"), Marker("y")
    solver.add_object(a, x)
    solver.solve()
    recorder = Recorder()
    solver.attach(b, recorder)
    solver.add_object(a, y)
    solver.solve()

    assert solver.work["merged"] == 1
    assert recorder.applied == [x, y]


def make_function(analysis, name, positional=(), keyword_only=(), defaults=None):
    signature = Signature(positional=positional, keyword_only=keyword_only)
    return analysis.function(name, "mod", signature, defaults=defaults or {})


def call(analysis, callee, args=(), keywords=(), caller="mod"):
    result = analysis.node()
    analysis.add_call(callee, caller, list(args), list(keywords), result, "mod:1:0")
    return result


def load(analysis, base, attr, dst):
    analysis.add_load(base, attr, dst, "mod", "mod:1:0")


def store(analysis, base, attr, src):
    analysis.add_store(base, attr, src, "mod", "mod:1:0")


def holding(analysis, *objects):
    node = analysis.node()
    for obj in objects:
        analysis.add_object(node, obj)
    return node


def test_load_and_store_on_a_module():
    analysis = Analysis()
    module = analysis.module("mod")
    function = make_function(analysis, "mod.f")
    module_node = holding(analysis, module)
    loaded = analysis.node()
    load(analysis, module_node, "f", loaded)
    store(analysis, module_node, "f", holding(analysis, function))
    analysis.solve()

    assert names(loaded, analysis) == ["mod.f"]


def test_call_binds_arguments_and_returns_result():
    analysis = Analysis()
    target = make_function(analysis, "mod.target")
    f = make_function(analysis, "mod.f", positional=("a", "b"), keyword_only=("k",))
    analysis.add_edge(f.parameters["k"], f.return_node)
    result = call(
        analysis,
        holding(analysis, f),
        args=[None, holding(analysis, target)],
        keywords=[("k", holding(analysis, target))],
    )
    analysis.solve()

    assert names(f.parameters["a"], analysis) == []
    assert names(f.parameters["b"], analysis) == ["mod.target"]
    assert names(result, analysis) == ["mod.target"]
    assert call_graph(analysis) == {"mod": {"mod.f": None}}


def test_a_call_with_extra_or_unknown_arguments_binds_nothing():
    analysis = Analysis()
    f = make_function(analysis, "mod.f", positional=("a",))
    value = holding(analysis, make_function(analysis, "mod.g"))
    call(analysis, holding(analysis, f), args=[value, value])
    call(analysis, holding(analysis, f), args=[value], keywords=[("z", value)])
    analysis.solve()

    assert names(f.parameters["a"], analysis) == []
    assert call_graph(analysis) == {}


def test_defaults_flow_into_their_parameters():
    analysis = Analysis()
    default = holding(analysis, make_function(analysis, "mod.g"))
    f = make_function(analysis, "mod.f", positional=("a",), defaults={"a": default})
    analysis.solve()

    assert names(f.parameters["a"], analysis) == ["mod.g"]


def test_callee_that_arrives_late_is_still_called():
    analysis = Analysis()
    f = make_function(analysis, "mod.f", positional=("a",))
    callee = analysis.node()
    call(analysis, callee, args=[holding(analysis, make_function(analysis, "mod.g"))])
    analysis.solve()
    assert call_graph(analysis) == {}

    analysis.add_edge(holding(analysis, f), callee)
    analysis.solve()

    assert call_graph(analysis) == {"mod": {"mod.f": None}}
    assert names(f.parameters["a"], analysis) == ["mod.g"]


def test_recursive_function_terminates():
    analysis = Analysis()
    f = make_function(analysis, "mod.f", positional=("a",))
    f_node = holding(analysis, f)
    inner = call(analysis, f_node, args=[f.parameters["a"]], caller="mod.f")
    analysis.add_edge(inner, f.return_node)
    analysis.add_edge(f_node, f.return_node)
    outer = call(analysis, f_node, args=[f_node])
    analysis.solve()

    assert names(outer, analysis) == ["mod.f"]
    assert call_graph(analysis) == {"mod": {"mod.f": None}, "mod.f": {"mod.f": None}}


def make_class(analysis, name, defines=(), bases=()):
    return analysis.new_class(name, "mod", defines, list(bases))


def test_instantiation_calls_init_bound_to_a_new_instance_per_site():
    analysis = Analysis()
    cls = make_class(analysis, "mod.C", defines=["__init__"])
    init = make_function(analysis, "mod.C.__init__", positional=("self", "x"))
    analysis.add_object(analysis.field(cls, "__init__"), init)
    cls_node = holding(analysis, cls)
    arg = holding(analysis, make_function(analysis, "mod.g"))
    first = call(analysis, cls_node, args=[arg])
    second = call(analysis, cls_node, args=[arg])
    analysis.solve()

    first, second = objects(analysis, first), objects(analysis, second)
    assert len(first) == len(second) == 1
    assert first != second
    assert objects(analysis, init.parameters["self"]) == first + second
    assert names(init.parameters["x"], analysis) == ["mod.g"]
    assert call_graph(analysis) == {"mod": {"mod.C.__init__": None}}


def test_instance_stored_as_its_own_call_method_terminates():
    analysis = Analysis()
    cls_node = holding(analysis, make_class(analysis, "mod.A"))
    instance = call(analysis, cls_node)
    store(analysis, cls_node, "__call__", instance)
    result = call(analysis, instance)
    analysis.solve()

    assert names(result, analysis) == []


def test_class_stored_as_its_own_init_terminates():
    analysis = Analysis()
    cls = make_class(analysis, "mod.A")
    cls_node = holding(analysis, cls)
    store(analysis, cls_node, "__init__", cls_node)
    result = call(analysis, cls_node)
    analysis.solve()

    assert len(objects(analysis, result)) == 1


def test_class_without_init_is_instantiated_without_a_call_edge():
    analysis = Analysis()
    result = call(analysis, holding(analysis, make_class(analysis, "mod.C")))
    analysis.solve()

    assert len(objects(analysis, result)) == 1
    assert call_graph(analysis) == {}


def test_method_loaded_through_an_instance_is_bound():
    analysis = Analysis()
    cls = make_class(analysis, "mod.C", defines=["m"])
    method = make_function(analysis, "mod.C.m", positional=("self",))
    analysis.add_object(analysis.field(cls, "m"), method)
    instance = call(analysis, holding(analysis, cls))
    loaded = analysis.node()
    load(analysis, instance, "m", loaded)
    call(analysis, loaded)
    analysis.solve()

    receivers = objects(analysis, method.parameters["self"])
    assert receivers == objects(analysis, instance)
    assert call_graph(analysis) == {"mod": {"mod.C.m": None}}


def test_static_method_is_not_bound():
    analysis = Analysis()
    cls = make_class(analysis, "mod.C", defines=["s"])
    function = make_function(analysis, "mod.C.s", positional=("a",))
    staticmethod = holding(
        analysis, analysis.external(f"{BUILTIN_MODULE}.staticmethod")
    )
    wrapped = call(analysis, staticmethod, args=[holding(analysis, function)])
    analysis.add_edge(wrapped, analysis.field(cls, "s"))
    instance = call(analysis, holding(analysis, cls))
    loaded = analysis.node()
    load(analysis, instance, "s", loaded)
    analysis.solve()

    assert names(loaded, analysis) == ["mod.C.s"]


def test_function_loaded_through_its_class_is_not_bound():
    analysis = Analysis()
    cls = make_class(analysis, "mod.C", defines=["m"])
    method = make_function(analysis, "mod.C.m", positional=("self",))
    analysis.add_object(analysis.field(cls, "m"), method)
    loaded = analysis.node()
    load(analysis, holding(analysis, cls), "m", loaded)
    analysis.solve()

    assert names(loaded, analysis) == ["mod.C.m"]


def test_instance_fields_belong_to_their_allocation_site():
    analysis = Analysis()
    cls_node = holding(analysis, make_class(analysis, "mod.C"))
    first, second = call(analysis, cls_node), call(analysis, cls_node)
    store(analysis, first, "f", holding(analysis, make_function(analysis, "mod.f")))
    store(analysis, second, "f", holding(analysis, make_function(analysis, "mod.g")))
    loaded = analysis.node()
    load(analysis, first, "f", loaded)
    analysis.solve()

    assert names(loaded, analysis) == ["mod.f"]


def test_attribute_lookup_follows_the_mro_and_stops_at_the_first_definition():
    analysis = Analysis()
    a = make_class(analysis, "mod.A", defines=["m"])
    b = make_class(analysis, "mod.B", defines=["m"], bases=[holding(analysis, a)])
    c = make_class(analysis, "mod.C", bases=[holding(analysis, b)])
    analysis.add_object(analysis.field(a, "m"), make_function(analysis, "mod.A.m"))
    analysis.add_object(analysis.field(b, "m"), make_function(analysis, "mod.B.m"))
    loaded = analysis.node()
    load(analysis, holding(analysis, c), "m", loaded)
    analysis.solve()

    assert names(loaded, analysis) == ["mod.B.m"]
    assert c.mro == [c, b, a]


def test_lookup_is_redone_when_a_base_arrives_late():
    analysis = Analysis()
    a = make_class(analysis, "mod.A", defines=["m"])
    analysis.add_object(analysis.field(a, "m"), make_function(analysis, "mod.A.m"))
    base = analysis.node()
    b = make_class(analysis, "mod.B", bases=[base])
    loaded = analysis.node()
    load(analysis, holding(analysis, b), "m", loaded)
    analysis.solve()
    assert names(loaded, analysis) == []

    analysis.add_object(base, a)
    analysis.solve()

    assert names(loaded, analysis) == ["mod.A.m"]


def test_late_base_of_a_base_reaches_subclasses():
    analysis = Analysis()
    a = make_class(analysis, "mod.A", defines=["m"])
    analysis.add_object(analysis.field(a, "m"), make_function(analysis, "mod.A.m"))
    base_of_b = analysis.node()
    b = make_class(analysis, "mod.B", bases=[base_of_b])
    c = make_class(analysis, "mod.C", bases=[holding(analysis, b)])
    instance = call(analysis, holding(analysis, c))
    loaded = analysis.node()
    load(analysis, instance, "m", loaded)
    analysis.solve()

    analysis.add_object(base_of_b, a)
    analysis.solve()

    assert c.mro == [c, b, a]
    assert [obj.function.name for obj in objects(analysis, loaded)] == ["mod.A.m"]


def alternative_slots(analysis, count):
    root = make_class(analysis, "mod.Root", defines=["n"])
    analysis.add_object(
        analysis.field(root, "n"), make_function(analysis, "mod.Root.n")
    )
    slots = []
    for i in range(count):
        candidates = []
        for prefix in ("X", "Y"):
            name = f"mod.{prefix}{i}"
            cls = make_class(analysis, name, ["n"], [holding(analysis, root)])
            function = make_function(analysis, f"{name}.n")
            analysis.add_object(analysis.field(cls, "n"), function)
            candidates.append(cls)
        slots.append(holding(analysis, *candidates))
    return slots


def test_lookup_is_the_union_over_alternative_hierarchies():
    analysis = Analysis()
    c = make_class(analysis, "mod.C", bases=alternative_slots(analysis, 2))
    loaded = analysis.node()
    load(analysis, holding(analysis, c), "n", loaded)
    analysis.solve()

    assert sorted(names(loaded, analysis)) == ["mod.X0.n", "mod.Y0.n"]


def test_too_many_alternative_hierarchies_find_every_definition():
    analysis = Analysis()
    c = make_class(analysis, "mod.C", bases=alternative_slots(analysis, 4))
    loaded = analysis.node()
    load(analysis, holding(analysis, c), "n", loaded)
    analysis.solve()

    assert sorted(names(loaded, analysis)) == sorted(
        [f"mod.{p}{i}.n" for p in "XY" for i in range(4)] + ["mod.Root.n"]
    )


def test_cyclic_inheritance_terminates():
    analysis = Analysis()
    a_bases, b_bases = analysis.node(), analysis.node()
    a = make_class(analysis, "mod.A", bases=[a_bases])
    b = make_class(analysis, "mod.B", bases=[b_bases])
    analysis.add_object(a_bases, b)
    analysis.add_object(b_bases, a)
    analysis.add_object(a_bases, a)
    loaded = analysis.node()
    load(analysis, holding(analysis, a, b), "m", loaded)
    analysis.solve()

    assert (a.mros, a.exhaustive) == ([[a, b]], True)
    assert (b.mros, b.exhaustive) == ([[b, a]], True)


def test_inconsistent_hierarchy_does_not_fail():
    analysis = Analysis()
    x = make_class(analysis, "mod.X")
    y = make_class(analysis, "mod.Y")
    xy = make_class(
        analysis, "mod.XY", bases=[holding(analysis, x), holding(analysis, y)]
    )
    yx = make_class(
        analysis, "mod.YX", bases=[holding(analysis, y), holding(analysis, x)]
    )
    z = make_class(
        analysis, "mod.Z", bases=[holding(analysis, xy), holding(analysis, yx)]
    )
    analysis.solve()

    assert z.mro == [z, xy, x, y, yx]


def test_external_attributes_calls_and_results():
    analysis = Analysis()
    module = holding(analysis, analysis.external("ext"))
    cls = analysis.node()
    load(analysis, module, "Cls", cls)
    instance = call(analysis, cls)
    method = analysis.node()
    load(analysis, instance, "method", method)
    call(analysis, method)
    analysis.solve()

    assert names(instance, analysis) == ["<unknown>"]
    assert names(method, analysis) == ["<unknown>"]
    assert call_graph(analysis) == {"mod": {"ext.Cls": None}}
    assert analysis.external_callees == {"ext.Cls": "name"}


def test_loop_over_an_attribute_adds_one_name():
    analysis = Analysis()
    x = holding(analysis, analysis.external("ext"))
    load(analysis, x, "next", x)
    analysis.solve()

    assert names(x, analysis) == ["ext", "ext.next", "<unknown>"]


def chain_of_loads(analysis, start, attrs):
    nodes = []
    for attr in attrs:
        node = analysis.node()
        load(analysis, start, attr, node)
        nodes.append(node)
        start = node
    return nodes


def test_stored_external_is_extended():
    analysis = Analysis()
    path, join = chain_of_loads(
        analysis, holding(analysis, analysis.external("os")), ["path", "join"]
    )
    analysis.solve()

    assert names(join, analysis) == ["os.path.join"]


def test_names_grow_at_most_two_steps_past_their_root():
    analysis = Analysis()
    loads = chain_of_loads(
        analysis, holding(analysis, analysis.external("ext")), ["a", "b", "c"]
    )
    analysis.solve()

    loaded = [names(node, analysis) for node in loads]
    assert loaded == [["ext.a"], ["ext.a.b"], ["<unknown>"]]


def test_imported_module_path_is_a_root():
    analysis = Analysis()
    analysis.add_external_module("ext.sub.mod")
    *_, f = chain_of_loads(
        analysis, holding(analysis, analysis.external("ext")), ["sub", "mod", "f"]
    )
    analysis.solve()

    assert names(f, analysis) == ["ext.sub.mod.f"]


def test_attribute_already_past_the_root_is_not_appended_again():
    analysis = Analysis()
    *_, again = chain_of_loads(
        analysis, holding(analysis, analysis.external("ext")), ["a", "b", "a"]
    )
    analysis.solve()

    assert names(again, analysis) == ["<unknown>"]


def test_loop_over_method_calls_is_bounded():
    analysis = Analysis()
    x = holding(analysis, analysis.external("ext"))
    method = analysis.node()
    load(analysis, x, "next", method)
    analysis.add_edge(call(analysis, method), x)
    analysis.solve()

    assert names(x, analysis) == ["ext", "<unknown>"]
    assert call_graph(analysis) == {"mod": {"ext.next": None}}


def test_attributes_stored_on_externals_are_not_tracked():
    analysis = Analysis()
    ext = holding(analysis, analysis.external("ext"))
    store(analysis, ext, "hook", holding(analysis, make_function(analysis, "mod.f")))
    loaded = analysis.node()
    load(analysis, ext, "hook", loaded)
    analysis.solve()

    assert names(loaded, analysis) == ["ext.hook"]


def test_external_base_class_provides_missing_attributes():
    analysis = Analysis()
    base = analysis.external("ext.Base")
    a = make_class(analysis, "mod.A", bases=[holding(analysis, base)])
    instance = call(analysis, holding(analysis, a))
    method = analysis.node()
    load(analysis, instance, "method", method)
    analysis.solve()

    assert call_graph(analysis) == {"mod": {"ext.Base.__init__": None}}
    assert names(method, analysis) == ["ext.Base.method"]
    assert a.mro == [a, base]


def test_attribute_of_an_external_base_is_one_step_past_the_base():
    analysis = Analysis()
    (base,) = chain_of_loads(
        analysis, holding(analysis, analysis.external("ext")), ["Base"]
    )
    a = make_class(analysis, "mod.A", bases=[base])
    instance = call(analysis, holding(analysis, a))
    attr, b = chain_of_loads(analysis, instance, ["attr", "b"])
    analysis.solve()

    assert names(attr, analysis) == ["ext.Base.attr"]
    assert names(b, analysis) == ["<unknown>"]


def test_builtin_object_base_adds_nothing():
    analysis = Analysis()
    obj = analysis.external(f"{BUILTIN_MODULE}.object")
    a = make_class(analysis, "mod.A", bases=[holding(analysis, obj)])
    call(analysis, holding(analysis, a))
    analysis.solve()

    assert a.mro == [a]
    assert call_graph(analysis) == {}


@pytest.mark.parametrize("name", ["ext", f"{BUILTIN_MODULE}.len"])
def test_externals_are_interned_by_name(name):
    analysis = Analysis()

    assert analysis.external(name) is analysis.external(name)


@pytest.mark.parametrize("builtin", ["dict", "list", "set", "tuple"])
def test_modelled_builtin_called_without_unpacked_arguments(builtin):
    analysis = Analysis()
    callee = holding(analysis, analysis.external(f"{BUILTIN_MODULE}.{builtin}"))
    result = call(analysis, callee)
    analysis.solve()

    assert [obj.kind for obj in objects(analysis, result)] == [builtin]


def test_the_parts_of_the_analysis_define_distinct_methods():
    parts = Analysis.__mro__[1:-1]
    names = [name for part in parts for name in vars(part) if not name.startswith("__")]
    assert len(names) == len(set(names))
    assert not set(names) & set(vars(Analysis))


def test_constant_names_do_not_depend_on_the_unicode_database():
    analysis = Analysis()

    assert analysis.const("a͸é").name == "'a\\u0378\\xe9'"
    assert analysis.const(-3).name == "-3"


def test_constraint_sees_the_objects_it_added_while_it_is_applied():
    solver = Solver(SATURATED)
    trigger, b, out = Node("trigger"), Node("b"), Node("out")

    class CopyBack(Constraint):
        def apply(self, obj):
            solver.add_object(b, obj)
            for value in solver.objects(b):
                solver.add_object(out, value)

    solver.attach(trigger, CopyBack())
    solver.add_object(trigger, Marker("x"))
    solver.add_object(trigger, Marker("y"))
    solver.solve()

    assert names(out, solver) == ["x", "y"]


def test_long_chain_of_attachments_to_constant_nodes_does_not_exhaust_the_stack():
    solver = Solver(SATURATED)
    constants = [solver.constant(Marker(f"c{i}")) for i in range(5000)]
    seen = []

    class Chain(Constraint):
        def __init__(self, index):
            self.index = index

        def apply(self, obj):
            seen.append(self.index)
            if self.index + 1 < len(constants):
                solver.attach(constants[self.index + 1], Chain(self.index + 1))

    solver.attach(constants[0], Chain(0))
    solver.solve()

    assert seen == list(range(5000))


def test_constant_sets_stay_shared_across_a_rebuild_of_the_table(monkeypatch):
    monkeypatch.setattr(solver_module, "_SWEEP_NEW_OBJECTS_MIN", 1)
    solver = Solver(SATURATED)
    x = Marker("x")
    constant = solver.constant(x)
    other = Node("other")
    for name in ("y", "z"):
        solver.add_object(other, Marker(name))
    solver.solve()
    a, b = Node("a"), Node("b")
    solver.add_object(b, x)
    solver.solve()

    class Close(Constraint):
        def apply(self, obj):
            solver.add_edge(b, a)

    solver.add_edge(constant, a)
    solver.add_edge(a, b)
    solver.attach(a, Close())
    solver.solve()

    assert solver.work["merged"] == 1


def test_copying_fields_along_a_long_chain_of_containers_does_not_exhaust_the_stack():
    analysis = Analysis()
    containers = [analysis.container("list", f"mod:{i}:0") for i in range(1200)]
    for source, target in zip(containers, containers[1:]):
        analysis.copy_fields(source, target)
    analysis.element(containers[0], 0)

    assert 0 in containers[-1].fields


def _cache_violations():
    from pycg.analysis.protocols import _Operator
    from pycg.analysis.semantics import Call

    site = "mod:1:0#1:1"

    def iterated(analysis, first, second):
        analysis.iterated(first, "construct", "mod", site)
        analysis.iterated(second, "construct", "mod", site)

    def container(analysis, first, second):
        analysis.container_at("tuple", "origin", site, "rule", 2)
        analysis.container_at("tuple", "origin", site, "rule", 3)

    def spread(analysis, first, second):
        call = Call(analysis, "mod", [], [], None, site, None, [(first, True)])
        copy = Call(analysis, "mod", [], [], None, site, call, [(second, True)])
        analysis._spread(call, "*", first)
        analysis._spread(copy, "*", second)

    def special_method(analysis, first, second):
        call = Call(analysis, "mod", [first], [], None, site)
        copy = Call(analysis, "mod", [second], [], None, site, call)
        analysis._roots[copy] = call
        cls = analysis.new_class("mod.C", "mod", ["__call__"], [])
        analysis.add_object(analysis.field(cls, "__call__"), analysis.external("m.f"))
        analysis.solve()
        instance = analysis.instance(cls, call)
        analysis.call_dunder(instance, "__call__", call, None)
        analysis.call_dunder(instance, "__call__", copy, None)

    def comparison(analysis, first, second):
        operation = _Operator(
            analysis,
            first,
            second,
            "__contains__",
            None,
            False,
            None,
            False,
            "mod",
            site,
        )
        operation.compare_call("value", first)
        operation.compare_call("value", second)

    def site_call(analysis, first, second):
        analysis.site_call("mod", site, ("role",), [first])
        analysis.site_call("mod", site, ("role",), [first, second])

    return [iterated, container, spread, special_method, comparison, site_call]


@pytest.mark.parametrize("ask_twice", _cache_violations(), ids=lambda f: f.__name__)
def test_a_cache_refuses_another_input_under_one_key(ask_twice):
    analysis = Analysis()
    with pytest.raises(AssertionError):
        ask_twice(analysis, analysis.node(), analysis.node())


def test_a_modelled_name_may_be_both_analysed_and_outside():
    analysis = Analysis()
    analysed = analysis.returning_argument("abc.abstractmethod", True)
    outside = analysis.returning_argument("abc.abstractmethod", False)

    assert (analysed.analysed, outside.analysed) == (True, False)


def test_a_node_at_the_cap_keeps_its_objects():
    solver = Solver(SATURATED, cap=2)
    node = Node("node")
    for name in ("x", "y"):
        solver.add_object(node, Marker(name))
    solver.solve()

    assert names(node, solver) == ["x", "y"]


def test_a_node_past_the_cap_holds_the_saturated_value():
    solver = Solver(SATURATED, cap=2)
    a, b, result = Node("a"), Node("b"), Node("result")
    solver.add_edge(a, b)
    recorder = Recorder(result)
    solver.attach(b, recorder)
    for name in ("x", "y", "z"):
        solver.add_object(a, Marker(name))
    solver.solve()

    assert names(a, solver) == ["<saturated>"]
    assert names(b, solver) == ["<saturated>"]
    assert recorder.applied == []
    assert names(result, solver) == ["<saturated>"]


def test_a_constraint_keeps_what_it_saw_in_the_rounds_before_saturation():
    solver = Solver(SATURATED, cap=2)
    node = Node("node")
    recorder = Recorder()
    solver.attach(node, recorder)
    solver.add_object(node, Marker("x"))
    solver.solve()
    for name in ("y", "z"):
        solver.add_object(node, Marker(name))
    solver.solve()

    assert [obj.name for obj in recorder.applied] == ["x"]
    assert names(node, solver) == ["<saturated>"]


def test_a_node_that_receives_the_saturated_value_is_saturated():
    solver = Solver(SATURATED, cap=2)
    a, b = Node("a"), Node("b")
    solver.add_object(b, Marker("x"))
    solver.add_edge(a, b)
    solver.add_object(a, SATURATED)
    solver.solve()
    solver.add_object(b, Marker("y"))
    solver.solve()

    assert names(b, solver) == ["<saturated>"]


def test_a_cycle_whose_union_passes_the_cap_is_saturated():
    solver = Solver(SATURATED, cap=2)
    a, b, result = Node("a"), Node("b"), Node("result")
    recorders = [Recorder(result), Recorder()]
    solver.attach(a, recorders[0])
    solver.attach(b, recorders[1])
    solver.add_object(a, Marker("x"))
    solver.add_object(b, Marker("y"))
    solver.solve()
    solver.add_edge(a, b)
    solver.add_edge(b, a)
    solver.add_object(a, Marker("z"))
    solver.solve()

    assert names(a, solver) == names(b, solver) == ["<saturated>"]
    assert [obj.name for obj in recorders[0].applied] == ["x"]
    assert [obj.name for obj in recorders[1].applied] == ["y"]
    assert names(result, solver) == ["<saturated>"]


def test_a_constraint_that_holds_an_opaque_object_gives_the_saturated_value():
    solver = Solver(SATURATED)
    hidden, shown = Marker("hidden"), Marker("shown")
    node, result, other = Node("node"), Node("result"), Node("other")
    seen = []

    def rule(obj, held):
        seen.append((obj.name, held.name))

    solver.attach(node, Each(rule, hidden, results=(result,)))
    solver.attach(node, Each(rule, shown, results=(other,)))
    solver.opaque = lambda obj: obj is hidden
    solver.add_object(node, Marker("x"))
    solver.solve()

    assert seen == [("x", "shown")]
    assert names(result, solver) == ["<saturated>"]
    assert names(other, solver) == []


@pytest.mark.parametrize("held", ["binding", "delivery"])
def test_a_constraint_that_holds_an_unknown_class_gives_the_saturated_value(held):
    analysis = Analysis(cap=2)
    bases = holding(analysis, *(make_class(analysis, f"mod.{n}") for n in "ABC"))
    unknown = make_class(analysis, "mod.U", bases=[bases])
    found, dst = analysis.node(), analysis.node()
    if held == "binding":
        constraint = _Bind(analysis, unknown, dst, False)
    else:
        constraint = _Deliver(
            analysis, unknown, Load(analysis, "f", dst, "mod", 1), None
        )
    analysis.solver.attach(found, constraint)
    analysis.solve()
    analysis.add_object(found, make_function(analysis, "mod.f"))
    analysis.solve()

    assert names(dst, analysis) == ["<saturated>"]


def test_a_follower_of_a_saturated_node_holds_the_saturated_value():
    solver = Solver(SATURATED, cap=1)
    source = Node("source")
    for name in ("x", "y"):
        solver.add_object(source, Marker(name))
    solver.solve()
    follower = solver.follower(source, solver.phase - 1)
    solver.add_object(source, Marker("z"))
    solver.solve()

    assert names(follower, solver) == ["<saturated>"]


def test_a_constraint_on_opaque_and_plain_objects_sees_the_plain_ones():
    solver = Solver(SATURATED)
    hidden, shown = Marker("hidden"), Marker("shown")
    node, result = Node("node"), Node("result")
    for obj in (hidden, shown):
        solver.add_object(node, obj)
    solver.solve()
    solver.opaque = lambda obj: obj is hidden
    recorder = Recorder(result)
    solver.attach(node, recorder)

    assert recorder.applied == [shown]
    assert names(result, solver) == ["<saturated>"]


def test_a_cycle_that_closes_between_rounds_merges_a_merged_node_once_more():
    solver = Solver(SATURATED)
    a, b, c = Node("a"), Node("b"), Node("c")
    x = Marker("x")
    recorder = Recorder()
    solver.attach(a, recorder)
    solver.add_object(a, x)
    solver.add_edge(a, b)
    solver.add_edge(b, a)
    solver.add_edge(b, c)
    closed = []

    def close():
        if closed:
            return False
        closed.append(True)
        solver.add_edge(c, a)
        return True

    solver.between_rounds = close
    solver.solve()

    assert solver.work["merged"] == 2
    assert recorder.applied == [x]
    assert names(c, solver) == ["x"]
