
import functools
@functools.lru_cache
def bare(n): pass
@functools.lru_cache(maxsize=32)
def sized(n): pass
def use():
    bare(1)
