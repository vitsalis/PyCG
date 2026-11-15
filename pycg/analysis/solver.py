"""The solver: propagates objects along the assignment graph until nothing
changes.

A node holds a set of objects (its points-to set). A subset edge `src -> dst`
states that every object of `src` is also in `dst`. A constraint attached to
a node is applied once to every object that reaches the node; applying it may
add objects, edges and constraints, but never removes anything, so the solve
is monotone and terminates.

The algorithm is a worklist with difference propagation. Three mechanisms
keep its cost close to the size of the result rather than to the number of
nodes times the size of their sets:

- Difference propagation. A node keeps `done`, the objects that its edges
  have seen, and an inbox of the sets it received since. Processing a node
  removes what it has seen from each received set and sends the new objects
  (the delta) as one set along its edges.

- Shared sets (hash consing). Every set the solver keeps is immutable and
  exists once: a table maps each set's content to its one copy. A node
  refers to a set and an inbox to the sets it received; the union and the
  difference of two sets are computed once and remembered. Many nodes hold
  the same set (all the variables that a generic value reaches) and receive
  the same deltas, and then they share one set and one union per delta.
  When the sets created since the table was last rebuilt hold more objects
  than the sets that survived, the table is rebuilt from the sets that
  nodes hold, so replaced sets do not accumulate.

- Cycle collapsing. The nodes of a cycle of subset edges hold the same set
  at the fixpoint, so they can be one node. When a node's successor already
  holds the same set (with hash consing, the same object), the edge may
  close a cycle (lazy cycle detection; Hardekopf and Lin, PLDI 2007). Such
  edges wait for one search (Tarjan's algorithm) that finds the strongly
  connected components reachable from all their successors and merges each
  into one node, its representative (union-find): before a propagation
  starts, at its fixpoint, and during it once it has walked as many nodes
  and edges as the last search (see `_collapse_cycles`). This cannot
  change a result: at the fixpoint every node of a cycle holds the union
  of their sets, which is what the merged node holds. Each constraint
  still sees each object exactly once: when nodes merge, the successors of
  each node outside the cycle catch up on the objects that the others had
  already seen, and its constraints in the next round.

The solve runs in rounds. A round propagates along the edges until no node
has an inbox; then each node whose set grew applies its constraints to the
objects that are new since it last did (`fired`). What the constraints add
(objects, edges, constraints) waits for the next round's propagation. So a
constraint sees each object of its node once, and when it does, the node
already holds everything that the edges bring it in that round: the
objects whose rules apply in a round are those of the propagation's
fixpoint, whatever order the solver takes nodes in.

A node that would hold more objects than the cap (`cap`, a parameter of
the analysis; None for no cap), or that receives the saturated value, is
saturated: from then on it holds the saturated value only (the solver's
`saturated`), which its successors receive and its constraints see once.
What its constraints did with the objects of earlier rounds stays. Since
those are the objects of fixpoints of propagation, which the cap does not
change the uniqueness of (sets of at most `cap` objects, and the saturated
value above all of them, form a lattice in which propagation is
monotone), the result does not depend on the order.

A constant node holds one object from its creation and never receives
another (the value of a literal or a definition). Its edges and constraints
act at once and are not kept.

Objects are numbered in the order in which they first reach a node.
Constraints see new objects in that order and `objects()` lists them in that
order, so the result does not depend on object identity or hashing. The
order of delivery differs from a naive solver's; the rules of the analysis
must not depend on it (tests/test_order_independence.py).
"""

import random
from collections import deque
from types import MethodType

EMPTY = frozenset()

# The table of sets is rebuilt at the earliest when the sets added since the
# last rebuild hold this many objects.
_MIN_SWEEP = 1 << 20

# The cap of the analysis unless its user gives another (see above): hubs
# of generic code (a parameter that every strategy of a library reaches)
# cost their size times their constraints, and calls through them are
# noise. Only the entry points of the library and the command line read it.
DEFAULT_CAP = 5000

# The objects of a set that a constraint acts on (`Constraint.kinds`) are
# selected once and kept for a set of at least this many objects; for a
# smaller one, looking the selection up costs more than the constraint's own
# test of each object.
_MIN_SELECTION = 32

