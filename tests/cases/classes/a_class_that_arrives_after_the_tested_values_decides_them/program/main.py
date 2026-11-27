
class A:
    def m(self): pass
def f(): pass
def check(cls):
    x = A()
    if isinstance(x, cls):
        x.m()
    y = 1
    if isinstance(y, cls):
        f()
check(A)
check(int)
