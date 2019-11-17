import os
import ast

from pycg import utils
from pycg.processing.base import ProcessingBase

class CallGraphProcessor(ProcessingBase):
    def __init__(self, modulename, filename, import_manager,
            scope_manager, def_manager, call_graph, modules_analyzed=None):
        super().__init__(modulename, modules_analyzed)
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

        # Stack for names of functions
        self.name_stack = []
        self.last_called_names = None

    @property
    def current_ns(self):
        return ".".join(self.name_stack)

    def get_last_called_names(self):
        return self.last_called_names

    def set_last_called_names(self, names):
        self.last_called_names = names

    def visit_Module(self, node):
        self.name_stack.append(self.modulename)
        self.scope_manager.get_scope(self.modulename).reset_counters()
        self.generic_visit(node)
        self.name_stack.pop()

    def visit_FunctionDef(self, node):
        self.name_stack.append(node.name)
        self.scope_manager.get_scope(self.current_ns).reset_counters()
        self.call_graph.add_node(self.current_ns)
        for stmt in node.body:
            self.visit(stmt)
        self.name_stack.pop()

    def visit_Lambda(self, node):
        counter = self.scope_manager.get_scope(self.current_ns).inc_lambda_counter()
        lambda_name = utils.get_lambda_name(counter)
        lambda_fullns = utils.join_ns(self.current_ns, lambda_name)

        self.call_graph.add_node(lambda_fullns)

        self.name_stack.append(lambda_name)
        self.visit(node.body)
        self.name_stack.pop()

    def visit_Call(self, node):
        # First visit the child function so that on the case of
        #       func()()()
        # we first visit the call to func and then the other calls
        self.visit(node.func)

        names = set()
        if isinstance(node.func, ast.Name):
            defi = self.scope_manager.get_def(self.current_ns, node.func.id)
            names = self.closured.get(defi.get_ns(), None)
        else:
            last_called_names = self.get_last_called_names()
            for name in last_called_names:
                return_ns = utils.join_ns(name, utils.constants.RETURN_NAME)
                returns = self.closured.get(return_ns)
                for ret in returns:
                    defi = self.def_manager.get(ret)
                    names.add(defi.get_ns())

        if names:
            self.set_last_called_names(names)
            for pointer in names:
                pointer_def = self.def_manager.get(pointer)
                if pointer_def.is_function_def():
                    self.call_graph.add_edge(self.current_ns, pointer)

    def analyze_submodules(self):
        """
        Analyze all submodules, and merge all the call graph, tracking etc
        information with the information for this module.
        """
        imports = self.import_manager.get_imports(self.modulename)

        for imp in imports:
            if imp in self.get_modules_analyzed():
                continue

            fname = self.import_manager.get_filepath(imp)

            visitor = CallGraphProcessor(imp, fname, self.import_manager,
                self.scope_manager, self.def_manager, self.call_graph,
                modules_analyzed=self.get_modules_analyzed())
            visitor.analyze()
            self.merge_modules_analyzed(visitor.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
