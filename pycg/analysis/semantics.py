"""The rules of the analysis: how loads, stores and calls act on each kind of
object, and the program-wide state that they build (objects, fields, class
hierarchies and call edges).

The builder states constraints through `Analysis` (`add_load`, `add_store`,
`add_call`) and the solver applies them to each object that reaches their
node. A call edge is recorded when a call constraint meets something
callable, so the call graph is complete when the solve ends.
"""

from collections import deque

from .annotations import Annotations
from .arguments import Arguments
from .attributes import MAX_EXTERNAL_STEPS, Attributes, Delete, Load, Store
from .builtin_models import DECORATOR, method_model
from .builtin_rules import BuiltinRules
from .containers import Containers
from .hierarchy import Hierarchy, opaque
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

# The functions that import a module by name; called with a str literal,
# they give the module that the builder resolved (`Analysis.literal_imports`).
IMPORTERS = frozenset({"importlib.import_module", "<builtin>.__import__"})

# A call passes at most this many receivers before its arguments (see
# `call_bound`). A callable that a bound method, a property or `__new__`
# calls with receivers may pass them on with one more: `C.__new__ = D` and
# `D.__new__ = C` make `C()` call `D(C)`, which calls `C(D, C)`, and so on;
# the cap makes that end. A property whose getter is a bound method passes
# two.
MAX_RECEIVERS = 3


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
):
    def __init__(self, cap=None):
        # What a node holds once it would hold more objects than `cap`, if
        # not None (see solver.py and `Saturated`).
        self.saturated = Saturated("<saturated>")
        self.solver = Solver(self.saturated, cap)
        # Which classes are unknown is decided between rounds (see
        # `Hierarchy.unknown_classes`).
        self.solver.between_rounds = self.unknown_classes
        # What the stubs say about outside code (see outside.py): the
        # definitions of outside names, and the typed value of each class.
        self.stubs = Stubs()
        self._stub_definitions = {}
        self._typed = {}
        self._closures = {}
        self.modules = {}
        self.externals = {}
        self.functions = []
        self.classes = []
        # The call edges by site: (caller name, site, construct) ->
        # {callee name: None}, where the construct is what makes the call
        # (see `_construct`).
        self.site_edges = {}
        # Each outside callee, with how the analysis knows it: "stub" (the
        # stub data or the builtin models declare it) or "name" (an access
        # path of a value without a type).
        self.external_callees = {}
        # Each call expression: its caller, its site and the node of its
        # callee (None if the callee has no value).
        self.call_expressions = []
        # (caller, site) of each expression that a statement, a
        # comprehension or a dict display iterates: an iteration at the
        # site of a call expression (`for x in f()`) is not one that the
        # callee makes (`list(x)`).
        self.iterated_expressions = set()
        # The nodes that the assignment graph output shows.
        self.named_nodes = []
        self._instances = {}
        # Implicit calls by finite key (see `call_dunder` and `site_call`).
        self._dunder_calls = {}
        # What each implicit call of `__new__` returns (see `instantiate`).
        self._new_results = {}
        # Class -> the instances of it that those have seen, in one set.
        self._class_instances = {}
        # The calls of the metaclass that each class statement makes, and
        # the `__new__` functions whose results run `__init__` (see
        # `add_metaclass_call`).
        self._statement_calls = {}
        self._statement_news = set()
        self._made_classes = set()
        # The call at the root of each implicit call that copies another.
        self._roots = {}
        self._site_calls = {}
        self._bound_methods = {}
        self._builtin_methods = {}
        self._wrappers = {}
        self._supers = {}
        self._fallbacks = {}
        self._fallback_nodes = {}
        self._returning = {}
        self.unknown_external = UnknownExternal("<unknown>", MAX_EXTERNAL_STEPS)
        self._generators = {}
        self._coroutines = {}
        # Call backs by origin, the calls they have called back, and the
        # argument nodes they call.
        self._callbacks = {}
        self._callback_values = set()
        # Calls to outside code with stubs, by call and callee, whose
        # arguments a builtin may call or call special methods of.
        self._typed_callbacks = set()
        # Opened files (see `Outside.open_file`): the copies of their mode
        # and buffering arguments, in order, and how many the completion has
        # handled; the calls whose mode may be unknown, and the (call, mode)
        # pairs that read the buffering.
        self._open_arguments = []
        self._completed_open_arguments = 0
        self._unknown_modes = set()
        self._open_modes = set()
        # Calls that bound methods make: (call, receivers) -> call, and back.
        self._prefixes = {}
        self._callees = {}
        self._model_bindings = {}
        # Each set of parameter names that a binding holds -> its one copy.
        self._name_sets = {}
        # (path, overload, number of parameters bound) -> the signature.
        self._stub_signatures = {}
        self._receiver_calls = {}
        self._handlers = set()
        self._unpacked = {}
        # Construct -> what iterating over its iterable gives (see
        # Containers.iterated).
        self._iterated = {}
        self._consts = {}
        self._containers = {}
        self._constants = {}
        self._subscriptions = set()
        # The stored keys that each key comparison of a construct has
        # called `__eq__` on (see `_KeyLookup`).
        self._compared_keys = {}
        # The rules that wait until a class may answer a name, by class,
        # name, `after` and `unless` (see `Hierarchy.later`).
        self._watches = {}
        # The loads of an attribute that no instance has yet, by class and
        # name: the result node of each load with the instances that it
        # loads the attribute of (see `read_field`).
        self._field_readers = {}
        # Observer notifications not yet made (see Containers.element).
        self._notices = deque()
        self._notifying = False
        self._external_modules = set()
        # The module that each call site imports by a str literal, if its
        # callee is an importer (see `IMPORTERS`).
        self.literal_imports = {}
        # The sites of `super()` without arguments, whose arguments the
        # builder supplies (see `BuiltinRules._rule_super`); the calls and
        # classes of `super(C, x)` with arguments that are paired; and the
        # receivers that Python accepts for each class `C`, shared by its
        # sites.
        self.zero_argument_super = set()
        self._super_pairs = set()
        self._super_accepted = {}
        # Entry points (see `_complete`): the receiver of each method with
        # the node of what it may hold, the functions that analysed code
        # called, and how many of each the completion has handled.
        self._receivers = []
        self._called = set()
        self._completed_receivers = 0
        # The entry receivers that the completion fills (see `_complete`).
        self._entry_receivers = []
        self._completed_functions = 0
        # Annotations as values (see annotations.py): the type forms by
        # site, the (node, destination, shape) triples read, the node of
        # each class and its subclasses, and the dataclass-like classes;
        # the analysed classes below each outside class (by stub path), and
        # the nodes of their instances or classes that annotations read.
        self._type_forms = {}
        self._annotated = set()
        self._tested_classes = set()
        # The subscriptions of the filters of class tests, one per (node of
        # a class expression or of a position of a tuple of classes, filter,
        # alternative, position), in order, for the completion; and the
        # names of the stub MRO of each stub class (see narrowing.py).
        self._class_filters = {}
        self._completed_class_filters = 0
        self._stub_ancestors = {}
        self._families = {}
        self._dataclass_like_classes = set()
        self._classes_below = {}
        self._below_nodes = {}
        # Patterns (see patterns.py): by prefix, suffix and case, what the
        # analysis knows of each, the names that stores assign (on any
        # object, and on each class), and each module's names when the
        # solve starts.
        self._patterns = {}
        self._pattern_states = {}
        self._store_names = set()
        self._class_store_names = {}
        self._module_names = {}
        # The operands of `+` and `%` that make patterns, with the node of
        # each result, and how many the completion has handled.
        self._pattern_operands = []
        self._completed_pattern_operands = 0
        # Reflection (see reflection.py): the node of the names of each
        # class and instance, and of the members of each class.
        self._namespace_nodes = {}
        # Subscripts by key node, and how many the completion has handled.
        self._keyed = []
        self._completed_keys = 0
        # getattr and setattr with names that are not literals, to decide.
        self._dynamic_accesses = []

    # Objects

    def module(self, name):
        if name not in self.modules:
            self.modules[name] = Module(name)
        return self.modules[name]

    def external(self, name, steps=0, inexact=False):
        """The external named `name`, `steps` loads past its root (see
        `External` for `inexact`). The module `builtins` is the namespace of
        the builtins, so a name in it is the builtin's: `builtins.len` is
        `<builtin>.len`."""
        module, dot, rest = name.partition(".")
        if module == "builtins":
            name = BUILTIN_MODULE + dot + rest
        key = (name, steps, inexact)
        if key not in self.externals:
            self.externals[key] = External(name, steps, inexact)
        return self.externals[key]

    def same_class(self, obj):
        """`obj`, or for an inexact external the external of the same class:
        the class that a hierarchy holds, so that C3 sees one class."""
        if isinstance(obj, External) and obj.inexact:
            return self.external(obj.name, obj.steps)
        return obj

    def function(self, name, module, signature, defaults, generator=False):
        """Create a function with nodes for its parameters and its return
        value, and for a generator function (`generator`) the nodes of what
        it yields and what is sent to it.

        `defaults` maps parameter names to the nodes of their default values.
        A default flows into its parameter at each call that may omit the
        argument, and, through the completion (see `solve`), when no
        analysed code calls the function.
        """
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
        """The decorator that the modelled callable `name` returns. One name
        may be both an analysed function and an outside one (a module
        `abc` that defines `abstractmethod` and imports the frozen `abc`),
        so whether it is analysed is part of the key."""
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
        """The instance of `cls` that stands for "an object of this class",
        whoever created it."""
        key = (cls, None)
        if key not in self._instances:
            self._instances[key] = Instance(cls, "<object>")
            self.add_object(cls.instances, self._instances[key])
        return self._instances[key]

    def add_method(self, cls, name, function, kind):
        """`function` is defined in the body of `cls` as `name`, plain or
        decorated with `kind` ("staticmethod" or "classmethod"). If its
        receiver (its first parameter, or `args[0]` for `def run(*args)`)
        holds nothing at a fixpoint, it gets every instance of `cls` and of
        its subclasses that inherit `name`; for a class method, `cls` and
        those subclasses; for a static method, nothing (see `_complete`)."""
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
        """How many objects, calls, nodes and per-key constraints the
        analysis made: every table of what it makes on demand while it
        solves. Finite by construction (see *Termination* in the design);
        the termination test bounds it, and checks that it covers every
        table."""
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
        )
        return sum(map(len, made))

    def bound_method(self, receiver, function):
        """`function` (an analysed function or an outside method) bound to
        `receiver`."""
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
        """The `kind` object (`staticmethod`, `classmethod`, `property`) that
        `call` creates."""
        key = (kind, call.origin)
        if key not in self._wrappers:
            self._wrappers[key] = Wrapper(kind, call.site)
        return self._wrappers[key]

    # Nodes

    def node(self, label=None):
        """Create a node. A labelled node is shown in the assignment graph
        output."""
        node = Node(label)
        if label is not None:
            self.named_nodes.append(node)
        return node

    def field(self, obj, name):
        if name not in obj.fields:
            obj.fields[name] = node = self.node(f"{obj.name}.{name}")
            if type(obj) is Instance:
                # The loads that waited for this attribute (see `read_field`).
                readers = self._field_readers.get((obj.cls, name), {})
                for dst, receivers in readers.items():
                    if obj in receivers:
                        self.add_edge(node, dst)
        return obj.fields[name]

    def read_field(self, instance, name, dst):
        """dst ⊇ the attribute `name` of `instance` itself. The node of an
        attribute of an instance is made when something first asks for it
        to write it (`field`); until then a load of it is an entry in a
        list of its class and name, and nothing else."""
        node = instance.fields.get(name)
        if node is not None:
            self.add_edge(node, dst)
            return
        readers = self._field_readers.setdefault((instance.cls, name), {})
        readers.setdefault(dst, []).append(instance)

    def constant(self, obj):
        """Return a node that holds only `obj`."""
        if obj not in self._constants:
            self._constants[obj] = self.solver.constant(obj)
        return self._constants[obj]

    # Constraints

    def add_object(self, node, obj):
        self.solver.add_object(node, obj)

    def add_edge(self, src, dst):
        self.solver.add_edge(src, dst)

    def add_load(self, base, attr, dst, caller, site):
        """dst ⊇ base.attr, in the scope named `caller`. A property getter
        that the load runs is called from there."""
        self.solver.attach(base, Load(self, attr, dst, caller, site))

    def add_store(self, base, attr, src, caller, site):
        """base.attr ⊇ src, in the scope named `caller`. A property setter
        that the store runs is called from there."""
        self.pattern_store_name(attr)
        self.solver.attach(base, Store(self, attr, src, caller, site))

    def add_delete(self, base, attr, caller, site):
        """del base.attr, in the scope named `caller`."""
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
    ):
        """dst ⊇ callee(*args, **keywords), called from the scope named
        `caller`.

        The arguments are described under `Call`. `site` names the call in
        instance names. `dst` may be None if the result is not used. A
        `decorator` call applies a decorator to its one argument; any other
        is a call expression, whose `callee` is None if it has no value.
        """
        if not decorator:
            self.call_expressions.append((caller, site, callee))
        if callee is None:
            return
        call = Call(self, caller, args, keywords, dst, site, None, star, double_star)
        call.decorator = decorator
        self.solver.attach(callee, call)

    def solve(self):
        """Solve the constraints; at each fixpoint, first decide the class
        hierarchies that still wait (see `Hierarchy.decide_hierarchies`),
        and only when none waits complete what the solve cannot find on its
        own (see `_complete`); solve again, until nothing is added."""
        self.freeze_module_names()
        self.solver.solve()
        while self.decide_hierarchies() or self._complete():
            self.solver.solve()

    def _complete(self):
        """Add what the solve cannot find on its own, at a fixpoint. Each
        step only adds: what a later solve brings is added to, never taken
        back (see *Order of the fixpoint steps* in the design). The steps,
        in order:

        1. Code that no analysed code calls is an entry point: a receiver
           that holds nothing gets every instance of its class and of its
           subclasses (the classes, for a class method), and a function
           that no analysed code calls gets its defaults.
        2. A subscript whose key holds nothing reads or writes every element
           (see containers.py).
        3. getattr and setattr with names that are not literals get the
           names their name nodes hold (see builtin_rules.py).
        4. A class test whose class expression, or a position of whose
           tuple of classes, holds nothing lets every value pass (see
           narrowing.py).
        5. Only when the steps before added nothing, so that what they add
           (defaults, the targets of computed names) has reached the
           arguments: the mode or buffering of an opened file that holds
           nothing is unknown (see outside.py).
        6. Only when step 5 added nothing too, for the same reason (an entry
           point's receiver reaches `__getattr__`, which gets a name): an
           operand of a pattern of `+` or `%` that holds nothing makes the
           result a str of unknown value as well (see patterns.py).

        Return whether anything was added.
        """
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
                    # A saturated receiver absorbs it: no progress.
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
        """Whether `obj`, an instance of `cls` or of a subclass (or such a
        class, for a class method), may run `function`, which `cls` defines
        as `name`: in some MRO of its class, the first analysed class body
        that defines `name` is that of `cls`, or binds `function` itself
        there (`run = Base.run`), also wrapped in a static or class method.
        A class that reaches an instance method's receiver is an instance of
        a metaclass and passes, as do opaque values."""
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
        """Whether the class attribute `name` of `cls` may hold `function`,
        or a static or class method that wraps it, at this fixpoint."""
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
        """The functions that a call of the saturated value may run: those
        that reached a saturated node themselves, bound, wrapped (a static
        or class method), or as the methods of a class or instance that
        did. They are called (see `_complete`). Code that only a call
        through such code reaches is not known to be called."""
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

    # Calls

    def call(self, obj, call):
        match obj:
            case Function():
                if not self.returns_argument(obj, call):
                    self._call_function(obj, call, None)
            case UnknownExternal():
                self._outside_result(call)
            case ReturnsArgument():
                self.model_edge(obj.name, obj.analysed, call)
                self.return_argument(DECORATOR, obj.name, obj.analysed, call)
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
                # Through the worklist: flow-insensitively a wrapper can wrap
                # itself (f = staticmethod(f)).
                self.add_edge(self.field(obj, "__func__"), self._callee(call))
            case BuiltinMethod():
                self.add_external_call_edge(obj.name, call, "stub")
                rule = method_model(obj.type_name, obj.method)
                self.apply_rule(rule, call, obj.receiver)
            case External():
                module = self.literal_imports.get(call.site)
                if module is not None and obj.name in IMPORTERS:
                    # An import by a str literal (see builder.py).
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
        """The result of a call of outside code without stubs, named or not:
        the external without a name, so nothing loaded from it, no element
        of it and no call of it names a callee (see *External names* in the
        design). A decorator may also return what it decorates, its last
        argument after any receivers."""
        if call.dst is None:
            return
        self.add_object(call.dst, self.unknown_external)
        if call.decorator and call.args[-1] is not None:
            self.add_edge(call.args[-1], call.dst)

    def add_external_call_edge(self, name, call, known):
        """The edge of `call` to the outside name `name`, which the analysis
        knows as `known` (see `external_callees`; the stub data wins). Only
        call expressions give edges to code outside the analysed modules,
        not the implicit calls that the interpreter makes."""
        if not call.implicit:
            self._add_call_edge(call, name)
            if self.external_callees.get(name) != "stub":
                self.external_callees[name] = known

    def unresolved_calls(self):
        """The call expressions whose callee is not known, after the solve,
        by (caller, site), with the cause: "saturated" for a callee that
        holds the saturated value (see `Solver.cap`), or an unknown class
        or an instance of one (see `unknown_classes`), and that gave no edge
        before, "computed name" for what `getattr` gives with a name that
        is not a literal and whose names are not known (see `names_known`),
        "outside value" for the external without a name (see
        `unknown_external`), else "no value". A callee that holds another
        value is known, though the call may give no edge (a class whose
        `__init__` is object's, a method of an abstract outside class)."""
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
        """Call the functions, bound methods and callable instances in the
        nodes `values`, which `call` passes to a builtin that applies them
        (see `Outside.call_back_builtin`), whether `call` is a call
        expression or an implicit call. The calls come from the caller of
        `call`, with unknown arguments. Classes are not instantiated. The
        builtin makes these calls, so they are implicit.

        There is one call back per origin (its scope and site are the
        origin's), and every call with that origin passes its arguments to
        it: a call that adds receivers to another keeps its origin and has
        other arguments."""
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
        """Call a function, bound method or instance (see `_call_back`)."""
        self.call(obj, callback)

    def call_bound(self, obj, receivers, call):
        """Call `obj` with `receivers` before the arguments of `call`, as a
        bound method does. If `call` is itself a call that a bound method
        makes, its receivers come after these. At most `MAX_RECEIVERS` are
        passed, the innermost. A function binds the first to its first
        parameter; any other callable (a class, a callable instance, a
        static method) gets them as arguments."""
        base, prefix = self._prefixes.get(call, (call, ()))
        receivers = (receivers + prefix)[:MAX_RECEIVERS]
        if isinstance(obj, Function):
            rest = self._prefixed_call(base, receivers[1:])
            self._call_function(obj, rest, receivers[0])
        else:
            self.call(obj, self._prefixed_call(base, receivers))

    def _prefixed_call(self, base, receivers):
        """The call `base` with the constants of `receivers` before its
        arguments: one per call and tuple of receivers."""
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
            self._receiver_calls[key] = call
            self._prefixes[call] = (base, receivers)
        return self._receiver_calls[key]

    def _callee(self, call):
        """A node whose objects `call` calls, through the worklist."""
        if call not in self._callees:
            node = self.node()
            self.solver.attach(node, call)
            self._callees[call] = node
        return self._callees[call]

    def _call_function(self, function, call, receiver):
        if not self._may_bind(function, call, receiver):
            # Python raises before the function starts.
            return
        self._add_call_edge(call, function.name)
        self._called.add(function)
        self._function_result(function, call, receiver)

    def _function_result(self, function, call, receiver):
        """What a call of `function` does but its edge: bind the arguments
        of `call`, and `receiver` if it is not None, and give `call` what
        the function returns (its generator or coroutine for those
        functions)."""
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
        """Whether `call` may bind its arguments to the parameters of
        `function`. Decided only where both are known in full: the call
        comes from a call expression without `*` or `**` arguments (its
        own call, or the `__new__`, `__init__` or `__call__` that it runs,
        which get its arguments), and the function has no decorator but
        `staticmethod` or `classmethod`. Receivers count as positional
        arguments."""
        if call.star or call.double_star or function.decorated:
            return True
        base = self._prefixes.get(call, (call, ()))[0]
        if self._roots.get(base, base).implicit:
            return True
        signature = function.signature
        given = len(call.args) + (receiver is not None)
        if given > len(signature.positional) and signature.vararg is None:
            return False
        filled = set(signature.positional[:given])
        for name, _ in call.keywords:
            if signature.accepts_keyword(name):
                if name in filled:
                    return False
                filled.add(name)
            elif signature.kwarg is None:
                return False
        required = [
            name
            for name in (*signature.positional, *signature.keyword_only)
            if name not in function.optional
        ]
        return all(name in filled for name in required)

    def instantiate(self, cls, call):
        """A call of the class `cls`, as `type.__call__` makes it: it calls
        `__new__` with the class and the arguments, gives what that returns,
        and calls `__init__` with the arguments on it if it is an instance
        of `cls` (or of a subclass). Where Python's own `__new__` (or an
        outside base's) runs, it returns the instance that this call
        creates. An analysed `__new__` is a static method that takes the
        class (see the builder); it gives what it returns."""
        default = self.python_method(cls, "__new__")
        self.solver.attach(
            default, Each(self._python_new, cls, call, results=(call.dst,))
        )
        new = self._implicit_call(cls, "__new__", call, call.dst)
        if new not in self._new_results:
            instances = self._class_instances.setdefault(cls, set())
            returned = _Returned(self, call, instances)
            self._new_results[new] = returned
            self.solver.attach(
                self.lookup(cls, "__new__", cls),
                Each(self._new, cls, new, results=(new.dst,)),
            )
            self.solver.attach(new.dst, Each(returned.by_new))
            self.solver.attach(cls.instances, Each(returned.of_class))

    def add_init_subclass(self, cls, keywords, double_star, caller, site):
        """The class statement at `site` that creates `cls` calls the
        `__init_subclass__` of the nearest base that defines it (the lookup
        after `cls`), a class method bound to `cls`, with the keyword
        arguments of the statement but `metaclass`, from the scope
        `caller`. The nodes of `**mapping` arguments are `double_star`."""
        origin = ("init_subclass", site)
        call = Call(
            self, caller, [], keywords, None, site, origin, (), double_star, True
        )
        self.solver.attach(self.lookup(cls, "__init_subclass__", cls, cls), call)

    def add_set_name(self, value, cls, name, caller, site):
        """The class statement at `site` that creates `cls` calls the
        `__set_name__` of each instance or class that its body binds to
        `name`, with the class and the name, implicitly, from the scope
        `caller`."""
        kinds = (Instance, Class)
        set_name = Each(self._set_name, cls, name, caller, site, kinds=kinds)
        self.solver.attach(value, set_name)

    def _set_name(self, obj, cls, name, caller, site):
        args = [self.constant(cls), self.constant(self.const(name))]
        call = self.site_call(caller, site, ("set_name", name), args)
        self.call_dunder(obj, "__set_name__", call, None)

    def add_metaclass_call(self, cls, statement, caller, site):
        """The class statement at `site` that creates `cls` is a call of
        each analysed metaclass of `cls`, implicitly, from the scope
        `caller`, with the name, a tuple of the bases, a dict of the
        namespace, and the keyword arguments (`statement` holds them, from
        the builder): first the metaclass's `__prepare__` (with the name,
        the bases and the keywords), then `__new__` and `__init__` as for
        any call of a class (see `instantiate`). Where Python's own
        `type.__new__` runs, it makes `cls`, and `__init__` runs on it; an
        analysed `__new__` is called with the metaclass, and `__init__` runs
        on each class that it may return, with that class's own statement
        (see `_statement_made`). `type` itself calls nothing that the
        analysis reports."""
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
        """The `__new__` of a metaclass may return the class `cls`: its
        `__init__` runs with the arguments of the statement of `cls`. The
        analysis does not tell apart the statements that call one `__new__`
        (`type.__new__` gives every class of the metaclass, see
        `Outside._new_instance`), but each statement makes its own class,
        and `__init__` is the same method for each; so the work grows with
        the number of classes, not with its square. The statement of `cls`
        may make its call later (see `_call_metaclass`)."""
        self._made_classes.add(cls)
        calls = self._statement_calls.get(cls)
        if calls is not None:
            self.call_dunder(cls, "__init__", calls[0], None)

    def _python_new(self, method, cls, call):
        """Python's own `__new__` makes an instance, once Python may make
        an object of `cls` (see `Hierarchy._concrete`), and `__init__` runs
        on it."""
        made = Each(self._python_instance, call, results=(call.dst,))
        self.solver.attach(cls.instantiable, made)

    def _python_instance(self, cls, call):
        instance = self.instance(cls, call)
        if call.dst is not None:
            self.add_object(call.dst, instance)
        self.call_dunder(instance, "__init__", call, None)

    def _new(self, method, cls, call):
        """Call the `__new__` that an analysed class defines; an outside
        one is Python's (see `_python_new`)."""
        if not isinstance(method, External):
            self.call_bound(method, (cls,), call)

    def call_dunder(self, obj, name, call, dst, unless=()):
        """Call the special method `name` of the instance or class `obj`:
        the method of its type (see `_types`), bound to `obj`, with the
        arguments of `call`; with `unless`, only where Python falls back to
        it (see `Hierarchy.lookup`).

        The implicit call is a copy of the call that `call` comes from: the
        call expression, site call or call back at the root of the chain of
        implicit calls that copy each other (`_roots`), with the receivers
        that bound methods add, at most `MAX_RECEIVERS` (see `call_bound`).
        It is made once per instance, method name, root call and `unless`,
        and each request adds an edge from its result to `dst`. So an
        instance stored as its class's `__call__`, a class stored as its own
        `__init__` or a class method of it, makes finitely many implicit
        calls (see *Termination*).
        """
        if type(obj) is Instance:
            # The class decides the method: the call is made once the class
            # may have one.
            rule = self._call_dunder
            self.later(obj.cls, name, obj, None, unless, rule, name, call, dst, unless)
        else:
            self._call_dunder(obj, name, call, dst, unless)

    def _call_dunder(self, obj, name, call, dst, unless):
        implicit = self._implicit_call(obj, name, call, dst, unless)
        # The implicit call is that of one instance, method name and
        # `unless` (see `_implicit_call`), so it tells whether this was done.
        if not implicit.attached:
            implicit.attached = True
            method = Each(
                self._type_method, obj, name, implicit, unless, results=(implicit.dst,)
            )
            self.solver.attach(self._types(obj), method)

    def _types(self, obj):
        """The node of the types of the instance or class `obj`, which
        decide its special methods: the class for an instance, the
        metaclasses for a class (an outside metaclass is an external)."""
        if isinstance(obj, Instance):
            return self.constant(obj.cls)
        return obj.metaclass

    def _type_method(self, cls, obj, name, implicit, unless):
        """Call the special method `name` of `obj` with `implicit`: the
        method of its type `cls`, bound to `obj`; an outside metaclass's
        (`type`'s) as the stubs give it."""
        if isinstance(cls, Class):
            self.solver.attach(self.lookup(cls, name, obj, None, unless), implicit)
            return
        method = self.node()
        for definition in self.stub_definitions(cls) or ():
            if definition.kind == "class":
                self.stub_member(obj, definition.path, cls.name, name, method)
        self.solver.attach(method, implicit)

    def _implicit_call(self, owner, name, call, dst, unless=()):
        """The implicit call of the method `name` of `owner` (an instance,
        or a class for `__new__`) that `call` causes: a copy of the call at
        the root of its chain, with the receivers of `call` (see
        `call_dunder`). Each request adds an edge from its result to
        `dst`."""
        base, receivers = self._prefixes.get(call, (call, ()))
        root = self._roots.get(base, base)
        key = (owner, name, root, unless)
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
            self._dunder_calls[key] = template
            self._roots[template] = root
        # Every call that shares the root has its arguments (see
        # *Termination*); one that did not would lose them here.
        assert (template.args, template.keywords) == (base.args, base.keywords)
        assert (template.star, template.double_star) == (base.star, base.double_star)
        implicit = self._prefixed_call(template, receivers)
        if dst is not None:
            self.add_edge(implicit.dst, dst)
        return implicit

    def site_call(
        self, caller, site, role, args=(), implicit=True, dst=None, rest=None
    ):
        """The call that the construct at `site` makes, in the scope named
        `caller`, for `role` (a tuple of names, such as `("iterate",)` for
        the `__iter__` of a for loop): by default an implicit one. `rest`,
        if not None, is a node of arguments at any position after `args`.

        There is one such call per scope, construct and role, whose origin
        is that key; another request for it with other argument or result
        nodes is joined to its nodes by edges. So the calls, and the
        instances they create, are finite (see *Termination*). Every
        request for one role passes the same number of arguments: a role
        names what the construct calls, and that decides the arguments
        (`("hook", "Store", name)` passes the name and the value)."""
        key = (caller, site, role, implicit)
        call = self._site_calls.get(key)
        if call is None:
            nodes = [self.node() for _ in args]
            # `f(*args, *untracked, rest)`: `rest` binds at any later position.
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
    """What makes the calls with `origin` (see `Call`): "call" for a call
    expression, "decorator" for a decorator application, the role of an
    implicit call that a construct makes (see `site_call`), or the step of
    a class statement ("class statement", "prepare", "init_subclass").
    The calls that a call expression causes (`__init__`, call backs) share
    its origin."""
    if isinstance(origin, Call):
        return "decorator" if origin.decorator else "call"
    if len(origin) == 2:
        return (origin[0],)
    return origin[2]


