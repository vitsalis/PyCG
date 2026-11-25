def func1():
    return 1

def func2():
    return 2

results = {f() for f in (func1, func2)}
