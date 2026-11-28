import functools


@functools.lru_cache(maxsize=None)
def cached(value):
    return value


def plain(value):
    return value


cached(1)
wrapped = functools.lru_cache(maxsize=2)(plain)
wrapped(2)
