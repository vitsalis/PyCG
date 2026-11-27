
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
    len(x)
    for item in x:
        pass
use(a)
use(b)
C.__len__ = f
C.__iter__ = g
