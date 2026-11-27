
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def rest(*args):
    args = args[1:]
    return args[0]
def nested(*args):
    def reset():
        nonlocal args
        args = (h,)
    return args[0]
def use():
    rest(None, f)()
    nested(f)()
rest(None, g)
nested(g)
