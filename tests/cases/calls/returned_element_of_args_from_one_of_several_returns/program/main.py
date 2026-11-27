
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def make():
    return h
def pick(flag, *args):
    if flag:
        return args[0]
    return make()
def use():
    pick(True, f)()
pick(True, g)
