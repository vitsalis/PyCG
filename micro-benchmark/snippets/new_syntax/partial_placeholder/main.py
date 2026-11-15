import functools

def divide(a, b):
    return a / b

halve = functools.partial(divide, functools.Placeholder, 2)
halve(10)
