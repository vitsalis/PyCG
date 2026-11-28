def f(): pass
def g(): pass
def h(): pass

def first(*args):
    return args[0]
def far(*args):
    return args[-9223372036854775809]
items = [f]
items[-9223372036854775809] = g
def call_first():
    first(*items)()
def call_far():
    far(*items)()
