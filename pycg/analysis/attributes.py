"""Attribute loads and stores, and the names of externals.

`Attributes` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses.
"""

from .builtin_models import PROPERTY_ACCESSORS
from .hierarchy import EXPLICIT
from .model import (
    BUILTIN_MODULE,
    BoundMethod,
    Class,
    Const,
    Container,
    Coroutine,
    External,
    Fallback,
    Function,
    Generator,
    Instance,
    Module,
    Pattern,
    Super,
    Typed,
    Wrapper,
)
from .solver import Constraint, Each

# An attribute load extends an external name by one step, up to this many
# steps past the root of the name, and never with an attribute that is already
# among those steps; so a loop such as `x = x.parent` adds one name. An
# element of an external is that external, and the result of calling one
# without stubs has no name, so no name grows past its root by more than these
# steps, but for one more step that names a member of a stubbed outside base
# (`base_member_external`).
MAX_EXTERNAL_STEPS = 2

# The descriptor methods that an access calls: an analysed class's, and the
# bound method of an outside base that the stubs describe, which runs by its
# stub (the builtin `property`'s by its rule); a plain external, an outside
# base without stubs, is not called. Where an outside base resolves `__get__`
# (`property` aside), the instance is also the value of a load (see
# `Hierarchy.descriptor_itself`).
ANALYSED_METHODS = (Function, BoundMethod, Instance, Wrapper, Class)


