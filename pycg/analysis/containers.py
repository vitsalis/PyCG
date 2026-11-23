"""Containers and constants: the elements of lists, tuples, sets and dicts,
and how subscripts, slices, unpacking and iteration reach them.

`Containers` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses.

A container keeps its elements in nodes: one field per constant index or key,
`unknown` for elements stored under any other key, and, for a dict, `keys`.
A read with a constant key gets that field and `unknown`. A read of a dict
with a pattern key (patterns.py) gets the fields whose key is a str that the
pattern matches, and `unknown`. A read with any other key gets every
element. A key that holds nothing when the solve
reaches a fixpoint comes from code or values that the analysis does not see
(an argument from outside, `i + 1`): the completion then reads every element
or stores under an unknown key.
"""

from .builtin_models import builtin_kind
from .model import (
    Class,
    Const,
    Container,
    Coroutine,
    External,
    Generator,
    Instance,
    Pattern,
    Typed,
    TypeForm,
    constant_name,
)
from .solver import Constraint, Each

# Containers whose elements have positions.
SEQUENCES = ("list", "tuple")

# The builtin collections, whose iterator is another object (a generator
# and an iterator are their own).
COLLECTIONS = ("list", "tuple", "set", "frozenset", "dict")

# The builtin collections that keep their keys by hash, with the hash.
HASHED = ("set", "frozenset", "dict")


def is_dict(container):
    """Whether `container` keeps keys as a dict does: a dict, or a dict of
    `collections` (`OrderedDict`)."""
    return builtin_kind(container.kind) == "dict"


def hashes_keys(container):
    """Whether `container` keeps its keys by hash: a set, a frozenset or a
    dict (also a dict of `collections`)."""
    return builtin_kind(container.kind) in HASHED


def keeps_hashes(container):
    """Whether a set, `dict.fromkeys` or a set method reuses the hashes of
    the elements of `container` (CPython: a set or frozenset, or a dict of
    exactly that class) rather than hashing them again."""
    return container.kind in HASHED


def keeps_mapping_hashes(container):
    """Whether a dict that takes the items of the mapping `container`
    (`dict(m)`, `update`, `{**m}`, a `Counter`) reuses their hashes: a dict
    that iterates as `dict` does, which an `OrderedDict` does not."""
    return is_dict(container) and container.kind != "collections.OrderedDict"