class Call(Constraint):
    """A call. `args` holds a node per positional argument before the first
    unpacked one (None for an argument without a value); `star` holds the
    nodes of the positional arguments from the first `*iterable` on, each
    with whether it is unpacked; `keywords` holds a (name, node) pair per
    keyword argument and `double_star` the nodes of the `**mapping`
    arguments.

    `origin` is the call written in the source; an implicit call such as
    `__init__` shares the origin of the call that caused it. The origin
    identifies the instances that a call creates. An `implicit` call is one
    that the interpreter makes, not a call expression: it gives no edges to
    code outside the analysed modules. A `decorator` call applies a
    decorator to its one argument. `attached` is true once
    `Analysis.call_dunder` attached the call, the implicit call of a special
    method, to the types of its instance.
    """

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
        "attached",
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
        self.attached = False

    def apply(self, obj):
        self.analysis.call(obj, self)

    def results(self):
        # A call of the saturated value: no edge (the site is unresolved,
        # see `unresolved_calls`), and the result is saturated.
        return (self.dst,)


class _Returned:
    """What an implicit call of `__new__` for a class returns, and the
    instances of the class and its subclasses: `__init__` runs, with the
    arguments of `call`, on each object that is both (see
    `Analysis.instantiate`). Each side may arrive
    first: a class's instances grow as its subclasses get their bases.

    The calls of a class share the set `instances`: a class has thousands
    of calls and of instances. Each call sees every instance, in the same
    rounds, unless it comes after the instances of the class saturated: it
    then sees none, and `sees` stays false."""

    __slots__ = ("analysis", "call", "returned", "instances", "sees")

    def __init__(self, analysis, call, instances):
        self.analysis = analysis
        self.call = call
        self.returned = set()
        self.instances = instances
        self.sees = False

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
