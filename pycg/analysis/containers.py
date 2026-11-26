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

SEQUENCES = ("list", "tuple")

COLLECTIONS = ("list", "tuple", "set", "frozenset", "dict")

HASHED = ("set", "frozenset", "dict")


def is_dict(container):
    return builtin_kind(container.kind) == "dict"


def hashes_keys(container):
    return builtin_kind(container.kind) in HASHED


def keeps_hashes(container):
    return container.kind in HASHED


def keeps_mapping_hashes(container):
    return is_dict(container) and container.kind != "collections.OrderedDict"


class Containers:
    def const(self, value):
        if value not in self._consts:
            self._consts[value] = Const(value)
        return self._consts[value]

    def container(self, kind, site, length=None):
        return Container(kind, site, length, exact=True)

    def container_at(self, kind, origin, site, rule, length=None, exact=False):
        key = (kind, origin, rule, exact)
        if key not in self._containers:
            self._containers[key] = Container(kind, site, length, exact)
        container = self._containers[key]
        assert container.length == length, f"{key!r} with another length"
        return container

    def inexact(self, obj):
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
            alias.every_element = self.every(container)
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
        self.solver.attach(src, Each(self._add_inexact, dst, results=(dst,)))

    def _add_inexact(self, obj, dst):
        self.add_object(dst, self.inexact(obj))

    def add_class_member(self, value, field):
        self.add_inexact(value, field)

    def element(self, container, key):
        node = container.fields.get(key)
        if node is None:
            node = self.node(f"{container.name}[{constant_name(key)}]")
            container.fields[key] = node
            if container.every_element is not None:
                self.add_edge(node, container.every_element)
            for observer in list(container.observers):
                self._notify(observer, key, node)
        return node

    def unknown(self, container):
        if container.unknown is None:
            container.unknown = self.node(f"{container.name}[?]")
            if container.every_element is not None:
                self.add_edge(container.unknown, container.every_element)
        return container.unknown

    def every(self, container):
        if container.every_element is None:
            container.every_element = self.node()
            for node in container.fields.values():
                self.add_edge(node, container.every_element)
            if container.unknown is not None:
                self.add_edge(container.unknown, container.every_element)
        return container.every_element

    def keys(self, container):
        if container.keys is None:
            container.keys = self.node(f"{container.name}.<keys>")
        return container.keys

    def aliased(self, container):
        if container.aliased is None:
            container.aliased = self.node(f"{container.name}.<aliased>")
        return container.aliased

    def factory(self, container):
        if container.factory is None:
            container.factory = self.node(f"{container.name}.<factory>")
        return container.factory

    def elements(self, container):
        if is_dict(container):
            return self.keys(container)
        return self.every(container)

    def observe(self, container, observer):
        container.observers.append(observer)
        for key, node in list(container.fields.items()):
            self._notify(observer, key, node)

    def _notify(self, observer, key, node):
        notices = self._notices
        if self._notifying:
            notices.append((observer, key, node))
            return
        self._notifying = True
        try:
            if notices:
                notices.append((observer, key, node))
            else:
                observer(key, node)
            while notices:
                observer, key, node = notices.popleft()
                observer(key, node)
        finally:
            self._notifying = False

    def _field_key(self, container, key):
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
        if isinstance(key, Const):
            position = self._field_key(container, key.value)
            if position is not None:
                self.add_edge(self.element(container, position), dst)
                self.add_edge(self.unknown(container), dst)
                return
        elif isinstance(key, Pattern) and key.exact and is_dict(container):
            self._read_pattern(key, container, dst)
            return
        self.add_edge(self.every(container), dst)

    def _read_pattern(self, pattern, container, dst):
        self.add_edge(self.unknown(container), dst)
        self.add_edge(self.aliased(container), dst)

        def read_field(key, node):
            if isinstance(key, str) and pattern.matches(key) is not None:
                self.add_edge(node, dst)

        self.observe(container, read_field)

    def write_key(self, key, container, src):
        if isinstance(key, Const):
            position = self._field_key(container, key.value)
            if position is not None:
                self.add_edge(src, self.element(container, position))
                if not key.exact and is_dict(container):
                    self.add_edge(src, self.aliased(container))
                return
        self.add_edge(src, self.unknown(container))

    def add_hash(self, key, caller, site, stored=None):
        call = self.site_call(caller, site, ("hash",))
        self.add_special_call(key, "__hash__", call)
        if stored is not None:
            self._compare_keys(key, caller, site, stored)

    def _compare_keys(self, key, caller, site, stored):
        pairing = self._key_lookup(caller, site)
        self.solver.attach(key, Each(pairing.key))
        self.solver.attach(stored, Each(pairing.stored, kinds=(Instance, Class)))

    def _subscript_keyed(self, container, subscript):
        key, dst, src = subscript.key, subscript.dst, subscript.src
        if dst is not None:
            if subscript.reads is None:
                subscript.reads = _KeyedGroup(self.read_key, dst, dst)
                self.solver.attach(key, subscript.reads)
            subscript.reads.add(container)
            self._keyed.append((key, container, dst, True))
        if is_dict(container):
            self.add_edge(key, self.keys(container))
        if src is not None:
            if subscript.writes is None:
                subscript.writes = _KeyedGroup(self.write_key, src, None)
                self.solver.attach(key, subscript.writes)
            subscript.writes.add(container)
            self._keyed.append((key, container, src, False))

    def _key_lookup(self, caller, site):
        compare = self.site_call(caller, site, ("hash_eq",), [None])
        compared = self._compared_keys.setdefault(compare, set())
        return _KeyLookup(self, compare, compared)

    def _hash_subscript_key(self, subscript, stored):
        key = (subscript.key, subscript.caller, subscript.site)
        pairing = self._subscript_keys.get(key)
        if pairing is None:
            call = self.site_call(subscript.caller, subscript.site, ("hash",))
            self.add_special_call(subscript.key, "__hash__", call)
            pairing = self._key_lookup(subscript.caller, subscript.site)
            self._subscript_keys[key] = pairing
            self.solver.attach(subscript.key, Each(pairing.key))
        self.solver.attach(stored, Each(pairing.stored, kinds=(Instance, Class)))

    def key_store(self, container):
        return self.keys(container) if is_dict(container) else self.unknown(container)

    def add_keys(self, target, source, construct, caller, site, keeps=keeps_hashes):
        hashed, kept = self.entering_keys(source, construct, caller, site, keeps)
        self.add_edge(hashed, self.key_store(target))
        self.add_edge(kept, self.key_store(target))
        self.add_hash(hashed, caller, site, self.elements(target))

    def entering_keys(self, source, construct, caller, site, keeps=keeps_hashes):
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
        if dst is None:
            return
        if key is None:
            self.add_edge(self.every(container), dst)
            return
        self.solver.attach(key, _Keyed(self.read_key, container, dst, dst))
        self._keyed.append((key, container, dst, True))

    def write_keyed(self, container, key, src):
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
        self.copy_fields(source, target)
        self.add_edge(self.keys(source), self.keys(target))

    def add_subscript(self, base, key, dst, src, caller, site, delete=False):
        subscript = _Subscript(self, key, dst, src, delete, caller, site)
        self.solver.attach(base, subscript)

    def add_slice(self, base, bounds, dst, src, caller, site, delete=False):
        slice_ = _Slice(self, bounds, dst, src, delete, caller, site)
        self.solver.attach(base, slice_)

    def add_unpack(self, value, before, starred, after, caller, site):
        unpack = _Unpack(self, before, starred, after, caller, site)
        self.solver.attach(value, unpack)

    def add_iteration(self, iterable, dst, caller, site, is_async=False):
        iteration = _Iterate(self, dst, caller, site, is_async, role="for")
        self.solver.attach(iterable, iteration)

    def iterated(self, iterable, construct, caller, site):
        found = self._iterated.get(construct)
        if found is None:
            node = self.node()
            self._iterated[construct] = (iterable, node)
            self.add_iteration(iterable, node, caller, site)
            return node
        iterated, node = found
        assert iterated is iterable, f"{construct!r} iterates another node"
        return node

    def iteration(self, dst, caller, site, unless=(), role="iterate"):
        return _Iterate(self, dst, caller, site, unless=unless, role=role)

    def add_next(self, iterator, dst, caller, site):
        iteration = _Iterate(self, dst, caller, site, role="next")
        each = Each(self.next_element, iteration, results=(dst,))
        self.solver.attach(iterator, each)

    def add_iter(self, iterable, dst, caller, site):
        iteration = _Iterate(self, dst, caller, site, role="iter")
        self.solver.attach(iterable, Each(self._iter, iteration, dst, results=(dst,)))

    def _iter(self, obj, iteration, dst):
        if (
            isinstance(obj, Container)
            and obj.exact
            and builtin_kind(obj.kind) in COLLECTIONS
        ):
            obj = self.container_iterator(obj)
        self.iterator(obj, iteration, dst)

    def container_iterator(self, container):
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
        self.add_iteration(iterable, function.yield_node, caller, site)
        each = Each(self._yield_from, function, dst, results=(dst,))
        self.solver.attach(iterable, each)

    def _yield_from(self, obj, function, dst):
        if isinstance(obj, Generator):
            self.add_edge(function.sent_node, obj.function.sent_node)
            self.add_edge(obj.function.return_node, dst)

    def add_dict_items(self, target, source, caller, site):
        hub = self._dict_hubs.get(source)
        if hub is None:
            hub = self._dict_hubs[source] = _DictHub(
                Container("dict", site), self.node()
            )
        self.solver.attach(source, _DictItems(self, target, hub, caller, site))

    def add_elements(self, target, source, caller, site):
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

    def apply_subscript(self, obj, subscript):
        if isinstance(obj, Const):
            obj = self.string_constant_value(obj)
            if obj is None:
                return
        if isinstance(obj, Container):
            if subscript.key is None:
                self.read_keyed(obj, None, subscript.dst)
                self.write_keyed(obj, None, subscript.src)
            else:
                self._subscript_keyed(obj, subscript)
            if is_dict(obj) and subscript.key is not None:
                self._hash_subscript_key(subscript, self.keys(obj))
            if obj.factory is not None and subscript.dst is not None:
                self.call_factory(obj, subscript)
        elif isinstance(obj, (Instance, Class)):
            self.subscript_object(obj, subscript, subscript.key)
        elif isinstance(obj, Typed):
            origin = (subscript.caller, subscript.site, "subscript")
            self.typed_special(obj, "__getitem__", subscript.dst, origin)
        elif isinstance(obj, External) and subscript.dst is not None:
            self.add_object(subscript.dst, obj)

    def call_factory(self, container, subscript):
        role = ("subscript", "factory")
        call = self.site_call(subscript.caller, subscript.site, role)
        self.add_edge(container.factory, self._callee(call))
        self.add_edge(call.dst, self.unknown(container))

    def subscript_object(self, obj, subscript, key):
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
                missing = ("__getitem__",)
                self.call_dunder(obj, "__missing__", call, subscript.dst, missing)
        if subscript.src is not None:
            call = subscript.call("__setitem__", [key, subscript.src])
            self.call_dunder(obj, "__setitem__", call, None)
        if subscript.delete:
            call = subscript.call("__delitem__", [key])
            self.call_dunder(obj, "__delitem__", call, None)

    def _metaclass_subscript(self, meta, cls, subscript, key):
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
        if isinstance(obj, Const):
            obj = self.string_constant_value(obj)
            if obj is None:
                return
        if isinstance(obj, (Instance, Class)):
            self.subscript_object(obj, slice_, None)
        elif isinstance(obj, Container) and obj.kind in SEQUENCES:
            if slice_.dst is not None:
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
        if obj.kind not in SEQUENCES or operation.method not in ("__add__", "__mul__"):
            return
        site = operation.site
        concatenation = operation.method == "__add__"
        if operation.inplace and not is_left:
            return
        if operation.inplace and obj.kind == "list":
            result = obj
        else:
            result = self.container_at(obj.kind, operation, site, "operator")
            if is_left and concatenation:
                self.copy_fields(obj, result)
            else:
                self.add_edge(self.every(obj), self.unknown(result))
        if operation.inplace and concatenation and operation.right is not None:
            elements = self.iterated(operation.right, operation, operation.caller, site)
            self.add_edge(elements, self.unknown(result))
            if obj.kind == "list":
                self.add_length_hint(operation.right, operation.caller, site)
        self.add_object(operation.dst, result)

    def copy_fields(self, source, target):
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
        self.iterator(obj, iteration, iteration.iterators())

    def iterator(self, obj, iteration, dst):
        if isinstance(obj, Const):
            obj = self.string_constant_value(obj)
            if obj is None:
                return
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
        if isinstance(cls, Class):
            key = (cls, type(obj), iteration, dst)
            sequences = self._sequences.get(key)
            if sequences is None:
                sequences = _Sequences(self, iteration, dst)
                self._sequences[key] = sequences
            unless = ("__iter__", *iteration.unless)
            found = self.lookup(cls, "__getitem__", obj, None, unless)
            if found not in sequences.lookups:
                sequences.lookups[found] = None
                self.solver.attach(found, sequences)
            sequences.add(obj)

    def sequence_iterator(self, obj, iteration, dst):
        origin = (iteration.caller, iteration.site, iteration.role)
        iterator = self.container_at("iterator", origin, iteration.site, "iterate")
        self.add_object(self.iterator_source(iterator), obj)
        self.add_object(dst, iterator)

    def iterator_source(self, iterator):
        return self.keys(iterator)

    def next_element(self, obj, iteration):
        match obj:
            case Instance() | Class() if iteration.is_async:
                self.call_dunder(obj, "__anext__", iteration.call(), iteration.anext())
            case Instance() | Class():
                self.call_dunder(obj, "__next__", iteration.call(), iteration.dst)
            case Container() if obj in self._library and not iteration.is_async:
                self.advance_library(obj, iteration)
            case Container(kind="iterator"):
                next_item = Each(self._next_item, iteration, results=(iteration.dst,))
                self.solver.attach(self.iterator_source(obj), next_item)
            case Container(kind="callable_iterator"):
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
                self.add_object(iteration.dst, obj)

    def _next_item(self, obj, iteration):
        self.call_dunder(obj, "__getitem__", iteration.index_call(), iteration.dst)

    def apply_dict_items(self, obj, items):
        if not (isinstance(obj, Container) and is_dict(obj)):
            items.pairs().apply(obj)
            return
        hub, target, caller, site = items.hub, items.target, items.caller, items.site
        if obj not in hub.sources:
            hub.sources[obj] = None
            if hub.active:
                self._into_hub(hub, obj)
        if (target, caller, site) not in hub.targets:
            hub.targets[(target, caller, site)] = None
            if hub.active:
                self._out_of_hub(hub, target, caller, site)
        if hub.active:
            return
        if len(hub.sources) == 1:
            self.copy_items(obj, target)
            if not keeps_mapping_hashes(obj):
                self.add_hash(self.keys(obj), caller, site, self.keys(target))
            return
        hub.active = True
        for source in hub.sources:
            self._into_hub(hub, source)
        for target, caller, site in hub.targets:
            self._out_of_hub(hub, target, caller, site)

    def _into_hub(self, hub, source):
        self.copy_items(source, hub.container)
        if not keeps_mapping_hashes(source):
            self.add_edge(self.keys(source), hub.hashed)

    def _out_of_hub(self, hub, target, caller, site):
        if (caller, site) not in hub.sites:
            hub.sites.add((caller, site))
            call = self.site_call(caller, site, ("hash",))
            self.add_special_call(hub.hashed, "__hash__", call)
        self.copy_items(hub.container, target)
        self._compare_keys(hub.hashed, caller, site, self.keys(target))


