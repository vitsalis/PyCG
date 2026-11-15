def func1():
    pass

def gen():
    yield func1

g = gen()
next(g)()
