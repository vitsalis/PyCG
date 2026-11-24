def func1():
    pass

def func2():
    pass

def func3():
    pass

match (func1, func2, func3):
    case [first, *rest]:
        rest[-1]()
