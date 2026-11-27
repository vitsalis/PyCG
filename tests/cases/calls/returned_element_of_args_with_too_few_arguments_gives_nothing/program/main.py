
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def second(*args):
    return args[1]
def use():
    second(f)()
second(g, h)
