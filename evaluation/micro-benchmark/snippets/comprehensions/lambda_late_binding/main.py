def func1():
    pass

def func2():
    pass

handlers = [lambda: g() for g in (func1, func2)]
handlers[0]()
