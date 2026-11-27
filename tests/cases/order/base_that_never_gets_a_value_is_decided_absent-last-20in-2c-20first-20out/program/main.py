
class C(undefined):
    def f(self): pass
    def g(self):
        self.f()
C().g()
