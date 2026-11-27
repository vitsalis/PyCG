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

from collections.abc import Sequence
def made():
    yield Other()
def parse(arg):
    if isinstance(arg, (list, tuple)):
        for value in arg:
            value.inside()
    if isinstance(arg, object):
        for value in arg:
            value.after()
    if not isinstance(arg, Sequence):
        for value in arg:
            value.other()
parse([A()])
parse((B(),))
parse({Sub(): 1})
parse(made())
