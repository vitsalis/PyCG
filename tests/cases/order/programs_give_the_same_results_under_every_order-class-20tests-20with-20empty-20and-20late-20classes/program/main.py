
import abc
def f(x, classes):
    if not isinstance(x, classes):
        x.lower()
    if isinstance(x, classes):
        x.upper()
f("s", ())
def target(): pass
def h(x, classes):
    if isinstance(x, classes):
        x()
h(target, ())
def meta(): return abc.ABCMeta
def base(): return abc.ABC
class Late(metaclass=meta()):
    def f(self): pass
class Later(base()):
    def f(self): pass
class Plain:
    def f(self): pass
def g(y=Plain(), z=Late()):
    for v in (y, z):
        if isinstance(v, Late):
            v.f()
        if not isinstance(v, (Later, Plain)):
            v.f()
