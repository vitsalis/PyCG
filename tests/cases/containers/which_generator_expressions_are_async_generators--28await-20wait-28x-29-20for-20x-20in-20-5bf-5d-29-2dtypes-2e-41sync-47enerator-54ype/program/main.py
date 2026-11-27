
def f(): pass
async def wait(x):
    return x
async def produce():
    yield f
async def use():
    g = (await wait(x) for x in [f])
    g.close()
    await g.aclose()
    g.__aiter__()
