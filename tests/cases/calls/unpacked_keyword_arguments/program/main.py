def f(): pass
def g(): pass
def h(): pass

def named(a=None, b=None, **rest):
    b()
    rest["c"]()
named(**{"b": f, "c": g})
