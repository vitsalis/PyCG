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

One state per call origin and operation: every call of that origin (the
implicit calls that copy a call expression, each with its receivers)
merges its arguments into the state's nodes and gets the state's result.
A position, a fill value or an initial value that a later call brings is
wired into every activation made before. Each advancing of a lazy object
from a scope and a site is one activation with one result node, made
before its subscriptions, which every later request of the same key
joins (`advance_library`). Lazy objects, scopes, sites and positions are
finite, so the activations are; a lazy object that is its own source
(`x = chain(x, y)`) reaches its own activation, which exists. The tuples
of `product` and `zip_longest` have one shape per arity of the calls of
the origin (None where an unpacked argument or a repetition hides the
positions), so a later call of another arity adds a shape and changes
none; the key of `groupby` becoming the item rewires what came before.
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

# What `len()` of an argument calls: `__len__` (heapq.nlargest).
LENGTH = (("__len__", ()),)
# The key of a position that is not known (an unpacked argument).
ANY = "*"


class _Lazy:
    """The state of one call origin of an operation of the table: how it
    advances (`mode`), what it gives (`values`), the scope and site of the
    call, a node per position of its arguments (`arguments`, `ANY` for one
    that is not known) and of its sources (`sources`: the iterators, or the
    iterables for `chain` and `merge`), the items made at the call for a
    materializer, the values that the result gets as they are (`given`),
    the arities of the calls (`arities`: the number of positions, None
    where an unpacked argument or a repetition hides them), the tuples of
    a materializer's items, one per arity (`shapes`), whether the key of
    `groupby` is the item (`identity`), and the activations made."""

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
        "given",
        "arities",
        "shapes",
        "identity",
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
        self.given = None
        self.arities = {}
        self.shapes = {}
        self.identity = False
        self.group = None
        self.activations = []


