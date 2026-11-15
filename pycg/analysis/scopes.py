"""Python scopes and name resolution, computed from the AST of a module.

The analysis needs to know, for every name in every scope, which scope binds
it. Python decides this statically: a name is local to a function if the
function binds it anywhere, unless the function declares it `global` or
`nonlocal`. This module applies those rules to the AST directly instead of
using `symtable`, whose tables differ between Python versions.

Each scope also gets the qualified name that the call graph uses for it:
`mod.Class.method`, `mod.outer.inner`, `mod.<lambda1>`. Lambdas are numbered
per enclosing named scope, in source order.
"""

import ast

MODULE = "module"
CLASS = "class"
FUNCTION = "function"
LAMBDA = "lambda"
COMPREHENSION = "comprehension"

# The builtins that read or write the names of a scope through its namespace:
# the scope that calls them (`globals` and the code that `exec` and `eval`
# run: also the module). `vars` only without an argument.
NAMESPACE_CALLS = {
    "globals": ("module",),
    "locals": ("caller",),
    "vars": ("caller",),
    "exec": ("caller", "module"),
    "eval": ("caller", "module"),
}

_COMPREHENSION_NAMES = {
    ast.ListComp: "<listcomp>",
    ast.SetComp: "<setcomp>",
    ast.DictComp: "<dictcomp>",
    ast.GeneratorExp: "<genexpr>",
}


class Scope:
    """A module, class body, function, lambda or comprehension.

    `bound` holds the names that the scope binds, in order of first binding.
    `defined` holds those it binds to a value: an annotation without a value
    (`x: int`) makes a name local but gives it no value, so a class body
    with only `x: int` has no attribute `x`. `owner` is the nearest scope
    that is not a comprehension; functions, classes and lambdas are named
    after it. `caller` is the nearest function, lambda or module: calls made
    in a class body or a comprehension belong to it, because classes and
    comprehensions are not call-graph nodes. `private_class` is the name of the
    innermost class whose body contains the scope (the class itself for a
    class body): it mangles private names (see `mangle`). `generator` is
    true for a function or lambda that contains `yield`. `asynchronous` is
    true for a comprehension that contains `await` or `async for`, directly
    or in a list, set or dict comprehension in it: a generator expression
    is then an async generator. `rebound` holds the
    names that a statement or expression binds (not a parameter list),
    including those that a nested scope binds through `nonlocal`. `shared`
    holds the names that code outside the scope's own statements rebinds: a
    nested scope through `global` or `nonlocal`, or an assignment expression
    in a comprehension. `star_import` is true for a module with
    `from ... import *`, and `dynamic` for a scope whose names code reads or
    writes through its namespace (see `NAMESPACE_CALLS`). `imports` maps
    each name that the scope binds to what binds it: the absolute dotted
    name that every statement binding it imports (`typing` for `import
    typing as t`, `typing.TYPE_CHECKING` for `from typing import
    TYPE_CHECKING`), or None if another statement binds it. `reads` holds
    the names that the scope loads.
    """

    __slots__ = (
        "kind",
        "node",
        "parent",
        "owner",
        "caller",
        "local_name",
        "name",
        "private_class",
        "bound",
        "defined",
        "globals",
        "nonlocals",
        "generator",
        "asynchronous",
        "rebound",
        "shared",
        "star_import",
        "dynamic",
        "imports",
        "reads",
    )

    def __init__(self, kind, node, parent, local_name):
        self.kind = kind
        self.node = node
        self.parent = parent
        self.owner = parent.owner if kind == COMPREHENSION else self
        self.caller = parent.caller if kind in (CLASS, COMPREHENSION) else self
        self.local_name = local_name
        self.name = None
        if kind == CLASS:
            self.private_class = local_name
        else:
            self.private_class = parent.private_class if parent else None
        self.bound = {}
        self.defined = {}
        self.globals = set()
        self.nonlocals = set()
        self.generator = False
        self.asynchronous = False
        self.rebound = set()
        self.shared = set()
        self.star_import = False
        self.dynamic = False
        self.imports = {}
        self.reads = set()

    def __repr__(self):
        return f"<Scope {self.kind} {self.name}>"

    def mangle(self, name):
        """Return `name` as Python stores it in this scope.

        Inside a class, a name `__x` that does not end with `__` is a private
        name and becomes `_Class__x`, with the leading underscores of the
        class name removed. This applies to bindings, name loads, parameters
        and attribute accesses (`self.__x`), but not to keyword arguments.
        """
        return mangle(self.private_class, name)


