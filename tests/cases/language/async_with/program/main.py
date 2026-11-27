
class Session:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *exc):
        pass
    def get(self): pass
async def use():
    async with Session() as session:
        session.get()
