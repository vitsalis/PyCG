
import asyncio
async def use():
    async with asyncio.timeout(1) as t:
        t.expired()
    reader, writer = await asyncio.open_connection("h", 1)
    async for line in reader:
        line.decode()
