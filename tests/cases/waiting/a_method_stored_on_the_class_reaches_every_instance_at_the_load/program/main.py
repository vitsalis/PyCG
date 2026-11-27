
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
    x.run()
for x in (a, b, d):
    use(x)
C.run = f
