
import ext
def f(): pass
def g(): pass

async def work():
    pass
def use():
    pending = work()
    try:
        pending.cancel()
    except AttributeError:
        pass
    pending.close()
