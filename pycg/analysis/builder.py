"""Turn the AST of one module into constraints.

The builder walks each module once. Every expression that can hold an object
gets a node (see expressions.py); statements become subset edges between
nodes and load, store and call constraints on them. The builder never reads
points-to sets: the solver resolves everything later. Statements without a
handler are walked, so calls inside them are found.
"""

import ast
from contextlib import contextmanager
from importlib.util import resolve_name

from .annotations import AnnotationBuilder, OwnStub, imported_names
from .expressions import TYPE_CHECKING_IMPORTS, TYPING_MODULES, Expressions
from .flow import FALSE, TRUE, UNBOUND, UNKNOWN, Flow, State, literals_of
from .matching import Matching
from .model import BUILTIN_MODULE, Signature
from .narrowing import ClassTestBuilder
from .patterns import PatternBuilder
from .scopes import CLASS, COMPREHENSION, MODULE, analyse_scopes
from .stubs import Stubs

# Names that the interpreter gives every module, which the stubs of
# `builtins` do not list.
MODULE_NAMES = frozenset(
    {"__debug__", "__doc__", "__loader__", "__name__", "__package__", "__spec__"}
)


def _builtin_names():
    """The names of the builtins in every version and on every platform,
    from the stubs, so that the results do not depend on the interpreter
    that runs the analysis (not the stubs' private helpers, nor the classes
    that exist only in stubs), and the names that every module has."""
    names = Stubs().module("builtins")["names"]
    return MODULE_NAMES | frozenset(
        name
        for name, entry in names.items()
        if not (name.startswith("_") and not name.startswith("__"))
        and not entry.get("tco")
    )


BUILTIN_NAMES = _builtin_names()

# The class attributes that a class statement turns from a plain function
# into a static or class method (`type.__new__` does). Each takes the class
# first, so a receiver that no analysed call gives gets the classes.
IMPLICIT_METHODS = {
    "__new__": "staticmethod",
    "__init_subclass__": "classmethod",
    "__class_getitem__": "classmethod",
}


