
def f(): pass
def g(): pass
class C:
    locals()
    f()
    f = g
