def func1():
    pass

def registry():
    pass

registry.handler = func1
registry.handler()
