import asyncio

def parse():
    pass

async def load():
    parse()

def run_sync():
    asyncio.run(load())

run_sync()
