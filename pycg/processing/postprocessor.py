import ast

from pycg.processing.base import ProcessingBase
from pycg import utils

class PostProcessor(ProcessingBase):
    def __init__(self, input_file, modname,
            import_manager, scope_manager, def_manager, modules_analyzed=None):
        super().__init__(input_file, modname, modules_analyzed)
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.closured = self.def_manager.transitive_closure()

    def visit_Lambda(self, node):
        counter = self.scope_manager.get_scope(self.current_ns).inc_lambda_counter()
        lambda_name = utils.get_lambda_name(counter)
        super().visit_Lambda(node, lambda_name)

    def visit_Call(self, node):
        self.visit(node.func)

        names = self.retrieve_call_names(node)
        if not names:
            return

        self.last_called_names = names

        for name in names:
            defi = self.def_manager.get(name)
            self.iterate_call_args(defi, node)

    def analyze_submodules(self):
        super().analyze_submodules(PostProcessor, self.import_manager,
                self.scope_manager, self.def_manager,
                modules_analyzed=self.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
