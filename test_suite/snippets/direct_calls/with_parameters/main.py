def func():
    pass

def func2(a):
    return a

def func3():
    return func2

func3()(func)()
