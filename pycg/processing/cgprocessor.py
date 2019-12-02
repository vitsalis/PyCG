import os
import ast

from pycg import utils
from pycg.processing.base import ProcessingBase
from pycg.machinery.callgraph import CallGraph

class CallGraphProcessor(ProcessingBase):
    def __init__(self, filename, modname, import_manager,
            scope_manager, def_manager, class_manager,
            call_graph=None, modules_analyzed=None):
        super().__init__(filename, modname, modules_analyzed)
        # parent directory of file
        self.parent_dir = os.path.dirname(filename)

        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager

        self.call_graph = call_graph
        if not self.call_graph:
            self.call_graph = CallGraph()

        self.closured = self.def_manager.transitive_closure()

        # Stack for names of functions
        self.name_stack = []

    def get_call_graph(self):
        return self.call_graph.get()

    def visit_FunctionDef(self, node):
        current_ns = utils.join_ns(self.current_ns, node.name)
        self.call_graph.add_node(current_ns)

        super().visit_FunctionDef(node)

    def visit_Lambda(self, node):
        counter = self.scope_manager.get_scope(self.current_ns).inc_lambda_counter()
        lambda_name = utils.get_lambda_name(counter)
        lambda_fullns = utils.join_ns(self.current_ns, lambda_name)

        self.call_graph.add_node(lambda_fullns)

        super().visit_Lambda(node, lambda_name)

    def visit_Call(self, node):
        # First visit the child function so that on the case of
        #       func()()()
        # we first visit the call to func and then the other calls
        self.visit(node.func)

        names = self.retrieve_call_names(node)
        if not names:
            return

        self.last_called_names = names
        for pointer in names:
            pointer_def = self.def_manager.get(pointer)
            if pointer_def.get_type() == utils.constants.FUN_DEF:
                self.call_graph.add_edge(self.current_ns, pointer)

            if pointer_def.get_type() == utils.constants.CLS_DEF:
                init_ns = self.find_cls_fun_ns(pointer, utils.constants.CLS_INIT)
                if init_ns:
                    self.call_graph.add_edge(self.current_ns, init_ns)

    def analyze_submodules(self):
        super().analyze_submodules(CallGraphProcessor, self.import_manager,
                self.scope_manager, self.def_manager, self.class_manager,
                call_graph=self.call_graph, modules_analyzed=self.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
