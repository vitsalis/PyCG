"""Selected operations of the standard library that iterate what they get
(`LIBRARY_ITERATION`; design.md, "Selected standard-library operations").

An eager operation iterates its arguments at the call, from the scope of
the call. A lazy operation calls `iter()` on them at the call and gives a
lazy object, an engine container of the operation's class whose state
(`_Lazy`) holds the iterators, or the iterables for `chain` and
`heapq.merge`. The object is advanced where an iteration of the program
advances it (`next_element`: `next()`, `.__next__()`, a loop, unpacking,
the builtins and the operations that consume it, another lazy object that
is itself advanced): from that scope and site, it advances its sources. A
lazy object that no analysed code advances advances nothing: its client
does. Construction, storing, returning and `iter()` of it advance nothing.

Each advancing of a lazy object from a scope and a site is one activation
with one result node, made before its subscriptions, which every later
request of the same key joins (`advance_library`). Lazy objects, scopes
and sites are finite, so the activations are; a lazy object that is its
own source (`x = chain(x, y)`) reaches its own activation, which exists.
"""

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
    LIBRARY_ITERATION,
    MATERIALIZE,
    NOT_CONSUMING,
    POSITIONS,
    STARMAP,
    TEE,
    TUPLES,
)
from .model import Container
from .solver import Each

# What `len()` of an argument calls: `__len__` (heapq.nlargest).
LENGTH = (("__len__", ()),)


class _Lazy:
    """The state of a lazy object of the table: how it advances, what it
    gives, and a node of sources per position."""

    __slots__ = ("mode", "values", "sources", "group", "keyed")

    def __init__(self, mode, values, sources):
        self.mode = mode
        self.values = values
        self.sources = sources
        self.group = None
        self.keyed = False


