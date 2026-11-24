"""The nodes and call sites of a macro-benchmark project, with candidate callees.

The source is read with ast and tokenize; nothing of it is imported or run.
A call site is a place in the source that can call a function: an explicit
call, or an implicit one (an operator, an attribute access, a `for` loop).
For each site, the candidates are the functions of the package that could be
the callee by name alone: a deliberately naive over-approximation that the
ledger (see ledger.py) must decide one by one. See evaluation/macro-benchmark/README.md.
"""

import ast
import bisect
import io
import re
import string
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPES = (*_FUNCTIONS, ast.ClassDef)

# The kinds of sites, in the order of the ledger. A site of an explicit kind
# always needs a ledger entry; any other site only if it has candidates.
KINDS = (
    "call",
    "decorator",
    "class",
    "with",
    "async-with",
    "iter",
    "async-iter",
    "mapping",
    "await",
    "op",
    "getitem",
    "setitem",
    "delitem",
    "getattr",
    "setattr",
    "delattr",
    "truth",
    "format",
    "raise",
    "match",
)
EXPLICIT_KINDS = ("call", "decorator")

# The special methods that implicit sites propose by name.
_ITER = ("__iter__", "__next__", "__getitem__")
_KEY = ("__hash__", "__eq__", "__index__")
_TRUTH = ("__bool__", "__len__")
_ORDER = ("__lt__", "__gt__", "__le__", "__ge__")
_STR = ("__str__", "__repr__")
# What a `%` conversion calls, with the fallbacks of `object` and of the
# number protocol (%s: __str__, then __repr__; %d: __int__, then __index__).
_PERCENT = {
    **dict.fromkeys("s", _STR),
    **dict.fromkeys("ra", ("__repr__",)),
    **dict.fromkeys("diu", ("__int__", "__index__")),
    **dict.fromkeys("oxXc", ("__index__",)),
    **dict.fromkeys("eEfFgG", ("__float__", "__index__")),
    **dict.fromkeys("b", ("__bytes__",)),
}
_PERCENT_BYTES = {**_PERCENT, "s": ("__bytes__",)}
_PERCENT_SPEC = re.compile(
    r"%(\([^)]*\))?[#0 +-]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[hlL]?(.)"
)
_KEY_LOOKUP = ("__getitem__", "__missing__")  # `%(key)s` and `{0[key]}`
_ANY_PERCENT = {n for names in _PERCENT.values() for n in names} | set(_KEY_LOOKUP)
# What a field of str.format calls, by its conversion.
_FORMAT_FIELD = {None: ("__format__", *_STR), "s": _STR, "r": ("__repr__",)}
_FORMAT_FIELD["a"] = _FORMAT_FIELD["r"]
_ANY_FORMAT = {"__format__", *_STR, "__getattr__", "__getattribute__", *_KEY_LOOKUP}
_SPECIAL = {
    "with": ("__enter__", "__exit__"),
    "async-with": ("__aenter__", "__aexit__"),
    "iter": _ITER,
    "async-iter": ("__aiter__", "__anext__"),
    "mapping": ("keys", "__getitem__"),
    "await": ("__await__",),
    "getitem": ("__getitem__", "__class_getitem__", "__missing__", *_KEY),
    "setitem": ("__setitem__", *_KEY),
    "delitem": ("__delitem__", *_KEY),
    "getattr": ("__getattr__", "__getattribute__"),
    "setattr": ("__setattr__",),
    "delattr": ("__delattr__",),
    "truth": _TRUTH,
}
_BINARY = {
    ast.Add: ("+", "add"),
    ast.Sub: ("-", "sub"),
    ast.Mult: ("*", "mul"),
    ast.MatMult: ("@", "matmul"),
    ast.Div: ("/", "truediv"),
    ast.FloorDiv: ("//", "floordiv"),
    ast.Mod: ("%", "mod"),
    ast.Pow: ("**", "pow"),
    ast.LShift: ("<<", "lshift"),
    ast.RShift: (">>", "rshift"),
    ast.BitOr: ("|", "or"),
    ast.BitXor: ("^", "xor"),
    ast.BitAnd: ("&", "and"),
}
_UNARY = {ast.UAdd: "__pos__", ast.USub: "__neg__", ast.Invert: "__invert__"}
# `x in c`: the container's __contains__, or iteration; then the element's
# __eq__, after its __hash__ in a dict or set (as for a key of `c[x]`).
_CONTAINS = ("__contains__", *_ITER, "__hash__", "__eq__")
_COMPARE = {
    ast.Eq: ("==", ("__eq__",)),
    ast.NotEq: ("!=", ("__ne__", "__eq__")),
    ast.Lt: ("<", ("__lt__", "__gt__")),
    ast.LtE: ("<=", ("__le__", "__ge__")),
    ast.Gt: (">", ("__gt__", "__lt__")),
    ast.GtE: (">=", ("__ge__", "__le__")),
    ast.In: ("in", _CONTAINS),
    ast.NotIn: ("not", _CONTAINS),
}
# Builtin functions that call special methods of their arguments.
_PROTOCOLS = {
    "abs": ("__abs__",),
    "all": _ITER + _TRUTH,
    "any": _ITER + _TRUTH,
    "ascii": ("__repr__",),
    "bool": _TRUTH,
    "bytes": ("__bytes__", "__index__", *_ITER),
    "delattr": ("__delattr__",),
    "dict": (*_ITER, "keys", "__getitem__"),
    "dir": ("__dir__",),
    "divmod": ("__divmod__", "__rdivmod__"),
    "enumerate": _ITER,
    "filter": _ITER + _TRUTH,
    "float": ("__float__", "__index__"),
    "format": ("__format__", *_STR),
    "frozenset": (*_ITER, "__hash__", "__eq__"),
    "getattr": ("__getattr__", "__getattribute__"),
    "hasattr": ("__getattr__", "__getattribute__"),
    "hash": ("__hash__",),
    "int": ("__int__", "__index__", "__trunc__"),
    "isinstance": ("__instancecheck__",),
    "issubclass": ("__subclasscheck__",),
    "iter": _ITER,
    "len": ("__len__",),
    "list": (*_ITER, "__len__"),
    "map": _ITER,
    "max": _ITER + _ORDER,
    "min": _ITER + _ORDER,
    "next": ("__next__",),
    "pow": ("__pow__", "__rpow__"),
    "print": _STR,
    "repr": ("__repr__",),
    "reversed": ("__reversed__", "__len__", "__getitem__"),
    "round": ("__round__",),
    "set": (*_ITER, "__hash__", "__eq__"),
    "setattr": ("__setattr__",),
    "sorted": _ITER + _ORDER,
    "str": _STR,
    "sum": (*_ITER, "__add__", "__radd__"),
    "tuple": (*_ITER, "__len__"),
    "zip": _ITER,
}
# Iterating over the result of these builtins iterates over a builtin object.
_BUILTIN_ITERABLES = {
    "dict",
    "enumerate",
    "filter",
    "frozenset",
    "list",
    "map",
    "range",
    "reversed",
    "set",
    "sorted",
    "tuple",
    "zip",
}
# The truth value of the result of these builtins is a bool or an int.
_BUILTIN_TESTS = {"all", "any", "bool", "callable", "hasattr", "isinstance", "len"}
# These builtins return a dict.
_BUILTIN_MAPPINGS = {"dict", "globals", "locals", "vars"}
_DISPLAYS = (
    ast.Constant,
    ast.JoinedStr,
    ast.Tuple,
    ast.List,
    ast.Set,
    ast.Dict,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)
