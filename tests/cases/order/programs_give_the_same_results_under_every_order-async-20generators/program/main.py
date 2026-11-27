
def f(): pass
async def wait(x): return x
async def produce():
    yield f
async def use():
    for g in [produce(), (await wait(x) for x in [f]), (x async for x in produce())]:
        async for h in g.__aiter__():
            h()
        await g.aclose()
