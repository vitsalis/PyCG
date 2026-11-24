"""The solver against a naive reference on random constraint systems.

The reference keeps a plain set per node, shares nothing and merges
nothing. It solves in the solver's rounds by brute force: copy along every
edge until nothing changes (a node past the cap holds the saturated value),
then apply every constraint to the objects of its node that it has not
seen, and again, until nothing changes. A system has nodes, objects, subset
edges (cycles included) and constraints. A constraint reacts to each object
that reaches its node with actions from a table: add an edge, add an
object, or attach a new constraint. The solver must give every node the
same set as the reference, and apply every constraint exactly once to each
object it sees, whatever order it processes nodes in, also with a cap
small enough that nodes saturate.

A system also has followers: nodes with one edge from a node, which nothing
reads at first. The reference adds the edge at once. The solver makes the
node only when something reads it (`Solver.follower`), and must then give
it the state that the reference's node has.

The rules of class hierarchies read state that depends on the order in
which bases arrive; random hierarchies on the real analysis must give the
same lookups and MROs under every order. The exhaustive order, which stands
for many hierarchies, must find at least what each of them finds.
"""

from contextlib import contextmanager

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pycg.analysis import hierarchy as hierarchy_module
from pycg.analysis import solver as solver_module
from pycg.analysis.model import BUILTIN_MODULE, Signature
from pycg.analysis.semantics import Analysis
from pycg.analysis.solver import Constraint, Node, Solver

pytestmark = pytest.mark.slow

NODES = 8
OBJECTS = 6
KINDS = 3
FOLLOWERS = 2


class Marker:
    def __init__(self, index):
        self.index = index


# What a saturated node holds.
SATURATED = Marker(-1)


class ReferenceSolver:
    """The rounds of the solver by brute force: copy along every edge until
    nothing changes, then apply every constraint to the objects of its node
    that it has not seen, until nothing changes. An object added to a node
    arrives with the next copying; a constraint attached to a node sees at
    once what the node held after the last copying. A node past `cap`
    objects holds the saturated value; None for no cap."""

    def __init__(self, cap=None):
        self.cap = cap
        self.pts = {}
        self.edges = []
        self.constraints = []  # (node, constraint, objects applied)
        self.added = []

    def _cap(self, objects):
        if SATURATED in objects or (self.cap is not None and len(objects) > self.cap):
            return {SATURATED}
        return objects

    def add_object(self, node, obj):
        self.added.append((node, obj))

    def add_edge(self, src, dst):
        self.edges.append((src, dst))

    def attach(self, node, constraint):
        seen = set(self.pts.get(node, ()))
        self.constraints.append((node, constraint, seen))
        for obj in sorted(seen - {SATURATED}, key=lambda o: o.index):
            constraint.apply(obj)

    def solve(self):
        while True:
            added, self.added = self.added, []
            for node, obj in added:
                self.pts[node] = self._cap(self.pts.get(node, set()) | {obj})
            changed = True
            while changed:
                changed = False
                for src, dst in list(self.edges):
                    target = self.pts.get(dst, set())
                    joined = self._cap(target | self.pts.get(src, set()))
                    if joined != target:
                        self.pts[dst] = joined
                        changed = True
            fired = False
            for node, constraint, applied in list(self.constraints):
                new = self.pts.get(node, set()) - applied
                applied |= new
                # A constraint never sees the saturated value.
                new.discard(SATURATED)
                for obj in sorted(new, key=lambda o: o.index):
                    constraint.apply(obj)
                    fired = True
            if not fired and not self.added:
                return

    def objects(self, node):
        return self.pts.get(node, set())

    def constant(self, obj):
        node = object()
        self.pts[node] = {obj}
        return node


