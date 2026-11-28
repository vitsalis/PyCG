
import mystery
import sys
class A:
    def m(self): pass
class B:
    def m(self): pass
def opened(x, cls):
    if isinstance(x, (cls,)):
        x.m()
def negated(x, cls):
    if not isinstance(x, (cls, int)):
        return
    x.m()
opened(A(), mystery.K)
opened(B(), 5)
negated(1, str)
negated(A(), sys.modules["m"].K)
