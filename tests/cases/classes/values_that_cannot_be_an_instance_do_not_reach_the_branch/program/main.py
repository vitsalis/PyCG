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

def use(x=Other(), y=Sub()):
    if isinstance(x, A):
        x.inside()
    if isinstance(y, A):
        y.other()
def strings(x="s", y=Other()):
    if isinstance(x, bytes):
        x.decode()
    if isinstance(y, str):
        y.inside()
