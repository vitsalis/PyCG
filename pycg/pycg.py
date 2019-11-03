import sys
import os
import ast

from pycg.preprocessor import Preprocessor
from pycg.machinery.scopes import ScopeManager
from pycg.machinery.definitions import DefinitionManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.callgraph import CallGraph

import pycg.utils

class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, modulename, filename, import_manager, scope_manager, def_manager, call_graph, modules_analyzed=None):
        # name of file being analyzed
        self.filename = filename
        # parent directory of file
        self.parent_dir = os.path.dirname(filename)
        # name of the module being analyzed
        self.modulename = modulename
        with open(filename, "rt") as f:
            self.contents = f.read()

        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.call_graph = call_graph

        self.closured = self.def_manager.transitive_closure()

        # Add the current module to the already analyzed list
        if not modules_analyzed:
            self.modules_analyzed = set()
        else:
            self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(modulename)
        # Stack for names of functions
        self.name_stack = []

    def get_current_namespace(self):
        return ".".join(self.name_stack)

    def get_modules_analyzed(self):
        return self.modules_analyzed

    def merge_modules_analyzed(self, analyzed):
        self.modules_analyzed = self.modules_analyzed.union(analyzed)

    def visit_Module(self, node):
        self.name_stack.append(self.modulename)
        self.generic_visit(node)
        self.name_stack.pop()

    def visit_FunctionDef(self, node):
        self.name_stack.append(node.name)
        self.call_graph.add_node(self.get_current_namespace())
        for stmt in node.body:
            self.visit(stmt)
        self.name_stack.pop()

    def visit_Call(self, node):
        self.visit(node.func)
        current_namespace = self.get_current_namespace()
        defi = self.scope_manager.get_def(current_namespace, node.func.id)

        if self.closured.get(defi.get_ns(), None):
            for pointer in self.closured[defi.get_ns()]:
                self.call_graph.add_edge(current_namespace, pointer)



    def analyze_submodules(self):
        """
        Analyze all submodules, and merge all the call graph, tracking etc
        information with the information for this module.
        """
        imports = self.import_manager.get_imports(self.modulename)

        for imp in imports:
            if imp in self.modules_analyzed:
                continue

            fname = self.import_manager.get_filepath(imp)

            visitor = ModuleVisitor(imp, fname, self.import_manager,
                self.scope_manager, self.def_manager, self.call_graph,
                modules_analyzed=self.modules_analyzed)
            visitor.analyze()
            self.merge_modules_analyzed(visitor.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()

class CallGraphGenerator(object):
    def setUp(self):
        self.import_manager = ImportManager(self.input_file)
        self.scope_manager = ScopeManager()
        self.def_manager = DefinitionManager()
        self.call_graph = CallGraph()

        self.import_manager.install_hooks()

    def tearDown(self):
        self.import_manager.remove_hooks()

    def __init__(self, input_file):
        input_mod = pycg.utils.to_mod_name(input_file.split("/")[-1])
        self.input_file = os.path.abspath(input_file)

        self.setUp()

        # preprocessing
        self.preprocessor = Preprocessor(input_file, self.import_manager, self.scope_manager, self.def_manager)
        self.preprocessor.analyze()

        self.import_manager.remove_hooks()

        self.def_manager.complete_definitions()

        self.visitor = ModuleVisitor(input_mod, input_file, self.import_manager, self.scope_manager, self.def_manager, self.call_graph)
        self.visitor.analyze()

    def output(self):
        return self.call_graph.get()
