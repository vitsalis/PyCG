import asyncio

class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def query(self):
        pass

async def start():
    async with Session() as session:
        await session.query()

asyncio.run(start())
