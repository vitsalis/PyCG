def f(): pass
def g(): pass
def h(): pass

def first(*args):
    return args[0]
def far(*args):
    return args[9345883071009581737]
items = [f]
items[9345883071009581737] = g
def call_first():
    first(*items)()
def call_far():
    far(*items)()
