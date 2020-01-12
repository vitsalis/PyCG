import os
import ast

from pycg.processing.preprocessor import PreProcessor
from pycg.processing.postprocessor import PostProcessor
from pycg.processing.cgprocessor import CallGraphProcessor

from pycg.machinery.scopes import ScopeManager
from pycg.machinery.definitions import DefinitionManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.classes import ClassManager
from pycg.machinery.callgraph import CallGraph
from pycg import utils

class CallGraphGenerator(object):
    def setUp(self):
        self.import_manager = ImportManager()
        self.scope_manager = ScopeManager()
        self.def_manager = DefinitionManager()
        self.class_manager = ClassManager()
        self.cg = CallGraph()

    def remove_import_hooks(self):
        self.import_manager.remove_hooks()

    def tearDown(self):
        self.remove_import_hooks()

    def __init__(self, entry_points):
        self.entry_points = entry_points
        self.setUp()

    def analyze(self):
        # preprocessing
        modules_analyzed = set()
        for entry_point in self.entry_points:
            input_mod = utils.to_mod_name(entry_point.split("/")[-1])
            input_file = os.path.abspath(entry_point)
            input_pkg = entry_point

            if not input_mod in modules_analyzed:
                self.import_manager.set_pkg(input_file)
                self.import_manager.install_hooks()

                processor = PreProcessor(input_file, input_mod,
                        self.import_manager, self.scope_manager, self.def_manager,
                        self.class_manager, modules_analyzed=modules_analyzed)
                processor.analyze()
                modules_analyzed = modules_analyzed.union(processor.get_modules_analyzed())

                self.remove_import_hooks()

        self.def_manager.complete_definitions()

        modules_analyzed = set()
        for entry_point in self.entry_points:
            input_mod = utils.to_mod_name(entry_point.split("/")[-1])
            input_file = os.path.abspath(entry_point)

            if not input_mod in modules_analyzed:
                processor = PostProcessor(input_file, input_mod,
                        self.import_manager, self.scope_manager, self.def_manager,
                        self.class_manager, modules_analyzed=modules_analyzed)
                processor.analyze()
                modules_analyzed = modules_analyzed.union(processor.get_modules_analyzed())

        self.def_manager.complete_definitions()

        modules_analyzed = set()
        for entry_point in self.entry_points:
            input_mod = utils.to_mod_name(entry_point.split("/")[-1])
            input_file = os.path.abspath(entry_point)

            if not input_mod in modules_analyzed:
                self.visitor = CallGraphProcessor(input_file, input_mod,
                        self.import_manager, self.scope_manager, self.def_manager,
                        self.class_manager, modules_analyzed=modules_analyzed,
                        call_graph=self.cg)
                self.visitor.analyze()
                modules_analyzed = modules_analyzed.union(self.visitor.get_modules_analyzed())

    def output(self):
        return self.cg.get()