class Rule(Constraint):
    """A constraint of kind `kind`. Its actions for each object come from
    `table`; `path` identifies it the same way in every solver. A rule only
    attaches rules of higher kinds, so every system is finite."""

    def __init__(self, system, kind, path):
        self.system = system
        self.kind = kind
        self.path = path
        self.applied = []

    def apply(self, obj):
        self.applied.append(obj)
        system = self.system
        for number, action in enumerate(system.table.get((self.kind, obj.index), ())):
            match action:
                case ("edge", src, dst):
                    system.solver.add_edge(system.nodes[src], system.nodes[dst])
                case ("object", node, index):
                    system.solver.add_object(system.nodes[node], system.objects[index])
                case ("attach", node, kind) if kind > self.kind:
                    rule = Rule(system, kind, (self.path, obj.index, number))
                    system.rules.append((node, rule))
                    system.solver.attach(system.nodes[node], rule)
                case ("follow", slot):
                    system.follow(slot)
                case ("read", slot, kind) if kind > self.kind:
                    path = (self.path, obj.index, number)
                    system.read(slot, Rule(system, kind, path))


class System:
    def __init__(self, solver, spec, make_node):
        self.solver = solver
        self.table = spec["table"]
        self.nodes = [make_node(f"n{i}") for i in range(NODES)]
        self.objects = [Marker(i) for i in range(OBJECTS)]
        self.rules = []
        self.constant_rules = []
        # The followers by slot: the node, for the solver the source and
        # the phase until something reads it; None until `follow`.
        self.late = hasattr(solver, "follower")
        self.make_node = make_node
        self.followers = [None] * FOLLOWERS
        self.read_slots = set()
        self.waiting = {}
        for position, step in enumerate(spec["steps"]):
            match step:
                case ("object", node, index):
                    solver.add_object(self.nodes[node], self.objects[index])
                case ("edge", src, dst):
                    solver.add_edge(self.nodes[src], self.nodes[dst])
                case ("cycle", ring):
                    for src, dst in zip(ring, ring[1:] + ring[:1]):
                        solver.add_edge(self.nodes[src], self.nodes[dst])
                case ("attach", node, kind):
                    rule = Rule(self, kind, ("root", position))
                    self.rules.append((node, rule))
                    solver.attach(self.nodes[node], rule)
                case ("constant", index, dst):
                    constant = solver.constant(self.objects[index])
                    solver.add_edge(constant, self.nodes[dst])
                case ("constant rule", index, kind):
                    constant = solver.constant(self.objects[index])
                    rule = Rule(self, kind, ("root", position))
                    self.constant_rules.append((index, rule))
                    solver.attach(constant, rule)
                case ("follow", slot):
                    self.follow(slot)
                case ("read", slot, kind):
                    self.read(slot, Rule(self, kind, ("root", position)))
                case ("solve",):
                    solver.solve()
        solver.solve()

    def follow(self, slot):
        """Make follower `slot` follow its node, once: the node after
        `slot`. What tried to read it before reads it now, so that the
        order of the actions of a round does not matter."""
        if self.followers[slot] is not None:
            return
        src = self.nodes[slot + 1]
        if self.late:
            self.followers[slot] = (src, self.solver.phase)
        else:
            self.followers[slot] = self.make_node(f"f{slot}")
            self.solver.add_edge(src, self.followers[slot])
        for rule in self.waiting.pop(slot, ()):
            self.read(slot, rule)

    def read(self, slot, rule):
        """Read follower `slot`: attach `rule` to it and send what it holds
        on to node `slot`."""
        if self.followers[slot] is None:
            self.waiting.setdefault(slot, []).append(rule)
            return
        if self.late and slot not in self.read_slots:
            src, since = self.followers[slot]
            self.followers[slot] = self.solver.follower(src, since)
        self.read_slots.add(slot)
        self.rules.append((NODES + slot, rule))
        self.solver.attach(self.followers[slot], rule)
        self.solver.add_edge(self.followers[slot], self.nodes[slot])

    def result(self):
        # A follower that nothing read is not compared: the solver has none.
        nodes = self.nodes + [
            self.followers[slot] if slot in self.read_slots else None
            for slot in range(FOLLOWERS)
        ]
        sets = [
            frozenset(o.index for o in self.solver.objects(node))
            if node is not None
            else frozenset()
            for node in nodes
        ]
        rules = [rule for _, rule in self.rules + self.constant_rules]
        applied = {rule.path: sorted(o.index for o in rule.applied) for rule in rules}
        return sets, applied


