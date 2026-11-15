#
# Copyright (c) 2020 Vitalis Salis.
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
import sys
from importlib.machinery import FrozenImporter


class ImportManager(object):
    """Resolves imports to modules under the package root.

    Module names are dotted paths relative to the package root (`mod_dir`).
    Resolution reads only the filesystem: it never imports or executes code
    and never reads or changes `sys.path` or `sys.modules`.

    The import graph maps each module under the root to its file and to the
    modules under the root that it imports.
    """

    def __init__(self):
        self.import_graph = dict()
        self.current_module = ""
        self.input_file = ""
        self.mod_dir = None

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

    def handle_import(self, name, level):
        """Resolve the import of `name` with relative `level` from the current
        module.

        `name` is the imported module for `import a.b` and the module joined
        with the imported name for `from a import b` ("a.b"). If no module
        "a.b" exists, "b" is taken to be an attribute of module "a".

        Return the name of the imported module if it is under the package
        root, else None. Add the module and every package on its path to the
        import graph, with edges from the current module. The packages are
        added even if the module is missing, because Python runs them before
        the import fails.
        """
        # Built-in and frozen modules take precedence over any file, as in
        # Python.
        if level == 0 and _is_builtin_or_frozen(name.split(".")[0]):
            return None

        base = self._get_base_package(level)
        if base is None:
            return None

        parts = base + name.split(".")
        modules = self._find_modules(parts)
        for modname, filename in modules:
            if not self.get_node(modname):
                self.create_node(modname)
                if filename:
                    self.set_filepath(modname, filename)
            if modname != self.current_module:
                self.create_edge(modname)

        # Either the whole name is a module, or all but its last part is
        # and the last part is an attribute of that module.
        if modules and len(modules) >= len(parts) - 1:
            return modules[-1][0]
        return None

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

    def _find_modules(self, parts):
        """Find the modules on the path `parts` (a list of name parts).

        Return a (name, filename) pair for each module of the longest prefix
        of `parts` that exists under the root: the first element is the
        top-level package, the last is the deepest module found. The filename
        is None for a namespace package. Within a directory a package with
        __init__.py comes first, then a module file, then a namespace
        package, as in Python.
        """
        found = []
        directory = self.mod_dir
        for index, part in enumerate(parts):
            # `*` from `from a import *` is never a module.
            if not part.isidentifier():
                break

            name = ".".join(parts[: index + 1])
            path = os.path.join(directory, part)
            init_file = os.path.join(path, "__init__.py")
            # Compare against directory listings so that the match is case
            # sensitive also on case-insensitive filesystems. A directory
            # named like a source file is not a source file.
            entries = _list_dir(directory)
            if (
                part in entries
                and "__init__.py" in _list_dir(path)
                and os.path.isfile(init_file)
            ):
                found.append((name, init_file))
            elif part + ".py" in entries and os.path.isfile(path + ".py"):
                found.append((name, path + ".py"))
                # A plain module has no submodules.
                break
            elif part in entries and os.path.isdir(path):
                found.append((name, None))
            else:
                break
            directory = path

        return found


def _is_builtin_or_frozen(name):
    # FrozenImporter.find_spec only looks the name up in the interpreter's
    # table of frozen modules (io, os, ...). It imports nothing.
    return (
        name in sys.builtin_module_names or FrozenImporter.find_spec(name) is not None
    )


def _list_dir(path):
    try:
        return set(os.listdir(path))
    except OSError:
        return set()


class ImportManagerError(Exception):
    pass
