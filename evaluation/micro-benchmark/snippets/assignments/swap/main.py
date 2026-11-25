def func1():
    pass

def func2():
    pass

a, b = func1, func2
a, b = b, a
a()