class Attributes:
    def _descriptor(self, obj, receiver, method, hook, access):
        """Run the descriptor `obj`, found on the class of the instance
        `receiver`, for `access`, which calls its `method` (`__get__`,
        `__set__` or `__delete__`); return whether `obj` is one. A property
        is: it calls its accessor (`fget`...) with the instance. So is an
        instance: it calls the method that its class resolves with the
        instance (and the class, for `__get__`; see `ANALYSED_METHODS`); a
        load also gets the instance itself where no class resolves
        `__get__` or an outside one other than `property` does (see
        `descriptor_itself`). The accessor runs from `hook` (see
        `_call_accessor`)."""
        if isinstance(obj, Wrapper) and obj.kind == "property":
            accessor = self.field(obj, PROPERTY_ACCESSORS[method])
            self._call_accessor(accessor, receiver, (receiver,), hook, access)
            return True
        if not isinstance(obj, Instance):
            return False
        if isinstance(access, Load):
            itself = Each(self._itself, obj, access.dst, results=(access.dst,))
            self.solver.attach(self.descriptor_itself(obj.cls), itself)
        prefix = (receiver, receiver.cls) if method == "__get__" else (receiver,)
        found = self.lookup(obj.cls, method, obj)
        self._call_accessor(found, receiver, prefix, hook, access, ANALYSED_METHODS)
        return True

    def _itself(self, python_method, obj, dst):
        self.add_object(dst, obj)

    def _class_attribute(self, obj, cls, load):
        """Add `obj`, found on `cls` by a load through the class, to the
        result of `load`. An instance whose class defines `__get__` calls
        it with None and `cls` instead, from the scope of the load (see
        `_descriptor`); a property loaded through its class is itself; a
        `Fallback` (the `__getattr__` of the metaclass) is called with the
        attribute name."""
        if isinstance(obj, Fallback):
            self.call(obj.method, load.named_call())
            return
        if not isinstance(obj, Instance):
            self.add_object(load.dst, obj)
            return
        itself = Each(self._itself, obj, load.dst, results=(load.dst,))
        self.solver.attach(self.python_method(obj.cls, "__get__"), itself)
        role = ("class get", load.attr)
        args = [None, self.constant(cls)]
        call = self.site_call(load.caller, load.site, role, args, dst=load.dst)
        found = self.lookup(obj.cls, "__get__", obj)
        each = Each(self._class_get, call, kinds=ANALYSED_METHODS, results=(call.dst,))
        self.solver.attach(found, each)

    def _class_get(self, method, call):
        """Call the `__get__` method `method` with `call`, but property's
        own: with None for the instance, it gives the property, as
        `_itself` does."""
        if not (isinstance(method, BoundMethod) and _is_property_method(method)):
            self.call(method, call)

    def _call_accessor(self, accessor, receiver, prefix, hook, access, kinds=None):
        """Call the accessors in the node `accessor` (of the `kinds`, if
        given) with the arguments `prefix` before those of `access`, made
        through the instance `receiver`. Python's own attribute `hook` calls
        them from the scope of the access, where it may run (see
        `python_method`); a hook that the class defines is their caller,
        whatever its body does. `hook` is None for a `super()` load, which
        no hook of the class runs."""
        if hook is None:
            self._accessor_from(None, accessor, prefix, access, kinds)
            return
        python = self.python_method(receiver.cls, hook)
        from_access = Each(
            self._accessor_from,
            accessor,
            prefix,
            access,
            kinds,
            results=(access._result(),),
        )
        self.solver.attach(python, from_access)
        found = self.lookup(receiver.cls, hook, receiver)
        self.solver.attach(found, from_access)

    def _accessor_from(self, hook, accessor, prefix, access, kinds):
        """Call the accessors in `accessor` for `access` from the function
        of the hook object `hook` (a function or a method of one), or else
        from the scope of the access: an external hook
        (`object.__setattr__`) is Python's own."""
        function = hook.function if isinstance(hook, BoundMethod) else hook
        caller = function.name if isinstance(function, Function) else None
        call = access.accessor_call(caller)
        accessors = Each(
            self.call_bound, prefix, call, kinds=kinds, results=(call.dst,)
        )
        self.solver.attach(accessor, accessors)

    def _module_getattr(self, function, module, attr, load):
        """A load of the name `attr`, which `module` does not bind, calls the
        module's `__getattr__` with the name (PEP 562), implicitly from the
        scope of the load, and gets its result. The objects of the field
        arrive during the solve, when every module is built and linked, so
        `defines` is complete."""
        if attr in module.defines:
            return
        name = self.constant(self.const(attr))
        role = ("module getattr", attr)
        call = self.site_call(load.caller, load.site, role, [name], dst=load.dst)
        self.call(function, call)

    def add_name_lookup(self, base, attr, dst):
        """dst ⊇ base.attr as a name that nothing evaluates (in a string
        annotation): what a module binds, what a class defines in its MROs
        (not a metaclass's `__getattr__`, and a descriptor is not run), and
        the name of an outside object. No hook runs, so no call is made."""
        self.solver.attach(base, Each(self._name_lookup, attr, dst, results=(dst,)))

    def _name_lookup(self, obj, attr, dst):
        match obj:
            case Module():
                self.add_edge(self.field(obj, attr), dst)
            case Class():
                found = self.lookup(obj, attr, obj, None, EXPLICIT)
                each = Each(self._defined_name, dst, results=(dst,))
                self.solver.attach(found, each)
            case External():
                self.external_attribute(obj, attr, dst)

    def _defined_name(self, obj, dst):
        if not isinstance(obj, Fallback):
            self.add_object(dst, obj)

    def load(self, obj, attr, load):
        dst = load.dst
        match obj:
            case Module():
                self.add_edge(self.field(obj, attr), dst)
                getattr_field = self.field(obj, "__getattr__")
                each = Each(self._module_getattr, obj, attr, load, results=(dst,))
                self.solver.attach(getattr_field, each)
            case Function():
                self.add_edge(self.field(obj, attr), dst)
            case Class():
                found = self.lookup(obj, attr, obj, None, EXPLICIT)
                each = Each(self._class_attribute, obj, load, results=(dst,))
                self.solver.attach(found, each)
                if attr == "__dict__":
                    self.add_namespace(obj, dst)
            case Instance():
                self.read_field(obj, attr, dst)
                # The class side of the load, once the class may answer.
                cls = obj.cls
                self.later(cls, attr, obj, None, EXPLICIT, self._deliver_load, load)
                # The call of the hook is one per site, shared by every
                # receiver: it is made at once (see `_Access.hook_call`).
                hook, call = "__getattribute__", load.hook_call(dst)
                self.later(cls, hook, obj, None, (), self._call_hook, hook, call)
            case External():
                self.external_attribute(obj, attr, dst)
            case Typed():
                self.typed_attribute(obj, attr, dst)
            case BoundMethod():
                self.add_edge(self.field(obj.function, attr), dst)
            case Wrapper() | Container() | Generator():
                self.load_builtin_attribute(obj, obj.kind, attr, dst)
            case Const() | Pattern():
                self.load_builtin_attribute(obj, obj.type_name, attr, dst)
            case Coroutine():
                # A method of the coroutine type, named by its public path.
                self.add_object(dst, self.external(f"types.CoroutineType.{attr}", 2))
            case Super():
                receiver = obj.receiver
                owner = receiver.cls if isinstance(receiver, Instance) else receiver
                found = self.lookup(owner, attr, receiver, obj.cls, EXPLICIT)
                if isinstance(receiver, Instance):
                    self.solver.attach(found, _Deliver(self, receiver, load, None))
                else:
                    each = Each(self._class_attribute, owner, load, results=(dst,))
                    self.solver.attach(found, each)
                    # The class may also be an instance of the class of
                    # `super()` (in a method of its metaclass).
                    through = Each(
                        self._super_metaclass, obj, load, kinds=(Class,), results=(dst,)
                    )
                    self.solver.attach(receiver.metaclass, through)

    def _super_metaclass(self, meta, sup, load):
        """`super(C, cls)` where the class `cls` is an instance of C: look
        in the MROs of its metaclass `meta` after C, bound to `cls`."""
        found = self.lookup(meta, load.attr, sup.receiver, sup.cls, EXPLICIT)
        self.add_edge(found, load.dst)

    def store(self, obj, attr, src, store):
        """`obj.attr = src`. An instance also calls its class's
        `__setattr__`, and the setter of a property that its class defines.
        The instance's field gets `src` either way."""
        # What the code stores on an external is not tracked.
        if isinstance(obj, (Module, Function, Class, Instance)):
            self.add_edge(src, self.field(obj, attr))
        if isinstance(obj, (Class, Instance)):
            self.stored_name(obj, attr)
        if isinstance(obj, Class):
            self.pattern_class_store(obj, attr)
            self.class_attribute_stored(obj, attr)
        if isinstance(obj, Instance):
            cls = obj.cls
            self.later(cls, attr, obj, None, (), self._found_store, store)
            hook, call = "__setattr__", store.hook_call(None)
            self.later(cls, hook, obj, None, (), self._call_hook, hook, call)

    def _deliver_load(self, obj, load):
        found = self.lookup(obj.cls, load.attr, obj, None, EXPLICIT)
        self.solver.attach(found, _Deliver(self, obj, load, "__getattribute__"))

    def _found_store(self, obj, store):
        found = self.lookup(obj.cls, store.attr, obj)
        self.solver.attach(found, Each(self._deliver_store, obj, store))

    def deliver(self, obj, receiver, load, hook):
        """Add `obj`, found on the class of the instance `receiver`, to the
        result of `load`. A descriptor runs `__get__` instead, through `hook`
        (see `_descriptor`), and a `Fallback` calls `__getattr__` with the
        attribute name."""
        if isinstance(obj, Fallback):
            self.call(obj.method, load.named_call())
        elif not self._descriptor(obj, receiver, "__get__", hook, load):
            self.add_object(load.dst, obj)

    def delete(self, obj, attr, delete):
        """`del obj.attr`: an instance calls its class's `__delattr__`, and
        the deleter of a property that its class defines."""
        if isinstance(obj, Instance):
            found = self.lookup(obj.cls, attr, obj)
            self.solver.attach(found, Each(self._deliver_delete, obj, delete))
            self._call_hook(obj, "__delattr__", delete.hook_call(None))

    def _call_hook(self, instance, hook, call):
        """Call the attribute hook `hook` that an analysed class of
        `instance` defines, with `call`, the hook call of an access (see
        `_Access.hook_call`). An external class's hook is Python's, whose
        loads, stores and deletions the analysis models itself; its result
        is not an external."""
        found = self.lookup(instance.cls, hook, instance)
        each = Each(self._call_analysed_hook, call, results=(call.dst,))
        self.solver.attach(found, each)

    def _call_analysed_hook(self, obj, call):
        if not isinstance(obj, External):
            self.call(obj, call)

    def _deliver_delete(self, obj, receiver, delete):
        self._descriptor(obj, receiver, "__delete__", "__delattr__", delete)

    def _deliver_store(self, obj, receiver, store):
        """Run `__set__` of `obj`, found on the class of the instance
        `receiver`, if it is a descriptor (see `store`)."""
        self._descriptor(obj, receiver, "__set__", "__setattr__", store)

    def add_external_module(self, name):
        """Record that the code imports the external module `name`.

        `import a.b.c` binds `a`; reaching `a.b` or `a.b.c` by attribute
        then gives a module, which is a root like any import.
        """
        parts = name.split(".")
        for end in range(2, len(parts) + 1):
            self._external_modules.add(".".join(parts[:end]))

    def external_attribute(self, external, attr, dst):
        """dst ⊇ external.attr, within the bound of external names; past it,
        the external without a name. Every external that is not a root is
        made here. What the stubs describe gives what they say (see
        outside.py)."""
        bounded = (
            external.steps < MAX_EXTERNAL_STEPS
            and attr not in external.steps_past_root()
        )
        definitions = self.stub_definitions(external)
        if definitions is not None:
            self.outside_attribute(external, attr, dst, definitions, bounded)
        elif bounded:
            self._add_external_attribute(external, attr, dst, external.steps + 1)
        else:
            self.add_object(dst, self.unknown_external)

    def base_member_external(self, base, attr):
        """The outside name of the member `attr` that a lookup through an
        analysed class finds in its outside base `base`, which the stubs
        describe: one step past the base, which may pass the bound by one
        (a stub class has finitely many members). A base past the bound, a
        member class of such a base, names no member."""
        if base.steps > MAX_EXTERNAL_STEPS:
            return self.unknown_external
        return self.external(f"{base.name}.{attr}", base.steps + 1)

    def _add_external_attribute(self, external, attr, dst, steps):
        name = f"{external.name}.{attr}"
        # A submodule of an imported module, and a builtin, are roots.
        if name in self._external_modules or external.name == BUILTIN_MODULE:
            steps = 0
        self.add_object(dst, self.external(name, steps))


