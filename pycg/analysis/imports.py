#
# Copyright (c) 2026 Vitalis Salis.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import os


class ImportManager(object):
    """Resolves imports to modules under the package root.

    Module names are dotted paths relative to the package root (`mod_dir`).
    Resolution reads only the filesystem: it never imports or executes code
    and never reads or changes `sys.path` or `sys.modules`.

    The import graph maps each module under the root to its file and to the
    modules under the root that it imports. An import may also find an
    extension module, a binary file (see `_extension`): it is outside code,
    named by its dotted name, and `extension_modules` maps it to its file.
    """

    def __init__(self):
        self.import_graph = dict()
        self.extension_modules = {}
        self.current_module = ""
        self.input_file = ""
        self.mod_dir = None
        # The names in each directory read so far: every import of a module
        # looks in the directories of its packages, and the files are those
        # of one analysis.
        self._listings = {}

    def set_pkg(self, input_pkg):
        self.mod_dir = os.path.abspath(input_pkg)

    def get_mod_dir(self):
        return self.mod_dir

    def is_internal(self, filename):
        """Return True if `filename` is inside the package root."""
        path = os.path.abspath(filename)
        return os.path.commonpath([self.mod_dir, path]) == self.mod_dir

    def get_node(self, name):
        if name in self.import_graph:
            return self.import_graph[name]

    def create_node(self, name):
        if not name or not isinstance(name, str):
            raise ImportManagerError("Invalid node name")

        if self.get_node(name):
            raise ImportManagerError("Can't create a node a second time")

        self.import_graph[name] = {"filename": "", "imports": set()}
        return self.import_graph[name]

    def create_edge(self, dest):
        if not dest or not isinstance(dest, str):
            raise ImportManagerError("Invalid node name")

        node = self.get_node(self.current_module)
        if not node:
            raise ImportManagerError("Can't add edge to a non existing node")

        node["imports"].add(dest)

    def set_current_mod(self, name, fname):
        self.current_module = name
        self.input_file = os.path.abspath(fname)

    def get_filepath(self, modname):
        if modname in self.import_graph:
            return self.import_graph[modname]["filename"]

    def set_filepath(self, node_name, filename):
        if not filename or not isinstance(filename, str):
            raise ImportManagerError("Invalid node name")

        node = self.get_node(node_name)
        if not node:
            raise ImportManagerError("Node does not exist")

        node["filename"] = os.path.abspath(filename)

    def get_imports(self, modname):
        if modname not in self.import_graph:
            return []
        return self.import_graph[modname]["imports"]

    def get_import_graph(self):
        return self.import_graph

    def handle_import(self, name, level, record=True):
        """Resolve the import of `name` with relative `level` from the current
        module.

        `name` is the imported module for `import a.b` and the module joined
        with the imported name for `from a import b` ("a.b"). If no module
        "a.b" exists, "b" is taken to be an attribute of module "a".

        Return the name of the imported module if it is under the package
        root, else None. Add the module and every package on its path to the
        import graph, with edges from the current module. The packages are
        added even if the module is missing, because Python runs them before
        the import fails. Without `record` (a lazy import that nothing
        reads), only resolve: the import runs nothing.

        In an absolute import, built-in and frozen modules take precedence
        over any file, as in Python, also for submodules: `importlib` is not
        frozen but `importlib.util` is. Such a module is external.
        """
        base = self._get_base_package(level)
        if base is None:
            return None

        parts = base + name.split(".")
        modules, reached_frozen = self._find_modules(parts, absolute=level == 0)
        for modname, filename in modules if record else ():
            if not self.get_node(modname):
                self.create_node(modname)
                if filename:
                    self.set_filepath(modname, filename)
            if modname != self.current_module:
                self.create_edge(modname)

        if reached_frozen:
            return None
        # Either the whole name is a module, or all but its last part is
        # and the last part is an attribute of that module.
        if modules and len(modules) >= len(parts) - 1:
            return modules[-1][0]
        return None

    def module_files(self, name):
        """The files under the root that hold the module `name`, in the
        order of `_candidates`: the first is the module, the others are
        shadowed. The directories of its packages are taken as they are
        named, whatever holds them."""
        *packages, last = name.split(".")
        return self._candidates(os.path.join(self.mod_dir, *packages), last)

    def locate(self, name):
        """What an absolute import of the dotted `name` would find under the
        package root, without importing it: `(module, None)` if `name` is a
        module, `(module, attribute)` if its last part is an attribute of a
        module, None if neither is under the root. It registers nothing: an
        extension module that it meets is not recorded."""
        parts = name.split(".")
        modules, reached_frozen = self._find_modules(parts, True, record=False)
        if reached_frozen or not modules:
            return None
        if len(modules) == len(parts):
            return modules[-1][0], None
        if len(modules) == len(parts) - 1:
            return modules[-1][0], parts[-1]
        return None

    def packages(self, name):
        """The packages that an absolute import of the dotted `name` passes
        through, from the top-level one, as `_find_modules` resolves them:
        each prefix of `name` (not `name` itself) that is a regular or a
        namespace package, up to the first that is not (a module, a
        built-in or frozen module, nothing). A regular package's file is
        the `__init__.py` in its own directory: the module `pkg/__init__.py`
        that `pkg.__init__` names is no package. It registers nothing."""
        parts = name.split(".")[:-1]
        found, _ = self._find_modules(parts, True, record=False)
        packages = []
        for package, filename in found:
            directory = os.path.join(self.mod_dir, *package.split("."))
            initializer = os.path.join(directory, "__init__.py")
            if filename is not None and filename != initializer:
                break
            packages.append(package)
        return packages

    def _get_base_package(self, level):
        """Return the package that a relative import of `level` starts from,
        as a list of name parts.

        Return [] for an absolute import and None if the import goes beyond
        the top-level package. The package root itself is not a package.
        """
        if level == 0:
            return []

        package = self.current_module.split(".")
        # The module name of an __init__.py file is the name of its package.
        if os.path.basename(self.input_file) != "__init__.py":
            package = package[:-1]

        if level > len(package):
            return None

        return package[: len(package) - level + 1]

    def _find_modules(self, parts, absolute, record=True):
        """Find the modules on the path `parts` (a list of name parts).

        Return a list with a (name, filename) pair for each module of the
        longest prefix of `parts` that exists under the root: the first
        element is the top-level package, the last is the deepest module
        found. The filename is None for a namespace package. Within a
        directory the files of a name decide by `_candidates`: a package
        with __init__.py, then a module file, then an extension module, which
        ends the search; with none, a namespace package.

        For an `absolute` import, the search also stops at a prefix that is a
        built-in or frozen module; the second element of the result tells
        whether it did. With `record`, an extension module that the search
        meets becomes one of the program's (`extension_modules`).
        """
        found = []
        directory = self.mod_dir
        for index, part in enumerate(parts):
            # `*` from `from a import *` is never a module.
            if not part.isidentifier():
                break

            name = ".".join(parts[: index + 1])
            if absolute and _is_builtin_or_frozen(name):
                return found, True
            path = os.path.join(directory, part)
            files = self._candidates(directory, part)
            if files and os.path.basename(files[0]) == "__init__.py":
                found.append((name, files[0]))
            elif files and files[0].endswith(".py"):
                found.append((name, files[0]))
                # A plain module has no submodules.
                break
            elif files:
                if record:
                    self.extension_modules[name] = files[0]
                break
            elif part in self._list_dir(directory) and os.path.isdir(path):
                found.append((name, None))
            else:
                break
            directory = path

        return found, False

    def _candidates(self, directory, part):
        """The files in `directory` that hold the module `part`, in the order
        that decides which one is the module, the one rule for imports and
        entry points: its package (`part/__init__.py`), its module file
        (`part.py`), its extension binaries by name (see `extension_name`).
        The first is the module and the others are shadowed: whatever the
        order in which they are reached, the analysis uses the first. Python
        tries a binary before a module file; PyCG analyses the source. Names
        are compared with directory listings, so the match is case sensitive
        also on case-insensitive filesystems, and a directory named like a
        file is not that file. Only file names are read."""
        entries = self._list_dir(directory)
        path = os.path.join(directory, part)
        found = []
        init_file = os.path.join(path, "__init__.py")
        if part in entries and "__init__.py" in self._list_dir(path):
            if os.path.isfile(init_file):
                found.append(init_file)
        if part + ".py" in entries and os.path.isfile(path + ".py"):
            found.append(path + ".py")
        for entry in sorted(entry for entry in entries if entry.startswith(part + ".")):
            if extension_name(entry) == part:
                if os.path.isfile(os.path.join(directory, entry)):
                    found.append(os.path.join(directory, entry))
        return found

    def _list_dir(self, path):
        entries = self._listings.get(path)
        if entries is None:
            try:
                entries = frozenset(os.listdir(path))
            except OSError:
                entries = frozenset()
            self._listings[path] = entries
        return entries


