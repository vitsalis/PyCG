import asyncio

async def fetch():
    return 1

async def process():
    return await fetch()

asyncio.run(process())
