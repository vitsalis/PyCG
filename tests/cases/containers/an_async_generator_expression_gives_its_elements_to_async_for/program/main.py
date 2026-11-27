
def f(): pass
async def wait(x):
    return x
async def use():
    async for item in (await wait(x) for x in [f]).__aiter__():
        item()
