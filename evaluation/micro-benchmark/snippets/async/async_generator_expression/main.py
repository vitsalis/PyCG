import asyncio

def first():
    pass

async def wait(value):
    return value

async def start():
    handlers = (await wait(handler) for handler in [first])
    async for handler in handlers.__aiter__():
        handler()
    await handlers.aclose()

asyncio.run(start())
