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

class Meta(type):
    def inside(cls): pass
def classes(k=A, m=Meta):
    for c in (k, m):
        if issubclass(c, type):
            c.inside(c)
def numbers(n=1):
    if isinstance(n, bool):
        n.bit_count()
    else:
        n.bit_length()
