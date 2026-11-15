"""Find the modules of a program, build their constraints and solve them.

Discovery starts from the entry points and follows imports that resolve to
files under the package root. Each module is read, parsed and built once; a
module that cannot be read or parsed has failed, and is analysed as an empty
module. The stub `x.pyi` beside a module file `x.py` is read for the
annotations that the source leaves out (see annotations.py); one that cannot
be read or parsed is ignored. An import that finds an extension module under
the root (a binary file, see `ImportManager`) makes an outside module of that
name. When all modules are built, the cross-module facts that need every
module (submodules and extension modules as attributes of their packages,
star imports) are added and the solver runs.
"""

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
    """A module under the package root that was analysed: its name, its
    file, its number of lines (0 if it failed), its status and the cause
    of a status other than "analysed" (see `_cause`): "failed" if its file
    could not be read or parsed, "partial" if its build stopped early."""

    __slots__ = ("name", "file", "line_count", "status", "cause")

    def __init__(self, name, file, line_count, cause=None):
        self.name = name
        self.file = file
        self.line_count = line_count
        self.status = "analysed" if cause is None else "failed"
        self.cause = cause


class Program:
    """The analysis of the program reachable from `entry_points`.

    Module names are dotted paths relative to the package root: `package` if
    given, else the deepest directory that contains every entry point. `cap`
    is the most objects that a node holds before it saturates (None for no
    cap, see solver.py).
    """

    def __init__(self, entry_points, package, cap):
        entry_points = [os.path.abspath(path) for path in entry_points]
        if package:
            self.root = os.path.abspath(package)
        else:
            self.root = _common_directory(entry_points)
        self.entry_points = entry_points
        self.analysis = Analysis(cap)
        # Analysed modules by name, in the order they were built.
        self.modules = {}
        # The extension modules that imports found, by name, with their
        # files (see `ImportManager`).
        self.extension_modules = {}
        self._imports = ImportManager()
        self._imports.set_pkg(self.root)
        # The names of the entry modules.
        self._entry_names = set()
        # By module name, the files that entry points give and that no
        # import finds (`a.pyw`, a script without a suffix), by name.
        self._entry_files = {}
        self._star_imports = {}
        self._exports = {}
        self._declares_all = set()

    def analyse(self):
        # The entry points by module name. Of the files of one name, the
        # analysis uses the first of `module_files`, whatever the order of
        # the entry points.
        named = {}
        for path in self.entry_points:
            name = self._module_name(path)
            if name:
                named.setdefault(name, set()).add(path)
        queue = deque()
        for name, paths in named.items():
            self._entry_names.add(name)
            found = self._imports.module_files(name)
            others = sorted(paths - set(found), key=self._relative)
            self._entry_files[name] = others
            first = (found + others)[0]
            if extension_name(os.path.basename(first)):
                self._imports.extension_modules[name] = first
            else:
                queue.append((name, first))

        # Star imports whose listed submodules are not imported yet.
        pending_stars = []
        while queue:
            name, path = queue.popleft()
            if name in self.modules:
                continue
            self._build(name, path)
            pending_stars.extend(
                (name, holder) for holder in self._star_imports.get(name, ())
            )
            importers = [name] + self._import_listed_submodules(pending_stars)
            for importer in importers:
                for imported in sorted(self._imports.get_imports(importer)):
                    imported_path = self._imports.get_filepath(imported)
                    # Namespace packages have no file.
                    if imported_path and imported not in self.modules:
                        queue.append((imported, imported_path))

        self.extension_modules = dict(sorted(self._imports.extension_modules.items()))
        self._link_submodules()
        self._link_star_imports()
        self.analysis.solve()

    def shadowed(self, name, file):
        """The other files under the root that hold the module `name`,
        whose file is `file`: the analysis does not use them. The files of a
        name are those that an import finds, in the order of
        `ImportManager.module_files`, then those that only entry points
        give, by name."""
        files = self._imports.module_files(name) + self._entry_files.get(name, [])
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
        # The module of a package's __init__.py is the package. The root is
        # not a package, so its __init__.py has no name.
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
        is_entry = name in self._entry_names
        builder = ModuleBuilder(
            self.analysis,
            self._imports,
            module,
            tree,
            is_package,
            is_entry,
            _own_stub(path),
        )
        try:
            builder.build()
        except RecursionError as error:
            logger.warning(
                "%s: code is nested too deeply; its analysis is incomplete", path
            )
            # What the build made before it stopped is kept.
            self.modules[name].status = "partial"
            self.modules[name].cause = _cause(error)
        self._star_imports[name] = builder.star_imports
        declared = _declared_all(tree)
        if declared is None:
            public = [n for n in builder.defined if not n.startswith("_")]
            self._exports[name] = dict.fromkeys(public)
        else:
            self._exports[name] = dict.fromkeys(declared)
            self._declares_all.add(name)

    def _import_listed_submodules(self, pending_stars):
        """Import the submodules that star imports bring in.

        `from pkg import *` imports each name in `pkg.__all__` that is a
        submodule of `pkg`. That needs `pkg` built, so a star import waits in
        `pending_stars` until it is. Return the importers that may now import
        more modules.
        """
        importers = []
        for star in list(pending_stars):
            importer, holder = star
            if holder not in self.modules:
                continue
            pending_stars.remove(star)
            if holder not in self._declares_all:
                continue
            self._imports.set_current_mod(importer, self.modules[importer].file)
            for name in self._exports[holder]:
                self._imports.handle_import(f"{holder}.{name}", 0)
            importers.append(importer)
        return importers

    def _link_submodules(self):
        """Make each module an attribute of its package, as importing it
        does. A package without `__all__` then exports its public
        submodules, as it does its other public names. An extension module
        is the outside module of its name. The packages of an entry module,
        which no import names, are attributes of theirs too, as far as an
        import resolves them as packages (`ImportManager.packages`: a
        module `ns.py` wins over a namespace directory `ns/`); their source
        is not analysed for it."""
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
                if public and package not in self._declares_all:
                    self._exports.setdefault(package, {})[attribute] = None

    def _link_star_imports(self):
        """Copy the exported globals of each star-imported module into the
        importing module.

        A module without `__all__` also exports what its own star imports
        brought in, so the exports are completed transitively first.
        """
        changed = True
        while changed:
            changed = False
            for importer, holders in self._star_imports.items():
                if importer in self._declares_all:
                    continue
                exports = self._exports[importer]
                for holder in holders:
                    for name in list(self._exports.get(holder, ())):
                        if name not in exports:
                            exports[name] = None
                            changed = True

        for importer, holders in self._star_imports.items():
            importer_module = self.analysis.module(importer)
            for holder in holders:
                holder_module = self.analysis.module(holder)
                for name in self._exports.get(holder, ()):
                    importer_module.defines.add(name)
                    self.analysis.add_edge(
                        self.analysis.field(holder_module, name),
                        self.analysis.field(importer_module, name),
                    )


