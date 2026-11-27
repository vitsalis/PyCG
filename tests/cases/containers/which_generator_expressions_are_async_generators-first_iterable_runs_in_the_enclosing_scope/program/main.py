
def f(): pass
async def wait(x):
    return x
async def produce():
    yield f
async def use():
    g = (x for x in await wait([f]))
    g.close()
    await g.aclose()
    g.__aiter__()
