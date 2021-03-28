def func4():
    pass

def func2():
    pass

def func3():
    pass

def func(a, b, c):
    a()
    b()
    c()

func(func2, c=func4, b=func3)
