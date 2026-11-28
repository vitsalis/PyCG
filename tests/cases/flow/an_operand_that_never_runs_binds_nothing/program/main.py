
def f(): pass
def g(): pass
def h(): pass

def use():
    handler = f
    True or (handler := g)
    handler()
    other = f
    (other := g) if () else None
    other()
