TRUE = 1
FALSE = 2
UNKNOWN = TRUE | FALSE

LITERAL_TYPES = (str, bytes, int, float, bool, type(None))


def literals_of(*values):
    return frozenset((type(value), value) for value in values)


def values_of(literals):
    return [value for _, value in literals]


def truth_of(values):
    truth = 0
    for value in values:
        truth |= TRUE if value else FALSE
    return truth


UNBOUND = (None, True, 0, frozenset())


class State:
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
        names = {}
        state = self
        while state is not base:
            names.update(dict.fromkeys(state.changes))
            state = state.parent
        return names


class _Loop:
    __slots__ = ("heads", "entry", "breaks")

    def __init__(self, heads, entry):
        self.heads = heads
        self.entry = entry
        self.breaks = []


class Flow:
    def __init__(self, analysis):
        self.analysis = analysis
        self.state = State()
        self._loops = []
        self._pending_finally_blocks = []
        self._recorders = []

    def read(self, name):
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
        return self.state.get(name)

    def narrow(self, name, tested, definition, state=None):
        state = self.state if state is None else state
        if state.narrowed is None:
            state.narrowed = {}
        state.narrowed[name] = (tested, definition)

    def define(self, name, node, truth=UNKNOWN, values=None):
        self._set(name, (node, False, truth, values))

    def unbind(self, name):
        self._set(name, UNBOUND)

    def _set(self, name, definition):
        self.state.changes[name] = definition
        for recorder in self._recorders:
            recorder.setdefault(name, []).append(definition)

    def end_path(self):
        self.state.reachable = False

    def join(self, definitions):
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

    def branch(self, start):
        self.state = State(start)
        return self.state

    def merge(self, base, ends, target=None):
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
        kept = set()
        state = end
        while state is not None and state is not base:
            for name, (tested, definition) in (state.narrowed or {}).items():
                current = target.get(name)
                if name not in kept and current == tested:
                    kept.add(name)
                    self.narrow(name, current, definition, target)
            state = state.parent

    def record(self):
        recorder = {}
        self._recorders.append(recorder)
        return recorder

    def stop(self, recorder):
        assert self._recorders[-1] is recorder
        self._recorders.pop()

    def anywhere(self, base, recorder):
        state = State(base)
        for name, definitions in recorder.items():
            state.changes[name] = self.join([base.get(name)] + definitions)
        return state

    def start_loop(self, names):
        heads = {}
        for name, unbinds in names.items():
            node, unbound = self.state.get(name)[:2]
            head = self.analysis.node()
            if node is not None:
                self.analysis.add_edge(node, head)
            heads[name] = head
            self.state.changes[name] = (head, unbound or unbinds, UNKNOWN, None)
        self._loops.append(_Loop(heads, self.state))

    def next_iteration(self, state=None):
        self._next_iteration(self._loops[-1], self.state if state is None else state)

    def _next_iteration(self, loop, state):
        if not state.reachable:
            return
        for name, head in loop.heads.items():
            node = state.get(name)[0]
            if node is not None and node is not head:
                self.analysis.add_edge(node, head)

    def jump(self, leaves):
        if self._loops and self.state.reachable:
            heads = self._loops[-1].heads
            self._jump(leaves, {name: self.state.get(name) for name in heads})
        self.end_path()

    def _jump(self, leaves, definitions):
        loop = self._loops[-1]
        if self._pending_finally_blocks and self._pending_finally_blocks[-1][0] == len(
            self._loops
        ):
            self._pending_finally_blocks[-1][1].append((leaves, definitions))
            return
        state = State(loop.entry)
        state.changes = definitions
        state.reachable = True
        if leaves:
            loop.breaks.append(state)
        else:
            self._next_iteration(loop, state)

    def stop_loop(self):
        return self._loops.pop().breaks

    def start_finally(self):
        self._pending_finally_blocks.append((len(self._loops), []))

    def run_finally(self):
        return self._pending_finally_blocks.pop()[1]

    def end_finally(self, jumps, start):
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
