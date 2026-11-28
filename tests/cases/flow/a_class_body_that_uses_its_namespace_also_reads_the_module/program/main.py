
def f(): pass
def g(): pass
def h(): pass

class C:
    locals()
    f()
    f = g
def builtin():
    class D:
        vars()
        len()
        len = h
def outer():
    f = h
    class Inner:
        locals()
        f()
        f = g
def function():
    locals()
    f()
    f = g
