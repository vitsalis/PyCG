def func1():
    pass

def register(registry):
    registry.append(func1)

handlers = []
register(handlers)
handlers[0]()
