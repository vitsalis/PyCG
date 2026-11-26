import ast

MODULE = "module"
CLASS = "class"
FUNCTION = "function"
LAMBDA = "lambda"
COMPREHENSION = "comprehension"

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
    __slots__ = (
        "kind",
        "node",
        "parent",
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
        "definitions",
        "reads",
    )

    def __init__(self, kind, node, parent, local_name):
        self.kind = kind
        self.node = node
        self.parent = parent
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
        self.definitions = {}
        self.reads = set()

    @property
    def owner(self):
        return self.parent.owner if self.kind == COMPREHENSION else self

    @property
    def caller(self):
        return self.parent.caller if self.kind in (CLASS, COMPREHENSION) else self

    def mangle(self, name):
        return mangle(self.private_class, name)


def mangle(private_class, name):
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
    def __init__(self, tree, module, scopes, scope_of_node, loops):
        self.tree = tree
        self.module = module
        self.scopes = scopes
        self._scope_of_node = scope_of_node
        self._loops = loops
        self._resolved = {}
        self._inline = {}
        self.unread_lazy = set()

    def scope_of(self, node):
        return self._scope_of_node[node]

    def loop_bindings(self, node):
        return self._loops[node]

    def tracked(self, scope, name):
        return (
            name in scope.bound
            and name not in scope.shared
            and scope.kind != COMPREHENSION
            and not scope.star_import
            and not scope.dynamic
        )

    def imported(self, scope, name):
        if name in scope.shared or scope.star_import or scope.dynamic:
            return None
        return scope.imports.get(name)

    def definition(self, scope, name):
        if name in scope.shared or scope.star_import or scope.dynamic:
            return None
        return scope.definitions.get(name)

    def inline(self, reader, binder):
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
    collector = _Collector(tree)
    collector.run()
    _apply_declarations(collector.scopes, collector.module)
    _assign_names(collector.scopes, collector.lambdas_by_owner, module_name)
    ordered = sorted(collector.scopes[1:], key=_position)
    scopes = ModuleScopes(
        tree,
        collector.module,
        [collector.module] + ordered,
        collector.scope_of_node,
        collector.loop_bindings_by_node,
    )
    _find_namespace_uses(scopes, collector.namespace_uses)
    _find_unread_lazy_imports(scopes, collector.explicit_lazy_aliases)
    return scopes


def _find_namespace_uses(scopes, uses):
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
    return any(
        isinstance(node, ast.Name) and node.id == name for node in ast.walk(statement)
    )


