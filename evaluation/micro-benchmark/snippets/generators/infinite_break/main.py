def func1():
    pass

def func2():
    pass

def alternate():
    while True:
        yield func1
        yield func2

for f in alternate():
    f()
    break
