
def f(*args): pass
def g(*args): pass
def h(*args): pass
class C:
    pass
class D(C):
    pass
a = C()
b = C()
d = D()

class Lazy:
    def __getattr__(self, name):
        return f
def use(x):
    len(x)
    x.value = 1
use(Lazy())
use(Lazy())
Lazy.__len__ = g
Lazy.__setattr__ = h
