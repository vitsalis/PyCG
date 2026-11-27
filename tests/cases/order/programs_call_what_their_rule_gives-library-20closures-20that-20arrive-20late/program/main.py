
import contextlib, functools
def deco():
    return LATE
@deco()
def managed():
    yield
@functools.lru_cache(maxsize=SIZE)
def cached(n): pass
def use():
    with managed():
        cached(1)
SIZE = 3
LATE = contextlib.contextmanager