def mangle(private_class, name):
    """`name` as Python stores it inside the class named `private_class`
    (None outside any class): see `Scope.mangle`."""
    if (
        private_class is None
        or not name.startswith("__")
        or name.endswith("__")
        or "." in name
    ):
        return name
    stripped = private_class.lstrip("_")
    return f"_{stripped}{name}" if stripped else name


class ModuleScopes:
    """The scopes of one module and the resolution of names in them.
    `unread_lazy` holds the aliases of the lazy imports whose names the
    module never reads (see `_find_unread_lazy_imports`)."""

    def __init__(self, tree, module, scopes, scope_of_node, loops):
        self.tree = tree
        self.module = module
        # In source order, the module first.
        self.scopes = scopes
        self._scope_of_node = scope_of_node
        self._loops = loops
        self._resolved = {}
        self._inline = {}
        self.unread_lazy = set()

    def scope_of(self, node):
        """Return the scope that a module, def, lambda, class or
        comprehension node creates."""
        return self._scope_of_node[node]

    def loop_bindings(self, node):
        """The names that the `for` or `while` statement `node` may bind
        in its scope on an iteration (its target, its test, its body, not
        its `else` block), in order, each with whether it may also unbind
        it (`del`, the end of an `except ... as` handler)."""
        return self._loops[node]

    def tracked(self, scope, name):
        """Whether the builder follows the definitions of `name`, bound in
        `scope`, in statement order (see *Local variables by definition* in
        the design): only the scope's own statements rebind it, so the
        definitions that reach a point are known there. Names of
        comprehensions and of a module with a star import are not."""
        return (
            name in scope.bound
            and name not in scope.shared
            and scope.kind != COMPREHENSION
            and not scope.star_import
            and not scope.dynamic
        )

    def imported(self, scope, name):
        """The dotted name that every statement binding `name` in `scope`
        imports (see `Scope.imports`), if only the scope's own statements
        bind it; else None. Then the name holds that import wherever it is
        bound, whenever it is read."""
        if name in scope.shared or scope.star_import or scope.dynamic:
            return None
        return scope.imports.get(name)

    def inline(self, reader, binder):
        """Whether code of the scope `reader` runs while the statements of
        `binder`, the scope that binds a name it reads, run, in their order:
        `reader` is `binder`, or reaches it only through class bodies and
        list, set and dict comprehensions, which run where they are written.
        A function, lambda or generator expression runs at times that the
        statements do not decide."""
        key = (reader, binder)
        if key not in self._inline:
            scope = reader
            while scope is not binder and (
                scope.kind == CLASS
                or (
                    scope.kind == COMPREHENSION
                    and not isinstance(scope.node, ast.GeneratorExp)
                )
            ):
                scope = scope.parent
            self._inline[key] = scope is binder
        return self._inline[key]

    def resolve(self, scope, name):
        """Return the scope that binds `name` when `scope` uses it.

        Names that no function scope binds resolve to the module scope; the
        caller decides whether such a name is a global or a builtin.
        """
        key = (scope, name)
        if key not in self._resolved:
            self._resolved[key] = self._resolve(scope, name)
        return self._resolved[key]

    def _resolve(self, scope, name):
        if name in scope.globals:
            return self.module
        if name in scope.bound:
            return scope
        return self._enclosing(scope, name)

    def _enclosing(self, scope, name):
        """Enclosing class bodies are not visible from nested scopes, with
        one exception: Python gives every function in a class body, and
        every function nested in those, an implicit `__class__` variable,
        the innermost class around it. For `__class__` that class is the
        scope that binds it; the class body itself has none."""
        in_function = scope.kind in (FUNCTION, LAMBDA)
        enclosing = scope.parent
        while enclosing is not None and enclosing.kind != MODULE:
            if enclosing.kind == CLASS:
                if name == "__class__" and in_function:
                    return enclosing
            else:
                if name in enclosing.globals:
                    return self.module
                if name in enclosing.bound:
                    return enclosing
                if enclosing.kind in (FUNCTION, LAMBDA):
                    in_function = True
            enclosing = enclosing.parent
        return self.module


