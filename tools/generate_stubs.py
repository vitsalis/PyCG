import argparse
import ast
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

TYPING_MODULES = ("typing", "typing_extensions")
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
TYPE_BY_BARE_SPECIAL_FORM = {
    "Self": "*self",
    "Never": "*none",
    "NoReturn": "*none",
    "LiteralString": "builtins.str",
    "Callable": ["*call", None, None],
    "Type": "builtins.type",
}
SPECIAL_FORMS_TRANSPARENT = frozenset(
    {"Annotated", "ClassVar", "Final", "NotRequired", "ReadOnly", "Required"}
)
CLASS_BY_TYPING_ALIAS = {
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
BINDING_KIND_BY_TYPE_FACTORY = {
    "TypeVar": "typevar",
    "ParamSpec": "paramspec",
    "TypeVarTuple": "typevartuple",
    "NewType": "newtype",
}
BINDING_KINDS_REFERENCE = ("from", "module", "assign")
BINDING_KINDS_TYPE_ONLY = ("alias", *BINDING_KIND_BY_TYPE_FACTORY.values())
BINDING_KINDS = (
    "func",
    "class",
    "var",
    *BINDING_KINDS_TYPE_ONLY,
    *BINDING_KINDS_REFERENCE,
)
PROPERTY_DECORATORS = frozenset(
    {
        ("builtins", "property"),
        ("functools", "cached_property"),
        ("types", "DynamicClassAttribute"),
    }
)
GENERIC_ARGUMENT_DEPTH_MAX = 2

THIRD_PARTY_DIRECTORY_NAME = "third_party"
BINDING_NOT_FROM_EXTENSION = "<not from an extension module>"
OUTPUT_DIRECTORY_DEFAULT = Path(__file__).resolve().parent.parent / (
    "crates/stubs/stub_data"
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate PyCG's stub data from the stubs of typeshed: one JSON "
            "file per top-level module of the standard library, one per "
            "top-level module of the third-party distributions in "
            f"{THIRD_PARTY_DIRECTORY_NAME}/, a README that records the "
            "commit and each distribution's version, and typeshed's licence. "
            "The names of the classes that CPython's extension modules define "
            "come from CPython's Lib/ sources. Reads the stubs and the sources "
            "with ast: nothing is imported or executed."
        )
    )
    parser.add_argument("checkout", type=Path, help="typeshed checkout")
    parser.add_argument(
        "commit", help="typeshed commit of the checkout, recorded in the README"
    )
    parser.add_argument(
        "--cpython",
        nargs=2,
        action="append",
        required=True,
        metavar=("CHECKOUT", "COMMIT"),
        help="CPython checkout of one supported version (Lib/ and "
        "Include/patchlevel.h) and its commit, recorded in the README; "
        "once per version",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=OUTPUT_DIRECTORY_DEFAULT,
        help="output directory (default: crates/stubs/stub_data/)",
    )
    arguments = parser.parse_args()
    cpython_libraries = [
        read_cpython_library(Path(checkout), commit)
        for checkout, commit in arguments.cpython
    ]
    for library in cpython_libraries:
        if sys.version_info[:2] < _version_order(library)[:2]:
            parser.error(
                f"the sources of CPython {library.version} need Python "
                f"{'.'.join(map(str, _version_order(library)[:2]))} or later "
                "to parse"
            )
    reader = StubReader.from_typeshed(arguments.checkout, cpython_libraries)
    licence = arguments.checkout / "LICENSE"
    packages = reader.generate()
    for conflict in reader.extension_name_conflicts:
        print(f"kept the stub's name of {conflict}", file=sys.stderr)
    write(
        packages,
        arguments.output,
        arguments.commit,
        licence,
        reader.distributions,
        cpython_libraries,
    )
    return 0


