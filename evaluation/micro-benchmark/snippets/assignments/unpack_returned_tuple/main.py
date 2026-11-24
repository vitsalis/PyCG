def func1():
    pass

def func2():
    pass

def pair():
    return func1, func2

first, second = pair()
second()
