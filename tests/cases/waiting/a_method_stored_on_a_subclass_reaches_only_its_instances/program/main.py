
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

def first(x):
    x.run()
def second(x):
    x.run()
first(a)
first(b)
second(d)
D.run = f
