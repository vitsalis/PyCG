class C: pass
class D: pass
C.__new__ = D
D.__new__ = C
C()
