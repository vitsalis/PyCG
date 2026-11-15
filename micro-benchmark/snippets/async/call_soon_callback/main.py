import asyncio

def tick():
    pass

async def start():
    loop = asyncio.get_running_loop()
    loop.call_soon(tick)
    await asyncio.sleep(0)

asyncio.run(start())
