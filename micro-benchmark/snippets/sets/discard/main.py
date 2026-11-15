def func1():
    pass

def func2():
    pass

handlers = {func1, func2}
handlers.discard(func1)
for f in handlers:
    f()
