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
import ast

from pycg.processing.preprocessor import PreProcessor
from pycg.processing.postprocessor import PostProcessor
from pycg.processing.cgprocessor import CallGraphProcessor
from pycg.processing.keyerrprocessor import KeyErrProcessor

from pycg.machinery.scopes import ScopeManager
from pycg.machinery.definitions import DefinitionManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.classes import ClassManager
from pycg.machinery.callgraph import CallGraph
from pycg.machinery.key_err import KeyErrors
from pycg.machinery.modules import ModuleManager
from pycg import utils

class CallGraphGenerator(object):
    def __init__(self, entry_points, package, max_iter, operation):
        self.entry_points = entry_points
        self.package = package
        self.state = None
        self.max_iter = max_iter
        self.operation = operation
        self.setUp()

    def setUp(self):
        self.import_manager = ImportManager()
        self.scope_manager = ScopeManager()
        self.def_manager = DefinitionManager()
        self.class_manager = ClassManager()
        self.module_manager = ModuleManager()
        self.cg = CallGraph()
        self.key_errs = KeyErrors()

    def extract_state(self):
        state = {}
        state["defs"] = {}
        for key, defi in self.def_manager.get_defs().items():
            state["defs"][key] = {
                "names": defi.get_name_pointer().get().copy(),
                "lit": defi.get_lit_pointer().get().copy()
            }

        state["scopes"] = {}
        for key, scope in self.scope_manager.get_scopes().items():
            state["scopes"][key] = set([x.get_ns() for (_, x) in scope.get_defs().items()])

        state["classes"] = {}
        for key, ch in self.class_manager.get_classes().items():
            state["classes"][key] = ch.get_mro().copy()
        return state

    def reset_counters(self):
        for key, scope in self.scope_manager.get_scopes().items():
            scope.reset_counters()

    def has_converged(self):
        if not self.state:
            return False

        curr_state = self.extract_state()

        # check defs
        for key, defi in curr_state["defs"].items():
            if not key in self.state["defs"]:
                return False
            if defi["names"] != self.state["defs"][key]["names"]:
                return False
            if defi["lit"] != self.state["defs"][key]["lit"]:
                return False

        # check scopes
        for key, scope in curr_state["scopes"].items():
            if not key in self.state["scopes"]:
                return False
            if scope != self.state["scopes"][key]:
                return False

        # check classes
        for key, ch in curr_state["classes"].items():
            if not key in self.state["classes"]:
                return False
            if ch != self.state["classes"][key]:
                return False

        return True

    def remove_import_hooks(self):
        self.import_manager.remove_hooks()

    def tearDown(self):
        self.remove_import_hooks()

    def _get_mod_name(self, entry, pkg):
        # We do this because we want __init__ modules to
        # only contain the parent module
        # since pycg can't differentiate between functions
        # coming from __init__ files.

        input_mod = utils.to_mod_name(
            os.path.relpath(entry, pkg))
        if input_mod.endswith("__init__"):
            input_mod = ".".join(input_mod.split(".")[:-1])

        return input_mod

    def do_pass(self, cls, install_hooks=False, *args, **kwargs):
        modules_analyzed = set()
        for entry_point in self.entry_points:
            input_pkg = self.package
            input_mod = self._get_mod_name(entry_point, input_pkg)
            input_file = os.path.abspath(entry_point)

            if not input_mod:
                continue

            if not input_pkg:
                input_pkg = os.path.dirname(input_file)

            if not input_mod in modules_analyzed:
                if install_hooks:
                    self.import_manager.set_pkg(input_pkg)
                    self.import_manager.install_hooks()

                processor = cls(input_file, input_mod,
                                modules_analyzed=modules_analyzed, *args, **kwargs)
                processor.analyze()
                modules_analyzed = modules_analyzed.union(processor.get_modules_analyzed())

                if install_hooks:
                    self.remove_import_hooks()

    def analyze(self):
        self.do_pass(PreProcessor, True,
                self.import_manager, self.scope_manager, self.def_manager,
                self.class_manager, self.module_manager)
        self.def_manager.complete_definitions()

        iter_cnt = 0
        while (self.max_iter < 0 or iter_cnt < self.max_iter) and (not self.has_converged()):
            self.state = self.extract_state()
            self.reset_counters()
            self.do_pass(PostProcessor, False,
                    self.import_manager, self.scope_manager, self.def_manager,
                    self.class_manager, self.module_manager)

            self.def_manager.complete_definitions()
            iter_cnt += 1

        self.reset_counters()
        if self.operation == utils.constants.CALL_GRAPH_OP:
            self.do_pass(CallGraphProcessor, False,
                    self.import_manager, self.scope_manager, self.def_manager,
                    self.class_manager, self.module_manager, call_graph=self.cg)
        elif self.operation == utils.constants.KEY_ERR_OP:
            self.do_pass(KeyErrProcessor, False,
                    self.import_manager, self.scope_manager, self.def_manager,
                    self.class_manager, self.key_errs)
        else:
            raise Exception("Invalid operation: " + self.operation)


    def output(self):
        return self.cg.get()

    def output_key_errs(self):
        return self.key_errs.get()

    def output_edges(self):
        return self.key_errors

    def output_edges(self):
        return self.cg.get_edges()

    def _generate_mods(self, mods):
        res = {}
        for mod, node in mods.items():
            res[mod] = {
                "filename": os.path.relpath(node.get_filename(), self.package)\
                    if node.get_filename() else None,
                "methods": node.get_methods()
            }
        return res

    def output_internal_mods(self):
        return self._generate_mods(self.module_manager.get_internal_modules())

    def output_external_mods(self):
        return self._generate_mods(self.module_manager.get_external_modules())

    def output_functions(self):
        functions = []
        for ns, defi in self.def_manager.get_defs().items():
            if defi.is_function_def():
                functions.append(ns)
        return functions

    def output_classes(self):
        classes = {}
        for cls, node in self.class_manager.get_classes().items():
            classes[cls] = {
                "mro": node.get_mro(),
                "module": node.get_module()
            }
        return classes

    def get_as_graph(self):
        return self.def_manager.get_defs().items()
