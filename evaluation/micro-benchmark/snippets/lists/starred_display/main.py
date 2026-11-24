def func1():
    pass

def func2():
    pass

def func3():
    pass

first = [func1]
second = (func2, func3)
combined = [*first, *second]
combined[2]()
