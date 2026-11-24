import asyncio

async def fetch():
    pass

async def wait_for_it(coro):
    await coro

async def start():
    pending = fetch()
    await wait_for_it(pending)

asyncio.run(start())