def _is_property_method(method):
    """Whether the bound method `method` is a method of `property`."""
    function = method.function
    return isinstance(function, External) and function.name.startswith(
        f"{BUILTIN_MODULE}.property."
    )


class _Access(Constraint):
    """An attribute load, store or deletion in the scope named `caller`."""

    __slots__ = (
        "analysis",
        "attr",
        "caller",
        "site",
        "_accessor_calls",
        "_named_call",
        "_hook_calls",
    )

    def __init__(self, analysis, attr, caller, site):
        self.analysis = analysis
        self.attr = attr
        self.caller = caller
        self.site = site
        self._accessor_calls = {}
        self._named_call = None
        self._hook_calls = {}

    def named_call(self):
        """The implicit call of `__getattr__` with the attribute name."""
        if self._named_call is None:
            name = self.analysis.constant(self.analysis.const(self.attr))
            role = ("getattr", type(self).__name__, self.attr)
            self._named_call = self.analysis.site_call(
                self.caller, self.site, role, [name], dst=self._result()
            )
        return self._named_call

    def hook_call(self, dst):
        """The implicit call of an attribute hook with the attribute name
        and the other arguments (`__setattr__(name, value)`), whose result
        goes to `dst`."""
        if dst not in self._hook_calls:
            name = self.analysis.constant(self.analysis.const(self.attr))
            role = ("hook", type(self).__name__, self.attr)
            self._hook_calls[dst] = self.analysis.site_call(
                self.caller, self.site, role, [name, *self._arguments()], dst=dst
            )
        return self._hook_calls[dst]

    def accessor_call(self, caller):
        """The implicit call of a descriptor's accessor that the access
        runs, from the scope named `caller`, or from the scope of the access
        if None, with the access's arguments; the instance (and the class,
        for `__get__`) come before them (see `Attributes._descriptor`)."""
        if caller not in self._accessor_calls:
            self._accessor_calls[caller] = self.analysis.site_call(
                self.caller if caller is None else caller,
                self.site,
                ("accessor", type(self).__name__, self.attr),
                self._arguments(),
                dst=self._result(),
            )
        return self._accessor_calls[caller]


