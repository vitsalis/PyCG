@dec
@dec2(1)
async def f(a, /, b=1, *args: int, c, d=2, **kw) -> int:
    return (yield)
