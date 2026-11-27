def f(): pass
def g(): pass
def h(): pass

first = {"key": f}
second = {"key": g}
def use():
    first["key"]()
