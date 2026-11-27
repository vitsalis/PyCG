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

import collections
def decode(content):
    if isinstance(content, bytes):
        content = content.decode()
    return content
def items(d):
    if not isinstance(d, dict):
        raise TypeError(d)
    return d.items()
def ordered(d):
    if isinstance(d, collections.OrderedDict):
        d.move_to_end(1)