class Containers:
    # Objects

    def const(self, value):
        """The constant `value`, a `str`, `bytes` or an `int` that is not a
        bool. No str equals bytes or an int, so the value is the key."""
        if value not in self._consts:
            self._consts[value] = Const(value)
        return self._consts[value]

    def container(self, kind, site, length=None):
        """A new container, for a display or comprehension at `site`: exactly
        of its class."""
        return Container(kind, site, length, exact=True)

    def container_at(self, kind, origin, site, rule, length=None, exact=False):
        """The container of `kind` that `rule` makes for the analysed
        operation `origin` (a call, a slice, an unpacking) at `site`, exactly
        of its class if `exact`. One call may reach several rules
        (`factory(*args)` that is `tuple` or `dict.items`), so the rule is
        part of the key, and the key decides the length; a copy is exact if
        what it copies is, so that is part of the key too."""
        key = (kind, origin, rule, exact)
        if key not in self._containers:
            self._containers[key] = Container(kind, site, length, exact)
        container = self._containers[key]
        assert container.length == length, f"{key!r} with another length"
        return container

    def inexact(self, obj):
        """`obj` as a value whose class is not known: itself unless it is an
        exact container, generator, coroutine, constant or pattern, else
        the one alias of it that is not exact, with its elements (the same
        nodes), its function or its value, and its name. It stands for an
        object that Python may make from `obj` (an enum member)."""
        exact = isinstance(obj, (Container, Generator, Coroutine, Const, Pattern))
        if not exact or not obj.exact:
            return obj
        if isinstance(obj, Pattern):
            return self.pattern(obj.prefix, obj.suffix, obj.case, exact=False)
        if isinstance(obj, Generator):
            return self._inexact_of(self._generators, obj, Generator)
        if isinstance(obj, Coroutine):
            return self._inexact_of(self._coroutines, obj, Coroutine)
        if isinstance(obj, Const):
            # Keyed apart from the values, which are str, bytes or int.
            key = (obj.value, "inexact")
            if key not in self._consts:
                self._consts[key] = Const(obj.value, exact=False)
            return self._consts[key]
        container = obj
        key = (container.kind, container, "inexact", False)
        alias = self._containers.get(key)
        if alias is None:
            alias = Container(container.kind, "", container.length)
            alias.name = container.name
            alias.fields = container.fields
            alias.observers = container.observers
            alias.unknown = self.unknown(container)
            alias.every = self.every(container)
            alias.keys = self.keys(container)
            alias.factory = container.factory
            alias.aliased = self.aliased(container)
            self._containers[key] = alias
        return alias

    def _inexact_of(self, table, obj, kind):
        key = (obj.function, "inexact")
        if key not in table:
            table[key] = kind(obj.function, exact=False)
        return table[key]

    def add_inexact(self, src, dst):
        """dst ⊇ the values of `src`, as values whose class is not known
        (see `inexact`)."""
        self.solver.attach(src, Each(self._add_inexact, dst, results=(dst,)))

    def _add_inexact(self, obj, dst):
        self.add_object(dst, self.inexact(obj))

    def add_class_member(self, value, field):
        """field ⊇ the values that a class body binds to a name, as values
        whose class is not known (see `inexact`): a metaclass (an enum's),
        `__init_subclass__` or a decorator may replace them."""
        self.add_inexact(value, field)

    # Nodes of a container

    def element(self, container, key):
        """The node of the elements stored under the constant `key`."""
        node = container.fields.get(key)
        if node is None:
            node = self.node(f"{container.name}[{constant_name(key)}]")
            container.fields[key] = node
            if container.every is not None:
                self.add_edge(node, container.every)
            for observer in list(container.observers):
                self._notify(observer, key, node)
        return node

    def unknown(self, container):
        """The node of the elements stored under keys that are not known."""
        if container.unknown is None:
            container.unknown = self.node(f"{container.name}[?]")
            if container.every is not None:
                self.add_edge(container.unknown, container.every)
        return container.unknown

    def every(self, container):
        """A node that holds every element of `container`."""
        if container.every is None:
            container.every = self.node()
            for node in container.fields.values():
                self.add_edge(node, container.every)
            if container.unknown is not None:
                self.add_edge(container.unknown, container.every)
        return container.every

    def keys(self, container):
        """The node of the keys of a dict."""
        if container.keys is None:
            container.keys = self.node(f"{container.name}.<keys>")
        return container.keys

    def aliased(self, container):
        """The node of the elements of a dict stored under a key that is an
        alias of a class member (see `write_key`)."""
        if container.aliased is None:
            container.aliased = self.node(f"{container.name}.<aliased>")
        return container.aliased

    def factory(self, container):
        """The node of the factories of a `defaultdict`."""
        if container.factory is None:
            container.factory = self.node(f"{container.name}.<factory>")
        return container.factory

    def elements(self, container):
        """What iterating over `container` gives: the keys of a dict, every
        element of the others."""
        if is_dict(container):
            return self.keys(container)
        return self.every(container)

    def observe(self, container, observer):
        """Call `observer(key, node)` for each field of `container`, now and
        when it is added."""
        container.observers.append(observer)
        for key, node in list(container.fields.items()):
            self._notify(observer, key, node)

    def _notify(self, observer, key, node):
        """Call `observer(key, node)` after the notifications already
        queued. A notification that adds a field to another container queues
        more instead of nesting calls, so a long chain of copied containers
        (`a + b + c + ...`) does not exhaust the stack in any order."""
        notices = self._notices
        if self._notifying:
            notices.append((observer, key, node))
            return
        self._notifying = True
        try:
            if notices:
                # Left by a run that an error stopped: they go first.
                notices.append((observer, key, node))
            else:
                observer(key, node)
            while notices:
                observer, key, node = notices.popleft()
                observer(key, node)
        finally:
            self._notifying = False

    # Reads and writes by key

    def _field_key(self, container, key):
        """The field that the constant `key` selects in `container`, or None
        if it is not known: a negative index of a sequence of unknown
        length, or any index of a container that keeps no positions (a
        `deque`, whose `appendleft` moves them)."""
        if is_dict(container):
            return key
        if container.kind not in SEQUENCES:
            return None
        if isinstance(key, int) and key < 0:
            if container.length is not None and key >= -container.length:
                return key + container.length
            return None
        return key

    def read_key(self, key, container, dst):
        """dst ⊇ container[key] for the key object `key`."""
        if isinstance(key, Const):
            position = self._field_key(container, key.value)
            if position is not None:
                self.add_edge(self.element(container, position), dst)
                self.add_edge(self.unknown(container), dst)
                return
        elif isinstance(key, Pattern) and key.exact and is_dict(container):
            # An inexact pattern is a class member (an enum member), which
            # may equal any key: it reads every element.
            self._read_pattern(key, container, dst)
            return
        self.add_edge(self.every(container), dst)

    def _read_pattern(self, pattern, container, dst):
        """dst ⊇ container[pattern] for the dict `container`: the fields
        whose key is a str that `pattern` matches, now and when they are
        added, `unknown`, and the elements stored under an alias of a class
        member (`aliased`), whatever its value. A str with the constant
        prefix p and suffix s equals only the strs that start with p and end
        with s, and no str equals bytes or an int; a class member may
        define its own equality."""
        self.add_edge(self.unknown(container), dst)
        self.add_edge(self.aliased(container), dst)

        def read_field(key, node):
            if isinstance(key, str) and pattern.matches(key) is not None:
                self.add_edge(node, dst)

        self.observe(container, read_field)

    def write_key(self, key, container, src):
        """container[key] ⊇ src for the key object `key`. A key that is an
        alias of a class member (an inexact constant, an enum member) is
        stored under its value, and in `aliased` too: by its own equality,
        hashing or construction it may equal any str (see
        `_read_pattern`)."""
        if isinstance(key, Const):
            position = self._field_key(container, key.value)
            if position is not None:
                self.add_edge(src, self.element(container, position))
                if not key.exact and is_dict(container):
                    self.add_edge(src, self.aliased(container))
                return
        self.add_edge(src, self.unknown(container))

    def add_hash(self, key, caller, site, stored=None):
        """A set or dict hashes its keys: `__hash__` of each object that the
        key node `key` holds. A store or lookup also compares each object
        of the key, whatever it is (a constant, a function), with each key
        in the node `stored` that is another object, as Python does where
        the hashes are equal: the `__eq__` of a stored key that is an
        instance or class. Each stored key is compared once per construct,
        not once per pair of keys."""
        call = self.site_call(caller, site, ("hash",))
        self.add_special_call(key, "__hash__", call)
        if stored is not None:
            compare = self.site_call(caller, site, ("hash_eq",), [None])
            compared = self._compared_keys.setdefault(compare, set())
            pairing = _KeyLookup(self, compare, compared)
            self.solver.attach(key, Each(pairing.key))
            self.solver.attach(stored, Each(pairing.stored, kinds=(Instance, Class)))

    def key_store(self, container):
        """The node that a key entering the set or dict `container` goes
        to: the keys of a dict, the elements of a set."""
        return self.keys(container) if is_dict(container) else self.unknown(container)

    def add_keys(self, target, source, construct, caller, site, keeps=keeps_hashes):
        """The elements of each iterable that the node `source` holds enter
        the set or dict `target`: they are hashed and compared with its
        keys (see `add_hash`), but those of a container whose hashes Python
        reuses (`keeps`), which keep their hash (`set(s)`). `construct` (the
        arguments of a call bound to a model) iterates `source` once for
        every target."""
        hashed, kept = self.entering_keys(source, construct, caller, site, keeps)
        self.add_edge(hashed, self.key_store(target))
        self.add_edge(kept, self.key_store(target))
        self.add_hash(hashed, caller, site, self.elements(target))

    def entering_keys(self, source, construct, caller, site, keeps=keeps_hashes):
        """Two nodes, made once for `construct`: the elements of the
        iterables in `source` that a set or dict hashes when they enter it,
        and those of the containers whose hashes it reuses (`keeps`)."""
        found = self._iterated.get(("keys", construct))
        if found is None:
            hashed, kept = self.node(), self.node()
            iteration = _Iterate(self, hashed, caller, site, role="elements")
            each = Each(
                self._enter_keys, kept, iteration, keeps, results=(hashed, kept)
            )
            self.solver.attach(source, each)
            found = self._iterated[("keys", construct)] = (source, (hashed, kept))
        iterated, nodes = found
        assert iterated is source, f"{construct!r} hashes another node"
        return nodes

    def _enter_keys(self, obj, kept, iteration, keeps):
        if isinstance(obj, Container) and keeps(obj):
            self.add_edge(self.elements(obj), kept)
        else:
            iteration.apply(obj)

    def read_keyed(self, container, key, dst):
        """dst ⊇ container[key] for each object of the key node `key` (None
        if the key is not tracked)."""
        if dst is None:
            return
        if key is None:
            self.add_edge(self.every(container), dst)
            return
        self.solver.attach(key, _Keyed(self.read_key, container, dst, dst))
        self._keyed.append((key, container, dst, True))

    def write_keyed(self, container, key, src):
        """container[key] ⊇ src for each object of the key node `key`. A
        dict records its keys even if the value is not tracked."""
        if key is not None and is_dict(container):
            self.add_edge(key, self.keys(container))
        if src is None:
            return
        if key is None:
            self.add_edge(src, self.unknown(container))
            return
        self.solver.attach(key, _Keyed(self.write_key, container, src, None))
        self._keyed.append((key, container, src, False))

    def _complete_keys(self):
        """Read every element, or store under an unknown key, where the key
        holds nothing at the fixpoint. Return whether anything was added."""
        added = False
        for key, container, node, read in self._keyed[self._completed_keys :]:
            if not self.solver.objects(key):
                if read:
                    self.add_edge(self.every(container), node)
                else:
                    self.add_edge(node, self.unknown(container))
                added = True
        self._completed_keys = len(self._keyed)
        return added

    def copy_range(self, source, target, bounds):
        """Copy the elements of the sequence `source` from `start` to `stop`,
        where `bounds` is `(start, stop)`, to `target` from position 0. If
        the bounds or the length are not known (`bounds` None), every
        element goes to `unknown`."""
        if bounds is not None and source.length is not None:
            start, stop, _ = slice(*bounds).indices(source.length)
            for offset, position in enumerate(range(start, stop)):
                self.add_edge(
                    self.element(source, position), self.element(target, offset)
                )
            self.add_edge(self.unknown(source), self.unknown(target))
        else:
            self.add_edge(self.every(source), self.unknown(target))

    def copy_items(self, source, target):
        """Copy the items of the dict `source` to the dict `target`, key by
        key."""
        self.copy_fields(source, target)
        self.add_edge(self.keys(source), self.keys(target))

    # Constraints that the builder states

    def add_subscript(self, base, key, dst, src, caller, site, delete=False):
        """dst ⊇ base[key] (if `dst`), base[key] ⊇ src (if `src`), and
        `del base[key]` (if `delete`)."""
        subscript = _Subscript(self, key, dst, src, delete, caller, site)
        self.solver.attach(base, subscript)

    def add_slice(self, base, bounds, dst, src, caller, site, delete=False):
        """dst ⊇ base[start:stop] (if `dst`); base[start:stop] = src (if
        `src`); `del base[start:stop]` (if `delete`). `bounds` is
        `(start, stop)` with constant ints or None, or None if they are not
        constant or the slice has a step."""
        slice_ = _Slice(self, bounds, dst, src, delete, caller, site)
        self.solver.attach(base, slice_)

    def add_unpack(self, value, before, starred, after, caller, site):
        """Unpack `value` into the target nodes `before`, a starred target
        (None if there is none) and `after`."""
        unpack = _Unpack(self, before, starred, after, caller, site)
        self.solver.attach(value, unpack)

    def add_iteration(self, iterable, dst, caller, site, is_async=False):
        """dst ⊇ the elements that iterating over `iterable` gives (with
        `async for` if `is_async`)."""
        iteration = _Iterate(self, dst, caller, site, is_async, role="for")
        self.solver.attach(iterable, iteration)

    def iterated(self, iterable, construct, caller, site):
        """A node with what iterating over the node `iterable` gives, made
        once for `construct` (an operator, a slice, or the arguments of a
        call bound to a model), which always iterates the same node. Each
        container that the construct extends gets an edge from it, so many
        containers and many iterables cost their sum."""
        found = self._iterated.get(construct)
        if found is None:
            node = self.node()
            self._iterated[construct] = (iterable, node)
            self.add_iteration(iterable, node, caller, site)
            return node
        iterated, node = found
        # The cache keeps the first iterable: a construct that iterated
        # another node would lose what it holds.
        assert iterated is iterable, f"{construct!r} iterates another node"
        return node

    def iteration(self, dst, caller, site, unless=(), role="iterate"):
        """A constraint that adds to `dst` what iterating over each object
        gives (see `iterate` for `unless`); `role` tells apart the
        iterations of one construct (see `site_call`)."""
        return _Iterate(self, dst, caller, site, unless=unless, role=role)

    def add_next(self, iterator, dst, caller, site):
        """dst ⊇ next(iterator)"""
        iteration = _Iterate(self, dst, caller, site, role="next")
        each = Each(self.next_element, iteration, results=(dst,))
        self.solver.attach(iterator, each)

    def add_iter(self, iterable, dst, caller, site):
        """dst ⊇ iter(iterable)"""
        iteration = _Iterate(self, dst, caller, site, role="iter")
        self.solver.attach(iterable, Each(self._iter, iteration, dst, results=(dst,)))

    def _iter(self, obj, iteration, dst):
        """iter() of an exact collection is another object: its iterator
        (see `container_iterator`)."""
        if (
            isinstance(obj, Container)
            and obj.exact
            and builtin_kind(obj.kind) in COLLECTIONS
        ):
            obj = self.container_iterator(obj)
        self.iterator(obj, iteration, dst)

    def container_iterator(self, container):
        """The iterator that iter() makes of the exact container
        `container`, one per container: a container of kind
        `<kind>_iterator` (`list_iterator`), exactly of that class, a builtin
        class below `object` that the stubs do not have, whose elements are
        what iterating over `container` gives."""
        kind = f"{builtin_kind(container.kind)}_iterator"
        key = (kind, container, "iter", True)
        iterator = self._containers.get(key)
        if iterator is None:
            iterator = Container(kind, "", exact=True)
            iterator.name = f"{kind}@{container.name.partition('@')[2]}"
            self._containers[key] = iterator
            self.add_edge(self.elements(container), self.unknown(iterator))
        return iterator

    def add_yield_from(self, iterable, function, dst, caller, site):
        """`dst = yield from iterable` in the generator function `function`:
        it yields the elements of `iterable`, values sent to it go to an
        inner generator, and `dst` gets the value that the inner generator
        returns."""
        self.add_iteration(iterable, function.yield_node, caller, site)
        each = Each(self._yield_from, function, dst, results=(dst,))
        self.solver.attach(iterable, each)

    def _yield_from(self, obj, function, dst):
        if isinstance(obj, Generator):
            self.add_edge(function.sent_node, obj.function.sent_node)
            if dst is not None:
                self.add_edge(obj.function.return_node, dst)

    def add_dict_items(self, target, source, caller, site):
        """Add to the dict `target` the items of each mapping, or iterable of
        (key, value) pairs, that `source` holds."""
        self.solver.attach(source, _DictItems(self, target, caller, site))

    def add_elements(self, target, source, caller, site):
        """Add to `target` the elements of each iterable that `source` holds,
        at their positions where both are sequences."""
        iteration = _Iterate(self, self.unknown(target), caller, site, role="elements")
        self.solver.attach(
            source,
            Each(self._copy_elements, target, iteration, results=(iteration.dst,)),
        )

    def _copy_elements(self, obj, target, iteration):
        if (
            isinstance(obj, Container)
            and obj.kind in SEQUENCES
            and target.kind in SEQUENCES
        ):
            self.copy_range(obj, target, (0, None))
        else:
            iteration.apply(obj)

    # Rules applied to each object

    def apply_subscript(self, obj, subscript):
        if isinstance(obj, Container):
            self.read_keyed(obj, subscript.key, subscript.dst)
            self.write_keyed(obj, subscript.key, subscript.src)
            if is_dict(obj) and subscript.key is not None:
                # A read, a store and a deletion all look the key up.
                stored = self.keys(obj)
                self.add_hash(subscript.key, subscript.caller, subscript.site, stored)
            if obj.factory is not None and subscript.dst is not None:
                self.call_factory(obj, subscript)
        elif isinstance(obj, (Instance, Class)):
            self.subscript_object(obj, subscript, subscript.key)
        elif isinstance(obj, Typed):
            origin = (subscript.caller, subscript.site, "subscript")
            self.typed_special(obj, "__getitem__", subscript.dst, origin)
        elif isinstance(obj, External) and subscript.dst is not None:
            # An element of an external is named like the external.
            self.add_object(subscript.dst, obj)

    def call_factory(self, container, subscript):
        """A read `d[k]` of the defaultdict `container` calls its factories
        for a missing key (`__missing__` does), without arguments: implicit
        calls from the scope of the read, whose results are values of
        `container`. A key may always be missing. One call per read joins
        the factories of every defaultdict that the read reaches and gives
        its result to all of them, so that the calls, and what they make,
        are as many as the reads (see *Termination*)."""
        role = ("subscript", "factory")
        call = self.site_call(subscript.caller, subscript.site, role)
        self.add_edge(container.factory, self._callee(call))
        self.add_edge(call.dst, self.unknown(container))

    def subscript_object(self, obj, subscript, key):
        """Call `__getitem__`, `__setitem__` or `__delitem__` of the
        instance or class `obj` for `subscript`, whose key node is `key`. A
        read of an instance also calls `__missing__` where no analysed class
        defines `__getitem__` (dict's runs; the analysis does not check that
        the class is a dict); a read of a class calls its
        `__class_getitem__` where no metaclass defines `__getitem__` (see
        `_metaclass_subscript`)."""
        if subscript.dst is not None:
            call = subscript.call("__getitem__", [key])
            self.call_dunder(obj, "__getitem__", call, subscript.dst)
            if isinstance(obj, Class):
                each = Each(
                    self._metaclass_subscript,
                    obj,
                    subscript,
                    key,
                    results=(subscript.dst,),
                )
                self.solver.attach(self._types(obj), each)
            else:
                # dict.__getitem__ calls the `__missing__` of a subclass for
                # a key it does not have.
                missing = ("__getitem__",)
                self.call_dunder(obj, "__missing__", call, subscript.dst, missing)
        if subscript.src is not None:
            call = subscript.call("__setitem__", [key, subscript.src])
            self.call_dunder(obj, "__setitem__", call, None)
        if subscript.delete:
            call = subscript.call("__delitem__", [key])
            self.call_dunder(obj, "__delitem__", call, None)

    def _metaclass_subscript(self, meta, cls, subscript, key):
        """`cls[key]` calls the `__class_getitem__` of `cls` where its
        metaclass `meta` defines no `__getitem__` (see
        `_class_subscript`)."""
        if isinstance(meta, Class):
            python = self.python_method(meta, "__getitem__")
            each = Each(
                self._class_subscript, cls, subscript, key, results=(subscript.dst,)
            )
            self.solver.attach(python, each)
            return
        for definition in self.stub_definitions(meta) or ():
            if definition.kind == "class":
                if self.stubs.member(definition.path, "__getitem__"):
                    return
        self._class_subscript(None, cls, subscript, key)

    def _class_subscript(self, python_method, cls, subscript, key):
        """`cls[key]` calls `__class_getitem__` of `cls`, a class method,
        with the key node `key`, and gives what it returns. Where no
        analysed class defines it, an outside base's (`typing.Generic`'s)
        makes a generic alias, which calls and loads through the class:
        the subscript gives the class itself (see `python_method`)."""
        key_of = (cls, subscript, "class subscript")
        if key_of in self._subscriptions:
            return
        self._subscriptions.add(key_of)
        call = subscript.call("__class_getitem__", [key])
        self.add_edge(call.dst, subscript.dst)
        method = self.lookup(cls, "__class_getitem__", cls)
        self.solver.attach(method, Each(self._class_getitem, call, results=(call.dst,)))
        alias = self.python_method(cls, "__class_getitem__")
        self.solver.attach(
            alias,
            Each(self._generic_alias, cls, subscript.dst, results=(subscript.dst,)),
        )

    def _class_getitem(self, method, call):
        if not isinstance(method, (External, Typed)):
            self.call(method, call)

    def _generic_alias(self, python_method, cls, dst):
        self.add_object(dst, cls)

    def apply_slice(self, obj, slice_):
        if isinstance(obj, (Instance, Class)):
            # The key is a slice object, which the analysis does not track.
            self.subscript_object(obj, slice_, None)
        elif isinstance(obj, Container) and obj.kind in SEQUENCES:
            if slice_.dst is not None:
                # A subclass may override `__getitem__`: the slice of a
                # container of a declared type is not exact.
                exact = obj.exact
                result = self.container_at(
                    obj.kind, slice_, slice_.site, "slice", exact=exact
                )
                self.copy_range(obj, result, slice_.bounds)
                self.add_object(slice_.dst, result)
            if slice_.src is not None:
                elements = self.iterated(slice_.src, slice_, slice_.caller, slice_.site)
                self.add_edge(elements, self.unknown(obj))
        elif isinstance(obj, Typed):
            origin = (slice_.caller, slice_.site, "slice")
            self.typed_special(obj, "__getitem__", slice_.dst, origin)
        elif isinstance(obj, External) and slice_.dst is not None:
            self.add_object(slice_.dst, obj)

    def apply_unpack(self, obj, unpack):
        if isinstance(obj, Container) and obj.kind in SEQUENCES:
            for index, dst in enumerate(unpack.before):
                self.read_key(self.const(index), obj, dst)
            count = len(unpack.after)
            for index, dst in enumerate(unpack.after):
                self.read_key(self.const(index - count), obj, dst)
            if unpack.starred is not None:
                bounds = (len(unpack.before), -count or None)
                self.copy_range(obj, unpack.rest(), bounds)
        else:
            unpack.iteration().apply(obj)

    def combine(self, obj, operation, is_left):
        """Concatenation (`+`) and repetition (`*`) of a list or tuple `obj`,
        an operand of `operation`. `xs += ys` changes the list `xs` in
        place. Otherwise the result is a new container: the elements of the
        left operand of `+` keep their positions, the others have unknown
        ones."""
        if obj.kind not in SEQUENCES or operation.method not in ("__add__", "__mul__"):
            return
        site = operation.site
        concatenation = operation.method == "__add__"
        if operation.inplace and not is_left:
            # The left operand of an in-place operator decides the result.
            return
        if operation.inplace and obj.kind == "list":
            result = obj
        else:
            # Not exact: a subclass operand may override `__add__` or
            # `__mul__`, or `__radd__` and `__rmul__`, which run first.
            result = self.container_at(obj.kind, operation, site, "operator")
            if is_left and concatenation:
                self.copy_fields(obj, result)
            else:
                self.add_edge(self.every(obj), self.unknown(result))
        if operation.inplace and concatenation and operation.right is not None:
            elements = self.iterated(operation.right, operation, operation.caller, site)
            self.add_edge(elements, self.unknown(result))
            if obj.kind == "list":
                # `xs += ys` is `xs.extend(ys)`: it asks the length of ys.
                self.add_length_hint(operation.right, operation.caller, site)
        if operation.dst is not None:
            self.add_object(operation.dst, result)

    def copy_fields(self, source, target):
        """Copy every field of `source` to the same field of `target`, now
        and when it is added. Once per pair: many sites copy the same
        container to the same place (pydantic: half of 191,000 copies), and
        each copy would add the same edges again for every field."""
        pair = (source, target, "copy fields")
        if pair in self._subscriptions:
            return
        self._subscriptions.add(pair)

        fields = target.fields
        add_edge = self.solver.add_edge

        def copy_field(key, node):
            add_edge(node, fields.get(key) or self.element(target, key))

        self.observe(source, copy_field)
        self.add_edge(self.unknown(source), self.unknown(target))
        if is_dict(source) and is_dict(target):
            self.add_edge(self.aliased(source), self.aliased(target))

    def iterate(self, obj, iteration):
        """Add to the result of `iteration` what iterating over `obj`
        gives: what `next()` gives on each iterator that `iter()` gives on
        `obj` (see `iterator` and `next_element`)."""
        self.iterator(obj, iteration, iteration.iterators())

    def iterator(self, obj, iteration, dst):
        """Add to `dst` what `iter()` on `obj` gives (`aiter()` for an async
        iteration); every iteration goes through here. A container, a
        generator or an external is its own iterator. An instance or class
        gives what its `__iter__` returns, or, if its type defines no
        `__iter__` but `__getitem__`, an iterator whose `next()` calls
        `__getitem__` (the sequence protocol). `iteration.unless` lists
        methods that, where a class defines them, make Python use them
        instead (`__contains__` for `in`). A typed value gives what its
        class's `__iter__` returns."""
        if isinstance(obj, Typed):
            name = "__aiter__" if iteration.is_async else "__iter__"
            origin = (iteration.caller, iteration.site, iteration.role)
            self.typed_special(obj, name, dst, origin)
            return
        if not isinstance(obj, (Instance, Class)):
            if isinstance(obj, (Container, Generator, External)):
                self.add_object(dst, obj)
            return
        name = "__aiter__" if iteration.is_async else "__iter__"
        self.call_dunder(obj, name, iteration.call(), dst, iteration.unless)
        if not iteration.is_async:
            sequence = Each(self._sequence_type, obj, iteration, dst, results=(dst,))
            self.solver.attach(self._types(obj), sequence)

    def _sequence_type(self, cls, obj, iteration, dst):
        """The sequence protocol: `obj` is iterated through `__getitem__`
        where its type `cls`, an analysed class, defines no `__iter__` but
        `__getitem__`."""
        if isinstance(cls, Class):
            unless = ("__iter__", *iteration.unless)
            found = self.lookup(cls, "__getitem__", obj, None, unless)
            each = Each(self._sequence_iterator, obj, iteration, dst, results=(dst,))
            self.solver.attach(found, each)

    def _sequence_iterator(self, method, obj, iteration, dst):
        origin = (iteration.caller, iteration.site, iteration.role)
        iterator = self.container_at("iterator", origin, iteration.site, "iterate")
        self.add_object(self.iterator_source(iterator), obj)
        self.add_object(dst, iterator)

    def iterator_source(self, iterator):
        """The node of what an iterator that `iter()` makes iterates over:
        the sequences of an `iterator`, the callables of a
        `callable_iterator`, the sequences of a `reversed` object. It is the
        node that holds the keys of a dict."""
        return self.keys(iterator)

    def next_element(self, obj, iteration):
        """Add to the result of `iteration` what `next()` on the iterator
        `obj` gives. The calls that it makes come from the scope that
        iterates."""
        match obj:
            case Instance() | Class() if iteration.is_async:
                # `async for` awaits what `__anext__` returns.
                self.call_dunder(obj, "__anext__", iteration.call(), iteration.anext())
            case Instance() | Class():
                self.call_dunder(obj, "__next__", iteration.call(), iteration.dst)
            case Container() if obj in self._library and not iteration.is_async:
                # A lazy object of a standard-library operation: it advances
                # its sources from here (see library.py).
                self.advance_library(obj, iteration)
            case Container(kind="iterator"):
                # The sequence protocol: __getitem__ with an unknown index.
                next_item = Each(self._next_item, iteration, results=(iteration.dst,))
                self.solver.attach(self.iterator_source(obj), next_item)
            case Container(kind="callable_iterator"):
                # iter(callable, sentinel): next() calls the callable.
                self.solver.attach(self.iterator_source(obj), iteration.callable_call())
            case Container():
                self.add_edge(self.elements(obj), iteration.dst)
            case Generator():
                self.add_edge(obj.function.yield_node, iteration.dst)
            case Typed() if iteration.is_async:
                origin = (iteration.caller, iteration.site, iteration.role)
                self.typed_special(obj, "__anext__", iteration.anext(), origin)
            case Typed():
                origin = (iteration.caller, iteration.site, iteration.role)
                self.typed_special(obj, "__next__", iteration.dst, origin)
            case External():
                # An element of an external is named like the external.
                self.add_object(iteration.dst, obj)

    def _next_item(self, obj, iteration):
        self.call_dunder(obj, "__getitem__", iteration.index_call(), iteration.dst)

    def apply_dict_items(self, obj, items):
        if isinstance(obj, Container) and is_dict(obj):
            self.copy_items(obj, items.target)
            if not keeps_mapping_hashes(obj):
                stored = self.keys(items.target)
                self.add_hash(self.keys(obj), items.caller, items.site, stored)
        else:
            items.pairs().apply(obj)


