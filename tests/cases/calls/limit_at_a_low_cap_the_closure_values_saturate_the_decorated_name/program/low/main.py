
from functools import lru_cache
@lru_cache(maxsize=32)
def f(): pass
f()
