
import asyncio
class Result:
    def done(self): pass
async def main():
    return Result()
async def later():
    return Result()
asyncio.run(main()).done()
def use():
    asyncio.Runner().run(later()).done()
