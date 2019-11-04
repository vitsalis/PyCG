# TODO
# 1) stdlib
# 2) Modifications to to sys.path inside the analyzed module
# 3) Handle PYTHONPATH env variable
# 4) Usage of the `site` module
# 5) `from smth import *` uses the `__all__.py` module of the file
# 6) importlib dynamic imports
# 7) `*.pth` files

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
    def __init__(self, input_file):
        self.import_graph = dict()
        self.current_module = ""
        self.input_file = os.path.abspath(input_file)
        self.mod_dir = os.path.dirname(self.input_file)
        self.old_path_hooks = None
        self.old_path = None

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

    def set_current_mod(self, name):
        self.current_module = name

    def get_filepath(self, modname):
        return self.import_graph[modname]["filename"]

    def set_filepath(self, node_name, filename):
        if not filename or not isinstance(filename, str):
            raise ImportManagerError("Invalid node name")

        node = self.get_node(node_name)
        if not node:
            raise ImportManagerError("Node does not exist")

        node["filename"] = filename

    def get_imports(self, modname):
        return self.import_graph[modname]["imports"]

    def _handle_import_level(self, name, level):
        # add a dot for each level
        package = self._get_module_path().split(".")
        if level > len(package):
            raise ImportError("Attempting import beyond top level package")

        mod_name = ("." * level) + name
        package = ".".join(package[:-level])
        return mod_name, package

    def handle_import(self, name, level):

        # We currently don't support builtin modules because they're frozen.
        # Add an edge and continue.
        # TODO: identify a way to include frozen modules
        root = name.split(".")[0]
        if root in sys.builtin_module_names:
            self.create_edge(root)
            return

        # Import the module
        mod_name, package = self._handle_import_level(name, level)
        try:
            mod = importlib.import_module(mod_name, package=package)
        except ImportError as e:
            # try the parent
            mod_name = ".".join(mod_name.split(".")[:-1])
            mod = importlib.import_module(mod_name, package=package)

        return utils.to_mod_name(
            os.path.relpath(mod.__file__, self.mod_dir))

    def get_import_graph(self):
        return self.import_graph

    def install_hooks(self):
        loader = get_custom_loader(self)
        self.old_path_hooks = copy.deepcopy(sys.path_hooks)
        self.old_path = copy.deepcopy(sys.path)

        loader_details = loader, importlib.machinery.all_suffixes()
        sys.path_hooks.insert(0, importlib.machinery.FileFinder.path_hook(loader_details))
        sys.path.insert(0, self.mod_dir)

        self._clear_caches()

    def remove_hooks(self):
        sys.path_hooks = self.old_path_hooks
        sys.path = self.old_path

        self._clear_caches()

class ImportManagerError(Exception):
    pass
