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

def rebinds(x):
    if isinstance(x, A):
        x = Other()
        x.inside()
def loops(x):
    while isinstance(x, A):
        x.inside()
        x = Other()
        x.after()
def walrus(x):
    if isinstance(x, A) and (x := Other()):
        x.inside()
def joins(x, flag):
    if isinstance(x, A):
        if flag:
            x = Other()
        x.inside()
