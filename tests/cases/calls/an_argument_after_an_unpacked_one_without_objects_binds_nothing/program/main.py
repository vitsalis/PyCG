def f(): pass
def g(): pass
def h(): pass

def take(*args):
    args[0]()
take(*(f,), 1.5)
