from collections import deque

from .annotations import Annotations
from .arguments import Arguments
from .attributes import EXTERNAL_STEPS_PAST_ROOT_MAX, Attributes, Delete, Load, Store
from .builtin_models import RETURNED_DECORATOR_SIGNATURE, method_model
from .builtin_rules import BuiltinRules
from .containers import Containers
from .hierarchy import Hierarchy, opaque
from .library import LibraryIteration
from .model import (
    BUILTIN_MODULE,
    BoundMethod,
    BuiltinMethod,
    Class,
    Closure,
    Container,
    Coroutine,
    External,
    Fallback,
    Function,
    Generator,
    Instance,
    Module,
    ReturnsArgument,
    Saturated,
    Super,
    Typed,
    UnknownExternal,
    Wrapper,
)
from .narrowing import ClassTests
from .outside import Outside
from .patterns import Patterns
from .protocols import Protocols
from .reflection import Reflection
from .solver import Constraint, Each, Node, Solver
from .stubs import Stubs

LITERAL_IMPORTERS = frozenset({"importlib.import_module", "<builtin>.__import__"})

RECEIVERS_PER_CALL_MAX = 3


class Analysis(
    Hierarchy,
    Attributes,
    Arguments,
    Containers,
    Protocols,
    BuiltinRules,
    Annotations,
    ClassTests,
    Patterns,
    Reflection,
    Outside,
    LibraryIteration,
):
    def __init__(self, cap=None):
        self.saturated = Saturated("<saturated>")
        self.solver = Solver(self.saturated, cap)
        self.solver.between_rounds = self.unknown_classes
        self.stubs = Stubs()
        self._stub_definitions = {}
        self._typed = {}
        self._closures = {}
        self.modules = {}
        self.externals = {}
        self.functions = []
        self.classes = []
        self.site_edges = {}
        self.external_callees = {}
        self.call_expressions = []
        self.iterated_expressions = set()
        self.named_nodes = []
        self._instances = {}
        self._dunder_calls = {}
        self._dunder_owners = {}
        self._new_results = {}
        self._class_instances = {}
        self._statement_calls = {}
        self._statement_news = set()
        self._made_classes = set()
        self._roots = {}
        self._site_calls = {}
        self._bound_methods = {}
        self._builtin_methods = {}
        self._wrappers = {}
        self._supers = {}
        self._fallbacks = {}
        self._fallback_nodes = {}
        self._returning = {}
        self.unknown_external = UnknownExternal(
            "<unknown>", EXTERNAL_STEPS_PAST_ROOT_MAX
        )
        self._generators = {}
        self._coroutines = {}
        self._callbacks = {}
        self._callback_values = set()
        self._typed_callbacks = set()
        self._open_arguments = []
        self._completed_open_arguments = 0
        self._unknown_modes = set()
        self._open_modes = set()
        self._prefixes = {}
        self._callees = {}
        self._model_bindings = {}
        self._name_sets = {}
        self._stub_signatures = {}
        self._receiver_calls = {}
        self._handlers = set()
        self._unpacked = {}
        self._iterated = {}
        self._library = {}
        self._library_advances = {}
        self._library_calls = {}
        self._consts = {}
        self._containers = {}
        self._constants = {}
        self._subscriptions = set()
        self._compared_keys = {}
        self._sequences = {}
        self._dict_hubs = {}
        self._subscript_keys = {}
        self._watches = {}
        self._field_readers = {}
        self._notices = deque()
        self._notifying = False
        self._external_modules = set()
        self.literal_imports = {}
        self.read_namespaces = set()
        self._namespace_names_read = frozenset()
        self.none_arguments = {}
        self.none_keywords = {}
        self.zero_argument_super = set()
        self._super_pairs = set()
        self._super_accepted = {}
        self._receivers = []
        self._called = set()
        self._completed_receivers = 0
        self._entry_receivers = []
        self._completed_functions = 0
        self._type_forms = {}
        self._annotated = set()
        self._tested_classes = set()
        self._class_filters = {}
        self._completed_class_filters = 0
        self._stub_ancestors = {}
        self._families = {}
        self._dataclass_like_classes = set()
        self._structure_classes = set()
        self._classes_below = {}
        self._below_nodes = {}
        self._patterns = {}
        self._pattern_states = {}
        self._store_names = set()
        self._class_store_names = {}
        self._module_names = {}
        self._pattern_operands = []
        self._completed_pattern_operands = 0
        self._namespace_nodes = {}
        self._keyed = []
        self._completed_keys = 0
        self._dynamic_accesses = []

    def module(self, name):
        if name not in self.modules:
            self.modules[name] = Module(name)
        return self.modules[name]

    def external(self, name, steps=0, inexact=False):
        module, dot, rest = name.partition(".")
        if module == "builtins":
            name = BUILTIN_MODULE + dot + rest
        key = (name, steps, inexact)
        if key not in self.externals:
            self.externals[key] = External(name, steps, inexact)
        return self.externals[key]

    def same_class(self, obj):
        if isinstance(obj, External) and obj.inexact:
            return self.external(obj.name, obj.steps)
        return obj

    def function(self, name, module, signature, defaults, generator=False):
        parameters = {
            parameter: self.node(f"{name}.{parameter}")
            for parameter in signature.names()
        }
        return_node = self.node(f"{name}.<return>")
        optional = frozenset(defaults)
        defaults = {
            parameter: default
            for parameter, default in defaults.items()
            if default is not None
        }
        function = Function(name, module, signature, parameters, defaults, return_node)
        function.optional = optional
        if generator:
            function.yield_node = self.node(f"{name}.<yield>")
            function.sent_node = self.node(f"{name}.<sent>")
        if signature.vararg:
            function.varargs = Container("tuple", name, exact=True)
            self.add_object(parameters[signature.vararg], function.varargs)
        if signature.kwarg:
            function.varkeywords = Container("dict", name, exact=True)
            self.add_object(parameters[signature.kwarg], function.varkeywords)
        self.functions.append(function)
        return function

    def returning_argument(self, name, analysed):
        key = (name, analysed)
        if key not in self._returning:
            self._returning[key] = ReturnsArgument(name, analysed)
        return self._returning[key]

    def fallback(self, method):
        if method not in self._fallbacks:
            self._fallbacks[method] = Fallback(method)
        return self._fallbacks[method]

    def super_object(self, cls, receiver):
        key = (cls, receiver)
        if key not in self._supers:
            self._supers[key] = Super(cls, receiver)
        return self._supers[key]

    def generator(self, function):
        if function not in self._generators:
            self._generators[function] = Generator(function)
        return self._generators[function]

    def coroutine(self, function):
        if function not in self._coroutines:
            self._coroutines[function] = Coroutine(function)
        return self._coroutines[function]

    def instance(self, cls, call):
        key = (cls, call.origin)
        if key not in self._instances:
            self._instances[key] = Instance(cls, call.site)
            self.add_object(cls.instances, self._instances[key])
        return self._instances[key]

    def abstract_instance(self, cls):
        key = (cls, None)
        if key not in self._instances:
            self._instances[key] = Instance(cls, "<object>")
            self.add_object(cls.instances, self._instances[key])
        return self._instances[key]

    def add_method(self, cls, name, function, kind):
        if kind == "staticmethod":
            return
        positional = function.signature.positional
        if positional:
            receiver = function.parameters[positional[0]]
        elif function.varargs is not None:
            receiver = self.element(function.varargs, 0)
        else:
            return
        source = self.family(cls) if kind == "classmethod" else cls.instances
        self._receivers.append((receiver, source, function, cls, name))

    def object_count(self):
        made = (
            self.externals,
            self._class_filters,
            self._typed,
            self._closures,
            self._instances,
            self._containers,
            self._bound_methods,
            self._builtin_methods,
            self._families,
            self._below_nodes,
            self._wrappers,
            self._supers,
            self._fallbacks,
            self._generators,
            self._coroutines,
            self._returning,
            self._consts,
            self._patterns,
            self._site_calls,
            self._dunder_calls,
            self._receiver_calls,
            self._callbacks,
            self._constants,
            self._callees,
            self._fallback_nodes,
            self._model_bindings,
            self._entry_receivers,
            self._super_pairs,
            self._super_accepted,
            self._unpacked,
            self._iterated,
            self._namespace_nodes,
            self.named_nodes,
            self._open_arguments,
            self._open_modes,
            self._library,
            self._library_advances,
        )
        return sum(map(len, made))

    def bound_method(self, receiver, function):
        key = (receiver, function)
        if key not in self._bound_methods:
            self._bound_methods[key] = BoundMethod(receiver, function)
        return self._bound_methods[key]

    def builtin_method(self, receiver, type_name, method):
        key = (receiver, method)
        if key not in self._builtin_methods:
            name = f"{self.kind_class(type_name)[1]}.{method}"
            method_object = BuiltinMethod(receiver, type_name, method, name)
            self._builtin_methods[key] = method_object
        return self._builtin_methods[key]

    def wrapper(self, kind, call):
        key = (kind, call.origin)
        if key not in self._wrappers:
            self._wrappers[key] = Wrapper(kind, call.site)
        return self._wrappers[key]

    def node(self, label=None):
        node = Node(label)
        if label is not None:
            self.named_nodes.append(node)
        return node

    def field(self, obj, name):
        if name not in obj.fields:
            obj.fields[name] = node = self.node(f"{obj.name}.{name}")
            if type(obj) is Instance:
                readers = self._field_readers.get((obj.cls, name), {})
                for dst, receivers in readers.items():
                    if obj in receivers:
                        self.add_edge(node, dst)
        return obj.fields[name]

    def read_field(self, instance, name, dst):
        node = instance.fields.get(name)
        if node is not None:
            self.add_edge(node, dst)
            return
        readers = self._field_readers.setdefault((instance.cls, name), {})
        readers.setdefault(dst, []).append(instance)

    def constant(self, obj):
        if obj not in self._constants:
            self._constants[obj] = self.solver.constant(obj)
        return self._constants[obj]

    def add_object(self, node, obj):
        self.solver.add_object(node, obj)

    def add_edge(self, src, dst):
        self.solver.add_edge(src, dst)

    def add_load(self, base, attr, dst, caller, site):
        self.solver.attach(base, Load(self, attr, dst, caller, site))

    def add_store(self, base, attr, src, caller, site):
        self.pattern_store_name(attr)
        self.solver.attach(base, Store(self, attr, src, caller, site))

    def add_delete(self, base, attr, caller, site):
        self.solver.attach(base, Delete(self, attr, caller, site))

    def add_call(
        self,
        callee,
        caller,
        args,
        keywords,
        dst,
        site,
        star=(),
        double_star=(),
        decorator=False,
        applies=False,
    ):
        if not decorator:
            self.call_expressions.append((caller, site, callee))
        if callee is None:
            return
        call = Call(self, caller, args, keywords, dst, site, None, star, double_star)
        call.decorator = decorator
        call.applies = applies
        self.solver.attach(callee, call)

    def solve(self):
        self.freeze_module_names()
        self._namespace_names_read = frozenset(
            name
            for cls in self.classes
            if cls.name in self.read_namespaces
            for name in cls.defines
        )
        self.solver.solve()
        while self.decide_hierarchies() or self._complete():
            self.solver.solve()

    def _complete(self):
        added = False
        absorbed = self._absorbed_functions()
        for entry in self._receivers[self._completed_receivers :]:
            receiver, source, function = entry[:3]
            if not self.solver.objects(receiver) and function not in absorbed:
                self._entry_receivers.append(entry)
        self._completed_receivers = len(self._receivers)
        holds = self.solver.holds
        for receiver, source, function, cls, name in self._entry_receivers:
            for obj in self.solver.objects(source):
                if not holds(receiver, obj) and self._inherits_method(
                    obj, cls, name, function
                ):
                    self.add_object(receiver, obj)
                    added = holds(receiver, obj) or added
        for function in self.functions[self._completed_functions :]:
            if function not in self._called and function not in absorbed:
                for parameter, default in function.defaults.items():
                    self.add_edge(default, function.parameters[parameter])
                    added = True
        self._completed_functions = len(self.functions)
        added = self._complete_keys() or added
        added = self.complete_dynamic_accesses() or added
        added = self.complete_class_tests() or added
        if added:
            return True
        return self.complete_open_arguments() or self.complete_pattern_operands()

    def _inherits_method(self, obj, cls, name, function):
        if opaque(obj) or not isinstance(obj, (Instance, Class)):
            return True
        owner = obj.cls if isinstance(obj, Instance) else obj
        if owner is cls or (isinstance(obj, Class) and cls not in obj.ancestors):
            return True
        if owner.exhaustive:
            return cls in owner.mros[0]
        for mro in owner.mros:
            definer = next(
                (c for c in mro if isinstance(c, Class) and name in c.defines), None
            )
            if definer is cls or self._binds_function(definer, name, function):
                return True
        return False

    def _binds_function(self, cls, name, function):
        if cls is None:
            return False
        for value in self.solver.objects(self.field(cls, name)):
            if value is function:
                return True
            if isinstance(value, Wrapper) and function in self.solver.objects(
                self.field(value, "__func__")
            ):
                return True
        return False

    def _absorbed_functions(self):
        functions = set()
        pending = list(self.solver.absorbed())
        seen = set()
        while pending:
            obj = pending.pop()
            if obj in seen:
                continue
            seen.add(obj)
            if isinstance(obj, BoundMethod):
                pending.append(obj.function)
            elif isinstance(obj, Instance):
                pending.append(obj.cls)
            elif isinstance(obj, Function):
                functions.add(obj)
            elif isinstance(obj, Wrapper) and "__func__" in obj.fields:
                pending.extend(self.solver.objects(obj.fields["__func__"]))
            elif isinstance(obj, Class):
                for owner in obj.mro:
                    for field in getattr(owner, "fields", {}).values():
                        pending.extend(
                            value
                            for value in self.solver.objects(field)
                            if isinstance(value, (Function, Wrapper))
                        )
        return functions

    def call(self, obj, call):
        match obj:
            case Function():
                if not self.returns_argument(obj, call):
                    self._call_function(obj, call, None)
            case UnknownExternal():
                self._outside_result(call)
            case ReturnsArgument():
                self.model_edge(obj.name, obj.analysed, call)
                self.return_argument(
                    RETURNED_DECORATOR_SIGNATURE, obj.name, obj.analysed, call
                )
            case Closure():
                self.call_closure(obj, call)
            case BoundMethod():
                self.call_bound(obj.function, (obj.receiver,), call)
            case Class():
                self.instantiate(obj, call)
            case Instance():
                self.call_dunder(obj, "__call__", call, call.dst)
            case Typed():
                self.call_typed(obj, call)
            case Wrapper(kind="staticmethod"):
                self.add_edge(self.field(obj, "__func__"), self._callee(call))
            case BuiltinMethod():
                self.add_external_call_edge(obj.name, call, "stub")
                rule = method_model(obj.type_name, obj.method)
                self.apply_rule(rule, call, obj.receiver)
            case External():
                module = self.literal_imports.get(call.site)
                if module is not None and obj.name in LITERAL_IMPORTERS:
                    self.add_external_call_edge(obj.name, call, "stub")
                    if call.dst is not None:
                        self.add_edge(module, call.dst)
                    return
                definitions = self.stub_definitions(obj)
                if definitions is not None:
                    self.call_outside(obj, definitions, call)
                    return
                self.add_external_call_edge(obj.name, call, "name")
                self._outside_result(call)

    def _outside_result(self, call):
        if call.dst is None:
            return
        self.add_object(call.dst, self.unknown_external)
        if call.decorator and call.args[-1] is not None:
            self.add_edge(call.args[-1], call.dst)

    def add_external_call_edge(self, name, call, known):
        if not call.implicit:
            self._add_call_edge(call, name)
            if self.external_callees.get(name) != "stub":
                self.external_callees[name] = known

    def unresolved_calls(self):
        resolved = {key[:2] for key in self.site_edges if key[2] == "call"}
        computed = {
            access.dst
            for access in self._dynamic_accesses
            if not self.names_known(access)
        }
        unresolved = {}
        for caller, site, callee in self.call_expressions:
            if (caller, site) in resolved:
                continue
            objects = () if callee is None else self.solver.objects(callee)
            known = (obj for obj in objects if obj is not self.unknown_external)
            if not all(map(opaque, known)):
                continue
            if any(map(opaque, objects)):
                cause = "saturated"
            elif callee is not None and callee in computed:
                cause = "computed name"
            elif objects:
                cause = "outside value"
            else:
                cause = "no value"
            unresolved[caller, site] = cause
        return unresolved

    def _call_back(self, call, values):
        callback = self._callbacks.get(call.origin)
        if callback is None:
            callback = Call(
                self, call.caller, [], [], None, call.site, call.origin, implicit=True
            )
            self._callbacks[call.origin] = callback
        for value in values:
            if value is not None and (callback, value) not in self._callback_values:
                self._callback_values.add((callback, value))
                call_back = Each(
                    self._call_back_object,
                    callback,
                    kinds=(Function, BoundMethod, Instance),
                )
                self.solver.attach(value, call_back)

    def _call_back_object(self, obj, callback):
        self.call(obj, callback)

    def call_bound(self, obj, receivers, call):
        base, prefix = self._prefixes.get(call, (call, ()))
        receivers = (receivers + prefix)[:RECEIVERS_PER_CALL_MAX]
        if isinstance(obj, Function):
            rest = self._prefixed_call(base, receivers[1:])
            self._call_function(obj, rest, receivers[0])
        else:
            self.call(obj, self._prefixed_call(base, receivers))

    def _prefixed_call(self, base, receivers):
        if not receivers:
            return base
        key = (base, receivers)
        if key not in self._receiver_calls:
            call = Call(
                self,
                base.caller,
                [*(self.constant(receiver) for receiver in receivers), *base.args],
                base.keywords,
                base.dst,
                base.site,
                base.origin,
                base.star,
                base.double_star,
                base.implicit,
            )
            call.decorator = base.decorator
            call.applies = base.applies
            self._receiver_calls[key] = call
            self._prefixes[call] = (base, receivers)
        return self._receiver_calls[key]

    def literal_none(self, call, index):
        base, receivers = self._prefixes.get(call, (call, ()))
        root = self._roots.get(base, base)
        if root.origin is not root:
            return False
        nones = self.none_arguments.get((root.caller, root.site), ())
        return index - len(receivers) in nones

    def literal_none_keyword(self, call, name):
        base, _ = self._prefixes.get(call, (call, ()))
        root = self._roots.get(base, base)
        if root.origin is not root:
            return False
        return name in self.none_keywords.get((root.caller, root.site), ())

    def _callee(self, call):
        if call not in self._callees:
            node = self.node()
            self.solver.attach(node, call)
            self._callees[call] = node
        return self._callees[call]

    def _call_function(self, function, call, receiver):
        if not self._may_bind(function, call, receiver):
            return
        self._add_call_edge(call, function.name)
        if call.caller != function.name:
            self._called.add(function)
        self._function_result(function, call, receiver)

    def _function_result(self, function, call, receiver):
        self.bind_arguments(function, call, receiver)
        if call.dst is None:
            return
        if function.yield_node is not None:
            self.add_object(call.dst, self.generator(function))
        elif function.is_async:
            self.add_object(call.dst, self.coroutine(function))
        else:
            self.add_edge(function.return_node, call.dst)

    def _may_bind(self, function, call, receiver):
        if call.star or call.double_star or function.decorated:
            return True
        base = self._prefixes.get(call, (call, ()))[0]
        if self._roots.get(base, base).implicit:
            return True
        given = len(call.args) + (receiver is not None)
        keywords = [name for name, _ in call.keywords]
        return function.signature.binds(given, keywords, function.optional)

    def instantiate(self, cls, call):
        default = self.python_method(cls, "__new__")
        self.solver.attach(
            default, Each(self._python_new, cls, call, results=(call.dst,))
        )
        new = self._implicit_call(cls, "__new__", call, None)
        if new not in self._new_results:
            instances = self._class_instances.setdefault(cls, set())
            returned = _Returned(self, call, cls, instances)
            self._new_results[new] = returned
            self.solver.attach(
                self.lookup(cls, "__new__", cls),
                Each(self._new, cls, new, results=(new.dst,)),
            )
            self.solver.attach(cls.instances, Each(returned.of_class))
        if call.dst is not None:
            self._new_results[new].add_dst(call.dst)

    def add_init_subclass(self, cls, keywords, double_star, caller, site):
        origin = ("init_subclass", site)
        call = Call(
            self, caller, [], keywords, None, site, origin, (), double_star, True
        )
        self.solver.attach(self.lookup(cls, "__init_subclass__", cls, cls), call)

    def add_set_name(self, value, cls, name, caller, site):
        kinds = (Instance, Class)
        set_name = Each(self._set_name, cls, name, caller, site, kinds=kinds)
        self.solver.attach(value, set_name)

    def _set_name(self, obj, cls, name, caller, site):
        args = [self.constant(cls), self.constant(self.const(name))]
        call = self.site_call(caller, site, ("set_name", name), args)
        self.call_dunder(obj, "__set_name__", call, None)

    def add_metaclass_call(self, cls, statement, caller, site):
        each = Each(self._call_metaclass, cls, statement, caller, site, kinds=(Class,))
        self.solver.attach(cls.metaclass, each)

    def _call_metaclass(self, meta, cls, statement, caller, site):
        if cls not in self._statement_calls:
            name, bases, namespace, keywords, double_star = statement
            origin = ("class statement", site)
            members = self.container_at("tuple", origin, site, "bases", len(bases))
            for index, base in enumerate(bases):
                if base is not None:
                    self.add_edge(base, self.element(members, index))
            body = self.container_at("dict", origin, site, "namespace")
            for key, value in namespace:
                self.write_keyed(body, self.constant(self.const(key)), value)
            args = [
                self.constant(self.const(name)),
                self.constant(members),
                self.constant(body),
            ]
            call = Call(
                self, caller, args, keywords, None, site, origin, (), double_star, True
            )
            prepare = Call(
                self,
                caller,
                args[:2],
                keywords,
                None,
                site,
                ("prepare", site),
                (),
                double_star,
                True,
            )
            self._statement_calls[cls] = (call, prepare)
            if cls in self._made_classes:
                self.call_dunder(cls, "__init__", call, None)
        call, prepare = self._statement_calls[cls]
        found = self.lookup(meta, "__prepare__", meta)
        hook = Each(self._call_analysed_hook, prepare, results=(prepare.dst,))
        self.solver.attach(found, hook)
        python = self.python_method(meta, "__new__")
        self.solver.attach(python, Each(self._init_statement_class, cls, call))
        found = self.lookup(meta, "__new__", meta)
        self.solver.attach(found, Each(self._statement_new, meta, call))

    def _init_statement_class(self, python_method, cls, call):
        self.call_dunder(cls, "__init__", call, None)

    def _statement_new(self, method, meta, call):
        if isinstance(method, External):
            return
        self.call_bound(method, (meta,), call)
        if isinstance(method, Function) and method not in self._statement_news:
            self._statement_news.add(method)
            made = Each(self._statement_made, kinds=(Class,))
            self.solver.attach(method.return_node, made)

    def _statement_made(self, cls):
        self._made_classes.add(cls)
        calls = self._statement_calls.get(cls)
        if calls is not None:
            self.call_dunder(cls, "__init__", calls[0], None)

    def _python_new(self, method, cls, call):
        made = Each(self._python_instance, call, results=(call.dst,))
        self.solver.attach(cls.instantiable, made)

    def _python_instance(self, cls, call):
        instance = self.instance(cls, call)
        if call.dst is not None:
            self.add_object(call.dst, instance)
        self.call_dunder(instance, "__init__", call, None)

    def _new(self, method, cls, call):
        if not isinstance(method, External):
            self._new_results[call].start(call.dst)
            self.call_bound(method, (cls,), call)

    def call_dunder(self, obj, name, call, dst, unless=()):
        if type(obj) is Instance:
            rule = self._call_dunder
            self.later(obj.cls, name, obj, None, unless, rule, name, call, dst, unless)
        else:
            self._call_dunder(obj, name, call, dst, unless)

    def _call_dunder(self, obj, name, call, dst, unless):
        implicit = self._implicit_call(obj, name, call, dst, unless)
        owners = self._dunder_owners.setdefault(implicit, set())
        if obj not in owners:
            owners.add(obj)
            method = Each(
                self._type_method, obj, name, implicit, unless, results=(implicit.dst,)
            )
            self.solver.attach(self._types(obj), method)

    def _types(self, obj):
        if isinstance(obj, Instance):
            return self.constant(obj.cls)
        return obj.metaclass

    def _type_method(self, cls, obj, name, implicit, unless):
        if isinstance(cls, Class):
            self.solver.attach(self.lookup(cls, name, obj, None, unless), implicit)
            return
        method = self.node()
        for definition in self.stub_definitions(cls) or ():
            if definition.kind == "class":
                self.stub_member(obj, definition.path, cls.name, name, method)
        self.solver.attach(method, implicit)

    def _implicit_call(self, owner, name, call, dst, unless=()):
        base, receivers = self._prefixes.get(call, (call, ()))
        root = self._roots.get(base, base)
        typed = owner.cls if type(owner) is Instance else owner
        key = (typed, type(owner) is Instance, name, root, unless)
        template = self._dunder_calls.get(key)
        if template is None:
            template = Call(
                self,
                base.caller,
                base.args,
                base.keywords,
                self.node(),
                base.site,
                base.origin,
                base.star,
                base.double_star,
                base.implicit,
            )
            template.decorator = base.decorator
            template.applies = base.applies
            self._dunder_calls[key] = template
            self._roots[template] = root
        assert (template.args, template.keywords) == (base.args, base.keywords)
        assert (template.star, template.double_star) == (base.star, base.double_star)
        implicit = self._prefixed_call(template, receivers)
        if dst is not None:
            self.add_edge(implicit.dst, dst)
        return implicit

    def site_call(
        self, caller, site, role, args=(), implicit=True, dst=None, rest=None
    ):
        key = (caller, site, role, implicit)
        call = self._site_calls.get(key)
        if call is None:
            nodes = [self.node() for _ in args]
            star = () if rest is None else ((None, True), (self.node(), False))
            call = Call(
                self, caller, nodes, [], self.node(), site, key, star, implicit=implicit
            )
            self._site_calls[key] = call
        assert len(args) == len(call.args), f"{key!r} with another arity"
        assert (rest is None) == (not call.star), f"{key!r} with another arity"
        for value, node in zip(args, call.args):
            if value is not None:
                self.add_edge(value, node)
        if rest is not None:
            self.add_edge(rest, call.star[1][0])
        if dst is not None:
            self.add_edge(call.dst, dst)
        return call

    def _add_call_edge(self, call, callee):
        key = (call.caller, call.site, _construct(call.origin))
        self.site_edges.setdefault(key, {})[callee] = None


