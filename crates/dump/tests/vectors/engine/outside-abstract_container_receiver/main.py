import itertools


def handler():
    pass


first, second = itertools.tee([handler])
first.__next__()()
first.__sizeof__()