def analyse_scopes(tree, module_name):
    """Compute the scopes of the module `tree` named `module_name`."""
    collector = _Collector(tree)
    collector.run()
    _apply_declarations(collector.scopes, collector.module)
    _assign_names(collector.scopes, collector.lambdas, module_name)
    ordered = sorted(collector.scopes[1:], key=_position)
    scopes = ModuleScopes(
        tree,
        collector.module,
        [collector.module] + ordered,
        collector.scope_of_node,
        collector.loops,
    )
    _find_namespace_uses(scopes, collector.namespace_uses)
    _find_unread_lazy_imports(scopes, collector.lazy)
    return scopes


def _find_namespace_uses(scopes, uses):
    """Mark the scopes whose names code reads or writes through their
    namespace (see `NAMESPACE_CALLS`): `uses` holds each call of such a
    builtin, by name and scope, and each `sys.modules[__name__]`, as the
    name "sys.modules" and the scope. A name that the code binds is not the
    builtin."""
    for name, scope in uses:
        if name == "sys.modules":
            binder = scopes.resolve(scope, "sys")
            if scopes.imported(binder, "sys") == "sys":
                scopes.module.dynamic = True
            continue
        if name in scopes.resolve(scope, name).bound:
            continue
        for which in NAMESPACE_CALLS[name]:
            target = scopes.module if which == "module" else scope.owner
            target.dynamic = True


def _find_unread_lazy_imports(scopes, explicit):
    """Find the lazy imports (PEP 810) whose names the module never reads.

    A lazy import binds its name and imports its module when code first
    reads the name, so a module that no code of the importing module reads
    is never imported by it. The lazy imports are the `explicit` ones
    (`lazy import`, `lazy from ... import`) and the top-level imports whose
    module a literal `__lazy_modules__` lists before them. A read is a load
    of the name in any scope of the module, whether or not that code runs;
    a module that uses its namespace (`globals()`) reads every name.
    """
    lazy = explicit + _listed_lazy_imports(scopes.tree)
    if not lazy or scopes.module.dynamic:
        return
    read = {
        name
        for scope in scopes.scopes
        for name in scope.reads
        if scopes.resolve(scope, name) is scopes.module
    }
    for alias in lazy:
        if (alias.asname or alias.name.partition(".")[0]) not in read:
            scopes.unread_lazy.add(alias)


def _listed_lazy_imports(tree):
    """The aliases of the top-level imports whose module (the `from`
    module, absolute) `__lazy_modules__` lists when they run, as long as
    every top-level statement before them that mentions it (outside `def`
    and `class`) assigns it one literal list or tuple of strings; the last
    one counts. A star import is never lazy."""
    listed = None
    lazy = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if mentions(statement, "__lazy_modules__"):
            strings = literal_assignment(statement, "__lazy_modules__")
            listed = None if strings is None else set(strings)
        if not listed:
            continue
        if isinstance(statement, ast.Import):
            lazy.extend(alias for alias in statement.names if alias.name in listed)
        elif (
            isinstance(statement, ast.ImportFrom)
            and statement.level == 0
            and statement.module in listed
        ):
            lazy.extend(alias for alias in statement.names if alias.name != "*")
    return lazy


def mentions(statement, name):
    """Whether `statement` mentions the variable `name`."""
    return any(
        isinstance(node, ast.Name) and node.id == name for node in ast.walk(statement)
    )


def literal_assignment(statement, name):
    """For `name = <literal list or tuple of strings>`, the strings; else
    None."""
    if isinstance(statement, ast.Assign) and all(
        _is_name(target, name) for target in statement.targets
    ):
        value = statement.value
    elif isinstance(statement, ast.AnnAssign) and _is_name(statement.target, name):
        value = statement.value
    else:
        return None
    if isinstance(value, (ast.List, ast.Tuple)) and all(
        isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        for elt in value.elts
    ):
        return [elt.value for elt in value.elts]
    return None