def _common_directory(paths):
    if not paths:
        return os.path.abspath(os.curdir)
    return os.path.commonpath([os.path.dirname(path) for path in paths])


def _own_stub(path):
    """The tree of the stub of the module file `path`: `x.pyi` in the same
    directory as `x.py`. None if there is none, if it cannot be read or
    parsed, or if it has a `global` or `nonlocal` statement, whose scopes
    the stub reader does not model: it is then ignored."""
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
    """Read a source file in the encoding it declares: (source, None), or
    (None, the cause of the failure)."""
    try:
        with tokenize.open(path) as file:
            return file.read(), None
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        logger.warning("Skipping %s: cannot read it: %s", path, error)
        return None, _cause(error)


def _parse(source, path):
    """(tree, None), or (None, the cause of the failure)."""
    try:
        # Warnings about the analysed code (invalid escape sequences, for
        # example) are not the analysis' concern.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ast.parse(source, path), None
    except (SyntaxError, ValueError, RecursionError) as error:
        logger.warning("Skipping %s: cannot parse it: %s", path, error)
        return None, _cause(error)


def _line_count(source):
    """The number of lines of `source` as Python numbers them: the file was
    read with universal newlines, and only a newline ends a line (a form
    feed does not, though `str.splitlines` breaks there)."""
    if not source:
        return 0
    return source.count("\n") + (not source.endswith("\n"))


def _cause(error):
    """Why a file could not be read or parsed: the type of the error, with
    its line or byte where Python gives one. Not the message, which changes
    between versions of Python, nor a path."""
    cause = type(error).__name__
    if isinstance(error, SyntaxError) and error.lineno:
        return f"{cause} (line {error.lineno})"
    if isinstance(error, UnicodeDecodeError):
        return f"{cause} (byte {error.start})"
    return cause


def _declared_all(tree):
    """The names in `__all__`, or None if the module does not declare them
    in a form the analysis reads; star imports then take the public names.

    The form is: every top-level statement that mentions `__all__` assigns
    it one literal list or tuple of strings, and the last one counts.
    Anything else, such as a name in the list, `+` or
    `__all__.extend(...)`, does not count.
    """
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
