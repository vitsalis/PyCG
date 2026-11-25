def func1():
    pass

def func2():
    pass

def gen():
    yield func1
    yield func2

first, second = gen()
second()
