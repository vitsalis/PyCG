import functools


def logged(func):
    @functools.wraps(func)
    def wrapper(*args):
        return func(*args)

    return wrapper


@logged
def add(a, b):
    return a + b


add(1, 2)
