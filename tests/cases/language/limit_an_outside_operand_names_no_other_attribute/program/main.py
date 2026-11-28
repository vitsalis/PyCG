
import ext
class Visitor:
    def visit_a(self): pass
    def hit(self): pass
    def visit(self):
        getattr(self, "visit_" + ext.value)()
Visitor().visit()
