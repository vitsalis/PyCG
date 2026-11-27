
import ext
def f(): pass
def g(): pass

class Box:
    def __await__(self):
        yield
        return g
    def __call__(self):
        pass
async def make():
    return Box()
async def awaited():
    box = await make()
    box()
def not_awaited():
    coroutine = make()
    coroutine()
    coroutine.close()
