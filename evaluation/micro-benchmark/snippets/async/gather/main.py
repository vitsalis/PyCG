import asyncio

async def first():
    pass

async def second():
    pass

async def start():
    await asyncio.gather(first(), second())

asyncio.run(start())