node_index = st.integers(0, NODES - 1)
object_index = st.integers(0, OBJECTS - 1)
kind = st.integers(0, KINDS - 1)
slot = st.integers(0, FOLLOWERS - 1)
action = st.one_of(
    st.tuples(st.just("edge"), node_index, node_index),
    st.tuples(st.just("object"), node_index, object_index),
    st.tuples(st.just("attach"), node_index, kind),
    st.tuples(st.just("follow"), slot),
    st.tuples(st.just("read"), slot, kind),
)
step = st.one_of(
    st.tuples(st.just("object"), node_index, object_index),
    st.tuples(st.just("edge"), node_index, node_index),
    st.tuples(st.just("cycle"), st.lists(node_index, min_size=2, max_size=5)),
    st.tuples(st.just("attach"), node_index, kind),
    st.tuples(st.just("constant"), object_index, node_index),
    st.tuples(st.just("constant rule"), object_index, kind),
    st.tuples(st.just("follow"), slot),
    st.tuples(st.just("read"), slot, kind),
    st.just(("solve",)),
)
systems = st.fixed_dictionaries(
    {
        "steps": st.lists(step, max_size=40),
        "table": st.dictionaries(
            st.tuples(kind, object_index), st.lists(action, max_size=3), max_size=12
        ),
    }
)


@contextmanager
def solving_in(order):
    saved = Solver.order
    Solver.order = order
    try:
        yield
    finally:
        Solver.order = saved


ORDERS = {
    "first in, first out": solver_module.Order,
    "last in, first out": solver_module.LastInFirstOut,
    "random": lambda: solver_module.Shuffled(7),
}


@pytest.fixture(
    params=[
        "first in, first out",
        "sweep always",
        "last in, first out",
        "random",
        "small cap, first in, first out",
        "small cap, last in, first out",
        "small cap, random",
    ]
)
def variant(request, monkeypatch):
    """The solver without a cap; with its table of sets rebuilt as often as
    possible; with other processing orders; and with a cap that saturates
    nodes. None may change a result, and with the cap the result is that of
    the reference with the cap. Return a function that makes the order,
    and the cap: each example gets a new order, so that an example replays
    in the same order when hypothesis shrinks it."""
    name = request.param
    if name == "sweep always":
        monkeypatch.setattr(solver_module, "_MIN_SWEEP", 1)
        return solver_module.Order, None
    if name.startswith("small cap, "):
        return ORDERS[name.removeprefix("small cap, ")], 2
    return ORDERS[name], None