class Load(_Access):
    __slots__ = ("dst",)

    def __init__(self, analysis, attr, dst, caller, site):
        super().__init__(analysis, attr, caller, site)
        self.dst = dst

    def _arguments(self):
        return []

    def _result(self):
        return self.dst

    def apply(self, obj):
        self.analysis.load(obj, self.attr, self)

    def results(self):
        return (self.dst,)


class Store(_Access):
    __slots__ = ("src",)

    def __init__(self, analysis, attr, src, caller, site):
        super().__init__(analysis, attr, caller, site)
        self.src = src

    def _arguments(self):
        return [self.src]

    def _result(self):
        return None

    def apply(self, obj):
        self.analysis.store(obj, self.attr, self.src, self)


class Delete(_Access):
    __slots__ = ()

    def _arguments(self):
        return []

    def _result(self):
        return None

    def apply(self, obj):
        self.analysis.delete(obj, self.attr, self)


class _Deliver(Constraint):
    """Adds the class attribute that a load through the instance `receiver`
    found to the result of the load (see `Attributes.deliver` for
    `hook`)."""

    __slots__ = ("analysis", "receiver", "load", "hook")

    def __init__(self, analysis, receiver, load, hook):
        self.analysis = analysis
        self.receiver = receiver
        self.load = load
        self.hook = hook

    def apply(self, obj):
        self.analysis.deliver(obj, self.receiver, self.load, self.hook)

    def results(self):
        return (self.load._result(),)

    def captured(self):
        return (self.receiver,)
