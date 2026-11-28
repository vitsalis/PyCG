
def f(): pass
def g(): pass
def h(): pass

class A:
    def m(self): pass
class B:
    def m(self): pass
def run(x):
    if isinstance(x, A):
        x = B()
    else:
        return
    x.m()
run(A())
