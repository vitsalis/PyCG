def func1():
    pass

def func2():
    pass

handlers = [func1, func2]
del handlers[0]
handlers[0]()
