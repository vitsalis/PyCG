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

def use(x=A(), y=Sub(), z=Other()):
    for v in (x, y, z):
        if isinstance(v, A):
            pass
        else:
            v.inside()
        if not isinstance(v, (B, Other)):
            v.after()
def text(value=b"b", other="s"):
    for v in (value, other):
        if not isinstance(v, bytes):
            v.upper()
