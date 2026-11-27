
import contextlib
import functools
from contextlib import asynccontextmanager, contextmanager

@contextmanager
def managed():
    yield

@asynccontextmanager
async def amanaged():
    yield

@functools.lru_cache(maxsize=32)
def square(n):
    return n * n

class C:
    @contextlib.contextmanager
    def cm(self):
        yield

    @functools.lru_cache(maxsize=None, typed=True)
    def m(self):
        pass

    def run(self):
        with self.cm():
            self.m()

def use():
    with managed():
        pass
    square(2)
    square.cache_clear()
    managed().__enter__()

async def ause():
    async with amanaged():
        pass
