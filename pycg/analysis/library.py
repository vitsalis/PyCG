from .builtin_models import (
    EAGER,
    FIRST,
    GROUPBY,
    GROUPER,
    ITEMS,
    LARGEST,
    LAZY,
    LAZY_ALL,
    LAZY_OUTER,
    LENGTH_HINT,
    LIBRARY_ITERATION,
    LIBRARY_VALUES,
    MATERIALIZE,
    MERGE,
    NOT_CONSUMING,
    POSITIONS,
    READS_TUPLES,
    REPEATS,
    STARMAP,
    TEE,
    TUPLE_STORAGE,
    TUPLES,
)
from .model import Container
from .solver import Each

LENGTH_SPECIAL_CALLS = (("__len__", ()),)
POSITION_UNKNOWN = "*"


class _OperationState:
    __slots__ = (
        "path",
        "mode",
        "values",
        "caller",
        "site",
        "unless",
        "arguments",
        "sources",
        "items",
        "made",
        "values_as_given",
        "arities",
        "shapes",
        "key_is_item",
        "group",
        "activations",
    )

    def __init__(self, path, mode, values, caller, site):
        self.path = path
        self.mode = mode
        self.values = values
        self.caller = caller
        self.site = site
        self.unless = (TUPLE_STORAGE,) if path in READS_TUPLES else ()
        self.arguments = {}
        self.sources = {}
        self.items = {}
        self.made = None
        self.values_as_given = None
        self.arities = {}
        self.shapes = {}
        self.key_is_item = False
        self.group = None
        self.activations = []


class _Activation:
    __slots__ = ("lazy", "caller", "site", "found", "items", "made", "shapes")

    def __init__(self, lazy, caller, site, found):
        self.lazy = lazy
        self.caller = caller
        self.site = site
        self.found = found
        self.items = {}
        self.made = None
        self.shapes = {}


