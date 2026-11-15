import asyncio
from collections.abc import AsyncIterator

def first():
    pass

class Once(AsyncIterator):
    def __init__(self):
        self.done = False

    async def __anext__(self):
        if self.done:
            raise StopAsyncIteration
        self.done = True
        return first

async def start():
    async for handler in Once():
        handler()

asyncio.run(start())
