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
    def __init__(self):
        self.import_graph = dict()
        self.extension_modules = {}
        self.current_module = ""
        self.input_file = ""
        self.mod_dir = None
        self._directory_entries_by_path = {}

    def set_pkg(self, input_pkg):
        self.mod_dir = os.path.abspath(input_pkg)

    def get_mod_dir(self):
        return self.mod_dir

    def is_internal(self, filename):
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
        assert modname in self.import_graph, modname
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
        if modules and len(modules) >= len(parts) - 1:
            return modules[-1][0]
        return None

    def module_files(self, name):
        *packages, last = name.split(".")
        return self._candidates(os.path.join(self.mod_dir, *packages), last)

    def locate(self, name):
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
        if level == 0:
            return []

        package = self.current_module.split(".")
        if os.path.basename(self.input_file) != "__init__.py":
            package = package[:-1]

        if level > len(package):
            return None

        return package[: len(package) - level + 1]

    def _find_modules(self, parts, absolute, record=True):
        found = []
        directory = self.mod_dir
        for index, part in enumerate(parts):
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
        entries = self._directory_entries_by_path.get(path)
        if entries is None:
            try:
                entries = frozenset(os.listdir(path))
            except OSError:
                entries = frozenset()
            self._directory_entries_by_path[path] = entries
        return entries


BUILTIN_OR_FROZEN_MODULES = frozenset(
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
    return name in BUILTIN_OR_FROZEN_MODULES


def extension_name(filename):
    stem, dot, suffix = filename.rpartition(".")
    name, _, tag = stem.partition(".")
    if dot and suffix in ("so", "pyd") and name and "." not in tag:
        return name
    return None


class ImportManagerError(Exception):
    pass
