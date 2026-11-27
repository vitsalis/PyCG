
class A: pass
class B: pass
Base = A
class A(Base):
    def m(self): pass
Base = A
class X(A, B): pass
class Y(B, A): pass
class Z(X, Y): pass
Z().m()
Left = Right = object
class P(Right):
    def p(self): pass
class Q(Left):
    def q(self): pass
def swap():
    global Left, Right
    Left, Right = P, Q
Q().p()
