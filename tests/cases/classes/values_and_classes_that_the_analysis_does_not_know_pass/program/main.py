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

import abc
import collections.abc
import ext
class Abstract(abc.ABC):
    def inside(self): pass
def unknown_value(x=ext.value):
    if isinstance(x, A):
        x.inside()
    else:
        x.after()
def unknown_class(x=Other()):
    if isinstance(x, ext.Thing):
        x.inside()
def nothing(x=Other(), kind=None):
    if isinstance(x, kind):
        x.inside()
    else:
        x.after()
def partly(x=Other(), kind=None):
    if not isinstance(x, (B, kind)):
        x.inside()
    if isinstance(x, (B, kind)):
        x.after()
def abstract(x=Other(), y=Abstract()):
    for v in (x, y):
        if isinstance(v, Abstract):
            v.inside()
        if isinstance(v, collections.abc.Sized):
            v.after()
        else:
            v.other()
