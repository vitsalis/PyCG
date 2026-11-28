class A:
    @classmethod
    def f(a, b, c):
        c.run()
class B:
    f = classmethod(A.f)
class C:
    f = classmethod(B.f)
    @staticmethod
    def run(): pass
C.f()
