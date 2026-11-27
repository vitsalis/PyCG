
import functools
def f(): pass
def g(): pass
def h(): pass
def get(self):
    return h
class C:
    def m(self): pass
    def __len__(self): return 0
    p = property(**{"fget": get})
    s = staticmethod(*[g])
def use(c):
    len(*(c,))
    getattr(*(c, "m"))()
    c.p()
    C.s()
    functools.update_wrapper(wrapped=g, wrapper=f)()
use(C())
