def func1():
    pass

def func2():
    pass

def build():
    handlers = []
    for f in (func1, func2):
        handlers.append(lambda f=f: f())
    return handlers

build()[0]()