class _Activation:
    """An advancing of a lazy object from a scope and a site: its result
    node, the items of each position, and the tuple or pair it makes."""

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
    """The part of `Analysis` for the operations of the table."""

    def library_operation(self, call, path, overloads):
        """The call `call` binds the operation `path` of the table with
        `overloads` (parameters, result, bound arguments)."""
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
            arity = 1 + max((p for p, _ in arguments if p != ANY), default=-1)
        for parameters, _, bound in overloads:
            name = LIBRARY_VALUES.get(path)
            if name is not None and bound.given(name) and bound[name] is not None:
                self.add_edge(bound[name], self._given(state))
            repeat = REPEATS.get(path)
            if repeat is not None and bound.given(repeat):
                arity = None
            if mode == GROUPBY and _identity_key(self, call, parameters, bound):
                self._identity(state)
        if values in (TUPLES, POSITIONS):
            self._arity(state, arity if values == POSITIONS else None)
        if call.dst is not None and state.made is not None:
            self.add_object(call.dst, state.made)

    def _new_operation(self, call, path, mode, values, kind):
        state = _Lazy(path, mode, values, call.caller, call.site)
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
                grouper = _Lazy(path, LAZY, ITEMS, call.caller, site)
                grouper.sources = state.sources
                self._library[group] = grouper
                state.group = group
        return state

    def _operation_arguments(self, roles, overloads, call):
        """The (position, node) of each iterated argument that the overloads
        bind: by name, or for "*" every parameter typed as an abstract
        iterable, in order. The arguments that `*iterables` takes keep their
        positions where the call unpacks nothing (`product(a, b)`); an
        unpacked argument is at a position that is not known (`ANY`)."""
        found = []
        for parameters, _, bound in overloads:
            if roles == ("*",):
                chosen = [p for p in parameters if _iterable_type(p[3])]
            else:
                chosen = [p for name in roles for p in parameters if p[0] == name]
            for index, parameter in enumerate(chosen):
                if parameter[1] == "*" and bound.varargs is not None:
                    if call.star:
                        found.append((ANY, self.every(bound.varargs)))
                        continue
                    for offset in range(len(call.args) - index):
                        element = self.element(bound.varargs, offset)
                        found.append((index + offset, element))
                    continue
                node = self._parameter_node(bound, parameter)
                if node is not None:
                    # A named parameter keeps its role (compress's data),
                    # also where the call unpacks its arguments.
                    found.append((index, node))
        return found

    def _argument(self, state, position):
        """The node of the arguments at `position`, made with what the mode
        does with them at the call (once per position)."""
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
            self.add_length_hint(node, caller, site, _hint(state.unless))
            state.items[position] = items
            for arity, shape in state.shapes.items():
                self._into_shape(items, shape, arity, position)
        elif mode == LARGEST:
            self.add_length_hint(node, caller, site, LENGTH)
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

    def _given(self, state):
        """The node of the values that the result gets as they are."""
        if state.given is None:
            state.given = self.node()
            for activation in state.activations:
                if state.values == POSITIONS:
                    # A fill value can be at any position.
                    for shape in activation.shapes.values():
                        self.add_edge(state.given, self.unknown(shape))
                else:
                    self.add_edge(state.given, activation.found)
        return state.given

    def _arity(self, state, arity):
        """A call of `state` makes tuples of `arity` positions (None: not
        known): a tuple shape of that length for the materializer and for
        every activation, made once per arity, with the items of every
        position wired into it."""
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
        # The site is part of the key: each advancing makes its own tuples.
        rule = ("library items", activation.caller, activation.site, arity)
        shape = self.container_at(
            "tuple", activation.lazy, activation.site, rule, arity, exact=True
        )
        activation.shapes[arity] = shape
        self.add_object(activation.found, shape)
        for position, items in list(activation.items.items()):
            self._into_shape(items, shape, arity, position)
        if state.given is not None:
            self.add_edge(state.given, self.unknown(shape))

    def _into_shape(self, items, shape, arity, position):
        """The items of `position` in the tuple `shape` of `arity`: at that
        position, at any position where the arity is not known, nowhere for
        a position that the shape does not have."""
        if arity is None:
            self.add_edge(items, self.unknown(shape))
        elif position != ANY and position < arity:
            self.add_edge(items, self.element(shape, position))

    def _identity(self, state):
        """The key of `groupby` is the item."""
        if state.identity:
            return
        state.identity = True
        for activation in state.activations:
            for items in activation.items.values():
                self.add_edge(items, self.element(activation.made, 0))

    def _iterate(self, node, dst, caller, site, role, unless=()):
        iteration = self.iteration(dst, caller, site, unless=unless, role=role)
        self.solver.attach(node, iteration)

    def _advance(self, node, dst, caller, site, role):
        """dst ⊇ what advancing the iterators of `node` gives, from there."""
        advance = self.iteration(dst, caller, site, role=role)
        self.solver.attach(node, Each(self.next_element, advance, results=(dst,)))

    def _obtain(self, node, caller, site, tag):
        """A node with what `iter()` of each object of `node` gives, called
        from `caller` at `site`."""
        iterators = self.node()
        iteration = self.iteration(self.node(), caller, site, role=("library", tag))
        each = Each(self.iterator, iteration, iterators, results=(iterators,))
        self.solver.attach(node, each)
        return iterators

    def advance_library(self, obj, iteration):
        """Advance the lazy object `obj` from the scope and site of
        `iteration`: one activation per key, whose result node every
        request joins."""
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
            if state.given is not None and state.values != POSITIONS:
                self.add_edge(state.given, found)
        self.add_edge(found, iteration.dst)

    def _wire(self, state, activation, position):
        """Advance the sources of `position` for `activation`."""
        caller, site = activation.caller, activation.site
        source, found = state.sources[position], activation.found
        role = ("library", position)
        if state.mode == LAZY_ALL:
            self._iterate(source, found, caller, site, role)
            return
        if state.mode == MERGE:
            # iter() of each iterable, advanced; the last one is delegated
            # to with `yield from`, which takes iter() of its iterator again.
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
            # Each item is an inner iterable, iterated here.
            self._iterate(items, found, caller, site, ("library", "inner"))
        elif state.mode == STARMAP:
            # Each argument bundle is made a tuple: iterated, its length asked.
            self._iterate(items, self.node(), caller, site, ("library", "bundle"))
            self.add_length_hint(items, caller, site)
        elif state.mode == GROUPBY:
            if state.identity:
                self.add_edge(items, self.element(activation.made, 0))
        elif state.values == ITEMS or (state.values == FIRST and position == 0):
            self.add_edge(items, found)
        elif state.values in (TUPLES, POSITIONS):
            for arity, shape in activation.shapes.items():
                self._into_shape(items, shape, arity, position)

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


def _identity_key(analysis, call, parameters, bound):
    """Whether the key of a call of `groupby` may be the item: no key, a key
    that `**kwargs` may omit, or the literal `None` (by keyword or at its
    position)."""
    if not bound.surely("key") or bound["key"] is None:
        return True
    if analysis.literal_none_keyword(call, "key"):
        return True
    names = [parameter[0] for parameter in parameters]
    return "key" in names and analysis.literal_none(call, names.index("key"))


def _hint(unless):
    """The length hint of a materializer: `LENGTH_HINT`, skipped as a whole
    where the class derives from `tuple` for `math.dist`."""
    if not unless:
        return LENGTH_HINT
    return tuple((name, (*skips, *unless)) for name, skips in LENGTH_HINT)


# The abstract iterables of the stubs that a parameter of an operation is
# typed as, at its top level or in an arm of a union.
_ITERABLES = frozenset({"typing.Iterable", "typing.Iterator", "typing.Collection"})


def _iterable_type(reduced):
    if isinstance(reduced, list) and reduced[:1] == ["|"]:
        return any(_iterable_type(arm) for arm in reduced[1:])
    if isinstance(reduced, list) and reduced and isinstance(reduced[0], str):
        return reduced[0] in _ITERABLES
    return isinstance(reduced, str) and reduced in _ITERABLES
