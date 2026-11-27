
import collections.abc
def f(): pass
class Items(collections.abc.Iterator):
    def __next__(self): return f
class Stream(collections.abc.AsyncIterator):
    async def __anext__(self): return f
def items(source):
    for item in source:
        item()
async def stream(source):
    async for item in source.__aiter__():
        item()
items(Items())
items(Items().__iter__())
stream(Stream())
