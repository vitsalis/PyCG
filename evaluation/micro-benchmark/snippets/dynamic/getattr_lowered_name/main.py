class Field:
    pass


class Index:
    pass


class Other:
    pass


class Visitor:
    def visit(self, node):
        name = f"visit_{type(node).__name__}".lower()
        method = getattr(self, name, self.generic_visit)
        return method(node)

    def generic_visit(self, node):
        pass

    def visit_field(self, node):
        pass

    def visit_Field(self, node):
        pass

    def visit_index(self, node):
        pass


visitor = Visitor()
visitor.visit(Field())
visitor.visit(Index())
visitor.visit(Other())
