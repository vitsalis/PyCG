def func1():
    return 1

def func2():
    return 2

total = sum(f() for f in (func1, func2))