class ModuleBuilder(
    Matching, Expressions, AnnotationBuilder, PatternBuilder, ClassTestBuilder
):
    """Emits the constraints of one module.

    `module` is the analysis object of the module and `is_package` tells
    whether its file is an `__init__.py`, which matters for relative imports.
    `is_entry` tells whether it is an entry point, which may run as
    `__main__` or be imported. `stub` is the tree of the module's own stub
    (`x.pyi` beside `x.py`), which gives the annotations that the source
    leaves out (see annotations.py), or None.
    """

    def __init__(
        self, analysis, imports, module, tree, is_package, is_entry=False, stub=None
    ):
        self.analysis = analysis
        self.imports = imports
        self.module = module
        self.tree = tree
        self.is_package = is_package
        self.is_entry = is_entry
        self.scopes = analyse_scopes(tree, module.name)
        # The names that imports under `if TYPE_CHECKING:` would bind, which
        # bind nothing at run time: the qualified name that the import would
        # bind (`mod.Name`, `mod.Class.Name` in a class body) to the dotted
        # name it would import. For resolving annotations only.
        self.type_only_names = {}
        # Modules imported with `from ... import *`, in order.
        self.star_imports = []
        self._scope = self.scopes.module
        self._function = None
        self._classes = {}
        self._variables = {}
        # For each scope, the names that walked code binds but the builder
        # does not track, with their nodes (see `_untracked`).
        self._untracked_names = {}
        self._builtin_globals = {}
        # The names that imports bind to `importlib` and to
        # `importlib.import_module` (see `literal_import`).
        self._importlib_names = set()
        self._import_module_names = set()
        # The definitions of the scopes whose statements are being walked
        # (see flow.py), and those of the current one.
        self._flow = Flow(self.analysis)
        self._flows = {self.scopes.module: self._flow}
        # What `bool()` of an evaluated expression gives and the literal
        # values it has, where known (see `Expressions._facts`).
        self._known_facts = {}
        # The nodes of the operands of each binary operator, for the
        # patterns that `+` and `%` make (see `Expressions.expression`).
        self._binop_operands = {}
        # The tests that `TYPE_CHECKING` decides, with the truth they have
        # for a type checker.
        self._type_checking = {}
        # The class tests that the builder evaluated, by call, and the node
        # that each gives its name where it holds (see narrowing.py).
        self._class_tests = {}
        self._narrowed_nodes = {}
        self.own_stub = None
        if stub is not None:
            self.own_stub = OwnStub(stub, self._absolute_module_name)
        # The path of the stub's scope whose annotation is being read, or
        # None for the source's (see annotations.py).
        self._reading_stub = None
        # By module or class scope, the names that the source annotates.
        self._source_annotated = {}
        # By path, the class definitions that a stub class names.
        self._stub_classes = {}

    def build(self):
        try:
            self._statements(self.tree.body)
        finally:
            # The names that the module binds at run time, in order: a load
            # of another calls its `__getattr__`, and a star import of it
            # takes the public ones (unless it declares `__all__`).
            self.defined = list(self._bound_at_end(self.scopes.module))
            self.module.defines.update(self.defined)

    # Context

    @contextmanager
    def _inside(self, scope, function):
        saved = (self._scope, self._function, self._flow)
        self._scope, self._function = scope, function
        if scope.kind != COMPREHENSION:
            # A comprehension binds only names that are not tracked.
            self._flow = self._flows[scope] = Flow(self.analysis)
            if function is not None:
                # The parameters are the first definitions of a function.
                for name, parameter in function.parameters.items():
                    if self.scopes.tracked(scope, name):
                        definition = (parameter, False, UNKNOWN, None)
                        self._flow.state.changes[name] = definition
        try:
            yield
        finally:
            self._flows.pop(scope, None)
            self._scope, self._function, self._flow = saved

    @property
    def _caller(self):
        return self._scope.caller.name

    def _site(self, node):
        return self._span(node, node)

    def _span(self, first, last):
        """The site from the start of the node `first` to the end of the
        node `last`."""
        start = f"{self.module.name}:{first.lineno}:{first.col_offset}"
        return f"{start}#{last.end_lineno}:{last.end_col_offset}"

    # Names

    def _variable(self, scope, name):
        """The node of the variable `name` bound in `scope`. Module and class
        variables are fields of their module or class."""
        if scope.kind == MODULE:
            return self.analysis.field(self.module, name)
        if scope.kind == CLASS:
            return self.analysis.field(self._classes[scope], name)
        key = (scope, name)
        if key not in self._variables:
            self._variables[key] = self.analysis.node(f"{scope.name}.{name}")
        return self._variables[key]

    def _load_name(self, name):
        return self._read_name(name)[0]

    def _read_name(self, name):
        """Read the name `name` in the current scope: the node of its value,
        and what `bool()` of it may give and its literal values (see
        flow.py). A reader that runs in statement order with the scope that binds it
        reads the definitions that reach it; any other reads the variable,
        which every definition flows into."""
        unknown = (UNKNOWN, None)
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        if scope.kind == CLASS and scope is not self._scope:
            # The implicit `__class__` variable of a function in a class.
            return self.analysis.constant(self._classes[scope]), unknown
        if self._is_builtin(scope, name):
            facts = unknown
            if name == "__name__" and not self.is_entry and not scope.dynamic:
                # Not bound by the module, which is not an entry point (an
                # entry point may run as `__main__` or be imported): the
                # module's own name.
                facts = (TRUE, literals_of(self.module.name))
            return self._builtin_global(name), facts
        definition = self._reaching(scope, name)
        if definition is None and scope.kind == CLASS:
            # The class body does not track its names (it uses its
            # namespace): any value that it binds, or, where the name may be
            # unbound, the module's and the builtin's (LOAD_NAME, below).
            definition = (self._variable(scope, name), True, UNKNOWN, None)
        if definition is None:
            # Read at other times: known only for a name that is always the
            # same import.
            facts = unknown
            if self.scopes.imported(scope, name) in TYPE_CHECKING_IMPORTS:
                facts = (FALSE, literals_of(False))
            return self._variable(scope, name), facts
        value, unbound, truth, values = definition
        if not unbound:
            return value, (truth or UNKNOWN, values)
        if scope.kind == CLASS:
            # Where a class body has not bound the name, it reads it from
            # the module globals and the builtins (LOAD_NAME), never from an
            # enclosing function.
            module_value = self._value_of(self.scopes.module, name)
            return self._join([value, module_value]), unknown
        if scope.kind == MODULE and name in BUILTIN_NAMES:
            builtin = self.analysis.external(f"{BUILTIN_MODULE}.{name}")
            value = self._join([value, self.analysis.constant(builtin)])
            return value, unknown
        return value, (truth or UNKNOWN, values)

    def _value_of(self, scope, name):
        """The node of the module name `name` read from the current scope
        (a class body's fallback), or of the builtin."""
        if self._is_builtin(scope, name):
            return self._builtin_global(name)
        definition = self._reaching(scope, name)
        if definition is None:
            return self._variable(scope, name)
        value, unbound = definition[:2]
        if unbound and name in BUILTIN_NAMES:
            builtin = self.analysis.external(f"{BUILTIN_MODULE}.{name}")
            return self._join([value, self.analysis.constant(builtin)])
        return value

    def _reaching(self, scope, name):
        """The definition of `name`, bound in `scope`, that reaches the
        current point (see flow.py), or None if the current scope does not
        read it in statement order: the name is not tracked, or the reader
        runs at other times."""
        flow = self._flows.get(scope)
        if (
            flow is None
            or not self.scopes.tracked(scope, name)
            or not self.scopes.inline(self._scope, scope)
        ):
            return None
        return flow.read(name)

    def _bind(self, name, value, truth=UNKNOWN, values=None):
        """Bind `name` in the current scope to `value` (None if untracked),
        whose truth is `truth` and whose literal values are `values`. A
        tracked name gets a new definition; the variable gets the value
        too, for readers that do not run in statement order (and the
        assignment graph), except in a class body, whose namespace is what
        reaches its end."""
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        if scope is self._scope and self.scopes.tracked(scope, name):
            self._flow.define(name, value, truth, values)
            if scope.kind == CLASS:
                return
            variable = self._variable(scope, name)
        else:
            variable = self._untracked(scope, name)
        if value is not None:
            self.analysis.add_edge(value, variable)

    def _untracked(self, scope, name):
        """The node of every value that walked code binds to `name`, which
        `scope` binds but does not track: its variable, or in a class body
        a node that becomes the member at the end of the body (see
        `_bound_at_end`)."""
        bound = self._untracked_names.setdefault(scope, {})
        if name not in bound:
            if scope.kind == CLASS:
                bound[name] = self.analysis.node()
            else:
                bound[name] = self._variable(scope, name)
        return bound[name]

    def _bound_at_end(self, scope):
        """The names that the module or class body `scope`, whose statements
        were just walked, may bind at their end, each with the node of its
        value (None if untracked): for a tracked name, the definitions that
        reach the end; for another, every value that walked code binds."""
        state = self._flows[scope].state
        members = {}
        for name in state.changed(None):
            definition = state.get(name)
            if definition != UNBOUND:
                members[name] = definition[0]
        members.update(self._untracked_names.get(scope, {}))
        return members

    def _unbind(self, name):
        """`del name`, or the end of an `except ... as name` handler."""
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        if scope is self._scope and self.scopes.tracked(scope, name):
            self._flow.unbind(name)

    def _is_builtin(self, scope, name):
        """True if `name`, resolved to `scope`, may be a builtin: the module
        does not bind it, so it is a builtin unless a star import or another
        module sets it."""
        return (
            scope.kind == MODULE and name not in scope.bound and name in BUILTIN_NAMES
        )

    def builtin_name(self, name):
        """The node of the builtin `name`, or None if no builtin has it."""
        if name not in BUILTIN_NAMES:
            return None
        return self.analysis.constant(
            self.analysis.external(f"{BUILTIN_MODULE}.{name}")
        )

    def _builtin_global(self, name):
        """A node for a builtin name: the module global of that name, if
        anything sets it, and the builtin."""
        if name not in self._builtin_globals:
            node = self.analysis.node()
            self.analysis.add_edge(self.analysis.field(self.module, name), node)
            builtin = self.analysis.external(f"{BUILTIN_MODULE}.{name}")
            self.analysis.add_object(node, builtin)
            self._builtin_globals[name] = node
        return self._builtin_globals[name]

    def _is_builtin_reference(self, node, name):
        if not (isinstance(node, ast.Name) and node.id == name):
            return False
        return self._is_builtin(self.scopes.resolve(self._scope, name), name)

    # Statements

    def _statements(self, statements):
        """Walk `statements` in order, up to the first that cannot run (see
        *Code that cannot run* in the design)."""
        for statement in statements:
            if not self._flow.state.reachable:
                return
            self.statement(statement)

    def statement(self, node):
        handler = getattr(self, f"_stmt_{type(node).__name__}", None)
        if handler is None:
            self._walk(node)
        else:
            handler(node)

    def _stmt_FunctionDef(self, node):
        scope = self.scopes.scope_of(node)
        decorators = [self.expression(decorator) for decorator in node.decorator_list]
        function = self._function_object(node, scope)
        function.decorated = any(
            not (_names(d, "staticmethod") or _names(d, "classmethod"))
            for d in node.decorator_list
        )
        if self._scope.kind == CLASS:
            kind = next(
                (
                    name
                    for name in ("staticmethod", "classmethod")
                    if any(_names(d, name) for d in node.decorator_list)
                ),
                None,
            )
            if node.name in IMPLICIT_METHODS:
                kind = "classmethod"
            self.analysis.add_method(
                self._classes[self._scope],
                self._scope.mangle(node.name),
                function,
                kind,
            )
        # A function is true; a decorator may return any value.
        truth = UNKNOWN if node.decorator_list else TRUE
        self._bind(node.name, self._decorate(node, decorators, function), truth)
        with self._inside(scope, function):
            self._statements(node.body)

    _stmt_AsyncFunctionDef = _stmt_FunctionDef

    def _decorate(self, node, decorators, obj):
        """The value of a decorated definition of `obj`: the decorators,
        whose values are `decorators`, applied bottom-up. Each application
        is a call from the enclosing function or module."""
        value = self.analysis.constant(obj)
        for decorator, expression in reversed(
            list(zip(decorators, node.decorator_list))
        ):
            if decorator is None:
                value = None
                continue
            result = self.analysis.node()
            self.analysis.add_call(
                decorator,
                self._caller,
                [value],
                [],
                result,
                self._site(expression),
                decorator=True,
            )
            value = result
        return value

    def _function_object(self, node, scope):
        """Create the function object of a def or lambda. Its default values
        are evaluated in the enclosing scope."""
        arguments = node.args
        positional = [
            scope.mangle(arg.arg) for arg in arguments.posonlyargs + arguments.args
        ]
        keyword_only = [scope.mangle(arg.arg) for arg in arguments.kwonlyargs]
        vararg = scope.mangle(arguments.vararg.arg) if arguments.vararg else None
        kwarg = scope.mangle(arguments.kwarg.arg) if arguments.kwarg else None
        signature = Signature(
            positional=positional,
            positional_only_count=len(arguments.posonlyargs),
            keyword_only=keyword_only,
            vararg=vararg,
            kwarg=kwarg,
        )
        defaults = {}
        with_defaults = positional[len(positional) - len(arguments.defaults) :]
        for name, default in zip(with_defaults, arguments.defaults):
            defaults[name] = self.expression(default)
        for name, default in zip(keyword_only, arguments.kw_defaults):
            if default is not None:
                defaults[name] = self.expression(default)

        function = self.analysis.function(
            scope.name, self.module.name, signature, defaults, scope.generator
        )
        # Its `__name__`: the name of the def, `<lambda>` for a lambda.
        name = "<lambda>" if isinstance(node, ast.Lambda) else node.name
        name_field = self.analysis.field(function, "__name__")
        self.analysis.add_object(name_field, self.analysis.const(name))
        # An `async def` is a coroutine function, or with `yield` an async
        # generator function.
        function.is_async = isinstance(node, ast.AsyncFunctionDef)
        function.lineno, function.end_lineno = node.lineno, node.end_lineno
        function.col_offset, function.end_col_offset = (
            node.col_offset,
            node.end_col_offset,
        )
        self.parameter_annotations(function, arguments, scope)
        for name, parameter in function.parameters.items():
            variable = parameter
            if name in scope.rebound and self.scopes.tracked(scope, name):
                # The parameter is the first definition of the variable: it
                # holds what calls pass, and the variable every definition.
                variable = self.analysis.node(parameter.label)
                self.analysis.add_edge(parameter, variable)
            self._variables[(scope, name)] = variable
        return function

    def _stmt_ClassDef(self, node):
        scope = self.scopes.scope_of(node)
        decorators = [self.expression(decorator) for decorator in node.decorator_list]
        bases = [self.expression(base) for base in node.bases]
        # The keyword arguments go to `__init_subclass__`, but `metaclass`.
        keywords, double_star, metaclass = [], [], None
        for keyword in node.keywords:
            value = self.expression(keyword.value)
            if keyword.arg is None:
                double_star.append(value)
            elif keyword.arg == "metaclass":
                metaclass = value
            else:
                keywords.append((keyword.arg, value))
        # A body that uses its namespace may bind any name: none is final.
        finals = {
            scope.mangle(name): statement
            for name, statement in _final_bindings(node.body).items()
            if not scope.dynamic
        }
        cls = self.analysis.new_class(
            scope.name,
            self.module.name,
            scope.defined,
            bases,
            any(_names(base, "Protocol") for base in node.bases),
            frozenset(_abstract_methods(finals)),
            metaclass,
            scope.dynamic,
        )
        cls.lineno, cls.end_lineno = node.lineno, node.end_lineno
        self._classes[scope] = cls
        self.defined_class(scope, cls)
        site = self._site(node)
        with self._inside(scope, None):
            self._statements(node.body)
            # The namespace of the class is what reaches the end of its body:
            # the names that it may bind there, with their values.
            members = self._bound_at_end(scope)
            namespace = []
            for name, value in members.items():
                if value is None:
                    continue
                namespace.append((name, value))
                field = self.analysis.field(cls, name)
                if name in IMPLICIT_METHODS:
                    kind = IMPLICIT_METHODS[name]
                    self.analysis.add_implicit_method(value, field, kind, site)
                else:
                    self.analysis.add_class_member(value, field)
                # The caller of a class body is that of the class statement.
                self.analysis.add_set_name(value, cls, name, self._caller, site)
            # A slot is a descriptor that Python makes on the class.
            slots = _slots(finals) if "__slots__" in members else ()
            cls.defines = frozenset(members).union(map(self._scope.mangle, slots))
        self.analysis.add_init_subclass(cls, keywords, double_star, self._caller, site)
        statement = (node.name, bases, namespace, keywords, double_star)
        self.analysis.add_metaclass_call(cls, statement, self._caller, site)
        if cls.annotations:
            self.analysis.add_annotated_class(
                cls,
                [decorator for decorator in decorators if decorator is not None],
                [base for base in bases if base is not None],
            )
        # A class is true unless its metaclass says otherwise (an empty
        # `Enum` is false).
        plain = not (node.decorator_list or node.bases or node.keywords)
        truth = TRUE if plain else UNKNOWN
        self._bind(node.name, self._decorate(node, decorators, cls), truth)

    def _stmt_Return(self, node):
        if node.value is not None:
            value = self._returned(node.value)
            if value is not None and self._function is not None:
                self.analysis.add_edge(value, self._function.return_node)
        self._flow.end_path()

    def _returned(self, node):
        """The values that the returned expression `node` gives to the
        result of the function, but not the parameters or elements of
        `*args` that it returns unchanged (see `_returns_parameter`), also
        as a part of a conditional expression or of `and`/`or` that may give
        the result: each call gets its own arguments back for them."""
        if isinstance(node, (ast.IfExp, ast.BoolOp)):
            return self.choice(node, self._returned)
        if self._returns_parameter(node):
            return None
        return self.expression(node)

    def _returns_parameter(self, value):
        """If `value` is a parameter of the current function that the
        function never rebinds, or `args[i]` for its `*args` parameter and
        an int literal `i` >= 0, record that the function returns it
        unchanged and return True: each call then gets its own argument
        back, instead of every argument that any call passes. A call of a
        generator or coroutine function returns no argument: it gives a
        generator or coroutine, which returns it later."""
        function = self._function
        if function is None or function.yield_node is not None or function.is_async:
            return False
        signature = function.signature
        index = _element_index(value)
        if index is not None:
            name = self._scope.mangle(value.value.id)
            if name != signature.vararg:
                return False
            returned = (name, index)
        elif isinstance(value, ast.Name):
            name = returned = self._scope.mangle(value.id)
            if name not in signature.positional and name not in signature.keyword_only:
                return False
        else:
            return False
        if self.scopes.resolve(self._scope, name) is not self._scope:
            return False
        if self.scopes.tracked(self._scope, name):
            # The parameter's own definition reaches the return.
            if self._flow.definition(name)[:2] != (function.parameters[name], False):
                return False
        elif name in self._scope.rebound:
            return False
        function.passthrough.add(returned)
        return True

    def _stmt_Assign(self, node):
        value = self.expression(node.value)
        facts = self._facts(node.value)
        if self._may_alias(node.targets):
            value = self._join([value, self.alias_form(node.value)])
        for target in node.targets:
            # A name that the stub annotates is assigned as if the
            # annotation were written here (see annotations.py).
            declared = self.declared(self.stub_variable(target), target)
            self._assign(target, self._join([value, declared]), *facts)

    def _may_alias(self, targets):
        """Whether an assignment to `targets` may bind a type alias that
        annotations read: one name at module or class level."""
        return (
            self._scope.kind in (MODULE, CLASS)
            and len(targets) == 1
            and isinstance(targets[0], ast.Name)
        )

    def _stmt_AnnAssign(self, node):
        # The annotation of a class-level name is a value that a
        # dataclass-like class makes a field (see annotations.py). With a
        # value, the target also gets what the annotation names. Without a
        # value nothing is stored, but the parts of an attribute or
        # subscript target are evaluated.
        target = node.target
        class_level = self._may_alias([target]) and self._scope.kind == CLASS
        annotation = None
        if class_level or node.value is not None:
            annotation = self.annotation(node.annotation)
        if class_level and annotation is not None:
            cls = self._classes[self._scope]
            if cls.annotations is None:
                cls.annotations = {}
            cls.annotations[self._scope.mangle(target.id)] = annotation
        if node.value is not None:
            value = self.expression(node.value)
            facts = self._facts(node.value)
            if self._may_alias([target]):
                value = self._join([value, self.alias_form(node.value)])
            value = self._join([value, self.declared(annotation, target)])
            self._assign(target, value, *facts)
        elif isinstance(target, ast.Attribute):
            self.expression(target.value)
        elif isinstance(target, ast.Subscript):
            self._subscript_parts(target)

    def _stmt_AugAssign(self, node):
        """`x op= v` evaluates the parts of `x` once, reads `x`, evaluates
        `v`, applies the in-place operator and stores the result in `x`."""
        target = node.target
        site = self._site(target)
        match target:
            case ast.Name():
                current = self._load_name(target.id)
                value = self.expression(node.value)
                self._bind(target.id, self._operator(current, value, node))
            case ast.Attribute():
                base = self.expression(target.value)
                attr = self._scope.mangle(target.attr)
                current = None
                if base is not None:
                    current = self.analysis.node()
                    self.analysis.add_load(base, attr, current, self._caller, site)
                value = self.expression(node.value)
                result = self._operator(current, value, node)
                if base is not None and result is not None:
                    self.analysis.add_store(base, attr, result, self._caller, site)
            case ast.Subscript():
                base, index = self._subscript_parts(target)
                current = None
                if base is not None:
                    current = self.analysis.node()
                    self._subscript(base, index, current, None, target)
                value = self.expression(node.value)
                if base is not None:
                    result = self._operator(current, value, node)
                    if result is None:
                        result = self.analysis.node()
                    self._subscript(base, index, None, result, target)
            case _:
                self.expression(target)
                self.expression(node.value)

    def _stmt_Assert(self, node):
        """The message is evaluated only where the test is false, and then
        the statement raises."""
        self.condition(node.test)
        truth = self._truth(node.test)
        flow = self._flow
        if node.msg is not None and truth & FALSE:
            base = flow.state
            flow.branch(base)
            self.expression(node.msg)
            flow.state = base
        if not truth & TRUE:
            flow.end_path()
        self.narrow(node.test, True)

    def _stmt_Expr(self, node):
        # A constant statement, such as a docstring, has no effect.
        if not isinstance(node.value, ast.Constant):
            self.expression(node.value)

    def _stmt_Delete(self, node):
        for target in node.targets:
            self._delete(target)

    def _delete(self, target):
        match target:
            case ast.Name():
                self._unbind(target.id)
            case ast.Attribute():
                base = self.expression(target.value)
                if base is not None:
                    attr = self._scope.mangle(target.attr)
                    site = self._site(target)
                    self.analysis.add_delete(base, attr, self._caller, site)
            case ast.Subscript():
                base, index = self._subscript_parts(target)
                if base is not None:
                    self._subscript(base, index, None, None, target, delete=True)
            case ast.Tuple() | ast.List():
                for element in target.elts:
                    self._delete(element)

    def _stmt_If(self, node):
        # An elif chain nests in `orelse`; follow it in a loop, so that long
        # chains do not exhaust the Python stack. Each test runs where the
        # tests before it were false.
        # A branch runs only if the test may have its truth.
        flow = self._flow
        base, ends = flow.state, []
        while flow.state.reachable:
            self.condition(node.test)
            truth = self._truth(node.test)
            checked = self._type_checking.get(node.test)
            if checked is not None:
                self._record_type_only(node.body if checked else node.orelse)
            tested = flow.state
            flow.branch(tested)
            flow.state.reachable = tested.reachable and bool(truth & TRUE)
            self.narrow(node.test, True)
            self._statements(node.body)
            ends.append(flow.state)
            flow.branch(tested)
            flow.state.reachable = tested.reachable and bool(truth & FALSE)
            self.narrow(node.test, False)
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                node = node.orelse[0]
            else:
                self._statements(node.orelse)
                break
        ends.append(flow.state)
        flow.merge(base, ends)

    def _record_type_only(self, statements):
        """Record the imports in `statements`, a block that only a type
        checker runs, in `type_only_names`."""
        private = self._scope.private_class
        imports = imported_names(statements, self._absolute_module_name, private)
        for name, target in imports:
            qualified = f"{self._scope.name}.{self._scope.mangle(name)}"
            self.type_only_names[qualified] = target

    def _stmt_For(self, node):
        """Each iteration binds the target and runs the body; the loop ends,
        and the else block runs, at the start of an iteration."""
        is_async = isinstance(node, ast.AsyncFor)
        elements = self._elements_of(node.iter, is_async)
        flow = self._flow
        flow.start_loop(self._loop_names(node))
        entry = flow.state
        flow.branch(entry)
        self._assign(node.target, elements)
        self._statements(node.body)
        flow.next_iteration()
        self._loop_exit(node, entry, entry, flow.stop_loop())

    _stmt_AsyncFor = _stmt_For

    def _stmt_While(self, node):
        """The test runs at the start of each iteration; the loop ends, and
        the else block runs, where it is false."""
        flow = self._flow
        flow.start_loop(self._loop_names(node))
        self.condition(node.test)
        truth = self._truth(node.test)
        tested = flow.state
        flow.branch(tested)
        flow.state.reachable = tested.reachable and bool(truth & TRUE)
        self.narrow(node.test, True)
        self._statements(node.body)
        flow.next_iteration()
        breaks = flow.stop_loop()
        # Where the test is never false (`while True`), only `break` leaves.
        exit = State(tested)
        exit.reachable = tested.reachable and bool(truth & FALSE)
        self.narrow(node.test, False, exit)
        self._loop_exit(node, tested, exit, breaks)

    def _loop_names(self, node):
        """The tracked names that the loop `node` binds on its iterations."""
        return {
            name: unbinds
            for name, unbinds in self.scopes.loop_bindings(node).items()
            if self.scopes.tracked(self._scope, name)
        }

    def _loop_exit(self, node, start, exit, breaks):
        """After a loop whose iterations start at the state `start` and
        which ends normally at `exit` (`start` itself, or a state forked
        from it): its else block, then where that and each `break` meet."""
        flow = self._flow
        flow.branch(exit)
        self._statements(node.orelse)
        flow.merge(start, [flow.state] + breaks)

    def _stmt_Break(self, node):
        self._flow.jump(leaves=True)

    def _stmt_Continue(self, node):
        self._flow.jump(leaves=False)

    def _stmt_With(self, node):
        """The body runs after the managers are entered. `__exit__` may
        suppress an exception raised anywhere in it, so what follows also
        starts from every definition that the statement makes."""
        flow = self._flow
        base = flow.state
        record = flow.record()
        flow.branch(base)
        self._with(node)
        flow.stop(record)
        flow.merge(base, [flow.state, flow.anywhere(base, record)])

    def _with(self, node):
        is_async = isinstance(node, ast.AsyncWith)
        for item in node.items:
            manager = self.expression(item.context_expr)
            target = None
            if manager is not None:
                if item.optional_vars is not None:
                    target = self.analysis.node()
                site = self._site(item.context_expr)
                self.analysis.add_with(manager, target, self._caller, site, is_async)
            if item.optional_vars is not None:
                self._assign(item.optional_vars, target)
        self._statements(node.body)

    def _stmt_Raise(self, node):
        """`raise exc from cause`: a class is instantiated (see
        `Protocols.add_raise`)."""
        for expression in (node.exc, node.cause):
            if expression is not None:
                value = self.expression(expression)
                if value is not None:
                    site = self._site(expression)
                    self.analysis.add_raise(value, self._caller, site)
        self._flow.end_path()

    def _stmt_Try(self, node):
        """A handler starts from any point of the body that may raise; the
        else block from its end. The finally block starts from any point of
        the statement, and after the statement the names that it binds have
        its definitions, the others those of the paths that end normally.
        A `break` or `continue` waits for the finally block, which may
        replace it."""
        flow = self._flow
        base = flow.state
        everything = None
        if node.finalbody:
            everything = flow.record()
            flow.start_finally()
        in_body = flow.record()
        flow.branch(base)
        self._statements(node.body)
        body_end = flow.state
        flow.stop(in_body)
        ends = []
        if node.handlers:
            raising = flow.anywhere(base, in_body)
        grouped = isinstance(node, ast.TryStar)
        for handler in node.handlers:
            # An `except` clause runs alone; every `except*` clause that
            # matches part of the group runs, in order, so it starts where
            # the ones before it ran or did not.
            flow.branch(raising)
            types = self.expression(handler.type) if handler.type else None
            if handler.name:
                caught = self.analysis.node()
                if types is not None:
                    self.analysis.add_handler(types, caught)
                self._bind(handler.name, caught)
            self._statements(handler.body)
            if handler.name:
                # Python deletes the name at the end of the handler.
                self._unbind(handler.name)
            if grouped:
                # A clause that raises does not stop the next ones: its
                # exception joins the group that the statement raises.
                end = flow.state
                end.reachable = raising.reachable
                after = State(raising)
                flow.merge(raising, [State(raising), end], target=after)
                raising = after
            else:
                ends.append(flow.state)
        if grouped and node.handlers:
            ends.append(raising)
        flow.branch(body_end)
        self._statements(node.orelse)
        ends.append(flow.state)
        if everything is None:
            flow.merge(base, ends)
            return
        flow.stop(everything)
        jumps = flow.run_finally()
        start = flow.anywhere(base, everything)
        flow.branch(start)
        self._statements(node.finalbody)
        final = flow.state
        bound = final.changed(start)
        flow.end_finally(jumps, start)
        flow.merge(base, ends)
        for name in bound:
            base.changes[name] = final.get(name)
        base.reachable = base.reachable and final.reachable

    _stmt_TryStar = _stmt_Try

    _stmt_AsyncWith = _stmt_With

    def _stmt_Import(self, node):
        for alias in node.names:
            if alias.name == "importlib":
                self._importlib_names.add(alias.asname or alias.name)
            # Inside a class, `import __m` imports `_Class__m` (a dotted
            # name is not mangled).
            name = self._scope.mangle(alias.name)
            record = alias not in self.scopes.unread_lazy
            imported = self.imports.handle_import(name, 0, record)
            if imported is None:
                # Importing a.b.c attaches b to a and c to a.b, whatever the
                # import binds.
                self.analysis.add_external_module(name)
            if alias.asname:
                value = self._imported_module(name, imported)
                self._bind(alias.asname, value)
                continue
            # `import a.b.c` binds `a`.
            top = name.partition(".")[0]
            if imported is None:
                top_object = self.analysis.external(top)
            else:
                top_object = self.analysis.module(top)
            self._bind(alias.name.partition(".")[0], self.analysis.constant(top_object))

    def literal_import(self, node):
        """If the call `node` may be `importlib.import_module` or
        `__import__` with a str literal, an import resolved as an import
        statement: discovery builds the module, and the node of the module
        that the call gives if its callee is that function (see
        `Analysis.literal_imports`) is returned; else None. The called name
        must be, in the scope that reads it, the module's import of the
        function, or the builtin: a parameter or a local of that name is
        not it. `__import__` gives the top-level package unless `fromlist`
        is a non-empty literal, as Python does."""
        func, top = node.func, False
        if isinstance(func, ast.Name) and self._module_import(
            func.id, self._import_module_names
        ):
            pass
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and self._module_import(func.value.id, self._importlib_names)
        ):
            pass
        elif self._is_builtin_reference(func, "__import__"):
            fromlist = node.args[3] if len(node.args) > 3 else None
            for keyword in node.keywords:
                if keyword.arg == "fromlist":
                    fromlist = keyword.value
            top = not (
                isinstance(fromlist, (ast.List, ast.Tuple, ast.Set)) and fromlist.elts
            )
        else:
            return None
        if not node.args or not isinstance(node.args[0], ast.Constant):
            return None
        name = node.args[0].value
        if not isinstance(name, str) or not all(
            part.isidentifier() for part in name.split(".")
        ):
            return None
        imported = self.imports.handle_import(name, 0)
        if imported is None:
            self.analysis.add_external_module(name)
        if not top:
            return self._imported_module(name, imported)
        package = name.partition(".")[0]
        if imported is None:
            return self.analysis.constant(self.analysis.external(package))
        return self.analysis.constant(self.analysis.module(package))

    def _module_import(self, name, imported_names):
        """Whether `name`, read in the current scope, is a module-level name
        that an import binds to what `imported_names` records."""
        scope = self.scopes.resolve(self._scope, self._scope.mangle(name))
        return scope.kind == MODULE and name in imported_names

    def _imported_module(self, name, imported):
        """The value of `import name as alias`, given the module that the
        import manager found."""
        if imported == name:
            return self.analysis.constant(self.analysis.module(name))
        if imported is not None:
            # Only the parent is a module: the last part is its attribute.
            module = self.analysis.module(imported)
            return self.analysis.field(module, name.rpartition(".")[2])
        return self.analysis.constant(self.analysis.external(name))

    def _stmt_ImportFrom(self, node):
        # Inside a class, `from __m import x` imports from `_Class__m`.
        source = self._scope.mangle(node.module) if node.module else None
        holder = self._absolute_module_name(source, node.level)
        for alias in node.names:
            if holder == "importlib" and alias.name == "import_module":
                self._import_module_names.add(alias.asname or alias.name)
            if alias.name == "*":
                name = f"{source}.*" if source else "*"
                imported = self.imports.handle_import(name, node.level)
                if imported is not None:
                    self.star_imports.append(imported)
                continue
            # Inside a class, `from m import __x` reads and binds `_Class__x`,
            # but the from-list keeps `__x`: a submodule `m.__x` is imported.
            member = self._scope.mangle(alias.name)
            name = f"{source}.{alias.name}" if source else alias.name
            record = alias not in self.scopes.unread_lazy
            imported = self.imports.handle_import(name, node.level, record)
            if imported is not None and holder is not None:
                # An attribute of the module, which includes its submodules,
                # loaded as `module.member` is (a module's `__getattr__`
                # gives a name that the module does not bind).
                module = self.analysis.constant(self.analysis.module(holder))
                value = self.analysis.node()
                site = self._site(alias)
                self.analysis.add_load(module, member, value, self._caller, site)
            else:
                external = (
                    f"{holder or source}.{member}" if holder or source else member
                )
                value = self.analysis.imported_value(external)
                if holder:
                    # `from a.b import c` imports a.b and attaches it to a.
                    self.analysis.add_external_module(holder)
            truth = UNKNOWN
            if imported is None and holder in TYPING_MODULES:
                truth = FALSE if member == "TYPE_CHECKING" else UNKNOWN
            self._bind(alias.asname or alias.name, value, truth)

    def _absolute_module_name(self, module, level):
        """The absolute name of the module in `from module import ...`, or
        None if a relative import goes beyond the top-level package."""
        if level == 0:
            return module
        if self.is_package:
            package = self.module.name
        else:
            package = self.module.name.rpartition(".")[0]
        try:
            return resolve_name("." * level + (module or ""), package)
        except ImportError:
            return None

    def _stmt_TypeAlias(self, node):
        # The value is evaluated lazily; annotations may name the alias (see
        # annotations.py), so the name holds its type form.
        self._bind(node.name.id, self.annotation(node.value))

    # Assignment targets

    def _assign(self, target, value, truth=UNKNOWN, values=None):
        """Assign the node `value` (None if untracked), whose truth is
        `truth` and whose literal values are `values`, to `target`. A store
        to an attribute or subscript happens even if the value is untracked:
        it may call a setter or `__setitem__`."""
        if value is None and isinstance(target, (ast.Attribute, ast.Subscript)):
            value = self.analysis.node()
        match target:
            case ast.Name():
                self._bind(target.id, value, truth, values)
            case ast.Attribute():
                base = self.expression(target.value)
                if base is not None:
                    attr = self._scope.mangle(target.attr)
                    self.analysis.add_store(
                        base, attr, value, self._caller, self._site(target)
                    )
            case ast.Subscript():
                base, index = self._subscript_parts(target)
                if base is not None:
                    self._subscript(base, index, None, value, target)
            case ast.Tuple() | ast.List():
                self._unpack(target, value)
            case _:
                self.expression(target)

    def _unpack(self, target, value):
        """Assign the elements of `value` to the elements of a tuple or list
        target, which may have one starred element."""
        elements = target.elts
        star = next(
            (i for i, elt in enumerate(elements) if isinstance(elt, ast.Starred)),
            None,
        )
        if star is None:
            before, starred, after = elements, None, []
        else:
            before, starred, after = (
                elements[:star],
                elements[star].value,
                elements[star + 1 :],
            )
        if value is None:
            for element in before + ([starred] if starred else []) + after:
                self._assign(element, None)
            return
        before_nodes = [self.analysis.node() for _ in before]
        after_nodes = [self.analysis.node() for _ in after]
        starred_node = self.analysis.node() if starred is not None else None
        self.analysis.add_unpack(
            value,
            before_nodes,
            starred_node,
            after_nodes,
            self._caller,
            self._site(target),
        )
        for element, node in zip(before, before_nodes):
            self._assign(element, node)
        if starred is not None:
            self._assign(starred, starred_node)
        for element, node in zip(after, after_nodes):
            self._assign(element, node)


