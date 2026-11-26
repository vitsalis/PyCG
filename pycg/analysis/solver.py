import random
from collections import deque
from types import MethodType

EMPTY = frozenset()

_SWEEP_NEW_OBJECTS_MIN = 1 << 20

DEFAULT_CAP = 5000

_KIND_SELECTION_OBJECTS_MIN = 32

_ATTACH_NESTING_MAX = 50


class Node:
    __slots__ = (
        "label",
        "representative",
        "done",
        "inbox",
        "successors",
        "constraints",
        "fired",
        "constraint_groups",
    )

    def __init__(self, label=None):
        self.label = label
        self.representative = None
        self.done = EMPTY
        self.inbox = None
        self.successors = None
        self.constraints = None
        self.fired = EMPTY
        self.constraint_groups = None

    def __repr__(self):
        return f"<Node {self.label or id(self)}>"


class Witness(Node):
    __slots__ = ("watch",)

    def __init__(self, watch):
        super().__init__()
        self.watch = watch


class Watch:
    __slots__ = ("waiting",)

    def __init__(self):
        self.waiting = []

    def wait(self, rule, receiver):
        self.waiting.append(rule)
        self.waiting.append(receiver)

    def wake(self):
        waiting, self.waiting = self.waiting, None
        receivers_by_rule = {}
        for index in range(0, len(waiting), 2):
            receivers_by_rule.setdefault(waiting[index], []).append(waiting[index + 1])
        for (rule, *args), receivers in receivers_by_rule.items():
            for receiver in receivers:
                rule(receiver, *args)


class Constant:
    __slots__ = ("done",)
    label = representative = inbox = successors = constraints = fired = (
        constraint_groups
    ) = None

    def __init__(self, done):
        self.done = done


