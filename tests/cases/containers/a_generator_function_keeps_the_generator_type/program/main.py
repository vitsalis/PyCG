
def f(): pass
def produce():
    yield f
async def use():
    g = produce()
    for item in g.__iter__():
        item()
    g.close()
    g.aclose()
