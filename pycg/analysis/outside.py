import json

from .builtin_models import (
    CALLS_BACK,
    CLOSURES,
    CONTAINER_CLASSES,
    HASHED_ARGUMENTS,
    ITERATOR,
    LAZY_MODES,
    LENGTH_HINTS,
    LIBRARY_ITERATION,
    OPENERS,
    REFLECTION_CALLS,
    VARIABLE_TYPES,
    builtin_kind,
    opened_class,
)
from .containers import hashes_keys
from .model import (
    BUILTIN_MODULE,
    Class,
    Closure,
    Const,
    Container,
    External,
    Generator,
    Instance,
    Signature,
    Typed,
    UnknownExternal,
    Wrapper,
)
from .solver import Each

STUB_BUILTINS = "builtins"
OBJECT = "builtins.object"
TYPE_CALL = "builtins.type.__call__"

KIND_CLASSES = {
    "generator": ("types.GeneratorType", "types.GeneratorType"),
    "async_generator": ("types.AsyncGeneratorType", "types.AsyncGeneratorType"),
    "dict_keys": ("_collections_abc.dict_keys", f"{BUILTIN_MODULE}.dict_keys"),
    "dict_values": ("_collections_abc.dict_values", f"{BUILTIN_MODULE}.dict_values"),
    "dict_items": ("_collections_abc.dict_items", f"{BUILTIN_MODULE}.dict_items"),
}

BUILTIN_CONTAINERS = {
    "builtins.list": "list",
    "builtins.tuple": "tuple",
    "builtins.set": "set",
    "builtins.frozenset": "frozenset",
    "builtins.dict": "dict",
}
ABSTRACT_ITERABLES = frozenset(
    {
        "typing.AbstractSet",
        "typing.AsyncGenerator",
        "typing.AsyncIterable",
        "typing.AsyncIterator",
        "typing.Collection",
        "typing.Generator",
        "typing.Iterable",
        "typing.Iterator",
        "typing.KeysView",
        "typing.MutableSequence",
        "typing.MutableSet",
        "typing.Reversible",
        "typing.Sequence",
        "typing.ValuesView",
    }
)
ABSTRACT_MAPPINGS = frozenset({"typing.Mapping", "typing.MutableMapping"})
AWAITED_PARAMETERS = {
    "typing.Awaitable": 0,
    "typing.Coroutine": 2,
    "typing.Generator": 2,
    "_asyncio.Future": 0,
    "_asyncio.Task": 0,
}
ELEMENT_PARAMETERS = ABSTRACT_ITERABLES | {
    "builtins.list",
    "builtins.set",
    "builtins.frozenset",
    "builtins.tuple",
}
ORDERING_COMPARISON_BY_BUILTIN = {
    "builtins.sorted": "__lt__",
    "builtins.list.sort": "__lt__",
    "builtins.min": "__lt__",
    "builtins.max": "__gt__",
}
REFLECTED_COMPARISONS = {
    "__lt__": "__gt__",
    "__gt__": "__lt__",
    "__le__": "__ge__",
    "__ge__": "__le__",
}
MRO_ENTRIES = {
    "typing.NamedTuple": "builtins.tuple",
    "typing.TypedDict": "builtins.dict",
    "typing_extensions.TypedDict": "builtins.dict",
}
TYPES_SAYING_NOTHING = frozenset({OBJECT})
STRING_CONSTANT_CLASSES = {str: "builtins.str", bytes: "builtins.bytes"}

FUNCTION_TYPES = frozenset(
    {
        "builtins.function",
        "types.BuiltinFunctionType",
        "types.ClassMethodDescriptorType",
        "types.FunctionType",
        "types.MethodDescriptorType",
        "types.MethodType",
        "types.MethodWrapperType",
        "types.WrapperDescriptorType",
    }
)


def stub_path(name):
    if name == BUILTIN_MODULE or name.startswith(f"{BUILTIN_MODULE}."):
        return STUB_BUILTINS + name[len(BUILTIN_MODULE) :]
    return name


def outside_name(path):
    if path == STUB_BUILTINS or path.startswith(f"{STUB_BUILTINS}."):
        return BUILTIN_MODULE + path[len(STUB_BUILTINS) :]
    return path


