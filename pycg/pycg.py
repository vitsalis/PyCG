import os
import ast

from pycg.processing.preprocessor import PreProcessor
from pycg.processing.postprocessor import PostProcessor
from pycg.processing.cgprocessor import CallGraphProcessor

from pycg.machinery.scopes import ScopeManager
from pycg.machinery.definitions import DefinitionManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.callgraph import CallGraph
from pycg import utils

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
        self.input_mod = utils.to_mod_name(input_file.split("/")[-1])
        self.input_file = os.path.abspath(input_file)

        self.setUp()

    def analyze(self):
        # preprocessing
        self.preprocessor = PreProcessor(self.input_file,
                self.import_manager, self.scope_manager, self.def_manager)
        self.preprocessor.analyze()

        self.import_manager.remove_hooks()

        self.def_manager.complete_definitions()

        self.visitor = CallGraphProcessor(self.input_mod,
                self.input_file, self.import_manager,
                self.scope_manager, self.def_manager, self.call_graph)
        self.visitor.analyze()

    def output(self):
        return self.call_graph.get()
