
rebound = read = 1
def install():
    global rebound
    rebound = 2
def reader():
    global read
    return read
def outer():
    mine = cell = 1
    def inner():
        nonlocal cell
        cell = 2
    [last := x for x in ()]
