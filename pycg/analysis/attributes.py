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

EXTERNAL_STEPS_PAST_ROOT_MAX = 2

ANALYSED_METHODS = (Function, BoundMethod, Instance, Wrapper, Class)


class Attributes:
    def _descriptor(self, obj, receiver, method, hook, access):
        if isinstance(obj, Wrapper) and obj.kind == "property":
            accessor = self.field(obj, PROPERTY_ACCESSORS[method])
            self._call_accessor(accessor, receiver, (receiver,), hook, access)
            return True
        if not isinstance(obj, Instance):
            return False
        if isinstance(access, Load):
            key = ("descriptor itself", obj, access.dst)
            if key not in self._subscriptions:
                self._subscriptions.add(key)
                itself = Each(self._itself, obj, access.dst, results=(access.dst,))
                self.solver.attach(self.descriptor_itself(obj.cls), itself)
        prefix = (receiver, receiver.cls) if method == "__get__" else (receiver,)
        found = self.lookup(obj.cls, method, obj)
        self._call_accessor(found, receiver, prefix, hook, access, ANALYSED_METHODS)
        return True

    def _itself(self, python_method, obj, dst):
        self.add_object(dst, obj)

    def _class_attribute(self, obj, cls, load):
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
        if not (isinstance(method, BoundMethod) and _is_property_method(method)):
            self.call(method, call)

    def _call_accessor(self, accessor, receiver, prefix, hook, access, kinds=None):
        if hook is None:
            accessors = self.accessors_of(None, accessor, access, kinds, len(prefix))
            accessors.add(receiver)
            return
        entry = (accessor, access, kinds, len(prefix))
        hooks = self._hooks_of(receiver, hook, (receiver.cls, hook))
        if entry not in hooks.receivers and hooks.lookups_saturated():
            hooks = self._hooks_of(receiver, hook, (receiver.cls, hook, entry))
        hooks.add(entry, receiver)

    def _hooks_of(self, receiver, hook, key):
        hooks = self._accessor_hooks.get(key)
        if hooks is None:
            found = self.python_method(receiver.cls, hook)
            looked_up = self.lookup(receiver.cls, hook, receiver)
            hooks = _AccessorHooks(self, (found, looked_up))
            self._accessor_hooks[key] = hooks
            self.solver.attach(found, hooks)
            self.solver.attach(looked_up, hooks)
        return hooks

    def accessors_of(self, caller, accessor, access, kinds, width):
        call = access.accessor_call(caller)
        key = (accessor, call, kinds, width)
        accessors = self._accessor_receivers.get(key)
        if accessors is None:
            accessors = _Accessors(self, call, kinds, width)
            self._accessor_receivers[key] = accessors
            self.solver.attach(accessor, accessors)
        return accessors

    def _module_getattr(self, function, module, attr, load):
        if attr in module.defines:
            return
        name = self.constant(self.const(attr))
        role = ("module getattr", attr)
        call = self.site_call(load.caller, load.site, role, [name], dst=load.dst)
        self.call(function, call)

    def add_name_lookup(self, base, attr, dst):
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
                cls = obj.cls
                self.later(cls, attr, obj, None, EXPLICIT, self._deliver_load, load)
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
                self.add_object(dst, self.external(f"types.CoroutineType.{attr}", 2))
            case Super():
                receiver = obj.receiver
                owner = receiver.cls if isinstance(receiver, Instance) else receiver
                found = self.lookup(owner, attr, receiver, obj.cls, EXPLICIT)
                if isinstance(receiver, Instance):
                    self._deliver(found, receiver, load, None)
                else:
                    each = Each(self._class_attribute, owner, load, results=(dst,))
                    self.solver.attach(found, each)
                    through = Each(
                        self._super_metaclass, obj, load, kinds=(Class,), results=(dst,)
                    )
                    self.solver.attach(receiver.metaclass, through)

    def _super_metaclass(self, meta, sup, load):
        found = self.lookup(meta, load.attr, sup.receiver, sup.cls, EXPLICIT)
        self.add_edge(found, load.dst)

    def store(self, obj, attr, src, store):
        if isinstance(obj, (Module, Function, Class)):
            self.add_edge(src, self.field(obj, attr))
        if isinstance(obj, (Class, Instance)):
            self.stored_name(obj, attr)
        if isinstance(obj, Class):
            self.pattern_class_store(obj, attr)
            self.class_attribute_stored(obj, attr)
        if isinstance(obj, Instance):
            cls = obj.cls
            self._store_field(obj, attr, src)
            self.later(cls, attr, obj, None, (), self._found_store, store)
            hook, call = "__setattr__", store.hook_call(None)
            self.later(cls, hook, obj, None, (), self._call_hook, hook, call)

    def _store_field(self, obj, attr, src):
        field = self.field(obj, attr)
        self._write_field_once(self.instance_dict_written(obj.cls, attr), src, field)

    def _write_field_once(self, written, src, field):
        writes = self._field_writes.get(written)
        if writes is None:
            writes = self._field_writes[written] = _FieldWrites(self)
            self.solver.attach(written, writes)
        writes.add(src, field)

    def _store_past(self, value, src, field):
        if isinstance(value, Wrapper) and value.kind == "property":
            return
        if isinstance(value, Instance):
            self._write_field_once(self.not_data_descriptor(value.cls), src, field)
            return
        self.add_edge(src, field)

    def _deliver_load(self, obj, load):
        found = self.lookup(obj.cls, load.attr, obj, None, EXPLICIT)
        self._deliver(found, obj, load, "__getattribute__")

    def _deliver(self, found, receiver, load, hook):
        deliveries = self._deliveries.get(found)
        if deliveries is None:
            deliveries = _Deliveries(self, receiver, hook)
            self._deliveries[found] = deliveries
            self.solver.attach(found, deliveries)
        assert deliveries.receiver is receiver, found
        assert deliveries.hook == hook, found
        deliveries.loads.append(load)
        self.solver.apply_now(found, _Deliver(self, receiver, load, hook))

    def _found_store(self, obj, store):
        found = self.lookup(obj.cls, store.attr, obj)
        field = self.field(obj, store.attr)
        past = Each(self._store_past, store.src, field, results=(field,))
        self.solver.attach(found, past)
        self.solver.attach(found, Each(self._deliver_store, obj, store))

    def deliver(self, obj, receiver, load, hook):
        if isinstance(obj, Fallback):
            self.call(obj.method, load.named_call())
        elif not self._descriptor(obj, receiver, "__get__", hook, load):
            self.add_object(load.dst, obj)

    def delete(self, obj, attr, delete):
        if isinstance(obj, Instance):
            found = self.lookup(obj.cls, attr, obj)
            self.solver.attach(found, Each(self._deliver_delete, obj, delete))
            self._call_hook(obj, "__delattr__", delete.hook_call(None))

    def _call_hook(self, instance, hook, call):
        found = self.lookup(instance.cls, hook, instance)
        hooks = self._hook_calls.get(found)
        if hooks is None:
            hooks = _HookCalls(self, found)
            self._hook_calls[found] = hooks
            self.solver.attach(found, hooks)
        hooks.add(call)

    def _call_analysed_hook(self, obj, call):
        if not isinstance(obj, External):
            self.call(obj, call)

    def _deliver_delete(self, obj, receiver, delete):
        self._descriptor(obj, receiver, "__delete__", "__delattr__", delete)

    def _deliver_store(self, obj, receiver, store):
        self._descriptor(obj, receiver, "__set__", "__setattr__", store)

    def add_external_module(self, name):
        parts = name.split(".")
        for end in range(2, len(parts) + 1):
            self._external_modules.add(".".join(parts[:end]))

    def external_attribute(self, external, attr, dst):
        bounded = (
            external.steps < EXTERNAL_STEPS_PAST_ROOT_MAX
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
        if base.steps > EXTERNAL_STEPS_PAST_ROOT_MAX:
            return self.unknown_external
        return self.external(f"{base.name}.{attr}", base.steps + 1)

    def _add_external_attribute(self, external, attr, dst, steps):
        name = f"{external.name}.{attr}"
        if name in self._external_modules or external.name == BUILTIN_MODULE:
            steps = 0
        self.add_object(dst, self.external(name, steps))


def _is_property_method(method):
    function = method.function
    return isinstance(function, External) and function.name.startswith(
        f"{BUILTIN_MODULE}.property."
    )


def _prefix(receiver, width):
    return (receiver, receiver.cls) if width == 2 else (receiver,)


class _AccessorHooks(Constraint):
    __slots__ = (
        "analysis",
        "lookups",
        "receivers",
        "callers",
        "results_of",
        "saturated",
    )

    def __init__(self, analysis, lookups):
        self.analysis = analysis
        self.lookups = lookups
        self.receivers = {}
        self.callers = {}
        self.results_of = {}
        self.saturated = False

    def results(self):
        return tuple(self.results_of)

    def saturate(self, solver):
        self.saturated = True
        super().saturate(solver)

    def lookups_saturated(self):
        return any(map(self.analysis.solver.is_saturated, self.lookups))

    def apply(self, hook):
        function = hook.function if isinstance(hook, BoundMethod) else hook
        caller = function.name if isinstance(function, Function) else None
        if caller in self.callers:
            return
        self.callers[caller] = None
        for entry, receivers in list(self.receivers.items()):
            accessors = self.analysis.accessors_of(caller, *entry)
            for receiver in list(receivers):
                accessors.add(receiver)

    def add(self, entry, receiver):
        receivers = self.receivers.get(entry)
        if receivers is None:
            receivers = self.receivers[entry] = []
            result = entry[1]._result()
            if result is not None and result not in self.results_of:
                self.results_of[result] = None
                if self.saturated:
                    self.analysis.solver.add_object(
                        result, self.analysis.solver.saturated
                    )
        receivers.append(receiver)
        for caller in list(self.callers):
            self.analysis.accessors_of(caller, *entry).add(receiver)


class _Accessors(Constraint):
    __slots__ = ("analysis", "call", "kinds", "width", "receivers", "methods")

    def __init__(self, analysis, call, kinds, width):
        self.analysis = analysis
        self.call = call
        self.kinds = kinds
        self.width = width
        self.receivers = []
        self.methods = []

    def results(self):
        return (self.call.dst,)

    def apply(self, method):
        if self.kinds is not None and not isinstance(method, self.kinds):
            return
        self.methods.append(method)
        for receiver in list(self.receivers):
            self.analysis.call_bound(method, _prefix(receiver, self.width), self.call)

    def add(self, receiver):
        self.receivers.append(receiver)
        prefix = _prefix(receiver, self.width)
        for method in list(self.methods):
            self.analysis.call_bound(method, prefix, self.call)


class _FieldWrites(Constraint):
    __slots__ = ("analysis", "writes", "written", "saturated")

    def __init__(self, analysis):
        self.analysis = analysis
        self.writes = {}
        self.written = False
        self.saturated = False

    def results(self):
        return tuple(field for _, field in self.writes)

    def saturate(self, solver):
        self.saturated = True
        super().saturate(solver)

    def apply(self, marker):
        if self.written:
            return
        self.written = True
        for src, field in self.writes:
            self.analysis.add_edge(src, field)

    def add(self, src, field):
        if (src, field) in self.writes:
            return
        self.writes[(src, field)] = None
        if self.saturated:
            self.analysis.solver.add_object(field, self.analysis.solver.saturated)
        elif self.written:
            self.analysis.add_edge(src, field)


class _HookCalls(Constraint):
    __slots__ = ("analysis", "found", "calls", "hooks", "saw_opaque")

    def __init__(self, analysis, found):
        self.analysis = analysis
        self.found = found
        self.calls = []
        self.hooks = []
        self.saw_opaque = False

    def results(self):
        return tuple(call.dst for call in self.calls)

    def saturate(self, solver):
        self.saw_opaque = True
        super().saturate(solver)

    def apply(self, hook):
        if isinstance(hook, External):
            return
        self.hooks.append(hook)
        for call in list(self.calls):
            self.analysis.call(hook, call)

    def add(self, call):
        self.calls.append(call)
        solver = self.analysis.solver
        if solver.is_saturated(self.found):
            _saturate(solver, call)
            return
        opaque = solver.opaque
        hooks = [hook for hook in self.hooks if not (opaque and opaque(hook))]
        if self.saw_opaque or len(hooks) < len(self.hooks):
            _saturate(solver, call)
        for hook in hooks:
            self.analysis.call(hook, call)


def _saturate(solver, call):
    if call.dst is not None:
        solver.add_object(call.dst, solver.saturated)


class _Access(Constraint):
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
        if self._named_call is None:
            name = self.analysis.constant(self.analysis.const(self.attr))
            role = ("getattr", type(self).__name__, self.attr)
            self._named_call = self.analysis.site_call(
                self.caller, self.site, role, [name], dst=self._result()
            )
        return self._named_call

    def hook_call(self, dst):
        if dst not in self._hook_calls:
            name = self.analysis.constant(self.analysis.const(self.attr))
            role = ("hook", type(self).__name__, self.attr)
            self._hook_calls[dst] = self.analysis.site_call(
                self.caller, self.site, role, [name, *self._arguments()], dst=dst
            )
        return self._hook_calls[dst]

    def accessor_call(self, caller):
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


class _Deliveries(Constraint):
    __slots__ = ("analysis", "receiver", "hook", "loads")

    def __init__(self, analysis, receiver, hook):
        self.analysis = analysis
        self.receiver = receiver
        self.hook = hook
        self.loads = []

    def apply(self, obj):
        self.apply_each((obj,))

    def apply_each(self, objects):
        deliver, receiver, hook = self.analysis.deliver, self.receiver, self.hook
        loads = list(self.loads)
        for obj in objects:
            for load in loads:
                deliver(obj, receiver, load, hook)

    def results(self):
        return tuple(load._result() for load in self.loads)

    def captured(self):
        return (self.receiver,)
