
def f(self=None): pass
def g(): pass
class C:
    handler = f
C.extra = g
def use():
    C.handler()
    C().handler()
    C.extra()
