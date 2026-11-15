def func1():
    pass

def func2():
    pass

handlers = [func1]
snapshot = handlers.copy()
handlers[0] = func2
snapshot[0]()
