def func1():
    pass

def func2():
    pass

def make(f):
    def inner():
        f()
    return inner

first = make(func1)
second = make(func2)
first()