class Outside:
    def stub_definitions(self, external):
        name = external.name
        if name not in self._stub_definitions:
            result = None
            if not isinstance(external, UnknownExternal):
                path = stub_path(name)
                if self.stubs.module(path.partition(".")[0]) is not None:
                    result = self.stubs.find(path)
            self._stub_definitions[name] = result
        return self._stub_definitions[name]

    def imported_value(self, name):
        external = self.external(name)
        definitions = self.stub_definitions(external)
        values = [d for d in definitions or () if not _named(d)]
        if not values:
            return self.constant(external)
        node = self.node()
        for definition in definitions:
            if definition in values:
                context = _Context(origin=("attribute", definition.path))
                self.add_type(_variable_type(definition), node, context)
            else:
                self.add_object(node, external)
        return node

    def annotated_outside(self, external, dst, as_class, owner):
        for definition in self.stub_definitions(external) or ():
            if definition.kind != "class" or definition.path in TYPES_SAYING_NOTHING:
                continue
            if definition.path.partition(".")[0] in ("typing", "typing_extensions"):
                continue
            if as_class:
                self.add_object(dst, external)
            else:
                context = _Context(origin=("annotation", owner))
                self._add_instance(definition.path, (), dst, context, ())

    def mro_entry(self, base):
        for definition in self.stub_definitions(base) or ():
            replaced = MRO_ENTRIES.get(definition.path)
            if replaced is not None:
                return self.external(outside_name(self.stubs.public_name(replaced)))
            abc = self.stubs.abc_name(definition.path)
            if abc is not None and abc != base.name:
                return self.external(abc)
        return base

    def string_constant_value(self, const):
        cls = STRING_CONSTANT_CLASSES.get(type(const.value))
        return None if cls is None else self.typed(cls)

    def typed(self, cls):
        if cls not in self._typed:
            name = outside_name(self.stubs.public_name(cls))
            self._typed[cls] = Typed(cls, name, self.stubs.abstract(cls))
        return self._typed[cls]

    def closure(self, name, result):
        key = (name, json.dumps(result))
        if key not in self._closures:
            self._closures[key] = Closure(name, result)
        return self._closures[key]

    def call_closure(self, closure, call):
        self.add_external_call_edge(closure.name, call, "stub")
        if call.dst is None:
            return
        self.add_type(closure.result, call.dst, _Context(call))
        if call.decorator and call.args[-1] is not None:
            self.add_edge(call.args[-1], call.dst)

    def outside_attribute(self, external, attr, dst, definitions, bounded):
        named = False
        for definition in definitions:
            for found in self.stubs.attribute(definition, attr):
                if _named(found):
                    named = True
                else:
                    context = _Context(origin=("attribute", found.path))
                    if found.owner is not None and definition.kind == "class":
                        context.receivers = (external,)
                    self.add_type(_variable_type(found), dst, context)
        if named:
            if bounded:
                self._add_external_attribute(external, attr, dst, external.steps + 1)
            else:
                self.add_object(dst, self.unknown_external)

    def typed_attribute(self, typed, attr, dst):
        self.stub_member(typed, typed.cls, typed.name, attr, dst)

    def builtin_member(self, obj, kind, attr, dst):
        cls, prefix = self.kind_class(kind)
        self.stub_member(obj, cls, prefix, attr, dst)

    def kind_class(self, kind):
        if kind in KIND_CLASSES:
            return KIND_CLASSES[kind]
        if "." in kind:
            return kind, outside_name(self.stubs.public_name(kind))
        return f"{STUB_BUILTINS}.{kind}", f"{BUILTIN_MODULE}.{kind}"

    def stub_member(self, receiver, cls, prefix, attr, dst):
        for definition in self.stubs.member(cls, attr):
            name = f"{prefix}.{attr}"
            if definition.kind == "function":
                method = self.external(name, 1)
                decorator = definition.entry.get("d")
                if decorator == "staticmethod":
                    self.add_object(dst, method)
                elif decorator == "classmethod":
                    owner = self._class_object(receiver)
                    self.add_object(dst, self.bound_method(owner, method))
                else:
                    self.add_object(dst, self.bound_method(receiver, method))
            elif definition.kind == "class":
                self.add_object(dst, self.external(name, 1))
            else:
                origin = ("attribute", definition.path)
                context = _Context(origin=origin, receivers=(receiver,))
                self.add_type(definition.entry["t"], dst, context)

    def outside_base_member(self, base, attr, receiver, dst):
        found = False
        for definition in self.stub_definitions(base):
            if definition.kind != "class":
                continue
            members = self.stubs.member(definition.path, attr)
            for member in members:
                if member.owner != OBJECT:
                    found = True
                    self._deliver_base_member(member, base, attr, receiver, dst)
            if not members and isinstance(receiver, Class):
                for member in self.stubs.metaclass_member(definition.path, attr):
                    if member.kind == "function":
                        found = True
                        method = self.base_member_external(base, attr)
                        self.add_object(dst, self.bound_method(receiver, method))
        return found

    def object_member(self, classes, attr, receiver, dst):
        members = self.stubs.member(OBJECT, attr)
        if not members:
            return False
        through = next(
            (
                base
                for base in classes
                if isinstance(base, External)
                and self.stub_definitions(base) is not None
            ),
            None,
        )
        if through is None:
            through = self.external(outside_name(OBJECT))
        for member in members:
            self._deliver_base_member(member, through, attr, receiver, dst)
        return True

    def _deliver_base_member(self, member, base, attr, receiver, dst):
        instance = isinstance(receiver, Instance)
        if member.kind == "function":
            method = self.base_member_external(base, attr)
            decorator = member.entry.get("d")
            if decorator == "classmethod":
                owner = receiver.cls if instance else receiver
                self.add_object(dst, self.bound_method(owner, method))
            elif instance and decorator != "staticmethod":
                self.add_object(dst, self.bound_method(receiver, method))
            else:
                self.add_object(dst, method)
        elif member.kind == "class":
            self.add_object(dst, self.base_member_external(base, attr))
        elif instance or member.kind == "variable":
            origin = ("attribute", member.path)
            context = _Context(origin=origin, receivers=(receiver,))
            self.add_type(member.entry["t"], dst, context)

    def _class_object(self, obj):
        match obj:
            case Class() | External():
                return obj
            case Instance():
                return obj.cls
            case Typed():
                return self.external(obj.name)
            case Const():
                name = f"{BUILTIN_MODULE}.{obj.type_name}"
                return self.external(name, inexact=not obj.exact)
            case Container() | Generator():
                name = self.kind_class(obj.kind)[1]
                return self.external(name, inexact=not obj.exact)
            case Wrapper():
                return self.external(self.kind_class(obj.kind)[1])
        return obj

    def call_outside(self, external, definitions, call):
        base, receivers = self._prefixes.get(call, (call, ()))
        if self.returns_argument(external, call):
            return
        if not (receivers and self._unknown_class(receivers[0])):
            self.add_external_call_edge(external.name, call, "stub")
        receiver = external if external.inexact else None
        for definition in definitions:
            if definition.kind == "class" and definition.path in CONTAINER_CLASSES:
                entry = CONTAINER_CLASSES[definition.path][1]
                self.apply_rule(entry, call, receiver)
                return
        rule = self.builtin_function_rule(external)
        if rule is not None:
            self.apply_rule(rule, call, receiver)
            if (base, external) not in self._typed_callbacks:
                self._typed_callbacks.add((base, external))
                overloads = []
                for definition in definitions:
                    if definition.kind == "function":
                        overloads += self._bound_signatures(definition, call)
                    elif definition.kind == "class":
                        overloads += self._constructor_signatures(definition, call)
                self.call_protocols(base, overloads, plain=True)
            return
        overloads, builtins, calling, hinting, library = [], [], [], [], []
        consuming = []
        for definition in definitions:
            if definition.kind == "function":
                found = self._call_signatures(definition, call, receivers, external)
            elif definition.kind == "class":
                found = self._constructor_signatures(definition, call)
                if call.dst is not None:
                    context = _Context(call=call)
                    self._add_instance(definition.path, (), call.dst, context, ())
            else:
                continue
            overloads += found
            if definition.path.startswith(f"{STUB_BUILTINS}."):
                builtins += found
            if definition.path in LENGTH_HINTS:
                hinting += [(LENGTH_HINTS[definition.path], each) for each in found]
            if definition.path in CALLS_BACK:
                calling += [(CALLS_BACK[definition.path], each) for each in found]
            if definition.path in LIBRARY_ITERATION:
                library.append((definition.path, found))
            elif definition.path.startswith(f"{STUB_BUILTINS}."):
                consuming += [(definition.path, each) for each in found]
        if call.dst is not None and call.decorator and call.args[-1] is not None:
            self.add_edge(call.args[-1], call.dst)
        if (call, external) not in self._typed_callbacks:
            self._typed_callbacks.add((call, external))
            hashed = [d.path for d in definitions if d.path in HASHED_ARGUMENTS]
            if hashed:
                self.hash_arguments(hashed[0], call, builtins, receivers)
            comparisons = [
                ORDERING_COMPARISON_BY_BUILTIN[d.path]
                for d in definitions
                if d.path in ORDERING_COMPARISON_BY_BUILTIN
            ]
            if comparisons:
                self.call_protocols(base, builtins, plain=True)
                self.compare_items(comparisons[0], call, builtins)
            else:
                self.call_back_builtin(base, builtins)
                self.call_protocols(base, builtins)
            if calling:
                self.call_back_library(call, calling)
            if hinting:
                self.length_hints(call, hinting)
            for path, found in library:
                self.library_operation(call, path, found)
            if consuming:
                self.consume_library(call, consuming)
            for definition in definitions:
                entry = REFLECTION_CALLS.get(definition.path)
                if entry is not None:
                    self.apply_rule(entry, call, None)

    def call_back_library(self, call, overloads):
        back = self.site_call(call.caller, call.site, ("call back",), [None])
        for name, (parameters, _, bound) in overloads:
            for parameter in parameters:
                node = self._parameter_node(bound, parameter)
                if parameter[0] == name and node is not None:
                    self.add_edge(node, self._callee(back))

    def length_hints(self, call, hinting):
        for (name, plan, how), (parameters, _, bound) in hinting:
            for parameter in parameters:
                node = self._parameter_node(bound, parameter)
                if parameter[0] != name or node is None:
                    continue
                if how == ITERATOR:
                    self.add_iterator_length_hint(node, call.caller, call.site)
                else:
                    self.add_length_hint(node, call.caller, call.site, plan)

    def compare_items(self, method, call, overloads):
        iterables, items, keys, compared = (self.node() for _ in range(4))
        keyed = False
        for parameters, _, bound in overloads:
            positional = [p for p in parameters if p[1] in ("/", "", "*")]
            target = iterables if len(positional) == 1 else items
            for parameter in positional:
                node = self._parameter_node(bound, parameter)
                if node is not None:
                    self.add_edge(node, target)
            if bound.given("key"):
                self.add_edge(bound["key"], keys)
                keyed = keyed or bound.surely("key")
        self.add_iteration(iterables, items, call.caller, call.site)
        if not keyed:
            self.add_edge(items, compared)
        by_key = self.site_call(call.caller, call.site, ("key",), [items], dst=compared)
        self.add_edge(keys, self._callee(by_key))
        plan = [(method, ()), (REFLECTED_COMPARISONS[method], (method,))]
        self.solver.attach(
            compared, Each(self._call_protocol, plan, call, kinds=(Instance, Class))
        )
        self.compare_containers(compared, method, call, "protocol")

    def hash_arguments(self, path, call, overloads, receivers):
        parameter, iterable = HASHED_ARGUMENTS[path]
        given = self.node()
        for parameters, _, bound in overloads:
            for each in parameters:
                node = self._parameter_node(bound, each)
                if each[0] == parameter and node is not None:
                    self.add_edge(node, given)
        stored = self.node()
        receiver = receivers[0] if receivers else None
        if isinstance(receiver, Container) and hashes_keys(receiver):
            self.add_edge(self.elements(receiver), stored)
        if iterable:
            construct = ("arguments", call, path)
            given, kept = self.entering_keys(given, construct, call.caller, call.site)
            self.add_edge(given, stored)
            self.add_edge(kept, stored)
        self.add_hash(given, call.caller, call.site, stored)

    def call_typed(self, typed, call):
        cls, name = typed.cls, typed.name
        if cls in FUNCTION_TYPES:
            self.call(self.unknown_external, call)
            return
        for definition in self.stubs.member(cls, "__call__"):
            if definition.path == TYPE_CALL:
                self.call(self.unknown_external, call)
            elif definition.kind == "function":
                method = self.external(f"{name}.__call__", 1)
                self.call_bound(method, (typed,), call)

    def _unknown_class(self, obj):
        if isinstance(obj, Typed):
            return obj.abstract
        if isinstance(obj, Container) and "." in obj.kind:
            return self.stubs.abstract(obj.kind)
        return False

    def _call_signatures(self, definition, call, receivers, external=None):
        entry = definition.entry
        skip = 1 if entry.get("d") == "classmethod" and not receivers else 0
        if skip and definition.owner is not None:
            receivers = (self._class_method_owner(definition, external),)
        signatures = entry["s"]
        fitting = [
            index
            for index, signature in enumerate(signatures)
            if _fits(signature["p"][skip:], call)
        ] or range(len(signatures))
        overloads, results = [], []
        for index in fitting:
            signature = signatures[index]
            parameters = signature["p"][skip:]
            bound = self.bind_stub(call, definition.path, index, parameters)
            if call.dst is not None:
                context = _Context(call, receivers, bound, parameters)
                entry = LIBRARY_ITERATION.get(definition.path)
                context.deferred = entry is not None and entry[0] in LAZY_MODES
                results.append((signature["r"], context))
            overloads.append((parameters, signature["r"], bound))
        unpacked = call.star or call.double_star
        if results and definition.path in OPENERS and not unpacked:
            self.open_file(call, overloads[0][2], results)
        else:
            closure = CLOSURES.get(definition.path)
            for reduced, context in results:
                if closure is not None and reduced[:1] == ["*call"]:
                    self.add_object(call.dst, self.closure(closure, reduced[1]))
                else:
                    self.add_type(reduced, call.dst, context)
        creates = any(signatures[index]["r"] == "*self" for index in fitting)
        if creates and not receivers and definition.path.endswith(".__new__"):
            if call.dst is not None and call.args and call.args[0] is not None:
                each = Each(self._new_instance, call, results=(call.dst,))
                self.solver.attach(call.args[0], each)
        return overloads

    def _class_method_owner(self, definition, external):
        if external is not None and "." in external.name:
            holder = self.external(external.name.rpartition(".")[0])
            found = self.stub_definitions(holder)
            if found is None or any(d.kind == "class" for d in found):
                return holder
        public = self.stubs.public_name(definition.owner)
        return self.external(outside_name(public))

    def _new_instance(self, obj, call):
        match obj:
            case Class() if all(map(self._derives_from_type, obj.mros)):
                self.add_edge(obj.instances, call.dst)
            case Class():
                made = Each(self._made_instance, call, results=(call.dst,))
                self.solver.attach(obj.instantiable, made)
            case External():
                for value in self.outside_instance_of(obj):
                    self.add_object(call.dst, value)

    def _made_instance(self, cls, call):
        self.add_object(call.dst, self.instance(cls, call))

    def open_file(self, call, bound, results):
        buffering = None
        if bound.given("buffering"):
            buffering = self._open_argument(bound["buffering"])
        if bound.given("mode"):
            mode = self._open_argument(bound["mode"])
            each = Each(self._open_mode, call, buffering, results, results=(call.dst,))
            self.solver.attach(mode, each)
        else:
            self._opened("r", call, buffering)

    def _open_argument(self, node):
        copy = self.node()
        self.add_edge(node, copy)
        self._open_arguments.append(copy)
        return copy

    def _open_mode(self, obj, call, buffering, results):
        if _str_constant(obj):
            self._opened(obj.value, call, buffering)
        elif call not in self._unknown_modes:
            self._unknown_modes.add(call)
            for reduced, context in results:
                self.add_type(reduced, call.dst, context)

    def _opened(self, mode, call, buffering):
        if buffering is None:
            self._add_opened(mode, (False,), call)
        elif (call, mode) not in self._open_modes:
            self._open_modes.add((call, mode))
            each = Each(self._open_buffering, mode, call, results=(call.dst,))
            self.solver.attach(buffering, each)

    def _open_buffering(self, obj, mode, call):
        if isinstance(obj, Const) and type(obj.value) is int:
            self._add_opened(mode, (obj.value == 0,), call)
        else:
            self._add_opened(mode, (False, True), call)

    def _add_opened(self, mode, unbuffered, call):
        for each in unbuffered:
            cls = opened_class(mode, each)
            if cls is not None:
                self.add_object(call.dst, self.typed(cls))

    def complete_open_arguments(self):
        pending = self._open_arguments[self._completed_open_arguments :]
        self._completed_open_arguments = len(self._open_arguments)
        empty = [node for node in pending if not self.solver.objects(node)]
        for node in empty:
            self.add_object(node, self.unknown_external)
        return bool(empty)

    def _bound_signatures(self, definition, call):
        signatures = definition.entry["s"]
        fitting = [
            index
            for index, signature in enumerate(signatures)
            if _fits(signature["p"], call)
        ] or range(len(signatures))
        overloads = []
        for index in fitting:
            parameters = signatures[index]["p"]
            bound = self.bind_stub(call, definition.path, index, parameters)
            overloads.append((parameters, signatures[index]["r"], bound))
        return overloads

    def _constructor_signatures(self, definition, call):
        overloads = []
        for name in ("__new__", "__init__"):
            for member in self.stubs.member(definition.path, name):
                if member.kind != "function" or member.owner == OBJECT:
                    continue
                signatures = member.entry["s"]
                fitting = [
                    index
                    for index, signature in enumerate(signatures)
                    if _fits(signature["p"][1:], call)
                ] or range(len(signatures))
                for index in fitting:
                    parameters = signatures[index]["p"][1:]
                    bound = self.bind_stub(call, member.path, index, parameters)
                    overloads.append((parameters, None, bound))
        return overloads

    def call_back_builtin(self, call, overloads):
        values = []
        for parameters, _, bound in overloads:
            for parameter in parameters:
                if _callable(parameter):
                    node = self._parameter_node(bound, parameter)
                    if node is not None and node not in values:
                        values.append(node)
        if values:
            self._call_back(call, values)

    def call_protocols(self, call, overloads, plain=False):
        by_argument = {}
        for parameters, _, bound in overloads:
            positions = [p for p in parameters if p[1] in ("/", "")]
            for parameter in parameters:
                node = self._parameter_node(bound, parameter)
                if node is None:
                    continue
                if parameter in positions:
                    key = positions.index(parameter)
                else:
                    key = (parameter[1], parameter[0])
                nodes, protocols = by_argument.setdefault(key, ([], []))
                if node not in nodes:
                    nodes.append(node)
                _parameter_classes(parameter[3], protocols)
        for nodes, protocols in by_argument.values():
            plan, earlier = [], ()
            for cls in protocols:
                names = [n for n in self._protocol_methods(cls) if n not in earlier]
                plan += [(name, earlier) for name in names]
                earlier += tuple(names)
            if plain:
                plan = [(n, unless) for n, unless in plan if not _special(n)]
            if plan:
                for node in nodes:
                    kinds = (Instance, Class)
                    calls = Each(self._call_protocol, plan, call, kinds=kinds)
                    self.solver.attach(node, calls)

    def _call_protocol(self, obj, plan, call, kind="protocol"):
        for name, unless in plan:
            if kind == "compare":
                role = ("compare", name)
            else:
                role = ("protocol", name)
            implicit = self.site_call(call.caller, call.site, role)
            if isinstance(obj, Class):
                each = Each(
                    self._metaclass_protocol,
                    obj,
                    name,
                    implicit,
                    unless,
                    results=(implicit.dst,),
                )
                self.solver.attach(obj.metaclass, each)
            else:
                self.call_dunder(obj, name, implicit, None, unless)

    def _metaclass_protocol(self, meta, cls, name, implicit, unless):
        if isinstance(meta, Class):
            found = self.lookup(meta, name, cls, None, unless)
            self.solver.attach(
                found, Each(self.call, implicit, results=(implicit.dst,))
            )

    def _parameter_node(self, bound, parameter):
        name, kind = parameter[0], parameter[1]
        if kind == "*":
            return None if bound.varargs is None else self.every(bound.varargs)
        if kind == "**":
            container = bound.varkeywords
            return None if container is None else self.every(container)
        return bound[name] if bound.given(name) else None

    def _protocol_methods(self, cls):
        definition = self.stubs.definition(cls)
        if definition is None or not definition.entry.get("proto"):
            return ()
        names = []
        for owner in self.stubs.mro(cls):
            found = self.stubs.definition(owner)
            if owner == OBJECT or found is None:
                continue
            for name, member in found.entry["m"].items():
                if member["k"] == "f" and name not in names:
                    names.append(name)
        return names

    def bind_stub(self, call, path, index, parameters):
        key = (call, path, index)
        if key not in self._model_bindings:
            shared = (path, index, len(parameters))
            signature = self._stub_signatures.get(shared)
            if signature is None:
                signature = self._stub_signatures[shared] = _signature(parameters)
            self._model_bindings[key] = self.bind_signature(call, signature, {})
        return self._model_bindings[key]

    def typed_special(self, typed, method, dst, origin):
        if dst is None:
            return
        for definition in self.stubs.member(self._stub_class(typed), method):
            if definition.kind != "function":
                continue
            for signature in definition.entry["s"]:
                context = _Context(origin=origin, receivers=(typed,))
                self.add_type(signature["r"], dst, context)

    def outside_instance_of(self, external):
        definitions = self.stub_definitions(external)
        if definitions is None:
            return [external]
        return [self.typed(d.path) for d in definitions if d.kind == "class"]

    def add_type(self, reduced, dst, context, position=()):
        if reduced is None:
            self.add_object(dst, self.unknown_external)
        elif isinstance(reduced, str):
            if reduced == "*self":
                self._add_receivers(dst, context)
            elif reduced != "*none":
                self._add_instance(reduced, (), dst, context, position)
        elif reduced[0] == "|":
            for index, arm in enumerate(reduced[1:]):
                self.add_type(arm, dst, context, (*position, index))
        elif reduced[0] == "*type":
            self._add_class(reduced[1], dst, context)
        elif reduced[0] == "*var":
            self._add_variable(reduced, dst, context, position)
        elif reduced[0] == "*call":
            self.add_object(dst, self.unknown_external)
        else:
            self._add_instance(reduced[0], reduced[1:], dst, context, position)

    def _add_instance(self, cls, arguments, dst, context, position):
        if cls in TYPES_SAYING_NOTHING:
            self.add_object(dst, self.unknown_external)
            return
        kind = BUILTIN_CONTAINERS.get(cls)
        if kind is None and (
            cls in ABSTRACT_ITERABLES
            or cls in ABSTRACT_MAPPINGS
            or cls in CONTAINER_CLASSES
        ):
            kind = cls
        if kind is not None:
            self._add_container(kind, arguments, dst, context, position)
        elif self.stubs.definition(cls) is not None:
            self.add_object(dst, self.typed(cls))
        else:
            self.add_object(dst, self.unknown_external)

    def _add_container(self, kind, arguments, dst, context, position):
        length = None
        fixed = kind == "tuple" and arguments and "..." not in arguments
        if fixed:
            length = len(arguments)
        rule = ("stub", position, json.dumps([kind, *arguments]))
        container = self.container_at(kind, context.origin, context.site, rule, length)
        self.add_object(dst, container)
        if fixed:
            for index, argument in enumerate(arguments):
                node = self.element(container, index)
                self.add_type(argument, node, context, (*position, index))
        elif builtin_kind(kind) == "dict" or kind in ABSTRACT_MAPPINGS:
            if arguments:
                keys = self.keys(container)
                self.add_type(arguments[0], keys, context, (*position, 0))
            if len(arguments) == 2:
                values = self.unknown(container)
                self.add_type(arguments[1], values, context, (*position, 1))
        elif arguments and arguments[0] != "...":
            node = self.unknown(container)
            self.add_type(arguments[0], node, context, (*position, 0))

    def _add_receivers(self, dst, context):
        for receiver in context.receivers[:1]:
            match receiver:
                case Instance():
                    self.add_object(dst, receiver)
                    self.add_object(dst, self.abstract_instance(receiver.cls))
                case Class():
                    self.add_object(dst, self.abstract_instance(receiver))
                case Const():
                    self.add_object(dst, self.typed(f"builtins.{receiver.type_name}"))
                case External():
                    for value in self.outside_instance_of(receiver):
                        self.add_object(dst, value)
                case _:
                    self.add_object(dst, receiver)

    def _add_class(self, reduced, dst, context):
        match reduced:
            case str() if reduced == "*self":
                for receiver in context.receivers[:1]:
                    self.add_object(dst, self._class_object(receiver))
            case str() if not reduced.startswith("*"):
                if reduced not in TYPES_SAYING_NOTHING and self.stubs.definition(
                    reduced
                ):
                    public = self.stubs.public_name(reduced)
                    self.add_object(dst, self.external(outside_name(public)))
            case ["|", *arms]:
                for arm in arms:
                    self._add_class(arm, dst, context)
            case ["*var", name, *rest]:
                bindings = self._bindings(name, context)
                for node, how in bindings or ():
                    if how == "class":
                        self.add_edge(node, dst)
                if bindings is None and rest:
                    self._add_class(rest[0], dst, context)

    def _add_variable(self, reduced, dst, context, position):
        name = reduced[1]
        constraints = _constraints(reduced)
        bindings = self._bindings(name, context)
        for node, how in bindings or ():
            if how == "value" and constraints:
                pick = Each(
                    self._add_constraint,
                    constraints,
                    dst,
                    context,
                    position,
                    results=(dst,),
                )
                self.solver.attach(node, pick)
            elif how == "value":
                self.add_edge(node, dst)
            elif how == "class":
                self.solver.attach(
                    node, Each(self._add_instances_of, dst, results=(dst,))
                )
            elif how == "elements" and context.deferred:
                continue
            elif how == "elements":
                call = context.call
                construct = ("elements", call, node)
                elements = self.iterated(node, construct, call.caller, call.site)
                self.add_edge(elements, dst)
            elif how == "awaited":
                call = context.call
                self.add_await(node, dst, call.caller, call.site)
        if bindings is None:
            bound = reduced[2] if len(reduced) > 2 else None
            self.add_type(bound, dst, context, position)

    def _add_constraint(self, obj, constraints, dst, context, position):
        cls = self._stub_class(obj)
        mro = self.stubs.mro(cls) if cls is not None else ()
        matching = [c for c in constraints if c in mro] or constraints
        for constraint in matching:
            self.add_type(constraint, dst, context, position)

    def _stub_class(self, obj):
        match obj:
            case Typed():
                return obj.cls
            case Const():
                return f"{STUB_BUILTINS}.{obj.type_name}"
            case Container():
                return self.kind_class(obj.kind)[0]
        return None

    def _bindings(self, name, context):
        if context.parameters is None:
            return None
        found, passed = [], False
        for parameter in context.parameters:
            if not _mentions(parameter[3], name):
                continue
            node = self._parameter_node(context.bound, parameter)
            if node is None:
                continue
            passed = True
            how = _binds(parameter[3], name)
            if how is not None and parameter[1] != "**":
                found.append((node, how))
        return found if passed else None

    def _add_instances_of(self, obj, dst):
        match obj:
            case Class():
                self.add_edge(obj.instances, dst)
            case External():
                for value in self.outside_instance_of(obj):
                    self.add_object(dst, value)


