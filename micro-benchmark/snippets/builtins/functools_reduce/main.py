import functools

def add(a, b):
    return a + b

functools.reduce(add, [1, 2, 3])
