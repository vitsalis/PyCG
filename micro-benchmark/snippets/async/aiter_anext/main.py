import asyncio

async def ticks():
    yield 1

async def start():
    iterator = aiter(ticks())
    await anext(iterator)

asyncio.run(start())
