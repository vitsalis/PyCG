
class Visitor:
    def __init__(self):
        self.visit_extra = extra
    def visit(self, kind):
        getattr(self, "visit_" + kind)()
def late(self): pass
def extra(): pass
class Child(Visitor):
    pass
Child.visit_late = late
