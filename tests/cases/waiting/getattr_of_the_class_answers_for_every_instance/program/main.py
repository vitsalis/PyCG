
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
    x.missing()
use(Lazy())
use(Lazy())
