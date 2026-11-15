"""Generate PyCG's stub data from the stubs of typeshed.

    python -I tools/generate_stubs.py <typeshed checkout> <commit> [<output>]

Reads the stubs of the standard library (`<checkout>/stdlib/`) and of every
third-party distribution (`<checkout>/stubs/<distribution>/`, with its
`METADATA.toml`) with `ast`: no stub is imported or executed. Writes one
JSON file per top-level module into `<output>` (default:
`pycg/analysis/stub_data/`), those of the distributions into its
`third_party/` directory; a README that records the commit and each
distribution's version; and typeshed's licence. `pycg/analysis/stubs.py`
loads the files and describes their format. This script is a development
tool, not part of the installed package, and uses the standard library
only. Its output depends only on the stubs: the same checkout gives the
same files on every Python version that can parse them.

Which stub gives a module:

- The standard library and the distributions are read together, so a stub
  resolves the names that it imports from any of them.
- A top-level name that the standard library has is the standard
  library's: a distribution's modules under it are left out (setuptools'
  `distutils`).
- A directory that holds stubs but no `__init__.pyi` is a namespace
  package, a module without names. Several distributions may share one
  (`google`: protobuf's `google.protobuf`, google-cloud-ndb's
  `google.cloud.ndb`); a module of two distributions stops the generator.
- Every module of a stub is kept, also the helper modules that exist only
  in stubs (`_typeshed` in the standard library): they define types.
- A distribution marked obsolete (its library ships its own types since a
  version) or partial in `METADATA.toml` is read like the others; the
  README marks it.
- Directories whose name starts with `@` (`@tests`) hold no stubs.
- A class's public name is a path through the modules of its own
  distribution (the standard library counts as one), so a distribution
  that re-exports a class does not rename it.

What a stub says is kept as far as the analysis can use it, and the rest is
dropped:

- Every Python version and platform counts: the branches of `if
  sys.version_info ...` and `if sys.platform ...` are all read, and a name
  that they define differently has every definition.
- A type keeps classes, unions, `None`, `Self`, `type[...]`, callables with
  their result (and their parameters, when listed), type variables with
  their bound or constraints, and two layers of the arguments of generic
  classes (see `MAX_DEPTH`). `Any`, `ParamSpec`, `TypeVarTuple`,
  `Concatenate` and the parameters of generic type aliases are dropped (an
  alias stands for its definition, unsubstituted). The parameters that a
  function passes on (`*args: P.args`, `**kwargs: P.kwargs`, `*args:
  Unpack[Ts]`) are `object`. `Literal[...]` is the
  class of its values, `TypeGuard` and `TypeIs` are `bool`, and
  `Annotated`, `ClassVar`, `Final`, `Required`, `NotRequired` and
  `ReadOnly` are the type they wrap. A recursive alias is unknown where it
  recurs.
- A module keeps what it defines and what it re-exports (`from x import y
  as y`, `import x as x`, star imports, names in `__all__`); imports that a
  stub only uses are dropped.
"""

import ast
import json
import shutil
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

TYPING_MODULES = ("typing", "typing_extensions")
# The names of `typing` and `typing_extensions` that are special forms of
# annotations rather than classes.
SPECIAL_FORMS = frozenset(
    {
        "Annotated",
        "Any",
        "Callable",
        "ClassVar",
        "Concatenate",
        "Final",
        "Generic",
        "Literal",
        "LiteralString",
        "Never",
        "NoReturn",
        "NotRequired",
        "Optional",
        "Protocol",
        "ReadOnly",
        "Required",
        "Self",
        "Type",
        "TypeAlias",
        "TypeGuard",
        "TypeIs",
        "Union",
        "Unpack",
    }
)
# The type that a special form without arguments stands for.
BARE_SPECIAL_FORMS = {
    "Self": "*self",
    "Never": "*none",
    "NoReturn": "*none",
    "LiteralString": "builtins.str",
    "Callable": ["*call", None, None],
    "Type": "builtins.type",
}
# Special forms whose value is the type they wrap.
TRANSPARENT = frozenset(
    {"Annotated", "ClassVar", "Final", "NotRequired", "ReadOnly", "Required"}
)
# Aliases in `typing` of builtin and `collections` classes.
TYPING_ALIASES = {
    "List": "builtins.list",
    "Dict": "builtins.dict",
    "Set": "builtins.set",
    "FrozenSet": "builtins.frozenset",
    "Tuple": "builtins.tuple",
    "DefaultDict": "collections.defaultdict",
    "OrderedDict": "collections.OrderedDict",
    "Counter": "collections.Counter",
    "Deque": "collections.deque",
    "ChainMap": "collections.ChainMap",
}
# Assignments that make type variables and new types.
TYPEVAR_KINDS = {
    "TypeVar": "typevar",
    "ParamSpec": "paramspec",
    "TypeVarTuple": "typevartuple",
    "NewType": "newtype",
}
# Binding kinds that only bind a name to another definition.
IMPORTS = ("from", "module", "assign")
# Decorators that make a method a property.
PROPERTY_DECORATORS = frozenset(
    {
        ("builtins", "property"),
        ("functools", "cached_property"),
        ("types", "DynamicClassAttribute"),
    }
)
# Layers of generic arguments that a type keeps: `list[tuple[str, int]]` has
# two; in `list[tuple[list[str], int]]` the inner `list` keeps no arguments.
MAX_DEPTH = 2


