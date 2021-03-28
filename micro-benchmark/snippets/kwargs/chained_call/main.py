def func3():
    pass

def func2(a=func3):
    a()

def func1(a, b=func2):
    a(b)

func1(a=func2, b=func3)
