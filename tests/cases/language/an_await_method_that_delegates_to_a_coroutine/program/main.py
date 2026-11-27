
import ext
def f(): pass
def g(): pass

async def compute():
    return f
class Deferred:
    def __await__(self):
        return compute().__await__()
async def use():
    (await ext.fetch())()
    await Deferred()