class Order:
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
        self.saturated = saturated
        self.cap = cap
        self._worklist = deque()
        self._number_by_object = {}
        self._cycle_suspects = []
        self._last_search_walked = 0
        self._propagated_at_last_search = 0
        self._applications_in_progress = 0
        self._added_by_node = {}
        self._attach_nesting = 0
        self._attach_deferred = deque()
        self._firing_nodes = {}
        self._set_by_content = {EMPTY: EMPTY}
        self._union_by_set_ids = {}
        self._difference_by_set_ids = {}
        self._ordered_by_set_id = {}
        self._selection_by_set_id_and_kinds = {}
        self._set_holders = []
        self._new_sets_object_count = 0
        self._sweep_at_new_objects = _SWEEP_NEW_OBJECTS_MIN
        self._copied = 0
        self._applied = 0
        self._processed = 0
        self._propagated_nodes_and_edges = 0
        self._merged = 0
        self._searched = 0
        self._edges = 0
        self._saturated_set = self.constant(saturated).done
        self.phase = 0
        self.absorbed_sets = {}
        self.between_rounds = None
        self.opaque = None

    def revisit(self, function, obj, *args):
        if not (self.opaque and self.opaque(obj)):
            function(obj, *args)

    def absorbed(self):
        found = set()
        for objects in self.absorbed_sets.values():
            found.update(objects)
        found.discard(self.saturated)
        return found

    def _absorb(self, objects):
        if objects and objects is not self._saturated_set:
            self.absorbed_sets[id(objects)] = objects

    @property
    def work(self):
        return {
            "copied": self._copied,
            "applied": self._applied,
            "edges": self._edges,
            "processed": self._processed,
            "merged": self._merged,
            "searched": self._searched,
        }

    def follower(self, src, since):
        node = Node()
        if src.representative is not None:
            src = _find_representative(src)
        done = src.done
        if since == self.phase or not done:
            self.add_edge(src, node)
            return node
        node.done = done
        self._set_holders.append(node)
        if type(src) is not Constant:
            self._edges += 1
            if done is not self._saturated_set:
                self._link(src, node, False)
        return node

    def constant(self, obj):
        node = Constant(self._singleton(obj))
        self._set_holders.append(node)
        return node

    def add_object(self, node, obj):
        if type(node) is Witness and node.watch.waiting is not None:
            node.watch.wake()
        if node.representative is not None:
            node = _find_representative(node)
        if obj in node.done:
            return
        if node.done is self._saturated_set:
            self._absorb(self._singleton(obj))
            return
        if type(node) is Constant:
            raise ValueError("a constant node receives no other object")
        if self._applications_in_progress:
            if obj not in self._number_by_object:
                self._number_by_object[obj] = len(self._number_by_object)
            self._added_by_node.setdefault(node, {})[obj] = None
        else:
            self._receive(node, self._singleton(obj))

    def add_edge(self, src, dst):
        if type(dst) is Witness and dst.watch.waiting is not None:
            dst.watch.wake()
        if src.representative is not None:
            src = _find_representative(src)
        if dst.representative is not None:
            dst = _find_representative(dst)
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
        if dst.done is self._saturated_set:
            self._link(src, dst, False)
            self._absorb(src.done)
            return
        if src.done and src.done is dst.done:
            self._link(src, dst, True)
            self._cycle_suspects.append(dst)
            return
        self._link(src, dst, False)
        if src.done:
            self._receive(dst, src.done)

    def _link(self, src, dst, searched):
        successors = src.successors
        assert successors is not dst
        assert type(successors) is not dict or dst not in successors
        if type(successors) is dict:
            successors[dst] = searched
        elif successors is not None:
            src.successors = {successors: False, dst: searched}
        elif searched:
            src.successors = {dst: True}
        else:
            src.successors = dst

    def attach(self, node, constraint):
        if node.representative is not None:
            node = _find_representative(node)
        seen = node.done
        if type(node) is Constant:
            pass
        elif node.constraint_groups is not None:
            node.constraint_groups.append(([constraint], seen))
        elif not node.constraints:
            node.constraints = [constraint]
            node.fired = seen
        elif node.fired is seen:
            node.constraints.append(constraint)
        else:
            node.constraint_groups = [
                (node.constraints, node.fired),
                ([constraint], seen),
            ]
            node.constraints = None
            self._firing_nodes[node] = None
        if not seen:
            return
        if self._attach_nesting >= _ATTACH_NESTING_MAX:
            self._attach_deferred.append((constraint, seen))
            return
        self._attach_nesting += 1
        try:
            self._apply([constraint], seen)
        finally:
            self._attach_nesting -= 1

    def apply_now(self, node, constraint):
        if node.representative is not None:
            node = _find_representative(node)
        seen = node.done
        if not seen:
            return
        if self._attach_nesting >= _ATTACH_NESTING_MAX:
            self._attach_deferred.append((constraint, seen))
            return
        self._attach_nesting += 1
        try:
            self._apply([constraint], seen)
        finally:
            self._attach_nesting -= 1

    def objects(self, node):
        node = _find_representative(node)
        done = node.done
        if done is self._saturated_set:
            return [self.saturated]
        added = self._added_by_node.get(node)
        if node.inbox is None and added is None:
            return list(self._ordered(done)) if done else []
        objects = done.union(*_received(node), added or ())
        return sorted(objects, key=self._number_by_object.__getitem__)

    def is_saturated(self, node):
        return _find_representative(node).done is self._saturated_set

    def holds(self, node, obj):
        node = _find_representative(node)
        if obj in node.done:
            return True
        if node.done is self._saturated_set:
            return False
        if any(obj in objects for objects in _received(node)):
            return True
        return obj in self._added_by_node.get(node, ())

    def solve(self):
        starting = True
        while True:
            if self._attach_deferred:
                constraint, objects = self._attach_deferred.popleft()
                self._apply([constraint], objects)
                continue
            if self._new_sets_object_count > self._sweep_at_new_objects:
                self._sweep()
            if self._cycle_suspects and (
                starting
                or not self._worklist
                or self._propagated_nodes_and_edges - self._propagated_at_last_search
                >= self._last_search_walked
            ):
                self._collapse_cycles()
                continue
            if not self._worklist:
                self.phase += 1
                if self.between_rounds is not None and self.between_rounds():
                    starting = True
                    continue
                if not self._firing_nodes:
                    return
                self._fire()
                starting = True
                continue
            starting = False
            node = self.order.take(self._worklist)
            if node.representative is None and node.inbox is not None:
                self._process(node)

    def _receive(self, node, objects):
        assert node.representative is None
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
        if done is self._saturated_set:
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
            self._set_holders.append(node)
        self._processed += 1
        successors = node.successors
        if successors is None:
            self._propagated_nodes_and_edges += 1
        elif type(successors) is dict:
            self._propagated_nodes_and_edges += 1 + len(successors)
        else:
            self._propagated_nodes_and_edges += 2
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
        if node.constraints or node.constraint_groups:
            self._firing_nodes[node] = None

    def _saturate(self, node):
        node.done = self._saturated_set
        successors = _successors_with_searched(node)
        node.successors = None
        for dst, _ in successors:
            target = _find_representative(dst)
            if target is not node:
                self._receive(target, self._saturated_set)

    def _propagate(self, node, delta):
        successors = node.successors
        if type(successors) is not dict:
            target = (
                successors
                if successors.representative is None
                else _find_representative(successors)
            )
            if target is not successors:
                if target is node:
                    node.successors = None
                    return
                node.successors = target
            if target.done is self._saturated_set:
                self._absorb(delta)
            elif target.done is not node.done:
                self._receive(target, delta)
            else:
                node.successors = {target: True}
                self._cycle_suspects.append(target)
            return
        for dst in self.order.arrange(list(successors)):
            target = dst if dst.representative is None else _find_representative(dst)
            if target is not dst:
                searched = successors.pop(dst)
                if target is node or target in successors:
                    continue
                successors[target] = searched
            if target.done is self._saturated_set:
                self._absorb(delta)
                continue
            if target.done is not node.done:
                self._receive(target, delta)
            elif not successors[target]:
                successors[target] = True
                self._cycle_suspects.append(target)

    def _fire(self):
        firing, self._firing_nodes = self._firing_nodes, {}
        self._applications_in_progress += 1
        try:
            for node in self.order.arrange(list(firing)):
                self._fire_node(_find_representative(node))
        finally:
            self._applications_in_progress -= 1
        self._flush()

    def _fire_node(self, node):
        done = node.done
        constraint_groups = node.constraint_groups
        if constraint_groups is None:
            constraint_groups = [(node.constraints or (), node.fired)]
        else:
            node.constraint_groups = None
            node.constraints = [
                c for constraints, _ in constraint_groups for c in constraints
            ]
        node.fired = done
        for constraints, fired in constraint_groups:
            if constraints and fired is not done:
                new = self._difference(done, fired)
                if new:
                    self._apply(list(constraints), new)

    def _apply(self, constraints, objects):
        self._applied += len(constraints) * len(objects)
        constraints = self.order.arrange(constraints)
        opaque = self.opaque
        if objects is self._saturated_set or (opaque and any(map(opaque, objects))):
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
            (obj,) = objects
            for constraint in constraints:
                constraint.apply(obj)
            return
        self._applications_in_progress += 1
        try:
            ordered = self._ordered(objects)
            select = len(ordered) >= _KIND_SELECTION_OBJECTS_MIN
            for constraint in constraints:
                kinds = constraint.kinds
                if select and kinds is not None:
                    constraint.apply_each(self._of_kinds(objects, ordered, kinds))
                else:
                    constraint.apply_each(ordered)
        finally:
            self._applications_in_progress -= 1
        self._flush()

    def _flush(self):
        if self._applications_in_progress or not self._added_by_node:
            return
        added, self._added_by_node = self._added_by_node, {}
        for node, new in added.items():
            objects = self._intern(frozenset(new))
            self._copied += len(objects)
            self._receive(_find_representative(node), objects)

    def _ordered(self, objects):
        entry = self._ordered_by_set_id.get(id(objects))
        if entry is None:
            ordered = sorted(objects, key=self._number_by_object.__getitem__)
            entry = self._ordered_by_set_id[id(objects)] = (objects, ordered)
        return entry[1]

    def _of_kinds(self, objects, ordered, kinds):
        key = (id(objects), kinds)
        entry = self._selection_by_set_id_and_kinds.get(key)
        if entry is None:
            selected = [obj for obj in ordered if isinstance(obj, kinds)]
            entry = self._selection_by_set_id_and_kinds[key] = (objects, selected)
        return entry[1]

    def _singleton(self, obj):
        if obj not in self._number_by_object:
            self._number_by_object[obj] = len(self._number_by_object)
        self._copied += 1
        return self._intern(frozenset((obj,)))

    def _intern(self, objects):
        copy = self._set_by_content.setdefault(objects, objects)
        if copy is objects:
            self._new_sets_object_count += len(objects)
        return copy

    def _union(self, a, b):
        if not a or a is b:
            return b
        if not b:
            return a
        key = (id(a), id(b))
        entry = self._union_by_set_ids.get(key)
        if entry is None:
            union = a | b
            self._copied += len(union)
            entry = self._union_by_set_ids[key] = (a, b, self._intern(union))
        return entry[2]

    def _difference(self, a, b):
        if not b:
            return a
        key = (id(a), id(b))
        entry = self._difference_by_set_ids.get(key)
        if entry is None:
            difference = a - b
            self._copied += len(difference)
            entry = self._difference_by_set_ids[key] = (a, b, self._intern(difference))
        return entry[2]

    def _set_done(self, node, objects):
        if not node.done and objects:
            self._set_holders.append(node)
        node.done = objects

    def _sweep(self):
        holders = [
            node
            for node in self._set_holders
            if node.representative is None and node.done
        ]
        sets = {EMPTY: EMPTY}
        for node in holders:
            sets[node.done] = node.done
        for node in self._worklist:
            for objects in _received(node):
                sets[objects] = objects
        self._set_by_content = sets
        self._union_by_set_ids = {}
        self._difference_by_set_ids = {}
        self._ordered_by_set_id = {}
        self._selection_by_set_id_and_kinds = {}
        self._set_holders = holders
        self._new_sets_object_count = 0
        self._sweep_at_new_objects = max(sum(map(len, sets)), _SWEEP_NEW_OBJECTS_MIN)

    def _collapse_cycles(self):
        starts, self._cycle_suspects = self._cycle_suspects, []
        components, searched = _cycle_components(starts)
        self._searched += searched
        self._last_search_walked = searched
        self._propagated_at_last_search = self._propagated_nodes_and_edges
        for component in components:
            self._merge(component)

    def _merge(self, members):
        assert len(members) > 1
        representative = members[0]
        sets = {id(member.done): member.done for member in members}
        if len(sets) == 1:
            (done,) = sets.values()
        else:
            done = self._intern(EMPTY.union(*sets.values()))
            self._copied += len(done)
        cap = self.cap
        if self.saturated in done or (cap is not None and len(done) > cap):
            self._absorb(done)
            done = self._saturated_set
        inside = set(members)
        extras = {}
        catch_up = []
        for member in members:
            if member.done is done:
                continue
            outside = [
                dst
                for dst, _ in _successors_with_searched(member)
                if _find_representative(dst) not in inside
            ]
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
        constraint_groups = []
        for member in members:
            inbox.extend(_received(member))
            if member.constraint_groups:
                constraint_groups.extend(member.constraint_groups)
            elif member.constraints:
                constraint_groups.append((member.constraints, member.fired))
            if member is not representative:
                member.representative = representative
        successors = {}
        for member in members:
            for dst, searched in _successors_with_searched(member):
                target = _find_representative(dst)
                if target is not representative and target not in successors:
                    successors[target] = searched
            if member is not representative:
                member.done = EMPTY
                member.inbox = member.successors = member.constraints = None
                member.constraint_groups = None
                member.fired = EMPTY
        self._merged += len(members) - 1
        self._set_done(representative, done)
        representative.successors = None
        for target, searched in successors.items():
            self._link(representative, target, searched)
        representative.constraints = None
        representative.constraint_groups = constraint_groups or None
        representative.fired = EMPTY
        if constraint_groups:
            self._firing_nodes[representative] = None
        representative.inbox = None
        for objects in inbox:
            self._receive(representative, objects)
        for successors, extra in catch_up:
            for dst in successors:
                target = _find_representative(dst)
                if target is not representative:
                    self._receive(target, extra)


