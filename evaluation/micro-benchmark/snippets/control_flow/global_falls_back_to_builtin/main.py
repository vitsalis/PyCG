callable = lambda value: True


def check(value):
    return callable(value)


check(1)
del callable
check(2)
