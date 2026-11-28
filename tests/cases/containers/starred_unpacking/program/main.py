def f(): pass
def g(): pass
def h(): pass
def k(): pass
first, *middle, last = f, g, h, k
def use():
    middle[0]()
    last()
