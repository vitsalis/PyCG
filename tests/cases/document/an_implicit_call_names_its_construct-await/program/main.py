class Waits:
    def __await__(self): yield
async def f():
    await Waits()