class _Context:
    __slots__ = ("call", "receivers", "bound", "parameters", "origin", "deferred")

    def __init__(
        self, call=None, receivers=(), bound=None, parameters=None, origin=None
    ):
        self.deferred = False
        self.call = call
        self.receivers = receivers
        self.bound = bound
        self.parameters = parameters
        self.origin = call.origin if origin is None else origin

    @property
    def site(self):
        if self.call is not None:
            return self.call.site
        return str(self.origin[1])


def _special(name):
    return name.startswith("__") and name.endswith("__")


def _constraints(reduced):
    if len(reduced) > 3 and reduced[3] == "c":
        union = reduced[2]
        return union[1:] if isinstance(union, list) and union[:1] == ["|"] else [union]
    return ()


def _mentions(reduced, name):
    if isinstance(reduced, list):
        if reduced[:1] == ["*var"]:
            return reduced[1] == name
        return any(_mentions(part, name) for part in reduced)
    return False


def _binds(reduced, name):
    match reduced:
        case ["*var", var, *_] if var == name:
            return "value"
        case ["*type", ["*var", var, *_]] if var == name:
            return "class"
        case ["|", *arms]:
            for arm in arms:
                how = _binds(arm, name)
                if how is not None:
                    return how
        case [str() as cls, *arguments] if _awaited(cls, arguments) == name:
            return "awaited"
        case [str() as cls, ["*var", var, *_], *_] if var == name:
            if cls in ELEMENT_PARAMETERS:
                return "elements"
    return None


