
def g(): pass
def f(a, /, **kwargs):
    a()
f(a=g)