# Past this many nested `attach` calls, applying a constraint to the objects
# a node already has waits for the solve, so the Python stack is not
# exhausted.
_MAX_NESTING = 50


class Node:
    """A place that holds objects: a variable, a field, a return value or the
    value of an expression. `label` names it in the assignment graph output;
    nodes for intermediate values have none. The other slots belong to the
    solver."""

    __slots__ = (
        "label",
        "rep",
        "done",
        "inbox",
        "successors",
        "constraints",
        "fired",
        "groups",
    )

    def __init__(self, label=None):
        self.label = label
        # The node that this one was merged into, or None.
        self.rep = None
        self.done = EMPTY
        # The sets received since the node was last processed: None, one
        # set, or a dict of sets by id. A node with an inbox is queued.
        self.inbox = None
        # The successors: None; one node, whose edge has not started a
        # search for cycles (most nodes with a successor have one, and a
        # program has millions); or a dict, successor -> whether the edge
        # to it started a search.
        self.successors = None
        self.constraints = None
        # The set that the constraints have been applied to. After a merge,
        # until the next round: the constraints of each merged node with
        # the set that they had been applied to.
        self.fired = EMPTY
        self.groups = None

    def __repr__(self):
        return f"<Node {self.label or id(self)}>"


class Witness(Node):
    """The node of the first lookup of a name on a class through one of its
    instances (see `Hierarchy.later`). The lookups of the same name through
    the other instances of the class get their first object in the same
    round as this one, so the rules that wait for them (`watch`) run when
    the first object or edge is added to it, before it arrives."""

    __slots__ = ("watch",)

    def __init__(self, watch):
        super().__init__()
        self.watch = watch


class Watch:
    """The rules that wait until a class may answer a name: `waiting` maps
    a rule with its arguments to the instances it waits to run for, and is
    None once the rules have run (see `Hierarchy.later`)."""

    __slots__ = ("waiting",)

    def __init__(self):
        self.waiting = {}

    def wake(self):
        waiting, self.waiting = self.waiting, None
        for (rule, *args), receivers in waiting.items():
            for receiver in receivers:
                rule(receiver, *args)


class Constant:
    """A node that holds one object from its creation and never receives
    another: the value of a literal or of a definition. An edge from it
    gives its target the object at once, and a constraint attached to it is
    applied at once; neither is kept. A program has many (pygments: 116k),
    so it keeps only its set; the other parts of a node are always empty."""

    __slots__ = ("done",)
    label = rep = inbox = successors = constraints = fired = groups = None

    def __init__(self, done):
        self.done = done


class Order:
    """The order in which the solver takes nodes from its worklist (first
    in, first out) and visits successors and constraints (as added).

    Results do not depend on it. The subclasses below are a test hook that
    checks this (tests/test_order_independence.py): a test replaces
    `Solver.order`."""

    def take(self, worklist):
        return worklist.popleft()

    def arrange(self, items):
        return items


class LastInFirstOut(Order):
    def take(self, worklist):
        return worklist.pop()


class Reversed(Order):
    def arrange(self, items):
        return items[::-1]


class Shuffled(Order):
    """A random order, the same for the same seed."""

    def __init__(self, seed):
        self.random = random.Random(seed)

    def take(self, worklist):
        worklist.rotate(-self.random.randrange(len(worklist)))
        return worklist.popleft()

    def arrange(self, items):
        items = list(items)
        self.random.shuffle(items)
        return items


