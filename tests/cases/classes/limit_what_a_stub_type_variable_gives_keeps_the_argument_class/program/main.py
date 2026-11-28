class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

from copy import deepcopy
from functools import reduce
def folded():
    x = reduce(lambda acc, _: list(acc), [0], (A(),))
    if isinstance(x, list):
        x[0].inside()
def copied():
    xs = [B()]
    x = deepcopy(xs, {id(xs): (B(),)})
    if isinstance(x, tuple):
        x[0].after()
