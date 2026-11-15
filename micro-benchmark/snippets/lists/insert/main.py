def func1():
    pass

def func2():
    pass

handlers = [func1]
handlers.insert(0, func2)
handlers[0]()