class Solver:
    order = Order()

    def __init__(self, saturated, cap=None):
        # The object that a saturated node holds, and its set (below).
        self.saturated = saturated
        # A node that would hold more objects than this is saturated; None
        # for no cap.
        self.cap = cap
        self._worklist = deque()
        # Each object's number, in the order objects first reach a node.
        self._numbers = {}
        # Successors whose edges may close a cycle, found while processing;
        # the nodes and edges that the last search for cycles walked, and
        # the nodes and edges that propagation walked until then (see
        # `_collapse_cycles`).
        self._suspects = []
        self._search_cost = 0
        self._propagated_at_search = 0
        # How many constraint applications are in progress, and the objects
        # that they add, by node (see `_apply`).
        self._applying = 0
        self._added = {}
        # How deeply `attach` calls nest, and the applications it deferred.
        self._nesting = 0
        self._deferred = deque()
        # The nodes whose constraints have objects to see in the next round.
        self._firing = {}
        # Each set's content -> its one copy.
        self._sets = {EMPTY: EMPTY}
        # (id(a), id(b)) -> (a, b, a | b) and (a, b, a - b) for sets of the
        # table. An entry keeps `a` and `b` alive, so their ids are not
        # reused.
        self._unions = {}
        self._differences = {}
        # id(s) -> (s, the objects of s in order), for sets of the table.
        self._orders = {}
        # (id(s), kinds) -> (s, the objects of s of those kinds in order).
        self._kinds = {}
        # Nodes that hold a set, for rebuilding the table.
        self._holders = []
        # The table is rebuilt when the sets added since the last rebuild
        # hold more objects than the sets that survived it.
        self._new_size = 0
        self._sweep_at = _MIN_SWEEP
        # Machine-independent measures of the work done (see `work`).
        self._copied = 0
        self._applied = 0
        self._processed = 0
        # Nodes processed plus the edges along which they sent their delta.
        self._propagated = 0
        self._merged = 0
        self._searched = 0
        self._edges = 0
        self._saturated = self.constant(saturated).done
        # How many times propagation has reached a fixpoint and the rules
        # ran again (see `follower`).
        self.phase = 0
        # The sets of objects that reached saturated nodes, by id (see
        # `absorbed`): empty until a node saturates.
        self.absorbed_sets = {}
        # `between_rounds`, if set, runs when propagation reaches a
        # fixpoint, before the constraints apply, and returns whether it
        # added objects (then propagation goes on). It may set `opaque`, a
        # test of the objects that no rule may see, which constraints then
        # see as the saturated value. Both are fixed while constraints
        # apply.
        self.between_rounds = None
        self.opaque = None

    def revisit(self, function, obj, *args):
        """Call the rule `function(obj, *args)` for an object that a rule
        remembered and comes back to, as constraints are applied: not for
        one that stands for the saturated value (see `opaque`). Every rule
        that comes back to an object goes through here."""
        if not (self.opaque and self.opaque(obj)):
            function(obj, *args)

    def absorbed(self):
        """The objects that reached a saturated node: a call of the
        saturated value may call any of them."""
        found = set()
        for objects in self.absorbed_sets.values():
            found.update(objects)
        found.discard(self.saturated)
        return found

    def _absorb(self, objects):
        if objects and objects is not self._saturated:
            self.absorbed_sets[id(objects)] = objects

    @property
    def work(self):
        """Objects written into new sets (`copied`), constraint applications
        (`applied`), subset edges added (`edges`), nodes processed
        (`processed`), nodes merged into another (`merged`) and nodes and
        edges walked by searches for cycles (`searched`). A set that is
        reused, not built, copies nothing."""
        return {
            "copied": self._copied,
            "applied": self._applied,
            "edges": self._edges,
            "processed": self._processed,
            "merged": self._merged,
            "searched": self._searched,
        }

    def follower(self, src, since):
        """A new node with the edge `src -> node`, in the state that it
        would have if the edge had been added in phase `since` (`phase`)
        and nothing else had touched the node. For a node that nothing
        could see until now: it need not exist, nor receive what `src`
        holds, before something reads it.

        The rules run between propagations, and a propagation ends at its
        fixpoint. In a later phase than `since` the node would hold the set
        of `src` (the same set, or the saturated value with it: it has no
        other source). In the same phase it would still wait for what `src`
        held, which is what `src` holds now."""
        node = Node()
        if src.rep is not None:
            src = _find(src)
        done = src.done
        if since == self.phase or not done:
            self.add_edge(src, node)
            return node
        node.done = done
        self._holders.append(node)
        if type(src) is not Constant:
            self._edges += 1
            if done is not self._saturated:
                self._link(src, node, False)
        return node

    def constant(self, obj):
        """A new node that holds `obj` and nothing else, ever. Its set
        stays in the table of sets."""
        node = Constant(self._singleton(obj))
        self._holders.append(node)
        return node

    def add_object(self, node, obj):
        if type(node) is Witness and node.watch.waiting is not None:
            node.watch.wake()
        if node.rep is not None:
            node = _find(node)
        if obj in node.done:
            return
        if node.done is self._saturated:
            self._absorb(self._singleton(obj))
            return
        if type(node) is Constant:
            raise ValueError("a constant node receives no other object")
        if self._applying:
            if obj not in self._numbers:
                self._numbers[obj] = len(self._numbers)
            self._added.setdefault(node, {})[obj] = None
        else:
            self._receive(node, self._singleton(obj))

    def add_edge(self, src, dst):
        """Add `src -> dst` and send `dst` the objects that `src` has."""
        if type(dst) is Witness and dst.watch.waiting is not None:
            dst.watch.wake()
        if src.rep is not None:
            src = _find(src)
        if dst.rep is not None:
            dst = _find(dst)
        if type(dst) is Constant:
            raise ValueError("a constant node receives no other object")
        if type(src) is Constant:
            self._receive(dst, src.done)
            return
        if src is dst:
            return
        successors = src.successors
        if type(successors) is dict:
            if dst in successors:
                return
        elif successors is dst:
            return
        self._edges += 1
        # The objects in the inbox of `src` travel when it is processed.
        if dst.done is self._saturated:
            self._link(src, dst, False)
            self._absorb(src.done)
            return
        if src.done and src.done is dst.done:
            # As in `_propagate`: the edge may close a cycle. Edges that
            # constraints add, a round after their nodes got the same set,
            # are found here.
            self._link(src, dst, True)
            self._suspects.append(dst)
            return
        self._link(src, dst, False)
        if src.done:
            self._receive(dst, src.done)

    def _link(self, src, dst, searched):
        """Give `src` the successor `dst`, which it does not have; `searched`
        tells whether the edge started a search for cycles."""
        successors = src.successors
        if type(successors) is dict:
            successors[dst] = searched
        elif successors is not None:
            src.successors = {successors: False, dst: searched}
        elif searched:
            src.successors = {dst: True}
        else:
            src.successors = dst

    def attach(self, node, constraint):
        """Attach `constraint` to `node` and apply it at once to the objects
        that `node` holds; the rounds apply it to the objects that arrive
        later. The constraint then sees every object that reaches `node`
        once (see `Constraint`), and what it sees does not depend on when
        the node's other constraints last saw its objects."""
        if node.rep is not None:
            node = _find(node)
        seen = node.done
        if type(node) is Constant:
            pass
        elif node.groups is not None:
            node.groups.append(([constraint], seen))
        elif not node.constraints:
            node.constraints = [constraint]
            node.fired = seen
        elif node.fired is seen:
            node.constraints.append(constraint)
        else:
            # The other constraints have not seen all of `seen` yet.
            node.groups = [(node.constraints, node.fired), ([constraint], seen)]
            node.constraints = None
            self._firing[node] = None
        if not seen:
            return
        if self._nesting >= _MAX_NESTING:
            # A chain of constraints that attach constraints would nest
            # without bound; the solve applies this one later.
            self._deferred.append((constraint, seen))
            return
        self._nesting += 1
        try:
            self._apply([constraint], seen)
        finally:
            self._nesting -= 1

    def objects(self, node):
        """The objects of `node`, in the order they first reached a node,
        including those that the constraints being applied added to it."""
        node = _find(node)
        if node.done is self._saturated:
            return [self.saturated]
        objects = node.done.union(*_received(node), self._added.get(node, ()))
        return sorted(objects, key=self._numbers.__getitem__)

    def holds(self, node, obj):
        """Whether `obj` is one of `objects(node)`, without listing them."""
        node = _find(node)
        if obj in node.done:
            return True
        if node.done is self._saturated:
            return False
        if any(obj in objects for objects in _received(node)):
            return True
        return obj in self._added.get(node, ())

    def solve(self):
        # A propagation starts here, and after each fixpoint.
        starting = True
        while True:
            if self._deferred:
                constraint, objects = self._deferred.popleft()
                self._apply([constraint], objects)
                continue
            if self._new_size > self._sweep_at:
                self._sweep()
            if self._suspects and (
                starting
                or not self._worklist
                or self._propagated - self._propagated_at_search >= self._search_cost
            ):
                # See `_collapse_cycles` for when to search.
                self._collapse_cycles()
                continue
            if not self._worklist:
                # What the rules sent has arrived: they run again.
                self.phase += 1
                if self.between_rounds is not None and self.between_rounds():
                    starting = True
                    continue
                if not self._firing:
                    return
                self._fire()
                starting = True
                continue
            starting = False
            node = self.order.take(self._worklist)
            # A merged node's inbox moved to its representative.
            if node.rep is None and node.inbox is not None:
                self._process(node)

    # Propagation

    def _receive(self, node, objects):
        """Put the set `objects`, from the table, in the inbox of the
        representative `node`. A set is kept once, and not at all if it is
        the node's own set."""
        inbox = node.inbox
        if objects is node.done or objects is inbox:
            return
        if inbox is None:
            node.inbox = objects
            self._worklist.append(node)
        elif type(inbox) is dict:
            inbox[id(objects)] = objects
        else:
            node.inbox = {id(inbox): inbox, id(objects): objects}

    def _process(self, node):
        inbox, node.inbox = node.inbox, None
        done = node.done
        if done is self._saturated:
            for objects in _received_sets(inbox):
                self._absorb(objects)
            return
        if type(inbox) is dict:
            fresh = [self._difference(objects, done) for objects in inbox.values()]
            fresh = [objects for objects in fresh if objects]
            if not fresh:
                return
            if len(fresh) == 1:
                delta = fresh[0]
            else:
                delta = EMPTY.union(*fresh)
                self._copied += len(delta)
                delta = self._intern(delta)
        else:
            delta = self._difference(inbox, done)
            if not delta:
                return
        if not done:
            self._holders.append(node)
        self._processed += 1
        successors = node.successors
        if successors is None:
            self._propagated += 1
        elif type(successors) is dict:
            self._propagated += 1 + len(successors)
        else:
            self._propagated += 2
        cap = self.cap
        if self.saturated in delta or (
            cap is not None and len(done) + len(delta) > cap
        ):
            self._absorb(done)
            self._absorb(delta)
            self._saturate(node)
        else:
            node.done = self._union(done, delta)
            if node.successors:
                self._propagate(node, delta)
        if node.constraints or node.groups:
            self._firing[node] = None

    def _saturate(self, node):
        """Make `node` hold the saturated value only; its successors get it
        now and its constraints in the next round. It never changes again,
        so it keeps no successors."""
        node.done = self._saturated
        successors = _out(node)
        node.successors = None
        for dst, _ in successors:
            target = _find(dst)
            if target is not node:
                self._receive(target, self._saturated)

    def _propagate(self, node, delta):
        successors = node.successors
        if type(successors) is not dict:
            # One successor.
            target = successors if successors.rep is None else _find(successors)
            if target is not successors:
                # It was merged: the edge now leads to its representative.
                if target is node:
                    node.successors = None
                    return
                node.successors = target
            if target.done is self._saturated:
                self._absorb(delta)
            elif target.done is not node.done:
                self._receive(target, delta)
            else:
                # As below: the edge may close a cycle.
                node.successors = {target: True}
                self._suspects.append(target)
            return
        for dst in self.order.arrange(list(successors)):
            target = dst if dst.rep is None else _find(dst)
            if target is not dst:
                # `dst` was merged: the edge now leads to its representative.
                searched = successors.pop(dst)
                if target is node or target in successors:
                    continue
                successors[target] = searched
            if target.done is self._saturated:
                self._absorb(delta)
                continue
            if target.done is not node.done:
                self._receive(target, delta)
            elif not successors[target]:
                # `target` holds the same set: the edge may close a cycle.
                # Each edge starts a search at most once.
                successors[target] = True
                self._suspects.append(target)

    def _fire(self):
        """Apply the constraints of each node whose set grew to the objects
        that are new since they were last applied. What they add waits for
        the propagation of the next round."""
        firing, self._firing = self._firing, {}
        self._applying += 1
        try:
            for node in self.order.arrange(list(firing)):
                self._fire_node(_find(node))
        finally:
            self._applying -= 1
        self._flush()

    def _fire_node(self, node):
        done = node.done
        groups = node.groups
        if groups is None:
            groups = [(node.constraints or (), node.fired)]
        else:
            node.groups = None
            node.constraints = [c for constraints, _ in groups for c in constraints]
        node.fired = done
        # Constraints that this loop attaches to `node` see `done` at once.
        for constraints, fired in groups:
            if constraints and fired is not done:
                new = self._difference(done, fired)
                if new:
                    self._apply(list(constraints), new)

    def _apply(self, constraints, objects):
        """Apply `constraints` to `objects`, in order. The objects that they
        add to a node arrive as one set when all are applied.

        No rule sees the saturated value, nor what stands for it (`opaque`,
        which covers both): neither as an object that a constraint applies
        to, nor as one that the constraint holds (`Constraint.captured`).
        Such a constraint gives the saturated value to its results instead
        (`Constraint.saturate`)."""
        self._applied += len(constraints) * len(objects)
        constraints = self.order.arrange(constraints)
        opaque = self.opaque
        if objects is self._saturated or (opaque and any(map(opaque, objects))):
            for constraint in constraints:
                constraint.saturate(self)
            objects = [obj for obj in objects if opaque and not opaque(obj)]
            if not objects:
                return
            objects = self._intern(frozenset(objects))
        if opaque:
            applied = []
            for constraint in constraints:
                if any(map(opaque, constraint.captured())):
                    constraint.saturate(self)
                else:
                    applied.append(constraint)
            constraints = applied
        if len(objects) == 1:
            # One object: what the constraints add has nothing to collect.
            (obj,) = objects
            for constraint in constraints:
                constraint.apply(obj)
            return
        self._applying += 1
        try:
            ordered = self._ordered(objects)
            select = len(ordered) >= _MIN_SELECTION
            for constraint in constraints:
                kinds = constraint.kinds
                if select and kinds is not None:
                    constraint.apply_each(self._of_kinds(objects, ordered, kinds))
                else:
                    constraint.apply_each(ordered)
        finally:
            self._applying -= 1
        self._flush()

    def _flush(self):
        """Send the objects that the constraints added, as one set per node,
        when no application is in progress."""
        if self._applying or not self._added:
            return
        added, self._added = self._added, {}
        for node, new in added.items():
            objects = self._intern(frozenset(new))
            self._copied += len(objects)
            self._receive(_find(node), objects)

    # Sets

    def _ordered(self, objects):
        """The objects of the set `objects`, from the table, in order. Many
        nodes hold and receive the same sets, so the order is kept."""
        entry = self._orders.get(id(objects))
        if entry is None:
            ordered = sorted(objects, key=self._numbers.__getitem__)
            entry = self._orders[id(objects)] = (objects, ordered)
        return entry[1]

    def _of_kinds(self, objects, ordered, kinds):
        """The objects of the set `objects`, from the table, that are
        instances of `kinds`, in order (`ordered` is the whole set in
        order). Many constraints that act on a few kinds of objects are
        applied to the same large sets (each lookup in a dict reads the
        keys of the dict for the instances among them), so the selection
        is kept."""
        key = (id(objects), kinds)
        entry = self._kinds.get(key)
        if entry is None:
            selected = [obj for obj in ordered if isinstance(obj, kinds)]
            entry = self._kinds[key] = (objects, selected)
        return entry[1]

    def _singleton(self, obj):
        """The set of the one object `obj`."""
        if obj not in self._numbers:
            self._numbers[obj] = len(self._numbers)
        self._copied += 1
        return self._intern(frozenset((obj,)))

    def _intern(self, objects):
        """The one copy of the set `objects`."""
        copy = self._sets.setdefault(objects, objects)
        if copy is objects:
            self._new_size += len(objects)
        return copy

    def _union(self, a, b):
        """The union of the sets `a` and `b`, both from the table."""
        if not a or a is b:
            return b
        if not b:
            return a
        key = (id(a), id(b))
        entry = self._unions.get(key)
        if entry is None:
            union = a | b
            self._copied += len(union)
            entry = self._unions[key] = (a, b, self._intern(union))
        return entry[2]

    def _difference(self, a, b):
        """The objects of `a` that are not in `b`, both sets from the
        table."""
        if not b:
            return a
        key = (id(a), id(b))
        entry = self._differences.get(key)
        if entry is None:
            difference = a - b
            self._copied += len(difference)
            entry = self._differences[key] = (a, b, self._intern(difference))
        return entry[2]

    def _set_done(self, node, objects):
        if not node.done and objects:
            self._holders.append(node)
        node.done = objects

    def _sweep(self):
        """Rebuild the table of sets from the sets that nodes hold, and
        forget the remembered unions."""
        holders = [node for node in self._holders if node.rep is None and node.done]
        sets = {EMPTY: EMPTY}
        for node in holders:
            sets[node.done] = node.done
        for node in self._worklist:
            for objects in _received(node):
                sets[objects] = objects
        self._sets = sets
        self._unions = {}
        self._differences = {}
        self._orders = {}
        self._kinds = {}
        self._holders = holders
        self._new_size = 0
        self._sweep_at = max(sum(map(len, sets)), _MIN_SWEEP)

    # Cycles

    def _collapse_cycles(self):
        """Merge the cycles reachable from the edges that may have closed
        one since the last search, in one search that walks each node and
        each edge at most once. The solve searches when edges are waiting:
        before a propagation starts, so a cycle known by then is one node
        before objects go round it; at its fixpoint; and while it runs, once
        the nodes it has processed since the last search, and the edges
        along which they sent objects, are at least as many as the nodes and
        edges that search walked. So the searches while a propagation runs
        walk at most as many nodes and edges as the propagation did, plus
        the last search. The bound is per propagation: a later round may
        search again a part of the graph that did not change.

        A search per edge as it arrived walked the nodes after a meeting
        point once per path that reached it; a search only at the fixpoint
        let the objects that wait in a known cycle go round it, copied to
        every node; counting only the nodes that a search visits let it
        walk a dense part of the graph after every few processed nodes."""
        starts, self._suspects = self._suspects, []
        components, searched = _cycles(starts)
        self._searched += searched
        self._search_cost = searched
        self._propagated_at_search = self._propagated
        for component in components:
            self._merge(component)

    def _merge(self, members):
        """Merge the nodes `members`, which form a cycle, into the first.

        Each member's successors outside the cycle have seen its `done` set
        and catch up on the rest of the union now (the union minus that set
        is built only for a member that has such a successor; the members
        get the union itself); its constraints keep the set they have
        been applied to and catch up in the next round, so that each sees
        each object once. Edges between members disappear."""
        rep = members[0]
        # Members often hold the same set: each distinct set is used once.
        sets = {id(member.done): member.done for member in members}
        if len(sets) == 1:
            (done,) = sets.values()
        else:
            done = self._intern(EMPTY.union(*sets.values()))
            self._copied += len(done)
        cap = self.cap
        if self.saturated in done or (cap is not None and len(done) > cap):
            self._absorb(done)
            done = self._saturated
        # Only the successors outside the cycle catch up: the members get
        # the whole union.
        inside = set(members)
        extras = {}
        catch_up = []
        for member in members:
            if member.done is done:
                continue
            outside = [dst for dst, _ in _out(member) if _find(dst) not in inside]
            if not outside:
                continue
            extra = extras.get(id(member.done))
            if extra is None:
                if member.done:
                    extra = self._intern(done - member.done)
                    self._copied += len(extra)
                else:
                    extra = done
                extras[id(member.done)] = extra
            catch_up.append((outside, extra))
        inbox = []
        groups = []
        for member in members:
            inbox.extend(_received(member))
            if member.groups:
                groups.extend(member.groups)
            elif member.constraints:
                groups.append((member.constraints, member.fired))
            if member is not rep:
                member.rep = rep
        successors = {}
        for member in members:
            for dst, searched in _out(member):
                target = _find(dst)
                if target is not rep and target not in successors:
                    successors[target] = searched
            if member is not rep:
                member.done = EMPTY
                member.inbox = member.successors = member.constraints = None
                member.groups = None
                member.fired = EMPTY
        self._merged += len(members) - 1
        self._set_done(rep, done)
        rep.successors = None
        for target, searched in successors.items():
            self._link(rep, target, searched)
        rep.constraints = None
        rep.groups = groups or None
        rep.fired = EMPTY
        if groups:
            self._firing[rep] = None
        rep.inbox = None
        for objects in inbox:
            self._receive(rep, objects)
        for successors, extra in catch_up:
            for dst in successors:
                target = _find(dst)
                if target is not rep:
                    self._receive(target, extra)


