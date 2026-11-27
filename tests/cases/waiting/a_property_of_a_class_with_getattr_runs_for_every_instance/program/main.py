
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
    @property
    def size(self):
        return g
def use(x):
    x.size()
    x.other()
use(Lazy())
use(Lazy())
