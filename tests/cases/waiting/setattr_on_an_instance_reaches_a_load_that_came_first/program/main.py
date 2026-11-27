
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

def use(x):
    x.cb()
use(a)
use(b)
setattr(a, "cb", h)
