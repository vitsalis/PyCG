
import collections, ext
class A:
    def f(self): pass
def base(): return A
class B(base()):
    def f(self): pass
class C(ext.Base, collections.OrderedDict):
    def f(self): pass
class D:
    def f(self): pass
def kinds(): return (later(), str)
def later(): return D
KINDS = (B, C)
def make(): return [A(), B(), C(), D(), "s", b"b", 1, A, B]
def use(flag, kind=None):
    late = kinds()
    for x in make():
        if isinstance(x, late):
            x.f()
        elif not isinstance(x, KINDS):
            x.f()
            x.upper()
        elif isinstance(x, (A, bytes)) and flag:
            x.decode()
        if not isinstance(x, (dict, kind)):
            continue
        x.f()
        if issubclass(x, A):
            x().f()
        while isinstance(x, collections.OrderedDict):
            x.f()
            x = x.next
        x.f()
