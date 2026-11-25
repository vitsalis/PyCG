def func1():
    pass

def func2():
    pass

def func3():
    pass

def func4():
    pass

def func5():
    pass

def run(a, /, b, *args, c, **kwargs):
    a()
    b()
    args[0]()
    c()
    kwargs["d"]()

run(func1, func2, func3, c=func4, d=func5)
