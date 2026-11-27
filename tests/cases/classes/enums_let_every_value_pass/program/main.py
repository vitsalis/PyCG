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

import enum
def ints(x=Other()):
    if isinstance(x, enum.IntEnum):
        x.inside()
def flags(x=Other()):
    if isinstance(x, enum.IntFlag):
        x.after()
def strs(x=Other()):
    if isinstance(x, enum.StrEnum):
        x.other()