def _awaited(cls, arguments):
    position = AWAITED_PARAMETERS.get(cls)
    if position is None or position >= len(arguments):
        return None
    return _variable(arguments[position])


def _variable(reduced):
    if isinstance(reduced, list) and reduced[:1] == ["*var"]:
        return reduced[1]
    return None


def _parameter_classes(reduced, classes):
    match reduced:
        case ["|", *arms]:
            for arm in arms:
                _parameter_classes(arm, classes)
        case ["*var", _, bound]:
            _parameter_classes(bound, classes)
        case [str() as cls, *_] if not cls.startswith("*"):
            if cls not in classes:
                classes.append(cls)
        case str() if not reduced.startswith("*"):
            if reduced not in classes:
                classes.append(reduced)


def _variable_type(definition):
    return VARIABLE_TYPES.get(definition.path, definition.entry["t"])


def _named(definition):
    if definition.kind in ("module", "class", "function"):
        return True
    module = definition.path.partition(".")[0]
    return module in ("typing", "typing_extensions")


def _str_constant(obj):
    return isinstance(obj, Const) and isinstance(obj.value, str)


def _callable(parameter):
    if parameter is None:
        return False
    reduced = parameter[3]
    arms = (
        reduced[1:] if isinstance(reduced, list) and reduced[:1] == ["|"] else [reduced]
    )
    return any(isinstance(arm, list) and arm[:1] == ["*call"] for arm in arms)


def _fits(parameters, call):
    positional = [p for p in parameters if p[1] in ("/", "")]
    variadic = any(p[1] == "*" for p in parameters)
    keywords_any = any(p[1] == "**" for p in parameters)
    count = len(call.args)
    if count > len(positional) and not variadic:
        return False
    names = {p[0]: p for p in parameters}
    given = {name for name, _ in call.keywords}
    for name in given:
        parameter = names.get(name)
        if parameter is None or parameter[1] in ("/", "*", "**"):
            if not keywords_any:
                return False
    if call.star or call.double_star:
        return True
    for index, parameter in enumerate(positional):
        if index >= count and not parameter[2] and parameter[0] not in given:
            return False
    for parameter in parameters:
        if parameter[1] == "k" and not parameter[2] and parameter[0] not in given:
            return False
    return True


def _signature(parameters):
    positional = [p[0] for p in parameters if p[1] in ("/", "")]
    return Signature(
        positional=positional,
        positional_only_count=sum(1 for p in parameters if p[1] == "/"),
        keyword_only=[p[0] for p in parameters if p[1] == "k"],
        vararg=next((p[0] for p in parameters if p[1] == "*"), None),
        kwarg=next((p[0] for p in parameters if p[1] == "**"), None),
    )
