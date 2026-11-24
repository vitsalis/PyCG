def func_b():
    pass

def func_a():
    pass

handlers = [func_b, func_a]
handlers.sort(key=lambda f: f.__name__)
handlers[0]()