def _received_sets(inbox):
    """The sets of an inbox."""
    if inbox is None:
        return ()
    return inbox.values() if type(inbox) is dict else (inbox,)


def _received(node):
    """The sets in the inbox of `node`."""
    return _received_sets(node.inbox)


def _find(node):
    """The representative of `node`: the node it was merged into, or
    itself. Shortens the path for later calls."""
    if node.rep is None:
        return node
    root = node.rep
    while root.rep is not None:
        root = root.rep
    while node is not root:
        node.rep, node = root, node.rep
    return root


def _cycles(starts):
    """The strongly connected components of more than one node that are
    reachable from the nodes `starts`, with the number of nodes and edges
    walked (Tarjan's algorithm, without recursion). The first node of each
    component is the one the search reached first."""
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
    edges = 0
    for start in starts:
        start = _find(start)
        if start in index:
            continue
        index[start] = low[start] = len(index)
        stack.append(start)
        on_stack.add(start)
        work = [(start, _successors(start))]
        while work:
            node, successors = work[-1]
            for successor in successors:
                edges += 1
                if successor not in index:
                    index[successor] = low[successor] = len(index)
                    stack.append(successor)
                    on_stack.add(successor)
                    work.append((successor, _successors(successor)))
                    break
                if successor in on_stack:
                    low[node] = min(low[node], index[successor])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member is node:
                            break
                    if len(component) > 1:
                        component.reverse()
                        components.append(component)
    return components, len(index) + edges


