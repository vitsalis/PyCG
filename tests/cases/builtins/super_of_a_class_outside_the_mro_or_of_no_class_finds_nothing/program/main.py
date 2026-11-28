
class A:
    def m(self):
        return super(Exception, self).m()
    def n(self):
        super().n()
    def p(self):
        super(A.m, self).p()
A().m()
A.n(1)
A().p()
