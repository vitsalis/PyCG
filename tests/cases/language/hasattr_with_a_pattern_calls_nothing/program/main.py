
class Visitor:
    def check(self, kind):
        return hasattr(self, "visit_" + kind)
    def visit_field(self): pass