def _received_sets(inbox):
    if inbox is None:
        return ()
    return inbox.values() if type(inbox) is dict else (inbox,)


def _received(node):
    return _received_sets(node.inbox)


def _find_representative(node):
    if node.representative is None:
        return node
    root = node.representative
    while root.representative is not None:
        root = root.representative
    while node is not root:
        node.representative, node = root, node.representative
    return root


def _cycle_components(starts):
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
    edges = 0
    for start in starts:
        start = _find_representative(start)
        if start in index:
            continue
        index[start] = low[start] = len(index)
        stack.append(start)
        on_stack.add(start)
        work = [[start, _successor_list(start), 0]]
        while work:
            frame = work[-1]
            node, successors, position = frame
            count = len(successors)
            while position < count:
                successor = successors[position]
                position += 1
                edges += 1
                if successor not in index:
                    break
                if successor in on_stack:
                    known = index[successor]
                    if known < low[node]:
                        low[node] = known
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    if low[node] < low[parent]:
                        low[parent] = low[node]
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
                continue
            frame[2] = position
            index[successor] = low[successor] = len(index)
            stack.append(successor)
            on_stack.add(successor)
            work.append([successor, _successor_list(successor), 0])
    return components, len(index) + edges


def _successor_list(node):
    successors = node.successors
    if successors is None:
        return ()
    if type(successors) is not dict:
        successors = (successors,)
    return [
        dst if dst.representative is None else _find_representative(dst)
        for dst in successors
    ]


def _successors_with_searched(node):
    successors = node.successors
    if successors is None:
        return ()
    if type(successors) is dict:
        return successors.items()
    return ((successors, False),)


class Constraint:
    __slots__ = ()
    kinds = None

    def apply(self, obj):
        raise NotImplementedError

    def apply_each(self, objects):
        for obj in objects:
            self.apply(obj)

    def results(self):
        return ()

    def captured(self):
        return ()

    def saturate(self, solver):
        for node in self.results():
            if node is not None:
                solver.add_object(node, solver.saturated)


class Each(Constraint):
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
            function = MethodType(function, self.owner)
        if kinds is None:
            for obj in objects:
                function(obj, *args)
        else:
            for obj in objects:
                if isinstance(obj, kinds):
                    function(obj, *args)
