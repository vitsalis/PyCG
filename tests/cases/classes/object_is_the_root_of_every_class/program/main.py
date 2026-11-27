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

def instances(x=A(), y="s"):
    for v in (x, y):
        if isinstance(v, object):
            v.inside()
        else:
            v.after()
        if not isinstance(v, (B, object)):
            v.other()
def classes(k=A):
    if issubclass(k, object):
        k().inside()
    else:
        k().after()
