
def f(): pass
def g(): pass
def h(): pass

def before():
    handler = f
    handler = g
    handler()
def after():
    handler = f
    handler()
    handler = g
