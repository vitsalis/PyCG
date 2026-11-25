import asyncio

async def numbers():
    yield 1
    yield 2

async def double(n):
    return n * 2

async def start():
    return [await double(n) async for n in numbers()]

asyncio.run(start())
