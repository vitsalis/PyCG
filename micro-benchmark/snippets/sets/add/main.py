def func1():
    pass

handlers = set()
handlers.add(func1)
for f in handlers:
    f()
