
def f(): pass
def g(): pass
def h(): pass

def use():
    handler = f
    for handler in (g,):
        pass
    handler()
