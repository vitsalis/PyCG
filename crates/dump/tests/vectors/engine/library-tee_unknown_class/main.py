import itertools


def handler():
    pass


first, second = itertools.tee([handler])
first.__sizeof__()
next(second)()
