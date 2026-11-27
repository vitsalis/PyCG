
class A:
    def m(self): pass
class B(A):
    @staticmethod
    def s():
        super().m()
B.s()
