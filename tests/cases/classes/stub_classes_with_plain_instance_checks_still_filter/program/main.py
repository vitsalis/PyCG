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

import json
import uuid
class Mine(json.JSONDecodeError):
    def inside(self): pass
def errors(x=Other(), y=Mine("m", "d", 0)):
    for v in (x, y):
        if isinstance(v, ValueError):
            v.inside()
def ids(x=Other()):
    if isinstance(x, uuid.UUID):
        x.inside()
