
import asyncio
class Result:
    def done(self): pass
class Later:
    def __await__(self):
        yield
        return 1
async def make():
    return Result()
async def use():
    (await asyncio.wait_for(make(), 1)).done()
    (await asyncio.sleep(0, Result())).done()
    await Later()
asyncio.run(use())
