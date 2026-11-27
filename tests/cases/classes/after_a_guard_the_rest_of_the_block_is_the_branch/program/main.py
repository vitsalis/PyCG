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

def returns(x):
    if not isinstance(x, A):
        return
    x.inside()
def raises(x):
    if not isinstance(x, A):
        raise TypeError(x)
    x.inside()
def loops(xs):
    for x in xs:
        if not isinstance(x, A):
            continue
        x.inside()
    for x in xs:
        if not isinstance(x, B):
            break
        x.other()
    x.after()
def asserts(x):
    assert isinstance(x, A)
    x.inside()
def block(x, flag):
    if flag:
        if not isinstance(x, A):
            return
        x.inside()
    x.after()
def waits(x):
    while not isinstance(x, A):
        x = x.parent
    x.inside()
