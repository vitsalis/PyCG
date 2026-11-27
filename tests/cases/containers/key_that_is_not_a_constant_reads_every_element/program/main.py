def f(): pass
def g(): pass
def h(): pass

def pick(i):
    return [f, g][i]
pick(int("1"))()