class LibraryIteration:
    def library_operation(self, call, path, overloads):
        mode, roles, values, kind = LIBRARY_ITERATION[path]
        key = (call.origin, path)
        state = self._library_calls.get(key)
        if state is None:
            state = self._new_operation(call, path, mode, values, kind)
            self._library_calls[key] = state
        arguments = self._operation_arguments(roles, overloads, call)
        for position, node in arguments:
            self.add_edge(node, self._argument(state, position))
        arity = None
        if not call.star:
            arity = 1 + max(
                (p for p, _ in arguments if p != POSITION_UNKNOWN), default=-1
            )
        for parameters, _, bound in overloads:
            name = LIBRARY_VALUES.get(path)
            if name is not None and bound.given(name) and bound[name] is not None:
                self.add_edge(bound[name], self._values_as_given_node(state))
            repeat = REPEATS.get(path)
            if repeat is not None and bound.given(repeat):
                arity = None
            if mode == GROUPBY and _groupby_key_may_be_item(
                self, call, parameters, bound
            ):
                self._make_groupby_key_the_item(state)
        if values in (TUPLES, POSITIONS):
            self._arity(state, arity if values == POSITIONS else None)
        if call.dst is not None and state.made is not None:
            self.add_object(call.dst, state.made)

    def _new_operation(self, call, path, mode, values, kind):
        state = _OperationState(path, mode, values, call.caller, call.site)
        origin, site = call.origin, call.site
        if mode == MATERIALIZE:
            if kind is not None:
                state.made = self.container_at(kind, origin, site, ("library", path))
        elif mode not in (EAGER, LARGEST):
            lazy = self.container_at(kind, origin, site, ("library", path))
            self._library[lazy] = state
            state.made = lazy
            if mode == TEE:
                state.made = self.container_at("tuple", origin, site, "tee", exact=True)
                self.add_object(self.unknown(state.made), lazy)
            elif mode == GROUPBY:
                group = self.container_at(GROUPER, origin, site, "group")
                grouper = _OperationState(path, LAZY, ITEMS, call.caller, site)
                grouper.sources = state.sources
                self._library[group] = grouper
                state.group = group
        return state

    def _operation_arguments(self, roles, overloads, call):
        found = []
        for parameters, _, bound in overloads:
            if roles == ("*",):
                chosen = [p for p in parameters if _is_abstract_iterable_type(p[3])]
            else:
                chosen = [p for name in roles for p in parameters if p[0] == name]
            for index, parameter in enumerate(chosen):
                if parameter[1] == "*" and bound.varargs is not None:
                    if call.star:
                        found.append((POSITION_UNKNOWN, self.every(bound.varargs)))
                        continue
                    for offset in range(len(call.args) - index):
                        element = self.element(bound.varargs, offset)
                        found.append((index + offset, element))
                    continue
                node = self._parameter_node(bound, parameter)
                if node is not None:
                    found.append((index, node))
        return found

    def _argument(self, state, position):
        node = state.arguments.get(position)
        if node is not None:
            return node
        node = state.arguments[position] = self.node()
        caller, site, mode, path = state.caller, state.site, state.mode, state.path
        tag = (path, position)
        if mode == EAGER:
            self._iterate(node, self.node(), caller, site, ("library", tag))
        elif mode == MATERIALIZE:
            items = self.node()
            self._iterate(node, items, caller, site, ("library", tag), state.unless)
            self.add_length_hint(
                node, caller, site, _materializer_length_hint(state.unless)
            )
            state.items[position] = items
            for arity, shape in state.shapes.items():
                self._into_shape(items, shape, arity, position)
        elif mode == LARGEST:
            self.add_length_hint(node, caller, site, LENGTH_SPECIAL_CALLS)
            iterators = self._obtain(node, caller, site, tag)
            again = self._obtain(iterators, caller, site, (*tag, "again"))
            self._advance(again, self.node(), caller, site, ("library", tag))
        else:
            if mode in (LAZY_ALL, MERGE):
                source = node
            else:
                source = self._obtain(node, caller, site, tag)
                if mode == TEE:
                    source = self._obtain(source, caller, site, (*tag, "again"))
            state.sources[position] = source
            for activation in state.activations:
                self._wire(state, activation, position)
        return node

    def _values_as_given_node(self, state):
        if state.values_as_given is None:
            state.values_as_given = self.node()
            for activation in state.activations:
                if state.values == POSITIONS:
                    for shape in activation.shapes.values():
                        self.add_edge(state.values_as_given, self.unknown(shape))
                else:
                    self.add_edge(state.values_as_given, activation.found)
        return state.values_as_given

    def _arity(self, state, arity):
        if arity in state.arities:
            return
        state.arities[arity] = None
        if state.mode == MATERIALIZE and state.made is not None:
            rule = ("library items", state.path, arity)
            shape = self.container_at(
                "tuple", state.made, state.site, rule, arity, exact=True
            )
            state.shapes[arity] = shape
            self.add_object(self.unknown(state.made), shape)
            for position, items in list(state.items.items()):
                self._into_shape(items, shape, arity, position)
        for activation in state.activations:
            self._activation_shape(state, activation, arity)

    def _activation_shape(self, state, activation, arity):
        rule = ("library items", activation.caller, activation.site, arity)
        shape = self.container_at(
            "tuple", activation.lazy, activation.site, rule, arity, exact=True
        )
        activation.shapes[arity] = shape
        self.add_object(activation.found, shape)
        for position, items in list(activation.items.items()):
            self._into_shape(items, shape, arity, position)
        if state.values_as_given is not None:
            self.add_edge(state.values_as_given, self.unknown(shape))

    def _into_shape(self, items, shape, arity, position):
        if arity is None:
            self.add_edge(items, self.unknown(shape))
        elif position != POSITION_UNKNOWN and position < arity:
            self.add_edge(items, self.element(shape, position))

    def _make_groupby_key_the_item(self, state):
        if state.key_is_item:
            return
        state.key_is_item = True
        for activation in state.activations:
            for items in activation.items.values():
                self.add_edge(items, self.element(activation.made, 0))

    def _iterate(self, node, dst, caller, site, role, unless=()):
        iteration = self.iteration(dst, caller, site, unless=unless, role=role)
        self.solver.attach(node, iteration)

    def _advance(self, node, dst, caller, site, role):
        advance = self.iteration(dst, caller, site, role=role)
        self.solver.attach(node, Each(self.next_element, advance, results=(dst,)))

    def _obtain(self, node, caller, site, tag):
        iterators = self.node()
        iteration = self.iteration(self.node(), caller, site, role=("library", tag))
        each = Each(self.iterator, iteration, iterators, results=(iterators,))
        self.solver.attach(node, each)
        return iterators

    def advance_library(self, obj, iteration):
        key = (obj, iteration.caller, iteration.site)
        found = self._library_advances.get(key)
        if found is None:
            found = self._library_advances[key] = self.node()
            state = self._library[obj]
            activation = _Activation(obj, iteration.caller, iteration.site, found)
            if state.mode == GROUPBY:
                rule = ("group pair", iteration.caller, iteration.site)
                activation.made = self.container_at(
                    "tuple", obj, iteration.site, rule, 2, exact=True
                )
                self.add_object(self.element(activation.made, 1), state.group)
                self.add_object(found, activation.made)
            state.activations.append(activation)
            for arity in list(state.arities):
                self._activation_shape(state, activation, arity)
            for position in list(state.sources):
                self._wire(state, activation, position)
            if state.values_as_given is not None and state.values != POSITIONS:
                self.add_edge(state.values_as_given, found)
        self.add_edge(found, iteration.dst)

    def _wire(self, state, activation, position):
        caller, site = activation.caller, activation.site
        source, found = state.sources[position], activation.found
        role = ("library", position)
        if state.mode == LAZY_ALL:
            self._iterate(source, found, caller, site, role)
            return
        if state.mode == MERGE:
            iterators = self._obtain(source, caller, site, (state.path, position))
            again = self._obtain(
                iterators, caller, site, (state.path, position, "again")
            )
            self._advance(iterators, found, caller, site, role)
            self._advance(again, found, caller, site, (*role, "again"))
            return
        items = activation.items[position] = self.node()
        self._advance(source, items, caller, site, role)
        if state.mode == LAZY_OUTER:
            self._iterate(items, found, caller, site, ("library", "inner"))
        elif state.mode == STARMAP:
            self._iterate(items, self.node(), caller, site, ("library", "bundle"))
            self.add_length_hint(items, caller, site)
        elif state.mode == GROUPBY:
            if state.key_is_item:
                self.add_edge(items, self.element(activation.made, 0))
        elif state.values == ITEMS or (state.values == FIRST and position == 0):
            self.add_edge(items, found)
        elif state.values in (TUPLES, POSITIONS):
            for arity, shape in activation.shapes.items():
                self._into_shape(items, shape, arity, position)

    def consume_library(self, call, overloads):
        for path, (parameters, _, bound) in overloads:
            if path in NOT_CONSUMING:
                continue
            for parameter in parameters:
                if not _is_abstract_iterable_type(parameter[3]):
                    continue
                node = self._parameter_node(bound, parameter)
                if node is not None:
                    consume = Each(self._consume_library, call, kinds=(Container,))
                    self.solver.attach(node, consume)

    def _consume_library(self, obj, call):
        if obj in self._library:
            consuming = self.iteration(
                self.node(), call.caller, call.site, role="consume"
            )
            self.advance_library(obj, consuming)


def _groupby_key_may_be_item(analysis, call, parameters, bound):
    if not bound.surely("key") or bound["key"] is None:
        return True
    if analysis.literal_none_keyword(call, "key"):
        return True
    names = [parameter[0] for parameter in parameters]
    return "key" in names and analysis.literal_none(call, names.index("key"))


def _materializer_length_hint(unless):
    if not unless:
        return LENGTH_HINT
    return tuple((name, (*skips, *unless)) for name, skips in LENGTH_HINT)


_ABSTRACT_ITERABLE_TYPES = frozenset(
    {"typing.Iterable", "typing.Iterator", "typing.Collection"}
)


def _is_abstract_iterable_type(reduced):
    if isinstance(reduced, list) and reduced[:1] == ["|"]:
        return any(_is_abstract_iterable_type(arm) for arm in reduced[1:])
    if isinstance(reduced, list) and reduced and isinstance(reduced[0], str):
        return reduced[0] in _ABSTRACT_ITERABLE_TYPES
    return isinstance(reduced, str) and reduced in _ABSTRACT_ITERABLE_TYPES
