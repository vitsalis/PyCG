
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

def fill(x):
    x.value = 1
fill(a)
fill(b)
C.__setattr__ = h
