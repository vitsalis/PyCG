
import ext
def f(): pass
def g(): pass

class Session:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *exc):
        pass
    def get(self): pass
class Items:
    def __aiter__(self):
        return self
    async def __anext__(self):
        return f
async def use():
    async with Session() as session:
        session.get()
    async for item in Items():
        item()