def _successors(node):
    return (_find(dst) for dst, _ in _out(node))


def _out(node):
    """The successors of `node`, each with whether the edge to it started a
    search for cycles: pairs that can be counted."""
    successors = node.successors
    if successors is None:
        return ()
    if type(successors) is dict:
        return successors.items()
    return ((successors, False),)


class Constraint:
    """Reacts to each object that reaches the node it is attached to:
    `apply(obj)` handles one object.

    The saturated value never reaches `apply`: when the node saturates,
    `saturate` gives it to the nodes of `results()`, where the constraint
    puts what it finds, and does nothing else. So a rule never asks a
    question about it (is it a class, a constant key, a type?), and takes
    no branch for it. The same holds when an object that the constraint
    holds, `captured()`, stands for it.

    `kinds`, if not None, are the only types of objects that `apply` acts
    on: the solver may leave the other objects out."""

    __slots__ = ()
    kinds = None

    def apply(self, obj):
        raise NotImplementedError

    def apply_each(self, objects):
        """Apply the constraint to each of `objects`, in order: the
        solver's inner loop, which a constraint may write without a call
        of `apply` per object."""
        for obj in objects:
            self.apply(obj)

    def results(self):
        return ()

    def captured(self):
        """The objects that the constraint holds and passes to its rule
        with each object that it applies to."""
        return ()

    def saturate(self, solver):
        for node in self.results():
            if node is not None:
                solver.add_object(node, solver.saturated)


