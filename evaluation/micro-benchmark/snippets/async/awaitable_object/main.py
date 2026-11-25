import asyncio

async def compute():
    pass

class Deferred:
    def __await__(self):
        return compute().__await__()

async def start():
    await Deferred()

asyncio.run(start())
