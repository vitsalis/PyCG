def f(): pass
def g(): pass
def h(): pass

def first(*args):
    return args[0]
def far(*args):
    return args[18446744073709551617]
items = [f]
items[18446744073709551617] = g
def call_first():
    first(*items)()
def call_far():
    far(*items)()
