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
import sys
import ast
import os
import importlib
import copy

from pycg import utils

def get_custom_loader(ig_obj):
    """
    Closure which returns a custom loader
    that modifies an ImportManager object
    """
    class CustomLoader(importlib.abc.SourceLoader):
        def __init__(self, fullname, path):
            self.fullname = fullname
            self.path = path

            ig_obj.create_edge(self.fullname)
            if not ig_obj.get_node(self.fullname):
                ig_obj.create_node(self.fullname)
                ig_obj.set_filepath(self.fullname, self.path)

        def get_filename(self, fullname):
            return self.path

        def get_data(self, filename):
            return ""

    return CustomLoader

class ImportManager(object):
    def __init__(self):
        self.import_graph = dict()
        self.current_module = ""
        self.input_file = ""
        self.mod_dir = None
        self.old_path_hooks = None
        self.old_path = None

    def set_pkg(self, input_pkg):
        self.mod_dir = input_pkg

    def get_mod_dir(self):
        return self.mod_dir

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

        node = self.get_node(self._get_module_path())
        if not node:
            raise ImportManagerError("Can't add edge to a non existing node")

        node["imports"].add(dest)


    def _clear_caches(self):
        importlib.invalidate_caches()
        sys.path_importer_cache.clear()
        # TODO: maybe not do that since it empties the whole cache
        for name in self.import_graph:
            if name in sys.modules:
                del sys.modules[name]

    def _get_module_path(self):
        return self.current_module

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
        if not modname in self.import_graph:
            return []
        return self.import_graph[modname]["imports"]


    def _is_init_file(self):
        return self.input_file.endswith("__init__.py")

    def _handle_import_level(self, name, level):
        # add a dot for each level
        package = self._get_module_path().split(".")
        if level > len(package):
            raise ImportError("Attempting import beyond top level package")

        mod_name = ("." * level) + name
        # When an __init__ file is analyzed, then the module name doesn't contain
        # the __init__ part in it, so special care must be taken for levels.
        if self._is_init_file() and level >= 1:
            if level != 1:
                level -= 1
                package = package[:-level]
        else:
            package = package[:-level]

        return mod_name, ".".join(package)

    def _do_import(self, mod_name, package):
        if mod_name in sys.modules:
            self.create_edge(mod_name)
            return sys.modules[mod_name]

        return importlib.import_module(mod_name, package=package)

    def handle_import(self, name, level):
        # We currently don't support builtin modules because they're frozen.
        # Add an edge and continue.
        # TODO: identify a way to include frozen modules
        root = name.split(".")[0]
        if root in sys.builtin_module_names:
            self.create_edge(root)
            return

        # Import the module
        try:
            mod_name, package = self._handle_import_level(name, level)
        except ImportError:
            return

        parent = ".".join(mod_name.split(".")[:-1])
        parent_name = ".".join(name.split(".")[:-1])
        combos = [(mod_name, package),
                (parent, package),
                (utils.join_ns(package, name), ""),
                (utils.join_ns(package, parent_name), "")]

        mod = None
        for mn, pkg in combos:
            try:
                mod = self._do_import(mn, pkg)
                break
            except:
                continue

        if not mod:
            return

        if not hasattr(mod, "__file__") or not mod.__file__:
            return
        if self.mod_dir not in mod.__file__:
            return
        fname = mod.__file__
        if fname.endswith("__init__.py"):
            fname = os.path.split(fname)[0]

        return utils.to_mod_name(
            os.path.relpath(fname, self.mod_dir))

    def get_import_graph(self):
        return self.import_graph

    def install_hooks(self):
        loader = get_custom_loader(self)
        self.old_path_hooks = copy.deepcopy(sys.path_hooks)
        self.old_path = copy.deepcopy(sys.path)

        loader_details = loader, importlib.machinery.all_suffixes()
        sys.path_hooks.insert(0, importlib.machinery.FileFinder.path_hook(loader_details))
        sys.path.insert(0, os.path.abspath(self.mod_dir))

        self._clear_caches()

    def remove_hooks(self):
        sys.path_hooks = self.old_path_hooks
        sys.path = self.old_path

        self._clear_caches()

class ImportManagerError(Exception):
    pass
