def func1():
    pass

def func2():
    pass

def inner():
    yield func1

def outer():
    yield from inner()
    yield func2

for f in outer():
    f()
