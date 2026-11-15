import asyncio

def side_effect():
    pass

async def task():
    side_effect()

async def start():
    pending = task()
    pending.close()

asyncio.run(start())
