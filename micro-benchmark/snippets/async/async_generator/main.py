import asyncio

def first():
    pass

def second():
    pass

async def handlers():
    yield first
    yield second

async def start():
    async for handler in handlers():
        handler()

asyncio.run(start())
