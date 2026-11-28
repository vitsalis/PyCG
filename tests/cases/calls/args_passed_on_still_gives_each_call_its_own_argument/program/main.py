
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def log(*items):
    pass
def keep(items):
    pass
def first(*args):
    log(*args)
    keep(args)
    return args[0]
def use():
    first(f)()
first(g)
