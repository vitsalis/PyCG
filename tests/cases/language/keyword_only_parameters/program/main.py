
def g(): pass
def h(): pass
def f(*, a, b=h):
    a()
    b()
f(a=g)
