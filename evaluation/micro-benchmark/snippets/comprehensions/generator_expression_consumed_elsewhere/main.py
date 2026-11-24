def func1():
    return 1

def func2():
    return 2

def consume(values):
    total = 0
    for v in values:
        total += v
    return total

consume(f() for f in (func1, func2))
