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

import ext
def outside(x):
    if isinstance(x, ext.Thing):
        x.inside()
def unknown(x, kind):
    if isinstance(x, kind):
        x.inside()
def kept(x=Other(), kind=None):
    if isinstance(x, kind):
        x.inside()
