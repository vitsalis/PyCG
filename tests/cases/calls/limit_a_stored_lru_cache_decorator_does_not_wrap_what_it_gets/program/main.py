
import functools
def work(n):
    return {}
cache = functools.lru_cache(1024)
cached = cache(work)
def use():
    cached(1)