class _Keyed(Constraint):
    """Reads or writes, with `access` (`read_key` or `write_key`), the
    elements of `container` that each key object selects. A constant or a
    pattern selects its own; every other key selects all elements, so only
    the first one acts. A read puts what it selects in `result`; a
    saturated key selects nothing, and the read gives the saturated
    value."""

    __slots__ = ("access", "container", "node", "other_key", "result")

    def __init__(self, access, container, node, result):
        self.access = access
        self.container = container
        self.node = node
        self.other_key = False
        self.result = result

    def results(self):
        return (self.result,)

    def apply(self, key):
        if isinstance(key, TypeForm):
            # A type alias, which selects no element.
            return
        if not isinstance(key, (Const, Pattern)):
            if self.other_key:
                return
            self.other_key = True
        self.access(key, self.container, self.node)


class _Site(Constraint):
    """A constraint at a site in the scope named `caller`."""

    __slots__ = ("analysis", "caller", "site")

    def __init__(self, analysis, caller, site):
        self.analysis = analysis
        self.caller = caller
        self.site = site


class _Access(_Site):
    """A subscript or a slice: a load into `dst`, a store from `src`, a
    deletion. `call(name, args)` is the implicit call of the special method
    `name` of instances."""

    __slots__ = ("dst", "src", "delete", "_calls")

    def __init__(self, analysis, dst, src, delete, caller, site):
        super().__init__(analysis, caller, site)
        self.dst = dst
        self.src = src
        self.delete = delete
        self._calls = {}

    def call(self, name, args):
        if name not in self._calls:
            self._calls[name] = self.analysis.site_call(
                self.caller, self.site, ("subscript", name), args
            )
        return self._calls[name]


