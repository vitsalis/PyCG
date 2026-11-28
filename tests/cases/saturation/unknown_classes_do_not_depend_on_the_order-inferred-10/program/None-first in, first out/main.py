
class M0(type): pass
class M1(M0): pass
class M2(M1): pass
for meta in (M0, M2):
    class A(metaclass=meta):
        def method(self): pass
for meta in (M0, M1):
    class B(metaclass=meta): pass
class C(A, B): pass
C.method(None)
