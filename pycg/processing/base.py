import ast

class ProcessingBase(ast.NodeVisitor):
    def __init__(self, modname, modules_analyzed=None):
        self.modname = modname

        self.modules_analyzed = set()
        if modules_analyzed:
            self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(self.modname)

    def get_modules_analyzed(self):
        return self.modules_analyzed

    def merge_modules_analyzed(self, analyzed):
        self.modules_analyzed = self.modules_analyzed.union(analyzed)