# The modules that are builtin or frozen in every supported Python, 3.12 to
# 3.15: the intersection of `sys.builtin_module_names` and
# `_imp._frozen_module_names()` over those versions (and over static and
# shared builds), computed once. Python imports these before any file on
# the path, so an analysed module of the same name is never imported by an
# absolute import. A constant, so that the result does not depend on the
# Python that runs the analysis.
BUILTIN_OR_FROZEN = frozenset(
    {
        "__hello__",
        "__hello_alias__",
        "__hello_only__",
        "__phello__",
        "__phello__.__init__",
        "__phello__.ham",
        "__phello__.ham.__init__",
        "__phello__.ham.eggs",
        "__phello__.spam",
        "__phello_alias__",
        "__phello_alias__.spam",
        "_abc",
        "_ast",
        "_asyncio",
        "_codecs",
        "_collections",
        "_collections_abc",
        "_contextvars",
        "_datetime",
        "_frozen_importlib",
        "_frozen_importlib_external",
        "_functools",
        "_imp",
        "_io",
        "_locale",
        "_opcode",
        "_operator",
        "_signal",
        "_sitebuiltins",
        "_sre",
        "_stat",
        "_string",
        "_symtable",
        "_thread",
        "_tokenize",
        "_tracemalloc",
        "_typing",
        "_warnings",
        "_weakref",
        "abc",
        "atexit",
        "builtins",
        "codecs",
        "errno",
        "faulthandler",
        "gc",
        "genericpath",
        "importlib.machinery",
        "importlib.util",
        "io",
        "itertools",
        "marshal",
        "ntpath",
        "os",
        "posix",
        "posixpath",
        "pwd",
        "runpy",
        "site",
        "stat",
        "sys",
        "time",
        "zipimport",
    }
)


def _is_builtin_or_frozen(name):
    return name in BUILTIN_OR_FROZEN


def extension_name(filename):
    """The module name of the extension binary `filename`, or None:
    `name.so` or `name.pyd`, or with a tag before the suffix
    (`name.cpython-312-darwin.so`, `name.abi3.so`,
    `name.cp312-win_amd64.pyd`)."""
    stem, dot, suffix = filename.rpartition(".")
    name, _, tag = stem.partition(".")
    if dot and suffix in ("so", "pyd") and name and "." not in tag:
        return name
    return None


class ImportManagerError(Exception):
    pass
