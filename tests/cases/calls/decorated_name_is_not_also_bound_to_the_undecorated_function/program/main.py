
def other(): pass
def replace(f):
    return other
@replace
def g(): pass
g()
