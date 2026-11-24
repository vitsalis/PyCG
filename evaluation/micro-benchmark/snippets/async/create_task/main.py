import asyncio

def helper():
    pass

async def work():
    helper()

async def start():
    task = asyncio.create_task(work())
    await task

asyncio.run(start())