# The directory of the data of the third-party distributions, in the output
# directory (as pycg/analysis/stubs.py reads it).
THIRD_PARTY = "third_party"


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    checkout, commit = Path(argv[1]), argv[2]
    root = Path(__file__).resolve().parent.parent
    output = Path(argv[3]) if len(argv) == 4 else root / "pycg/analysis/stub_data"
    reader = StubReader.from_typeshed(checkout)
    licence = checkout / "LICENSE"
    write(reader.generate(), output, commit, licence, reader.distributions)
    return 0


def write(packages, output, commit, licence=None, distributions=()):
    """Write the data of each top-level module into `output`, those of the
    `distributions` into its `third_party/` directory, the README and the
    licence, replacing the JSON files that are there."""
    third_party = output / THIRD_PARTY
    third_party.mkdir(parents=True, exist_ok=True)
    for old in [*output.glob("*.json"), *third_party.glob("*.json")]:
        old.unlink()
    tops = {top for distribution in distributions for top in distribution.tops}
    for name, data in packages.items():
        directory = third_party if name in tops else output
        path = directory / f"{name}.json"
        path.write_text(dumps(data) + "\n", encoding="utf-8", newline="\n")
    readme = README.format(commit=commit, distributions=_table(distributions))
    (output / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    if licence is not None:
        shutil.copyfile(licence, output / "LICENSE")


def dumps(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


README = """\
# Stub data

Generated by `tools/generate_stubs.py` from the stubs of typeshed
(https://github.com/python/typeshed) at commit
`{commit}`:
the standard library (`stdlib/`) in this directory, and the third-party
distributions (`stubs/`) in `third_party/`.
Do not edit by hand: regenerate. typeshed is licensed under the Apache
License 2.0; its licence is in `LICENSE`. `pycg/analysis/stubs.py`
describes the format.

## Third-party distributions

Each distribution with the versions of its library that the stub describes
(`version` in its `METADATA.toml`) and the top-level modules it gives.
Obsolete: the library ships its own types since that version, and the stub
describes the versions before. Partial: the stub describes part of the
library.

| Distribution | Version | Modules | Notes |
|---|---|---|---|
{distributions}"""


def _table(distributions):
    rows = []
    for distribution in distributions:
        notes = []
        if distribution.obsolete_since is not None:
            notes.append(f"obsolete since {distribution.obsolete_since}")
        if distribution.partial:
            notes.append("partial")
        for top in distribution.left_out:
            notes.append(f"`{top}` left out: the standard library has it")
        modules = ", ".join(f"`{top}`" for top in distribution.tops)
        cells = [distribution.name, distribution.version, modules, "; ".join(notes)]
        rows.append("| " + " | ".join(cells) + " |\n")
    return "".join(rows)


class Distribution(NamedTuple):
    """A third-party distribution of typeshed: its name, the versions of
    the library that its stub describes, the version since which it is
    obsolete, whether it is partial, the top-level modules that it gives,
    and those left out because the standard library has them."""

    name: str
    version: str
    obsolete_since: str | None
    partial: bool
    tops: list
    left_out: list


def read_tree(root):
    """The modules of the stubs under `root`: each name with the stub's
    text and whether it is a package; and the names of the namespace
    packages, the directories that hold stubs but no `__init__.pyi`, which
    are modules without names. Directories whose name starts with `@` hold
    no stubs."""
    sources = {}
    for path in sorted(root.rglob("*.pyi")):
        parts = path.relative_to(root).with_suffix("").parts
        if any(part.startswith("@") for part in parts):
            continue
        package = parts[-1] == "__init__"
        if package:
            parts = parts[:-1]
        sources[".".join(parts)] = (path.read_text(encoding="utf-8"), package)
    namespaces = set()
    for name in list(sources):
        parts = name.split(".")
        for end in range(1, len(parts)):
            prefix = ".".join(parts[:end])
            if prefix not in sources:
                sources[prefix] = ("", True)
                namespaces.add(prefix)
    return sources, namespaces


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


# Scopes and definitions


class Binding:
    """One statement that binds a name in a module or class body. `kind` is
    one of: func, class, var, alias (a
    type alias), typevar, paramspec, typevartuple, newtype, and the imports
    from (an import of a name), module (an import of a module) and assign
    (`x = value`)."""

    __slots__ = ("kind", "node", "scope", "target", "reexport")

    def __init__(self, kind, node, scope=None, target=None, reexport=False):
        self.kind = kind
        self.node = node
        self.scope = scope
        self.target = target
        self.reexport = reexport


class Scope:
    """The bindings of a module or class body, by name, in source order;
    the modules it star-imports, and its `__all__`."""

    def __init__(self, module, qualname, parent=None):
        self.module = module
        self.qualname = qualname
        self.parent = parent
        self.bindings = {}
        self.stars = []
        self.all = None

    def add(self, name, binding):
        self.bindings.setdefault(name, []).append(binding)

    def qualify(self, name):
        return f"{self.qualname}.{name}" if self.qualname else name


class Def:
    """A definition: a module (qualname ""), or the bindings of one kind of
    a name in a scope."""

    __slots__ = ("kind", "module", "qualname", "bindings", "scope")

    def __init__(self, kind, module, qualname, bindings=(), scope=None):
        self.kind = kind
        self.module = module
        self.qualname = qualname
        self.bindings = bindings
        self.scope = scope

    @property
    def key(self):
        return (self.module, self.qualname)

    @property
    def path(self):
        return f"{self.module}.{self.qualname}" if self.qualname else self.module


def _unique(defs):
    result, seen = [], set()
    for found in defs:
        if (found.kind, found.key) not in seen:
            seen.add((found.kind, found.key))
            result.append(found)
    return result


class StubReader:
    def __init__(self, sources, owners=None, distributions=()):
        """`sources` maps each module name to its stub's text and whether it
        is a package; `owners` maps the modules of third-party
        distributions to the name of their distribution (the standard
        library's modules have none); `distributions` describes them."""
        self.sources = sources
        self.owners = owners or {}
        self.distributions = list(distributions)
        self._scopes = {}
        self._resolving = set()
        self._exports = {}
        self._mros = {}
        self._expanding = set()

    @classmethod
    def from_typeshed(cls, checkout):
        """The stubs of the standard library and of every distribution of
        the typeshed checkout `checkout` (see the module's docstring)."""
        sources, _ = read_tree(checkout / "stdlib")
        standard = {name.partition(".")[0] for name in sources}
        owners, namespaces, distributions = {}, set(), []
        stubs = checkout / "stubs"
        directories = sorted(stubs.iterdir()) if stubs.is_dir() else []
        for directory in directories:
            metadata_file = directory / "METADATA.toml"
            if not metadata_file.is_file():
                continue
            metadata = tomllib.loads(metadata_file.read_text(encoding="utf-8"))
            found, found_namespaces = read_tree(directory)
            tops, left_out = set(), set()
            for name, source in found.items():
                top = name.partition(".")[0]
                if top in standard:
                    left_out.add(top)
                    continue
                tops.add(top)
                if name in sources:
                    if name in found_namespaces:
                        # A namespace package that another distribution
                        # shares, or a package that it gives.
                        continue
                    if name not in namespaces:
                        raise ValueError(
                            f"{name} is in two distributions: "
                            f"{owners[name]} and {directory.name}"
                        )
                sources[name] = source
                owners[name] = directory.name
                if name in found_namespaces:
                    namespaces.add(name)
                else:
                    namespaces.discard(name)
            obsolete = metadata.get("obsolete-since")
            distribution = Distribution(
                name=directory.name,
                version=metadata["version"],
                obsolete_since=obsolete["version"] if obsolete else None,
                partial=bool(metadata.get("partial-stub", False)),
                tops=sorted(tops),
                left_out=sorted(left_out),
            )
            distributions.append(distribution)
        return cls(sources, owners, distributions)

    # Reading

    def scope(self, module):
        if module not in self._scopes:
            if module not in self.sources:
                return None
            text, package = self.sources[module]
            scope = Scope(module, "")
            self._scopes[module] = scope
            tree = ast.parse(text, filename=f"{module}.pyi")
            self._walk(tree.body, scope, package)
        return self._scopes[module]

    def _walk(self, statements, scope, package):
        for stmt in statements:
            self._statement(stmt, scope, package)

    def _statement(self, stmt, scope, package):
        match stmt:
            case ast.If():
                self._walk(stmt.body, scope, package)
                self._walk(stmt.orelse, scope, package)
            case ast.Try():
                for part in (stmt.body, stmt.orelse, stmt.finalbody):
                    self._walk(part, scope, package)
                for handler in stmt.handlers:
                    self._walk(handler.body, scope, package)
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                scope.add(stmt.name, Binding("func", stmt))
            case ast.ClassDef():
                inner = Scope(scope.module, scope.qualify(stmt.name), scope)
                self._walk(stmt.body, inner, package)
                scope.add(stmt.name, Binding("class", stmt, scope=inner))
            case ast.Import():
                for alias in stmt.names:
                    if alias.asname:
                        reexport = alias.asname == alias.name
                        binding = Binding("module", stmt, None, alias.name, reexport)
                        scope.add(alias.asname, binding)
                    else:
                        top = alias.name.partition(".")[0]
                        scope.add(top, Binding("module", stmt, None, top))
            case ast.ImportFrom():
                base = _absolute(scope.module, package, stmt.module, stmt.level)
                for alias in stmt.names:
                    if alias.name == "*":
                        scope.stars.append(base)
                        continue
                    reexport = alias.asname == alias.name
                    target = (base, alias.name)
                    binding = Binding("from", stmt, None, target, reexport)
                    scope.add(alias.asname or alias.name, binding)
            case ast.Assign(targets=[ast.Name(id=name)]):
                if name == "__all__":
                    scope.all = (scope.all or []) + _strings(stmt.value)
                    return
                value = stmt.value
                if isinstance(value, ast.Call):
                    callee = _dotted(value.func) or ""
                    kind = TYPEVAR_KINDS.get(callee.rpartition(".")[2], "assign")
                elif isinstance(value, (ast.Subscript, ast.BinOp)):
                    # `_Handler = Callable[[str], None]`: a type alias.
                    kind = "alias"
                else:
                    kind = "assign"
                scope.add(name, Binding(kind, stmt))
            case ast.AugAssign(target=ast.Name(id="__all__")):
                scope.all = (scope.all or []) + _strings(stmt.value)
            case ast.AnnAssign(target=ast.Name(id=name)):
                annotation = _dotted(stmt.annotation) or ""
                if annotation.rpartition(".")[2] == "TypeAlias":
                    scope.add(name, Binding("alias", stmt))
                else:
                    scope.add(name, Binding("var", stmt))
            case ast.TypeAlias(name=ast.Name(id=name)):
                scope.add(name, Binding("alias", stmt))

    # Resolution

    def resolve(self, module, name):
        """The definitions that `name` has in `module`: through imports,
        star imports and assignments of names, every alternative; or the
        submodule of that name. A name on a cycle of imports has none."""
        key = (module, name)
        if key in self._resolving:
            return []
        self._resolving.add(key)
        try:
            scope = self.scope(module)
            if scope is None:
                return []
            if name in scope.bindings:
                return self.resolve_bindings(scope, name)
            found = []
            for star in scope.stars:
                if name in self.exports(star):
                    found.extend(self.resolve(star, name))
            if not found and f"{module}.{name}" in self.sources:
                found.append(Def("module", f"{module}.{name}", ""))
            return _unique(found)
        finally:
            self._resolving.discard(key)

    def resolve_bindings(self, scope, name):
        """The definitions that the bindings of `name` in `scope` make: one
        per kind of definition, and those of every import (a name that one
        version defines and another re-exports has both)."""
        bindings = scope.bindings[name]
        defining = [b for b in bindings if b.kind not in IMPORTS]
        found = []
        for kind in dict.fromkeys(b.kind for b in defining):
            same = [b for b in defining if b.kind == kind]
            found.append(Def(kind, scope.module, scope.qualify(name), same, scope))
        for binding in bindings:
            if binding.kind in IMPORTS:
                found.extend(self._resolve_import(scope, name, binding))
        return _unique(found)

    def _resolve_import(self, scope, name, binding):
        if binding.kind == "module":
            if binding.target in self.sources:
                return [Def("module", binding.target, "")]
            return []
        if binding.kind == "from":
            return self.resolve_member(*binding.target)
        # `x = y` is what y is; `x = f()` is a value.
        value = binding.node.value
        if isinstance(value, (ast.Name, ast.Attribute)):
            found = self.resolve_expression(scope, value)
            if found:
                return found
        return [Def("assign", scope.module, scope.qualify(name), [binding], scope)]

    def resolve_member(self, module, name):
        """`module.name`: a submodule of that name, else the name."""
        if f"{module}.{name}" in self.sources:
            return [Def("module", f"{module}.{name}", "")]
        return self.resolve(module, name)

    def resolve_expression(self, scope, node):
        """The definitions that the name or attribute chain `node` refers to
        in `scope`. As for type checkers, a class body sees its own names
        and those of enclosing class bodies first, then the module's, then
        the builtins."""
        if isinstance(node, ast.Name):
            while scope.parent is not None:
                if node.id in scope.bindings:
                    return self.resolve_bindings(scope, node.id)
                scope = scope.parent
            found = self.resolve(scope.module, node.id)
            if not found and scope.module != "builtins":
                found = self.resolve("builtins", node.id)
            return found
        if isinstance(node, ast.Attribute):
            found = []
            for base in self.resolve_expression(scope, node.value):
                if base.kind == "module":
                    found.extend(self.resolve_member(base.module, node.attr))
                elif base.kind == "class":
                    for binding in base.bindings:
                        if node.attr in binding.scope.bindings:
                            found.extend(
                                self.resolve_bindings(binding.scope, node.attr)
                            )
            return _unique(found)
        return []

    def exports(self, module):
        """The names that `from module import *` gives: `__all__` if the
        module defines it, else its public names that it defines or
        re-exports."""
        if module in self._exports:
            return self._exports[module]
        self._exports[module] = frozenset()
        scope = self.scope(module)
        if scope is None:
            return frozenset()
        if scope.all is not None:
            names = set(scope.all)
        else:
            names = set()
            for name, bindings in scope.bindings.items():
                if not name.startswith("_") and any(_kept(b) for b in bindings):
                    names.add(name)
            for star in scope.stars:
                names.update(n for n in self.exports(star) if not n.startswith("_"))
        self._exports[module] = frozenset(names)
        return self._exports[module]

    def kept_names(self, scope):
        """The names that the data of a module or class keeps: those it
        defines, those it re-exports (also through star imports), and the
        names in its `__all__`."""
        names = {
            name
            for name, bindings in scope.bindings.items()
            if any(_kept(b) for b in bindings)
        }
        if scope.parent is None:
            names.update(self.exports(scope.module))
            for star in scope.stars:
                names.update(self.exports(star))
        return names

    # Types

    def type(self, scope, node, depth=0):
        """The reduced form of the annotation `node` (see stubs.py)."""
        match node:
            case ast.Constant(value=None):
                return "*none"
            case ast.Constant(value=str() as text):
                try:
                    parsed = ast.parse(text.strip(), mode="eval").body
                except SyntaxError:
                    return None
                return self.type(scope, parsed, depth)
            case ast.BinOp(op=ast.BitOr()):
                left = self.type(scope, node.left, depth)
                right = self.type(scope, node.right, depth)
                return _union([left, right])
            case ast.Attribute(attr="args" | "kwargs") if any(
                found.kind == "paramspec"
                for found in self.resolve_expression(scope, node.value)
            ):
                # `*args: P.args`: values that the function passes on.
                return "builtins.object"
            case ast.Starred():
                # `*args: *Ts`, as `Unpack[Ts]`.
                return "builtins.object"
            case ast.Name() | ast.Attribute():
                defs = self.resolve_expression(scope, node)
                return _union([self._named_type(found, depth) for found in defs])
            case ast.Subscript():
                return self._subscript_type(scope, node, depth)
        return None

    def _named_type(self, found, depth):
        special = _special(found)
        if special is not None:
            return BARE_SPECIAL_FORMS.get(special)
        if found.module in TYPING_MODULES and found.qualname in TYPING_ALIASES:
            return TYPING_ALIASES[found.qualname]
        if found.kind == "class":
            return found.path
        if found.kind == "typevar":
            bound, constrained = self._typevar_bound(found, depth)
            if bound is None:
                return ["*var", found.path]
            if constrained:
                # `AnyStr = TypeVar("AnyStr", str, bytes)`: the variable is
                # one of the constraints, not any subclass of their union.
                return ["*var", found.path, bound, "c"]
            return ["*var", found.path, bound]
        if found.kind == "newtype":
            call = found.bindings[0].node.value
            if len(call.args) == 2:
                return self.type(found.scope, call.args[1], depth)
            return None
        if found.kind in ("alias", "assign"):
            return self._alias_type(found, depth)
        return None

    def _typevar_bound(self, found, depth):
        """The bound of a type variable, or the union of its constraints,
        and whether they are constraints."""
        call = found.bindings[0].node.value
        constraints = [self.type(found.scope, arg, depth) for arg in call.args[1:]]
        if constraints:
            return _union(constraints), True
        for keyword in call.keywords:
            if keyword.arg == "bound":
                return self.type(found.scope, keyword.value, depth), False
        return None, False

    def _alias_type(self, found, depth):
        """The type that a type alias, or an assignment of a type, stands
        for: its definition, whose type parameters are not substituted."""
        if found.key in self._expanding:
            return None
        self._expanding.add(found.key)
        try:
            value = found.bindings[0].node.value
            if isinstance(value, ast.Call):
                # `x = C()` is an instance of C, not a type.
                return None
            return self.type(found.scope, value, depth)
        finally:
            self._expanding.discard(found.key)

    def _subscript_type(self, scope, node, depth):
        defs = self.resolve_expression(scope, node.value)
        if not defs:
            return None
        found = defs[0]
        items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        special = _special(found)
        if special in ("Union", "Optional"):
            arms = [self.type(scope, item, depth) for item in items]
            return _union(arms + (["*none"] if special == "Optional" else []))
        if special == "Callable":
            return self._callable_type(scope, items, depth)
        if special == "Type":
            return ["*type", self.type(scope, items[0], depth)]
        if special == "Literal":
            return _union([self._literal_type(scope, item) for item in items])
        if special in TRANSPARENT:
            return self.type(scope, items[0], depth)
        if special in ("TypeGuard", "TypeIs"):
            return "builtins.bool"
        if special == "Unpack":
            # `*args: Unpack[Ts]`: values that the function passes on.
            return "builtins.object"
        if special is not None:
            return None
        cls = _union([self._named_type(d, depth) for d in defs])
        if not isinstance(cls, str) or cls.startswith("*"):
            # A generic alias, or no class.
            return cls
        if depth >= MAX_DEPTH:
            return cls
        arguments = []
        for item in items:
            if isinstance(item, ast.Constant) and item.value is Ellipsis:
                arguments.append("...")
            elif not (isinstance(item, ast.Tuple) and not item.elts):
                arguments.append(self.type(scope, item, depth + 1))
        return [cls, *arguments]

    def _callable_type(self, scope, items, depth):
        if len(items) != 2:
            return ["*call", None, None]
        parameters, result = items
        returns = self.type(scope, result, depth)
        if isinstance(parameters, ast.List):
            listed = [self.type(scope, p, depth + 1) for p in parameters.elts]
            return ["*call", returns, listed]
        return ["*call", returns, None]

    def _literal_type(self, scope, node):
        if isinstance(node, ast.UnaryOp):
            node = node.operand
        if isinstance(node, ast.Constant):
            if node.value is None:
                return "*none"
            return f"builtins.{type(node.value).__name__}"
        if isinstance(node, ast.Attribute):
            # An enum member: its class.
            classes = [
                d.path
                for d in self.resolve_expression(scope, node.value)
                if d.kind == "class"
            ]
            return _union(classes) if classes else None
        return None

    # Classes

    def class_def(self, path):
        """The class whose definition path is `path`, or None."""
        module = path
        while "." in module:
            module = module.rpartition(".")[0]
            scope = self.scope(module)
            if scope is None:
                continue
            found = None
            for part in path[len(module) + 1 :].split("."):
                if scope is None or part not in scope.bindings:
                    return None
                defs = [
                    d for d in self.resolve_bindings(scope, part) if d.kind == "class"
                ]
                if not defs:
                    return None
                found = defs[0]
                scope = found.bindings[0].scope
            return found
        return None

    def bases(self, found):
        """The types of the base expressions of the class `found`, in every
        version, without `Generic` and `Protocol`; and whether it is a
        protocol."""
        result, protocol = [], False
        for binding in found.bindings:
            for base in binding.node.bases:
                target = base.value if isinstance(base, ast.Subscript) else base
                specials = [
                    _special(d) for d in self.resolve_expression(found.scope, target)
                ]
                if "Protocol" in specials or "Generic" in specials:
                    protocol = protocol or "Protocol" in specials
                    continue
                reduced = self.type(found.scope, base)
                if reduced is not None and reduced not in result:
                    result.append(reduced)
        return result, protocol

    def mro(self, path):
        """The classes that the class `path` inherits from, itself first,
        depth first: enough to find whether one of them defines a name."""
        if path in self._mros:
            return self._mros[path] or [path]
        self._mros[path] = None
        found = self.class_def(path)
        order = [path]
        if found is not None:
            for base in self.bases(found)[0]:
                for name in _class_names(base):
                    for cls in self.mro(name):
                        if cls not in order:
                            order.append(cls)
        self._mros[path] = order
        return order

    # Output

    def generate(self):
        """The data of every top-level module, by name."""
        public = self._public_class_names()
        packages = {}
        for module in sorted(self.sources):
            top = module.partition(".")[0]
            data = packages.setdefault(top, {"modules": {}})
            data["modules"][module] = self.module_data(module, public)
        return packages

    def module_data(self, module, public=None):
        scope = self.scope(module)
        data = {"names": self._names(scope, public or {})}
        if scope.all is not None:
            data["all"] = sorted(set(scope.all))
        return data

    def _names(self, scope, public):
        names = {}
        for name in sorted(self.kept_names(scope)):
            entry = self._entry(scope, name, public)
            if entry is not None:
                names[name] = entry
        return names

    def _entry(self, scope, name, public):
        bindings = scope.bindings.get(name, [])
        defining = [b for b in bindings if b.kind not in IMPORTS]
        if defining:
            kind = defining[0].kind
            same = [b for b in defining if b.kind == kind]
            if kind == "func":
                entry = self._function(scope, same)
            elif kind == "class":
                entry = self._class(scope, name, same, public)
            elif kind == "var":
                arms = [self._var_type(scope, b) for b in same]
                entry = {"k": "v", "t": _union(arms)}
            else:
                # Type variables, type aliases and new types are types only.
                return None
            imported = []
            for binding in bindings:
                if binding.kind in IMPORTS:
                    imported += self._resolve_import(scope, name, binding)
            also = self._reference(scope, name, _unique(imported))
            if also is not None and also["k"] == "r":
                # Another version or platform re-exports another definition.
                entry["also"] = also["to"]
        else:
            if bindings:
                found = self.resolve_bindings(scope, name)
            else:
                found = self.resolve(scope.module, name)
            entry = self._bound_method(scope, bindings) or self._reference(
                scope, name, found
            )
        return entry

    def _bound_method(self, scope, bindings):
        """`uniform = _inst.uniform`, a method of an instance that the
        module holds: a function with the signatures of the method, without
        the receiver. None for any other binding."""
        for binding in bindings:
            value = binding.node.value if binding.kind == "assign" else None
            if not isinstance(value, ast.Attribute):
                continue
            for base in self.resolve_expression(scope, value.value):
                if base.kind != "var":
                    continue
                types = [self._var_type(base.scope, b) for b in base.bindings]
                for cls in _class_names(_union(types)):
                    method = self._member(cls, value.attr)
                    if method is None:
                        continue
                    entry = self._function(method.scope, method.bindings)
                    if entry["k"] != "f":
                        continue
                    if entry.pop("d", None) != "staticmethod":
                        for signature in entry["s"]:
                            signature["p"] = signature["p"][1:]
                    return entry
        return None

    def _member(self, cls, name):
        """The function `name` that a lookup on the class `cls` finds."""
        for owner in self.mro(cls):
            found = self.class_def(owner)
            if found is None:
                continue
            for binding in found.bindings:
                if name in binding.scope.bindings:
                    defs = self.resolve_bindings(binding.scope, name)
                    return next((d for d in defs if d.kind == "func"), None)
        return None

    def _var_type(self, scope, binding):
        node = binding.node
        reduced = self.type(scope, node.annotation)
        if reduced is None and isinstance(node.value, ast.Constant):
            # `x: Final = 1` has the type of its value.
            return self._literal_type(scope, node.value)
        return reduced

    def _reference(self, scope, name, defs):
        """A name that refers to other definitions; an assignment of a value
        (`x = f()`) is a variable, of the class it calls if it calls one."""
        targets = []
        for found in defs:
            if found.kind == "assign" and found.key == (
                scope.module,
                scope.qualify(name),
            ):
                return {"k": "v", "t": self._assigned_type(found)}
            if found.kind in ("module", "func", "class", "var", "assign"):
                targets.append([found.module, found.qualname])
        if not targets:
            return None
        return {"k": "r", "to": targets}

    def _assigned_type(self, found):
        value = found.bindings[0].node.value
        if isinstance(value, ast.Call):
            classes = [
                d.path
                for d in self.resolve_expression(found.scope, value.func)
                if d.kind == "class"
            ]
            return _union(classes) if classes else None
        return None

    def _function(self, scope, bindings):
        signatures = []
        decorator, abstract, setter = None, False, False
        for binding in bindings:
            node = binding.node
            kinds = [self._decorator(scope, d) for d in node.decorator_list]
            if "setter" in kinds or "deleter" in kinds:
                setter = setter or "setter" in kinds
                continue
            abstract = abstract or "abstract" in kinds
            for kind in ("property", "classmethod", "staticmethod"):
                if kind in kinds:
                    decorator = kind
            signature = {
                "p": self._parameters(scope, node.args),
                "r": self.type(scope, node.returns),
            }
            if isinstance(node, ast.AsyncFunctionDef):
                signature["a"] = 1
            if signature not in signatures:
                # Versions and platforms may repeat a signature.
                signatures.append(signature)
        if decorator == "property":
            entry = {"k": "p", "t": _union([s["r"] for s in signatures])}
            if setter:
                entry["set"] = 1
        else:
            entry = {"k": "f", "s": signatures}
            if decorator is not None:
                entry["d"] = decorator
        if abstract:
            entry["x"] = 1
        return entry

    def _decorator(self, scope, node):
        target = node.func if isinstance(node, ast.Call) else node
        if isinstance(target, ast.Attribute) and target.attr in ("setter", "deleter"):
            return target.attr
        for found in self.resolve_expression(scope, target):
            if found.kind == "assign":
                # `_magic_enum_attr = property`
                value = found.bindings[0].node.value
                aliased = self.resolve_expression(found.scope, value)
                if aliased:
                    found = aliased[0]
            key = found.key
            if key in PROPERTY_DECORATORS:
                return "property"
            if key in (("builtins", "classmethod"), ("builtins", "staticmethod")):
                return key[1]
            if key in (("abc", "abstractmethod"), ("typing", "abstractmethod")):
                return "abstract"
            if key[0] in TYPING_MODULES and key[1] in ("type_check_only", "final"):
                return key[1]
        return None

    def _parameters(self, scope, arguments):
        positional = arguments.posonlyargs + arguments.args
        defaults = [None] * (len(positional) - len(arguments.defaults))
        defaults += arguments.defaults
        # Before PEP 570, stubs marked positional-only parameters with two
        # leading underscores, after a receiver.
        posonly = len(arguments.posonlyargs)
        if not posonly:
            names = [arg.arg for arg in arguments.args]
            start = 1 if names and not _old_positional_only(names[0]) else 0
            end = start
            while end < len(names) and _old_positional_only(names[end]):
                end += 1
            if end > start:
                posonly = end
        result = []
        for index, (arg, default) in enumerate(zip(positional, defaults)):
            kind = "/" if index < posonly else ""
            result.append(self._parameter(scope, arg, kind, default is not None))
        if arguments.vararg is not None:
            result.append(self._parameter(scope, arguments.vararg, "*", False))
        for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
            result.append(self._parameter(scope, arg, "k", default is not None))
        if arguments.kwarg is not None:
            result.append(self._parameter(scope, arguments.kwarg, "**", False))
        return result

    def _parameter(self, scope, arg, kind, default):
        reduced = self.type(scope, arg.annotation) if arg.annotation else None
        return [arg.arg, kind, int(default), reduced]

    def _class(self, scope, name, bindings, public):
        found = Def("class", scope.module, scope.qualify(name), bindings, scope)
        bases, protocol = self.bases(found)
        inner = Scope(scope.module, found.qualname, scope)
        for binding in bindings:
            for member, member_bindings in binding.scope.bindings.items():
                for member_binding in member_bindings:
                    inner.add(member, member_binding)
        entry = {"k": "c", "b": bases, "m": self._names(inner, public)}
        if protocol:
            entry["proto"] = 1
        decorators = [
            self._decorator(scope, d) for b in bindings for d in b.node.decorator_list
        ]
        if "type_check_only" in decorators:
            entry["tco"] = 1
        if "final" in decorators:
            entry["final"] = 1
        parameters = self._type_parameters(scope, bindings[0].node)
        if parameters:
            entry["tp"] = parameters
        for keyword in bindings[0].node.keywords:
            if keyword.arg == "metaclass":
                entry["meta"] = self.type(scope, keyword.value)
        path = public.get(found.path, found.path)
        if path != found.path:
            entry["pub"] = path
        return entry

    def _type_parameters(self, scope, node):
        """The type variables of a generic class, in order: those of
        `Generic[...]` or `Protocol[...]` if a base lists them, else those
        of the bases in order of appearance (PEP 484), or the parameters of
        `class C[T]`."""
        explicit, implicit = None, []
        for base in node.bases:
            if not isinstance(base, ast.Subscript):
                continue
            names = []
            for item in ast.walk(base.slice):
                if isinstance(item, (ast.Name, ast.Attribute)):
                    for found in self.resolve_expression(scope, item):
                        if found.kind == "typevar" and found.path not in names:
                            names.append(found.path)
            specials = [_special(d) for d in self.resolve_expression(scope, base.value)]
            if "Generic" in specials or "Protocol" in specials:
                explicit = names
            implicit.extend(n for n in names if n not in implicit)
        for parameter in getattr(node, "type_params", ()):
            implicit.append(f"{scope.module}.{parameter.name}")
        return explicit if explicit is not None else implicit

    def _public_class_names(self):
        """The public name of each class, by its definition path: its
        shortest path from a public module of its own distribution (the
        standard library is one) through public names, preferring its own
        module, then in alphabetical order. A nested class is named
        through its enclosing class. A class without a public path keeps
        its definition path."""
        paths = {}
        for module in sorted(self.sources):
            if any(part.startswith("_") for part in module.split(".")):
                continue
            scope = self.scope(module)
            for name in sorted(self.kept_names(scope)):
                if name.startswith("_"):
                    continue
                for found in self.resolve(module, name):
                    if found.kind != "class":
                        continue
                    if self.owners.get(module) != self.owners.get(found.module):
                        # A path through another distribution.
                        continue
                    path = f"{module}.{name}"
                    rank = (path.count("."), module != found.module, path)
                    if found.path not in paths or rank < paths[found.path][0]:
                        paths[found.path] = (rank, path)
        public = {key: path for key, (_, path) in paths.items()}
        # Nested classes, through the public name of the enclosing class.
        for module in sorted(self.sources):
            self._nested_public(self.scope(module), public)
        return public

    def _nested_public(self, scope, public):
        for name, bindings in scope.bindings.items():
            for binding in bindings:
                if binding.kind != "class":
                    continue
                path = f"{scope.module}.{scope.qualify(name)}"
                if scope.parent is not None and path not in public:
                    outer = f"{scope.module}.{scope.qualname}"
                    public[path] = f"{public.get(outer, outer)}.{name}"
                self._nested_public(binding.scope, public)


def _kept(binding):
    """Whether the data keeps the name that `binding` binds: definitions
    and assignments, and imports that re-export."""
    return binding.kind not in ("from", "module") or binding.reexport


def _class_names(reduced):
    """The definition paths of the classes in a reduced base type."""
    match reduced:
        case ["|", *arms]:
            return [name for arm in arms for name in _class_names(arm)]
        case [str() as cls, *_] if not cls.startswith("*"):
            return [cls]
        case str() if not reduced.startswith("*"):
            return [reduced]
    return []


def _old_positional_only(name):
    return name.startswith("__") and not name.endswith("__")


def _special(found):
    if found.module in TYPING_MODULES and found.qualname in SPECIAL_FORMS:
        return found.qualname
    if found.key == ("builtins", "type"):
        return "Type"
    return None


def _union(arms):
    """A union of reduced types: flat, without repeats, in order of first
    appearance; a single arm is itself, and no arm is unknown."""
    flat = []
    for arm in arms:
        for item in arm[1:] if isinstance(arm, list) and arm[:1] == ["|"] else [arm]:
            if item not in flat:
                flat.append(item)
    if not flat:
        return None
    if len(flat) == 1:
        return flat[0]
    return ["|", *flat]


def _strings(node):
    """The strings of a list or tuple display, and of their sums."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _strings(node.left) + _strings(node.right)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [
            e.value
            for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
    return []


def _absolute(module, package, target, level):
    if level == 0:
        return target
    parts = module.split(".")
    if not package:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    base = ".".join(parts)
    return f"{base}.{target}" if target else base


if __name__ == "__main__":
    sys.exit(main(sys.argv))
