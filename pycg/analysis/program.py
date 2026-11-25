import ast
import logging
import os
import tokenize
import warnings
from collections import deque

from .builder import ModuleBuilder
from .imports import ImportManager, extension_name
from .scopes import literal_assignment, mentions
from .semantics import Analysis

logger = logging.getLogger(__name__)


class SourceModule:
    __slots__ = ("name", "file", "line_count", "status", "cause")

    def __init__(self, name, file, line_count, cause=None):
        self.name = name
        self.file = file
        self.line_count = line_count
        self.status = "analysed" if cause is None else "failed"
        self.cause = cause


class Program:
    def __init__(self, entry_points, package, cap):
        entry_points = [os.path.abspath(path) for path in entry_points]
        if package:
            self.root = os.path.abspath(package)
        else:
            self.root = _common_directory(entry_points)
        self.entry_points = entry_points
        self.analysis = Analysis(cap)
        self.modules = {}
        self.extension_modules = {}
        self._imports = ImportManager()
        self._imports.set_pkg(self.root)
        self._entry_module_names = set()
        self._entry_only_files_by_name = {}
        self._star_imported_modules_by_importer = {}
        self._exports_by_module = {}
        self._modules_declaring_all = set()

    def analyse(self):
        named = {}
        for path in self.entry_points:
            name = self._module_name(path)
            if name:
                named.setdefault(name, set()).add(path)
        queue = deque()
        for name, paths in named.items():
            self._entry_module_names.add(name)
            found = self._imports.module_files(name)
            others = sorted(paths - set(found), key=self._relative)
            self._entry_only_files_by_name[name] = others
            first = (found + others)[0]
            if extension_name(os.path.basename(first)):
                self._imports.extension_modules[name] = first
            else:
                queue.append((name, first))

        pending_stars = []
        while queue:
            name, path = queue.popleft()
            if name in self.modules:
                continue
            self._build(name, path)
            pending_stars.extend(
                (name, holder)
                for holder in self._star_imported_modules_by_importer.get(name, ())
            )
            importers = [name] + self._import_listed_submodules(pending_stars)
            for importer in importers:
                for imported in sorted(self._imports.get_imports(importer)):
                    imported_path = self._imports.get_filepath(imported)
                    if imported_path and imported not in self.modules:
                        queue.append((imported, imported_path))

        self.extension_modules = dict(sorted(self._imports.extension_modules.items()))
        self._link_submodules()
        self._link_star_imports()
        self.analysis.solve()

    def shadowed(self, name, file):
        files = self._imports.module_files(name) + self._entry_only_files_by_name.get(
            name, []
        )
        return [other for other in files if other != file]

    def _relative(self, path):
        return os.path.relpath(path, self.root)

    def _module_name(self, path):
        relative = os.path.relpath(path, self.root)
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            logger.warning(
                "Skipping %s: it is not under the package root %s", path, self.root
            )
            return None
        if relative.endswith(".pyi"):
            logger.warning("Skipping %s: a stub is not source", path)
            return None
        if os.path.isdir(path):
            logger.warning(
                "Skipping %s: a directory is not a module file; give its files", path
            )
            return None
        directory, filename = os.path.split(relative)
        stem = extension_name(filename) or os.path.splitext(filename)[0]
        name = os.path.join(directory, stem).replace(os.sep, ".")
        if name == "__init__":
            logger.warning("Skipping %s: the package root is not a package", path)
            return None
        return name.removesuffix(".__init__")

    def _build(self, name, path):
        if not self._imports.get_node(name):
            self._imports.create_node(name)
            self._imports.set_filepath(name, path)
        self._imports.set_current_mod(name, path)

        source, failure = _read(path)
        tree = None
        if source is not None:
            tree, failure = _parse(source, path)
        lines = _line_count(source) if tree is not None else 0
        self.modules[name] = SourceModule(name, path, lines, failure)
        if tree is None:
            return

        is_package = os.path.basename(path) == "__init__.py"
        module = self.analysis.module(name)
        is_entry = name in self._entry_module_names
        builder = ModuleBuilder(
            self.analysis,
            self._imports,
            module,
            tree,
            is_package,
            is_entry,
            _own_stub_tree(path),
        )
        try:
            builder.build()
        except RecursionError as error:
            logger.warning(
                "%s: code is nested too deeply; its analysis is incomplete", path
            )
            self.modules[name].status = "partial"
            self.modules[name].cause = _cause(error)
        self._star_imported_modules_by_importer[name] = builder.star_imported_modules
        declared = _declared_all_names(tree)
        if declared is None:
            public = [
                n for n in builder.names_bound_at_run_time if not n.startswith("_")
            ]
            self._exports_by_module[name] = dict.fromkeys(public)
        else:
            self._exports_by_module[name] = dict.fromkeys(declared)
            self._modules_declaring_all.add(name)

    def _import_listed_submodules(self, pending_stars):
        importers = []
        for star in list(pending_stars):
            importer, holder = star
            if holder not in self.modules:
                continue
            pending_stars.remove(star)
            if holder not in self._modules_declaring_all:
                continue
            self._imports.set_current_mod(importer, self.modules[importer].file)
            for name in self._exports_by_module[holder]:
                self._imports.handle_import(f"{holder}.{name}", 0)
            importers.append(importer)
        return importers

    def _link_submodules(self):
        names = set(self._imports.get_import_graph())
        for name in list(names):
            names.update(self._imports.packages(name))
        submodules = [(name, self.analysis.module(name)) for name in names]
        submodules += [
            (name, self.analysis.external(name)) for name in self.extension_modules
        ]
        for name, module in sorted(submodules, key=lambda pair: pair[0]):
            package, _, attribute = name.rpartition(".")
            if package:
                holder = self.analysis.module(package)
                holder.defines.add(attribute)
                field = self.analysis.field(holder, attribute)
                self.analysis.add_object(field, module)
                public = not attribute.startswith("_")
                if public and package not in self._modules_declaring_all:
                    self._exports_by_module.setdefault(package, {})[attribute] = None

    def _link_star_imports(self):
        changed = True
        while changed:
            changed = False
            for importer, holders in self._star_imported_modules_by_importer.items():
                if importer in self._modules_declaring_all:
                    continue
                exports = self._exports_by_module[importer]
                for holder in holders:
                    for name in list(self._exports_by_module.get(holder, ())):
                        if name not in exports:
                            exports[name] = None
                            changed = True

        for importer, holders in self._star_imported_modules_by_importer.items():
            importer_module = self.analysis.module(importer)
            for holder in holders:
                holder_module = self.analysis.module(holder)
                for name in self._exports_by_module.get(holder, ()):
                    importer_module.defines.add(name)
                    self.analysis.add_edge(
                        self.analysis.field(holder_module, name),
                        self.analysis.field(importer_module, name),
                    )


