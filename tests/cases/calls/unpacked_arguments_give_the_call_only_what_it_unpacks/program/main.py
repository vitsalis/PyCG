
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def first(*args):
    return args[0]
def second(*args):
    return args[1]
def use():
    first(*[f, g])()
    items = []
    items.append(h)
    first(*items)()
    second(*[g], h)()
def other():
    # After a positional argument, the list's positions are not kept.
    second(f, *[g])()
first(k)
second(k, k)
