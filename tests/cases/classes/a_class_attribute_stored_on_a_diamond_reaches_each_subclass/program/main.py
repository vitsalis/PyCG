
def f(): pass
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass
A.x = f
D.x()