def _is_name(node, name):
    return isinstance(node, ast.Name) and node.id == name


def _position(scope):
    return (scope.node.lineno, scope.node.col_offset)


class _Collector:
    """Walk a module and record its scopes and the names each one binds.

    The walk is iterative, so deeply nested code does not exhaust the Python
    stack. Each work item is an AST node with the scope it is evaluated in
    and the loops of that scope around it, innermost last: a name that the
    item binds is bound on each iteration of those loops.
    """

    def __init__(self, tree):
        self.module = Scope(MODULE, tree, None, None)
        self.scopes = [self.module]
        self.scope_of_node = {tree: self.module}
        # Lambdas per owner scope, for numbering.
        self.lambdas = {}
        # The names that each loop binds (see `ModuleScopes.loop_bindings`).
        self.loops = {}
        # Calls of builtins that use a namespace (see `NAMESPACE_CALLS`).
        self.namespace_uses = []
        # The aliases of `lazy import` and `lazy from ... import`.
        self.lazy = []
        self._work = []
        self._loops = ()
        self._push(tree.body, self.module, ())

    def run(self):
        while self._work:
            node, scope, self._loops = self._work.pop()
            handler = getattr(self, "_visit_" + type(node).__name__, None)
            if handler is not None:
                handler(node, scope)
            else:
                self._push(ast.iter_child_nodes(node), scope)

    def _push(self, nodes, scope, loops=None):
        """Visit `nodes` in `scope`, inside `loops` (by default those of
        the item being visited; `()` for the body of a new scope)."""
        if loops is None:
            loops = self._loops
        # Reversed, so that nodes are visited in source order.
        self._work.extend((node, scope, loops) for node in reversed(list(nodes)))

    def _new_scope(self, kind, node, parent, local_name):
        scope = Scope(kind, node, parent, local_name)
        self.scopes.append(scope)
        self.scope_of_node[node] = scope
        return scope

    def _bind(self, scope, name, unbinds=False, imported=None):
        """Record that `scope` binds `name` (and, if `unbinds`, may unbind
        it; `imported` is what an import binds it to), on each iteration of
        the loops around the item."""
        _bind(scope, name, imported=imported)
        name = scope.mangle(name)
        for loop in self._loops:
            names = self.loops[loop]
            names[name] = names.get(name, False) or unbinds

    def _bind_parameters(self, arguments, scope):
        parameters = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
        for extra in (arguments.vararg, arguments.kwarg):
            if extra is not None:
                parameters.append(extra)
        for parameter in parameters:
            _bind(scope, parameter.arg, parameter=True)

    def _defaults(self, arguments):
        return arguments.defaults + [d for d in arguments.kw_defaults if d is not None]

    def _visit_FunctionDef(self, node, scope):
        self._bind(scope, node.name)
        function = self._new_scope(FUNCTION, node, scope, node.name)
        self._bind_parameters(node.args, function)
        # Decorators and defaults are evaluated in the enclosing scope.
        # Annotations are not analysed.
        self._push(node.decorator_list + self._defaults(node.args), scope)
        self._push(node.body, function, ())

    _visit_AsyncFunctionDef = _visit_FunctionDef

    def _visit_Lambda(self, node, scope):
        function = self._new_scope(LAMBDA, node, scope, None)
        self.lambdas.setdefault(scope.owner, []).append(function)
        self._bind_parameters(node.args, function)
        self._push(self._defaults(node.args), scope)
        self._push([node.body], function, ())

    def _visit_ClassDef(self, node, scope):
        self._bind(scope, node.name)
        body = self._new_scope(CLASS, node, scope, node.name)
        keywords = [keyword.value for keyword in node.keywords]
        self._push(node.decorator_list + node.bases + keywords, scope)
        self._push(node.body, body, ())

    def _visit_comprehension(self, node, scope):
        comprehension = self._new_scope(
            COMPREHENSION, node, scope, _COMPREHENSION_NAMES[type(node)]
        )
        # The first iterable is evaluated in the enclosing scope.
        self._push([node.generators[0].iter], scope)
        if any(generator.is_async for generator in node.generators):
            _mark_asynchronous(comprehension)
        inner = []
        for index, generator in enumerate(node.generators):
            if index > 0:
                inner.append(generator.iter)
            inner.append(generator.target)
            inner.extend(generator.ifs)
        if isinstance(node, ast.DictComp):
            # `{**mapping for ...}` (PEP 798) has a key and no value.
            inner.extend(part for part in (node.key, node.value) if part)
        else:
            inner.append(node.elt)
        self._push(inner, comprehension, ())

    _visit_ListComp = _visit_comprehension
    _visit_SetComp = _visit_comprehension
    _visit_DictComp = _visit_comprehension
    _visit_GeneratorExp = _visit_comprehension

    def _visit_Subscript(self, node, scope):
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "modules"
            and isinstance(value.value, ast.Name)
            and value.value.id == "sys"
            and isinstance(node.slice, ast.Name)
            and node.slice.id == "__name__"
        ):
            self.namespace_uses.append(("sys.modules", scope))
        self._push(ast.iter_child_nodes(node), scope)

    def _visit_Call(self, node, scope):
        function = node.func
        if isinstance(function, ast.Name) and function.id in NAMESPACE_CALLS:
            if function.id != "vars" or not (node.args or node.keywords):
                self.namespace_uses.append((function.id, scope))
        self._push(ast.iter_child_nodes(node), scope)

    def _visit_For(self, node, scope):
        self.loops[node] = {}
        inside = self._loops + (node,)
        # In the order of the fields: target, iter, body, orelse. The
        # iterable is evaluated once, before the loop; the else block runs
        # after it.
        self._push(node.orelse, scope)
        self._push(node.body, scope, inside)
        self._push([node.iter], scope)
        self._push([node.target], scope, inside)

    _visit_AsyncFor = _visit_For

    def _visit_While(self, node, scope):
        self.loops[node] = {}
        inside = self._loops + (node,)
        self._push(node.orelse, scope)
        self._push([node.test] + node.body, scope, inside)

    def _visit_Name(self, node, scope):
        if isinstance(node.ctx, ast.Load):
            scope.reads.add(scope.mangle(node.id))
        else:
            self._bind(scope, node.id, unbinds=isinstance(node.ctx, ast.Del))

    def _visit_NamedExpr(self, node, scope):
        # The target of `:=` belongs to the nearest scope that is not a
        # comprehension. A comprehension binds it on each of its iterations,
        # which the statements of that scope do not order.
        if scope.kind == COMPREHENSION:
            _bind(scope.owner, node.target.id)
            scope.owner.shared.add(scope.owner.mangle(node.target.id))
        else:
            self._bind(scope, node.target.id)
        self._push([node.value], scope)

    def _visit_Yield(self, node, scope):
        scope.owner.generator = True
        self._push(ast.iter_child_nodes(node), scope)

    _visit_YieldFrom = _visit_Yield

    def _visit_Await(self, node, scope):
        _mark_asynchronous(scope)
        self._push(ast.iter_child_nodes(node), scope)

    def _visit_Global(self, node, scope):
        scope.globals.update(scope.mangle(name) for name in node.names)

    def _visit_Nonlocal(self, node, scope):
        scope.nonlocals.update(scope.mangle(name) for name in node.names)

    def _visit_Import(self, node, scope):
        # `is_lazy` is new in Python 3.15.
        if getattr(node, "is_lazy", False):
            self.lazy.extend(node.names)
        for alias in node.names:
            if alias.asname:
                self._bind(scope, alias.asname, imported=alias.name)
            else:
                top = alias.name.partition(".")[0]
                self._bind(scope, top, imported=top)

    def _visit_ImportFrom(self, node, scope):
        if getattr(node, "is_lazy", False):
            self.lazy.extend(node.names)
        for alias in node.names:
            if alias.name == "*":
                scope.star_import = True
                continue
            # A relative import names a module of the package.
            imported = None
            if node.level == 0 and node.module:
                imported = f"{node.module}.{alias.name}"
            self._bind(scope, alias.asname or alias.name, imported=imported)

    def _visit_AnnAssign(self, node, scope):
        # The annotation is not analysed.
        if node.value is None and isinstance(node.target, ast.Name):
            _declare(scope, node.target.id)
            return
        self._push([node.target] + ([node.value] if node.value else []), scope)

    def _visit_ExceptHandler(self, node, scope):
        if node.name:
            # The name is unbound again at the end of the handler.
            self._bind(scope, node.name, unbinds=True)
        self._push(([node.type] if node.type else []) + node.body, scope)

    def _visit_MatchAs(self, node, scope):
        if node.name:
            self._bind(scope, node.name)
        if node.pattern:
            self._push([node.pattern], scope)

    def _visit_MatchStar(self, node, scope):
        if node.name:
            self._bind(scope, node.name)

    def _visit_MatchMapping(self, node, scope):
        if node.rest:
            self._bind(scope, node.rest)
        self._push(node.keys + node.patterns, scope)

    def _visit_TypeAlias(self, node, scope):
        # The value is evaluated lazily and is not analysed.
        self._bind(scope, node.name.id)


