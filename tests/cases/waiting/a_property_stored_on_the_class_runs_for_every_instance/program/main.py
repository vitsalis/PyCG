
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

def read(x):
    return x.size
read(a)
read(b)
C.size = property(f)
