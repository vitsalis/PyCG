def func(a):
    a()

def func2():
    return func3

def func3():
    pass

func(func2())
