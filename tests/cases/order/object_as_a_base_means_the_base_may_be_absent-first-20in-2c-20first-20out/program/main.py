
import sys
class A:
    def f(self): pass
class C(A if sys.argv else object):
    def __getattr__(self, name):
        pass
C().f()
