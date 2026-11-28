
class C:
    def f(self): pass
    locals()
def run():
    for member in C.__dict__.values():
        member(C())
run()
