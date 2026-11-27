
import ext
def f(): pass
def g(): pass

class Deferred:
    def __await__(self):
        yield
        return f
    def __call__(self):
        pass
async def use():
    handler = await Deferred()
    handler()
