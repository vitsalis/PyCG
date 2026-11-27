data = [y := i for i in range(3) if (z := i)]
sums = {k: v for k, v in pairs for w in v if w}
gen = (lambda: n for n in data)
sets = {a for a in data}
async def coroutine():
    values = [await x async for x in source]
    lazy = (await y for y in source)
    for item in values:
        await item
    while True:
        del item
        break
    else:
        done = 1
def generator():
    yield from data
    first = lambda: (yield)
f(lambda: 1, lambda: 2)