class _Subscript(_Access):
    __slots__ = ("key",)

    def __init__(self, analysis, key, dst, src, delete, caller, site):
        super().__init__(analysis, dst, src, delete, caller, site)
        self.key = key

    def apply(self, obj):
        self.analysis.apply_subscript(obj, self)

    def results(self):
        return (self.dst,)


class _Slice(_Access):
    __slots__ = ("bounds",)

    def __init__(self, analysis, bounds, dst, src, delete, caller, site):
        super().__init__(analysis, dst, src, delete, caller, site)
        self.bounds = bounds

    def apply(self, obj):
        self.analysis.apply_slice(obj, self)

    def results(self):
        return (self.dst,)


class _Unpack(_Site):
    """Unpacks into target nodes. Values that are not sequences are iterated
    once per site; every target gets all their elements."""

    __slots__ = ("before", "starred", "after", "_rest", "_iteration")

    def __init__(self, analysis, before, starred, after, caller, site):
        super().__init__(analysis, caller, site)
        self.before = before
        self.starred = starred
        self.after = after
        self._rest = None
        self._iteration = None

    def rest(self):
        """The list that the starred target gets."""
        if self._rest is None:
            origin = (self.caller, self.site, "rest")
            self._rest = self.analysis.container_at(
                "list", origin, self.site, "rest", exact=True
            )
            self.analysis.add_object(self.starred, self._rest)
        return self._rest

    def iteration(self):
        if self._iteration is None:
            analysis = self.analysis
            elements = analysis.node()
            for dst in self.before + self.after:
                analysis.add_edge(elements, dst)
            if self.starred is not None:
                analysis.add_edge(elements, analysis.unknown(self.rest()))
            self._iteration = _Iterate(
                analysis, elements, self.caller, self.site, role="unpack"
            )
            if self.starred is not None:
                # The starred target makes a list of the rest of the
                # iterator, which asks the iterator's length.
                iterators = self._iteration.iterators()
                analysis.add_length_hint(iterators, self.caller, self.site)
        return self._iteration

    def apply(self, obj):
        self.analysis.apply_unpack(obj, self)

    def results(self):
        return (*self.before, *self.after, self.starred)


