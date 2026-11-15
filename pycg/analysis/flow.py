"""Local variables by definition: the definitions of each name that reach
each point of a scope.

The builder walks the statements of a scope once, in order, and carries the
`State` of a `Flow`: for each name, the node of the value that the
definitions reaching that point give it, and whether the name may be unbound
there. A definition stores the node of the assigned value itself, so a plain
assignment makes no node. Where paths of control meet (after an `if`, a
loop, a `try`), each name that a path changed gets one join node that the
value of each path flows into. The builder decides which names it follows
this way (see `ModuleScopes.tracked`); the others keep one node.

A state is a set of changes over the state it was forked from, so a branch
copies nothing. A definition is a tuple `(node, unbound, truth, values)`:
`node` is None if the value is not tracked (or there is none), `unbound` is
true if the name may have no value on some path, `truth` says what `bool()`
of the value may give (see `TRUE`), and `values` is the set of the literal
values (see `LITERALS`, `literals_of`) that the name may have, or None if it
may have another value. The design describes the rule in *Local variables by
definition*.

A state also keeps the definitions that class tests give a name in the
branch where they hold (`narrowed`, see narrowing.py): a read sees one for
as long as the definition that the test read still reaches it. Joins, loop
heads, jumps and records take the definitions only, so it never leaves the
branch.
"""

# What `bool()` of a value may give, as bits: a value that may be true, one
# that may be false, either. A definition with no value has neither.
TRUE = 1
FALSE = 2
UNKNOWN = TRUE | FALSE

# The types of the literal values that definitions follow: immutable, and
# compared by value in the same way on every supported Python.
LITERALS = (str, bytes, int, float, bool, type(None))


def literals_of(*values):
    """The set of the literal `values`, each with its type: `True` and `1`
    (or `False`, `0` and `0.0`) are equal and hash alike, but `is` tells
    them apart, so a set of plain values would merge them."""
    return frozenset((type(value), value) for value in values)


def values_of(literals):
    """The values in a set that `literals_of` made."""
    return [value for _, value in literals]


def truth_of(values):
    """What `bool()` of any of the literal `values` may give."""
    truth = 0
    for value in values:
        truth |= TRUE if value else FALSE
    return truth


# The definition of a name that no statement of the scope has bound.
UNBOUND = (None, True, 0, frozenset())


class State:
    """The definitions at one point of a scope, as changes over `parent`.
    `reachable` is false once every path to the point has ended (`return`,
    `raise`, `break`, `continue`). `narrowed` maps a name to the definition
    that a class test read and the definition that it gives the name where
    it holds, or is None."""

    __slots__ = ("parent", "changes", "reachable", "narrowed")

    def __init__(self, parent=None):
        self.parent = parent
        self.changes = {}
        self.reachable = True if parent is None else parent.reachable
        self.narrowed = None

    def get(self, name):
        state = self
        while state is not None:
            definition = state.changes.get(name)
            if definition is not None:
                return definition
            state = state.parent
        return UNBOUND

    def changed(self, base):
        """The names whose definitions may differ from those of `base`, a
        state that this one was forked from, in order."""
        names = {}
        state = self
        while state is not base:
            names.update(dict.fromkeys(state.changes))
            state = state.parent
        return names


class _Loop:
    """A loop being walked: `heads` maps each name that the loop binds to
    the node that holds its value at the start of an iteration, `entry` is
    the state there, and `breaks` the states that `break` leaves with."""

    __slots__ = ("heads", "entry", "breaks")

    def __init__(self, heads, entry):
        self.heads = heads
        self.entry = entry
        self.breaks = []


