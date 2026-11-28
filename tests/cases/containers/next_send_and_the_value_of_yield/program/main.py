
def f(): pass
def g(): pass
def h(): pass
def echo():
    received = yield f
    received()
    yield g
def use():
    gen = echo()
    next(gen)()
    gen.send(h)()
    next(echo(), g)()