def literal_assignment(statement, name):
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
    def __init__(self, tree):
        self.module = Scope(MODULE, tree, None, None)
        self.scopes = [self.module]
        self.scope_of_node = {tree: self.module}
        self.lambdas_by_owner = {}
        self.loop_bindings_by_node = {}
        self.namespace_uses = []
        self.explicit_lazy_aliases = []
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
        if loops is None:
            loops = self._loops
        self._work.extend((node, scope, loops) for node in reversed(list(nodes)))

    def _new_scope(self, kind, node, parent, local_name):
        scope = Scope(kind, node, parent, local_name)
        self.scopes.append(scope)
        self.scope_of_node[node] = scope
        return scope

    def _bind(self, scope, name, unbinds=False, imported=None, definition=None):
        _bind(scope, name, imported=imported, definition=definition)
        name = scope.mangle(name)
        for loop in self._loops:
            names = self.loop_bindings_by_node[loop]
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
        plain = None if node.decorator_list or scope.kind == CLASS else node
        self._bind(scope, node.name, definition=plain)
        function = self._new_scope(FUNCTION, node, scope, node.name)
        self._bind_parameters(node.args, function)
        self._push(node.decorator_list + self._defaults(node.args), scope)
        self._push(node.body, function, ())

    _visit_AsyncFunctionDef = _visit_FunctionDef

    def _visit_Lambda(self, node, scope):
        function = self._new_scope(LAMBDA, node, scope, None)
        self.lambdas_by_owner.setdefault(scope.owner, []).append(function)
        self._bind_parameters(node.args, function)
        self._push(self._defaults(node.args), scope)
        self._push([node.body], function, ())

    def _visit_ClassDef(self, node, scope):
        plain = None if node.decorator_list or scope.kind == CLASS else node
        self._bind(scope, node.name, definition=plain)
        body = self._new_scope(CLASS, node, scope, node.name)
        keywords = [keyword.value for keyword in node.keywords]
        self._push(node.decorator_list + node.bases + keywords, scope)
        self._push(node.body, body, ())

    def _visit_comprehension(self, node, scope):
        comprehension = self._new_scope(
            COMPREHENSION, node, scope, _COMPREHENSION_NAMES[type(node)]
        )
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
        self.loop_bindings_by_node[node] = {}
        inside = self._loops + (node,)
        self._push(node.orelse, scope)
        self._push(node.body, scope, inside)
        self._push([node.iter], scope)
        self._push([node.target], scope, inside)

    _visit_AsyncFor = _visit_For

    def _visit_While(self, node, scope):
        self.loop_bindings_by_node[node] = {}
        inside = self._loops + (node,)
        self._push(node.orelse, scope)
        self._push([node.test] + node.body, scope, inside)

    def _visit_Name(self, node, scope):
        if isinstance(node.ctx, ast.Load):
            scope.reads.add(scope.mangle(node.id))
        else:
            self._bind(scope, node.id, unbinds=isinstance(node.ctx, ast.Del))

    def _visit_NamedExpr(self, node, scope):
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
        if getattr(node, "is_lazy", False):
            self.explicit_lazy_aliases.extend(node.names)
        for alias in node.names:
            if alias.asname:
                self._bind(scope, alias.asname, imported=alias.name)
            else:
                top = alias.name.partition(".")[0]
                self._bind(scope, top, imported=top)

    def _visit_ImportFrom(self, node, scope):
        if getattr(node, "is_lazy", False):
            self.explicit_lazy_aliases.extend(node.names)
        for alias in node.names:
            if alias.name == "*":
                scope.star_import = True
                continue
            imported = None
            if node.level == 0 and node.module:
                imported = f"{node.module}.{alias.name}"
            self._bind(scope, alias.asname or alias.name, imported=imported)

    def _visit_AnnAssign(self, node, scope):
        if node.value is None and isinstance(node.target, ast.Name):
            _declare(scope, node.target.id)
            return
        self._push([node.target] + ([node.value] if node.value else []), scope)

    def _visit_ExceptHandler(self, node, scope):
        if node.name:
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
        self._bind(scope, node.name.id)


def _bind(scope, name, parameter=False, imported=None, definition=None):
    name = scope.mangle(name)
    if scope.imports.get(name, imported) != imported:
        imported = None
    scope.imports[name] = imported
    if scope.definitions.get(name, definition) is not definition:
        definition = None
    scope.definitions[name] = definition
    scope.bound.setdefault(name, None)
    scope.defined.setdefault(name, None)
    if not parameter:
        scope.rebound.add(name)


def _mark_asynchronous(scope):
    while scope.kind == COMPREHENSION and not scope.asynchronous:
        scope.asynchronous = True
        if isinstance(scope.node, ast.GeneratorExp):
            break
        scope = scope.parent


def _declare(scope, name):
    scope.bound.setdefault(scope.mangle(name), None)


def _apply_declarations(scopes, module):
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
                enclosing = scope.parent
                while enclosing is not None and (
                    enclosing.kind == CLASS or name not in enclosing.bound
                ):
                    enclosing = enclosing.parent
                if enclosing is not None and enclosing.kind != MODULE:
                    enclosing.rebound.add(name)
                    enclosing.shared.add(name)


def _assign_names(scopes, lambdas, module_name):
    for owner_lambdas in lambdas.values():
        owner_lambdas.sort(key=_position)
        for number, scope in enumerate(owner_lambdas, start=1):
            scope.local_name = f"<lambda{number}>"

    for scope in scopes:
        if scope.kind == MODULE:
            scope.name = module_name
        elif scope.kind == COMPREHENSION:
            scope.name = f"{scope.parent.name}.{scope.local_name}"
        else:
            scope.name = f"{scope.parent.owner.name}.{scope.local_name}"
