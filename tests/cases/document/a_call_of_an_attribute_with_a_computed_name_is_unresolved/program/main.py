class C:
    def visit(self): pass
def run(name):
    getattr(C(), name)()