class _Keyed(Constraint):
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
            return
        if not isinstance(key, (Const, Pattern)):
            if self.other_key:
                return
            self.other_key = True
        self.access(key, self.container, self.node)


class _KeyedGroup(Constraint):
    __slots__ = ("access", "node", "result", "containers", "keys", "other_keys")

    def __init__(self, access, node, result):
        self.access = access
        self.node = node
        self.result = result
        self.containers = []
        self.keys = []
        self.other_keys = set()

    def results(self):
        return (self.result,)

    def add(self, container):
        self.containers.append(container)
        for key in self.keys:
            self._pair(key, container)

    def apply(self, key):
        if isinstance(key, TypeForm):
            return
        self.keys.append(key)
        for container in list(self.containers):
            self._pair(key, container)

    def _pair(self, key, container):
        if not isinstance(key, (Const, Pattern)):
            if container in self.other_keys:
                return
            self.other_keys.add(container)
        self.access(key, container, self.node)


class _Sequences(Constraint):
    __slots__ = ("analysis", "iteration", "dst", "lookups", "objects", "found")

    def __init__(self, analysis, iteration, dst):
        self.analysis = analysis
        self.iteration = iteration
        self.dst = dst
        self.lookups = {}
        self.objects = []
        self.found = False

    def results(self):
        return (self.dst,)

    def apply(self, method):
        if not self.found:
            self.found = True
            for obj in list(self.objects):
                self._iterate(obj)

    def add(self, obj):
        self.objects.append(obj)
        if self.found:
            self._iterate(obj)

    def _iterate(self, obj):
        analysis = self.analysis
        solver = analysis.solver
        if solver.opaque and solver.opaque(obj):
            analysis.add_object(self.dst, analysis.saturated)
        else:
            analysis.sequence_iterator(obj, self.iteration, self.dst)


