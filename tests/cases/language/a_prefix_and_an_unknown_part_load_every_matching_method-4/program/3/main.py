
class Visitor:
    def visit(self, node, kind):
        method = getattr(self, f"visit_{kind}", self.default_visit)
        return method(node)
    def default_visit(self, node): pass
class Interpreter(Visitor):
    def visit_field(self, node): pass
    def visit_index(self, node): pass
    def field_handler(self, node): pass
    def other(self, node): pass
