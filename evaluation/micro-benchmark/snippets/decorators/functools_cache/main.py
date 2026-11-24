import functools


@functools.cache
def square(n):
    return n * n


square(3)
square(3)
