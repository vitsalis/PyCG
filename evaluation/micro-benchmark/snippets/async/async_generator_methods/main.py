import asyncio

def first():
    pass

def cleanup():
    pass

async def ticks():
    try:
        yield first
        yield first
    finally:
        cleanup()

async def start():
    stream = ticks()
    async for handler in stream.__aiter__():
        handler()
        break
    await stream.__anext__()
    await stream.aclose()

asyncio.run(start())
