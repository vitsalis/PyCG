
import lib
async def use():
    x = await lib.fetch()
    x.run()
    async with lib.session() as s:
        s.get()
    async for item in lib.stream():
        item.run()
