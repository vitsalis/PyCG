
class A:
    def _func_a(self): pass
    def other(self): pass
def run():
    for name, member in vars(A).items():
        if name.startswith("_func_"):
            member(A())
run()
