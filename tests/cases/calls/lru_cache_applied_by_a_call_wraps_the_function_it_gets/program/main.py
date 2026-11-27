
import functools
def work(n):
    return {}
cached = functools.lru_cache(1024)(work)
def use():
    cached(1).items()