_TEXT_WIDTH = 60


class Site(NamedTuple):
    """A place in the source that can call a function."""

    module: str  # the module whose file has the site
    scope: str  # the node that the calls belong to: a module, function or lambda
    line: int
    column: int  # from 1, in characters, of the token that makes the call
    kind: str
    text: str  # the source of the site, on one line, for review
    candidates: frozenset  # functions of the package that are the callee by name
    value: bool  # the callee is a value with no name to match

    @property
    def key(self):
        """What identifies a site: two nodes of one name can be in two files."""
        return (self.module, self.line, self.column, self.kind)

    @property
    def explicit(self):
        """An explicit call or a decorator: its callees can be outside the package."""
        return self.kind in EXPLICIT_KINDS

    @property
    def needs_entry(self):
        return self.explicit or bool(self.candidates)


class Source(NamedTuple):
    modules: frozenset
    functions: frozenset  # functions and lambdas, named as in the README
    lambdas: int
    classes: int
    call_sites: int  # explicit calls
    scopes: tuple  # (module, node) for the modules, functions and lambdas, in order
    sites: tuple  # every site, in ledger order


def scan_source(project):
    """Name the nodes of the analysed source and find their call sites."""
    modules = [
        _Module(project.module_name(path), path) for path in project.source_files()
    ]
    scopes = [scope for module in modules for scope in module.scopes]
    index = _Index(scopes)
    sites = [site for module in modules for site in _Sites(module, index).sites]
    order = [
        (module.name, scope.name)
        for module in modules
        for scope in sorted(module.scopes, key=_position)
        if not isinstance(scope.node, ast.ClassDef)
    ]
    rank = {pair: n for n, pair in enumerate(order)}
    sites.sort(
        key=lambda s: (rank[s.module, s.scope], s.line, s.column, KINDS.index(s.kind))
    )
    counts = Counter(type(scope.node) for scope in scopes)
    return Source(
        modules=frozenset(module.name for module in modules),
        functions=frozenset(
            scope.name for scope in scopes if isinstance(scope.node, _FUNCTIONS)
        ),
        lambdas=counts[ast.Lambda],
        classes=counts[ast.ClassDef],
        call_sites=sum(site.kind == "call" for site in sites),
        scopes=tuple(dict.fromkeys(order)),
        sites=tuple(sites),
    )


