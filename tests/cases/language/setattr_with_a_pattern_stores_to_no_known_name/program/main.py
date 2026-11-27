
def handler(): pass
class Visitor:
    def visit_field(self): pass
    def install(self, kind):
        setattr(self, "visit_" + kind, handler)
    def run(self):
        self.visit_field()
