
class A:
    def f(self): pass
class B:
    def f(self): pass
class C(A, B):
    pass
C().f()