def lambda_positions(name, path):
    """{(line, column from 0): node name} of the lambdas of a module file,
    named as in the README (`pkg.mod.f.<lambda1>`)."""
    module = _Module(name, Path(path))
    return {
        (node.lineno, node.col_offset): module.lambda_names[id(node)]
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Lambda) and id(node) in module.lambda_names
    }


def _position(scope):
    node = scope.node
    return (0, 0) if isinstance(node, ast.Module) else (node.lineno, node.col_offset)


# --------------------------------------------------------------------------
# Scopes and names
# --------------------------------------------------------------------------


class _Scope:
    """A module, function, lambda or class body, with the nodes it evaluates."""

    def __init__(self, name, node, owner, parent, module):
        self.name = name  # dotted name; a class is not a node, but names nest in it
        self.node = node
        self.owner = owner  # the node that the calls made here belong to
        self.parent = parent
        self.module = module
        # The class whose name mangles the private names in the code of this scope.
        if isinstance(node, ast.ClassDef):
            self.private_class = node.name
        else:
            self.private_class = parent.private_class if parent else None
        self.nodes = list(_evaluated(node, module.lazy_annotations))
        defined, values, aliases = _bindings(node, self.nodes)
        self.defined = {self.mangle(n) for n in defined}
        self.values = {self.mangle(n) for n in values}
        self.aliases = {self.mangle(n): imported for n, imported in aliases.items()}

    def mangle(self, name):
        """The name that Python stores for the identifier `name` written in
        this scope: `__x` in the body of class `C` is `_C__x`."""
        return _mangle(name, self.private_class)


class _Module:
    def __init__(self, name, path):
        self.name = name
        self.source = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.tree = ast.parse(self.source, filename=str(path))
        self.lines = self.source.split("\n")
        self.lazy_annotations = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in self.tree.body
        )
        self.lambda_names = {}  # id(ast.Lambda) -> node name
        self.scopes = []
        pending = [_Scope(name, self.tree, name, None, self)]
        while pending:
            scope = pending.pop()
            self.scopes.append(scope)
            pending += self._children(scope)

    def _children(self, scope):
        """The scopes nested in `scope`, named as in the README.

        Lambdas are numbered from 1 by the position of the `lambda` keyword
        among the lambdas of the scope. A class is not a node, but the names
        of its body nest under it, and its calls belong to its owner.
        """
        nested = [node for node in scope.nodes if isinstance(node, _SCOPES)]
        lambdas = sorted(
            (node for node in nested if isinstance(node, ast.Lambda)),
            key=lambda node: (node.lineno, node.col_offset),
        )
        numbers = {id(node): n for n, node in enumerate(lambdas, 1)}
        children = []
        for node in nested:
            if isinstance(node, ast.Lambda):
                name = f"{scope.name}.<lambda{numbers[id(node)]}>"
                self.lambda_names[id(node)] = name
            else:
                name = f"{scope.name}.{node.name}"
            owner = scope.owner if isinstance(node, ast.ClassDef) else name
            children.append(_Scope(name, node, owner, scope, self))
        return children


def _evaluated(scope, lazy_annotations):
    """Yield the nodes that `scope` evaluates, and the scopes nested in it.

    The body of a nested scope belongs to that scope. Its decorators,
    default values, annotations, base classes and type parameters belong
    to `scope`, which evaluates them (annotation scopes are transparent).
    Comprehensions are not scopes of their own. With `from __future__
    import annotations`, annotations are strings; the annotations of local
    variables are never evaluated.
    """
    in_function = isinstance(scope, _FUNCTIONS)
    pending = [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, ast.Lambda):
            pending += _defaults(node.args)
        elif isinstance(node, _DEFS):
            pending += node.decorator_list + _defaults(node.args) + node.type_params
            if not lazy_annotations:
                pending += _annotations(node)
        elif isinstance(node, ast.ClassDef):
            pending += node.decorator_list + node.bases + node.keywords
            pending += node.type_params
        elif isinstance(node, ast.AnnAssign):
            pending += [node.target] + ([node.value] if node.value else [])
            if not lazy_annotations and not in_function:
                pending.append(node.annotation)
        else:
            pending += ast.iter_child_nodes(node)


def _defaults(arguments):
    return arguments.defaults + [d for d in arguments.kw_defaults if d is not None]


def _parameters(arguments):
    return [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        *filter(None, [arguments.vararg, arguments.kwarg]),
    ]


def _annotations(function):
    found = [a.annotation for a in _parameters(function.args) if a.annotation]
    return found + ([function.returns] if function.returns else [])


