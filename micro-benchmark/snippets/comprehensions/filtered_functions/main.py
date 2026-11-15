def func1():
    pass

def func2():
    pass

def func3():
    pass

handlers = [f for f in (func1, func2, func3) if f is not func2]
for h in handlers:
    h()
