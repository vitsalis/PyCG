def func1():
    pass

def func2():
    pass

def target(first, second=None):
    first()
    second()

def wrapper(*args, **kwargs):
    target(*args, **kwargs)

wrapper(func1, second=func2)