def _bind(scope, name, parameter=False, imported=None):
    """Record that `scope` binds `name` to a value, as a parameter or
    otherwise; `imported` is the dotted name that an import binds it to."""
    name = scope.mangle(name)
    if scope.imports.get(name, imported) != imported:
        imported = None
    scope.imports[name] = imported
    scope.bound.setdefault(name, None)
    scope.defined.setdefault(name, None)
    if not parameter:
        scope.rebound.add(name)


def _mark_asynchronous(scope):
    """Record an `await` or `async for` in `scope`. A comprehension that
    has one is asynchronous. The scope that runs a list, set or dict
    comprehension awaits it, so a comprehension around it is asynchronous
    too, up to the nearest generator expression, which no scope awaits."""
    while scope.kind == COMPREHENSION and not scope.asynchronous:
        scope.asynchronous = True
        if isinstance(scope.node, ast.GeneratorExp):
            break
        scope = scope.parent


def _declare(scope, name):
    """Record that `name` is local to `scope`, without a value."""
    scope.bound.setdefault(scope.mangle(name), None)


def _apply_declarations(scopes, module):
    """Move names declared `global` to the module, and drop names declared
    `nonlocal`: an enclosing function binds them. Either way the scope that
    binds the name shares it with the one that rebinds it."""
    for scope in scopes:
        for name in list(scope.bound):
            if name in scope.globals:
                del scope.bound[name]
                module.bound.setdefault(name, None)
                if scope is not module:
                    module.shared.add(name)
                if name in scope.defined:
                    del scope.defined[name]
                    module.defined.setdefault(name, None)
            elif name in scope.nonlocals:
                del scope.bound[name]
                scope.defined.pop(name, None)
                # The function that binds the name rebinds it; nonlocal skips
                # class namespaces.
                enclosing = scope.parent
                while enclosing is not None and (
                    enclosing.kind == CLASS or name not in enclosing.bound
                ):
                    enclosing = enclosing.parent
                if enclosing is not None and enclosing.kind != MODULE:
                    enclosing.rebound.add(name)
                    enclosing.shared.add(name)


def _assign_names(scopes, lambdas, module_name):
    """Give every scope its qualified name.

    Functions, classes and lambdas are named after their owner scope, so a
    lambda in a comprehension belongs to the function around it.
    Comprehensions are named after their parent; only variables use those
    names.
    """
    for owner_lambdas in lambdas.values():
        owner_lambdas.sort(key=_position)
        for number, scope in enumerate(owner_lambdas, start=1):
            scope.local_name = f"<lambda{number}>"

    # Parents come before their children in `scopes`.
    for scope in scopes:
        if scope.kind == MODULE:
            scope.name = module_name
        elif scope.kind == COMPREHENSION:
            scope.name = f"{scope.parent.name}.{scope.local_name}"
        else:
            scope.name = f"{scope.parent.owner.name}.{scope.local_name}"
