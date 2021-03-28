class A:
    class B:
        def bfunc(self):
            pass

class C(A.B):
    def cfunc(self):
        pass

c = C()
c.cfunc()
c.bfunc()
