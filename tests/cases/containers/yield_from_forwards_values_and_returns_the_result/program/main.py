
def f(): pass
def g(): pass
def inner():
    yield f
    return g
def outer():
    result = yield from inner()
    result()
    yield from [g]
for value in outer():
    value()