class Flow:
    """The definitions of the names of one scope, from the start of its
    statements to the point that the builder has reached."""

    def __init__(self, analysis):
        self.analysis = analysis
        self.state = State()
        self._loops = []
        # The `try` statements with a `finally` block whose other blocks are
        # being walked: the number of loops around each, and the jumps that
        # wait for its `finally` block (see `start_finally`).
        self._finals = []
        self._recorders = []

    # Definitions

    def read(self, name):
        """The definition of `name` that a read at the current point gets:
        the one that reaches it, or what the innermost class test of the
        name that read that same definition gives it there."""
        definition = self.state.get(name)
        state = self.state
        while state is not None:
            if state.narrowed is not None and name in state.narrowed:
                tested, narrowed = state.narrowed[name]
                if tested is definition:
                    return narrowed
            state = state.parent
        return definition

    def definition(self, name):
        """The definition of `name` that reaches the current point."""
        return self.state.get(name)

    def narrow(self, name, tested, definition, state=None):
        """In the branch that starts at `state` (by default the current
        one), a read of `name` gets `definition` while `tested` reaches it."""
        state = self.state if state is None else state
        if state.narrowed is None:
            state.narrowed = {}
        state.narrowed[name] = (tested, definition)

    def define(self, name, node, truth=UNKNOWN, values=None):
        """Bind `name` to the value of `node` (None if not tracked), whose
        truth is `truth` and whose literal values are `values`."""
        self._set(name, (node, False, truth, values))

    def unbind(self, name):
        """`del name`, or the end of an `except ... as name` handler."""
        self._set(name, UNBOUND)

    def _set(self, name, definition):
        self.state.changes[name] = definition
        for recorder in self._recorders:
            recorder.setdefault(name, []).append(definition)

    def end_path(self):
        """`return` or `raise`: no path continues from here."""
        self.state.reachable = False

    def join(self, definitions):
        """The definition that holds what any of `definitions` holds."""
        nodes, unbound, truth, values = [], False, 0, frozenset()
        for node, maybe, bits, literals in definitions:
            unbound = unbound or maybe
            truth |= bits
            values = None if values is None or literals is None else values | literals
            if node is not None and node not in nodes:
                nodes.append(node)
        if len(nodes) <= 1:
            return (nodes[0] if nodes else None, unbound, truth, values)
        joined = self.analysis.node()
        for node in nodes:
            self.analysis.add_edge(node, joined)
        return (joined, unbound, truth, values)

    # Paths

    def branch(self, start):
        """Start a path at the state `start`."""
        self.state = State(start)
        return self.state

    def merge(self, base, ends, target=None):
        """Continue from `target` (by default `base`) with the definitions
        that reach the end of any path that is still reachable among `ends`,
        each a state forked from `base`. If none is, the point is not
        reachable, and the definitions of all of them reach it."""
        target = base if target is None else target
        live = [end for end in ends if end.reachable] or ends
        names = {}
        for end in live:
            names.update(end.changed(base))
        changes = {name: self.join([end.get(name) for end in live]) for name in names}
        target.changes.update(changes)
        target.reachable = any(end.reachable for end in ends)
        self.state = target
        if len(live) == 1 and live[0].reachable:
            self._keep_narrowed(base, live[0], target)

    def _keep_narrowed(self, base, end, target):
        """Where only the path that ends at `end` goes on, the class tests
        that hold at its end hold after the join, at `target`: the rest of
        the block after `if not isinstance(x, C): return`."""
        kept = set()
        state = end
        while state is not None and state is not base:
            for name, (tested, definition) in (state.narrowed or {}).items():
                current = target.get(name)
                # The join of one path copies its definition.
                if name not in kept and current == tested:
                    kept.add(name)
                    self.narrow(name, current, definition, target)
            state = state.parent

    # Exceptions

    def record(self):
        """Start recording the definitions made from now on; return the
        record, a dict from name to the definitions in order."""
        recorder = {}
        self._recorders.append(recorder)
        return recorder

    def stop(self, recorder):
        """Stop the last record that started."""
        assert self._recorders[-1] is recorder
        self._recorders.pop()

    def anywhere(self, base, recorder):
        """The state at a point that an exception may leave from: anywhere
        after `base` while `recorder` recorded. Each name has the definition
        of `base` or any that was recorded."""
        state = State(base)
        for name, definitions in recorder.items():
            state.changes[name] = self.join([base.get(name)] + definitions)
        return state

    # Loops

    def start_loop(self, names):
        """Enter a loop that binds `names` (each with whether it may unbind
        it) on its iterations. Each name gets a head node, which the
        definition before the loop and those at the end of each iteration
        flow into, and the iterations read."""
        heads = {}
        for name, unbinds in names.items():
            node, unbound = self.state.get(name)[:2]
            head = self.analysis.node()
            if node is not None:
                self.analysis.add_edge(node, head)
            heads[name] = head
            # The iterations may give the name any value.
            self.state.changes[name] = (head, unbound or unbinds, UNKNOWN, None)
        self._loops.append(_Loop(heads, self.state))

    def next_iteration(self, state=None):
        """The end of an iteration at `state` (by default the current one):
        its definitions flow into the heads of the innermost loop."""
        self._next_iteration(self._loops[-1], self.state if state is None else state)

    def _next_iteration(self, loop, state):
        if not state.reachable:
            return
        for name, head in loop.heads.items():
            node = state.get(name)[0]
            if node is not None and node is not head:
                self.analysis.add_edge(node, head)

    def jump(self, leaves):
        """`break` (if `leaves`) or `continue` in the innermost loop. A
        jump outside a loop is a syntax error; it only ends the path."""
        if self._loops and self.state.reachable:
            heads = self._loops[-1].heads
            self._jump(leaves, {name: self.state.get(name) for name in heads})
        self.end_path()

    def _jump(self, leaves, definitions):
        """A jump with the `definitions` of the names of the innermost loop.
        A `finally` block inside that loop runs first, so the jump waits for
        the innermost one (see `end_finally`)."""
        loop = self._loops[-1]
        if self._finals and self._finals[-1][0] == len(self._loops):
            self._finals[-1][1].append((leaves, definitions))
            return
        state = State(loop.entry)
        state.changes = definitions
        state.reachable = True
        if leaves:
            loop.breaks.append(state)
        else:
            self._next_iteration(loop, state)

    def stop_loop(self):
        """Leave the innermost loop; return the states that its `break`
        statements leave with."""
        return self._loops.pop().breaks

    # `finally`

    def start_finally(self):
        """Enter a `try` statement with a `finally` block: until its block
        starts (see `run_finally`), a jump of a loop around the statement
        waits for the block."""
        self._finals.append((len(self._loops), []))

    def run_finally(self):
        """The `finally` block starts; return the jumps that wait for it."""
        return self._finals.pop()[1]

    def end_finally(self, jumps, start):
        """The `finally` block that started at the state `start` ends at the
        current state. If it ends normally, each of `jumps` goes on, with
        the block's definitions of the names that it binds; if it leaves
        (`return`, `raise`, `break`, `continue`), that replaces them."""
        final = self.state
        if not final.reachable:
            return
        bound = final.changed(start)
        for leaves, definitions in jumps:
            self._jump(
                leaves,
                {
                    name: final.get(name) if name in bound else definition
                    for name, definition in definitions.items()
                },
            )
