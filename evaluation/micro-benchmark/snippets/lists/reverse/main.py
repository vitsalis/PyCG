def func1():
    pass

def func2():
    pass

handlers = [func1, func2]
handlers.reverse()
handlers[0]()