class _Site(Constraint):
    __slots__ = ("analysis", "caller", "site")

    def __init__(self, analysis, caller, site):
        self.analysis = analysis
        self.caller = caller
        self.site = site


class _Access(_Site):
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
    __slots__ = ("key", "reads", "writes")

    def __init__(self, analysis, key, dst, src, delete, caller, site):
        super().__init__(analysis, dst, src, delete, caller, site)
        self.key = key
        self.reads = None
        self.writes = None

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
    __slots__ = ("before", "starred", "after", "_rest", "_iteration")

    def __init__(self, analysis, before, starred, after, caller, site):
        super().__init__(analysis, caller, site)
        self.before = before
        self.starred = starred
        self.after = after
        self._rest = None
        self._iteration = None

    def rest(self):
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
                iterators = self._iteration.iterators()
                analysis.add_length_hint(iterators, self.caller, self.site)
        return self._iteration

    def apply(self, obj):
        self.analysis.apply_unpack(obj, self)

    def results(self):
        return (*self.before, *self.after, self.starred)


class _KeyLookup:
    __slots__ = (
        "analysis",
        "call",
        "compared",
        "first",
        "many",
        "stored_keys",
        "first_stored",
    )

    def __init__(self, analysis, call, compared):
        self.analysis = analysis
        self.call = call
        self.compared = compared
        self.first = None
        self.many = False
        self.stored_keys = {}
        self.first_stored = False

    def key(self, obj):
        if self.many or obj is self.first:
            return
        if self.first is None:
            self.first = obj
            stored_keys, self.stored_keys = self.stored_keys, None
            self.first_stored = obj in stored_keys
            for stored in stored_keys:
                if stored is not obj:
                    self.analysis.solver.revisit(self._compare, stored)
            return
        self.many = True
        if self.first_stored:
            self.analysis.solver.revisit(self._compare, self.first)

    def stored(self, instance):
        if self.first is None:
            self.stored_keys[instance] = None
        elif self.many or instance is not self.first:
            self._compare(instance)
        else:
            self.first_stored = True

    def _compare(self, stored):
        if stored not in self.compared:
            self.compared.add(stored)
            self.analysis.call_dunder(stored, "__eq__", self.call, None)


class _Iterate(_Site):
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
        if self._index_call is None:
            self._index_call = self.analysis.site_call(
                self.caller, self.site, ("index", self.role), [None]
            )
        return self._index_call

    def callable_call(self):
        if self._callable_call is None:
            self._callable_call = self.analysis.site_call(
                self.caller, self.site, ("callable", self.role), dst=self.dst
            )
        return self._callable_call

    def anext(self):
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


class _DictHub:
    __slots__ = ("container", "hashed", "sources", "targets", "sites", "active")

    def __init__(self, container, hashed):
        self.container = container
        self.hashed = hashed
        self.sources = {}
        self.targets = {}
        self.sites = set()
        self.active = False


class _DictItems(_Site):
    __slots__ = ("target", "hub", "_pairs")

    def __init__(self, analysis, target, hub, caller, site):
        super().__init__(analysis, caller, site)
        self.target = target
        self.hub = hub
        self._pairs = None

    def pairs(self):
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
