
class Visitor:
    def visit(self, kind):
        return getattr(self, ("visit_" + kind).upper().lower(), self.default)()
    def default(self): pass
    def visit_field(self): pass
    def visit_Field(self): pass
    def VISIT_INDEX(self): pass
    def VISIT_Index(self): pass
    def visit_é(self): pass