# The fixture's state (the sweep threshold) is the same for every example;
# the order is made inside each example.
@settings(
    max_examples=1500,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(spec=systems)
def test_solver_agrees_with_the_naive_reference(spec, variant):
    make_order, cap = variant
    with solving_in(make_order()):
        real = System(Solver(SATURATED, cap), spec, Node)
    reference = System(ReferenceSolver(cap), spec, lambda label: label)
    sets, applied = real.result()
    expected_sets, expected_applied = reference.result()

    assert sets == expected_sets
    assert applied == expected_applied
    # Exactly once: each rule saw each object once, and each object of its
    # node unless the node saturated.
    for node, rule in real.rules:
        seen = sorted(o.index for o in rule.applied)
        assert len(seen) == len(set(seen))
        if sets[node] != {SATURATED.index}:
            assert seen == sorted(sets[node])
    for index, rule in real.constant_rules:
        assert [o.index for o in rule.applied] == [index]


@settings(max_examples=100, deadline=None)
@given(systems)
def test_solver_is_deterministic(spec):
    def run():
        system = System(Solver(SATURATED), spec, Node)
        order = [[o.index for o in system.solver.objects(n)] for n in system.nodes]
        log = [(rule.path, [o.index for o in rule.applied]) for _, rule in system.rules]
        return order, log

    assert run() == run()


# Hierarchies


CLASSES = 4
# Few nodes, so that base expressions often get classes.
BASE_NODES = 4
base_node = st.integers(0, BASE_NODES - 1)

hierarchy_systems = st.fixed_dictionaries(
    {
        # Per class: whether it defines f, g and __getattr__, and its base
        # expressions: nodes, or names of classes defined before it.
        "classes": st.lists(
            st.tuples(
                st.booleans(),
                st.booleans(),
                st.booleans(),
                st.lists(
                    st.one_of(
                        base_node,
                        st.tuples(st.just("name"), st.integers(0, CLASSES - 2)),
                    ),
                    max_size=4,
                ),
            ),
            min_size=1,
            max_size=CLASSES,
        ),
        "steps": st.lists(
            st.one_of(
                # Put a class (or `object`, past the last class) in a node.
                st.tuples(st.just("class"), base_node, st.integers(0, CLASSES)),
                st.tuples(st.just("edge"), base_node, base_node),
                # Look f up on a class, through it or an instance of it;
                # after a class, as super() does; only where no class
                # defines g or __getattr__, as for the special method that
                # Python falls back to.
                st.tuples(
                    st.just("lookup"),
                    st.integers(0, CLASSES - 1),
                    st.booleans(),
                    st.one_of(st.none(), st.integers(0, CLASSES - 1)),
                    st.sampled_from([(), ("g",), ("__getattr__",)]),
                ),
                st.just(("solve",)),
            ),
            min_size=1,
            max_size=20,
        ),
    }
)


def lookups(spec):
    """Build the hierarchy system `spec` on an analysis and return what each
    of its lookups finds, and the MRO of each class. Every class is looked
    up before the steps put classes in base nodes, and the steps add lookups
    at other times."""
    analysis = Analysis()
    nodes = [analysis.node(f"n{i}") for i in range(BASE_NODES)]
    classes = []
    for index, (*defines, bases) in enumerate(spec["classes"]):
        defined = zip(("f", "g", "__getattr__"), defines)
        names = [name for name, defines in defined if defines]
        # A name of a class defined later is no base expression.
        bases = [
            nodes[base]
            if isinstance(base, int)
            else analysis.constant(classes[base[1]])
            for base in bases
            if isinstance(base, int) or base[1] < index
        ]
        cls = analysis.new_class(f"mod.C{index}", "mod", names, bases)
        for name in names:
            signature = Signature(positional=("self",))
            function = analysis.function(f"mod.C{index}.{name}", "mod", signature, {})
            analysis.add_object(analysis.field(cls, name), function)
        classes.append(cls)
    results = []
    for cls in classes:
        results.append(analysis.lookup(cls, "f", cls))
        results.append(analysis.lookup(cls, "f", analysis.abstract_instance(cls)))
    for step in spec["steps"]:
        match step:
            case ("class", node, index):
                if index < len(classes):
                    base = classes[index]
                else:
                    base = analysis.external(f"{BUILTIN_MODULE}.object")
                analysis.add_object(nodes[node], base)
            case ("edge", src, dst):
                analysis.add_edge(nodes[src], nodes[dst])
            case ("lookup", index, through_instance, after, unless):
                if max(index, after or 0) >= len(classes):
                    continue
                cls = classes[index]
                receiver = analysis.abstract_instance(cls) if through_instance else cls
                after = None if after is None else classes[after]
                results.append(analysis.lookup(cls, "f", receiver, after, unless))
            case ("solve",):
                analysis.solve()
    analysis.solve()
    found = [sorted(obj.name for obj in analysis.solver.objects(n)) for n in results]
    return found, [[base.name for base in cls.mro] for cls in classes]


@contextmanager
def at_most_hierarchies(limit):
    saved = hierarchy_module.MAX_HIERARCHIES
    hierarchy_module.MAX_HIERARCHIES = limit
    try:
        yield
    finally:
        hierarchy_module.MAX_HIERARCHIES = saved


@settings(max_examples=500, deadline=None)
@given(hierarchy_systems)
def test_the_exhaustive_order_finds_what_every_hierarchy_would(spec):
    found, _ = lookups(spec)
    # Every class with two hierarchies or more gets the exhaustive order.
    with at_most_hierarchies(1):
        exhaustive, _ = lookups(spec)
    for ordinary, over in zip(found, exhaustive, strict=True):
        assert set(ordinary) <= set(over)


@settings(max_examples=500, deadline=None)
@given(hierarchy_systems)
def test_hierarchies_give_the_same_lookups_under_every_order(spec):
    orders = [
        solver_module.Order(),
        solver_module.LastInFirstOut(),
        solver_module.Reversed(),
        solver_module.Shuffled(1),
        solver_module.Shuffled(2),
    ]
    found = []
    for order in orders:
        with solving_in(order):
            found.append(lookups(spec))
    assert all(result == found[0] for result in found)
