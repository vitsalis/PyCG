
def a(): pass
def b(): pass
def c(): pass
def make(factory, *args):
    return factory(*args)
d = {"key": a}
make(d.items)
items = make(tuple, (a, b, c))
items[-1]()
