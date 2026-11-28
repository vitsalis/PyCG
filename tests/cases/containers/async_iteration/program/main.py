
def f(): pass
def g(): pass
class Stream:
    def __aiter__(self):
        return self
    async def __anext__(self):
        return f
async def produce():
    yield g
async def use():
    async for item in Stream():
        item()
    async for item in produce():
        item()
