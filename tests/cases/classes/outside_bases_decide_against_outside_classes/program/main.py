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
class Mine(dict):
    def inside(self): pass
    def after(self): pass
class Unknown(ext.Base):
    def inside(self): pass
    def after(self): pass
def use(x=Mine(), y=Other(), z=Unknown()):
    for v in (x, y, z):
        if isinstance(v, dict):
            v.inside()
        else:
            v.after()
