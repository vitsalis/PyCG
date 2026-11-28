
def f(): pass
def g(): pass
def h(): pass

class C:
    handler = f
    handler()
    handler = g
def use():
    C.handler()