class _KeyLookup:
    """A lookup in a dict: the `__eq__` of each stored key (an instance or
    class) that is another object than a looked-up key (any object),
    decided in time linear in the keys: once two looked-up objects are
    known, every stored key is another. `compared` holds the stored keys
    whose `__eq__` the construct has called with `call`: the lookups of one
    construct (one per dict that reaches it) share the call, so each stored
    key is called once for all of them."""

    __slots__ = ("analysis", "call", "compared", "first", "many", "stored_keys")

    def __init__(self, analysis, call, compared):
        self.analysis = analysis
        self.call = call
        self.compared = compared
        self.first = None
        self.many = False
        self.stored_keys = []

    def key(self, obj):
        if self.many or obj is self.first:
            return
        if self.first is None:
            self.first = obj
            compared = [s for s in self.stored_keys if s is not obj]
        else:
            self.many = True
            compared = self.stored_keys
        for stored in compared:
            self.analysis.solver.revisit(self._compare, stored)

    def stored(self, instance):
        self.stored_keys.append(instance)
        if self.many or (self.first is not None and instance is not self.first):
            self._compare(instance)

    def _compare(self, stored):
        if stored not in self.compared:
            self.compared.add(stored)
            self.analysis.call_dunder(stored, "__eq__", self.call, None)


