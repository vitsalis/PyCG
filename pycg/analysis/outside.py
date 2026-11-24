"""Code outside the analysed modules that the stubs describe: the builtins,
the standard library and the third-party libraries that typeshed has stubs
for (see stubs.py).

`Outside` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses. It decides what loads and calls of outside names
give when the stubs have their top-level module; outside code without
stubs keeps the bounded path names of attributes.py.

- A load on an outside module or class gives what the stubs say it has: a
  module, class or function keeps the path through which the code reached
  it (`os.path.join`); a variable or property gives a value of its type; a
  name that the stubs do not have gives nothing.
- A value whose type is an outside class is a `Typed` object, one per
  class. A method loaded through it is the outside function named through
  the public name of the class (`re.Pattern.match`, also when a base class
  defines it: `collections.OrderedDict.get`), bound to the value; the
  methods of the engine's own builtin objects (containers, constants,
  generators) are found the same way.
- Calling an outside function gives the edge, binds the arguments to each
  overload that the call fits, and gives a value of each one's return type
  (see `add_type`). Calling an outside class gives an instance of it.
"""

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

# The stub class of each kind of the engine's own builtin objects, and the
# prefix of the names of its methods, where they are not `builtins.<kind>`
# and `<builtin>.<kind>`.
KIND_CLASSES = {
    "generator": ("types.GeneratorType", "types.GeneratorType"),
    "async_generator": ("types.AsyncGeneratorType", "types.AsyncGeneratorType"),
    "dict_keys": ("_collections_abc.dict_keys", f"{BUILTIN_MODULE}.dict_keys"),
    "dict_values": ("_collections_abc.dict_values", f"{BUILTIN_MODULE}.dict_values"),
    "dict_items": ("_collections_abc.dict_items", f"{BUILTIN_MODULE}.dict_items"),
}

