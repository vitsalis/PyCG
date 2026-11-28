
def f(): pass
def g(): pass
def h(): pass

handler = f
def clear():
    global handler
    del handler
def use():
    handler()
