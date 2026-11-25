def func1():
    pass

def func2():
    pass

def func3():
    pass

handlers = [func1, func2]
handlers[:1] = [func3]
handlers[0]()
