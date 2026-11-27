
class C:
    def f(self): pass
def run():
    for name, value in C.__dict__.items():
        value(C())
run()