# Types whose values are the engine's own containers, by stub class: the
# builtin containers, and the abstract iterables and mappings of `typing`,
# whose elements are tracked but whose concrete class is not known. A
# container of an abstract type has that class as its kind.
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
# Parameter types whose argument at the given position is the type of what
# awaiting the argument gives: `asyncio.run(main: Awaitable[T]) -> T`.
AWAITED_PARAMETERS = {
    "typing.Awaitable": 0,
    "typing.Coroutine": 2,
    "typing.Generator": 2,
    "_asyncio.Future": 0,
    "_asyncio.Task": 0,
}
# Parameter types whose first argument is the type of the elements of the
# argument: `sorted(iterable: Iterable[T]) -> list[T]`.
ELEMENT_PARAMETERS = ABSTRACT_ITERABLES | {
    "builtins.list",
    "builtins.set",
    "builtins.frozenset",
    "builtins.tuple",
}
# The builtins that order their items, by definition path, with the
# comparison they make: sorted, list.sort and min use `<`, max `>`.
COMPARISONS = {
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
# Bases that a class statement replaces: a class with base
# `typing.NamedTuple` is a tuple subclass (its `__mro_entries__`), one with
# base `typing.TypedDict` a dict subclass (its metaclass makes the bases).
MRO_ENTRIES = {
    "typing.NamedTuple": "builtins.tuple",
    "typing.TypedDict": "builtins.dict",
    "typing_extensions.TypedDict": "builtins.dict",
}
# Types that say nothing about the value.
UNTYPED = frozenset({OBJECT})

# The types of function and method objects. Calling one runs its function,
# which the stubs do not know, not a `__call__` of the type.
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
    """The stub path of an outside name: `<builtin>.len` is `builtins.len`."""
    if name == BUILTIN_MODULE or name.startswith(f"{BUILTIN_MODULE}."):
        return STUB_BUILTINS + name[len(BUILTIN_MODULE) :]
    return name


def outside_name(path):
    """The callee name of a stub path: `builtins.str` is `<builtin>.str`."""
    if path == STUB_BUILTINS or path.startswith(f"{STUB_BUILTINS}."):
        return BUILTIN_MODULE + path[len(STUB_BUILTINS) :]
    return path


class Outside:
    def stub_definitions(self, external):
        """What the stubs say the outside name of `external` is (a list of
        definitions, maybe empty), or None if no stub has its top-level
        module: code without stubs."""
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
        """The node of what `from module import attr` binds, `name` being
        `module.attr`, for an outside module: the outside name, or for a
        variable that the stubs declare a value of its type, as a load
        through the module gives (`from os import environ`)."""
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
        """dst ⊇ what an annotation that names the outside `external`
        declares (macro scope rule B4): for a class of the stubs, a value
        of it (a typed value, one of the engine's containers for a builtin
        or abstract container), or the class itself for `type[C]`. The names
        of `typing` (`Any`), `object` and code without stubs declare
        nothing."""
        for definition in self.stub_definitions(external) or ():
            if definition.kind != "class" or definition.path in UNTYPED:
                continue
            if definition.path.partition(".")[0] in ("typing", "typing_extensions"):
                continue
            if as_class:
                self.add_object(dst, external)
            else:
                context = _Context(origin=("annotation", owner))
                self._add_instance(definition.path, (), dst, context, ())

    def mro_entry(self, base):
        """The base that a class statement puts in the bases for the outside
        base `base`: what its `__mro_entries__` returns (see
        `MRO_ENTRIES`), the class of `collections.abc` that a name of
        `typing` is an alias of (see `Stubs.abc_name`), else itself."""
        for definition in self.stub_definitions(base) or ():
            replaced = MRO_ENTRIES.get(definition.path)
            if replaced is not None:
                return self.external(outside_name(self.stubs.public_name(replaced)))
            abc = self.stubs.abc_name(definition.path)
            if abc is not None and abc != base.name:
                return self.external(abc)
        return base

    def typed(self, cls):
        """The instance of the stub class `cls` (a definition path)."""
        if cls not in self._typed:
            name = outside_name(self.stubs.public_name(cls))
            self._typed[cls] = Typed(cls, name, self.stubs.abstract(cls))
        return self._typed[cls]

    def closure(self, name, result):
        """The library closure `name` (see `CLOSURES`) whose calls give the
        reduced type `result`."""
        key = (name, json.dumps(result))
        if key not in self._closures:
            self._closures[key] = Closure(name, result)
        return self._closures[key]

    def call_closure(self, closure, call):
        """Call a library closure: the edge to its name and a value of its
        result type. Applied as a decorator, it may also return what it
        decorates, as any outside decorator (`@lru_cache(maxsize=32)`)."""
        self.add_external_call_edge(closure.name, call, "stub")
        if call.dst is None:
            return
        self.add_type(closure.result, call.dst, _Context(call))
        if call.decorator and call.args[-1] is not None:
            self.add_edge(call.args[-1], call.dst)

    # Loads

    def outside_attribute(self, external, attr, dst, definitions, bounded):
        """dst ⊇ external.attr for an outside name that the stubs have:
        modules, classes and functions are named by the path (`bounded`
        tells whether the bound of external names allows one more step);
        variables and properties give values of their types."""
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
        """dst ⊇ typed.attr: a member of its class."""
        self.stub_member(typed, typed.cls, typed.name, attr, dst)

    def builtin_member(self, obj, kind, attr, dst):
        """dst ⊇ obj.attr for the engine's builtin object `obj` of `kind`
        (a container, constant, generator or wrapper)."""
        cls, prefix = self.kind_class(kind)
        self.stub_member(obj, cls, prefix, attr, dst)

    def kind_class(self, kind):
        """The stub class of the engine's builtin objects of `kind`, and the
        prefix of the names of their methods."""
        if kind in KIND_CLASSES:
            return KIND_CLASSES[kind]
        if "." in kind:
            # A container of an abstract type of the stubs.
            return kind, outside_name(self.stubs.public_name(kind))
        return f"{STUB_BUILTINS}.{kind}", f"{BUILTIN_MODULE}.{kind}"

    def stub_member(self, receiver, cls, prefix, attr, dst):
        """dst ⊇ receiver.attr, found in the stub class `cls` through its
        MRO. A method is the outside function `prefix.attr`, bound to the
        receiver (to its class for a class method); a property or an
        attribute is a value of its type."""
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
                # The container of a value of the attribute is keyed by
                # the attribute, not by the receiver: a value fed back as a
                # receiver must not make a new one (see *Termination*).
                origin = ("attribute", definition.path)
                context = _Context(origin=origin, receivers=(receiver,))
                self.add_type(definition.entry["t"], dst, context)

    def outside_base_member(self, base, attr, receiver, dst):
        """dst ⊇ what a lookup of `attr` through `receiver` (an instance or
        a class of the analysed code) finds in the outside base `base`,
        which the stubs describe; return whether it finds anything. Members
        of `object` do not count: in Python's MRO, `object` comes after the
        other bases (see `object_member`)."""
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
                # Through the class, what its metaclass defines
                # (`ABCMeta.register`), bound to the class, unless a class
                # of its MRO, `object` too, defines it (`__new__`).
                for member in self.stubs.metaclass_member(definition.path, attr):
                    if member.kind == "function":
                        found = True
                        method = self.base_member_external(base, attr)
                        self.add_object(dst, self.bound_method(receiver, method))
        return found

    def object_member(self, classes, attr, receiver, dst):
        """dst ⊇ the member `attr` of `object`, which a lookup through
        `receiver` in `classes` (an MRO, without `object`) finds after them;
        return whether `object` has it. It is named through the first outside
        base that the stubs describe, else through `object`."""
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
        """dst ⊇ the outside member `member`, found through the base `base`
        and named through it, as loaded through `receiver`: a method bound
        as Python binds it, a property's or attribute's value."""
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
        """The class of the object `obj`, as an object."""
        match obj:
            case Class() | External():
                return obj
            case Instance():
                return obj.cls
            case Typed():
                return self.external(obj.name)
            case Const():
                name = f"{BUILTIN_MODULE}.{obj.type_name}"
                # An inexact value's class is not known: not its kind's own.
                return self.external(name, inexact=not obj.exact)
            case Container() | Generator():
                name = self.kind_class(obj.kind)[1]
                return self.external(name, inexact=not obj.exact)
            case Wrapper():
                return self.external(self.kind_class(obj.kind)[1])
        return obj

    # Calls

    def call_outside(self, external, definitions, call):
        """Call the outside name `external`, whose stub definitions are
        `definitions`: the edge (none for a method of a value whose class is
        not known), the rule of a modelled builtin, else the results of its
        signatures or an instance of its class."""
        base, receivers = self._prefixes.get(call, (call, ()))
        if self.returns_argument(external, call):
            return
        if not (receivers and self._unknown_class(receivers[0])):
            self.add_external_call_edge(external.name, call, "stub")
        # The receiver of a constructor rule is the class that it calls
        # where that class may be another (see `External.inexact`).
        receiver = external if external.inexact else None
        for definition in definitions:
            if definition.kind == "class" and definition.path in CONTAINER_CLASSES:
                # A container class of `collections`: its constructor's rule.
                entry = CONTAINER_CLASSES[definition.path][1]
                self.apply_rule(entry, call, receiver)
                return
        rule = self.builtin_function_rule(external)
        if rule is not None:
            self.apply_rule(rule, call, receiver)
            # The hand rule decides the result and the special methods it
            # calls; the plain methods of a protocol parameter are still
            # what the protocol declares (`print(file=f)` writes to f).
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
            # An outside decorator may return what it decorates.
            self.add_edge(call.args[-1], call.dst)
        # Once per call with its receivers: the list that `sort` compares is
        # its receiver.
        if (call, external) not in self._typed_callbacks:
            self._typed_callbacks.add((call, external))
            hashed = [d.path for d in definitions if d.path in HASHED_ARGUMENTS]
            if hashed:
                self.hash_arguments(hashed[0], call, builtins, receivers)
            comparisons = [
                COMPARISONS[d.path] for d in definitions if d.path in COMPARISONS
            ]
            if comparisons:
                # Like a hand rule, the comparison decides the special
                # methods and the key.
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
            # A namespace read by reflection (see reflection.py).
            for definition in definitions:
                entry = REFLECTION_CALLS.get(definition.path)
                if entry is not None:
                    self.apply_rule(entry, call, None)

    def call_back_library(self, call, overloads):
        """Call back what `call`, a call of a library function that calls
        what it is given (`CALLS_BACK`: `re.sub(pattern, repl, string)`),
        binds to the parameter that it calls, in each overload it fits
        (`overloads`: the parameter's name, then the parameters, result and
        bound arguments). Like `map`'s, the call back is implicit, from the
        scope of `call`, with one argument (the match), which holds no
        value: a typed `re.Match` drops its type argument, so its `group()`
        would be `bytes` too."""
        back = self.site_call(call.caller, call.site, ("call back",), [None])
        for name, (parameters, _, bound) in overloads:
            for parameter in parameters:
                node = self._parameter_node(bound, parameter)
                if parameter[0] == name and node is not None:
                    self.add_edge(node, self._callee(back))

    def length_hints(self, call, hinting):
        """A builtin of `LENGTH_HINTS` asks the length of the argument that
        each fitting overload binds to its parameter, or of the iterator of
        that argument (`ITERATOR`); `hinting` holds the entry and the
        overload (parameters, result, bound arguments)."""
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
        """`sorted`, `min`, `max` and `list.sort` compare their items with
        `method` (`<` or `>`), which falls back to the reflected method of
        the other item where no class defines it. The items are what each
        fitting overload (`overloads`: parameters, result and bound
        arguments) binds to its positional parameters: the elements of the
        one (`sorted(xs)`, the list that `sort` sorts), the values of
        several (`min(a, b)`). With a key, the key is called on the items
        and its results are compared instead. Implicit calls from the
        scope of `call`."""
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
        # Items that are containers compare their elements.
        self.compare_containers(compared, method, call, "protocol")

    def hash_arguments(self, path, call, overloads, receivers):
        """A method of a set, or `dict.fromkeys` (the stub path `path`),
        hashes what it gets (`HASHED_ARGUMENTS`: the parameter, and whether
        it takes an iterable of keys or one key) and compares it with the
        keys of its receiver, where that is a set that the analysis tracks,
        and with the other keys it gets, which Python puts in a new set or
        dict. The elements of a set or dict keep their hash (see
        `add_keys`)."""
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
        """Call the value `typed`: its class's `__call__`. A function or
        method object runs a function that is not known, as an unnamed
        external does. So does an instance of `type`, or of a metaclass
        that keeps `type.__call__`: a class that is not known, which the
        call instantiates (the edges of a class call are its own, never
        `type.__call__`)."""
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
        """Whether `obj` is a value whose concrete class is not known, so
        that its methods give no edges."""
        if isinstance(obj, Typed):
            return obj.abstract
        if isinstance(obj, Container) and "." in obj.kind:
            return self.stubs.abstract(obj.kind)
        return False

    def _call_signatures(self, definition, call, receivers, external=None):
        """Bind the arguments of `call` to each overload of the stub
        function `definition` that the call fits (all of them if it fits
        none), and give each one's result. A class method loaded through a
        class path gets no receiver for its first parameter. `__new__`, a
        static method, gives an instance of the class that its first
        argument holds for `Self` (`super().__new__(cls)`)."""
        entry = definition.entry
        skip = 1 if entry.get("d") == "classmethod" and not receivers else 0
        if skip and definition.owner is not None:
            # A class method loaded through a class (`datetime.fromordinal`,
            # defined on `date`): `Self` is an instance of that class.
            if external is not None and "." in external.name:
                receivers = (self.external(external.name.rpartition(".")[0]),)
            else:
                public = self.stubs.public_name(definition.owner)
                receivers = (self.external(outside_name(public)),)
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
                # A lazy operation of the table advances its arguments
                # where its object is advanced: its result's type variables
                # are not bound by iterating them here (see library.py).
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
                    # A callable that CPython makes as a named closure.
                    self.add_object(call.dst, self.closure(closure, reduced[1]))
                else:
                    self.add_type(reduced, call.dst, context)
        creates = any(signatures[index]["r"] == "*self" for index in fitting)
        if creates and not receivers and definition.path.endswith(".__new__"):
            if call.dst is not None and call.args and call.args[0] is not None:
                each = Each(self._new_instance, call, results=(call.dst,))
                self.solver.attach(call.args[0], each)
        return overloads

    def _new_instance(self, obj, call):
        """call.dst ⊇ an instance of the class `obj`, made by `call`. For a
        metaclass, that is the class being made (`type.__new__(mcs, ...)`),
        which the analysis does not tell apart: every class of it."""
        match obj:
            case Class() if all(map(self._derives_from_type, obj.mros)):
                self.add_edge(obj.instances, call.dst)
            case Class():
                # Not for a class that Python does not instantiate.
                made = Each(self._made_instance, call, results=(call.dst,))
                self.solver.attach(obj.instantiable, made)
            case External():
                for value in self.outside_instance_of(obj):
                    self.add_object(call.dst, value)

    def _made_instance(self, cls, call):
        self.add_object(call.dst, self.instance(cls, call))

    # Opened files

    def open_file(self, call, bound, results):
        """call.dst ⊇ the file object that a function of `OPENERS` makes, by
        the arguments that `bound` binds: for each str constant of its mode
        (`"r"` if the call gives none), with each value of its buffering,
        the class that `opened_class` selects. A mode that holds any other
        value is unknown and gives `results` (each fitting overload's type
        and context), as other calls do; so does a mode that holds nothing
        at a fixpoint (see `complete_open_arguments`). Only adds, as values
        arrive."""
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
        """A node of what the argument `node` holds, which the completion
        makes unknown if it holds nothing at a fixpoint."""
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
        """call.dst ⊇ the file object of `mode` with each value of the node
        `buffering` (None if the call gives none: buffered)."""
        if buffering is None:
            self._add_opened(mode, (False,), call)
        elif (call, mode) not in self._open_modes:
            self._open_modes.add((call, mode))
            each = Each(self._open_buffering, mode, call, results=(call.dst,))
            self.solver.attach(buffering, each)

    def _open_buffering(self, obj, mode, call):
        """An int constant buffering (or its alias, see `_str_constant`) is
        0 or not; any other value both."""
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
        """At a fixpoint that the other completion steps leave as it is
        (see `Analysis._complete`): a mode or buffering of an opened file
        that holds nothing is unknown. Every argument is read before any
        is marked, so the marks depend on that fixpoint only. Return
        whether anything was added."""
        pending = self._open_arguments[self._completed_open_arguments :]
        self._completed_open_arguments = len(self._open_arguments)
        empty = [node for node in pending if not self.solver.objects(node)]
        for node in empty:
            self.add_object(node, self.unknown_external)
        return bool(empty)

    def _bound_signatures(self, definition, call):
        """The overloads of the stub function `definition` that `call`
        fits, each with the arguments of the call bound to it, without
        their results."""
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
        """The overloads of `__new__` and `__init__` of the outside class
        `definition` that a call of the class fits, without their first
        parameter (the class or the instance), with no result, each with
        the arguments of the call bound to it."""
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
        """Call back what `call`, a call of a function or class of the
        `builtins` module, binds to a parameter typed as a callable in an
        overload it fits (`overloads`: parameters, result and bound
        arguments): `map(f, xs)`, `sorted(xs, key=f)`. Python's builtins
        that apply a function are part of the language; of other outside
        code, only the functions of `CALLS_BACK` call back (see
        `call_back_library`)."""
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
        """A function or class of the `builtins` module calls, on what an
        overload binds to a parameter typed as a protocol (`abs(x:
        SupportsAbs[T])`, `int(x: SupportsIndex)`), the special methods
        that the protocol declares, where it is an instance of an analysed
        class, or a class whose analysed metaclass defines them: implicit
        calls from the scope of `call`, with no arguments.
        Python uses the first protocol, in the order of the overloads and
        of the arms of a union, that the class implements: each method is
        called where no class defines an earlier one. With `plain`, only
        the methods that are not special methods (a builtin with a hand
        rule)."""
        # The parameters of the overloads that take one argument: the same
        # position, the same keyword.
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
        """Call on the instance or class `obj` each method of `plan` (a
        method and the methods whose definition makes Python skip it):
        implicit calls from the scope of `call` (a call, or any construct
        with a caller and a site), of the role `(kind, method)`: a builtin's
        ("protocol") or an operator's ("compare")."""
        for name, unless in plan:
            if kind == "compare":
                role = ("compare", name)
            else:
                role = ("protocol", name)
            implicit = self.site_call(call.caller, call.site, role)
            if isinstance(obj, Class):
                # A class's special methods are its metaclass's.
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
        """The node of what the call binds to the stub parameter: every
        value of `*args` and `**kwargs`; None if the call does not supply
        it."""
        name, kind = parameter[0], parameter[1]
        if kind == "*":
            return None if bound.varargs is None else self.every(bound.varargs)
        if kind == "**":
            container = bound.varkeywords
            return None if container is None else self.every(container)
        return bound[name] if bound.given(name) else None

    def _protocol_methods(self, cls):
        """The methods that the stub class `cls` declares, if it is a
        protocol (through its MRO, without `object`): what a builtin may
        call on an argument of that type (`__len__` of `Sized`, `write` of
        `SupportsWrite`)."""
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
        """Bind the arguments of `call` to the parameters of overload
        `index` of the stub function `path`, once per call and overload,
        like the arguments of a call of a function (see `bind_model`)."""
        key = (call, path, index)
        if key not in self._model_bindings:
            # One signature for all the calls of the overload: a binding
            # may keep it.
            shared = (path, index, len(parameters))
            signature = self._stub_signatures.get(shared)
            if signature is None:
                signature = self._stub_signatures[shared] = _signature(parameters)
            self._model_bindings[key] = self.bind_signature(call, signature, {})
        return self._model_bindings[key]

    # Special methods of typed values

    def typed_special(self, typed, method, dst, origin):
        """dst ⊇ what the special method `method` of the value `typed` (or
        of a container, by its class in the stubs) returns (`__iter__`,
        `__next__`, `__getitem__`, `__enter__`): no edge, because the
        interpreter makes the call."""
        if dst is None:
            return
        for definition in self.stubs.member(self._stub_class(typed), method):
            if definition.kind != "function":
                continue
            for signature in definition.entry["s"]:
                context = _Context(origin=origin, receivers=(typed,))
                self.add_type(signature["r"], dst, context)

    def outside_instance_of(self, external):
        """The value that stands for an instance of the outside class
        `external` (an exception that `except` catches): a typed value if
        the stubs have the class, else the external itself, named like the
        class."""
        definitions = self.stub_definitions(external)
        if definitions is None:
            return [external]
        return [self.typed(d.path) for d in definitions if d.kind == "class"]

    # Types

    def add_type(self, reduced, dst, context, position=()):
        """dst ⊇ the values of the reduced type `reduced` (see stubs.py) in
        `context`: an instance of a class (a typed value, or one of the
        engine's containers for the builtin and abstract containers, with
        values of their element types), each arm of a union, the receiver
        for `Self`, a class for `type[...]`, and for a type variable what
        the call binds to it. What is unknown (`Any`, `object`, a callable)
        is the unnamed external. `position` tells apart the containers that
        one origin makes for different parts of its type."""
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
        if cls in UNTYPED:
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
        # The type is part of the key: two results at one call (two stub
        # functions, two overloads) may have containers of other lengths.
        rule = ("stub", position, json.dumps([kind, *arguments]))
        container = self.container_at(kind, context.origin, context.site, rule, length)
        self.add_object(dst, container)
        if fixed:
            for index, argument in enumerate(arguments):
                node = self.element(container, index)
                self.add_type(argument, node, context, (*position, index))
        elif builtin_kind(kind) == "dict" or kind in ABSTRACT_MAPPINGS:
            # The keys, then the values (none for a `Counter`, whose values
            # are counts).
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
        """`Self`: the receiver; for an instance made by analysed code, also
        an instance of its class that outside code made, since a fluent
        method returns the receiver and a copying one a new instance; for a
        class, an instance of it."""
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
        """dst ⊇ the classes of type `type[reduced]`."""
        match reduced:
            case str() if reduced == "*self":
                for receiver in context.receivers[:1]:
                    self.add_object(dst, self._class_object(receiver))
            case str() if not reduced.startswith("*"):
                if reduced not in UNTYPED and self.stubs.definition(reduced):
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
                    # No argument binds it: the classes of its bound.
                    self._add_class(rest[0], dst, context)

    def _add_variable(self, reduced, dst, context, position):
        """dst ⊇ the values of a type variable: what the call binds to the
        parameters that have it as their type (the argument itself), as
        `type[T]` (instances of the class it passes) or as the element type
        of an iterable (its elements): the stub is taken at its word, so
        the result keeps their class (a limit, see *Class tests*). A type
        variable that the call binds to no argument (a class's, or one
        whose parameters the call does not pass) is its bound or its
        constraints, else unknown."""
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
        """dst ⊇ the constraint of a constrained type variable that the
        value `obj` bound to it is (`AnyStr` is `bytes` for b"x"); every
        constraint if it is none of them."""
        cls = self._stub_class(obj)
        mro = self.stubs.mro(cls) if cls is not None else ()
        matching = [c for c in constraints if c in mro] or constraints
        for constraint in matching:
            self.add_type(constraint, dst, context, position)

    def _stub_class(self, obj):
        """The stub class of an outside value or a builtin object, or None."""
        match obj:
            case Typed():
                return obj.cls
            case Const():
                return f"{STUB_BUILTINS}.{obj.type_name}"
            case Container():
                return self.kind_class(obj.kind)[0]
        return None

    def _bindings(self, name, context):
        """The nodes that the call binds to the parameters whose type has
        the type variable `name`, with how they have it; None if the call
        passes no argument to them: no parameter has it (a class's), or the
        call leaves out those that do (`parents` of `add_parser`). An
        argument whose type has the variable where the analysis does not
        read it (`PathLike[AnyStr]`, `**kwargs: T`) binds nothing known."""
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
            # `**kwargs: T` binds no type variable: the engine's mappings
            # keep their keys, a type argument would not (`frozendict(a=f,
            # b=g).get("x", f)` would give g).
            if how is not None and parameter[1] != "**":
                found.append((node, how))
        return found if passed else None

    def _add_instances_of(self, obj, dst):
        """dst ⊇ the instances of the class `obj` (`cast(C, x)`)."""
        match obj:
            case Class():
                self.add_edge(obj.instances, dst)
            case External():
                for value in self.outside_instance_of(obj):
                    self.add_object(dst, value)


class _Context:
    """What a type is read in: the call that gives it (None for the type of
    an attribute), whose origin identifies the containers it makes; the
    receivers of the call (for `Self`); the arguments bound to the
    parameters of the signature, and those parameters (for type
    variables)."""

    __slots__ = ("call", "receivers", "bound", "parameters", "origin", "deferred")

    def __init__(
        self, call=None, receivers=(), bound=None, parameters=None, origin=None
    ):
        # Whether the type variables that an iterable argument binds are
        # left unbound: a lazy operation's (see library.py).
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
    """The constraints of a constrained type variable, else ()."""
    if len(reduced) > 3 and reduced[3] == "c":
        union = reduced[2]
        return union[1:] if isinstance(union, list) and union[:1] == ["|"] else [union]
    return ()


def _mentions(reduced, name):
    """Whether the type variable `name` occurs in the reduced type."""
    if isinstance(reduced, list):
        if reduced[:1] == ["*var"]:
            return reduced[1] == name
        return any(_mentions(part, name) for part in reduced)
    return False


def _binds(reduced, name):
    """How a parameter of the reduced type gives the type variable `name`:
    "value" (`T`), "class" (`type[T]`), "elements" (`Iterable[T]`),
    "awaited" (`Awaitable[T]`), in the type or in an arm of its union; None
    if it occurs deeper."""
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
    """The type variable that awaiting a value of the generic class `cls`
    with the type `arguments` gives (`Awaitable[T]` gives `T`), or None."""
    position = AWAITED_PARAMETERS.get(cls)
    if position is None or position >= len(arguments):
        return None
    return _variable(arguments[position])


def _variable(reduced):
    """The name of the type variable that the reduced type is, or None."""
    if isinstance(reduced, list) and reduced[:1] == ["*var"]:
        return reduced[1]
    return None


def _parameter_classes(reduced, classes):
    """Add to `classes` the stub classes whose instances a parameter of the
    reduced type takes, through unions and the bounds of type variables."""
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
    """The reduced type of the value of the stub variable or property
    `definition`: what `VARIABLE_TYPES` states, else its stub type."""
    return VARIABLE_TYPES.get(definition.path, definition.entry["t"])


def _named(definition):
    """Whether a load of the stub definition gives its name rather than a
    value of its type: a module, a class, a function, and the names of
    `typing` (`Optional: _SpecialForm`), which annotations read by name."""
    if definition.kind in ("module", "class", "function"):
        return True
    module = definition.path.partition(".")[0]
    return module in ("typing", "typing_extensions")


def _str_constant(obj):
    """Whether `obj` is a str constant of the source, or its alias: the
    alias has the constant's value and only its class is not known (a str
    subclass, such as a `StrEnum` member, may stand for it), and `open`
    reads the value."""
    return isinstance(obj, Const) and isinstance(obj.value, str)


def _callable(parameter):
    """Whether the parameter (None for none) is typed as a callable, or as a
    union with one."""
    if parameter is None:
        return False
    reduced = parameter[3]
    arms = (
        reduced[1:] if isinstance(reduced, list) and reduced[:1] == ["|"] else [reduced]
    )
    return any(isinstance(arm, list) and arm[:1] == ["*call"] for arm in arms)


def _fits(parameters, call):
    """Whether the arguments of `call` can bind to `parameters`, by number
    and keyword names only (the types of the arguments are not checked)."""
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
