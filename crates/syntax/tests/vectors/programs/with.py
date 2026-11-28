with (open(a) as f, open(b)):
    pass
async def g():
    async with x as (y, z):
        async for i in j:
            await i
