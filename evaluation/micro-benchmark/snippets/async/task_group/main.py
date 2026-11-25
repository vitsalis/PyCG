import asyncio

async def work():
    pass

async def start():
    async with asyncio.TaskGroup() as group:
        group.create_task(work())

asyncio.run(start())
