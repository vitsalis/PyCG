
def a(): pass
def b(): pass
def c(): pass
def d(): pass
async def e(): pass
def g(): pass
async def make(): return g
async def run(flag):
    (a if flag else b)()
    (flag or c)()
    if (picked := d):
        picked()
    await e()
    (await make())()