class LibraryIteration:
    """The part of `Analysis` for the operations of the table."""

    def library_operation(self, call, path, overloads):
        """The call `call` binds the operation `path` of the table with
        `overloads` (parameters, result, bound arguments)."""
        key = ("library", call.origin, path)
        if key in self._library_calls:
            return
        self._library_calls.add(key)
        mode, roles, values, kind = LIBRARY_ITERATION[path]
        positions = self._operation_arguments(roles, overloads)
        caller, site = call.caller, call.site
        if mode == EAGER:
            for index, node in enumerate(positions):
                construct = ("library", call, path, index)
                self.iterated(node, construct, caller, site)
            return
        if mode == MATERIALIZE:
            self._materialize(call, path, positions, values, kind)
            return
        if mode == LARGEST:
            for index, node in enumerate(positions):
                self.add_length_hint(node, caller, site, LENGTH)
                iterators = self._obtain(node, call, (path, index))
                again = self._obtain(iterators, call, (path, index, "again"))
                advance = self.iteration(
                    self.node(), caller, site, role=("library", path, index)
                )
                self.solver.attach(
                    again, Each(self.next_element, advance, results=(advance.dst,))
                )
            return
        lazy = self.container_at(kind, call.origin, site, ("library", path))
        if mode == LAZY_ALL:
            sources = positions
        else:
            sources = [
                self._obtain(node, call, (path, index))
                for index, node in enumerate(positions)
            ]
            if mode == TEE:
                sources = [
                    self._obtain(node, call, (path, index, "again"))
                    for index, node in enumerate(sources)
                ]
        state = _Lazy(mode, values, sources)
        self._library[lazy] = state
        result = lazy
        if mode == TEE:
            result = self.container_at("tuple", call.origin, site, "tee", exact=True)
            self.add_object(self.unknown(result), lazy)
        elif mode == GROUPBY:
            state.keyed = any(bound.given("key") for _, _, bound in overloads)
            group = self.container_at(GROUPER, call.origin, site, "group")
            self._library[group] = _Lazy(LAZY, ITEMS, sources)
            state.group = group
        if call.dst is not None:
            self.add_object(call.dst, result)

    def _operation_arguments(self, roles, overloads):
        """A node per position of the iterated arguments that the
        overloads bind: by name, or for "*" every parameter typed as an
        abstract iterable, in order (`*iterables` is one position)."""
        positions = []
        for parameters, _, bound in overloads:
            if roles == ("*",):
                chosen = [p for p in parameters if _iterable_type(p[3])]
            else:
                chosen = [p for name in roles for p in parameters if p[0] == name]
            for index, parameter in enumerate(chosen):
                node = self._parameter_node(bound, parameter)
                if node is None:
                    continue
                while len(positions) <= index:
                    positions.append(self.node())
                self.add_edge(node, positions[index])
        return positions

    def _obtain(self, node, call, tag):
        """A node with what `iter()` of each object of `node` gives, called
        from the scope and site of `call`."""
        iterators = self.node()
        iteration = self.iteration(
            self.node(), call.caller, call.site, role=("library", tag)
        )
        each = Each(self.iterator, iteration, iterators, results=(iterators,))
        self.solver.attach(node, each)
        return iterators

    def _materialize(self, call, path, positions, values, kind):
        caller, site = call.caller, call.site
        items = []
        for index, node in enumerate(positions):
            construct = ("library", call, path, index)
            items.append(self.iterated(node, construct, caller, site))
            self.add_length_hint(node, caller, site)
        if kind is None or call.dst is None:
            return
        result = self.container_at(kind, call.origin, site, ("library", path))
        rule = ("library items", path)
        length = len(items) if values == POSITIONS else None
        made = self.container_at("tuple", call.origin, site, rule, length, exact=True)
        for index, node in enumerate(items):
            target = self.element(made, index) if length else self.unknown(made)
            self.add_edge(node, target)
        self.add_object(self.unknown(result), made)
        self.add_object(call.dst, result)

    def advance_library(self, obj, iteration):
        """Advance the lazy object `obj` from the scope and site of
        `iteration`: one activation per key, whose result node every
        request joins."""
        key = (obj, iteration.caller, iteration.site)
        found = self._library_advances.get(key)
        if found is None:
            found = self._library_advances[key] = self.node()
            self._activate(obj, self._library[obj], iteration, found)
        self.add_edge(found, iteration.dst)

    def _activate(self, obj, state, iteration, found):
        caller, site = iteration.caller, iteration.site
        if state.mode == LAZY_ALL:
            for index, node in enumerate(state.sources):
                target = found if state.values == ITEMS else self.node()
                each = self.iteration(target, caller, site, role=("library", index))
                self.solver.attach(node, each)
            return
        items = []
        for index, node in enumerate(state.sources):
            items.append(self.node())
            advance = self.iteration(
                items[index], caller, site, role=("library", index)
            )
            self.solver.attach(
                node, Each(self.next_element, advance, results=(items[index],))
            )
        if state.mode == LAZY_OUTER:
            # Each item is an inner iterable, iterated here.
            inner = self.iteration(found, caller, site, role=("library", "inner"))
            for node in items:
                self.solver.attach(node, inner)
            return
        if state.mode == STARMAP:
            # Each argument bundle is made a tuple: iterated, its length asked.
            for node in items:
                bundle = self.iteration(
                    self.node(), caller, site, role=("library", "bundle")
                )
                self.solver.attach(node, bundle)
                self.add_length_hint(node, caller, site)
            return
        if state.mode == GROUPBY:
            pair = self.container_at("tuple", obj, site, "group pair", 2, exact=True)
            if not state.keyed:
                for node in items:
                    self.add_edge(node, self.element(pair, 0))
            self.add_object(self.element(pair, 1), state.group)
            self.add_object(found, pair)
            return
        if state.values in (ITEMS, FIRST):
            for node in items[:1] if state.values == FIRST else items:
                self.add_edge(node, found)
        elif state.values in (TUPLES, POSITIONS):
            length = len(items) if state.values == POSITIONS else None
            made = self.container_at("tuple", obj, site, "items", length, exact=True)
            for index, node in enumerate(items):
                target = self.element(made, index) if length else self.unknown(made)
                self.add_edge(node, target)
            self.add_object(found, made)

    def consume_library(self, call, overloads):
        """A builtin of the stubs that takes an iterable (`str.join`, `sum`,
        `any`) consumes the lazy objects of the table that it gets, from the
        scope of its call."""
        for path, (parameters, _, bound) in overloads:
            if path in NOT_CONSUMING:
                continue
            for parameter in parameters:
                if not _iterable_type(parameter[3]):
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


# The abstract iterables of the stubs that a parameter of an operation is
# typed as, at its top level or in an arm of a union.
_ITERABLES = frozenset({"typing.Iterable", "typing.Iterator", "typing.Collection"})


def _iterable_type(reduced):
    if isinstance(reduced, list) and reduced[:1] == ["|"]:
        return any(_iterable_type(arm) for arm in reduced[1:])
    if isinstance(reduced, list) and reduced and isinstance(reduced[0], str):
        return reduced[0] in _ITERABLES
    return isinstance(reduced, str) and reduced in _ITERABLES