class _Iterate(_Site):
    """An iteration whose elements go to `dst`. The iterators that the
    `__iter__` of instances return are in `iterators()`; `call()` is the
    implicit call of the special methods."""

    __slots__ = (
        "dst",
        "is_async",
        "unless",
        "role",
        "_iterators",
        "_call",
        "_index_call",
        "_callable_call",
        "_anext",
    )

    def __init__(
        self, analysis, dst, caller, site, is_async=False, unless=(), role="iterate"
    ):
        super().__init__(analysis, caller, site)
        self.dst = dst
        self.is_async = is_async
        self.unless = unless
        # Tells apart the iterations of one construct (see `site_call`).
        self.role = (role, is_async, unless)
        self._iterators = None
        self._call = None
        self._index_call = None
        self._callable_call = None
        self._anext = None

    def call(self):
        if self._call is None:
            role = ("iterate", self.role)
            self._call = self.analysis.site_call(self.caller, self.site, role)
        return self._call

    def index_call(self):
        """The call of `__getitem__` with an index that is not known."""
        if self._index_call is None:
            self._index_call = self.analysis.site_call(
                self.caller, self.site, ("index", self.role), [None]
            )
        return self._index_call

    def callable_call(self):
        """The call of the callable of `iter(callable, sentinel)`, whose
        result is an element."""
        if self._callable_call is None:
            self._callable_call = self.analysis.site_call(
                self.caller, self.site, ("callable", self.role), dst=self.dst
            )
        return self._callable_call

    def anext(self):
        """The node of what `__anext__` returns, which an `async for`
        awaits to get an element."""
        if self._anext is None:
            self._anext = self.analysis.node()
            self.analysis.add_await(self._anext, self.dst, self.caller, self.site)
        return self._anext

    def iterators(self):
        if self._iterators is None:
            self._iterators = self.analysis.node()
            self.analysis.solver.attach(
                self._iterators,
                Each(self.analysis.next_element, self, results=(self.dst,)),
            )
        return self._iterators

    def apply(self, obj):
        self.analysis.iterate(obj, self)

    def results(self):
        return (self.dst,)


class _DictItems(_Site):
    __slots__ = ("target", "_pairs")

    def __init__(self, analysis, target, caller, site):
        super().__init__(analysis, caller, site)
        self.target = target
        self._pairs = None

    def pairs(self):
        """The iteration over (key, value) pairs, which are unpacked and
        stored in the target."""
        if self._pairs is None:
            analysis = self.analysis
            pairs, key, value = analysis.node(), analysis.node(), analysis.node()
            analysis.add_unpack(pairs, [key, value], None, [], self.caller, self.site)
            analysis.write_keyed(self.target, key, value)
            stored = analysis.keys(self.target)
            analysis.add_hash(key, self.caller, self.site, stored)
            self._pairs = _Iterate(
                analysis, pairs, self.caller, self.site, role="items"
            )
        return self._pairs

    def apply(self, obj):
        self.analysis.apply_dict_items(obj, self)
