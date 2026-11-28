
def f(): pass
def g(): pass
def h(): pass
def pick(value=h):
    return value
def use():
    pick(f)()
    pick(value=g)()
    pick()()
def other():
    pick(f)()
