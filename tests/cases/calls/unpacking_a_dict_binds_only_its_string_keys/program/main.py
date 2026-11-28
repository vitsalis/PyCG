def f(): pass
def g(): pass
def h(): pass

def take(a):
    a()
take(**{1: f, "a": g})
