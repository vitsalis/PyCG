import ast
import bisect
import io
import re
import string
import tokenize
from collections import Counter, defaultdict
from typing import NamedTuple

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_FUNCTION_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPE_NODES = (*_FUNCTION_NODES, ast.ClassDef)

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

_SPECIAL_ITERATION = ("__iter__", "__next__", "__getitem__")
_SPECIAL_KEY = ("__hash__", "__eq__", "__index__")
_SPECIAL_TRUTH = ("__bool__", "__len__")
_SPECIAL_ORDER = ("__lt__", "__gt__", "__le__", "__ge__")
_SPECIAL_STR = ("__str__", "__repr__")
_SPECIAL_BY_PERCENT_CONVERSION = {
    **dict.fromkeys("s", _SPECIAL_STR),
    **dict.fromkeys("ra", ("__repr__",)),
    **dict.fromkeys("diu", ("__int__", "__index__")),
    **dict.fromkeys("oxXc", ("__index__",)),
    **dict.fromkeys("eEfFgG", ("__float__", "__index__")),
    **dict.fromkeys("b", ("__bytes__",)),
}
_SPECIAL_BY_PERCENT_CONVERSION_BYTES = {
    **_SPECIAL_BY_PERCENT_CONVERSION,
    "s": ("__bytes__",),
}
_PERCENT_CONVERSION_PATTERN = re.compile(
    r"%(\([^)]*\))?[#0 +-]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[hlL]?(.)"
)
_SPECIAL_KEY_LOOKUP = ("__getitem__", "__missing__")
_SPECIAL_PERCENT_ANY = {
    name for names in _SPECIAL_BY_PERCENT_CONVERSION.values() for name in names
} | set(_SPECIAL_KEY_LOOKUP)
_SPECIAL_BY_FORMAT_CONVERSION = {
    None: ("__format__", *_SPECIAL_STR),
    "s": _SPECIAL_STR,
    "r": ("__repr__",),
}
_SPECIAL_BY_FORMAT_CONVERSION["a"] = _SPECIAL_BY_FORMAT_CONVERSION["r"]
_SPECIAL_FORMAT_ANY = {
    "__format__",
    *_SPECIAL_STR,
    "__getattr__",
    "__getattribute__",
    *_SPECIAL_KEY_LOOKUP,
}
_SPECIAL_BY_KIND = {
    "with": ("__enter__", "__exit__"),
    "async-with": ("__aenter__", "__aexit__"),
    "iter": _SPECIAL_ITERATION,
    "async-iter": ("__aiter__", "__anext__"),
    "mapping": ("keys", "__getitem__"),
    "await": ("__await__",),
    "getitem": ("__getitem__", "__class_getitem__", "__missing__", *_SPECIAL_KEY),
    "setitem": ("__setitem__", *_SPECIAL_KEY),
    "delitem": ("__delitem__", *_SPECIAL_KEY),
    "getattr": ("__getattr__", "__getattribute__"),
    "setattr": ("__setattr__",),
    "delattr": ("__delattr__",),
    "truth": _SPECIAL_TRUTH,
}
_BINARY_OPERATOR_SYMBOL_AND_NAME = {
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
_SPECIAL_BY_UNARY_OPERATOR = {
    ast.UAdd: "__pos__",
    ast.USub: "__neg__",
    ast.Invert: "__invert__",
}
_SPECIAL_CONTAINS = ("__contains__", *_SPECIAL_ITERATION, "__hash__", "__eq__")
_COMPARISON_SYMBOL_AND_SPECIAL = {
    ast.Eq: ("==", ("__eq__",)),
    ast.NotEq: ("!=", ("__ne__", "__eq__")),
    ast.Lt: ("<", ("__lt__", "__gt__")),
    ast.LtE: ("<=", ("__le__", "__ge__")),
    ast.Gt: (">", ("__gt__", "__lt__")),
    ast.GtE: (">=", ("__ge__", "__le__")),
    ast.In: ("in", _SPECIAL_CONTAINS),
    ast.NotIn: ("not", _SPECIAL_CONTAINS),
}
_SPECIAL_BY_BUILTIN = {
    "abs": ("__abs__",),
    "all": _SPECIAL_ITERATION + _SPECIAL_TRUTH,
    "any": _SPECIAL_ITERATION + _SPECIAL_TRUTH,
    "ascii": ("__repr__",),
    "bool": _SPECIAL_TRUTH,
    "bytes": ("__bytes__", "__index__", *_SPECIAL_ITERATION),
    "delattr": ("__delattr__",),
    "dict": (*_SPECIAL_ITERATION, "keys", "__getitem__"),
    "dir": ("__dir__",),
    "divmod": ("__divmod__", "__rdivmod__"),
    "enumerate": _SPECIAL_ITERATION,
    "filter": _SPECIAL_ITERATION + _SPECIAL_TRUTH,
    "float": ("__float__", "__index__"),
    "format": ("__format__", *_SPECIAL_STR),
    "frozenset": (*_SPECIAL_ITERATION, "__hash__", "__eq__"),
    "getattr": ("__getattr__", "__getattribute__"),
    "hasattr": ("__getattr__", "__getattribute__"),
    "hash": ("__hash__",),
    "int": ("__int__", "__index__", "__trunc__"),
    "isinstance": ("__instancecheck__",),
    "issubclass": ("__subclasscheck__",),
    "iter": _SPECIAL_ITERATION,
    "len": ("__len__",),
    "list": (*_SPECIAL_ITERATION, "__len__"),
    "map": _SPECIAL_ITERATION,
    "max": _SPECIAL_ITERATION + _SPECIAL_ORDER,
    "min": _SPECIAL_ITERATION + _SPECIAL_ORDER,
    "next": ("__next__",),
    "pow": ("__pow__", "__rpow__"),
    "print": _SPECIAL_STR,
    "repr": ("__repr__",),
    "reversed": ("__reversed__", "__len__", "__getitem__"),
    "round": ("__round__",),
    "set": (*_SPECIAL_ITERATION, "__hash__", "__eq__"),
    "setattr": ("__setattr__",),
    "sorted": _SPECIAL_ITERATION + _SPECIAL_ORDER,
    "str": _SPECIAL_STR,
    "sum": (*_SPECIAL_ITERATION, "__add__", "__radd__"),
    "tuple": (*_SPECIAL_ITERATION, "__len__"),
    "zip": _SPECIAL_ITERATION,
}
_BUILTINS_RETURNING_BUILTIN_ITERABLE = {
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
_BUILTINS_RETURNING_BOOL_OR_INT = {
    "all",
    "any",
    "bool",
    "callable",
    "hasattr",
    "isinstance",
    "len",
}
_BUILTINS_RETURNING_DICT = {"dict", "globals", "locals", "vars"}
_BUILTIN_BY_SYNTAX = (
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
_SITE_TEXT_LENGTH_MAX = 60
_SITE_TEXT_ELLIPSIS = "..."


class Site(NamedTuple):
    module: str
    scope: str
    line: int
    column: int
    kind: str
    text: str
    candidates: frozenset
    value: bool

    @property
    def key(self):
        return (self.module, self.line, self.column, self.kind)

    @property
    def explicit(self):
        return self.kind in EXPLICIT_KINDS

    @property
    def needs_entry(self):
        return self.explicit or bool(self.candidates)


class Source(NamedTuple):
    modules: frozenset
    functions: frozenset
    lambdas: int
    classes: int
    call_sites: int
    scopes: tuple
    sites: tuple


def scan_source(project):
    modules = [
        _Module(project.module_name(path), path) for path in project.source_files()
    ]
    scopes = [scope for module in modules for scope in module.scopes]
    index = _Index(scopes)
    sites = [site for module in modules for site in _Sites(module, index).sites]
    node_order = [
        (module.name, scope.name)
        for module in modules
        for scope in sorted(module.scopes, key=_scope_position)
        if not isinstance(scope.node, ast.ClassDef)
    ]
    node_rank = {pair: rank for rank, pair in enumerate(node_order)}
    sites.sort(
        key=lambda s: (
            node_rank[s.module, s.scope],
            s.line,
            s.column,
            KINDS.index(s.kind),
        )
    )
    scope_count_by_type = Counter(type(scope.node) for scope in scopes)
    return Source(
        modules=frozenset(module.name for module in modules),
        functions=frozenset(
            scope.name for scope in scopes if isinstance(scope.node, _FUNCTION_NODES)
        ),
        lambdas=scope_count_by_type[ast.Lambda],
        classes=scope_count_by_type[ast.ClassDef],
        call_sites=sum(site.kind == "call" for site in sites),
        scopes=tuple(dict.fromkeys(node_order)),
        sites=tuple(sites),
    )


def _scope_position(scope):
    node = scope.node
    return (0, 0) if isinstance(node, ast.Module) else (node.lineno, node.col_offset)


class _Scope:
    def __init__(self, name, node, call_owner, parent, module):
        assert isinstance(node, (ast.Module, *_SCOPE_NODES))
        assert (parent is None) == isinstance(node, ast.Module)
        self.name = name
        self.node = node
        self.call_owner = call_owner
        self.parent = parent
        self.module = module
        if isinstance(node, ast.ClassDef):
            self.mangling_class = node.name
        else:
            self.mangling_class = parent.mangling_class if parent else None
        self.nodes_evaluated = list(_nodes_evaluated(node, module.lazy_annotations))
        names_defined, names_bound_to_value, imported_name_by_alias = _bindings(
            node, self.nodes_evaluated
        )
        self.names_defined = {self.mangle(defined) for defined in names_defined}
        self.names_bound_to_value = {
            self.mangle(bound) for bound in names_bound_to_value
        }
        self.imported_name_by_alias = {
            self.mangle(alias): imported
            for alias, imported in imported_name_by_alias.items()
        }

    def mangle(self, name):
        return _mangle(name, self.mangling_class)


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
        self.lambda_name_by_node_id = {}
        self.scopes = []
        pending = [_Scope(name, self.tree, name, None, self)]
        while pending:
            scope = pending.pop()
            self.scopes.append(scope)
            pending += self._child_scopes(scope)

    def _child_scopes(self, scope):
        nested = [
            node for node in scope.nodes_evaluated if isinstance(node, _SCOPE_NODES)
        ]
        lambdas_by_keyword_position = sorted(
            (node for node in nested if isinstance(node, ast.Lambda)),
            key=lambda node: (node.lineno, node.col_offset),
        )
        lambda_number_by_node_id = {
            id(node): number
            for number, node in enumerate(lambdas_by_keyword_position, 1)
        }
        children = []
        for node in nested:
            if isinstance(node, ast.Lambda):
                name = f"{scope.name}.<lambda{lambda_number_by_node_id[id(node)]}>"
                self.lambda_name_by_node_id[id(node)] = name
            else:
                name = f"{scope.name}.{node.name}"
            if isinstance(node, ast.ClassDef):
                call_owner = scope.call_owner
            else:
                call_owner = name
            children.append(_Scope(name, node, call_owner, scope, self))
        return children


def _nodes_evaluated(scope, lazy_annotations):
    in_function = isinstance(scope, _FUNCTION_NODES)
    pending = [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, ast.Lambda):
            pending += _defaults(node.args)
        elif isinstance(node, _FUNCTION_DEFINITIONS):
            pending += node.decorator_list + _defaults(node.args) + node.type_params
            if not lazy_annotations:
                pending += _annotations(node)
        elif isinstance(node, ast.ClassDef):
            pending += node.decorator_list + node.bases + node.keywords
            pending += node.type_params
        elif isinstance(node, ast.AnnAssign):
            pending += [node.target] + ([node.value] if node.value else [])
            local_annotation = in_function
            if not lazy_annotations and not local_annotation:
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
    names_defined, names_bound_to_value, imported_name_by_alias = set(), set(), {}
    if isinstance(scope, _FUNCTION_NODES):
        names_bound_to_value.update(a.arg for a in _parameters(scope.args))
    for node in nodes:
        if isinstance(node, (*_FUNCTION_DEFINITIONS, ast.ClassDef)):
            names_defined.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names_defined.add(alias.asname or alias.name.partition(".")[0])
                if isinstance(node, ast.ImportFrom) and alias.asname:
                    imported_name_by_alias[alias.asname] = alias.name
        elif _is_value_assignment(node):
            names = {
                name for target in _targets(node) for name in _target_names(target)
            }
            assigns_lambda = isinstance(node.value, ast.Lambda)
            if assigns_lambda:
                names_defined.update(names)
            else:
                names_bound_to_value.update(names)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            names_bound_to_value.update(_target_names(node.target))
        elif isinstance(node, ast.withitem) and node.optional_vars:
            names_bound_to_value.update(_target_names(node.optional_vars))
        elif isinstance(node, ast.NamedExpr):
            names_bound_to_value.update(_target_names(node.target))
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            names_bound_to_value.update(filter(None, [node.name]))
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names_bound_to_value.add(node.rest)
    return names_defined, names_bound_to_value, imported_name_by_alias


def _is_value_assignment(node):
    if isinstance(node, ast.AnnAssign):
        return node.value is not None
    return isinstance(node, (ast.Assign, ast.AugAssign))


def _targets(assignment):
    return (
        assignment.targets
        if isinstance(assignment, ast.Assign)
        else [assignment.target]
    )


def _target_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _target_names(element)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return []


def _last_name(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _mangle(name, mangling_class):
    class_name_stripped = (mangling_class or "").lstrip("_")
    is_private = name.startswith("__") and not name.endswith("__") and "." not in name
    if class_name_stripped and is_private:
        return f"_{class_name_stripped}{name}"
    return name


def _class_short_names(scope, exprs):
    names = [
        _last_name(expr.value if isinstance(expr, ast.Subscript) else expr)
        for expr in exprs
    ]
    return tuple(scope.mangle(name) for name in names if name is not None)


def _binding_scope(scope, name):
    current = scope
    while current is not None:
        visible = current is scope or not isinstance(current.node, ast.ClassDef)
        bound = name in current.names_defined or name in current.names_bound_to_value
        if visible and bound:
            return current
        current = current.parent
    return None


class _Class(NamedTuple):
    name: str
    base_names: tuple
    metaclass_names: tuple
    node_name_by_method: dict


class _Index:
    def __init__(self, scopes):
        self.function_nodes_by_name = defaultdict(set)
        self.classes_by_name = defaultdict(list)
        self.property_nodes_by_kind = {
            kind: defaultdict(set) for kind in ("get", "set", "delete")
        }
        self.descriptor_holder_names = set()
        self.value_holder_names = set()
        self.inner_function_nodes_by_name = defaultdict(set)
        node_name_by_method_by_class_id = defaultdict(dict)
        property_calls_in_class_bodies = []
        for scope in scopes:
            node, parent = scope.node, scope.parent
            in_class = parent is not None and isinstance(parent.node, ast.ClassDef)
            if isinstance(node, _FUNCTION_DEFINITIONS):
                name = parent.mangle(node.name)
                self.function_nodes_by_name[name].add(scope.name)
                property_kind = _property_kind(node)
                if property_kind:
                    self.property_nodes_by_kind[property_kind][name].add(scope.name)
                elif in_class and node.decorator_list:
                    self.descriptor_holder_names.add(name)
                if in_class:
                    node_name_by_method_by_class_id[id(parent.node)][name] = scope.name
            if (
                isinstance(node, _FUNCTION_NODES)
                and parent
                and isinstance(parent.node, _FUNCTION_DEFINITIONS)
            ):
                outer_name = parent.parent.mangle(parent.node.name)
                self.inner_function_nodes_by_name[outer_name].add(scope.name)
            self._index_assignments(
                scope, node_name_by_method_by_class_id, property_calls_in_class_bodies
            )
        for class_body, name, call in property_calls_in_class_bodies:
            node_name_by_method = node_name_by_method_by_class_id[id(class_body.node)]
            for property_kind, accessor in _property_accessor_expressions(call):
                found = self._property_accessor_nodes(
                    class_body, accessor, node_name_by_method
                )
                self.property_nodes_by_kind[property_kind][name] |= found
        for scope in scopes:
            node, parent = scope.node, scope.parent
            if isinstance(node, ast.ClassDef):
                metaclass = [k.value for k in node.keywords if k.arg == "metaclass"]
                self.classes_by_name[parent.mangle(node.name)].append(
                    _Class(
                        name=scope.name,
                        base_names=_class_short_names(parent, node.bases),
                        metaclass_names=_class_short_names(parent, metaclass),
                        node_name_by_method=node_name_by_method_by_class_id[id(node)],
                    )
                )

    def _index_assignments(
        self, scope, node_name_by_method_by_class_id, property_calls_in_class_bodies
    ):
        if isinstance(scope.node, _FUNCTION_NODES):
            namespace_node = None
        else:
            namespace_node = scope.node
        in_class_body = isinstance(namespace_node, ast.ClassDef)
        for node in scope.nodes_evaluated:
            if not _is_value_assignment(node):
                continue
            for target in _targets(node):
                name = _last_name(target)
                if name is None:
                    continue
                name = scope.mangle(name)
                if isinstance(node.value, ast.Lambda):
                    lambda_name = scope.module.lambda_name_by_node_id[id(node.value)]
                    self.function_nodes_by_name[name].add(lambda_name)
                    if in_class_body and isinstance(target, ast.Name):
                        class_id = id(namespace_node)
                        node_name_by_method_by_class_id[class_id][name] = lambda_name
                elif isinstance(target, ast.Attribute) or namespace_node is not None:
                    self.value_holder_names.add(name)
                if in_class_body and isinstance(target, ast.Name):
                    self.descriptor_holder_names.add(name)
                    if _calls_property(node.value):
                        property_calls_in_class_bodies.append((scope, name, node.value))

    def _property_accessor_nodes(self, class_body, expr, node_name_by_method):
        if isinstance(expr, ast.Lambda):
            return {class_body.module.lambda_name_by_node_id[id(expr)]}
        if isinstance(expr, ast.Name):
            name = class_body.mangle(expr.id)
            if name in node_name_by_method:
                return {node_name_by_method[name]}
        return set()

    def functions_named(self, names):
        return {
            node for name in names for node in self.function_nodes_by_name.get(name, ())
        }

    def call_candidates(self, name):
        functions = set(self.function_nodes_by_name.get(name, ()))
        return functions | self.instantiation(name)

    def class_and_ancestors(self, cls):
        found, pending = {}, [cls]
        while pending:
            current = pending.pop(0)
            if current.name not in found:
                found[current.name] = current
                pending += [
                    base
                    for base_name in current.base_names
                    for base in self.classes_by_name.get(base_name, ())
                ]
        return list(found.values())

    def metaclasses(self, cls):
        names = {
            name
            for ancestor in self.class_and_ancestors(cls)
            for name in ancestor.metaclass_names
        }
        return [
            ancestor
            for name in names
            for metaclass in self.classes_by_name.get(name, ())
            for ancestor in self.class_and_ancestors(metaclass)
        ]

    def instantiation(self, name):
        found = set()
        for cls in self.classes_by_name.get(name, ()):
            for ancestor in self.class_and_ancestors(cls):
                methods = ancestor.node_name_by_method
                found |= {
                    methods[method]
                    for method in ("__init__", "__new__")
                    if method in methods
                }
            for metaclass in self.metaclasses(cls):
                if "__call__" in metaclass.node_name_by_method:
                    found.add(metaclass.node_name_by_method["__call__"])
        return found

    def class_creation(self, cls, binds_names):
        found = {
            ancestor.node_name_by_method["__init_subclass__"]
            for ancestor in self.class_and_ancestors(cls)[1:]
            if "__init_subclass__" in ancestor.node_name_by_method
        }
        for metaclass in self.metaclasses(cls):
            hooks = ("__new__", "__init__", "__prepare__")
            methods = metaclass.node_name_by_method
            found |= {methods[hook] for hook in hooks if hook in methods}
        if binds_names:
            found |= self.functions_named(["__set_name__"])
        return found

    def result_call_candidates(self, name):
        found = set(self.inner_function_nodes_by_name.get(name, ()))
        for cls in self.classes_by_name.get(name, ()):
            for ancestor in self.class_and_ancestors(cls):
                if "__call__" in ancestor.node_name_by_method:
                    found.add(ancestor.node_name_by_method["__call__"])
        return found


def _calls_property(expr):
    return isinstance(expr, ast.Call) and _last_name(expr.func) == "property"


def _property_accessor_expressions(call):
    kinds_by_position = ("get", "set", "delete")
    found = list(zip(kinds_by_position, call.args))
    kind_by_keyword = {"fget": "get", "fset": "set", "fdel": "delete"}
    found += [
        (kind_by_keyword[keyword.arg], keyword.value)
        for keyword in call.keywords
        if keyword.arg in kind_by_keyword
    ]
    return found


def _property_kind(function):
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


class _Sites:
    def __init__(self, module, index):
        self.module = module
        self.index = index
        self.tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(module.source).readline)
            if token.type in (tokenize.OP, tokenize.NAME)
        ]
        self.token_starts = [token.start for token in self.tokens]
        assert self.token_starts == sorted(self.token_starts)
        self.node_id_by_site_key = {}
        self.sites = []
        for scope in module.scopes:
            self._scan(scope)

    def _column_in_characters(self, line, column_in_bytes):
        line_bytes = self.module.lines[line - 1].encode()
        return len(line_bytes[:column_in_bytes].decode())

    def _start(self, node):
        return node.lineno, self._column_in_characters(node.lineno, node.col_offset)

    def _end(self, node):
        column = self._column_in_characters(node.end_lineno, node.end_col_offset)
        return node.end_lineno, column

    def _token_start_at_or_after(self, position, strings):
        first = bisect.bisect_left(self.token_starts, position)
        for token in self.tokens[first:]:
            if token.string in strings:
                return token.start
        raise ValueError(f"no {strings} after {position} in {self.module.name}")

    def _text(self, node, prefix=""):
        segment = ast.get_source_segment(self.module.source, node) or ""
        text = prefix + " ".join(segment.split())
        if len(text) > _SITE_TEXT_LENGTH_MAX:
            kept = _SITE_TEXT_LENGTH_MAX - len(_SITE_TEXT_ELLIPSIS)
            text = text[:kept] + _SITE_TEXT_ELLIPSIS
        return text

    def _add_site(
        self, scope, node, kind, candidates=None, *, at=None, text=None, value=False
    ):
        assert kind in KINDS
        line, column = at or self._start(node)
        if candidates is None:
            candidates = self._special_candidates(kind)
        site = Site(
            module=self.module.name,
            scope=scope.call_owner,
            line=line,
            column=column + 1,
            kind=kind,
            text=self._text(node) if text is None else text,
            candidates=frozenset(candidates),
            value=value,
        )
        if site.key in self.node_id_by_site_key:
            if self.node_id_by_site_key[site.key] != id(node):
                raise ValueError(f"two sites at {site.key} in {self.module.name}")
            return
        self.node_id_by_site_key[site.key] = id(node)
        self.sites.append(site)

    def _special_candidates(self, kind):
        return self.index.functions_named(_SPECIAL_BY_KIND[kind])

    def _scan(self, scope):
        truth_tested_by_id = {}
        for node in scope.nodes_evaluated:
            for expr in _truth_tested_expressions(node, scope):
                truth_tested_by_id[id(expr)] = expr
            handler = getattr(self, f"_{type(node).__name__}", None)
            if handler is not None:
                handler(scope, node)
        for expr in truth_tested_by_id.values():
            self._add_site(scope, expr, "truth")

    def _Call(self, scope, node):
        found, value = self._callee_candidates(scope, node.func)
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name in _SPECIAL_BY_BUILTIN and _binding_scope(scope, name) is None:
            found |= self.index.functions_named(_SPECIAL_BY_BUILTIN[name])
            argument = node.args[1] if len(node.args) > 1 else None
            if name in ("getattr", "hasattr") and isinstance(argument, ast.Constant):
                getters = self.index.property_nodes_by_kind["get"]
                found |= getters.get(argument.value, set())
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "format",
            "format_map",
        ):
            found |= self._format_call_candidates(node.func)
        found |= self._callback_candidates(scope, node)
        at = self._token_start_at_or_after(self._end(node.func), {"("})
        self._add_site(scope, node, "call", found, at=at, value=value)
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                self._add_iteration(scope, argument, argument)
        for keyword in node.keywords:
            if keyword.arg is None:
                self._add_mapping(scope, keyword.value)

    def _callee_candidates(self, scope, func):
        if isinstance(func, ast.Name):
            name = scope.mangle(func.id)
            found = self.index.call_candidates(name)
            binding = _binding_scope(scope, name)
            if binding is not None and name in binding.imported_name_by_alias:
                imported = binding.imported_name_by_alias[name].rpartition(".")[2]
                found |= self.index.call_candidates(imported)
            is_value = binding is not None and name in binding.names_bound_to_value
            return found, is_value
        if isinstance(func, ast.Attribute):
            name = scope.mangle(func.attr)
            is_value = name in self.index.value_holder_names or name == "__class__"
            return self.index.call_candidates(name), is_value
        if isinstance(func, ast.Lambda):
            return {self.module.lambda_name_by_node_id[id(func)]}, False
        if isinstance(func, ast.Call) and _last_name(func.func):
            name = scope.mangle(_last_name(func.func))
            found = self.index.result_call_candidates(name)
            return found, not found
        return set(), True

    def _callback_candidates(self, scope, call):
        found = set()
        functions = self.index.function_nodes_by_name
        for argument in [*call.args, *(k.value for k in call.keywords)]:
            if isinstance(argument, ast.Lambda):
                found.add(self.module.lambda_name_by_node_id[id(argument)])
            elif isinstance(argument, ast.Attribute):
                name = scope.mangle(argument.attr)
                found |= functions.get(name, set())
            elif isinstance(argument, ast.Name):
                name = scope.mangle(argument.id)
                binding = _binding_scope(scope, name)
                if binding is None or name not in binding.names_bound_to_value:
                    found |= functions.get(name, set())
        return found

    def _add_decorators(self, scope, node):
        for decorator in node.decorator_list:
            found, value = self._callee_candidates(scope, decorator)
            text = self._text(decorator, prefix="@")
            self._add_site(scope, decorator, "decorator", found, text=text, value=value)

    def _FunctionDef(self, scope, node):
        self._add_decorators(scope, node)

    _AsyncFunctionDef = _FunctionDef

    def _ClassDef(self, scope, node):
        self._add_decorators(scope, node)
        name = f"{scope.name}.{node.name}"
        same_name_classes = self.index.classes_by_name[scope.mangle(node.name)]
        record = next(cls for cls in same_name_classes if cls.name == name)
        binds_names = any(
            _is_value_assignment(statement)
            or isinstance(statement, _FUNCTION_DEFINITIONS)
            for statement in node.body
        )
        found = self.index.class_creation(record, binds_names)
        self._add_site(scope, node, "class", found, text=f"class {node.name}")

    def _With(self, scope, node, kind="with"):
        for item in node.items:
            expr = item.context_expr
            self._add_site(
                scope, item, kind, at=self._start(expr), text=self._text(expr)
            )
            if item.optional_vars is not None:
                self._add_unpacking(scope, item.optional_vars)

    def _AsyncWith(self, scope, node):
        self._With(scope, node, "async-with")

    def _For(self, scope, node, kind="iter"):
        self._add_iteration(scope, node.iter, node, kind)
        self._add_unpacking(scope, node.target)

    def _AsyncFor(self, scope, node):
        self._For(scope, node, "async-iter")

    def _comprehension(self, scope, node):
        self._For(scope, node, "async-iter" if node.is_async else "iter")

    def _YieldFrom(self, scope, node):
        self._add_iteration(scope, node.value, node)

    def _Starred(self, scope, node):
        if isinstance(node.ctx, ast.Load):
            self._add_iteration(scope, node, node)

    def _Assign(self, scope, node):
        if any(isinstance(t, (ast.Tuple, ast.List)) for t in node.targets):
            self._add_iteration(scope, node.value, node)

    def _add_iteration(self, scope, expr, site_node, kind="iter"):
        returns_builtin_iterable = _calls_unshadowed_builtin(
            scope, expr, _BUILTINS_RETURNING_BUILTIN_ITERABLE
        )
        builtin = isinstance(expr, _BUILTIN_BY_SYNTAX) or returns_builtin_iterable
        if not builtin:
            self._add_site(
                scope, site_node, kind, at=self._start(expr), text=self._text(expr)
            )

    def _add_unpacking(self, scope, target):
        if isinstance(target, (ast.Tuple, ast.List)):
            self._add_site(scope, target, "iter")

    def _add_mapping(self, scope, expr):
        returns_dict = _calls_unshadowed_builtin(scope, expr, _BUILTINS_RETURNING_DICT)
        if not isinstance(expr, (ast.Dict, ast.DictComp)) and not returns_dict:
            text = self._text(expr, prefix="**")
            self._add_site(scope, expr, "mapping", text=text)

    def _Dict(self, scope, node):
        for key, value in zip(node.keys, node.values):
            if key is None:
                self._add_mapping(scope, value)

    def _Await(self, scope, node):
        self._add_site(scope, node, "await")

    def _format_call_candidates(self, func):
        receiver = func.value
        template = receiver.value if isinstance(receiver, ast.Constant) else None
        if not isinstance(template, str):
            template = None
        names, attributes = _format_template_names(template)
        if func.attr == "format_map":
            names |= set(_SPECIAL_KEY_LOOKUP)
        found = self.index.functions_named(names)
        getters = self.index.property_nodes_by_kind["get"]
        for attribute in attributes:
            found |= getters.get(attribute, set())
        return found

    def _BinOp(self, scope, node):
        symbol, name = _BINARY_OPERATOR_SYMBOL_AND_NAME[type(node.op)]
        found = self.index.functions_named([f"__{name}__", f"__r{name}__"])
        is_percent_formatting = isinstance(node.op, ast.Mod)
        if is_percent_formatting:
            found |= self.index.functions_named(_percent_special_names(node.left))
        at = self._token_start_at_or_after(self._end(node.left), {symbol})
        self._add_site(scope, node, "op", found, at=at)

    def _AugAssign(self, scope, node):
        symbol, name = _BINARY_OPERATOR_SYMBOL_AND_NAME[type(node.op)]
        found = self.index.functions_named(
            [f"__i{name}__", f"__{name}__", f"__r{name}__"]
        )
        is_percent_formatting = isinstance(node.op, ast.Mod)
        if is_percent_formatting:
            found |= self.index.functions_named(_percent_special_names(node.target))
        at = self._token_start_at_or_after(self._end(node.target), {symbol + "="})
        self._add_site(scope, node, "op", found, at=at)
        self._add_augmented_target_read(scope, node.target)

    def _add_augmented_target_read(self, scope, target):
        if isinstance(target, ast.Attribute):
            self._add_attribute(scope, target, "getattr")
        elif isinstance(target, ast.Subscript):
            self._add_subscript(scope, target, "getitem")

    def _UnaryOp(self, scope, node):
        if type(node.op) in _SPECIAL_BY_UNARY_OPERATOR:
            special = _SPECIAL_BY_UNARY_OPERATOR[type(node.op)]
            self._add_site(scope, node, "op", self.index.functions_named([special]))

    def _Compare(self, scope, node):
        left = node.left
        for operator, right in zip(node.ops, node.comparators):
            if type(operator) in _COMPARISON_SYMBOL_AND_SPECIAL:
                symbol, names = _COMPARISON_SYMBOL_AND_SPECIAL[type(operator)]
                at = self._token_start_at_or_after(self._end(left), {symbol})
                found = self.index.functions_named(names)
                self._add_site(scope, node, "op", found, at=at)
            left = right

    def _Subscript(self, scope, node):
        kind = {ast.Load: "getitem", ast.Store: "setitem", ast.Del: "delitem"}
        self._add_subscript(scope, node, kind[type(node.ctx)])

    def _add_subscript(self, scope, node, kind):
        at = self._token_start_at_or_after(self._end(node.value), {"["})
        self._add_site(scope, node, kind, at=at)

    def _Attribute(self, scope, node):
        kind = {ast.Load: "getattr", ast.Store: "setattr", ast.Del: "delattr"}
        self._add_attribute(scope, node, kind[type(node.ctx)])

    def _add_attribute(self, scope, node, kind):
        accessor_kind = {"getattr": "get", "setattr": "set", "delattr": "delete"}[kind]
        name = scope.mangle(node.attr)
        found = self._special_candidates(kind)
        found |= self.index.property_nodes_by_kind[accessor_kind].get(name, set())
        if name in self.index.descriptor_holder_names:
            found |= self.index.functions_named([f"__{accessor_kind}__"])
        at = self._token_start_at_or_after(self._end(node.value), {node.attr})
        self._add_site(scope, node, kind, found, at=at)

    def _FormattedValue(self, scope, node):
        conversion_none = -1
        assert node.conversion in (conversion_none, ord("r"), ord("a"), ord("s"))
        special_by_conversion = {
            ord("r"): ("__repr__",),
            ord("a"): ("__repr__",),
            ord("s"): _SPECIAL_STR,
        }
        special_without_conversion = ("__format__", *_SPECIAL_STR)
        names = special_by_conversion.get(node.conversion, special_without_conversion)
        self._add_site(scope, node, "format", self.index.functions_named(names))

    def _Raise(self, scope, node):
        name = _last_name(node.exc) if node.exc is not None else None
        if name is not None:
            found = self.index.instantiation(scope.mangle(name))
            self._add_site(scope, node.exc, "raise", found)

    def _MatchClass(self, scope, node):
        found = self.index.functions_named(["__instancecheck__"])
        self._add_site(scope, node, "match", found)

    def _MatchMapping(self, scope, node):
        names = ["keys", "get", "__getitem__", "__len__"]
        self._add_site(scope, node, "match", self.index.functions_named(names))

    def _MatchSequence(self, scope, node):
        names = ["__len__", *_SPECIAL_ITERATION]
        self._add_site(scope, node, "match", self.index.functions_named(names))


def _percent_special_names(template):
    if not isinstance(template, ast.Constant) or not isinstance(
        template.value, (str, bytes)
    ):
        return _SPECIAL_PERCENT_ANY
    text = template.value
    if isinstance(text, bytes):
        special_by_conversion = _SPECIAL_BY_PERCENT_CONVERSION_BYTES
        text = text.decode("latin-1")
    else:
        special_by_conversion = _SPECIAL_BY_PERCENT_CONVERSION
    names = set()
    for key, conversion in _PERCENT_CONVERSION_PATTERN.findall(text):
        names.update(special_by_conversion.get(conversion, ()))
        if key:
            names.update(_SPECIAL_KEY_LOOKUP)
    return names


def _format_template_names(template):
    if template is None:
        return set(_SPECIAL_FORMAT_ANY), set()
    names, attributes = set(), set()
    try:
        fields = list(string.Formatter().parse(template))
    except ValueError:
        return set(_SPECIAL_FORMAT_ANY), set()
    for _, field, specification, conversion in fields:
        if field is None:
            continue
        names.update(_SPECIAL_BY_FORMAT_CONVERSION.get(conversion, ()))
        field_attributes = re.findall(r"\.(\w+)", field)
        if field_attributes:
            names.update(("__getattr__", "__getattribute__"))
            attributes.update(field_attributes)
        if "[" in field:
            names.update(_SPECIAL_KEY_LOOKUP)
        if specification and "{" in specification:
            nested_names, nested_attributes = _format_template_names(specification)
            names |= nested_names
            attributes |= nested_attributes
    return names, attributes


def _calls_unshadowed_builtin(scope, expr, names):
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id in names
        and _binding_scope(scope, expr.func.id) is None
    )


def _truth_tested_expressions(node, scope):
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
    return [expr for test in tests for expr in _truth_tested_operands(test, scope)]


def _truth_tested_operands(expr, scope):
    if isinstance(expr, ast.BoolOp):
        for value in expr.values:
            yield from _truth_tested_operands(value, scope)
    elif isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        yield from _truth_tested_operands(expr.operand, scope)
    elif isinstance(expr, (ast.Compare, ast.Constant)):
        return
    elif _calls_unshadowed_builtin(scope, expr, _BUILTINS_RETURNING_BOOL_OR_INT):
        return
    else:
        yield expr
