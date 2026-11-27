
class A:
    def m(self): pass
def f(): pass
def g(): pass
def use(x):
    y = None
    if callable(y):
        f()
    if isinstance(y, A):
        g()
    cls = None
    if isinstance(x, cls):
        x.m()
use(A())