def _common_directory(paths):
    if not paths:
        return os.path.abspath(os.curdir)
    return os.path.commonpath([os.path.dirname(path) for path in paths])


def _own_stub_tree(path):
    base, suffix = os.path.splitext(path)
    stub = base + ".pyi"
    if suffix != ".py" or not os.path.isfile(stub):
        return None
    source, _ = _read(stub)
    if source is None:
        return None
    tree = _parse(source, stub)[0]
    if tree is None:
        return None
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        return None
    return tree


def _read(path):
    try:
        with tokenize.open(path) as file:
            return file.read(), None
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        logger.warning("Skipping %s: cannot read it: %s", path, error)
        return None, _cause(error)


def _parse(source, path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ast.parse(source, path), None
    except (SyntaxError, ValueError, RecursionError) as error:
        logger.warning("Skipping %s: cannot parse it: %s", path, error)
        return None, _cause(error)


def _line_count(source):
    if not source:
        return 0
    return source.count("\n") + (not source.endswith("\n"))


def _cause(error):
    cause = type(error).__name__
    if isinstance(error, SyntaxError) and error.lineno:
        return f"{cause} (line {error.lineno})"
    if isinstance(error, UnicodeDecodeError):
        return f"{cause} (byte {error.start})"
    return cause


def _declared_all_names(tree):
    names = None
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not mentions(statement, "__all__"):
            continue
        names = literal_assignment(statement, "__all__")
        if names is None:
            return None
    return names
