def func1():
    pass

def inner():
    yield
    return func1

def outer():
    handler = yield from inner()
    handler()

for _ in outer():
    pass
