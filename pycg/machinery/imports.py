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
            ig_obj.add_edge(self.fullname)
            ig_obj.add_node(self.fullname, self.path)

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
        self.mod_dir = os.path.dirname(input_file)
        self.old_path_hooks = None
        self.old_path = None

    def _get_node(self, name):
        if not name in self.import_graph:
            return None
        return self.import_graph[name]

    def _create_node(self, name):
        self.import_graph[name] = {"filename": "", "imports": []}
        return self.import_graph[name]

    def _get_or_create(self, name):
        node = self._get_node(name)
        if not node:
            return self._create_node(name)
        return node

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

    def get_imports(self, modname):
        return self.import_graph[modname]["imports"]

    def add_node(self, node_name, filename):
        node = self._get_or_create(node_name)
        node["filename"] = filename

    def add_edge(self, dest):
        node = self._get_or_create(self._get_module_path())
        if not dest in node["imports"]:
            node["imports"].append(dest)

    def _handle_level(self, name, level):
        # add a dot for each level
        mod_name = ("." * level) + name
        package = self._get_module_path().split(".")
        if level > len(package):
            raise Exception("attempting import beyond top level package")
        package = ".".join(package[:-level])
        return mod_name, package

    def do_import(self, mod_name, level):
        mod_name, package = self._handle_level(mod_name, level)
        try:
            mod = importlib.import_module(mod_name, package=package)
        except ImportError as e:
            # try the parent
            mod_name = ".".join(mod_name.split(".")[:-1])
            mod = importlib.import_module(mod_name, package=package)

        filepath = os.path.relpath(mod.__file__, self.mod_dir)
        return utils.to_mod_name(filepath)

    def handle_import(self, name, level):
        # We currently don't support builtin modules because they're frozen.
        # Add an edge and continue.
        # TODO: identify a way to include frozen modules
        root = name.split(".")[0]
        if root in sys.builtin_module_names:
            self.add_edge(root)
            return

        # Import the module
        modname = self.do_import(name, level)
        return modname

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