def _names(expression, name):
    """Whether `expression` is the name `name`, or an attribute access that
    ends with it (`abc.abstractmethod`), or a call or subscript of one."""
    if isinstance(expression, (ast.Call, ast.Subscript)):
        expression = (
            expression.func if isinstance(expression, ast.Call) else expression.value
        )
    if isinstance(expression, ast.Name):
        return expression.id == name
    return isinstance(expression, ast.Attribute) and expression.attr == name


def _element_index(expression):
    """The index `i` if `expression` is `name[i]` with an int literal
    `i` >= 0 (not a bool), else None."""
    if not (
        isinstance(expression, ast.Subscript)
        and isinstance(expression.value, ast.Name)
        and isinstance(expression.slice, ast.Constant)
    ):
        return None
    index = expression.slice.value
    if type(index) is int and index >= 0:
        return index
    return None


def _slots(finals):
    """The names that `__slots__` lists, where its final binding in the
    class body (`finals`, see `_final_bindings`) assigns a str, or a tuple,
    a list or a dict (its keys) of str constants. `__dict__` is no slot of
    its own: it gives the instances the `__dict__` that `object` gives."""
    statement = finals.get("__slots__")
    match statement:
        case (
            ast.Assign(targets=[ast.Name()], value=value) | ast.AnnAssign(value=value)
        ) if value is not None:
            pass
        case _:
            return []
    match value:
        case ast.Constant(value=str() as name):
            names = [name]
        case ast.Tuple(elts=elements) | ast.List(elts=elements):
            names = [e.value for e in elements if isinstance(e, ast.Constant)]
        case ast.Dict(keys=keys):
            names = [k.value for k in keys if isinstance(k, ast.Constant)]
        case _:
            return []
    return [name for name in names if isinstance(name, str) and name != "__dict__"]


