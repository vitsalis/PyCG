def func1():
    pass

def func2():
    pass

def func3():
    pass

a = [func1, func2, func3]

a[0]()
a[1]()
a[2]()

def func4():
    pass

b = [None]
b[0] = func4

b[0]()