class Each(Constraint):
    """A constraint that calls `function(obj, *args)` for each object that
    reaches its node, or only for those that are instances of `kinds`.
    `results` are the nodes where `function` puts what it finds.

    A program has millions of them. Of a bound method it keeps the function
    and the object (`owner`), not the method that Python makes for each
    use; of one result it keeps the node, not a tuple."""

    __slots__ = ("function", "owner", "args", "kinds", "_results")

    def __init__(self, function, *args, kinds=None, results=()):
        if type(function) is MethodType:
            self.function = function.__func__
            self.owner = function.__self__
        else:
            self.function = function
            self.owner = None
        self.args = args
        self.kinds = kinds
        self._results = results[0] if len(results) == 1 else results

    def results(self):
        results = self._results
        return results if type(results) is tuple else (results,)

    def captured(self):
        return self.args

    def apply(self, obj):
        if self.kinds is None or isinstance(obj, self.kinds):
            if self.owner is None:
                self.function(obj, *self.args)
            else:
                self.function(self.owner, obj, *self.args)

    def apply_each(self, objects):
        function, args, kinds = self.function, self.args, self.kinds
        if self.owner is not None:
            # One bound method for the set, not one for each object.
            function = MethodType(function, self.owner)
        if kinds is None:
            for obj in objects:
                function(obj, *args)
        else:
            for obj in objects:
                if isinstance(obj, kinds):
                    function(obj, *args)
