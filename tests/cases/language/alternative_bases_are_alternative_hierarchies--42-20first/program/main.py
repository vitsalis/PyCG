
import sys
class Root:
    def m(self): pass
    def n(self): pass
class B(Root):
    pass
class A:
    def m(self): pass
class C(A if sys.argv else B):
    pass
C().m()
C().n()
