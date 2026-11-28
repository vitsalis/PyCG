
class A:
    def f(self): pass
class B:
    def f(self): pass
Left, Right = A, B
class C(Left):
    pass
class D(Right):
    def f(self): pass
def late():
    global Left, Right
    Left, Right = D, C
D().f()
