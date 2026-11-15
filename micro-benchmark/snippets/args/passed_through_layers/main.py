def target():
    pass

def inner(f):
    f()

def middle(f):
    inner(f)

def outer(f):
    middle(f)

outer(target)