def _construct(origin):
    if isinstance(origin, Call):
        return "decorator" if origin.decorator else "call"
    if len(origin) == 2:
        return (origin[0],)
    return origin[2]


class Call(Constraint):
    __slots__ = (
        "analysis",
        "caller",
        "args",
        "keywords",
        "dst",
        "site",
        "origin",
        "star",
        "double_star",
        "implicit",
        "decorator",
        "applies",
    )

    def __init__(
        self,
        analysis,
        caller,
        args,
        keywords,
        dst,
        site,
        origin=None,
        star=(),
        double_star=(),
        implicit=False,
    ):
        self.analysis = analysis
        self.caller = caller
        self.args = args
        self.keywords = keywords
        self.dst = dst
        self.site = site
        self.origin = self if origin is None else origin
        self.star = star
        self.double_star = double_star
        self.implicit = implicit
        self.decorator = False
        self.applies = False

    def apply(self, obj):
        self.analysis.call(obj, self)

    def results(self):
        return (self.dst,)


class _Returned:
    __slots__ = (
        "analysis",
        "call",
        "cls",
        "returned",
        "instances",
        "sees",
        "dst",
        "dsts",
        "held",
        "another",
    )

    def __init__(self, analysis, call, cls, instances):
        self.analysis = analysis
        self.call = call
        self.cls = cls
        self.returned = set()
        self.instances = instances
        self.sees = False
        self.dst = None
        self.dsts = []
        self.held = []
        self.another = False

    def add_dst(self, dst):
        if dst not in self.dsts:
            self.dsts.append(dst)
            if self.dst is not None:
                self.analysis.add_edge(self.dst, dst)

    def start(self, new):
        if self.dst is not None:
            return
        analysis = self.analysis
        self.dst = analysis.node()
        for dst in self.dsts:
            analysis.add_edge(self.dst, dst)
        analysis.solver.attach(new, Each(self.by_its_new, results=(self.dst,)))
        release = Each(self.release, results=(self.dst,))
        analysis.solver.attach(analysis.new_may_give_another(self.cls), release)
        analysis.solver.attach(self.dst, Each(self.by_new))

    def by_its_new(self, obj):
        if type(obj) is Instance and obj.cls is not self.cls and not self.another:
            self.held.append(obj)
        else:
            self.analysis.add_object(self.dst, obj)

    def release(self, marker):
        if not self.another:
            self.another = True
            for obj in self.held:
                self.analysis.add_object(self.dst, obj)
            self.held = []

    def by_new(self, obj):
        self.returned.add(obj)
        if self.sees and obj in self.instances:
            self._initialise(obj)

    def of_class(self, obj):
        self.sees = True
        self.instances.add(obj)
        if obj in self.returned:
            self._initialise(obj)

    def _initialise(self, obj):
        self.analysis.call_dunder(obj, "__init__", self.call, None)
