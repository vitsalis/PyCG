
class A:
    def f(self): pass
class B:
    def f(self): pass
def base():
    return A
class C(base(), B):
    pass
C().f()
