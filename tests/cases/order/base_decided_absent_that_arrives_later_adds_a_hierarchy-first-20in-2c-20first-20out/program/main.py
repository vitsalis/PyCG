
class Base:
    def f(self): pass
def make(base=Base):
    class C(base):
        def __getattr__(self, name): pass
        def g(self):
            self.f()
    return C
