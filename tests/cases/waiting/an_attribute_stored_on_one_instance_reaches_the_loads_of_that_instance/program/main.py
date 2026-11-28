
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

def both(x):
    x.cb()
def one(x):
    x.cb()
both(a)
both(b)
one(a)
b.cb = g
