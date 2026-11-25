import functools


def square(n):
    return n * n


cached = functools.lru_cache(16)(square)
cached(3)
