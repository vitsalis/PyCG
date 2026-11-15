import asyncio

async def start():
    pass

loop = asyncio.new_event_loop()
loop.run_until_complete(start())
loop.close()
