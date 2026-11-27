
def f(): pass
def g(): pass
def h(): pass

def wrong():
    x: int = f(1)
    g()
def right():
    x: int = f()
    g()
