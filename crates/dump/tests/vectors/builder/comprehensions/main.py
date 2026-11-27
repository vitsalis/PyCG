def gen(items):
    yield from items
    sent = yield items
    return [i for i in items if i], {i for i in items}, {i: j for i, j in items}, (i for i in items), sorted(i for i in items)
async def agen(items):
    return [i async for i in items], await items
