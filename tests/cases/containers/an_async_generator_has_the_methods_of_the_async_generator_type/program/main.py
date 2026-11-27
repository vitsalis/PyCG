
def f(): pass
async def produce():
    yield f
async def use():
    g = produce()
    async for item in g.__aiter__():
        item()
    await g.__anext__()
    await g.asend(None)
    await g.athrow(ValueError)
    await g.aclose()
    g.__next__()
    g.send(None)