def _bindings(scope, nodes):
    """(defined, values, aliases) for the names that `scope` binds.

    `defined` names are bound by def, class, import or a lambda; `values`
    by anything else (parameters, assignments, loops). `aliases` maps a name
    from `from m import a as b` to the imported name.
    """
    defined, values, aliases = set(), set(), {}
    if isinstance(scope, _FUNCTIONS):
        values.update(a.arg for a in _parameters(scope.args))
    for node in nodes:
        if isinstance(node, (*_DEFS, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add(alias.asname or alias.name.partition(".")[0])
                if isinstance(node, ast.ImportFrom) and alias.asname:
                    aliases[alias.asname] = alias.name
        elif _assigns(node):
            names = {name for target in _targets(node) for name in _names(target)}
            lam = isinstance(node.value, ast.Lambda)
            (defined if lam else values).update(names)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            values.update(_names(node.target))
        elif isinstance(node, ast.withitem) and node.optional_vars:
            values.update(_names(node.optional_vars))
        elif isinstance(node, ast.NamedExpr):
            values.update(_names(node.target))
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            values.update(filter(None, [node.name]))
        elif isinstance(node, ast.MatchMapping) and node.rest:
            values.add(node.rest)
    return defined, values, aliases


def _assigns(node):
    """Whether `node` is an assignment that binds a value: an annotation
    without a value (`tags: list`) binds nothing."""
    if isinstance(node, ast.AnnAssign):
        return node.value is not None
    return isinstance(node, (ast.Assign, ast.AugAssign))


def _targets(assignment):
    return (
        assignment.targets
        if isinstance(assignment, ast.Assign)
        else [assignment.target]
    )


def _names(target):
    """The names that an assignment target binds."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _names(element)]
    if isinstance(target, ast.Starred):
        return _names(target.value)
    return []


def _last_name(expr):
    """`f` for `f` and for `a.b.f`; None for any other expression."""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _mangle(name, private_class):
    """Private name mangling: `__x` (not `__x__`) in class `_C` is `_C__x`."""
    stripped = (private_class or "").lstrip("_")
    private = name.startswith("__") and not name.endswith("__") and "." not in name
    return f"_{stripped}{name}" if stripped and private else name


def _class_names(scope, exprs):
    """The short names of base classes or metaclasses that `scope` evaluates:
    `C` for `C`, `m.C` and `C[T]` (a generic class)."""
    names = [
        _last_name(expr.value if isinstance(expr, ast.Subscript) else expr)
        for expr in exprs
    ]
    return tuple(scope.mangle(name) for name in names if name is not None)


def _lookup(scope, name):
    """The scope whose binding of `name` a use in `scope` sees, or None.

    None is a builtin, or a name that no scope of the module binds. Class
    bodies are not visible from the scopes nested in them.
    """
    current = scope
    while current is not None:
        visible = current is scope or not isinstance(current.node, ast.ClassDef)
        if visible and (name in current.defined or name in current.values):
            return current
        current = current.parent
    return None


# --------------------------------------------------------------------------
# Definitions of the package, by name
# --------------------------------------------------------------------------


class _Class(NamedTuple):
    name: str
    bases: tuple  # last names of the base class expressions, without subscripts
    metaclasses: tuple  # last name of the `metaclass` keyword
    methods: dict  # name -> node name of the functions and lambdas in the body


class _Index:
    """The functions and classes of the package, by their short names.

    A short name is the name that Python stores: a private name `__x`
    defined in the body of class `C` is indexed as `_C__x`.
    """

    def __init__(self, scopes):
        self.functions = defaultdict(set)  # def name, or the name a lambda is bound to
        self.classes = defaultdict(list)
        self.properties = {kind: defaultdict(set) for kind in ("get", "set", "delete")}
        self.descriptor_names = set()  # class attributes that can hold a descriptor
        self.value_names = set()  # attributes that hold a value, not a def
        self.nested = defaultdict(set)  # def name -> functions defined directly in it
        methods = defaultdict(dict)
        property_calls = []  # (class body, attribute, `property(...)` call)
        for scope in scopes:
            node, parent = scope.node, scope.parent
            in_class = parent is not None and isinstance(parent.node, ast.ClassDef)
            if isinstance(node, _DEFS):
                name = parent.mangle(node.name)
                self.functions[name].add(scope.name)
                kind = _property_kind(node)
                if kind:
                    self.properties[kind][name].add(scope.name)
                elif in_class and node.decorator_list:
                    self.descriptor_names.add(name)
                if in_class:
                    methods[id(parent.node)][name] = scope.name
            if (
                isinstance(node, _FUNCTIONS)
                and parent
                and isinstance(parent.node, _DEFS)
            ):
                self.nested[parent.parent.mangle(parent.node.name)].add(scope.name)
            self._assignments(scope, methods, property_calls)
        for body, name, call in property_calls:
            for kind, accessor in _property_accessors(call):
                found = self._accessor(body, accessor, methods[id(body.node)])
                self.properties[kind][name] |= found
        for scope in scopes:
            node, parent = scope.node, scope.parent
            if isinstance(node, ast.ClassDef):
                metaclass = [k.value for k in node.keywords if k.arg == "metaclass"]
                self.classes[parent.mangle(node.name)].append(
                    _Class(
                        name=scope.name,
                        bases=_class_names(parent, node.bases),
                        metaclasses=_class_names(parent, metaclass),
                        methods=methods[id(node)],
                    )
                )

    def _assignments(self, scope, methods, property_calls):
        """Index lambdas bound to names, and attributes that hold values.
        Collect the `property(...)` calls bound in class bodies."""
        body_of = None if isinstance(scope.node, _FUNCTIONS) else scope.node
        for node in scope.nodes:
            if not _assigns(node):
                continue
            for target in _targets(node):
                name = _last_name(target)
                if name is None:
                    continue
                name = scope.mangle(name)
                if isinstance(node.value, ast.Lambda):
                    lam = scope.module.lambda_names[id(node.value)]
                    self.functions[name].add(lam)
                    if isinstance(body_of, ast.ClassDef) and isinstance(
                        target, ast.Name
                    ):
                        methods[id(body_of)][name] = lam
                elif isinstance(target, ast.Attribute) or body_of is not None:
                    self.value_names.add(name)
                if isinstance(body_of, ast.ClassDef) and isinstance(target, ast.Name):
                    self.descriptor_names.add(name)
                    if _calls_property(node.value):
                        property_calls.append((scope, name, node.value))

    def _accessor(self, body, expr, methods):
        """The functions that `expr`, an argument of `property(...)` in a
        class body, names: a lambda, or a function of that class body."""
        if isinstance(expr, ast.Lambda):
            return {body.module.lambda_names[id(expr)]}
        if isinstance(expr, ast.Name) and body.mangle(expr.id) in methods:
            return {methods[body.mangle(expr.id)]}
        return set()

    def special(self, names):
        return {f for name in names for f in self.functions.get(name, ())}

    def by_name(self, name):
        """Functions named `name`, and what instantiating a class named `name` runs."""
        return set(self.functions.get(name, ())) | self.instantiation(name)

    def ancestors(self, cls):
        """`cls` and the package classes that its bases name, transitively."""
        found, pending = {}, [cls]
        while pending:
            k = pending.pop(0)
            if k.name not in found:
                found[k.name] = k
                pending += [b for base in k.bases for b in self.classes.get(base, ())]
        return list(found.values())

    def metaclasses(self, cls):
        names = {m for k in self.ancestors(cls) for m in k.metaclasses}
        return [
            a for n in names for m in self.classes.get(n, ()) for a in self.ancestors(m)
        ]

    def instantiation(self, name):
        """__init__ and __new__ of classes named `name` and their package bases,
        and the __call__ of their package metaclasses."""
        found = set()
        for cls in self.classes.get(name, ()):
            for k in self.ancestors(cls):
                found |= {
                    k.methods[m] for m in ("__init__", "__new__") if m in k.methods
                }
            for meta in self.metaclasses(cls):
                if "__call__" in meta.methods:
                    found.add(meta.methods["__call__"])
        return found

    def definition(self, cls, binds_names):
        """What creating the class `cls` runs: __init_subclass__ of its bases,
        the metaclass, and __set_name__ of descriptors in its body."""
        found = {
            k.methods["__init_subclass__"]
            for k in self.ancestors(cls)[1:]
            if "__init_subclass__" in k.methods
        }
        for meta in self.metaclasses(cls):
            hooks = ("__new__", "__init__", "__prepare__")
            found |= {meta.methods[m] for m in hooks if m in meta.methods}
        if binds_names:
            found |= self.special(["__set_name__"])
        return found

    def returned_by(self, name):
        """What calling the result of `name(...)` can run: the functions defined
        in functions named `name`, or the __call__ of classes named `name`."""
        found = set(self.nested.get(name, ()))
        for cls in self.classes.get(name, ()):
            for k in self.ancestors(cls):
                if "__call__" in k.methods:
                    found.add(k.methods["__call__"])
        return found


def _calls_property(expr):
    """Whether `expr` is a call `property(...)`."""
    return isinstance(expr, ast.Call) and _last_name(expr.func) == "property"


def _property_accessors(call):
    """(kind, expression) for the accessors of `property(fget, fset, fdel)`,
    given by position or by keyword."""
    kinds = ("get", "set", "delete")
    found = list(zip(kinds, call.args))
    keywords = {"fget": "get", "fset": "set", "fdel": "delete"}
    found += [(keywords[k.arg], k.value) for k in call.keywords if k.arg in keywords]
    return found


def _property_kind(function):
    """'get', 'set' or 'delete' for a property-like decorated function, else None."""
    for decorator in function.decorator_list:
        name = _last_name(
            decorator.func if isinstance(decorator, ast.Call) else decorator
        )
        if name in ("property", "cached_property", "getter"):
            return "get"
        if name == "setter":
            return "set"
        if name == "deleter":
            return "delete"
    return None


# --------------------------------------------------------------------------
# Sites
# --------------------------------------------------------------------------


class _Sites:
    """The call sites of one module, with their candidates."""

    def __init__(self, module, index):
        self.module = module
        self.index = index
        self.tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(module.source).readline)
            if token.type in (tokenize.OP, tokenize.NAME)
        ]
        self.starts = [token.start for token in self.tokens]
        self.found = {}  # key -> id of the node, to merge one site reached twice
        self.sites = []
        for scope in module.scopes:
            self._scan(scope)

    # -- positions and text ----------------------------------------------------

    def _char(self, line, byte_column):
        return len(self.module.lines[line - 1].encode()[:byte_column].decode())

    def _start(self, node):
        return node.lineno, self._char(node.lineno, node.col_offset)

    def _end(self, node):
        return node.end_lineno, self._char(node.end_lineno, node.end_col_offset)

    def _token(self, after, strings):
        """The position of the first token in `strings` at or after `after`."""
        n = bisect.bisect_left(self.starts, after)
        for token in self.tokens[n:]:
            if token.string in strings:
                return token.start
        raise ValueError(f"no {strings} after {after} in {self.module.name}")

    def _text(self, node, prefix=""):
        segment = ast.get_source_segment(self.module.source, node) or ""
        text = prefix + " ".join(segment.split())
        if len(text) > _TEXT_WIDTH:
            text = text[: _TEXT_WIDTH - 3] + "..."
        return text

    def _add(self, scope, node, kind, found=None, *, at=None, text=None, value=False):
        """Record a site. By default it is at the start of `node`, shows its
        text, and its candidates are the special methods of its kind."""
        line, column = at or self._start(node)
        site = Site(
            module=self.module.name,
            scope=scope.owner,
            line=line,
            column=column + 1,
            kind=kind,
            text=self._text(node) if text is None else text,
            candidates=frozenset(self._special(kind) if found is None else found),
            value=value,
        )
        if site.key in self.found:
            if self.found[site.key] != id(node):
                raise ValueError(f"two sites at {site.key} in {self.module.name}")
            return
        self.found[site.key] = id(node)
        self.sites.append(site)

    def _special(self, kind):
        return self.index.special(_SPECIAL[kind])

    # -- scanning --------------------------------------------------------------

    def _scan(self, scope):
        tested = {}
        for node in scope.nodes:
            for expr in _tests(node, scope):
                tested[id(expr)] = expr
            handler = getattr(self, f"_{type(node).__name__}", None)
            if handler is not None:
                handler(scope, node)
        for expr in tested.values():
            self._add(scope, expr, "truth")

    def _Call(self, scope, node):
        found, value = self._callee(scope, node.func)
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name in _PROTOCOLS and _lookup(scope, name) is None:
            found |= self.index.special(_PROTOCOLS[name])
            argument = node.args[1] if len(node.args) > 1 else None
            if name in ("getattr", "hasattr") and isinstance(argument, ast.Constant):
                found |= self.index.properties["get"].get(argument.value, set())
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "format",
            "format_map",
        ):
            found |= self._format_call(node.func)
        found |= self._callbacks(scope, node)
        at = self._token(self._end(node.func), {"("})
        self._add(scope, node, "call", found, at=at, value=value)
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                self._iteration(scope, argument, argument)
        for keyword in node.keywords:
            if keyword.arg is None:
                self._mapping(scope, keyword.value)

    def _callee(self, scope, func):
        """(candidates, value) for calling the expression `func`."""
        if isinstance(func, ast.Name):
            name = scope.mangle(func.id)
            found = self.index.by_name(name)
            binding = _lookup(scope, name)
            if binding is not None and name in binding.aliases:
                original = binding.aliases[name].rpartition(".")[2]
                found |= self.index.by_name(original)
            return found, binding is not None and name in binding.values
        if isinstance(func, ast.Attribute):
            name = scope.mangle(func.attr)
            value = name in self.index.value_names or name == "__class__"
            return self.index.by_name(name), value
        if isinstance(func, ast.Lambda):
            return {self.module.lambda_names[id(func)]}, False
        if isinstance(func, ast.Call) and _last_name(func.func):
            found = self.index.returned_by(scope.mangle(_last_name(func.func)))
            return found, not found
        return set(), True

    def _callbacks(self, scope, call):
        """Package functions passed as arguments: the callee can call them."""
        found = set()
        for argument in [*call.args, *(k.value for k in call.keywords)]:
            if isinstance(argument, ast.Lambda):
                found.add(self.module.lambda_names[id(argument)])
            elif isinstance(argument, ast.Attribute):
                name = scope.mangle(argument.attr)
                found |= self.index.functions.get(name, set())
            elif isinstance(argument, ast.Name):
                name = scope.mangle(argument.id)
                binding = _lookup(scope, name)
                if binding is None or name not in binding.values:
                    found |= self.index.functions.get(name, set())
        return found

    def _decorators(self, scope, node):
        for decorator in node.decorator_list:
            found, value = self._callee(scope, decorator)
            text = self._text(decorator, prefix="@")
            self._add(scope, decorator, "decorator", found, text=text, value=value)

    def _FunctionDef(self, scope, node):
        self._decorators(scope, node)

    _AsyncFunctionDef = _FunctionDef

    def _ClassDef(self, scope, node):
        self._decorators(scope, node)
        name = f"{scope.name}.{node.name}"
        records = self.index.classes[scope.mangle(node.name)]
        record = next(k for k in records if k.name == name)
        binds = any(_assigns(n) or isinstance(n, _DEFS) for n in node.body)
        found = self.index.definition(record, binds)
        self._add(scope, node, "class", found, text=f"class {node.name}")

    def _With(self, scope, node, kind="with"):
        for item in node.items:
            expr = item.context_expr
            self._add(scope, item, kind, at=self._start(expr), text=self._text(expr))
            if item.optional_vars is not None:
                self._unpacking(scope, item.optional_vars)

    def _AsyncWith(self, scope, node):
        self._With(scope, node, "async-with")

    def _For(self, scope, node, kind="iter"):
        self._iteration(scope, node.iter, node, kind)
        self._unpacking(scope, node.target)

    def _AsyncFor(self, scope, node):
        self._For(scope, node, "async-iter")

    def _comprehension(self, scope, node):
        self._For(scope, node, "async-iter" if node.is_async else "iter")

    def _YieldFrom(self, scope, node):
        self._iteration(scope, node.value, node)

    def _Starred(self, scope, node):
        if isinstance(node.ctx, ast.Load):
            self._iteration(scope, node, node)

    def _Assign(self, scope, node):
        if any(isinstance(t, (ast.Tuple, ast.List)) for t in node.targets):
            self._iteration(scope, node.value, node)

    def _iteration(self, scope, expr, owner, kind="iter"):
        """A site that iterates over `expr`, unless that is a builtin object."""
        builtin = _calls_builtin(scope, expr, _BUILTIN_ITERABLES)
        if not isinstance(expr, _DISPLAYS) and not builtin:
            self._add(scope, owner, kind, at=self._start(expr), text=self._text(expr))

    def _unpacking(self, scope, target):
        if isinstance(target, (ast.Tuple, ast.List)):
            self._add(scope, target, "iter")

    def _mapping(self, scope, expr):
        """A site that unpacks `expr` with `**`, unless that is a builtin dict."""
        builtin = _calls_builtin(scope, expr, _BUILTIN_MAPPINGS)
        if not isinstance(expr, (ast.Dict, ast.DictComp)) and not builtin:
            self._add(scope, expr, "mapping", text=self._text(expr, prefix="**"))

    def _Dict(self, scope, node):
        for key, value in zip(node.keys, node.values):
            if key is None:
                self._mapping(scope, value)

    def _Await(self, scope, node):
        self._add(scope, node, "await")

    def _format_call(self, func):
        """What `template.format(...)` or `.format_map(...)` calls of its values."""
        receiver = func.value
        template = receiver.value if isinstance(receiver, ast.Constant) else None
        if not isinstance(template, str):
            template = None
        names, attributes = _format_fields(template)
        if func.attr == "format_map":
            names |= set(_KEY_LOOKUP)
        found = self.index.special(names)
        for attribute in attributes:
            found |= self.index.properties["get"].get(attribute, set())
        return found

    def _BinOp(self, scope, node):
        symbol, name = _BINARY[type(node.op)]
        found = self.index.special([f"__{name}__", f"__r{name}__"])
        if isinstance(node.op, ast.Mod):  # also string formatting
            found |= self.index.special(_percent_names(node.left))
        at = self._token(self._end(node.left), {symbol})
        self._add(scope, node, "op", found, at=at)

    def _AugAssign(self, scope, node):
        symbol, name = _BINARY[type(node.op)]
        found = self.index.special([f"__i{name}__", f"__{name}__", f"__r{name}__"])
        if isinstance(node.op, ast.Mod):  # also string formatting
            found |= self.index.special(_percent_names(node.target))
        at = self._token(self._end(node.target), {symbol + "="})
        self._add(scope, node, "op", found, at=at)
        target = node.target  # also read before it is written
        if isinstance(target, ast.Attribute):
            self._attribute(scope, target, "getattr")
        elif isinstance(target, ast.Subscript):
            self._subscript(scope, target, "getitem")

    def _UnaryOp(self, scope, node):
        if type(node.op) in _UNARY:
            self._add(scope, node, "op", self.index.special([_UNARY[type(node.op)]]))

    def _Compare(self, scope, node):
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            if type(op) in _COMPARE:
                symbol, names = _COMPARE[type(op)]
                at = self._token(self._end(left), {symbol})
                self._add(scope, node, "op", self.index.special(names), at=at)
            left = right

    def _Subscript(self, scope, node):
        kind = {ast.Load: "getitem", ast.Store: "setitem", ast.Del: "delitem"}
        self._subscript(scope, node, kind[type(node.ctx)])

    def _subscript(self, scope, node, kind):
        self._add(scope, node, kind, at=self._token(self._end(node.value), {"["}))

    def _Attribute(self, scope, node):
        kind = {ast.Load: "getattr", ast.Store: "setattr", ast.Del: "delattr"}
        self._attribute(scope, node, kind[type(node.ctx)])

    def _attribute(self, scope, node, kind):
        """__getattr__ & co., and the properties and descriptors of that name."""
        accessor = {"getattr": "get", "setattr": "set", "delattr": "delete"}[kind]
        name = scope.mangle(node.attr)
        found = self._special(kind)
        found |= self.index.properties[accessor].get(name, set())
        if name in self.index.descriptor_names:
            found |= self.index.special([f"__{accessor}__"])
        at = self._token(self._end(node.value), {node.attr})
        self._add(scope, node, kind, found, at=at)

    def _FormattedValue(self, scope, node):
        names = {ord("r"): ("__repr__",), ord("a"): ("__repr__",), ord("s"): _STR}
        found = self.index.special(names.get(node.conversion, ("__format__", *_STR)))
        self._add(scope, node, "format", found)

    def _Raise(self, scope, node):
        name = _last_name(node.exc) if node.exc is not None else None
        if name is not None:
            found = self.index.instantiation(scope.mangle(name))
            self._add(scope, node.exc, "raise", found)

    def _MatchClass(self, scope, node):
        self._add(scope, node, "match", self.index.special(["__instancecheck__"]))

    def _MatchMapping(self, scope, node):
        names = ["keys", "get", "__getitem__", "__len__"]
        self._add(scope, node, "match", self.index.special(names))

    def _MatchSequence(self, scope, node):
        self._add(scope, node, "match", self.index.special(["__len__", *_ITER]))


def _percent_names(template):
    """The special methods that `template % values` can call of the values.

    For a string or bytes literal, those of its conversions; for any other
    template, those of every conversion.
    """
    if not isinstance(template, ast.Constant) or not isinstance(
        template.value, (str, bytes)
    ):
        return _ANY_PERCENT
    text = template.value
    table = _PERCENT_BYTES if isinstance(text, bytes) else _PERCENT
    if isinstance(text, bytes):
        text = text.decode("latin-1")
    names = set()
    for key, conversion in _PERCENT_SPEC.findall(text):
        names.update(table.get(conversion, ()))
        if key:
            names.update(_KEY_LOOKUP)
    return names


def _format_fields(template):
    """(special methods, attribute names) that str.format can use of its values.

    For a literal template, those of its fields: the conversion, `.name` and
    `[key]` in a field name, and the fields nested in a format spec. For any
    other template, every special method that a field can call.
    """
    if template is None:
        return set(_ANY_FORMAT), set()
    names, attributes = set(), set()
    try:
        fields = list(string.Formatter().parse(template))
    except ValueError:  # not a valid template: format() raises
        return set(_ANY_FORMAT), set()
    for _, field, spec, conversion in fields:
        if field is None:
            continue
        names.update(_FORMAT_FIELD.get(conversion, ()))
        found = re.findall(r"\.(\w+)", field)
        if found:
            names.update(("__getattr__", "__getattribute__"))
            attributes.update(found)
        if "[" in field:
            names.update(_KEY_LOOKUP)
        if spec and "{" in spec:
            nested, nested_attributes = _format_fields(spec)
            names |= nested
            attributes |= nested_attributes
    return names, attributes


def _calls_builtin(scope, expr, names):
    """Whether `expr` calls one of the builtins `names`, not shadowed."""
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id in names
        and _lookup(scope, expr.func.id) is None
    )


def _tests(node, scope):
    """The expressions whose truth value `node` tests (see _tested)."""
    if isinstance(node, (ast.If, ast.While, ast.Assert, ast.IfExp)):
        tests = [node.test]
    elif isinstance(node, ast.comprehension):
        tests = node.ifs
    elif isinstance(node, ast.match_case) and node.guard is not None:
        tests = [node.guard]
    elif isinstance(node, ast.BoolOp):
        tests = node.values
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        tests = [node.operand]
    else:
        tests = []
    return [expr for test in tests for expr in _tested(test, scope)]


def _tested(expr, scope):
    """Yield the operands whose truth value testing `expr` asks for.

    `and`, `or` and `not` test their operands. A comparison, a constant and
    a builtin that returns a bool or an int give a builtin truth value.
    """
    if isinstance(expr, ast.BoolOp):
        for value in expr.values:
            yield from _tested(value, scope)
    elif isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        yield from _tested(expr.operand, scope)
    elif isinstance(expr, (ast.Compare, ast.Constant)):
        return
    elif _calls_builtin(scope, expr, _BUILTIN_TESTS):
        return
    else:
        yield expr
