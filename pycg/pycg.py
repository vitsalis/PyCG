import os
import ast

from pycg.processing.preprocessor import PreProcessor
from pycg.processing.postprocessor import PostProcessor
from pycg.processing.cgprocessor import CallGraphProcessor

from pycg.machinery.scopes import ScopeManager
from pycg.machinery.definitions import DefinitionManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.classes import ClassManager
from pycg import utils

class CallGraphGenerator(object):
    def setUp(self):
        self.import_manager = ImportManager(self.input_pkg)
        self.scope_manager = ScopeManager()
        self.def_manager = DefinitionManager()
        self.class_manager = ClassManager()

        self.import_manager.install_hooks()

    def remove_import_hooks(self):
        self.import_manager.remove_hooks()

    def tearDown(self):
        self.remove_import_hooks()

    def __init__(self, input_file, input_pkg):
        self.input_mod = utils.to_mod_name(input_file.split("/")[-1])
        self.input_file = os.path.abspath(input_file)
        self.input_pkg = input_pkg

        self.setUp()

    def analyze(self):
        # preprocessing
        PreProcessor(self.input_file, self.input_mod,
                self.import_manager, self.scope_manager, self.def_manager,
                self.class_manager, modules_analyzed=set()).analyze()

        self.remove_import_hooks()

        self.def_manager.complete_definitions()

        PostProcessor(self.input_file, self.input_mod,
                self.import_manager, self.scope_manager, self.def_manager,
                self.class_manager, modules_analyzed=set()).analyze()

        self.def_manager.complete_definitions()

        self.visitor = CallGraphProcessor(self.input_file, self.input_mod,
                self.import_manager, self.scope_manager, self.def_manager,
                self.class_manager, modules_analyzed=set())
        self.visitor.analyze()

    def output(self):
        return self.visitor.get_call_graph()
