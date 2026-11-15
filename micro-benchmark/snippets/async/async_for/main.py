import asyncio

class Countdown:
    def __init__(self, n):
        self.n = n

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.n == 0:
            raise StopAsyncIteration
        self.n -= 1
        return self.n

async def start():
    async for _ in Countdown(2):
        pass

asyncio.run(start())