def _abstract_methods(finals):
    """The names whose final binding in a class body (`finals`, see
    `_final_bindings`) is a method decorated with `abstractmethod`, under
    any other decorators (`property`, `classmethod`, `staticmethod`)."""
    return [
        name
        for name, statement in finals.items()
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_names(d, "abstractmethod") for d in statement.decorator_list)
    ]


# Statements that bind names only on some paths, or more than once.
_COMPOUND = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
)


def _final_bindings(body):
    """The statement that binds each name last in `body` (a class body), for
    the names that only plain statements at its top level bind: a `def`, a
    `class`, an assignment with a value or an import. A name that a
    compound statement (`if`, a loop, `try`, `with`, `match`), a `del` or
    an assignment expression binds has no certain binding until a later
    plain statement binds it again. An annotation without a value binds
    nothing."""
    finals = {}
    for statement in body:
        if isinstance(statement, (*_COMPOUND, ast.Delete)):
            for name in {*_bound_names(statement), *_walrus_names(statement)}:
                finals[name] = None
            continue
        for name in _bound_names(statement):
            finals[name] = statement
        for name in _walrus_names(statement):
            finals[name] = None
    return {name: s for name, s in finals.items() if s is not None}


def _bound_names(node):
    """The names that `node` binds in its own scope: targets of stores and
    deletions, definitions and imports, not inside nested scopes."""
    pending = [node]
    while pending:
        current = pending.pop()
        match current:
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                yield current.name
                if current is not node:
                    continue
                if not isinstance(current, ast.ClassDef):
                    pending.extend(current.decorator_list)
                    continue
                pending.extend([*current.decorator_list, *current.bases])
                continue
            case ast.Lambda() | ast.ListComp() | ast.SetComp() | ast.DictComp():
                continue
            case ast.GeneratorExp():
                continue
            case ast.AnnAssign(value=None):
                continue
            case ast.Name(ctx=ast.Store() | ast.Del()):
                yield current.id
            case ast.Import() | ast.ImportFrom():
                for alias in current.names:
                    yield (alias.asname or alias.name).partition(".")[0]
            case ast.MatchAs(name=str() as name) | ast.MatchStar(name=str() as name):
                yield name
            case ast.MatchMapping(rest=str() as name):
                yield name
            case ast.ExceptHandler(name=str() as name):
                yield name
        pending.extend(ast.iter_child_nodes(current))


def _walrus_names(statement):
    """The names that assignment expressions in `statement` bind in the
    class body: not those in nested functions, lambdas or classes."""
    names, pending = set(), [statement]
    while pending:
        node = pending.pop()
        match node:
            case ast.NamedExpr(target=ast.Name(id=name)):
                names.add(name)
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                # Its decorators and defaults run in the class body.
                pending.extend([*node.decorator_list, node.args])
                continue
            case ast.ClassDef():
                pending.extend([*node.decorator_list, *node.bases, *node.keywords])
                continue
            case ast.Lambda():
                pending.append(node.args)
                continue
        pending.extend(ast.iter_child_nodes(node))
    return names