def write(
    packages,
    output_directory,
    commit,
    licence=None,
    distributions=(),
    cpython_libraries=(),
):
    third_party_directory = output_directory / THIRD_PARTY_DIRECTORY_NAME
    third_party_directory.mkdir(parents=True, exist_ok=True)
    json_files_old = [
        *output_directory.glob("*.json"),
        *third_party_directory.glob("*.json"),
    ]
    for json_file_old in json_files_old:
        json_file_old.unlink()
    top_level_modules_third_party = {
        top_level_module
        for distribution in distributions
        for top_level_module in distribution.top_level_modules
    }
    for name, data in packages.items():
        if name in top_level_modules_third_party:
            directory = third_party_directory
        else:
            directory = output_directory
        path = directory / f"{name}.json"
        path.write_text(dumps(data) + "\n", encoding="utf-8", newline="\n")
    readme = README.format(
        commit=commit,
        cpython=_cpython_table_rows(cpython_libraries),
        distributions=_distribution_table_rows(distributions),
    )
    (output_directory / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    if licence is not None:
        shutil.copyfile(licence, output_directory / "LICENSE")


def dumps(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


README = """\
# Stub data

Generated by `tools/generate_stubs.py` from the stubs of typeshed
(https://github.com/python/typeshed) at commit
`{commit}`:
the standard library (`stdlib/`) in this directory, and the third-party
distributions (`stubs/`) in `third_party/`. The names of the classes that
CPython's extension modules define come from the `Lib/` sources of CPython
(https://github.com/python/cpython) at these commits:

| Version | Commit |
|---|---|
{cpython}
Do not edit by hand: regenerate. typeshed is licensed under the Apache
License 2.0; its licence is in `LICENSE`.

## Third-party distributions

Each distribution with the versions of its library that the stub describes
(`version` in its `METADATA.toml`) and the top-level modules it gives.
Obsolete: the library ships its own types since that version, and the stub
describes the versions before. Partial: the stub describes part of the
library.

| Distribution | Version | Modules | Notes |
|---|---|---|---|
{distributions}"""


def _cpython_table_rows(cpython_libraries):
    return "".join(
        f"| {library.version} | `{library.commit}` |\n"
        for library in sorted(cpython_libraries, key=_version_order)
    )


def _distribution_table_rows(distributions):
    rows = []
    for distribution in distributions:
        notes = []
        if distribution.obsolete_since is not None:
            notes.append(f"obsolete since {distribution.obsolete_since}")
        if distribution.partial:
            notes.append("partial")
        for top_level_module in distribution.top_level_modules_left_out:
            notes.append(f"`{top_level_module}` left out: the standard library has it")
        modules = ", ".join(
            f"`{top_level_module}`"
            for top_level_module in distribution.top_level_modules
        )
        cells = [distribution.name, distribution.version, modules, "; ".join(notes)]
        rows.append("| " + " | ".join(cells) + " |\n")
    return "".join(rows)


class Distribution(NamedTuple):
    name: str
    version: str
    obsolete_since: str | None
    partial: bool
    top_level_modules: list
    top_level_modules_left_out: list


class CPythonLibrary(NamedTuple):
    version: str
    commit: str
    library_directory: Path
    python_modules: frozenset


def read_cpython_library(checkout, commit):
    patchlevel = (checkout / "Include/patchlevel.h").read_text(encoding="utf-8")
    version = re.search(r'^#define PY_VERSION\s+"([^"]+)"', patchlevel, re.M)
    assert version is not None, checkout
    library_directory = checkout / "Lib"
    python_modules = set()
    for path in library_directory.rglob("*"):
        parts = path.relative_to(library_directory).parts
        if path.is_dir():
            python_modules.add(".".join(parts))
        elif path.suffix == ".py":
            parts = path.relative_to(library_directory).with_suffix("").parts
            python_modules.add(".".join(parts))
    return CPythonLibrary(
        version.group(1), commit, library_directory, frozenset(python_modules)
    )


def _version_order(library):
    return tuple(int(part) for part in re.findall(r"\d+", library.version)[:3])


def final_binding(library, module, name):
    parts = module.split(".")
    for path in (
        library.library_directory.joinpath(*parts).with_suffix(".py"),
        library.library_directory.joinpath(*parts, "__init__.py"),
    ):
        if path.is_file():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            return _final_binding_in(library, tree.body, name, None)
    return None


def _final_binding_in(library, statements, name, binding):
    for statement in statements:
        if isinstance(statement, (ast.Try, ast.TryStar)):
            body = statement.body + statement.orelse + statement.finalbody
            binding = _final_binding_in(library, body, name, binding)
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*":
                    binding = BINDING_NOT_FROM_EXTENSION
                    continue
                if (alias.asname or alias.name) != name:
                    continue
                source = statement.module
                if statement.level == 0 and source not in library.python_modules:
                    binding = f"{source}.{alias.name}"
                else:
                    binding = BINDING_NOT_FROM_EXTENSION
        elif name in _names_bound_by(statement):
            binding = BINDING_NOT_FROM_EXTENSION
    return binding


def _names_bound_by(statement):
    names = set()
    pending = [statement]
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node is not statement:
                continue
            pending.extend(node.decorator_list)
            continue
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp)):
            continue
        if isinstance(node, ast.GeneratorExp):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).partition(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        pending.extend(ast.iter_child_nodes(node))
    return names


def read_stub_tree(root):
    sources = {}
    for path in sorted(root.rglob("*.pyi")):
        parts = path.relative_to(root).with_suffix("").parts
        if any(part.startswith("@") for part in parts):
            continue
        package = parts[-1] == "__init__"
        if package:
            parts = parts[:-1]
        sources[".".join(parts)] = (path.read_text(encoding="utf-8"), package)
    namespace_packages = set()
    for name in list(sources):
        parts = name.split(".")
        for end in range(1, len(parts)):
            prefix = ".".join(parts[:end])
            if prefix not in sources:
                sources[prefix] = ("", True)
                namespace_packages.add(prefix)
    return sources, namespace_packages


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


class Binding:
    __slots__ = ("kind", "node", "scope", "target", "reexport")

    def __init__(self, kind, node, scope=None, target=None, reexport=False):
        assert kind in BINDING_KINDS, kind
        self.kind = kind
        self.node = node
        self.scope = scope
        self.target = target
        self.reexport = reexport


class Scope:
    def __init__(self, module, qualname, parent=None):
        self.module = module
        self.qualname = qualname
        self.parent = parent
        self.bindings_by_name = {}
        self.star_import_modules = []
        self.all_names = None

    def add(self, name, binding):
        self.bindings_by_name.setdefault(name, []).append(binding)

    def qualify(self, name):
        return f"{self.qualname}.{name}" if self.qualname else name


class Definition:
    __slots__ = ("kind", "module", "qualname", "bindings", "scope")

    def __init__(self, kind, module, qualname, bindings=(), scope=None):
        assert kind != "module" or qualname == "", qualname
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


def _unique_definitions(definitions):
    result, seen = [], set()
    for found in definitions:
        if (found.kind, found.key) not in seen:
            seen.add((found.kind, found.key))
            result.append(found)
    return result


class StubReader:
    def __init__(
        self,
        sources,
        distribution_by_module=None,
        distributions=(),
        cpython_libraries=(),
    ):
        self.sources = sources
        self.distribution_by_module = distribution_by_module or {}
        self.distributions = list(distributions)
        self.cpython_libraries = sorted(cpython_libraries, key=_version_order)
        self.extension_name_conflicts = []
        self._scope_by_module = {}
        self._keys_resolving = set()
        self._star_import_names_by_module = {}
        self._ancestors_by_class = {}
        self._aliases_expanding = set()

    @classmethod
    def from_typeshed(cls, checkout, cpython_libraries=()):
        sources, _ = read_stub_tree(checkout / "stdlib")
        top_level_modules_standard = {name.partition(".")[0] for name in sources}
        distribution_by_module, namespace_packages, distributions = {}, set(), []
        stubs = checkout / "stubs"
        directories = sorted(stubs.iterdir()) if stubs.is_dir() else []
        for directory in directories:
            metadata_file = directory / "METADATA.toml"
            if not metadata_file.is_file():
                continue
            metadata = tomllib.loads(metadata_file.read_text(encoding="utf-8"))
            found, namespace_packages_found = read_stub_tree(directory)
            top_level_modules, top_level_modules_left_out = set(), set()
            for name, source in found.items():
                top_level_module = name.partition(".")[0]
                if top_level_module in top_level_modules_standard:
                    top_level_modules_left_out.add(top_level_module)
                    continue
                top_level_modules.add(top_level_module)
                if name in sources:
                    if name in namespace_packages_found:
                        continue
                    if name not in namespace_packages:
                        raise ValueError(
                            f"{name} is in two distributions: "
                            f"{distribution_by_module[name]} and {directory.name}"
                        )
                sources[name] = source
                distribution_by_module[name] = directory.name
                if name in namespace_packages_found:
                    namespace_packages.add(name)
                else:
                    namespace_packages.discard(name)
            obsolete = metadata.get("obsolete-since")
            distribution = Distribution(
                name=directory.name,
                version=metadata["version"],
                obsolete_since=obsolete["version"] if obsolete else None,
                partial=bool(metadata.get("partial-stub", False)),
                top_level_modules=sorted(top_level_modules),
                top_level_modules_left_out=sorted(top_level_modules_left_out),
            )
            distributions.append(distribution)
        return cls(sources, distribution_by_module, distributions, cpython_libraries)

    def scope(self, module):
        if module not in self._scope_by_module:
            if module not in self.sources:
                return None
            text, package = self.sources[module]
            scope = Scope(module, "")
            self._scope_by_module[module] = scope
            tree = ast.parse(text, filename=f"{module}.pyi")
            self._walk(tree.body, scope, package)
        return self._scope_by_module[module]

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
                base = _absolute_module_name(
                    scope.module, package, stmt.module, stmt.level
                )
                for alias in stmt.names:
                    if alias.name == "*":
                        scope.star_import_modules.append(base)
                        continue
                    reexport = alias.asname == alias.name
                    target = (base, alias.name)
                    binding = Binding("from", stmt, None, target, reexport)
                    scope.add(alias.asname or alias.name, binding)
            case ast.Assign(targets=[ast.Name(id=name)]):
                if name == "__all__":
                    scope.all_names = (scope.all_names or []) + _string_constants(
                        stmt.value
                    )
                    return
                value = stmt.value
                if isinstance(value, ast.Call):
                    callee = _dotted_name(value.func) or ""
                    kind = BINDING_KIND_BY_TYPE_FACTORY.get(
                        callee.rpartition(".")[2], "assign"
                    )
                elif isinstance(value, (ast.Subscript, ast.BinOp)):
                    kind = "alias"
                else:
                    kind = "assign"
                scope.add(name, Binding(kind, stmt))
            case ast.AugAssign(target=ast.Name(id="__all__")):
                scope.all_names = (scope.all_names or []) + _string_constants(
                    stmt.value
                )
            case ast.AnnAssign(target=ast.Name(id=name)):
                annotation = _dotted_name(stmt.annotation) or ""
                if annotation.rpartition(".")[2] == "TypeAlias":
                    scope.add(name, Binding("alias", stmt))
                else:
                    scope.add(name, Binding("var", stmt))
            case ast.TypeAlias(name=ast.Name(id=name)):
                scope.add(name, Binding("alias", stmt))

    def resolve(self, module, name):
        key = (module, name)
        if key in self._keys_resolving:
            return []
        self._keys_resolving.add(key)
        try:
            scope = self.scope(module)
            if scope is None:
                return []
            if name in scope.bindings_by_name:
                return self.resolve_bindings(scope, name)
            found = []
            for star_import_module in scope.star_import_modules:
                if name in self.star_import_names(star_import_module):
                    found.extend(self.resolve(star_import_module, name))
            if not found and f"{module}.{name}" in self.sources:
                found.append(Definition("module", f"{module}.{name}", ""))
            return _unique_definitions(found)
        finally:
            self._keys_resolving.discard(key)

    def resolve_bindings(self, scope, name):
        bindings = scope.bindings_by_name[name]
        defining = [b for b in bindings if b.kind not in BINDING_KINDS_REFERENCE]
        found = []
        for kind in dict.fromkeys(b.kind for b in defining):
            same = [b for b in defining if b.kind == kind]
            found.append(
                Definition(kind, scope.module, scope.qualify(name), same, scope)
            )
        for binding in bindings:
            if binding.kind in BINDING_KINDS_REFERENCE:
                found.extend(self._resolve_reference(scope, name, binding))
        return _unique_definitions(found)

    def _resolve_reference(self, scope, name, binding):
        if binding.kind == "module":
            if binding.target in self.sources:
                return [Definition("module", binding.target, "")]
            return []
        if binding.kind == "from":
            return self.resolve_member(*binding.target)
        value = binding.node.value
        if isinstance(value, (ast.Name, ast.Attribute)):
            found = self.resolve_expression(scope, value)
            if found:
                return found
        return [
            Definition("assign", scope.module, scope.qualify(name), [binding], scope)
        ]

    def resolve_member(self, module, name):
        if f"{module}.{name}" in self.sources:
            return [Definition("module", f"{module}.{name}", "")]
        return self.resolve(module, name)

    def resolve_expression(self, scope, node):
        if isinstance(node, ast.Name):
            while scope.parent is not None:
                if node.id in scope.bindings_by_name:
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
                        if node.attr in binding.scope.bindings_by_name:
                            found.extend(
                                self.resolve_bindings(binding.scope, node.attr)
                            )
            return _unique_definitions(found)
        return []

    def star_import_names(self, module):
        if module in self._star_import_names_by_module:
            return self._star_import_names_by_module[module]
        self._star_import_names_by_module[module] = frozenset()
        scope = self.scope(module)
        if scope is None:
            return frozenset()
        if scope.all_names is not None:
            names = set(scope.all_names)
        else:
            names = set()
            for name, bindings in scope.bindings_by_name.items():
                if not name.startswith("_") and any(_binding_kept(b) for b in bindings):
                    names.add(name)
            for star_import_module in scope.star_import_modules:
                names.update(
                    star_name
                    for star_name in self.star_import_names(star_import_module)
                    if not star_name.startswith("_")
                )
        self._star_import_names_by_module[module] = frozenset(names)
        return self._star_import_names_by_module[module]

    def kept_names(self, scope):
        names = {
            name
            for name, bindings in scope.bindings_by_name.items()
            if any(_binding_kept(b) for b in bindings)
        }
        if scope.parent is None:
            names.update(self.star_import_names(scope.module))
            for star_import_module in scope.star_import_modules:
                names.update(self.star_import_names(star_import_module))
        return names

    def reduced_type(self, scope, node, depth=0):
        match node:
            case ast.Constant(value=None):
                return "*none"
            case ast.Constant(value=str() as text):
                try:
                    parsed = ast.parse(text.strip(), mode="eval").body
                except SyntaxError:
                    return None
                return self.reduced_type(scope, parsed, depth)
            case ast.BinOp(op=ast.BitOr()):
                left = self.reduced_type(scope, node.left, depth)
                right = self.reduced_type(scope, node.right, depth)
                return _union([left, right])
            case ast.Attribute(attr="args" | "kwargs") if any(
                found.kind == "paramspec"
                for found in self.resolve_expression(scope, node.value)
            ):
                return "builtins.object"
            case ast.Starred():
                return "builtins.object"
            case ast.Name() | ast.Attribute():
                definitions = self.resolve_expression(scope, node)
                return _union([self._named_type(found, depth) for found in definitions])
            case ast.Subscript():
                return self._subscript_type(scope, node, depth)
        return None

    def _named_type(self, found, depth):
        special_form = _special_form_name(found)
        if special_form is not None:
            return TYPE_BY_BARE_SPECIAL_FORM.get(special_form)
        if found.module in TYPING_MODULES and found.qualname in CLASS_BY_TYPING_ALIAS:
            return CLASS_BY_TYPING_ALIAS[found.qualname]
        if found.kind == "class":
            return found.path
        if found.kind == "typevar":
            bound, constrained = self._typevar_bound_or_constraints(found, depth)
            if bound is None:
                return ["*var", found.path]
            if constrained:
                return ["*var", found.path, bound, "c"]
            return ["*var", found.path, bound]
        if found.kind == "newtype":
            call = found.bindings[0].node.value
            if len(call.args) == 2:
                return self.reduced_type(found.scope, call.args[1], depth)
            return None
        if found.kind in ("alias", "assign"):
            return self._alias_type(found, depth)
        return None

    def _typevar_bound_or_constraints(self, found, depth):
        call = found.bindings[0].node.value
        constraints = [
            self.reduced_type(found.scope, arg, depth) for arg in call.args[1:]
        ]
        if constraints:
            return _union(constraints), True
        for keyword in call.keywords:
            if keyword.arg == "bound":
                return self.reduced_type(found.scope, keyword.value, depth), False
        return None, False

    def _alias_type(self, found, depth):
        if found.key in self._aliases_expanding:
            return None
        self._aliases_expanding.add(found.key)
        try:
            value = found.bindings[0].node.value
            value_is_instance = isinstance(value, ast.Call)
            if value_is_instance:
                return None
            return self.reduced_type(found.scope, value, depth)
        finally:
            self._aliases_expanding.discard(found.key)

    def _subscript_type(self, scope, node, depth):
        definitions = self.resolve_expression(scope, node.value)
        if not definitions:
            return None
        found = definitions[0]
        items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        special_form = _special_form_name(found)
        if special_form in ("Union", "Optional"):
            arms = [self.reduced_type(scope, item, depth) for item in items]
            return _union(arms + (["*none"] if special_form == "Optional" else []))
        if special_form == "Callable":
            return self._callable_type(scope, items, depth)
        if special_form == "Type":
            return ["*type", self.reduced_type(scope, items[0], depth)]
        if special_form == "Literal":
            return _union([self._literal_type(scope, item) for item in items])
        if special_form in SPECIAL_FORMS_TRANSPARENT:
            return self.reduced_type(scope, items[0], depth)
        if special_form in ("TypeGuard", "TypeIs"):
            return "builtins.bool"
        if special_form == "Unpack":
            return "builtins.object"
        if special_form is not None:
            return None
        cls = _union([self._named_type(d, depth) for d in definitions])
        cls_is_class = isinstance(cls, str) and not cls.startswith("*")
        if not cls_is_class:
            return cls
        if depth >= GENERIC_ARGUMENT_DEPTH_MAX:
            return cls
        arguments = []
        for item in items:
            if isinstance(item, ast.Constant) and item.value is Ellipsis:
                arguments.append("...")
            elif not (isinstance(item, ast.Tuple) and not item.elts):
                arguments.append(self.reduced_type(scope, item, depth + 1))
        return [cls, *arguments]

    def _callable_type(self, scope, items, depth):
        if len(items) != 2:
            return ["*call", None, None]
        parameters, result = items
        returns = self.reduced_type(scope, result, depth)
        if isinstance(parameters, ast.List):
            listed = [self.reduced_type(scope, p, depth + 1) for p in parameters.elts]
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
            enum_classes = [
                d.path
                for d in self.resolve_expression(scope, node.value)
                if d.kind == "class"
            ]
            return _union(enum_classes) if enum_classes else None
        return None

    def class_definition(self, path):
        module = path
        while "." in module:
            module = module.rpartition(".")[0]
            scope = self.scope(module)
            if scope is None:
                continue
            found = None
            for part in path[len(module) + 1 :].split("."):
                if scope is None or part not in scope.bindings_by_name:
                    return None
                classes = [
                    d for d in self.resolve_bindings(scope, part) if d.kind == "class"
                ]
                if not classes:
                    return None
                found = classes[0]
                scope = found.bindings[0].scope
            return found
        return None

    def bases_and_protocol(self, found):
        result, protocol = [], False
        for binding in found.bindings:
            for base in binding.node.bases:
                target = base.value if isinstance(base, ast.Subscript) else base
                special_forms = [
                    _special_form_name(d)
                    for d in self.resolve_expression(found.scope, target)
                ]
                if "Protocol" in special_forms or "Generic" in special_forms:
                    protocol = protocol or "Protocol" in special_forms
                    continue
                reduced = self.reduced_type(found.scope, base)
                if reduced is not None and reduced not in result:
                    result.append(reduced)
        return result, protocol

    def ancestors_depth_first(self, path):
        if path in self._ancestors_by_class:
            return self._ancestors_by_class[path] or [path]
        self._ancestors_by_class[path] = None
        found = self.class_definition(path)
        order = [path]
        if found is not None:
            for base in self.bases_and_protocol(found)[0]:
                for name in _class_paths(base):
                    for cls in self.ancestors_depth_first(name):
                        if cls not in order:
                            order.append(cls)
        self._ancestors_by_class[path] = order
        return order

    def generate(self):
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
        if scope.all_names is not None:
            data["all"] = sorted(set(scope.all_names))
        return data

    def _names(self, scope, public):
        names = {}
        for name in sorted(self.kept_names(scope)):
            entry = self._entry(scope, name, public)
            if entry is not None:
                names[name] = entry
        return names

    def _entry(self, scope, name, public):
        bindings = scope.bindings_by_name.get(name, [])
        defining = [b for b in bindings if b.kind not in BINDING_KINDS_REFERENCE]
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
                assert kind in BINDING_KINDS_TYPE_ONLY, kind
                return None
            referenced = []
            for binding in bindings:
                if binding.kind in BINDING_KINDS_REFERENCE:
                    referenced += self._resolve_reference(scope, name, binding)
            reference_in_other_version = self._reference(
                scope, name, _unique_definitions(referenced)
            )
            if (
                reference_in_other_version is not None
                and reference_in_other_version["k"] == "r"
            ):
                entry["also"] = reference_in_other_version["to"]
        else:
            if bindings:
                found = self.resolve_bindings(scope, name)
            else:
                found = self.resolve(scope.module, name)
            entry = self._method_of_module_instance(scope, bindings) or self._reference(
                scope, name, found
            )
        return entry

    def _method_of_module_instance(self, scope, bindings):
        for binding in bindings:
            value = binding.node.value if binding.kind == "assign" else None
            if not isinstance(value, ast.Attribute):
                continue
            for base in self.resolve_expression(scope, value.value):
                if base.kind != "var":
                    continue
                types = [self._var_type(base.scope, b) for b in base.bindings]
                for cls in _class_paths(_union(types)):
                    method = self._method_found_on_class(cls, value.attr)
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

    def _method_found_on_class(self, cls, name):
        for owner in self.ancestors_depth_first(cls):
            found = self.class_definition(owner)
            if found is None:
                continue
            for binding in found.bindings:
                if name in binding.scope.bindings_by_name:
                    definitions = self.resolve_bindings(binding.scope, name)
                    return next((d for d in definitions if d.kind == "func"), None)
        return None

    def _var_type(self, scope, binding):
        node = binding.node
        reduced = self.reduced_type(scope, node.annotation)
        if reduced is None and isinstance(node.value, ast.Constant):
            return self._literal_type(scope, node.value)
        return reduced

    def _reference(self, scope, name, definitions):
        targets = []
        for found in definitions:
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
            kinds = [self._decorator_kind(scope, d) for d in node.decorator_list]
            if "setter" in kinds or "deleter" in kinds:
                setter = setter or "setter" in kinds
                continue
            abstract = abstract or "abstract" in kinds
            for kind in ("property", "classmethod", "staticmethod"):
                if kind in kinds:
                    decorator = kind
            signature = {
                "p": self._parameters(scope, node.args),
                "r": self.reduced_type(scope, node.returns),
            }
            if isinstance(node, ast.AsyncFunctionDef):
                signature["a"] = 1
            if signature not in signatures:
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

    def _decorator_kind(self, scope, node):
        target = node.func if isinstance(node, ast.Call) else node
        if isinstance(target, ast.Attribute) and target.attr in ("setter", "deleter"):
            return target.attr
        for found in self.resolve_expression(scope, target):
            if found.kind == "assign":
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
        positional_only_count = len(arguments.posonlyargs)
        if not positional_only_count:
            names = [arg.arg for arg in arguments.args]
            start = 0
            if names and not _positional_only_before_pep_570(names[0]):
                start = 1
            end = start
            while end < len(names) and _positional_only_before_pep_570(names[end]):
                end += 1
            if end > start:
                positional_only_count = end
        result = []
        for index, (arg, default) in enumerate(zip(positional, defaults)):
            kind = "/" if index < positional_only_count else ""
            result.append(self._parameter(scope, arg, kind, default is not None))
        if arguments.vararg is not None:
            result.append(self._parameter(scope, arguments.vararg, "*", False))
        for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
            result.append(self._parameter(scope, arg, "k", default is not None))
        if arguments.kwarg is not None:
            result.append(self._parameter(scope, arguments.kwarg, "**", False))
        return result

    def _parameter(self, scope, arg, kind, default):
        reduced = self.reduced_type(scope, arg.annotation) if arg.annotation else None
        return [arg.arg, kind, int(default), reduced]

    def _class(self, scope, name, bindings, public):
        found = Definition("class", scope.module, scope.qualify(name), bindings, scope)
        bases, protocol = self.bases_and_protocol(found)
        inner = Scope(scope.module, found.qualname, scope)
        for binding in bindings:
            for member, member_bindings in binding.scope.bindings_by_name.items():
                for member_binding in member_bindings:
                    inner.add(member, member_binding)
        entry = {"k": "c", "b": bases, "m": self._names(inner, public)}
        if protocol:
            entry["proto"] = 1
        decorators = [
            self._decorator_kind(scope, d)
            for b in bindings
            for d in b.node.decorator_list
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
                entry["meta"] = self.reduced_type(scope, keyword.value)
        path = public.get(found.path, found.path)
        if path != found.path:
            entry["pub"] = path
        return entry

    def _type_parameters(self, scope, node):
        parameters_of_generic_base, parameters_in_order_of_appearance = None, []
        for base in node.bases:
            if not isinstance(base, ast.Subscript):
                continue
            names = []
            for item in ast.walk(base.slice):
                if isinstance(item, (ast.Name, ast.Attribute)):
                    for found in self.resolve_expression(scope, item):
                        if found.kind == "typevar" and found.path not in names:
                            names.append(found.path)
            special_forms = [
                _special_form_name(d)
                for d in self.resolve_expression(scope, base.value)
            ]
            if "Generic" in special_forms or "Protocol" in special_forms:
                parameters_of_generic_base = names
            parameters_in_order_of_appearance.extend(
                n for n in names if n not in parameters_in_order_of_appearance
            )
        for parameter in getattr(node, "type_params", ()):
            parameters_in_order_of_appearance.append(f"{scope.module}.{parameter.name}")
        if parameters_of_generic_base is not None:
            return parameters_of_generic_base
        return parameters_in_order_of_appearance

    def _public_class_names(self):
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
                    distribution_of_path = self.distribution_by_module.get(module)
                    distribution_of_class = self.distribution_by_module.get(
                        found.module
                    )
                    if distribution_of_path != distribution_of_class:
                        continue
                    path = f"{module}.{name}"
                    rank = (path.count("."), module != found.module, path)
                    if found.path not in paths or rank < paths[found.path][0]:
                        paths[found.path] = (rank, path)
        public = {key: path for key, (_, path) in paths.items()}
        self._add_extension_class_names(public)
        for module in sorted(self.sources):
            self._add_nested_class_public_names(self.scope(module), public)
        return public

    def _add_extension_class_names(self, public):
        self.extension_name_conflicts = []
        if not self.cpython_libraries:
            return
        for module in sorted(self.sources):
            if self.distribution_by_module.get(module) is not None:
                continue
            scope = self.scope(module)
            for name in sorted(scope.bindings_by_name):
                bindings = scope.bindings_by_name[name]
                if not any(binding.kind == "class" for binding in bindings):
                    continue
                path = f"{module}.{name}"
                named = public.get(path, path)
                if not self._names_no_public_path(named):
                    continue
                named_module, _, named_attribute = named.rpartition(".")
                binding_by_version = {}
                for library in self.cpython_libraries:
                    binding = final_binding(library, named_module, named_attribute)
                    if binding is not None:
                        binding_by_version[library.version] = binding
                found = set(binding_by_version.values())
                if (
                    found
                    and BINDING_NOT_FROM_EXTENSION not in found
                    and len(found) == 1
                ):
                    public[path] = found.pop()
                elif found - {BINDING_NOT_FROM_EXTENSION}:
                    versions = ", ".join(
                        f"{version}: {binding}"
                        for version, binding in binding_by_version.items()
                    )
                    self.extension_name_conflicts.append(f"{named} ({versions})")

    def _names_no_public_path(self, named):
        module, _, attribute = named.rpartition(".")
        if module not in self.sources:
            return False
        if any(part.startswith("_") for part in module.split(".")):
            return False
        if attribute.startswith("_"):
            return True
        all_names = self.scope(module).all_names
        return all_names is not None and attribute not in all_names

    def _add_nested_class_public_names(self, scope, public):
        for name, bindings in scope.bindings_by_name.items():
            for binding in bindings:
                if binding.kind != "class":
                    continue
                path = f"{scope.module}.{scope.qualify(name)}"
                if scope.parent is not None and path not in public:
                    outer = f"{scope.module}.{scope.qualname}"
                    public[path] = f"{public.get(outer, outer)}.{name}"
                self._add_nested_class_public_names(binding.scope, public)


def _binding_kept(binding):
    return binding.kind not in ("from", "module") or binding.reexport


def _class_paths(reduced):
    match reduced:
        case ["|", *arms]:
            return [name for arm in arms for name in _class_paths(arm)]
        case [str() as cls, *_] if not cls.startswith("*"):
            return [cls]
        case str() if not reduced.startswith("*"):
            return [reduced]
    return []


def _positional_only_before_pep_570(name):
    return name.startswith("__") and not name.endswith("__")


def _special_form_name(found):
    if found.module in TYPING_MODULES and found.qualname in SPECIAL_FORMS:
        return found.qualname
    if found.key == ("builtins", "type"):
        return "Type"
    return None


def _union(arms):
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


def _string_constants(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string_constants(node.left) + _string_constants(node.right)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [
            e.value
            for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
    return []


def _absolute_module_name(module, package, target, level):
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
    sys.exit(main())
